"""Command-line driver for a disposable local exercise."""

import argparse
import json
from pathlib import Path
import tempfile

from fixture import create_history
from pipeline import run
from simulation import Simulation, file_lock


def execute(directory, speed):
    directory.mkdir(parents=True, exist_ok=True)
    manifest = directory / "fixture.json"
    with file_lock(directory / "fixture.lock"):
        if manifest.exists():
            revisions = json.loads(manifest.read_text())["revisions"]
        else:
            revisions = create_history(directory / "repo")
            manifest.write_text(json.dumps({"revisions": revisions}, indent=2) + "\n")
    print(f"Fixture: {directory}", flush=True)
    for revision in revisions:
        print(f"Revision: {revision}", flush=True)

    def show(event):
        app = event.get("app", "")
        hit = f" cache_hit={event['cache_hit']}" if "cache_hit" in event else ""
        print(f"{event['revision'][:12]} {event['kind']} {app}{hit}", flush=True)

    sim = Simulation(directory / "repo", directory / "state", speed=speed, observer=show)
    run(sim, revisions)
    print(f"Release: {sim.state / 'release.json'}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path,
                        help="retain fixture and state here; use a directory outside the checkout")
    parser.add_argument("--speed", type=float, default=1, help="delay multiplier (default: 1)")
    args = parser.parse_args()
    if args.speed < 0:
        parser.error("--speed must be nonnegative")
    if args.directory:
        execute(args.directory.resolve(), args.speed)
    else:
        with tempfile.TemporaryDirectory(prefix="build-exercise-") as directory:
            execute(Path(directory), args.speed)


if __name__ == "__main__":
    main()
