# backend — upload harness

A small Express server that stands in for two things the mobile engines talk to: **our API** (presign + part reporting) and **S3** (accepting the bytes). It mirrors the production contract closely enough that client behavior carries over, and adds controls for injecting failures. See the top-level `AGENTS.md` first.

Not production code and not part of what you're expected to change — it's the thing you code against. Everything is in memory and resets on restart or `POST /__reset`. There's no auth.

## What's here

- `src/server.js` — listens on `PORT` (default 4000; `0` picks a free port). Prints `Upload harness listening on http://…` — the engine test suites parse that line.
- `src/app.js` — mounts the routers; logs one line per request.
- `src/routes/uploads.js` — the API: presign, report part, re-sign, status.
- `src/routes/s3.js` — fake S3: accepts PUTs to presigned URLs, returns `ETag`s, S3-style XML errors.
- `src/routes/admin.js` — `/__faults`, `/__config`, `/__reset`.
- `src/faults.js` — fault rule matching (the rule format is documented at the top of this file).
- `src/uploadStore.js` — upload records, assembly, and validation.
- `src/signing.js` — HMAC stand-in for SigV4; URLs carry an `exp` timestamp.

```
npm install
npm run dev    # auto-restarts on change
npm test       # harness self-tests
```

## API

### `POST /uploads` — presign

```json
{ "filename": "clip.mp4", "size": 5000, "parts": 5, "entryId": "optional" }
```

- Omit `parts` (or send `1`) for a single-part upload → `201 { id, key, parts: 1, url }`.
- `parts > 1` → `201 { id, key, parts, partUrls: [part1Url, part2Url, …] }`.
- `422` for unsupported file extensions (`mp4 mov m4v webm jpg jpeg png heic m4a`), `400` for bad input.
- Every call creates a **new** upload with a new key. Presigning again never resumes an earlier upload.

The server doesn't care how you split the file, but the parts are concatenated in part-number order and the result must be exactly `size` bytes.

### `PUT <url>` — upload bytes (fake S3)

Send the raw bytes as the body. On success: `200` with an `ETag` header (quoted, like S3: `"9e107d9d…"`).

Errors use S3's XML format, not JSON:

| Status | `<Code>` | When |
|---|---|---|
| `403` | `AccessDenied` / `<Message>Request has expired</Message>` | URL past its expiry |
| `403` | `SignatureDoesNotMatch` | URL tampered with |
| `404` | `NoSuchUpload` | multipart upload already completed |
| `5xx` | `InternalError` | injected fault |

Single-part uploads complete the moment the PUT succeeds. Re-PUTting a part replaces it.

### `POST /uploads/:id/parts` — report a part (multipart only)

```json
{ "partNumber": 2, "etag": "\"9e107d9d…\"" }
```

- The `etag` must match what S3 returned for that part (quotes optional). → `200 { id, status, partsReported }`.
- When every part has been reported, the upload is assembled and `status` becomes `complete` (or `failed`, see below).
- Reporting the same part again is a no-op, so retries are safe.
- `409` if that part hasn't been PUT yet; `400` for a bad part number or mismatched ETag; `404` unknown upload.

### `POST /uploads/:id/presign-parts` — fresh URLs for an existing upload

```json
{ "partNumbers": [3, 4] }
```

→ `{ "partUrls": { "3": "…", "4": "…" } }` for multipart, `{ "url": "…" }` for single-part (body ignored). `409` if the upload is no longer pending. Useful when URLs have expired — parts already uploaded and reported stay valid.

### `GET /uploads/:id`, `GET /uploads`

The server's view of an upload:

```json
{
  "id": "…", "key": "presigned/…/clip.mp4", "filename": "clip.mp4", "entryId": null,
  "size": 5000, "parts": 5, "multipart": true,
  "status": "pending | complete | failed",
  "failureReason": null,
  "partsStored": [1, 2, 3],      // parts S3 has bytes for
  "partsReported": [1, 2],       // parts whose ETag was reported
  "assembledSize": null, "sha256": null   // set once assembled
}
```

`failed` means the object was assembled but didn't validate (e.g. `size mismatch: declared 10000 bytes, received 4096`). `sha256` is of the assembled object — compare it to the source file.

## Fault injection

Register rules with `POST /__faults`; each matching request misbehaves, then the rule's use count goes down. `GET /__faults` lists rules with hit counts; `DELETE /__faults` clears them.

```json
{
  "route": "presign | s3 | parts | presign-parts | *",
  "part": 2,            // optional: only this part number (s3 single-part uploads are part 1)
  "uploadId": "…",      // optional: only this upload
  "times": 1,           // default 1; null = every matching request until cleared
  "action": { "type": "…" }
}
```

| `action` | Effect |
|---|---|
| `{"type":"status","status":500}` | Respond with that status; do nothing. |
| `{"type":"status","status":500,"afterHandling":true}` | Do the work, then respond with that status — the server committed but the client never hears about it. |
| `{"type":"expire"}` | (s3) Respond as if the URL expired. |
| `{"type":"drop","afterBytes":0}` | (s3) Kill the connection after reading that many body bytes; nothing is stored. |
| `{"type":"omitEtag"}` | (s3) Store the bytes, respond `200` with no `ETag` header. |
| `{"type":"delay","ms":1000}` | Wait, then handle normally. |

Example — fail S3 for part 2 twice, then let it through:

```
curl -X POST localhost:4000/__faults -H 'content-type: application/json' \
  -d '{"route":"s3","part":2,"times":2,"action":{"type":"status","status":503}}'
```

The engine test suites wrap this as `Harness.addFault(json)`.

### Other controls

- `PUT /__config {"urlTtlSeconds": 2}` — lifetime of URLs signed from now on (default 900; env `URL_TTL_SECONDS`). Production URL lifetime is unpredictable and can be minutes.
- `POST /__reset` — clear uploads, faults, and config.

## How this maps to production

| Harness | Production |
|---|---|
| `POST /uploads` | GraphQL `presignVideo` / `presignPicture` / `presignTrack` (links media to the answer at presign time) |
| `POST /uploads/:id/parts` | GraphQL `presignProgress` |
| `POST /uploads/:id/presign-parts` | GraphQL `presignedPartUrl` |
| Single-part completes on PUT | S3 ObjectCreated → SNS → webhook |
| Multipart completes on last report | Server calls S3 `CompleteMultipartUpload` |
| `status: failed` size check | Post-upload validation in the media processing job |
