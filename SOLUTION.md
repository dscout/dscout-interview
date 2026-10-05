# Build concurrency solution

## Changes and release policy

The outer pipeline no longer has a capacity-one pool, so revisions can build
concurrently. All three builds remain required, and `blerg` still depends on its
revision's `greeb` artifact. A child pipeline receives those artifacts and holds
the `release` pool around the release check and deployment.

Releases are fast-forward-only. With no current release, any successfully built
revision can deploy. Otherwise, only a strict descendant of the released commit
can deploy. Older, identical, and divergent revisions skip deployment but still
complete their builds. Git errors fail the check rather than allowing a release.

This allows useful intermediate releases without waiting for every older build,
but never rolls back a newer successful release. If the newest build fails, an
older successful revision can still release, provided it advances the current
release. A later retry of the newest revision can then advance it again.

## Measurements

Five cold-cache trials per pipeline used the same three-commit fixture, separate
empty state directories, and the unchanged default delays (`speed=1`). Execution
order alternated between starter-first and solution-first. Timing covers
`execute_pipeline`, excluding fixture creation and UI startup.

| Trial | Starter | Solution |
| --- | ---: | ---: |
| 1 | 3.789s | 1.849s |
| 2 | 3.766s | 1.863s |
| 3 | 3.748s | 2.202s |
| 4 | 3.908s | 2.009s |
| 5 | 3.692s | 1.725s |
| Median | 3.766s | 1.863s |

Median execution was 2.02x faster, a 50.5% reduction in elapsed time. Every trial
completed nine builds: six misses and three content-cache hits. Every trial ended
with the newest revision released. The solution performed between one and three
deployments, depending on completion order, so the improvement includes both
build overlap and skipping obsolete deployments. These are local measurements,
not a guarantee for other machines or workloads.

## Verification

Run the suite with:

```sh
.venv/bin/python -B -m unittest discover -s tests -v
```

All 55 tests pass, including six new tests against the actual exported pipeline:

- Hold older revisions at build completion until the newest release finishes.
  This forces out-of-order completion, demonstrates cross-revision progress,
  and checks that the older releases skip while all artifacts remain valid.
- Check the event history for nonoverlapping deployments and strictly advancing
  release revisions.
- Release the newest revision first, then replay older and reversed history in
  separate executions. Release state stays unchanged, and a warm replay still
  completes all nine builds as cache hits.
- Fail the newest revision's build, check that the successful preceding revision
  releases and the failed cache entry is absent, then retry successfully.
- Reject deployment from divergent history while preserving its built artifacts.
- Fail closed when the current release references an unavailable commit.

The synchronization test uses `speed=0` but an explicit gate, not elapsed-time
assumptions, to force concurrency. Performance measurements use real delays.
The TUI was also exercised manually, first observing an older revision overwrite
a newer release before adding the policy.

## Assumptions and limits

Git ancestry defines forward progress, not commit timestamps or submission order.
The fixture's linear history fits this policy; unrelated branch deployments and
intentional rollbacks are unsupported. Identical revision reruns skip deployment.
An environment must retain the Git objects referenced by its current release.

The deployment pool is local to one executor. This solution covers one active
exercise execution and sequential reruns, not concurrent executions or processes
sharing an environment. Those would need a shared lock around both the policy
check and deployment; atomic release-file writes alone are insufficient.

No production CI, deployment failures, process crashes, resource limits, or
large-history scalability were tested. The supplied executor and simulation are
unchanged, and deployments remain local and simulated.

## AI use

An AI coding agent read the exercise and executor, implemented the declaration and
release callback, added tests, ran the suite and benchmarks, and drafted this
write-up. The participant discussed the concurrency model and inspected the TUI,
observed out-of-order releases, and chose the requirement that releases must never
move backward. Existing tests passing was not treated as proof of that policy;
new tests explicitly force the problematic ordering.
