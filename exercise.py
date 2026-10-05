"""Command-line driver for a disposable local exercise."""

import argparse
import json
import math
from pathlib import Path
import tempfile

from fixture import add_changes, create_history, validate_apps
from pipeline import pipeline
from workflow import execute_pipeline
from simulation import Simulation, file_lock


def execute(directory, speed, *, observer=None, on_ready=None, changes=None,
            revisions=None):
    if changes is not None and revisions is not None:
        raise ValueError("changes and revisions are mutually exclusive")
    if changes is not None:
        changes = [validate_apps(apps) for apps in changes]
    if revisions is not None:
        revisions = list(revisions)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    manifest = directory / "fixture.json"
    with file_lock(directory / "fixture.lock"):
        if manifest.exists():
            history = json.loads(manifest.read_text())
        else:
            history = {"revisions": create_history(directory / "repo")}
            manifest.write_text(json.dumps(history, indent=2) + "\n")
        if changes is not None:
            revisions = []
            for apps in changes:
                revision = add_changes(directory / "repo", apps)
                history["revisions"].append(revision)
                manifest.write_text(json.dumps(history, indent=2) + "\n")
                revisions.append(revision)
        elif revisions is None:
            revisions = list(history["revisions"])
    if on_ready is not None:
        on_ready(revisions)
    if observer is None:
        print(f"Fixture: {directory}", flush=True)
        for revision in revisions:
            print(f"Revision: {revision}", flush=True)

    def show(event):
        app = event.get("app", event.get("task", ""))
        hit = f" cache_hit={event['cache_hit']}" if "cache_hit" in event else ""
        print(f"{event['revision'][:12]} {event['kind']} {app}{hit}", flush=True)

    sim = Simulation(directory / "repo", directory / "state", speed=speed,
                     observer=show if observer is None else observer)
    execute_pipeline(sim, pipeline, revisions)
    if observer is None:
        print(f"Release: {sim.state / 'release.json'}", flush=True)
    return sim


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path,
                        help="retain fixture and state here; use a directory outside the checkout")
    parser.add_argument("--speed", type=float, default=1, help="delay multiplier (default: 1)")
    parser.add_argument("--plain", action="store_true", help="run without the terminal UI")
    args = parser.parse_args()
    if not math.isfinite(args.speed) or args.speed < 0:
        parser.error("--speed must be finite and nonnegative")

    if args.plain:
        launch = execute
    else:
        try:
            from tui import BuildApp
        except ModuleNotFoundError as error:
            if error.name != "textual" and not (error.name or "").startswith("textual."):
                raise
            parser.error("Textual is required for the terminal UI. Install locally with "
                         "`python3 -m venv .venv` and "
                         "`.venv/bin/python -m pip install -r requirements.txt`, then run "
                         "`.venv/bin/python exercise.py`; or use --plain.")

        def launch(directory, speed):
            app = BuildApp(directory, speed)
            app.run()
            if app.failed or app.return_code:
                raise SystemExit(app.return_code or 1)

    if args.directory:
        launch(args.directory.resolve(), args.speed)
    else:
        with tempfile.TemporaryDirectory(prefix="build-exercise-") as directory:
            launch(Path(directory), args.speed)


if __name__ == "__main__":
    main()
