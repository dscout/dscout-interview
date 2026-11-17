# android — Kotlin upload engine

See the top-level `AGENTS.md` first.

A plain Kotlin/JVM library (no Android SDK) so `./gradlew test` runs anywhere with JDK 17. In the app, this code runs inside a foreground `UploadService`; here, whoever owns the `Uploader` calls `start()` instead.

```
./gradlew test                                   # all tests (boots ../backend automatically)
./gradlew test --tests '*UploaderTest*'          # one class
HARNESS_URL=http://127.0.0.1:4000 ./gradlew test # use a harness you're running
```

Requires `npm install` in `../backend` first (`../setup.sh` does it).

## Structure (`src/main/kotlin/com/dscout/uploader/`)

| File | Role |
|---|---|
| `Uploader.kt` | Public facade: `enqueue`, `upload` (start/resume), `cancel` (pause), `start`, `status`, `progress`. Also `UploadStatus`. |
| `UploaderConfig.kt` | Base URL, part size (5 MiB), max parts (1000), retry delay (5 min). |
| `worker/UploadWorker.kt` | Single-flight loop: walks pending uploads in id order, one at a time; schedules another pass after `retryDelayMillis` if anything asked to retry. |
| `upload/UploadLogic.kt` | One upload: presign if needed, then single- or multipart. |
| `upload/MediaPresigner.kt` | Calls presign, stores part URLs. Skipped when parts are already stored (resume). |
| `upload/SinglePartUpload.kt`, `MultiPartUpload.kt`, `BaseUpload.kt` | PUT bytes; multipart reports each part's ETag. |
| `upload/PartPlanner.kt` | Part count, offsets, lengths. |
| `s3/S3Client.kt` | Raw OkHttp PUT of a file byte range to a presigned URL. |
| `api/UploadApi.kt`, `HttpUploadApi.kt` | Our backend: presign, report part. |
| `db/UploadStore.kt`, `FileUploadStore.kt`, `UploadRecord.kt` | Persistence (stand-in for Room): upload records + per-part rows, JSON file, rewritten on each change. |

Results flow back as `UploadResult.SUCCESS | RETRY | FAILURE`.

## Tests (`src/test/kotlin/com/dscout/uploader/`)

- `Harness.kt` — boots/reaches the backend; `reset()`, `addFault(json)`, `upload(id)` / `uploads()` for the server's view, `setUrlTtlSeconds`.
- `TestSupport.kt` — `mediaFile`, `tempDir`, `sha256`, `eventually { }`, and `testConfig()` (1 KiB parts, 100 ms retry delay so multipart and retry paths run fast).
- `UploaderTest.kt`, `PartPlannerTest.kt`, `FileUploadStoreTest.kt`.

Simulate process death by closing an `Uploader` and constructing a new one on the same store file.
