import express from "express";
import { uploadsRouter } from "./routes/uploads.js";
import { s3Router } from "./routes/s3.js";
import { adminRouter } from "./routes/admin.js";

export function createApp({ log = true } = {}) {
  const app = express();

  if (log) {
    app.use((req, res, next) => {
      res.on("finish", () => {
        const path = req.path.startsWith("/s3/")
          ? `/s3/…${req.path.slice(-24)}${req.query.partNumber ? ` part=${req.query.partNumber}` : ""}`
          : req.path;
        console.log(`${req.method} ${path} -> ${res.statusCode}`);
      });
      next();
    });
  }

  // The fake S3 router reads raw bodies itself, so mount it before JSON parsing.
  app.use(s3Router);
  app.use(express.json());
  app.use(uploadsRouter);
  app.use(adminRouter);

  return app;
}
