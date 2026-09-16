# androidApp

Thin Android host for the `shared` Compose Multiplatform module. See the top-level `AGENTS.md` first for repo-wide context (tech stack, backend contract, current skeleton state).

## What's here

- `MainActivity.kt` — a single `ComponentActivity` that hands `shared`'s `BackendConfig` the backend base URL and then calls `setContent { App() }` from `shared`. Platform config wiring like that is the only logic that belongs here; if you're adding real screens or business logic, it almost certainly belongs in `shared/src/commonMain` instead.
- `res/values/strings.xml` — holds `backend_base_url`, the value `MainActivity` passes to `BackendConfig`.
- `AndroidManifest.xml` — `INTERNET` permission + a scoped `network_security_config.xml`.
- `res/xml/network_security_config.xml` — allows cleartext HTTP, but only to `10.0.2.2` and `localhost`. This is intentional and scoped, not a blanket allow — don't widen it without reason.

## Build / run

- Open the repo root in Android Studio, select the `androidApp` run configuration, run on any emulator.
- Or from the command line: `./gradlew :androidApp:installDebug`.

## Networking gotcha

The Android emulator can't reach the host machine via `localhost` — it uses `10.0.2.2` as an alias for the host's loopback interface instead. That's already the value of `backend_base_url` in `res/values/strings.xml`, so the app will work against a `backend/` running on the same machine as the emulator without extra config. A **physical device** needs the host's actual LAN IP instead — `10.0.2.2` won't resolve.

## Debugging

Logcat and the Compose Layout Inspector both work as usual. If `10.0.2.2` ever seems unreachable, `adb reverse tcp:4000 tcp:4000` is an alternative way to expose the backend to the emulator.
