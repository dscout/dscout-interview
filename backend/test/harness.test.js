import { test, before, after, beforeEach } from "node:test";
import assert from "node:assert/strict";
import crypto from "node:crypto";
import { createApp } from "../src/app.js";

let server;
let base;

before(async () => {
  server = createApp({ log: false }).listen(0, "127.0.0.1");
  await new Promise((resolve) => server.once("listening", resolve));
  base = `http://127.0.0.1:${server.address().port}`;
});

after(() => server.close());

beforeEach(() => fetch(`${base}/__reset`, { method: "POST" }));

const json = (method, path, body) =>
  fetch(`${base}${path}`, {
    method,
    headers: { "content-type": "application/json" },
    body: body && JSON.stringify(body),
  });

const sha256 = (buf) => crypto.createHash("sha256").update(buf).digest("hex");

test("single-part upload completes on PUT", async () => {
  const bytes = crypto.randomBytes(1000);
  const presign = await (await json("POST", "/uploads", { filename: "a.jpg", size: bytes.length })).json();
  assert.ok(presign.url);

  const put = await fetch(presign.url, { method: "PUT", body: bytes });
  assert.equal(put.status, 200);
  assert.match(put.headers.get("etag"), /^".+"$/);

  const status = await (await fetch(`${base}/uploads/${presign.id}`)).json();
  assert.equal(status.status, "complete");
  assert.equal(status.sha256, sha256(bytes));
});

test("multipart upload completes once every part is reported", async () => {
  const bytes = crypto.randomBytes(3000);
  const chunks = [bytes.subarray(0, 1000), bytes.subarray(1000, 2000), bytes.subarray(2000)];
  const presign = await (await json("POST", "/uploads", { filename: "v.mp4", size: 3000, parts: 3 })).json();
  assert.equal(presign.partUrls.length, 3);

  // Out-of-order is fine; completion waits for all parts.
  for (const i of [2, 0, 1]) {
    const put = await fetch(presign.partUrls[i], { method: "PUT", body: chunks[i] });
    const report = await json("POST", `/uploads/${presign.id}/parts`, {
      partNumber: i + 1,
      etag: put.headers.get("etag"),
    });
    assert.equal(report.status, 200);
  }

  const status = await (await fetch(`${base}/uploads/${presign.id}`)).json();
  assert.equal(status.status, "complete");
  assert.equal(status.sha256, sha256(bytes));
});

test("short uploads fail validation instead of completing", async () => {
  const presign = await (await json("POST", "/uploads", { filename: "a.png", size: 10 })).json();
  await fetch(presign.url, { method: "PUT", body: Buffer.alloc(4) });
  const status = await (await fetch(`${base}/uploads/${presign.id}`)).json();
  assert.equal(status.status, "failed");
  assert.match(status.failureReason, /size mismatch/);
});

test("expired URLs return S3's XML error", async () => {
  await json("PUT", "/__config", { urlTtlSeconds: -1 });
  const presign = await (await json("POST", "/uploads", { filename: "a.jpg", size: 4 })).json();
  const put = await fetch(presign.url, { method: "PUT", body: Buffer.alloc(4) });
  assert.equal(put.status, 403);
  assert.match(await put.text(), /Request has expired/);

  const fresh = await (await json("POST", `/uploads/${presign.id}/presign-parts`, {})).json();
  await json("PUT", "/__config", { urlTtlSeconds: 60 });
  // URL was re-signed while TTL was still -1, so it's expired too.
  assert.equal((await fetch(fresh.url, { method: "PUT", body: Buffer.alloc(4) })).status, 403);
});

test("faults: status, omitEtag, afterHandling", async () => {
  const presign = await (await json("POST", "/uploads", { filename: "v.mp4", size: 2, parts: 2 })).json();

  await json("POST", "/__faults", { route: "s3", part: 1, action: { type: "status", status: 503 } });
  assert.equal((await fetch(presign.partUrls[0], { method: "PUT", body: "a" })).status, 503);

  await json("POST", "/__faults", { route: "s3", action: { type: "omitEtag" } });
  const noEtag = await fetch(presign.partUrls[0], { method: "PUT", body: "a" });
  assert.equal(noEtag.status, 200);
  assert.equal(noEtag.headers.get("etag"), null);

  const put2 = await fetch(presign.partUrls[1], { method: "PUT", body: "b" });
  await json("POST", "/__faults", { route: "parts", action: { type: "status", status: 500, afterHandling: true } });
  const lost = await json("POST", `/uploads/${presign.id}/parts`, { partNumber: 2, etag: put2.headers.get("etag") });
  assert.equal(lost.status, 500);
  const status = await (await fetch(`${base}/uploads/${presign.id}`)).json();
  assert.deepEqual(status.partsReported, [2]);
});

test("drop fault kills the connection and stores nothing", async () => {
  const presign = await (await json("POST", "/uploads", { filename: "a.jpg", size: 4 })).json();
  await json("POST", "/__faults", { route: "s3", action: { type: "drop", afterBytes: 0 } });
  await assert.rejects(fetch(presign.url, { method: "PUT", body: Buffer.alloc(4) }));
  const status = await (await fetch(`${base}/uploads/${presign.id}`)).json();
  assert.deepEqual(status.partsStored, []);
});

test("rejects unsupported file types with 422", async () => {
  const res = await json("POST", "/uploads", { filename: "notes.txt", size: 4 });
  assert.equal(res.status, 422);
});
