# Upload priority

## Background

Today the upload engine treats every file the same: uploads go one at a time, oldest first. For most media that's fine, since nobody is waiting on a diary entry's video to land in the next five minutes.

Some media is time-sensitive, though:

- **Auto-recruit.** For some studies, responses are evaluated automatically as soon as they're complete, and a response can't be evaluated until its media has arrived. A participant whose screener video sits behind an hour of unrelated diary footage is effectively at the back of the line for a spot they may have already earned.
- **Participants who know they're late.** Sometimes a participant knows a deadline is close (an entry due today, a mission about to close) and is watching the uploads screen. Right now they can't do anything about it.

## What we want

1. **Product-driven priority.** Uploads that belong to certain products (auto-recruit to start with) go ahead of normal uploads, without anyone having to do anything.
2. **"Send this now."** On the uploads screen, a participant can tap a queued upload to move it to the front.

Both apps need this, and they should behave the same way.

## Out of scope

- Server changes. The backend doesn't know or care what order uploads arrive in.
- The uploads screen UI itself. Assume it exists and can call into the engine.

## Not decided yet

Product hasn't settled every detail. Part of this work is figuring out which questions need answers, proposing answers where you have an opinion, and saying what each choice would cost.
