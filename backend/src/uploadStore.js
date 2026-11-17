import crypto from "node:crypto";

// In-memory only. Everything resets on restart (or POST /__reset).
const uploads = new Map(); // id -> Upload
const byKey = new Map(); // key -> id

/**
 * Upload record. Mirrors the production `presign_requests` row, minus auth.
 *
 *   status: "pending"  presigned, bytes not all here yet
 *           "complete" object assembled and size matches what was declared
 *           "failed"   object assembled but failed validation (e.g. size)
 */
export function createUpload({ filename, size, parts, entryId }) {
  const id = crypto.randomUUID();
  const key = `presigned/${crypto.randomUUID()}/${sanitize(filename)}`;
  const upload = {
    id,
    key,
    filename,
    entryId: entryId ?? null,
    size,
    parts: parts ?? 1,
    multipart: (parts ?? 1) > 1,
    // S3's multipart UploadId; only meaningful when multipart.
    s3UploadId: (parts ?? 1) > 1 ? crypto.randomBytes(12).toString("hex") : null,
    storedParts: new Map(), // partNumber -> { bytes: Buffer, etag }
    reportedEtags: new Map(), // partNumber -> etag (multipart only)
    status: "pending",
    failureReason: null,
    sha256: null,
    assembledSize: null,
    createdAt: new Date().toISOString(),
    completedAt: null,
  };
  uploads.set(id, upload);
  byKey.set(key, id);
  return upload;
}

export function getUpload(id) {
  return uploads.get(id);
}

export function getUploadByKey(key) {
  return uploads.get(byKey.get(key));
}

export function listUploads() {
  return [...uploads.values()];
}

export function resetUploads() {
  uploads.clear();
  byKey.clear();
}

export function etagFor(bytes) {
  return `"${crypto.createHash("md5").update(bytes).digest("hex")}"`;
}

export function stripQuotes(etag) {
  return String(etag).replace(/^"+|"+$/g, "");
}

/**
 * Concatenate parts 1..N, validate against the declared size, and settle the
 * upload. Production does the S3 CompleteMultipartUpload + validation in a
 * background job; here it is synchronous. Idempotent: settled uploads are
 * left alone.
 */
export function finalize(upload) {
  if (upload.status !== "pending") return upload;

  const chunks = [];
  for (let n = 1; n <= upload.parts; n++) chunks.push(upload.storedParts.get(n).bytes);
  const object = Buffer.concat(chunks);

  upload.assembledSize = object.length;
  upload.sha256 = crypto.createHash("sha256").update(object).digest("hex");
  upload.completedAt = new Date().toISOString();
  if (object.length !== upload.size) {
    upload.status = "failed";
    upload.failureReason = `size mismatch: declared ${upload.size} bytes, received ${object.length}`;
  } else {
    upload.status = "complete";
  }
  return upload;
}

export function serialize(upload) {
  return {
    id: upload.id,
    key: upload.key,
    filename: upload.filename,
    entryId: upload.entryId,
    size: upload.size,
    parts: upload.parts,
    multipart: upload.multipart,
    status: upload.status,
    failureReason: upload.failureReason,
    partsStored: [...upload.storedParts.keys()].sort((a, b) => a - b),
    partsReported: [...upload.reportedEtags.keys()].sort((a, b) => a - b),
    assembledSize: upload.assembledSize,
    sha256: upload.sha256,
    createdAt: upload.createdAt,
    completedAt: upload.completedAt,
  };
}

function sanitize(filename) {
  const dot = filename.lastIndexOf(".");
  const base = (dot > 0 ? filename.slice(0, dot) : filename)
    .slice(0, 64)
    .replace(/[^a-zA-Z0-9_-]/g, "")
    .toLowerCase();
  const ext = dot > 0 ? filename.slice(dot + 1).toLowerCase() : "";
  return `${base || "file"}${ext ? `.${ext}` : ""}`;
}
