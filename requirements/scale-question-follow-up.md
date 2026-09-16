# Requirements: Scale question with conditional follow-up

## Summary

Add a new **scale** question type to the survey (a numeric range the respondent picks a single value from, e.g. 0–10), and support attaching an optional **follow-up question** to a scale question that only appears when the respondent's answer meets a defined condition.

## Functional requirements

1. A scale question has a numeric range (`min`, `max`) and a `step`. The respondent picks exactly one value in that range.
2. A scale question may optionally define a **follow-up condition**: a threshold (e.g. "answer ≤ 6") that determines whether a follow-up question is shown.
3. If the respondent's scale answer meets the threshold, the follow-up question is presented immediately after the scale question, before the survey continues.
4. If the respondent's scale answer does not meet the threshold, the follow-up question is skipped entirely — not shown, not required, and not counted in the question progress (e.g. "Question 3 of 4" should reflect only what the respondent actually sees).
5. A follow-up question, when shown, is always an open-text question. (Follow-ups do not themselves carry further conditions or follow-ups — one level only.)
6. The respondent can navigate Back out of a shown follow-up question; if they then change the scale answer such that the condition no longer holds, the follow-up should no longer be presented.
7. Both the scale answer and the follow-up answer (if shown) are submitted to the backend and included in the confirmation screen.
8. Existing question types (single-select, multi-select, open-text) are unaffected by this feature.

## Acceptance criteria

- Respondent can complete a survey containing a scale question with a follow-up, in both the "condition met" and "condition not met" paths, on both Android and iOS.
- Submitted responses persist the scale answer, and the follow-up answer only when it was actually shown and answered.
- A survey containing a scale question with **no** follow-up configured behaves as a plain scale question (no regression for that simpler case).

## Explicit non-goals

- No authoring UI for survey creators — question definitions are still hardcoded in the backend store, same as today.
- No support for multiple thresholds/branches on a single scale question (e.g. different follow-ups for different ranges) — one threshold, one follow-up.
- No support for follow-up chains (a follow-up triggering another follow-up).
- No requirement that the follow-up question type be configurable — it's always open-text for this feature.

## Out of scope for this document

How this is implemented — question schema shape, client vs. server validation, and how backend and client changes are sequenced/released — is intentionally not specified here. See `plans/scale-question-follow-up.md`.
