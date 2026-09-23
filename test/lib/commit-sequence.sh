#!/usr/bin/env bash
# Build an isolated, disposable Git history for the monorepo scenario.
# Sets BASE_COMMIT, GREEB_COMMIT, and ZORCH_COMMIT for the caller.

create_commit_sequence() {
  local repo="$1" nonce="$2"
  mkdir -p "$repo"
  git -C "$repo" init -q
  git -C "$repo" config user.name 'RWX challenge fixture'
  git -C "$repo" config user.email 'rwx-fixture@example.invalid'

  mkdir -p "$repo/source"
  printf 'zorch-%s-v1\n' "$nonce" > "$repo/source/zorch.txt"
  printf 'greeb-%s-v1\n' "$nonce" > "$repo/source/greeb.txt"
  printf 'blerg-%s-v1\n' "$nonce" > "$repo/source/blerg.txt"
  git -C "$repo" add source
  git -C "$repo" commit -qm 'fixture: initial monorepo state'
  BASE_COMMIT="$(git -C "$repo" rev-parse HEAD)"

  printf 'greeb-%s-v2\n' "$nonce" > "$repo/source/greeb.txt"
  git -C "$repo" add source/greeb.txt
  git -C "$repo" commit -qm 'fixture: change greeb'
  GREEB_COMMIT="$(git -C "$repo" rev-parse HEAD)"

  printf 'zorch-%s-v2\n' "$nonce" > "$repo/source/zorch.txt"
  git -C "$repo" add source/zorch.txt
  git -C "$repo" commit -qm 'fixture: change zorch'
  ZORCH_COMMIT="$(git -C "$repo" rev-parse HEAD)"

  export BASE_COMMIT GREEB_COMMIT ZORCH_COMMIT
}

# Create actual commits based on the current checkout, then create isolated
# worktrees at the two revisions used by the RWX run sequence. The caller owns
# cleanup of the supplied temporary directory and its Git worktrees.
create_commit_worktrees() {
  local checkout="$1" workdir="$2" nonce="$3"
  local history="$workdir/history"

  git -C "$checkout" worktree add --quiet --detach "$history" HEAD
  git -C "$history" config user.name 'RWX challenge fixture'
  git -C "$history" config user.email 'rwx-fixture@example.invalid'

  mkdir -p "$history/source"
  printf 'zorch-%s-v1\n' "$nonce" > "$history/source/zorch.txt"
  printf 'greeb-%s-v1\n' "$nonce" > "$history/source/greeb.txt"
  printf 'blerg-%s-v1\n' "$nonce" > "$history/source/blerg.txt"
  git -C "$history" add source
  git -C "$history" commit -qm 'fixture: initial monorepo state'
  BASE_COMMIT="$(git -C "$history" rev-parse HEAD)"

  printf 'greeb-%s-v2\n' "$nonce" > "$history/source/greeb.txt"
  git -C "$history" add source/greeb.txt
  git -C "$history" commit -qm 'fixture: change greeb'
  GREEB_COMMIT="$(git -C "$history" rev-parse HEAD)"

  printf 'zorch-%s-v2\n' "$nonce" > "$history/source/zorch.txt"
  git -C "$history" add source/zorch.txt
  git -C "$history" commit -qm 'fixture: change zorch'
  ZORCH_COMMIT="$(git -C "$history" rev-parse HEAD)"

  git -C "$checkout" worktree add --quiet --detach "$workdir/greeb" "$GREEB_COMMIT"
  git -C "$checkout" worktree add --quiet --detach "$workdir/zorch" "$ZORCH_COMMIT"

  export BASE_COMMIT GREEB_COMMIT ZORCH_COMMIT
  export GREEB_WORKTREE="$workdir/greeb" ZORCH_WORKTREE="$workdir/zorch"
}
