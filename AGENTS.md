# dscout-interview

The media upload engine from the dscout participant apps, extracted into a standalone repo. Participants capture photos, videos, and screen recordings while answering questions; the engine gets those files to S3 reliably, in the background, across flaky networks and app restarts.

Read this file first, then the AGENTS.md in whichever directory you're working in.

## Layout

```
backend/   Node/Express upload harness: presign API + fake S3 + fault injection (see backend/AGENTS.md)
android/   Kotlin upload engine (JVM library; see android/AGENTS.md)
ios/       Swift upload engine (Swift package; see ios/AGENTS.md)
```

`android/` and `ios/` are independent implementations of the same engine — same design, same behavior, each written in its platform's idiom. They are ports of the production code, simplified: no UI, no app host, and the platform background-execution glue (Android foreground service, iOS background tasks) is replaced by a `start()` method the host would call. Media "comes from" a file path.

Both engines are libraries with test suites; neither needs an emulator or simulator. Their tests boot the backend harness automatically.

## How an upload works

```
 enqueue(file)                     ┌────────────── backend harness ──────────────┐
      │                            │                                             │
      ▼                            │  POST /uploads ─────────► presigned URL(s)  │
 store (persisted) ──► worker ─────┼─►                                           │
                       one upload  │  PUT /s3/<key>[?partNumber=n] ──► ETag      │
                       at a time   │                                             │
                                   │  POST /uploads/:id/parts {n, etag}          │
                                   │     (multipart only; completes when all     │
                                   │      parts are reported)                    │
                                   └─────────────────────────────────────────────┘
```

1. **Enqueue.** The app hands the engine a file (and optionally the `entryId` of the answer it belongs to). A record is persisted immediately, so it survives process death.
2. **Presign.** The worker asks the backend for upload URLs. Files at or under one part size get a single URL; larger files are split into fixed-size parts, each with its own URL.
3. **Upload.** Bytes go straight to S3 with plain HTTP `PUT`s — no AWS SDK; the presigned URL carries the credentials.
4. **Report.** For multipart, each part's `ETag` (returned by S3) is reported to the backend. Once every part is reported, the backend assembles the object. Single-part uploads complete as soon as S3 has the object (in production, via an S3 event).

The participant's answer is submitted to the server *before* its media finishes uploading — that's the normal case, not an edge case. Uploads keep going in the background after the questionnaire is closed, and must survive the app being killed and relaunched.

## Current state

The engine is ported from production and works on the happy path; the shipped tests cover single-part, multipart, ordering, and a transient S3 error. Its behavior under other failure conditions has not been tested much. The backend harness exists to make those conditions easy to reproduce — see "Fault injection" in `backend/AGENTS.md`.

## Running everything

```
./setup.sh                          # checks toolchains, installs harness deps, runs all tests
cd backend && npm test              # harness self-tests
cd android && ./gradlew test        # Kotlin engine
cd ios && swift test                # Swift engine
cd backend && npm run dev           # run the harness yourself on :4000 (watch its request log)
```

Engine tests boot their own harness on a free port and log its output to `android/build/harness.log` / `ios/.build/harness.log`. To point them at a harness you're running yourself, set `HARNESS_URL=http://127.0.0.1:4000`.

## Tech stack

| Component | Version |
|---|---|
| Node | 20+ (see `backend/.nvmrc`) |
| JDK | 17 |
| Kotlin | 2.2.0 (JVM), coroutines 1.9, OkHttp 4.12, kotlinx.serialization 1.7 |
| Gradle | 8.11.1 via committed wrapper in `android/` |
| Swift | 5.9+ tools (Swift 5 language mode), Xcode 15+ |

## Conventions

- Kotlin package root: `com.dscout.uploader`. Kotlin official code style.
- Swift module: `DscoutUploader`.
- Keep the two engines behaviorally equivalent where practical — a fix in one usually applies to the other.
