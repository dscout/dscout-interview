import express from "express";
import cors from "cors";
import { surveyRouter } from "./routes/survey.js";

const PORT = process.env.PORT || 4000;

const app = express();

// Permissive CORS is intentional here: this backend is only ever reached
// from an Android emulator / iOS simulator on the same machine during the
// interview exercise, never deployed or exposed publicly.
app.use(cors());
app.use(express.json());
app.use(surveyRouter);

app.listen(PORT, () => {
  console.log(`Survey backend listening on http://localhost:${PORT}`);
});
