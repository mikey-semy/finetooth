# Баннер в корневой файл инструкций проекта

Ставится в самое начало файла, который читается в КАЖДОЙ сессии проекта
(`CLAUDE.md`, `AGENTS.md`, `.cursorrules` — что используется у вас). Без него
новая сессия просто не узнает, что ревью существует, и начнёт своё параллельное.

Умирает вместе с каталогом ревью — об этом сказано в нём самом.

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
