import { Router } from "express";
import { config, resetConfig } from "../config.js";
import { addFault, listFaults, clearFaults } from "../faults.js";
import { resetUploads } from "../uploadStore.js";

// Test-only controls. Double-underscore prefix so they're never mistaken for
// part of the client contract.
export const adminRouter = Router();

adminRouter.get("/__faults", (_req, res) => res.json(listFaults()));

adminRouter.post("/__faults", (req, res) => {
  try {
    res.status(201).json(addFault(req.body));
  } catch (err) {
    res.status(400).json({ error: err.message });
  }
});

adminRouter.delete("/__faults", (_req, res) => {
  clearFaults();
  res.status(204).end();
});

adminRouter.get("/__config", (_req, res) => res.json(config));

/** Body: { urlTtlSeconds } — affects URLs signed after the change. */
adminRouter.put("/__config", (req, res) => {
  const { urlTtlSeconds } = req.body ?? {};
  if (urlTtlSeconds !== undefined) {
    if (!Number.isInteger(urlTtlSeconds)) {
      return res.status(400).json({ error: "urlTtlSeconds must be an integer" });
    }
    config.urlTtlSeconds = urlTtlSeconds;
  }
  res.json(config);
});

/** Clears uploads, faults, and config overrides. */
adminRouter.post("/__reset", (_req, res) => {
  resetUploads();
  clearFaults();
  resetConfig();
  res.status(204).end();
});
