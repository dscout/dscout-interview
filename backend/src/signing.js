import crypto from "node:crypto";
import { config } from "./config.js";

// Stand-in for AWS SigV4. A URL is valid if its signature matches the
// (key, uploadId, partNumber, exp) tuple and `exp` hasn't passed.
const SECRET = crypto.randomBytes(32);

function signature(key, uploadId, partNumber, exp) {
  return crypto
    .createHmac("sha256", SECRET)
    .update(`${key}\n${uploadId ?? ""}\n${partNumber ?? ""}\n${exp}`)
    .digest("hex");
}

export function presignUrl(baseUrl, { key, uploadId, partNumber }) {
  const exp = Math.floor(Date.now() / 1000) + config.urlTtlSeconds;
  const params = new URLSearchParams();
  if (uploadId) params.set("uploadId", uploadId);
  if (partNumber) params.set("partNumber", String(partNumber));
  params.set("exp", String(exp));
  params.set("sig", signature(key, uploadId, partNumber, exp));
  return `${baseUrl}/s3/${key}?${params}`;
}

/** Returns null if valid, otherwise "expired" | "bad-signature". */
export function verifyUrl({ key, uploadId, partNumber, exp, sig }) {
  const expected = signature(key, uploadId, partNumber, exp);
  if (
    !sig ||
    sig.length !== expected.length ||
    !crypto.timingSafeEqual(Buffer.from(sig), Buffer.from(expected))
  ) {
    return "bad-signature";
  }
  if (Number(exp) < Date.now() / 1000) return "expired";
  return null;
}
