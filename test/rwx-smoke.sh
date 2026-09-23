#!/usr/bin/env bash
# Opt-in end-to-end smoke test. Starts two real RWX runs from a real local Git
# commit sequence, then checks the baseline's expected cache behavior.

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT/test/lib/commit-sequence.sh"

if ! rwx whoami >/dev/null 2>&1; then
  echo "not signed in to RWX — run 'rwx login'" >&2
  exit 1
fi

workdir="$(mktemp -d)"
cleanup() {
  git -C "$ROOT" worktree remove --force "$workdir/greeb" >/dev/null 2>&1 || true
  git -C "$ROOT" worktree remove --force "$workdir/zorch" >/dev/null 2>&1 || true
  git -C "$ROOT" worktree remove --force "$workdir/history" >/dev/null 2>&1 || true
  rm -rf "$workdir"
}
trap cleanup EXIT

nonce="smoke-$(date +%s)-$RANDOM"
create_commit_worktrees "$ROOT" "$workdir" "$nonce"

for tree in "$GREEB_WORKTREE" "$ZORCH_WORKTREE"; do
  mkdir -p "$tree/.rwx"
  cp "$ROOT/.rwx/monorepo-undivided.yml" "$tree/.rwx/monorepo-undivided.yml"
done

start_run() {
  local tree="$1" revision="$2" result_var="$3" output
  output="$(cd "$tree" && rwx run .rwx/monorepo-undivided.yml \
    --title "monorepo fixture ${revision:0:12}" \
    --init "revision=$revision" --json)"
  local id
  id="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["RunID"])' <<<"$output")"
  printf -v "$result_var" '%s' "$id"
  echo "Started ${revision:0:12}: https://cloud.rwx.com/dscout/runs/$id"
}

start_run "$GREEB_WORKTREE" "$GREEB_COMMIT" FIRST_RUN
start_run "$ZORCH_WORKTREE" "$ZORCH_COMMIT" SECOND_RUN

rwx results "$FIRST_RUN" --wait --json > "$workdir/first.json"
rwx results "$SECOND_RUN" --wait --json > "$workdir/second.json"

python3 - "$workdir/first.json" "$workdir/second.json" <<'PY'
import json
import sys


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def tasks(run):
    found = {}
    pending = list(run.get("Tasks", []))
    while pending:
        task = pending.pop()
        found[task["Key"]] = task
        pending.extend(task.get("Subtasks", []))
    return found


def state(task_map, key):
    return task_map[key]["Status"]["FinishedSubStatus"]

first_run, second_run = map(load, sys.argv[1:])
assert first_run["ResultStatus"] == "succeeded", first_run["ResultStatus"]
assert second_run["ResultStatus"] == "succeeded", second_run["ResultStatus"]
first, second = tasks(first_run), tasks(second_run)
for key in ("build-zorch", "build-greeb", "build-blerg", "deploy"):
    assert state(first, key) == "executed", ("first", key, state(first, key))

assert state(second, "build-zorch") == "executed", state(second, "build-zorch")
for key in ("build-greeb", "build-blerg"):
    assert state(second, key) == "cache_hit", ("second", key, state(second, key))
assert state(second, "deploy") == "executed", state(second, "deploy")
print("RWX baseline smoke test passed: unchanged greeb and blerg builds cache-hit")
PY
