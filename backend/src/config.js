// Runtime-tunable harness settings. Mutable on purpose: tests change them via
// PUT /__config without restarting the server.
export const config = {
  // How long presigned URLs stay valid. Real S3 URLs are signed for a day but
  // in production effectively expire whenever the signing credentials rotate
  // (sometimes minutes), so clients must treat expiry as unpredictable.
  urlTtlSeconds: Number(process.env.URL_TTL_SECONDS ?? 15 * 60),

  // S3's hard limit. Clients pick their own part size / count beneath it.
  maxParts: 10_000,

  allowedExtensions: ["mp4", "mov", "m4v", "webm", "jpg", "jpeg", "png", "heic", "m4a"],
};

export const defaults = { ...config };

export function resetConfig() {
  Object.assign(config, defaults);
}
