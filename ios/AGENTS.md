# ios — Swift upload engine

See the top-level `AGENTS.md` first.

A Swift package (macOS 13+/iOS 16+, Swift 5 language mode) so `swift test` runs without a simulator. In the app, this sits behind the media pipeline service and is kicked when the scene becomes active, when an entry is submitted, and from a background task; here, whoever owns the `Uploader` calls `start()`.

```
swift test                                     # all tests (boots ../backend automatically)
swift test --filter UploaderTests              # one class
HARNESS_URL=http://127.0.0.1:4000 swift test   # use a harness you're running
```

Requires `npm install` in `../backend` first (`../setup.sh` does it). Opening `Package.swift` in Xcode works too.

## Structure (`Sources/DscoutUploader/`)

| File | Role |
|---|---|
| `Uploader.swift` | Public facade: `enqueue`, `upload(id:)` (start/resume), `cancel(id:)` (pause), `start`, `status`, `progress`, `invalidate`. |
| `UploaderConfig.swift` | Base URL, part size (5 MiB), max parts (1000), retry delay (5 min). |
| `Pipeline/UploadWorker.swift` | Single-flight loop on a serial queue: walks pending uploads in id order, one at a time; schedules another pass after `retryDelay` if anything asked to retry. |
| `Pipeline/UploadLogic.swift` | One upload: presign if needed, then single- or multipart. |
| `Pipeline/MediaPresigner.swift` | Calls presign, stores part URLs. Skipped when parts are already stored (resume). |
| `Pipeline/Uploads.swift` | `BaseUpload`, `SinglePartUpload`, `MultipartUpload`: PUT bytes; multipart reports each part's ETag. |
| `Pipeline/PartPlanner.swift` | Part count and byte ranges. |
| `Networking/S3Client.swift` | Raw `URLSession` PUT to a presigned URL. |
| `Networking/UploadAPI.swift` | Our backend: presign, report part. |
| `Networking/URLSession+Synchronous.swift` | Semaphore wrapper; the worker queue blocks on each request. |
| `Persistence/UploadStore.swift`, `FileUploadStore.swift`, `UploadRecord.swift` | Persistence (stand-in for Core Data): upload records + per-part rows, JSON file, rewritten on each change. |

Results flow back as `UploadResult.success | .retry | .failure`.

## Tests (`Tests/DscoutUploaderTests/`)

- `Harness.swift` — boots/reaches the backend; `reset()`, `addFault(json)`, `upload(_:)` / `uploads()` for the server's view, `setURLTTL(seconds:)`.
- `TestSupport.swift` — `makeMediaFile`, `makeTempDirectory`, `sha256(of:)`, `eventually { }`, and `testConfig()` (1 KiB parts, 0.1 s retry delay so multipart and retry paths run fast).
- `UploaderTests.swift`, `PartPlannerTests.swift`, `FileUploadStoreTests.swift`.

Simulate app termination by invalidating an `Uploader` and constructing a new one on the same store file.
