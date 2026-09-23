#!/usr/bin/env bash
# Fast local contract test for the real Git worktree fixture. No RWX access
# needed; runs the same worktree creation function as the integration driver.

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "$ROOT/test/lib/commit-sequence.sh"

workdir="$(mktemp -d)"
repo="$workdir/repo"
mkdir -p "$repo"
git -C "$repo" init -q
git -C "$repo" config user.name 'Fixture test base'
git -C "$repo" config user.email 'fixture-test@example.invalid'
echo 'starter' > "$repo/README"
git -C "$repo" add README
git -C "$repo" commit -qm 'starter base'

cleanup() {
  git -C "$repo" worktree remove --force "$GREEB_WORKTREE" >/dev/null 2>&1 || true
  git -C "$repo" worktree remove --force "$ZORCH_WORKTREE" >/dev/null 2>&1 || true
  git -C "$repo" worktree remove --force "$workdir/history" >/dev/null 2>&1 || true
  rm -rf "$workdir"
}
trap cleanup EXIT

nonce="test-$RANDOM-$(date +%s)"
create_commit_worktrees "$repo" "$workdir" "$nonce"

[[ "$(git -C "$repo" rev-parse "$GREEB_COMMIT^")" == "$BASE_COMMIT" ]]
[[ "$(git -C "$repo" rev-parse "$ZORCH_COMMIT^")" == "$GREEB_COMMIT" ]]
[[ "$(git -C "$repo" diff-tree --no-commit-id --name-only -r "$GREEB_COMMIT")" == "source/greeb.txt" ]]
[[ "$(git -C "$repo" diff-tree --no-commit-id --name-only -r "$ZORCH_COMMIT")" == "source/zorch.txt" ]]
[[ "$(git -C "$GREEB_WORKTREE" rev-parse HEAD)" == "$GREEB_COMMIT" ]]
[[ "$(git -C "$ZORCH_WORKTREE" rev-parse HEAD)" == "$ZORCH_COMMIT" ]]
[[ "$(cat "$GREEB_WORKTREE/source/greeb.txt")" == "greeb-$nonce-v2" ]]
[[ "$(cat "$GREEB_WORKTREE/source/zorch.txt")" == "zorch-$nonce-v1" ]]
[[ "$(cat "$ZORCH_WORKTREE/source/greeb.txt")" == "greeb-$nonce-v2" ]]
[[ "$(cat "$ZORCH_WORKTREE/source/zorch.txt")" == "zorch-$nonce-v2" ]]

printf 'commit worktree fixture passed\n'
