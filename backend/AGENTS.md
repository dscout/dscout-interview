# backend

A small Express API for the survey app. See the top-level `AGENTS.md` first for repo-wide context (tech stack, backend contract, current skeleton state).

## What's here

- `src/server.js` — Express app setup, CORS, JSON body parsing, router mounting, `app.listen`.
- `src/routes/survey.js` — `GET /survey` and `POST /responses`.
- `src/store.js` — the data "layer": plain in-memory variables. **Data resets on every server restart — this is intentional**, not a bug. There is no database to install or configure.

## Run

```
npm install
npm start        # or: npm run dev (auto-restarts on file changes)
```

Defaults to port 4000 (override with `PORT`).

## Current state

`GET /survey` returns a real four-question survey from `store.js`, covering all three types (`SINGLE_SELECT`, `MULTI_SELECT`, and two `OPEN_TEXT`). `POST /responses` (`routes/survey.js`) validates `SINGLE_SELECT` (must match one of the question's `options`) and `OPEN_TEXT` (must be non-empty) answers, returning `400` on failure. `MULTI_SELECT` answers are intentionally left unvalidated — the client's multi-select UI is a known stub, so there's nothing well-formed to validate yet.

## Notes

- CORS is deliberately permissive (`cors()` with no options) — this backend is only ever reached from an Android emulator or iOS Simulator on the same machine during local development, never deployed or exposed publicly. Don't tighten this without a reason tied to that changing.
- Plain JavaScript (not TypeScript) was a deliberate choice for setup-script simplicity, not an oversight. There is no compile-time guarantee that `backend`'s JSON shapes match `shared`'s Kotlin models — keep them manually in sync when either changes.
