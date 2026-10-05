"""Candidate-editable pipeline definition."""

import json
import subprocess

from fixture import git
from workflow import Build, Call, Deploy, Pipeline


def advances_release(sim, commit, artifacts):
    release = sim.state / "release.json"
    if not release.exists():
        return True
    current = json.loads(release.read_text())["revision"]
    if commit == current:
        return False
    try:
        git(sim.repo, "merge-base", "--is-ancestor", current, commit)
    except subprocess.CalledProcessError as error:
        if error.returncode == 1:
            return False
        raise
    return True


release_pipeline = Pipeline(
    pool="release",
    tasks=[Deploy("release", when=advances_release)],
)

pipeline = Pipeline(
    tasks=[
        Build("zorch"),
        Build("greeb"),
        Build("blerg", needs=["greeb"]),
        Call("release", pipeline=release_pipeline, needs=["zorch", "greeb", "blerg"]),
    ],
)
