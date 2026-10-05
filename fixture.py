"""Disposable Git history, independent of the exercise checkout."""

import os
from pathlib import Path
import subprocess


def git(repo, *args):
    env = os.environ.copy()
    for key in list(env):
        if key.startswith("GIT_"):
            del env[key]
    env.update(
        GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
        GIT_AUTHOR_NAME="CI fixture", GIT_AUTHOR_EMAIL="fixture@example.invalid",
        GIT_COMMITTER_NAME="CI fixture", GIT_COMMITTER_EMAIL="fixture@example.invalid",
        GIT_AUTHOR_DATE="2026-01-01T00:00:00Z",
        GIT_COMMITTER_DATE="2026-01-01T00:00:00Z",
    )
    return subprocess.check_output(
        ["git", "-c", "core.hooksPath=/dev/null", "-c", "commit.gpgSign=false",
         "-C", str(repo), *args], env=env, text=True,
    ).strip()


def create_history(repo):
    repo = Path(repo)
    repo.mkdir()
    git(repo, "init", "--quiet", "--initial-branch=fixture")
    source = repo / "source"
    source.mkdir()
    for app in ("zorch", "greeb", "blerg"):
        (source / f"{app}.txt").write_text(f"{app}-v1\n")
    revisions = []
    for app, message in ((None, "initial apps"), ("greeb", "change greeb"),
                         ("zorch", "change zorch")):
        if app:
            (source / f"{app}.txt").write_text(f"{app}-v2\n")
        git(repo, "add", "source")
        git(repo, "commit", "--quiet", "-m", message)
        revisions.append(git(repo, "rev-parse", "HEAD"))
    return revisions
