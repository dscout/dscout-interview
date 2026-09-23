# DevOps challenge prototype

This is an early prototype for an RWX concurrency-pool exercise. The current
starter is intentionally undivided: a capacity-one queue covers CI and the
simulated deployment. It builds three small simulated apps (`zorch`, `greeb`,
`blerg`), with `blerg` depending on `greeb`. RWX content-based caching should
reuse the `greeb` and `blerg` build tasks when a later commit changes only
`zorch`.

## Local fixture test

```sh
bash test/cases/commit-sequence.sh
rwx lint .rwx/monorepo-undivided.yml
```

The fixture test creates a temporary Git repository and checks the commit
parents and exact changed paths. It does not need RWX credentials.

## RWX smoke test

```sh
./test/rwx-smoke.sh
```

This opt-in test creates actual commits in disposable Git worktrees, starts two
RWX runs, waits for them, and asserts that the second run executes `build-zorch`
but cache-hits `build-greeb` and `build-blerg`. It requires an authenticated
RWX CLI and consumes real RWX resources. No test commit is pushed. The CLI
patches each worktree's local state onto the remote base when starting a run.

To just start both runs without waiting for results:

```sh
./simulate-commit-sequence.sh
```

This also requires RWX authentication and consumes resources. The two revisions
are real local Git commits, created in temporary worktrees and removed on exit.
