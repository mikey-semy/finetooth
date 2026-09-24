# Review journal

Written as the work goes: what was decided, why, what was deliberately not done. Findings
can be recovered by a repeat run — decisions cannot.

Add only through the tool's `log` command: `<CLI> log <BLOCK> "text"`.

- **2026-09-15** · `setup` — Phase 0 assembled: 29 blocks, the skill installed into the project, the coverage map (1819 files, none unowned). Block order: cross-cutting invariants first, then vertical slices, then what needs a live system.
- **2026-09-15** · `setup` — Decided that the phase 3 blocks (E1–E4) own no files: they work on the running system. Because of that the first version of the tool assumed they cover the whole repository, and coverage added up fictitiously; the behavior is fixed — an empty list of paths means an empty set, not "everything".
- **2026-09-15** · `setup` — While checking coverage it turned out that a separate microservice was not accounted for in any block: it is given to block V3 together with the rest of the file path.
- **2026-09-15T19:19:31Z** · `setup` — Checking the path patterns showed that the order card is assembled from route-local components, and every specialized block would have missed its piece of the interface: the comments would have gone to the order list, like the rest of the card's tabs. Ownership reassigned by file, and a dead-pattern check added to review-check so that a typo in a path no longer narrows a block silently.
- **2026-09-15T19:52:07Z** · `H1` — Block accepted. The hunter read 25/25 files, both acceptance tables delivered; the verifier compared the route table mechanically (322 registrations against the hunter's 321 — the difference is two GET /ws branches declared collapsed) and confirmed the "Gate" column in every row. The "migration ↔ seed" grants checked twice: 48 INSERT INTO role_permissions statements rewritten as read-only queries against the live dev DB, no discrepancies — the defect class "grant lost on a clean install" is closed.
