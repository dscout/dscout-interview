# Plan sketch: scale question + conditional follow-up

(rough notes, not a finished plan — see `requirements/scale-question-follow-up.md` for what we're building)

- Backend used to have a slider-ish question type (`min`/`max`/`step`) before it got pulled out. We'll need something like that again, plus a way to say "if the answer is low, ask a follow-up question."
- Client doesn't render scale questions at all today, so that's new work regardless of the follow-up piece.
- Follow-up should just look like a normal open-text question, shown right after the scale question when it applies.
- Ship backend and app together in one release, probably? Should double check what happens if they land out of order.
- Tickets: one for backend schema/API, one for client (shared module covers both platforms, so maybe that's a single ticket?).
- Shouldn't be too big a lift — this feels similar to what MULTI_SELECT and OPEN_TEXT already do.

## Open questions (not resolved, just flagged)

- Does the "should we show the follow-up" check happen on the client or does the backend decide it?
- What happens to the "Question X of N" progress indicator when a question may or may not exist depending on a prior answer?

## Next step

Turn this into an actual architecture approach, a ticket breakdown, and a BE/FE release plan.
