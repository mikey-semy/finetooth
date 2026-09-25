# T1 — fix report, round 7 (the lead)

Fix review round 6: 4 medium, 3 low, all three parser defects in `verdict_mentions`, which
round 6 had given three rules under one assertion. The reviewer's remedy — the one that had
already worked for fences — was taken: **the behaviour table first, then the fix.** It was
built together with the kit author's rules for a verdict (24.09 note, §1.2: a verdict needs a
basis; "partially" in the qualifier is "not checked").

## One rule instead of three exceptions

A verdict is a clause: the hypothesis id at the start of a line (optionally in bold, in
backticks, followed by a parenthetical), a dash, the earliest verdict word of the clause and a
basis after it. `clause_verdict()` decides; `verdict_mentions()` no longer has the section
filter (R6-002: it dropped the verifier's disagreement) nor the whole-line backtick strip
(R6-001: it switched off `unquote_verdicts`). Tables count only when they are about
hypotheses; "hypothesis N refuted" in running text is read as before.

| finding | closed by |
|---|---|
| T1-052 (R6-001) | a span holding only a vocabulary word is blanked, every other backtick is markup; table row `` - `H1.1` — the `n/a` token … checked by test `` → checked |
| T1-053 (R6-002) | no section filter for clauses; table row "## Where I disagree … H1.1 — не проверена: …" → not checked |
| T1-054 (R6-003) | hunter templates (en, ru) describe one rule: the clause with a basis; the old backtick form "is still read" |
| T1-055 (R6-004) | `section_body(…, unclosed)`; the coverage-limits gate reads the hunter report in "quoted" mode; test both ways (report: section absent; manifest: present) |
| T1-056 (R6-005) | `fixed_in` of T1-047/049/051 point at what they changed |
| T1-057 (R6-006) | `restamp T1-038` |
| T1-058 (R6-007) | one code-span parser (`INLINE_CODE`); `unquote_verdicts` uses it |

## Measured

- `VerdictTableTest`, 29 lines both ways; each of five mutations red (partial qualifier, no
  basis, basis on the next line, vocabulary spans, table filter). Section-mode mutations: two,
  both red.
- Live registers (setfork-app 6 blocks, arch-dashboard 8, finetooth 1), old tool vs new: no
  count moved. One verdict changed meaning, correctly: setfork H5.12 "проверена частично,
  мутацией не прогнана" was read as checked, now not checked.
- `unittest` 238 OK; `skills-ref validate` valid.
