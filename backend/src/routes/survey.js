import { Router } from "express";
import { getSurvey, addResponse } from "../store.js";

export const surveyRouter = Router();

surveyRouter.get("/survey", (_req, res) => {
  res.json(getSurvey());
});

// Real per-type validation for SINGLE_SELECT and OPEN_TEXT. MULTI_SELECT is
// intentionally left unvalidated here — the client's multi-select UI is a
// known stub (see shared/.../App.kt), so there's nothing well-formed to
// validate yet.
function findQuestion(survey, questionId) {
  return survey.questions.find((q) => q.id === questionId);
}

function validateAnswer(question, answer) {
  if (!question) return `Unknown question id: ${answer.questionId}`;

  if (question.type === "SINGLE_SELECT") {
    if (!question.options.includes(answer.value)) {
      return `Invalid option for question ${question.id}: ${answer.value}`;
    }
  }

  if (question.type === "OPEN_TEXT") {
    if (typeof answer.value !== "string" || answer.value.trim() === "") {
      return `Question ${question.id} requires non-empty text`;
    }
  }

  return null;
}

surveyRouter.post("/responses", (req, res) => {
  const survey = getSurvey();
  const answers = req.body?.answers ?? [];

  for (const answer of answers) {
    const question = findQuestion(survey, answer.questionId);
    const error = validateAnswer(question, answer);
    if (error) {
      return res.status(400).json({ error });
    }
  }

  const stored = addResponse(req.body ?? {});
  res.status(201).json(stored);
});
