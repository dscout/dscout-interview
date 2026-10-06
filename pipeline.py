"""Candidate-editable pipeline definition."""

from workflow import Build, Deploy, Pipeline

# zorch ---------------------> release
# greeb --------> blerg ------> release
# Edges are needs; list order is not execution order.
pipeline = Pipeline(
    pool="pipeline",
    tasks=[
        Build("zorch"),
        Build("greeb"),
        Build("blerg", needs=["greeb"]),
        Deploy("release", needs=["zorch", "greeb", "blerg"]),
    ],
)
