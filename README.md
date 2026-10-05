# Build concurrency exercise

## Setup

Use **Python 3.10+ and Git** on macOS or Linux (including WSL). No packages,
accounts, credentials, Docker, or network services are required to run it.

Clone or copy the exercise checkout. If using the repository's branches, check
out `devops-challenge/build-concurrency`. Run commands below from the checkout's root.

## Scenario and task

A small monorepo contains three apps: `zorch`, `greeb`, and `blerg`.
`blerg` depends on `greeb`. Every revision needs builds for all three apps,
with content-based cache reuse where inputs match. Successful artifacts are
used for simulated releases. The starter in `pipeline.py` serializes the entire build-and-deploy
pipeline, including the revisions submitted to it.

**Improve throughput while preserving build and release correctness.** Keep
all required build work (execution or valid cache reuse) and keep deployment
simulated and local. Explain your design, how you tested it, your assumptions,
and the tradeoffs you considered. State what release behavior you intend and
why; ask for clarification if a requirement is ambiguous.

AI coding agents are encouraged. You are responsible for understanding and
verifying your submission. Include how you used agents in your design summary.
The public tests check the starter's mechanics; passing them alone is not a
complete verification of your changes.

## Run locally

```sh
python3 -B exercise.py
python3 -B -m unittest discover -s tests -v
```

The first command creates a temporary Git repository and local state, runs
three real commits, prints execution events, then removes the fixture. The
commits contain initial app sources, a `greeb` change, and a `zorch` change.
Nothing is pushed, and the exercise checkout's Git configuration, branches,
and source files are not changed. Default uncached build delays are 0.3 seconds
for `zorch` and 0.6 seconds each for `greeb` and `blerg`; release takes 0.2 seconds.

To retain and inspect a run, use a fresh directory outside your checkout:

```sh
RUN_DIR="$(mktemp -d)"
python3 -B exercise.py --directory "$RUN_DIR"
git -C "$RUN_DIR/repo" log --oneline --stat
python3 -m json.tool "$RUN_DIR/state/release.json"
```

Re-run with the same `--directory` to reuse its history and completed cache
entries. Events append on each invocation. Use a fresh directory for a cold
cache. Remove the fixture when finished: `rm -rf "$RUN_DIR"`.
`--speed 0` removes delays for fast checks; it does not establish concurrency
correctness. The default invocation always starts fresh.

## Files and interface

- `pipeline.py`: orchestration to improve. `run(sim, revisions)` receives
  revisions in submission order. `run_revision` builds and releases one revision.
- `simulation.py`: local build, cache, artifact, event, and release mechanics.
- `fixture.py`: independent disposable Git repository creation.
- `exercise.py`: local command-line driver.
- `tests/`: standard-library tests.

`Simulation.build(revision, app, dependency=None)` returns an artifact. Supply
that revision's `greeb` artifact when building `blerg`.
`Simulation.deploy(revision, artifacts)` requires a dictionary containing all
three apps' valid artifacts. Both accept commit IDs from the fixture repository.
`Simulation.lock(name)` is a shared filesystem lock, usable across threads and
local processes that share a state directory. Separate state directories model
separate environments.

The cache uses exact Git source content and a build-version identifier. A
`greeb` change also changes `blerg`'s cache inputs. Entries become reusable only
when successfully published. Cache hits still produce revision-associated
artifacts. Release validates those artifacts and updates shared local state
atomically; no real deployment occurs.

Retained output includes:

- `fixture.json`: revision IDs, inspectable using Git in `repo/`.
- `state/events.jsonl`: revision/app events, cache keys, and cache-hit information.
- `state/cache/`: completed content-keyed build results.
- `state/artifacts/<revision>/`: revision-associated build artifacts.
- `state/release.json`: shared simulated release state.

For your own tests, `Simulation` accepts a delay multiplier (`speed`), an
`observer(event)` callback called after an event is logged, and a
`fail_build(revision, app)` callback to fail a cache miss. Observers can use
synchronization primitives to control execution. A failure raises an exception
without publishing that build's cache entry. These hooks do not require a
pipeline-definition language or external services.

The simulation is intentionally small: it models source inputs, dependencies,
build reuse, artifacts, and local releases—not production CI, application
compilation, deployment rollback, or machine-crash recovery.
