import { Router } from "express";
import { config } from "../config.js";
import { presignUrl } from "../signing.js";
import { takeFault, sleep } from "../faults.js";
import {
  createUpload,
  getUpload,
  listUploads,
  serialize,
  stripQuotes,
  finalize,
} from "../uploadStore.js";

export const uploadsRouter = Router();

const baseUrl = (req) => `${req.protocol}://${req.get("host")}`;

/**
 * Presign. Body: { filename, size, parts?, entryId? }
 * `parts` > 1 makes it a multipart upload. Every call creates a brand-new
 * upload with a new key — retrying a presign never resumes an old one.
 */
uploadsRouter.post("/uploads", async (req, res) => {
  const fault = takeFault("presign");
  if (fault?.type === "delay") await sleep(fault.ms);
  if (fault?.type === "status" && !fault.afterHandling) {
    return res.status(fault.status).json({ error: "injected fault" });
  }

  const { filename, size, parts, entryId } = req.body ?? {};
  if (typeof filename !== "string" || !filename) {
    return res.status(400).json({ error: "filename is required" });
  }
  const ext = filename.split(".").pop().toLowerCase();
  if (!filename.includes(".") || !config.allowedExtensions.includes(ext)) {
    return res.status(422).json({ error: `unsupported file type: ${filename}` });
  }
  if (!Number.isInteger(size) || size <= 0) {
    return res.status(400).json({ error: "size must be a positive integer (bytes)" });
  }
  if (parts !== undefined && !(Number.isInteger(parts) && parts >= 1 && parts <= config.maxParts)) {
    return res.status(400).json({ error: `parts must be an integer from 1 to ${config.maxParts}` });
  }

  const upload = createUpload({ filename, size, parts, entryId });
  const body = { id: upload.id, key: upload.key, parts: upload.parts };
  if (upload.multipart) {
    body.partUrls = Array.from({ length: upload.parts }, (_, i) =>
      presignUrl(baseUrl(req), { key: upload.key, uploadId: upload.s3UploadId, partNumber: i + 1 }),
    );
  } else {
    body.url = presignUrl(baseUrl(req), { key: upload.key });
  }

  if (fault?.type === "status") return res.status(fault.status).json({ error: "injected fault" });
  res.status(201).json(body);
});

/**
 * Report one uploaded part's ETag. Body: { partNumber, etag }
 * The upload completes automatically once every part has been reported.
 * Reporting the same part again with the same ETag is a no-op.
 */
uploadsRouter.post("/uploads/:id/parts", async (req, res) => {
  const upload = getUpload(req.params.id);
  const { partNumber, etag } = req.body ?? {};
  const fault = takeFault("parts", { part: partNumber, uploadId: upload?.id });
  if (fault?.type === "delay") await sleep(fault.ms);
  if (fault?.type === "status" && !fault.afterHandling) {
    return res.status(fault.status).json({ error: "injected fault" });
  }

  if (!upload) return res.status(404).json({ error: "upload not found" });
  if (!upload.multipart) {
    return res.status(400).json({ error: "single-part uploads complete on PUT; nothing to report" });
  }
  if (!Number.isInteger(partNumber) || partNumber < 1 || partNumber > upload.parts) {
    return res.status(400).json({ error: `partNumber must be an integer from 1 to ${upload.parts}` });
  }
  const stored = upload.storedParts.get(partNumber);
  if (!stored) return res.status(409).json({ error: `part ${partNumber} has not been uploaded` });
  if (typeof etag !== "string" || stripQuotes(etag) !== stripQuotes(stored.etag)) {
    return res.status(400).json({ error: `etag does not match the stored part ${partNumber}` });
  }

  upload.reportedEtags.set(partNumber, stripQuotes(etag));
  if (upload.reportedEtags.size === upload.parts) finalize(upload);

  if (fault?.type === "status") return res.status(fault.status).json({ error: "injected fault" });
  res.json({ id: upload.id, status: upload.status, partsReported: serialize(upload).partsReported });
});

/**
 * Fresh URLs for an existing upload, e.g. after the originals expired.
 * Body: { partNumbers: [2, 3] } for multipart; ignored for single-part.
 * Returns { partUrls: { "2": url, "3": url } } or { url }.
 */
uploadsRouter.post("/uploads/:id/presign-parts", async (req, res) => {
  const upload = getUpload(req.params.id);
  const fault = takeFault("presign-parts", { uploadId: upload?.id });
  if (fault?.type === "delay") await sleep(fault.ms);
  if (fault?.type === "status") return res.status(fault.status).json({ error: "injected fault" });

  if (!upload) return res.status(404).json({ error: "upload not found" });
  if (upload.status !== "pending") return res.status(409).json({ error: `upload is ${upload.status}` });
  if (!upload.multipart) return res.json({ url: presignUrl(baseUrl(req), { key: upload.key }) });

  const { partNumbers } = req.body ?? {};
  if (!Array.isArray(partNumbers) || !partNumbers.every((n) => Number.isInteger(n) && n >= 1 && n <= upload.parts)) {
    return res.status(400).json({ error: `partNumbers must be integers from 1 to ${upload.parts}` });
  }
  const partUrls = Object.fromEntries(
    partNumbers.map((n) => [
      String(n),
      presignUrl(baseUrl(req), { key: upload.key, uploadId: upload.s3UploadId, partNumber: n }),
    ]),
  );
  res.json({ partUrls });
});

uploadsRouter.get("/uploads", (_req, res) => {
  res.json(listUploads().map(serialize));
});

uploadsRouter.get("/uploads/:id", (req, res) => {
  const upload = getUpload(req.params.id);
  if (!upload) return res.status(404).json({ error: "upload not found" });
  res.json(serialize(upload));
});
