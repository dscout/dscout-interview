#!/usr/bin/env bash
# Create real local Git commits and launch one RWX run per revision without
# waiting between them. The temporary worktrees are removed on exit.

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
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

nonce="challenge-$(date +%s)-$RANDOM"
create_commit_worktrees "$ROOT" "$workdir" "$nonce"

# The workflow is being developed locally and may not yet be committed. Copy
# the exact definition into each disposable worktree so rwx run patches it in.
for tree in "$GREEB_WORKTREE" "$ZORCH_WORKTREE"; do
  mkdir -p "$tree/.rwx"
  cp "$ROOT/.rwx/monorepo-undivided.yml" "$tree/.rwx/monorepo-undivided.yml"
done

start_revision() {
  local tree="$1" revision="$2"
  local output
  echo
  echo "Starting $revision from real commit $revision"
  output="$(cd "$tree" && rwx run .rwx/monorepo-undivided.yml \
    --title "$(git -C "$tree" log -1 --format=%s)" \
    --init "revision=$revision" 2>&1)" || {
      printf '%s\n' "$output" >&2
      return 1
    }
  printf '%s\n' "$output"
}

# Start the slower greeb-changing commit first, then the shorter zorch commit.
# The undivided concurrency pool should queue the second whole run.
start_revision "$GREEB_WORKTREE" "$GREEB_COMMIT"
start_revision "$ZORCH_WORKTREE" "$ZORCH_COMMIT"
