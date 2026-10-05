import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from textual.widgets import Button, Checkbox, DataTable, RichLog, Static

from exercise import execute
from simulation import APPS
from tui import BuildApp, NewChanges, SourceCheckbox, Welcome
from workflow import Build, Deploy, Pipeline


starter_pipeline = Pipeline(
    pool="pipeline",
    tasks=[
        Build("zorch"),
        Build("greeb"),
        Build("blerg", needs=["greeb"]),
        Deploy("release", needs=["zorch", "greeb", "blerg"]),
    ],
)


class TuiTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        pipeline_patch = patch("exercise.pipeline", starter_pipeline)
        pipeline_patch.start()
        self.addCleanup(pipeline_patch.stop)
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name) / "fixture"

    async def finished(self, app, pilot):
        for _ in range(200):
            if not app.running:
                return
            await pilot.pause(0.025)
        self.fail("UI worker did not finish")

    async def test_welcome_waits_for_choice_and_primary_is_visible(self):
        app = BuildApp(self.directory, 0)
        with patch("tui.execute") as mocked:
            async with app.run_test(size=(80, 24)) as pilot:
                self.assertIsInstance(app.screen, Welcome)
                button = app.screen.query_one("#run-example", Button)
                self.assertEqual(button.label.plain, "Run example")
                self.assertIs(app.focused, button)
                self.assertTrue(button.visible)
                self.assertGreater(button.region.width, 0)
                self.assertLessEqual(button.region.bottom, 24)
                instructions = "\n".join(str(widget.render()) for widget in app.screen.query(Static))
                for text in ("zorch, greeb, and blerg", "like CI", "pipeline.py",
                             "revisions overlap", "deployments one at a time",
                             "local and simulated", "no actual deployment",
                             "nothing changes in your checkout", "initial sources",
                             "greeb change", "zorch change"):
                    self.assertIn(text, instructions)
                self.assertNotIn("depends", instructions)
                self.assertNotIn("invalidat", instructions)
                await pilot.press("r", "n")
                app.action_rerun()
                app.action_new_changes()
                self.assertIsInstance(app.screen, Welcome)
                self.assertIn("Ready to run", str(app._status.render()))
                self.assertFalse(app.running)
                self.assertIsNone(app._thread)
                mocked.assert_not_called()
                self.assertFalse(self.directory.exists())

    async def test_choose_changes_first_submits_only_selected_revisions(self):
        app = BuildApp(self.directory, 0)
        with patch("tui.execute", wraps=execute) as mocked:
            async with app.run_test(size=(120, 35)) as pilot:
                await pilot.click("#choose-changes")
                self.assertIsInstance(app.screen, NewChanges)
                mocked.assert_not_called()
                self.assertFalse(self.directory.exists())
                await pilot.click("#change-blerg")
                await pilot.click("#queue-commit")
                await pilot.click("#change-zorch")
                await pilot.click("#run-pipeline")
                await self.finished(app, pilot)
                self.assertFalse(app.failed)
                self.assertNotIsInstance(app.screen, Welcome)
                self.assertEqual(mocked.call_count, 1)
                self.assertEqual(mocked.call_args.kwargs["changes"], [["blerg"], ["zorch"]])
                self.assertEqual(len(app._last_revisions), 2)
                executed = {event["revision"] for event in app.simulation.events()}
                self.assertEqual(executed, set(app._last_revisions))

    async def test_cancel_first_changes_returns_welcome_without_work(self):
        app = BuildApp(self.directory, 0)
        with patch("tui.execute") as mocked:
            async with app.run_test(size=(120, 35)) as pilot:
                for cancel in ("button", "escape"):
                    await pilot.click("#choose-changes")
                    await pilot.click("#change-greeb")
                    await pilot.click("#queue-commit")
                    if cancel == "button":
                        await pilot.click("#cancel")
                    else:
                        await pilot.press("escape")
                    self.assertIsInstance(app.screen, Welcome)
                    self.assertEqual(app.focused.id, "run-example")
                    self.assertFalse(self.directory.exists())
                    mocked.assert_not_called()
                    self.assertIsNone(app._thread)

    async def test_welcome_quit_does_no_work(self):
        for quit_choice in ("button", "q", "ctrl+c", "escape"):
            with self.subTest(quit_choice=quit_choice), patch("tui.execute") as mocked:
                app = BuildApp(self.directory, 0)
                async with app.run_test() as pilot:
                    if quit_choice == "button":
                        await pilot.click("#welcome-quit")
                    else:
                        await pilot.press(quit_choice)
                    self.assertFalse(app.is_running)
                mocked.assert_not_called()
                self.assertFalse(self.directory.exists())
                self.assertIsNone(app._thread)

    async def test_retained_history_label_and_reuse(self):
        await asyncio.to_thread(execute, self.directory, 0, changes=[["zorch"]],
                                observer=lambda event: None, on_ready=lambda revisions: None)
        manifest = (self.directory / "fixture.json").read_bytes()
        app = BuildApp(self.directory, 0)
        with patch("tui.execute", wraps=execute) as mocked:
            async with app.run_test() as pilot:
                self.assertIsInstance(app.screen, Welcome)
                button = app.screen.query_one("#run-example", Button)
                self.assertEqual(button.label.plain, "Run existing history")
                instructions = "\n".join(str(widget.render()) for widget in app.screen.query(Static))
                self.assertIn("saved history and completed cache", instructions)
                self.assertNotIn("initial sources", instructions)
                mocked.assert_not_called()
                await pilot.click("#run-example")
                await self.finished(app, pilot)
                self.assertFalse(app.failed)
                self.assertEqual(len(app._last_revisions), 4)
                self.assertEqual((self.directory / "fixture.json").read_bytes(), manifest)

    async def test_completion_and_warm_rerun(self):
        app = BuildApp(self.directory, 0)
        async with app.run_test(size=(120, 30)) as pilot:
            await pilot.press("enter")
            await self.finished(app, pilot)
            self.assertFalse(app.failed)
            self.assertIsNotNone(app.simulation)
            self.assertEqual(app.query_one(DataTable).row_count, 3)
            self.assertTrue(all(row["release"] == "finished" for row in app.states.values()))
            self.assertIn("Finished", str(app.query_one("#status", Static).render()))
            await pilot.press("r")
            await self.finished(app, pilot)
            builds = [event for event in app.simulation.events()
                      if event["kind"] == "build_finished"]
            self.assertEqual(len(builds), 18)
            self.assertTrue(all(event["cache_hit"] for event in builds[-9:]))
            self.assertTrue(all(row[app_name] == "finished (cache hit)"
                                for row in app.states.values() for app_name in APPS))

    async def test_new_changes_cancel_and_escape_preserve_run(self):
        app = BuildApp(self.directory, 0)
        async with app.run_test(size=(120, 35)) as pilot:
            await pilot.press("enter")
            await self.finished(app, pilot)
            original_revisions = app._last_revisions.copy()
            original_manifest = (self.directory / "fixture.json").read_bytes()
            original_events = app.simulation.events()
            for cancel in ("button", "escape"):
                await pilot.press("n")
                self.assertIsInstance(app.screen, NewChanges)
                await pilot.click("#change-greeb")
                await pilot.click("#queue-commit")
                await pilot.press("r", "n")
                self.assertFalse(app.running)
                if cancel == "button":
                    await pilot.click("#cancel")
                else:
                    await pilot.press("escape")
                self.assertNotIsInstance(app.screen, NewChanges)
                self.assertEqual(app._last_revisions, original_revisions)
                self.assertEqual((self.directory / "fixture.json").read_bytes(), original_manifest)
                self.assertEqual(app.simulation.events(), original_events)
                self.assertEqual(app.query_one(DataTable).row_count, 3)
            self.assertEqual(app.directory, self.directory)
        self.assertTrue(self.directory.exists())

    async def test_new_changes_checkbox_rendering_and_instructions(self):
        app = BuildApp(self.directory, 0)
        async with app.run_test(size=(120, 35)) as pilot:
            await pilot.press("enter")
            await self.finished(app, pilot)
            await pilot.press("n")
            modal = app.screen
            self.assertIsInstance(modal, NewChanges)
            self.assertEqual(modal.query_one("#queue-commit", Button).label.plain,
                             "Queue commit")
            self.assertEqual(modal.query_one("#run-pipeline", Button).label.plain,
                             "Run pipeline")
            instructions = "\n".join(str(widget.render()) for widget in modal.query(Static))
            self.assertIn("Check a box to simulate Git changes for that app in the monorepo.",
                          instructions)
            self.assertIn("The selected apps will change together in one new commit.",
                          instructions)
            self.assertIn("Queue commit lets you prepare another commit before running.",
                          instructions)
            self.assertIn("Run pipeline submits queued commits and any checked changes.",
                          instructions)
            self.assertNotIn("invalidat", instructions.lower())
            checkbox = modal.query_one("#change-greeb", SourceCheckbox)
            self.assertFalse(checkbox.value)
            self.assertEqual(checkbox._button.plain,
                             f"{checkbox.BUTTON_LEFT} {checkbox.BUTTON_RIGHT}")
            await pilot.click("#change-greeb")
            self.assertTrue(checkbox.value)
            self.assertEqual(checkbox._button.plain,
                             f"{checkbox.BUTTON_LEFT}X{checkbox.BUTTON_RIGHT}")
            await pilot.click("#change-greeb")
            self.assertFalse(checkbox.value)
            self.assertEqual(checkbox._button.plain,
                             f"{checkbox.BUTTON_LEFT} {checkbox.BUTTON_RIGHT}")
            await pilot.press("escape")

    async def test_new_changes_batch_and_warm_rerun(self):
        app = BuildApp(self.directory, 0)
        async with app.run_test(size=(120, 35)) as pilot:
            await pilot.press("enter")
            await self.finished(app, pilot)
            history = app._last_revisions.copy()
            await pilot.press("n")
            await pilot.click("#change-zorch")
            await pilot.click("#queue-commit")
            self.assertEqual(app.screen.batch, [["zorch"]])
            self.assertTrue(all(not checkbox.value for checkbox in app.screen.query(Checkbox)))
            self.assertIn("1. zorch", str(app.screen.query_one("#batch-summary", Static).render()))
            await pilot.click("#change-greeb")
            summary = str(app.screen.query_one("#selection-summary", Static).render())
            self.assertIn("Next commit: greeb", summary)
            self.assertNotIn("invalidat", summary.lower())
            self.assertFalse(app.screen.query_one("#change-blerg", Checkbox).value)
            await pilot.click("#run-pipeline")
            await self.finished(app, pilot)
            self.assertFalse(app.failed)
            batch = app._last_revisions.copy()
            self.assertEqual(len(batch), 2)
            self.assertTrue(set(batch).isdisjoint(history))
            self.assertEqual(app.query_one(DataTable).row_count, 2)
            self.assertEqual(json.loads((self.directory / "fixture.json").read_text())["revisions"],
                             history + batch)
            builds = [event for event in app.simulation.events()
                      if event["kind"] == "build_finished" and event["revision"] in batch]
            self.assertEqual(len(builds), 6)
            hits = {(event["revision"], event["app"]): event["cache_hit"] for event in builds}
            self.assertEqual([hits[batch[0], name] for name in APPS], [False, True, True])
            self.assertEqual([hits[batch[1], name] for name in APPS], [True, False, False])
            await pilot.press("r")
            await self.finished(app, pilot)
            self.assertFalse(app.failed)
            self.assertEqual(app._last_revisions, batch)
            self.assertEqual(app.query_one(DataTable).row_count, 2)
            self.assertTrue(all(row[name] == "finished (cache hit)"
                                for row in app.states.values() for name in APPS))
            self.assertEqual(json.loads((self.directory / "fixture.json").read_text())["revisions"],
                             history + batch)
            self.assertEqual(app.directory, self.directory)

    async def test_run_queued_changes_does_not_add_empty_selection(self):
        app = BuildApp(self.directory, 0)
        async with app.run_test(size=(120, 35)) as pilot:
            await pilot.press("enter")
            await self.finished(app, pilot)
            with patch("tui.execute", wraps=execute) as mocked:
                await pilot.press("n")
                await pilot.click("#change-blerg")
                await pilot.click("#queue-commit")
                await pilot.click("#run-pipeline")
                await self.finished(app, pilot)
                self.assertEqual(mocked.call_args.kwargs["changes"], [["blerg"]])
                self.assertEqual(len(app._last_revisions), 1)
                self.assertFalse(app.failed)

    async def test_run_empty_selection_creates_empty_commit(self):
        app = BuildApp(self.directory, 0)
        async with app.run_test(size=(120, 35)) as pilot:
            await pilot.press("enter")
            await self.finished(app, pilot)
            history = app._last_revisions.copy()
            with patch("tui.execute", wraps=execute) as mocked:
                await pilot.press("n")
                await pilot.click("#run-pipeline")
                await self.finished(app, pilot)
                self.assertEqual(mocked.call_args.kwargs["changes"], [[]])
            self.assertFalse(app.failed)
            self.assertEqual(len(app._last_revisions), 1)
            self.assertNotIn(app._last_revisions[0], history)
            self.assertTrue(all(row[name] == "finished (cache hit)"
                                for row in app.states.values() for name in APPS))

    async def test_pipeline_events_and_blocked_tasks(self):
        app = BuildApp(self.directory, 0)
        async with app.run_test(size=(120, 35)) as pilot:
            await pilot.press("enter")
            await self.finished(app, pilot)
            revision = app._last_revisions[0]
            original = app.states[revision].copy()
            for kind in ("pipeline_waiting", "pipeline_started", "pipeline_finished"):
                app._observe(dict(revision=revision, kind=kind, pipeline="builds"))
                self.assertEqual(app.states[revision], original)
            app._observe(dict(revision=revision, kind="deploy_requested"))
            self.assertEqual(app.states[revision]["release"], "ready")
            for task, column in (("blerg", "blerg"), ("deploy", "release")):
                app._observe(dict(revision=revision, kind="task_blocked", task=task))
                self.assertEqual(app.states[revision][column], "blocked")
            blocked = app.states[revision].copy()
            app._observe(dict(revision=revision, kind="task_blocked", task="nested"))
            self.assertEqual(app.states[revision], blocked)
            app._observe(dict(revision=revision, kind="pipeline_failed", pipeline="builds"))
            self.assertTrue(app.failed)
            self.assertEqual(app.states[revision], blocked)
            log = "\n".join(line.text for line in app.query_one(RichLog).lines)
            self.assertIn("task_blocked blerg", log)
            self.assertIn("pipeline_failed", log)

    async def test_worker_failure_visible_and_rerunnable(self):
        app = BuildApp(self.directory, 0)
        with patch("tui.execute", side_effect=RuntimeError("broken fixture")):
            async with app.run_test() as pilot:
                await pilot.press("enter")
                await self.finished(app, pilot)
                self.assertTrue(app.failed)
                self.assertIn("broken fixture", str(app.query_one("#status", Static).render()))
                self.assertTrue(app.query_one(RichLog).lines)
                with patch("tui.execute", execute):
                    await pilot.press("r")
                    await self.finished(app, pilot)
                    self.assertFalse(app.failed)

    async def test_forced_exit_during_start_joins_thread(self):
        release = threading.Event()
        started = threading.Event()
        unmounting = asyncio.Event()
        self.addCleanup(release.set)
        self.directory.mkdir()
        directory = self.directory
        existed_at_completion = []

        class ImmediateExitApp(BuildApp):
            def _start(self):
                super()._start()
                self.exit()

            async def on_unmount(self):
                unmounting.set()
                await super().on_unmount()

        def controlled(directory, speed, *, observer, on_ready):
            started.set()
            if not release.wait(5):
                raise TimeoutError("test release")
            on_ready(["revision"])
            observer(dict(revision="revision", kind="deploy_finished"))
            existed_at_completion.append(directory.exists())
            return object()

        app = ImmediateExitApp(directory, 0)

        async def run():
            async with app.run_test() as pilot:
                await pilot.press("enter")

        with patch("tui.execute", side_effect=controlled), patch.object(
            app, "call_from_thread", side_effect=RuntimeError("App is not running")
        ):
            task = asyncio.create_task(run())
            try:
                await asyncio.wait_for(unmounting.wait(), 5)
                self.assertTrue(started.is_set())
                self.assertTrue(app._thread.is_alive())
                self.assertTrue(app.running)
                self.assertTrue(directory.exists())
                self.assertFalse(task.done())
            finally:
                release.set()
                await asyncio.wait_for(task, 5)
        self.assertFalse(app._thread.is_alive())
        self.assertEqual(existed_at_completion, [True])
        self.assertTrue(directory.exists())

    async def test_forced_exit_while_executing_does_not_block_callbacks(self):
        release = threading.Event()
        started = threading.Event()
        unmounting = asyncio.Event()
        self.addCleanup(release.set)
        existed_at_completion = []

        class ShutdownApp(BuildApp):
            async def on_unmount(self):
                unmounting.set()
                await super().on_unmount()

        def controlled(directory, speed, *, observer, on_ready, revisions):
            self.assertEqual(revisions, app._last_revisions)
            on_ready(["revision"])
            started.set()
            if not release.wait(5):
                raise TimeoutError("test release")
            with ThreadPoolExecutor(max_workers=3) as pool:
                list(pool.map(lambda name: observer(dict(revision="revision", app=name,
                                                         kind="build_finished")), APPS))
            existed_at_completion.append(directory.exists())
            raise RuntimeError("failure during shutdown")

        app = ShutdownApp(self.directory, 0)
        run_thread = None

        async def run():
            nonlocal run_thread
            async with app.run_test() as pilot:
                await pilot.press("enter")
                await self.finished(app, pilot)
                with patch("tui.execute", side_effect=controlled):
                    app.action_rerun()
                    run_thread = app._thread
                    self.assertTrue(await asyncio.to_thread(started.wait, 5))
                    app.exit()

        with patch.object(app, "call_from_thread", side_effect=RuntimeError("App is not running")):
            task = asyncio.create_task(run())
            try:
                await asyncio.wait_for(unmounting.wait(), 10)
                self.assertTrue(app.running)
                self.assertTrue(run_thread.is_alive())
                self.assertTrue(self.directory.exists())
                self.assertFalse(task.done())
            finally:
                release.set()
                await asyncio.wait_for(task, 5)
        self.assertFalse(run_thread.is_alive())
        self.assertEqual(existed_at_completion, [True])
        self.assertTrue(self.directory.exists())

    async def test_states_concurrent_callbacks_and_busy_controls(self):
        release = threading.Event()
        started = threading.Event()
        self.addCleanup(release.set)

        def controlled(directory, speed, *, observer, on_ready):
            on_ready(["revision"])
            observer(dict(revision="revision", app="zorch", kind="build_requested"))
            started.set()
            if not release.wait(10):
                raise TimeoutError("test release")
            with ThreadPoolExecutor(max_workers=3) as pool:
                list(pool.map(lambda name: observer(dict(revision="revision", app=name,
                                                         kind="build_started")), APPS))
            observer(dict(revision="revision", app="zorch", kind="cache_hit"))
            observer(dict(revision="revision", app="greeb", kind="build_failed"))
            observer(dict(revision="revision", app="blerg", kind="build_finished", cache_hit=False))
            observer(dict(revision="revision", kind="deploy_requested"))
            observer(dict(revision="revision", kind="deploy_started"))
            observer(dict(revision="revision", kind="deploy_failed"))
            raise RuntimeError("build failed")

        app = BuildApp(self.directory, 0)
        with patch("tui.execute", side_effect=controlled) as mocked:
            async with app.run_test() as pilot:
                try:
                    await pilot.press("enter")
                    self.assertTrue(await asyncio.to_thread(started.wait, 5))
                    self.assertEqual(app.states["revision"]["zorch"], "waiting (cache lock)")
                    await pilot.press("r", "n", "q", "ctrl+c")
                    self.assertTrue(app.running)
                    self.assertEqual(mocked.call_count, 1)
                    self.assertEqual(app.directory, self.directory)
                finally:
                    release.set()
                await self.finished(app, pilot)
                self.assertTrue(app.failed)
                self.assertEqual(app.states["revision"], {
                    "zorch": "cache hit", "greeb": "failed", "blerg": "finished", "release": "failed",
                })
                await pilot.press("q")


if __name__ == "__main__":
    unittest.main()
