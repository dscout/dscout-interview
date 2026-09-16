# dscout-interview

A survey-taking app: Android + iOS clients sharing UI/logic via Compose Multiplatform, backed by a small Node/Express API. Read this file first, then the AGENTS.md in whichever module you're working in.

## Layout

```
shared/      Compose Multiplatform module — UI and domain logic shared by both apps
androidApp/  Thin Android host for shared/ (see androidApp/AGENTS.md)
iosApp/      Xcode project hosting shared/ via SwiftUI (see iosApp/AGENTS.md)
backend/     Node/Express API, in-memory store (see backend/AGENTS.md)
```

Almost all app logic belongs in `shared/`. `androidApp/` and `iosApp/` should stay thin — platform entry points and platform-specific glue only.

## Tech stack (pinned versions)

| Component | Version |
|---|---|
| Kotlin | 2.2.0 |
| Compose Multiplatform | 1.8.0 |
| AGP | 8.9.1 |
| Gradle | 8.11.1 (via committed wrapper — no system Gradle install needed) |
| JDK | 17 |
| compileSdk / targetSdk | 35 |
| minSdk | 24 |
| Node | 20+ (see `backend/.nvmrc`) |

If updating any of these, keep Kotlin and Compose Multiplatform on a JetBrains-certified compatible pair — they are not independently versioned.

## Current state: real survey, deliberately uneven

The survey flow (view → answer → submit → confirmation) is implemented in `shared/.../App.kt`, one question per screen with Back/Next/Submit and a progress indicator. The sample survey is four questions across three types. Those types are **not equally complete** — that unevenness is intentional, not an oversight:

- **Single-select** and **open-ended text** are fully working end-to-end (client UI, submission, and real backend validation).
- **Multi-select** has a client UI (checkboxes) but it's a stub: the underlying state only tracks a single selected value, not a set, so checking a second option silently replaces the first instead of adding to it. The backend also does no validation on multi-select answers.

The feature planned next is specified in `requirements/scale-question-follow-up.md` (the product requirements) and sketched in `plans/scale-question-follow-up.md` (a rough, deliberately unfinished plan). Neither is implemented — no scale question type exists in the app or the backend today.

## Backend contract (as currently implemented)

- `GET /survey` → `{ id, title, questions: [{ id, prompt, type, options? }] }`. `type` is one of `SINGLE_SELECT` / `MULTI_SELECT` / `OPEN_TEXT`; `options` applies to the select types.
- `POST /responses` → body is `{ surveyId, answers: [{ questionId, value?, values? }] }`. Real validation for `SINGLE_SELECT` (must match an option) and `OPEN_TEXT` (must be non-empty); `MULTI_SELECT` answers are accepted without validation (matches the client stub). Returns `201` with the stored record + generated `id`/`receivedAt`, or `400` with an `error` message.
- Base URL differs by platform: Android emulator uses `http://10.0.2.2:4000`, iOS Simulator uses `http://127.0.0.1:4000`. Each app host supplies its own value to `shared`'s `BackendConfig` during startup — Android from `res/values/strings.xml`, iOS from `Info.plist` — so it isn't left as something to rediscover.

## Conventions

- Package root: `com.dscout.surveyapp` (`.android` / `.shared` / `.ios` suffixes per module where applicable).
- Kotlin official code style (`gradle.properties`).
- New shared UI/logic goes in `shared/src/commonMain`; only add to `androidMain`/`iosMain` for genuine platform-specific needs (see `Platform.kt` for the `expect`/`actual` pattern already in use).
