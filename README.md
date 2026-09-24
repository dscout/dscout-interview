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

## Run it with RWX

You can use RWX from your own account; access to dscout's RWX organization is
not required. Create an RWX Cloud account, create or select an organization,
install the CLI, and authenticate:

```sh
brew install rwx-cloud/tap/rwx
rwx login
rwx whoami
```

Fork this repository to your GitHub account and run the exercise from your
fork's checkout. A public fork is the simplest setup: RWX must be able to clone
the commit being tested. Private forks need additional GitHub integration and
clone authentication configuration that is not included in this starter.

To start the simulated sequence, run:

```sh
./simulate-commit-sequence.sh
```

The script creates disposable local Git worktrees with two successive commits:
the first changes `greeb`; the next changes only `zorch`. It starts an RWX CLI
run from each worktree without pushing. The workflow clones your fork at each
commit. RWX runs use real compute and cache resources; check current RWX pricing
and any free credits before running. You can inspect results in your own RWX
organization.

The optional baseline smoke test waits for both runs and checks that the
unchanged builds cache-hit in the starter workflow. It uses RWX resources:

```sh
./test/rwx-smoke.sh
```
