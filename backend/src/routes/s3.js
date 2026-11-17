import { Router } from "express";
import { verifyUrl } from "../signing.js";
import { takeFault, sleep } from "../faults.js";
import { getUploadByKey, etagFor, finalize } from "../uploadStore.js";

// Fake S3. Accepts PUTs to presigned URLs:
//   single part:  PUT /s3/<key>?exp=&sig=
//   multipart:    PUT /s3/<key>?uploadId=&partNumber=&exp=&sig=
// Errors use S3's XML error format, so clients must not assume JSON.
export const s3Router = Router();

s3Router.put(/^\/s3\/(.+)$/, async (req, res) => {
  const key = req.params[0];
  const { uploadId, partNumber: partParam, exp, sig } = req.query;
  const partNumber = partParam ? Number(partParam) : undefined;

  const invalid = verifyUrl({ key, uploadId, partNumber, exp, sig });
  if (invalid === "bad-signature") {
    return s3Error(res, 403, "SignatureDoesNotMatch", "The request signature we calculated does not match the signature you provided.");
  }

  const upload = getUploadByKey(key);
  const fault = takeFault("s3", { part: partNumber ?? 1, uploadId: upload?.id });
  if (fault?.type === "delay") await sleep(fault.ms);

  if (invalid === "expired" || fault?.type === "expire") {
    return s3Error(res, 403, "AccessDenied", "Request has expired", `<Expires>${new Date(Number(exp) * 1000).toISOString()}</Expires>`);
  }
  if (!upload) return s3Error(res, 404, "NoSuchKey", "The specified key does not exist.");
  if (upload.multipart && (uploadId !== upload.s3UploadId || !partNumber)) {
    return s3Error(res, 400, "InvalidRequest", "Multipart upload requires uploadId and partNumber.");
  }
  if (upload.multipart && upload.status !== "pending") {
    return s3Error(res, 404, "NoSuchUpload", "The specified multipart upload does not exist. The upload ID may be invalid, or the upload may have been aborted or completed.");
  }
  if (fault?.type === "status" && !fault.afterHandling) {
    req.resume();
    return s3Error(res, fault.status, "InternalError", "We encountered an internal error. Please try again.");
  }

  const body = await readBody(req, fault?.type === "drop" ? fault.afterBytes ?? 0 : null);
  if (body === null) return; // connection dropped by fault

  const part = partNumber ?? 1;
  const etag = etagFor(body);
  upload.storedParts.set(part, { bytes: body, etag });

  // Single-part uploads complete when the object lands — production learns
  // this from an S3 ObjectCreated event, not from the client.
  if (!upload.multipart) finalize(upload);

  if (fault?.type === "status") {
    return s3Error(res, fault.status, "InternalError", "We encountered an internal error. Please try again.");
  }
  if (fault?.type !== "omitEtag") res.set("ETag", etag);
  res.status(200).end();
});

function s3Error(res, status, code, message, extra = "") {
  res
    .status(status)
    .type("application/xml")
    .send(
      `<?xml version="1.0" encoding="UTF-8"?>\n<Error><Code>${code}</Code><Message>${message}</Message>${extra}<RequestId>harness</RequestId></Error>`,
    );
}

/** Read the whole body; if `dropAfter` is set, kill the socket once that many bytes arrive. */
function readBody(req, dropAfter) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    let received = 0;
    let dropped = false;
    const drop = () => {
      dropped = true;
      req.socket.destroy();
      resolve(null);
    };
    if (dropAfter === 0) return drop();
    req.on("data", (chunk) => {
      if (dropped) return;
      chunks.push(chunk);
      received += chunk.length;
      if (dropAfter !== null && received >= dropAfter) drop();
    });
    req.on("end", () => !dropped && resolve(Buffer.concat(chunks)));
    req.on("error", (err) => !dropped && reject(err));
  });
}
