import crypto from "node:crypto";

// Fault injection. Tests (or a human with curl) register rules; each route
// asks `takeFault` whether the current request should misbehave.
//
// Rule shape:
//   {
//     route:    "presign" | "s3" | "parts" | "presign-parts" | "*",
//     part:     <number>   optional, only match this part number
//     uploadId: <string>   optional, only match this upload
//     times:    <number>   how many matching requests to affect (default 1);
//                          null = every matching request until cleared
//     action:   one of
//       { type: "status", status: 500 }
//           Respond with `status` without doing any work.
//       { type: "status", status: 500, afterHandling: true }
//           Do the work, THEN respond with `status` — i.e. the server
//           committed but the client never hears about it.
//       { type: "expire" }        (s3 only) respond as an expired URL (403)
//       { type: "drop", afterBytes: 0 }
//                                 (s3 only) kill the connection after reading
//                                 `afterBytes` of the body; nothing is stored
//       { type: "omitEtag" }      (s3 only) store bytes, respond 200 w/o ETag
//       { type: "delay", ms: 1000 }
//           Wait, then handle normally.
//   }
const ROUTES = new Set(["presign", "s3", "parts", "presign-parts", "*"]);
const ACTIONS = new Set(["status", "expire", "drop", "omitEtag", "delay"]);
const S3_ONLY = new Set(["expire", "drop", "omitEtag"]);

let rules = [];

export function addFault(input) {
  const { route, part, uploadId, action } = input ?? {};
  const times = input?.times === undefined ? 1 : input.times;
  if (!ROUTES.has(route)) throw new Error(`route must be one of ${[...ROUTES].join(", ")}`);
  if (!action || !ACTIONS.has(action.type)) {
    throw new Error(`action.type must be one of ${[...ACTIONS].join(", ")}`);
  }
  if (S3_ONLY.has(action.type) && route !== "s3") {
    throw new Error(`action ${action.type} only applies to route "s3"`);
  }
  if (action.type === "status" && !Number.isInteger(action.status)) {
    throw new Error("status action needs an integer `status`");
  }
  if (times !== null && !(Number.isInteger(times) && times > 0)) {
    throw new Error("times must be a positive integer or null");
  }
  const rule = { id: crypto.randomUUID(), route, part, uploadId, action, times, hits: 0 };
  rules.push(rule);
  return rule;
}

export function listFaults() {
  return rules;
}

export function clearFaults() {
  rules = [];
}

/** Returns the action to apply to this request, or null. Consumes one use. */
export function takeFault(route, { part, uploadId } = {}) {
  const rule = rules.find(
    (r) =>
      (r.route === route || r.route === "*") &&
      (r.part === undefined || r.part === part) &&
      (r.uploadId === undefined || r.uploadId === uploadId) &&
      (r.times === null || r.hits < r.times),
  );
  if (!rule) return null;
  rule.hits += 1;
  console.log(`  !! fault ${rule.action.type} on ${route}${part ? ` part ${part}` : ""}`);
  return rule.action;
}

export const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
