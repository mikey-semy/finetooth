# Banner for the project's root instructions file

Placed at the very top of the file that is read in EVERY session of the project
(`CLAUDE.md`, `AGENTS.md`, `.cursorrules` — whichever you use). Without it a new
session simply will not know that the review exists and will start a parallel one of its own.

It dies together with the review directory — it says so itself.

---

> ## ⏳ A full-project review is in progress — read `docs/review/README.md` first
>
> The whole code base is being reviewed block by block before the customer
> install. The review outlives any single context window, so **all of its state
> lives on disk, not in a conversation**: run `make review-status` to see where
> it stands and which block is next. Do not start a fresh review of your own and
> do not fix findings outside its rules — both are described in that README.
>
> When the review closes, `docs/review/` is deleted in one MR and this banner
> goes with it. The lasting lessons move into this file, into ADRs and into
> tests; the scaffolding does not survive the building.
