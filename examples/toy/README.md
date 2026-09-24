# Example: one reviewed block on a toy repository

This is what `docs/review/` looks like after one block has gone through the hunter and the
verifier — real files produced by the tool, on a three-file TypeScript "app" that is wrong on
purpose. Nothing here is a real project.

- `docs/review/blocks.json` — two blocks, one cross-cutting (`H1`, access) and one vertical
  (`V1`, billing); `H1` lists `V1`'s files as context (`ref_paths`).
- `docs/review/invariants.md` — three rules of the toy project; the hunter cites them.
- `docs/review/blocks/H1-access.md` — the manifest: three numbered hypotheses and an
  acceptance criterion that cannot be met without running the code.
- `docs/review/reports/H1-access.hunter.md` — the hunter's report: every file named by path,
  a verdict for every hypothesis, two findings with failure scenarios, and the mandatory
  "Coverage limits" section.
- `docs/review/reports/H1-access.verify.md` — the verifier's report: verdict per finding,
  own pass, coverage status.
- `docs/review/findings.jsonl` / `findings.md` — the register after `import H1` and
  `findings`; `coverage.tsv` — the file → block map; `state.json` — `H1` is `verified` with
  fingerprints of the reviewed files and hypotheses; `journal.md` — one decision.

To see the gates work, copy this directory into a fresh git repository, commit, and run
`python3 <skill>/scripts/review.py check`: it passes. Then edit `src/auth/session.ts` and
run `check` again — the block goes red ("files changed after the review") until you
`restamp H1`. Delete the "Coverage limits" section of the hunter report — red again.

`V1` is deliberately left at `todo`: its manifest is written, the block is next.
