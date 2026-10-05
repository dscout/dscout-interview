# Build concurrency exercise

## Get started

You'll need **Python 3.10+ and Git** on macOS or Linux (including WSL).
The terminal UI uses Textual, installed in a local virtual environment below.
No accounts, Docker, or cloud services. Installing dependencies needs internet
access; running the exercise does not.

Work from your fork or a copy of this repo on the
`devops-challenge/build-concurrency` branch. From the checkout's root, run:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -B exercise.py
.venv/bin/python -B -m unittest discover -s tests -v
```

Dependencies stay inside `.venv/`, not your global Python installation. No
activation is needed; delete `.venv/` to remove them.

The UI opens with a welcome dialog; nothing runs until you choose.
**Run example** submits the supplied three-commit scenario, or **Choose changes**
lets you prepare your own commits first. With a retained run directory, the first
choice becomes **Run existing history**, submitting its saved commits.

During a run, the UI shows each revision's builds, cache hits, and release
alongside a live event log and elapsed time. After a run, press
**r** to rerun the last batch, **n** to choose new simulated changes, or **q**
to quit. These controls are available after the current run finishes.

In **New changes**, check a box to simulate Git changes for that app in the
monorepo. The checked apps change together in one new commit. **Queue commit**
queues that commit and resets the checkboxes so you can prepare another.
**Queue example (3 commits)** adds a no-source-change commit, a `greeb` change,
and a `zorch` change to the queue, using the current repo.
**Run pipeline** submits the queued commits plus any currently checked changes.
With no queued or checked changes, it submits an empty commit with no source
changes. Every revision still needs all three builds or valid cache hits.

The commits are generated automatically and deterministically in the disposable
repo; no Git work is required from you.

Every UI submission reloads `pipeline.py` and starts with fresh simulation state.
**Rerun** replays the same commits so timing improvements reflect your pipeline
edits, not cache entries left by an earlier run. Cache reuse still happens between
commits within a run. Imported helper modules are not automatically reloaded;
restart the UI after editing those.
The default run directory is removed on exit; `--directory` retains it.

For agents, scripts, or a noninteractive terminal, use plain output:

```sh
.venv/bin/python -B exercise.py --plain
```

## The task

This little monorepo has three apps: `zorch`, `greeb`, and `blerg`.
`blerg` depends on `greeb`. Each revision needs all three built, though unchanged
inputs can reuse cached builds. The results go into a simulated release.

`pipeline.py` declares the build steps and their dependencies. The driver submits
Git commits to that pipeline, like commits arriving at CI. Independent steps can
run together, but the starter's capacity-one pool lets only one commit's pipeline
run at a time.

**Let builds for different revisions overlap, while keeping deployments one
at a time.** Make a sequence of revisions faster without breaking the build or
release behavior. Keep all required builds (or valid cache hits), and keep
releases local and simulated. Don't speed things up by shortening the delays,
skipping required work, or relaxing artifact checks.

We're interested in how you know your change works, not just whether it works
on the first try. Add tests that challenge your assumptions. The existing tests
check the simulation; passing them isn't enough to verify your new pipeline.

Include a short write-up:

- What did you change, and how much faster is it than the starter?
- What should happen when revisions are released, and why did you choose that behavior?
- How did you test it? What do those tests show, and what haven't you checked?
- What assumptions or tradeoffs did you make?

**AI coding agents are encouraged.** Tell us how you used them. You still own
understanding and checking the result. Ask us if a requirement is unclear.

## Inspect a run

**Run example** creates a temporary Git repo with three real commits: initial
sources, a `greeb` change, then a `zorch` change. Choosing your own changes first
initializes the same source history but submits only your new commits. Plain
mode runs the supplied history immediately. The temporary repo is cleaned up
when you exit. Nothing is pushed or changed in your checkout.

To keep the history and results, use a fresh directory outside your checkout:

```sh
RUN_DIR="$(mktemp -d)"
.venv/bin/python -B exercise.py --directory "$RUN_DIR"
git -C "$RUN_DIR/repo" log --oneline --stat
# Use the release path shown in the UI event log:
python3 -m json.tool "$RUN_DIR/runs/<run-id>/release.json"
```

Run again with the same `--directory` to reuse the Git history. Each UI run keeps
its own results under `runs/`, without reusing earlier runs' cache entries.
Plain mode uses `state/` and retains its cache across invocations.
Remove the directory when you're done: `rm -rf "$RUN_DIR"`.

Uncached builds take 0.3 seconds for `zorch` and 0.6 seconds each for `greeb` and
`blerg`; a release takes 0.2 seconds. `--speed 0` removes delays for quick checks,
but doesn't prove concurrency correctness.

## Where to work

- `pipeline.py`: the candidate-editable declaration, exported as `pipeline`.
- `workflow.py`: the supplied DAG executor and pipeline-pool mechanics.
- `simulation.py`: builds, caching, artifacts, events, and simulated releases.
- `fixture.py`: creates the disposable Git history and simulated source changes.
- `exercise.py`: the command-line driver.
- `tui.py`: the live display; it observes the same pipeline, without changing its behavior.
- `tests/`: the existing tests.

### Declaring a pipeline

Use the Python declarations in `workflow.py`; no YAML or scheduler code is needed:

- `Pipeline(tasks=[...], pool=None)`: runs once per submitted commit. A named
  pool has capacity one and covers the whole invocation. No pool means no
  pipeline-level concurrency limit.
- `Build("app", needs=[...])`: builds an app after its dependencies succeed.
  `Build("blerg", needs=["greeb"])` receives that commit's `greeb` artifact.
- `Deploy("name", needs=[...])`: releases the artifacts from its dependencies
  and any inputs supplied by a calling pipeline.
- `Call("name", pipeline=another_pipeline, needs=[...])`: calls a pipeline with
  the same commit ID and artifacts from its dependencies. The call waits for
  the child to finish; the child acquires its own pool, if declared.

Names are unique within a pipeline. `needs` refers to task names in that pipeline.
Independent ready tasks run concurrently. Failed tasks block their dependents;
already-running work and independent commits finish before execution returns an
error. Successful cache entries remain available. There are no automatic retries.

Pools are FIFO within one `execute_pipeline(sim, pipeline, commits)` call. Top-level
invocations queue in submission order; called pipelines queue when invoked. Pools
are not shared across separate executions or processes. A child cannot acquire a
pool already held by its parent, and recursive calls and cyclic task dependencies
are rejected. Pool acquisition cycles across child pipelines are also rejected.
Pools belong to pipelines, not individual tasks. Build dependencies must refer to
local task names; inherited artifacts are available to deployment and callbacks,
not a replacement for declaring a local build's dependencies.

For custom release behavior, `Deploy` also accepts `when(sim, commit, artifacts)`,
a Python callback evaluated before deployment while inside the containing pipeline's
pool, if any. Returning false skips that deployment; raising fails the task.
Callbacks and helper modules can live alongside your declaration. The executor does
not supply a release policy for you.

The simulation validates artifacts and atomically writes release state, but does
not itself serialize deployments. Your pipeline's concurrency boundaries control
that behavior. Atomic writes aren't the same as one deployment at a time.

### Simulation API

- `sim.build(revision, app, dependency=None)` returns an artifact. When building
  `blerg`, pass that revision's `greeb` artifact as the dependency.
- `sim.deploy(revision, artifacts)` takes a dictionary of valid artifacts for all
  three apps. It checks them and atomically updates the shared release state.
- `sim.lock(name)` provides a shared filesystem lock across threads or local
  processes using the same state directory. Separate state directories represent
  separate environments.

Build and deploy accept commit IDs from the fixture repo. Cache keys use Git
source content and a build-version identifier. Changing `greeb` also changes
`blerg`'s cache inputs. Only successfully published entries can be reused, and
cache hits still produce artifacts associated with the requested revision.

### Output files

In a retained run directory, you'll find the files below. UI results live under
`runs/<run-id>/` instead of `state/`, with a separate directory for each run:

- `fixture.json` and `repo/`: revision IDs and Git history.
- `state/events.jsonl`: build/release events, cache keys, and cache hits.
- `state/cache/`: completed cached builds.
- `state/artifacts/<revision>/`: artifacts for each revision.
- `state/release.json`: the current simulated release.

### Test hooks

`Simulation` accepts these optional arguments:

- `speed`: scales the delays.
- `observer(event)`: called after an event is logged. You can use synchronization
  primitives here to control execution in tests.
- `fail_build(revision, app)`: return `True` to fail a cache miss. The build raises
  an exception without publishing its cache entry.

This is a small simulation, not production CI. It doesn't compile real apps or
model deployment rollback or recovery from machine crashes.
