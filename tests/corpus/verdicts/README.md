# Verdict corpus (issue #17)

A frozen golden snapshot of what the hypothesis-verdict parser (`verdict_mentions` in
`skills/finetooth/scripts/review.py`) returns on real reports and on the verdict forms the
role templates prescribe. `tests/test_verdict_corpus.py` asserts that the parser reproduces
it exactly.

**It freezes behaviour, it does not bless it.** Some frozen answers are wrong (see below);
the redesign exists to change them. A parser change that moves anything here updates
`expected.json` or `template-forms.md` deliberately, entry by entry, and the commit says
which line moved and why. A red corpus test means "say what you changed", not "revert".

Taken on 2026-09-25 against the round-3 parser (`dev` at `d3a3963`).

## What is here

| path | what |
|---|---|
| `finetooth/` | the kit's own block T1: its 15 hunter / verify / fix / fix-review reports, copied verbatim from `docs/review/reports/` |
| `setfork-app/`, `arch-dashboard/` | two external projects' registers, 14 started blocks between them (6 + 8), 46 reports — **anonymised skeletons**, not the reports (see below) |
| `expected.json` | report → `{hypothesis: [verdicts]}`: the output of `verdict_mentions(text, block)` on the **original, full** report |
| `index.json` | report → its block id (the parser needs it) and report kind |
| `template-forms.md` | every verdict form of the four role templates, both languages, with today's output (`expect`) and the template's meaning (`intent`) |

Which reports: for every block with at least one report, every
`docs/review/reports/<block>-*.md` that is a hunter, verify, fix or fix-review report — the same
glob `review.py` itself uses. Kinds were taken from the file name: `hunter`, `hunter-parallel`
→ hunter; `verify` → verify; `fix`, `fixN`, `fix-N` → fix; `fixreview-N`, `diff-review*` →
fixreview. Calibration notes (`*-calibration.md`) are not reports and are left out. A
multi-block fix report (`H2-H3.fix.md`) is read with the block of its first name, as the glob
finds it.

## Anonymisation of the external projects

This repository is public; the two external projects are not. Their report text is **not**
copied. Each report is replaced by a skeleton, named `<project>/<kind>-<n>.md`, that holds only:

1. **every line the parser counts** — an unquoted line with a verdict word that names a
   hypothesis of the block by id (`H3.2`), by the free form (`гипотеза 2`, `hypothesis 2`) or
   by the first cell of a hypotheses table;
2. **every line that mentions a hypothesis near a verdict word but is not counted** — a line
   with any hypothesis id or the free form, and a verdict word (the parser's vocabulary or its
   live-language neighbours: `проверено`, `держит`, `подтверждаю`, `refuted` …), quoted or not;
   plus every row of a hypotheses table. These are the lines the redesign most needs;
3. **only as much structure as the parser's state needs**, all of it synthetic:
   - `(…)` — an elision marker: something stood here. It is a plain paragraph line at the
     margin, so it ends a table and cannot turn the next indented line into a code block;
   - `## Hypotheses` / `## Section` — a heading that opens / closes a hypotheses section,
     at its original level; headings that change nothing are dropped;
   - `| hypothesis |` / `| — |` — the first row of a table when the original first row was
     not kept: it says whether the table is about hypotheses, which decides whether its
     numbered rows count;
   - `~~~~~~~~` … `~~~~~~~~` — a fence around a kept line that was quoted in the original
     (fence, indented code, `>`, comment), so it stays a quotation.

Host names in kept lines are replaced with `<host>`. Nothing else is rewritten: kept lines are
verbatim, indentation included.

A skeleton is only accepted if `verdict_mentions(skeleton, block)` equals
`verdict_mentions(original, block)` — `expected.json` is the original's answer, and the test
runs the parser on the skeleton. So the skeletons prove today's behaviour but do not carry the
whole context: a case where the answer depends on a line that was elided (a verdict whose basis
continues on the next, uncounted line) is visible in the skeleton only by its first line. The
originals stay in the owners' registers.

## Size

| part | reports | lines |
|---|---|---|
| finetooth (T1, verbatim) | 15 | 4 810 (42 counted verdict lines) |
| setfork-app (6 blocks) | 13 | 109 kept (105 counted, 4 near) |
| arch-dashboard (8 blocks) | 33 | 92 kept (33 counted, 59 near) |
| template forms | — | 52 forms |

Fix and fix-review reports of the external projects keep no lines at all (their skeletons are
empty): no line in them mentions a hypothesis near a verdict word. They stay in the corpus as
`{}` so a redesign that starts reading hypothesis verdicts out of fix reports is caught on T1's.

## Frozen answers that look wrong — the redesign's first cases

Not fixed here. Each is visible in the files above.

**Partial answers read as full ones, or not at all.**
- `setfork-app/hunter-1.md` (H1): rows 5, 7, 8, 9, 12 «Проверена частично», row 13 «Проверена
  для … — … не читал» → `checked`.
- `setfork-app/verify-3.md` H3.7 «проверена НЕПОЛНО», `setfork-app/hunter-6.md` H15.4 «проверена
  не полностью», `setfork-app/hunter-5.md` H5.12 «проверена частично, мутацией не прогнана» →
  `checked` (the parallel hunter, `hunter-4.md`, says «НЕ ПРОВЕРЕНА» for the same H5.12 →
  `not checked`); `hunter-5.md` H5.6 «неприменима в части …» → `not applicable`.
- `arch-dashboard/hunter-8.md` row 8 «частично: … проверена …, заголовки не проверялись» →
  `checked`; rows 5 and 7 «частично», row 12 «устарела» → nothing.
- `arch-dashboard/hunter-1.md`, `verify-1.md`: row 5 «частично: …» → nothing, so H1.5 has no
  verdict in either report.

**Honest verdicts in a live language are not seen.**
- `arch-dashboard/hunter-3.md` … `hunter-7.md` (H3–H7): the hypotheses table's outcome column
  holds `да`, finding ids, «дефекта нет», «корректно» — no vocabulary word, so all 40
  hypotheses of five blocks read as unanswered. `hunter-7.md` also says «(гипотеза 2) — дефекта
  нет» three times in prose → nothing.
- `arch-dashboard/verify-2.md` (H2): the verifier's whole answer is «(гипотеза N) — держит» and
  «гипотезы 1 и 2 проверены» → `{}`; the plural free form «гипотезы 1 и 2» would also bind only 1.
  `verify-3.md` «Гипотезы 1 и 2 проверены» → nothing.
- `setfork-app/hunter-6.md` (H15): «(гипотеза 9) — держит», «Гипотезу 6 … проверил выборочно» →
  nothing.
- `arch-dashboard/verify-8.md`: «Осталось непроверенным: … гипотезы 8» — a `not checked` → nothing.

**A basis on the next line.**
- `setfork-app/verify-1.md` (H1): «… Гипотеза 11» ends a line whose verdict is on the line
  before → nothing; «Непроверенная половина гипотезы 7 закрыта» → nothing. Only H1.10 is read
  from this verifier.
- `arch-dashboard/hunter-8.md`: «гипотеза 10 в основном не / опровергнута» split across a
  line break → the prose line gives nothing (the table row still says `checked`).

**The verifier's disagreement read through the word it quotes.**
- `setfork-app/verify-6.md` (V1d): «Гипотеза 9 — «не подтвердилась» ОТКЛОНЯЮ частично» →
  `checked`, from the hunter's quoted word; the verifier's rejection is lost. V1d.5/6/8
  «подтверждаю «не подтвердилась»» come out right by the same accident.

**Quoted verdict syntax counted as a verdict** (the known defect from the issue).
- `finetooth/T1-tool.fixreview-1.md` lines 148–151: a parser matrix quoting
  `T1.1 — checked: …` in code spans → T1.1 `checked` ×6.
- `finetooth/T1-tool.fixreview-2.md` lines 100–102 → T1.1 `checked` ×3.
- `finetooth/T1-tool.fixreview-7.md` line 68 (quotes a finding's words) → T1.3 `not
  applicable`; line 180 `` `Гипотеза 1 проверена` → ['checked'] `` → T1.1 `checked`.
- `finetooth/T1-tool.verify.md` line 38 (a finding row quoting `['T1.1','T1.2']`), lines
  235–236 (matrix rows `hypothesis 2 refuted …`, `гипотеза №3 опровергнута`) → extra T1.1, T1.2,
  T1.3 `checked`.

**A verdict without a basis.**
- `template-forms.md` entries 1, 4, 7, 18, 21, 24: the template's own line with its
  placeholder (`checked: <what exactly proves it>`) → a verdict.

## Updating

The parser changes; the corpus follows by hand. Re-run the test, read every `was / now` pair
it prints, and for each one either fix the change or edit the entry in `expected.json`
(or `expect:` in `template-forms.md`) with the reason in the commit message. Do not regenerate
the file wholesale: that is the silent move the corpus exists to prevent.
