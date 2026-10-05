"""Local build/cache/release mechanics. No real applications are deployed."""

from contextlib import contextmanager
import fcntl
import hashlib
import json
from pathlib import Path
import tempfile
import time

from fixture import git

APPS = ("zorch", "greeb", "blerg")
BUILD_SECONDS = {"zorch": 0.3, "greeb": 0.6, "blerg": 0.6}


@contextmanager
def file_lock(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as out:
        temporary = Path(out.name)
        try:
            json.dump(value, out, sort_keys=True)
            out.write("\n")
            out.close()
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


class Simulation:
    """Shared state lives in state_dir; observer(event) runs after each logged event.

    speed scales delays (0 removes them). fail_build(revision, app) may return
    True to simulate a failed cache miss. Callbacks may block or raise for tests.
    """

    def __init__(self, repo, state_dir, *, speed=1, observer=None, fail_build=None):
        if speed < 0:
            raise ValueError("speed must be nonnegative")
        self.repo = Path(repo)
        self.state = Path(state_dir)
        self.state.mkdir(parents=True, exist_ok=True)
        self.speed = speed
        self.observer = observer
        self.fail_build = fail_build

    def lock(self, name):
        return file_lock(self.state / "locks" / f"{name}.lock")

    def event(self, kind, revision, **fields):
        with self.lock("events"):
            event = dict(kind=kind, revision=revision, time=time.monotonic(), **fields)
            with (self.state / "events.jsonl").open("a") as out:
                out.write(json.dumps(event, sort_keys=True) + "\n")
        if self.observer:
            self.observer(event)

    def resolve(self, revision):
        return git(self.repo, "rev-parse", "--verify", f"{revision}^{{commit}}")

    def cache_key(self, revision, app):
        if app not in APPS:
            raise ValueError(f"unknown app: {app}")
        inputs = {app: git(self.repo, "rev-parse", f"{revision}:source/{app}.txt")}
        if app == "blerg":
            inputs["greeb"] = self.cache_key(revision, "greeb")
        encoded = json.dumps(["build-v1", app, inputs], sort_keys=True).encode()
        return hashlib.sha256(encoded).hexdigest()

    def artifact_path(self, revision, app):
        return self.state / "artifacts" / revision / f"{app}.json"

    def build(self, revision, app, dependency=None):
        revision = self.resolve(revision)
        key = self.cache_key(revision, app)
        if app == "blerg":
            self.validate_artifact(revision, "greeb", dependency)
        self.event("build_requested", revision, app=app, key=key)
        try:
            with self.lock(f"cache-{key}"):
                cache = self.state / "cache" / f"{key}.json"
                hit = cache.exists()
                if hit:
                    payload = json.loads(cache.read_text())
                    if payload != {"app": app, "key": key}:
                        raise ValueError("invalid cache entry")
                    self.event("cache_hit", revision, app=app, key=key)
                else:
                    self.event("build_started", revision, app=app, key=key)
                    time.sleep(BUILD_SECONDS[app] * self.speed)
                    if self.fail_build and self.fail_build(revision, app):
                        raise RuntimeError(f"simulated build failure: {app}")
                    payload = {"app": app, "key": key}
                    write_json(cache, payload)
                    self.event("cache_published", revision, app=app, key=key)
                artifact = dict(payload, revision=revision)
                write_json(self.artifact_path(revision, app), artifact)
            self.event("build_finished", revision, app=app, key=key, cache_hit=hit)
            return artifact
        except Exception:
            self.event("build_failed", revision, app=app, key=key)
            raise

    def validate_artifact(self, revision, app, artifact):
        expected = {"revision": revision, "app": app,
                    "key": self.cache_key(revision, app)}
        if artifact != expected:
            raise ValueError(f"invalid {app} artifact for {revision}")
        path = self.artifact_path(revision, app)
        if not path.exists() or json.loads(path.read_text()) != expected:
            raise ValueError(f"missing {app} artifact for {revision}")

    def deploy(self, revision, artifacts):
        revision = self.resolve(revision)
        if set(artifacts) != set(APPS):
            raise ValueError("release requires all three apps")
        for app in APPS:
            self.validate_artifact(revision, app, artifacts[app])
        self.event("deploy_requested", revision)
        self.event("deploy_started", revision)
        time.sleep(0.2 * self.speed)
        write_json(self.state / "release.json",
                   {"revision": revision, "artifacts": artifacts})
        self.event("deploy_finished", revision)

    def events(self):
        with self.lock("events"):
            path = self.state / "events.jsonl"
            return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
