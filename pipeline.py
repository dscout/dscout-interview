"""Candidate-editable pipeline definition."""

from workflow import Build, Deploy, Pipeline

pipeline = Pipeline(
    pool="pipeline",
    tasks=[
        Build("zorch"),
        Build("greeb"),
        Build("blerg", needs=["greeb"]),
        Deploy("release", needs=["zorch", "greeb", "blerg"]),
    ],
)
