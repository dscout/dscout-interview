# DevOps exercise: monorepo CI and deployment

## Scenario

This repository contains a small simulated monorepo with three apps: `zorch`,
`greeb`, and `blerg`. `blerg` depends on `greeb`. Each app build is a separate
RWX task, and RWX content-based caching lets unchanged builds reuse prior
results. The workflow also includes a simulated deployment; it does not deploy
to a real environment.

The starter workflow is `.rwx/monorepo-undivided.yml`. It currently puts the
full workflow in a capacity-one concurrency pool.

## Your task

Improve the workflow's throughput while preserving the correctness of its
build and release behavior. Use RWX's concurrency and run-composition features
as appropriate. Keep the simulation safe: do not add real deployments or
external side effects.

Please make your changes in this repository and include a short summary of your
design, how you tested it, and any assumptions or tradeoffs you considered.

## Running the exercise

The local fixture test checks the generated commit history and requires Git and
Bash:

```sh
bash test/cases/commit-sequence.sh
```

To start the simulated sequence on RWX, sign in to the RWX CLI and run:

```sh
./simulate-commit-sequence.sh
```

This creates disposable local Git worktrees with two successive commits: the
first changes `greeb`; the next changes only `zorch`. It starts an RWX CLI run
from each worktree without pushing. RWX applies each worktree's local changes
to its clone for the run. RWX runs use real resources, so this command starts
billable work. You can inspect the runs in RWX after they start.

The optional baseline smoke test waits for both runs and checks that the
unchanged builds cache-hit in the starter workflow. It also requires an
authenticated RWX CLI and uses RWX resources:

```sh
./test/rwx-smoke.sh
```
