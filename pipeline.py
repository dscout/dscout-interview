"""Candidate-editable orchestration."""

from simulation import APPS


def run_revision(sim, revision):
    revision = sim.resolve(revision)
    artifacts = {}
    for app in APPS:
        artifacts[app] = sim.build(revision, app, artifacts.get("greeb"))
    sim.deploy(revision, artifacts)


def run(sim, revisions):
    with sim.lock("pipeline"):
        for revision in revisions:
            run_revision(sim, revision)
