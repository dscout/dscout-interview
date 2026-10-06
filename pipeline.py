"""Candidate-editable pipeline definition."""

from lib.fixture import git
from lib.workflow import Build, Call, Deploy, Pipeline


def deploy_if_current(sim, commit, app):
    deployed = sim.deployed(app)
    if deployed and (deployed["image"]["digest"] == sim.image_digest(commit, app)
                     or (deployed["revision"] != commit
                         and git(sim.repo, "merge-base", commit,
                                 deployed["revision"]) == commit)):
        return False
    if app == "blerg":
        greeb = sim.deployed("greeb")
        if (greeb["image"]["digest"] != sim.image_digest(commit, "greeb")
                and git(sim.repo, "merge-base", commit, greeb["revision"]) == commit):
            return False
    return True


def deployment(app, needs):
    name = f"deploy-{app}"
    return Call(name, needs=needs, pipeline=Pipeline(
        pool="deployment",
        tasks=[Deploy(
            name, app,
            when=lambda sim, commit, artifacts: deploy_if_current(sim, commit, app),
            image_reference="digest",
        )],
    ))


pipeline = Pipeline(tasks=[
    Build("zorch"),
    Build("greeb"),
    Build("blerg", needs=["greeb"]),
    deployment("zorch", ["zorch"]),
    deployment("greeb", ["greeb"]),
    deployment("blerg", ["blerg", "deploy-greeb"]),
])
