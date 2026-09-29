# T1 — fix review, round 7

## What was checked and how

The diff was read in full against the code at HEAD (`062fbb8`), not against the fix report.
Round 7 is one rewrite: `verdict_mentions` lost its hypotheses-section filter and its
whole-line backtick strip and gained a clause parser (`clause_verdict`, `PARTIAL`,
`NO_BASIS`); `section_body` gained an `unclosed` parameter and the coverage-limits gate
passes `"quoted"`; `CODE_SPAN` and `OLD_VERDICT_ITEM` are gone; `hunter.md`/`hunter.ru.md`
describe the new rule; `VerdictTableTest` (28 cases) and one `section_body` case are new.

**Differential parser matrix.** `4a8dad1` (before this round) and HEAD loaded side by side
into one process, 43 report lines through `verdict_mentions(text, "H1")`, old verdict vs new:
`scratchpad/probe/p.py`, `p2.py`, `p3.py`. 14 lines moved. Every move was then classified as
intended (the round's rule) or unintended.

**Live end to end.** Six scenarios built as throwaway git repositories on the repo's own
`Stand` (`scratchpad/probe/live.py`): a real `blocks.json`, a real manifest with two
hypotheses, real reports, then `init` → `set-status running` → `coverage` → `set-status
verified` → `hypotheses H1` → `check`, once with `4a8dad1` and once with HEAD. Four of the
six changed the exit code or the printed verdict. `check` on this repository itself: exit 1
on the `restamp T1` left for acceptance and nothing else — the bookkeeping reds of rounds
4–6 (R4-004, R6-006) are not repeated.

**Mutations, full suite each time** (`scratchpad/probe/mutate.py`; every mutant compiled,
tree restored clean afterwards):

| mechanism reverted | compiles | suite | red test |
|---|---|---|---|
| `PARTIAL` qualifier → "not checked" | yes | **RED** | `VerdictTableTest` |
| `NO_BASIS` → no verdict | yes | **RED** | `VerdictTableTest` |
| vocabulary span blanked in a clause | yes | **RED** | 3 tests |
| table counts only when about hypotheses | yes | **RED** | 3 tests |
| clause read outside the hypotheses section (R6-002) | yes | **RED** | `…перебивает_охотника`, `VerdictTableTest` |
| **coverage-limits gate reads the report in `"quoted"` mode (R6-004)** | yes | **GREEN** | — none — |

**Gate checked by violation.** The source-shape guard (`SourceRuleTest._quote_offenders`)
was fed three new code-span parsers with the real source appended; results in R7-008.

**Not done.** `skills-ref validate` is not installed on this machine, so the report's
"valid" line is unverified. The live-register measurement ("two projects, 14 blocks, no
count moved") could not be reproduced — those repositories are not here; I verified the
claim's shape only on this repository's own report, where `check` is green on the hypotheses
gates. `axes.py` and `run-role.sh` are untouched by this diff and were not re-reviewed.

## Findings

### R7-001 · high · a finding write-up that opens a line with a hypothesis id is counted as a second verdict, and `check` goes red on an honest report
**Location:** `skills/finetooth/scripts/review.py:2674`
**What is wrong:** the round removed the `sectioned` filter ("a report that HAS a hypotheses
section answers there") and replaced it with a shape rule — the id must open the line. A
sentence in a finding write-up that begins with the hypothesis id, a dash and a verdict word
satisfies that shape, so the report is read as answering the same hypothesis twice.
**Failure scenario:** a hunter report that answers in `## Гипотезы` and then, describing the
finding it came from, writes under `## Находки`:
`H1.1 — неприменима: именно это инструмент записывает для пути curation/n/a.ts`.
Same repository, same manifest, same report, both tools:

| | `4a8dad1` | HEAD |
|---|---|---|
| `verdict_mentions` H1.1 | `['checked']` | `['checked', 'not applicable']` |
| `check` | rc 0, "review state is consistent" | rc 1 |

HEAD's failure line: `H1: H1-demo.hunter.md gives hypothesis H1.1 different verdicts
(checked / not applicable) — the outcome would depend on line order; leave one`.
**Why it is a defect:** this is T1-048 (R5-003) word for word — "the block's own acceptance
criterion cannot be written without making `check` red" — and the comment the round deleted
said so explicitly: *"the kit's own review of its parser named T1.3 next to 'not applicable'
while describing the bug, and the gate asked to 'leave one'"*. The remedy the gate suggests
("leave one") is to delete a true sentence from a report, which is exactly the `>`-marking
cover-up R5-003 was filed against. Invariant 4 (a word inside prose is not a verdict).
**Introduced by this round or present before:** introduced by this round.
**Confidence:** confirmed

### R7-002 · high · the verifier's override is dropped when its basis is on the next line, and `check` reports the hunter's "checked" on a hypothesis the verifier called unproven
**Location:** `skills/finetooth/scripts/review.py:2721`
**What is wrong:** `clause_verdict` returns `None` unless the basis stands on the same line
after the verdict word. A verdict line followed by the reasoning as a separate paragraph or
an indented sub-item yields no verdict at all — and where a hunter verdict already exists,
`verdicts_for` keeps it.
**Failure scenario:** the verifier report writes

```
## Где я не согласен с охотником

- H1.2 — не проверена.

Доказательство охотника — снимок экрана с другой ветки; воспроизвести не удалось.
```

while the hunter wrote `- H1.2 — проверена: дёрнул кэш дважды…`. Measured end to end:
`hypotheses H1` prints `H1.2 checked`, `closed 2/2`, `check` rc **0** — "review state is
consistent". The same line on `4a8dad1` parses as `['not checked']`. English is identical
(`- H1.2 — not checked.` → no verdict).
**Why it is a defect:** invariant 1 — the gate is green on a state that is wrong, and the
one artefact of the method that exists to override a wrong verdict is the one being
silenced. This is R6-002's failure scenario verbatim, reopened through a different door two
commits after it was closed. Compounding it, invariant 9 / AGENTS.md rule 8: the round
taught the new rule to `hunter.md` and `hunter.ru.md` only — `verify.md:51` and
`verify.ru.md:52` still describe a verdict as «проверена: чем доказано» with no word about
the basis having to share the line, so the verifier is following its own prompt when it
loses its verdict.
**Introduced by this round or present before:** introduced by this round.
**Confidence:** confirmed

### R7-003 · medium · the hunter template's own indented-proof form yields no verdict at all, and the refusal names a requirement the report already meets
**Location:** `skills/finetooth/scripts/review.py:2700`
**What is wrong:** the same same-line-basis rule as R7-002, from the hunter's side. The
template explicitly blesses the shape the parser now refuses, and the gate's message does
not mention the real requirement.
**Failure scenario:** a hunter report written as `hunter.md:104` / `hunter.ru.md:104` promises —
"доказательство с отступом под строкой остаётся её частью":

```
## Гипотезы

- H1.1 — проверена:
  - доказано: прогнал функцию на матрице значений, предикат совпал.
- H1.2 — проверена:
  - доказано: дёрнул кэш дважды, второй вызов сходил в источник.
```

`4a8dad1`: `closed 2/2`, `check` rc 0. HEAD: `closed 0/2`, `check` rc 1 —
`H1: 2 of 2 hypotheses without a verdict (H1.1, H1.2) — each is closed with the word
'checked', 'not checked' or 'not applicable'`. Both lines are closed with the word
'checked'. The author is told to do what they have already done.
**Why it is a defect:** invariant 9 — the gate goes red on an honest report written as the
prompt prescribes, in both languages, and `hunter.md:104`/`hunter.ru.md:104` now contradict
`hunter.md:88`/`hunter.ru.md:89` two paragraphs apart — which is R6-003's claim
("the template now contradicts itself in both languages") at a new address. The round's own
quotation table asserts the same promise: `QuotationMapTest.CASES["sub-items of a list are
said, not quoted"]`. And AGENTS.md rule 3 / invariant 3 — a refusal must say what to do; this
one names a condition the report satisfies and stays silent about the missing basis. Two
further shapes lose their verdict the same way, with no rule stating it: a separator other
than a dash (`- H1.1 → checked: ran it`) and a period after the id (`- H1.1. — checked: ran
it`).
**Introduced by this round or present before:** introduced by this round.
**Confidence:** confirmed

### R7-004 · medium · the partial qualifier is searched over the whole clause whenever there is no colon, so an honest "checked" is recorded as "not checked"
**Location:** `skills/finetooth/scripts/review.py:2713`
**What is wrong:** `qualifier, colon, basis = tail.partition(":")`, and when there is no
colon — or when the colon ends the line — `qualifier` becomes the entire clause. `PARTIAL`
is then matched against the basis, which the rule as published forbids: CHANGELOG.md:19 says
"A partial qualifier **between the verdict word and the colon** … the word in the basis is
not". `PARTIAL` also contains the bare Russian `лишь`, which means "only/merely" and carries
no sense of partial work.
**Failure scenario:** measured end to end, hunter report line
`- H1.1 — проверена, расхождение лишь в тесте, прогнал матрицу значений.` — `4a8dad1`
prints `H1.1 checked`, HEAD prints `H1.1 not checked`, `check` rc 0 in both, so nothing goes
red and no one is told. The colon does not save it either:
`- H1.1 — проверена, лишь один файл читал по диффу: повторил замер` → `['not checked']`;
English: `- H1.1 — checked; the incomplete-index case does not arise` → `['not checked']`,
`- H1.1 — checked, only partly by reading: ran the mutation too` → `['not checked']`.
**Why it is a defect:** the hunter says "checked", the tool records "not checked", and
`hypotheses`, `summary` and every human reading them inherit the wrong answer with the gate
green — which is T1-052 (R6-001) restated with a different vocabulary bug in place of the
old one. Invariant 4: the parser is again deciding on the shape of a line rather than on
what it says.
**Introduced by this round or present before:** introduced by this round.
**Confidence:** confirmed

### R7-005 · medium · the round's central rule — no basis, no verdict — does not reach the table or the free form, so it is bypassed by writing the same answer as a table
**Location:** `skills/finetooth/scripts/review.py:2662`
**What is wrong:** the table branch calls `line_verdict` and the free-form branch calls
`line_verdict`; neither goes through `clause_verdict`, so neither requires a basis. The
result is that one state has two gate verdicts depending on markup.
**Failure scenario:** a hunter report whose whole Hypotheses section is

```
| # | гипотеза | итог |
|---|---|---|
| 1 | предикат расходится с каноном | проверена |
| 2 | кэш никогда не сбрасывается | проверена |
```

— `closed 2/2`, `check` rc 0, "review state is consistent" on HEAD. Not one word of basis
anywhere. The same two answers written in the form the template prescribes
(`- H1.1 — проверена`) are refused with "2 of 2 hypotheses without a verdict". The free form
is the same: `Гипотеза 1 проверена` → `['checked']`, and
`| # | hypothesis | outcome |` / `| 1 | the handler | checked: <how> |` — the template's
unfilled placeholder — → `['checked']`.
**Why it is a defect:** invariant 1 — a way to make `check` pass on a state that is wrong,
and the way is one line of markup. Rule 5: the fix went to one address of the "a bare word
is not an answer" rule out of three.
**Introduced by this round or present before:** the table and free-form paths behaved this
way before; the *asymmetry* is new — before this round both forms were accepted, now the
stricter rule reaches only the prescribed one.
**Confidence:** confirmed

### R7-006 · medium · the file-map gate reads the report raw, so the block's file list can be satisfied entirely out of a quotation
**Location:** `skills/finetooth/scripts/review.py:3195`
**What is wrong:** the `named_files` gate joins the reports with `read_text` and calls
`names_file` on the whole text. It never asks `unquoted()`. R6-004 named the coverage-limits
gate as the place "the round's principle does not reach"; this is the third gate with the
same property, and the fix did not come here.
**Failure scenario:** a hunter report whose only mention of the block's files is a pasted
listing inside a fence, with the report saying in its own words that it did not read it:

```
Файлы блока я перечислять не буду, вот вывод команды, которую я НЕ разбирал:

​```
$ git ls-files src
src/a.ts
src/b.ts
​```
```

With `named_files: true`, `check` exits **0** on both `4a8dad1` and HEAD: two files counted
as named by a quotation the report disowns.
**Why it is a defect:** invariant 1, and `hunter.md:105` promises the opposite in both
languages — "The same holds for **everything the state check reads in the report**". A
promise the mechanism does not keep is invariant 9 read backwards.
**Introduced by this round or present before:** present before.
**Confidence:** confirmed

### R7-007 · medium · the R6-004 fix is untested: reverting the gate's `"quoted"` mode leaves the whole suite green
**Location:** `skills/finetooth/scripts/review.py:3229`
**What is wrong:** the finding was that the coverage-limits **gate** reads a quoted section
as the report's own words. The fix is the third argument at `cmd_check`. The test the round
added, `test_раздел_охвата_в_незакрытой_ограде_пуст`, calls `section_body(md, LIMITS_HEADING,
"quoted")` directly — it exercises the library function, not the gate, so it cannot notice
the gate dropping the argument.
**Failure scenario:** revert line 3229 to
`section_body(hunter.read_text(encoding="utf-8"), LIMITS_HEADING)` — the file compiles and
`python3 -m unittest discover -s tests` prints `Ran 238 tests … OK`. The gate is back to
green on the exact report R6-004 was filed on, and nothing says so. Measured above.
**Why it is a defect:** invariant 2 and AGENTS.md rule 2 — "a check whose mechanism can be
disabled while the suite stays green is untested". The fix report's line for T1-055 claims
"test both ways (report: section absent; manifest: present)", which is true of
`section_body` and false of the gate; its "Section-mode mutations: two, both red" does not
cover this one.
**Introduced by this round or present before:** introduced by this round.
**Confidence:** confirmed

### R7-008 · low · T1-058 is recorded `fixed` while the half of it about the class guard is untouched — a third span parser is still invisible
**Location:** `tests/test_review.py:4074`
**What is wrong:** T1-058 claimed two things: a second code-span parser outside the
tracker, and "the class guard cannot see span parsers". The diff removes `CODE_SPAN` and
points `unquote_verdicts` at `INLINE_CODE` — the first half. The guard is not touched:
`QUOTE_DETECTORS` still lists only `FENCE, BLOCKQUOTE, LIST_OPEN, CODE_INDENT,
COMMENT_OPEN, COMMENT_CLOSE`, and `QUOTE_TRACKERS` does not include `unquote_verdicts`.
**Failure scenario:** checked by violation, the real source with one function appended, then
restored (`git status --porcelain` clean):

| probe appended to the tool | guard |
|---|---|
| `def strip_spans(line)` with its own `re.compile(r"\`+([^\`]*)\`+")` | **GREEN** |
| `def strip_spans(line)` deciding on backticks by hand, no regex | **GREEN** |
| `def verdict_of(line)` calling `INLINE_CODE.sub` outside the tracker | **GREEN** |

(The same three named `md` instead of `line` are seen — the guard recognises a markdown
parser by the argument name `md` and by `FENCE`-family constants, neither of which a span
parser has.) So the next round may add a fourth span rule exactly as this round added the
third, with the suite green — which is the situation T1-058 was filed to end.
**Why it is a defect:** rule 1 — a finding named closed whose second half the diff does not
touch, with no test for it, is a finding in itself; the fix report's line for T1-058 names
only the first half, so the register now says the guard question is settled.
**Introduced by this round or present before:** the blindness is older; recording it as
fixed is this round.
**Confidence:** confirmed

### R7-009 · low · the changelog and the fix report say the new table holds 29 lines; it holds 28
**Location:** `CHANGELOG.md:19`
**What is wrong:** `VerdictTableTest.CASES` has 28 entries (counted by `ast`, listed in
`scratchpad/probe/`). "29 lines both ways" / «29 строк в обе стороны» stands in
`CHANGELOG.md:19`, `CHANGELOG.ru.md:19`, `docs/review/reports/T1-tool.fix-7.md:30` and the
commit subject of `d1db6bb`.
**Failure scenario:** the changelog is the public account of this review — a reader checking
the released kit counts 28 cases where four documents promise 29 and cannot tell whether a
case was dropped in a later edit or the sentence was always wrong.
**Why it is a defect:** the same class as T1-047 (R5-002, medium) and T1-045 (R4-005) — a
number in the public account that the artefact does not bear out, in both languages at once,
so AGENTS.md rule 7 is satisfied only in the sense that both are wrong.
**Introduced by this round or present before:** introduced by this round.
**Confidence:** confirmed

### R7-010 · low · a coverage-limits section swallowed by an unclosed fence is reported as a missing section, and the message does not name the cause
**Location:** `skills/finetooth/scripts/review.py:3231`
**What is wrong:** with `"quoted"` mode the heading itself becomes a quotation, so
`section_body` returns `None` and the gate takes the first branch — "the hunter report has
no 'Coverage limits' section — what was deliberately not read and why". The second branch,
the one that says "as an ordinary line and not inside a fence or a quotation", is the
one that fits.
**Failure scenario:** the report of R6-004 — a `​```markdown` fence left unclosed above
`## Coverage limits`. Before this round the gate was green (the bug). Now it is correctly
red, but tells an author who wrote the section that the section is absent; the author adds
it again, above or below, and gets the same red, because the cause is the fence.
**Why it is a defect:** AGENTS.md rule 3 / invariant 3 — "a failure must say what to do…
the message is read by someone seeing the tool for the first time". The fix created a new
red and routed it to the wrong one of the two messages it already had.
**Introduced by this round or present before:** introduced by this round.
**Confidence:** confirmed

## Checked and found correct

- **R6-001's fix.** `unquote_verdicts` blanking only a span whose whole content is a
  vocabulary word, plus `.replace("`", "")` for the rest, is right in both directions:
  `` - `H1.1` — the `n/a` token in a path is handled; checked by test `` → `['checked']`
  (was `['not applicable']`), and `` - `H1.1 — проверена: посчитано` `` — the old template
  form — still → `['checked']`. The form without a list marker
  (`` `H1.1 — проверена: …` `` alone on a line) now works too, which R6-003's second shape
  needed and `4a8dad1` did not read.
- **A verdict word inside the basis does not flip the verdict** when the clause has a
  colon: `- H1.1 — проверена: частичный уникальный индекс не даёт второй строки` →
  `['checked']`. The author's rule 1.2 is honoured for the shape the rule describes; R7-004
  is about the shapes it does not.
- **The `NO_BASIS` placeholder rule** does what it says: `checked: …`, `checked: <how it was
  proven>` and bare `проверена` give no verdict, while `checked: <ran it> and more` does.
- **Five of the six mechanisms are proven by mutation**, each mutant compiling and the suite
  going red on it — see the table above. That is the part of invariant 2 this round got
  right, and it is why R7-007 stands out.
- **`INLINE_CODE` is not a performance risk.** 1 600 spans on one line: 0.6 ms; 320
  consecutive unclosed backticks: 1.6 ms. No super-linear path.
- **`MSG` key sets are equal** (56 and 56, difference empty) — the round added no one-sided
  string.
- **The register's bookkeeping is right this time.** 58 rows, 56 fixed / 1 deferred / 1
  rejected, no duplicate ids; the changelog's totals and "six rounds" match the row prefixes
  (hunt 24, R1 7, R2 5, R3 4, R4 5, R5 6, R6 7); every new row's `fixed_in` names a file
  `d1db6bb` actually touched; `findings.md` is in sync with the jsonl; `check` on this
  repository is red on the acceptance `restamp T1` and on nothing else. R4-004, R5-006,
  R6-005 and R6-006 are not repeated.
- **An English plural "Hypotheses 1 and 2 — checked: …"** yields no verdict while
  `гипотез\w*` catches the Russian plural. Judged below the bar: neither template
  prescribes the plural form and the Russian equivalent with a plural verb
  («проверены») fails too, so this is not a bilingual asymmetry of a gate but an
  unprescribed form that both languages mostly reject.

## Is another round needed

**Yes — and this is the point at which a human should decide whether the verdict parser is
being fixed or circled.**

What genuinely got better: R6-001 is closed in both directions and the register's
bookkeeping is finally clean — `check` on this repository is red on one line, the one left
for acceptance. Five of six new mechanisms are proven by mutation. That is real progress on
the *hygiene* of the round.

What did not: the parser. Of the ten findings above, **seven are inside the code this round
changed** (R7-001 through R7-005, R7-007, R7-010) and three are outside it (R7-006, R7-008,
R7-009 — the last two are about the round's own record rather than its code). Two of the
seven are the previous round's findings reopened at a new address within two commits:
R7-001 is T1-048/R5-003 word for word, R7-002 is T1-053/R6-002's own failure scenario. The
shape repeats every round: a narrowing is added to stop one false green, and it produces a
false red on the form some template prescribes plus a false green on the form it does not
reach.

The diagnosis the register now supports is that the rule cannot be derived from the defect
in front of it. The behaviour table was the right instinct, but it was built from the last
round's findings, not from the corpus that has to pass: the **prescribed forms of all four
role templates in both languages**, plus the reports of this review and of the two live
projects, plus the ways a report legitimately mentions a hypothesis id without answering it.
Until that corpus is the table, each round will keep trading one false verdict for another.

Concretely, one round should: make a clause span its continuation lines (which fixes R7-002
and R7-003 together and is what both templates already promise); scope the clause to where
answers belong, or to a shape prose cannot accidentally take (R7-001); confine `PARTIAL` to
the text between the verdict word and the colon as the changelog already claims, and drop
the bare `лишь` (R7-004); route the table and free-form paths through `clause_verdict`
(R7-005); teach `verify.md`/`verify.ru.md` the rule the hunter templates now carry; and test
the two gates, not their library functions (R7-007). If the round after that one still finds
defects in the same function, the answer is not another round — it is to stop narrowing and
let the gate demand one canonical form, refusing everything else with a message that shows
it.
