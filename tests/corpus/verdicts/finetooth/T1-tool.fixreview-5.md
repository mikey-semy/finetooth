# T1 — fix review, round 5

Diff range `879831b..HEAD` — two commits: `5a8fa14` (the code, the tests, the changelog, the
hunter report, the two reports) and `946b67d` (the register moves). Six findings: **one high,
two medium, three low.** The high one is a regression this round introduced, in the class the
round was fixing — the fifth round in a row in which that class produces a defect.

## What was checked and how

**The diff was read in full and compared against `docs/review/reports/T1-tool.fix-4.md`.**
The report covers rounds 4 and 5 together; everything it claims for round 5 was checked
against the code rather than taken on trust.

**The suite on HEAD:** `python3 -m unittest discover -s tests` → **233 tests, OK** in 175 s.
The fix report's gate line says 232. 232 is what `python3 tests/test_review.py` runs — see
R5-004.

**Both mechanisms of the fence change proven by reverting, one at a time, build intact:**

| mutant | build | red |
|---|---|---|
| the close anchoring dropped (`and indent <= open_col + FENCE_SLACK` removed) — the round-4 rule | `ast.parse`: BUILDS | `QuotationMapTest` — `'QQQ.QQ.' != 'QQQQQQ.'`, row "indented fence INSIDE a fence does not close it" |
| the unclosed-fence fallback removed (the `if char: return _quoted_pass(...)` tail) | `ast.parse`: BUILDS (`open_at` merely goes unused) | `QuotationMapTest` — `'.QQQ' != '....'`, row "a fence that never closes is text" |
| `review.py` from `ee0e6ce` in place (the round-2/3 column arithmetic) | runs | `QuotationMapTest` — `'...QQ' != '.QQQ.'`, row "opening fence deeper than the list column" |

So the changelog's claim "red under each of the three earlier variants" holds, measured.

**The guard the diff touches (`SourceRuleTest`, `QUOTE_TRACKERS` widened by `_quoted_pass`)
was checked by violation, in both forms it promises to catch** — two separate runs, because
the two assertions live in one test and the first short-circuits the second; the file restored
after each and `git status --porcelain` verified empty:

| violation appended to `review.py` | result |
|---|---|
| `report_headings(md)` with its own `FENCE.match` loop | **red**: `[('report_headings', ['FENCE'])] != []` |
| `limits_said(md)` reading `md.splitlines()` without asking the tracker | **red**: `['limits_said'] != []` |

Adding `_quoted_pass` to the allowlist is therefore not a weakening.

**Reproduced live, end to end, on throwaway repositories** (the suite's own `Stand`, the tool
called from the skill): R5-001 in both of its addresses — the hypotheses gate and the verifier
substance gate — on HEAD and on `879831b`. And on this repository itself: `check` (red only on
`restamp T1`, so R4-004 is genuinely closed), `hypotheses T1` (15/15), `findings` (idempotent,
the tree stays clean), `import T1` (correctly refuses a re-import).

**The whole-repository effect of the parser change was measured, not argued:** `quoted_lines`
under both parsers over all 58 markdown files tracked by git. Two documents change their
quotation map, and one of them changes by **146 lines** — see R5-001.

**What was not done.** `skills-ref validate` could not be run (the call is not permitted in
this session); the diff touches no skill metadata. No `claude -p` was run — `run-role.sh` is
unchanged in this diff. `MSG` key parity was not re-measured: the diff adds no `MSG` key.
`axes.py` was not re-read; the diff does not touch it.

## Findings

### R5-001 · high · "an unclosed fence is text" hands the template's own skeleton back as the report's answers, and `check` goes green

**Location:** `skills/finetooth/scripts/review.py:1529-1533`

**What is wrong:** the fix for R4-002 made an unclosed fence disappear: `_quoted_pass` re-runs
with the opener excluded, so every line the fence was holding becomes the document's own
words. That is the right answer for a manifest, where a swallowed fence loses hypotheses, and
the wrong answer for a report, where a swallowed fence is the only thing keeping a quoted
example from being read as an answer. One tracker serves both, so the round traded a
fail-closed defect for a fail-open one in the class invariant 1 calls the most serious here.

The fence does not have to be missing to be unclosed. It is enough that the closer does not
match the opener — and the natural way to get that is the ordinary authoring mistake of
wrapping an example that itself contains ``` in **four** backticks and closing it out of habit
with three:

~~~
## Гипотезы

Задание выдало вот такой образец, его надо было заполнить:

````markdown
- H1.1 — проверена: <чем именно доказано>
- H1.2 — проверена: <чем именно доказано>
```

Ни на одну гипотезу я не ответил: стенд не поднялся.

## Ограничения охвата

Живым запросом не проверял ничего.
~~~

**Failure scenario:** run end to end on a throwaway repository, the same manifest and the same
report through both tools (this shape, and the same shape closed with `~~~` instead of ```):

```
=== 879831b (before this round)
H1.1 NO VERDICT   H1.2 NO VERDICT   closed 0/2
check rc=1 · H1: 2 of 2 hypotheses without a verdict (H1.1, H1.2)
=== HEAD
H1.1 checked      H1.2 checked      closed 2/2
check rc=0 · review state is consistent
```

The report says in its own words that it answered nothing. `check` prints "review state is
consistent". This is T1-001 verbatim — the role template's skeleton, with the block id already
substituted, closing hypotheses nobody answered.

**The second address, also reproduced end to end:** the verifier substance gate (T1-033). A
`*.verify.md` whose whole body is the template's example inside a fence opened with ```` and
closed with ``` — nothing verified, nothing stated:

```
=== 879831b  check rc=1 · H1: verifier report H1-demo.verify.md has no coverage verdict —
              is it complete and what is left, as an ordinary line and not inside a fence
              or a quotation
=== HEAD     check rc=0 · review state is consistent
```

`unquoted()` is the same call, so the coverage-limits gate and `demote` (prompt assembly) are
exposed by construction.

**It is not a hypothetical shape.** Of the 58 markdown files tracked in this repository, the
new rule moves the quotation map of two, and one of them moves by 146 lines:
`docs/review/reports/T1-tool.fixreview-2.md:128-282` — the whole tail of a fix-review report,
which was
quoted text on `879831b` and is the report's own words on HEAD. The trigger there is an
*inline* four-backtick code span that happens to start a line (`   ```` ```markdown ```` fence
holding …`), which `FENCE` reads as an opener that never closes. `check` does not read
fixreview reports, so nothing is red today; a hunter report with the same construct is one
`git log` away.

**Why it is a defect:** invariant 1 ("any way to make `check` pass on a state that is wrong …
is the most serious class of defect here", named a vulnerability by SECURITY.md) and
invariant 4 ("a word inside a path, a code span or a fenced block is not a verdict").

**Introduced by this round or present before:** **introduced by this round** — `879831b` and
`ee0e6ce` both refuse every input above.

**Confidence:** confirmed

### R5-002 · medium · the changelog entry restates the review's totals and gets them wrong, in both languages

**Location:** `CHANGELOG.md:14` (and `CHANGELOG.ru.md:14`)

**What is wrong:** R4-005 was filed because the section's introduction asserted something
false. The fix moved the bullet below the introduction — correctly — and rewrote the
introduction with new totals that do not match the register:

> 45 findings over the hunt and four rounds of fix review, all confirmed by execution — 42
> fixed, 1 deferred and 2 rejected, each with its reason in the register.

`docs/review/findings.jsonl` holds 45 rows: **43 fixed, 1 deferred (T1-038), 1 rejected
(T1-039)**. `findings.md`, generated from it, agrees. Two of the three numbers are wrong, and
the third sentence ("each with its reason in the register") promises a reason for a second
rejected finding that does not exist.

**Failure scenario:** the changelog is the public account of the review — the thing a reader
of the released kit checks the register against. A reader counting rejections finds one where
the changelog promises two, and cannot tell whether a row was lost or the sentence is wrong.
The same false sentence stands in `CHANGELOG.ru.md`, so AGENTS.md rule 7 (both languages in
step) is satisfied only in the sense that both are wrong.

**Why it is a defect:** it is the exact defect R4-005 named — a changelog clause that asserts
something untrue — reintroduced by its own fix, and it is the one artefact of this review that
outlives `docs/review/`.

**Introduced by this round or present before:** introduced by this round.

**Confidence:** confirmed

### R5-003 · medium · the block's own acceptance criterion cannot be written without making `check` red, and this round closed the gate by re-marking the report instead of filing it

**Location:** `skills/finetooth/scripts/review.py:2481-2496` (`unquote_verdicts`)

**What is wrong:** `unquote_verdicts` blanks a code span only when its **whole content** is a
vocabulary word — deliberately, so that `` `H1.1 — checked: proven by running it` `` keeps
working as a real verdict. The consequence is that a code span carrying an example verdict
clause is indistinguishable from a real one. The acceptance criterion of this very block asks
for "a matrix of at least 20 report lines … with the expected and the actual verdict" — a
table every one of whose cells is such a span. Measured on a report holding exactly that
table, unquoted:

```
verdict_mentions → {'T1.1': ['checked', 'not applicable'],
                    'T1.2': ['checked', 'not checked']}
```

`check` then refuses the report with "gives hypothesis T1.1 different verdicts … leave one".

**Failure scenario:** measured on this repository. Restoring `T1-tool.hunter.md` to its
`879831b` text and running `check` produces **six** failures — T1.2, T1.3, T1.5, T1.7, T1.11,
T1.12 — all of them raised by the report's own 25-row parser matrix and by prose that quotes
verdict syntax. This round made those six go green by prefixing the offending lines with `>`.
No finding was filed for the parser, so the register records the gate as satisfied and the
defect as absent. The next project whose report answers this acceptance criterion honestly
hits the same red, with no record that it is known.

Two of the marked regions are not quotations at all but the report's own sentences, and the
`>` now cuts them in half: `T1-tool.hunter.md:156-157` leaves "The hunter template's" as a
paragraph and puts the rest of that sentence in a blockquote; `:196-200` puts "**Failure
scenario:** … and the gate is" inside a blockquote and "green — with the wrong answer to the
question" outside it. The fix report describes the edit as "markup only, text unchanged" — in
markdown the markup is the text, and rendered, the report now attributes its own findings to
somebody else.

**Why it is a defect:** invariant 9 — if `check` demands something the role template and the
acceptance criterion do not let the agent produce, "the gate will go red on an honest report —
that is a defect of the kit, not of the agent". And invariant 1 by its converse: the gate went
green because the input was re-marked, not because the state changed.

**Introduced by this round or present before:** the parser behaviour is **present before**;
the report edit that hides it, and the absence of a finding for it, are this round's.

**Confidence:** confirmed

### R5-004 · low · the new guard does not run when the test file is run directly

**Location:** `tests/test_review.py:4222-4261`

**What is wrong:** `QuotationMapTest` is defined **after** `if __name__ == "__main__":
unittest.main()`. Under `python3 -m unittest discover -s tests` the module is imported, the
guard block does not fire and the class is collected; under `python3 tests/test_review.py`
`unittest.main()` runs at line 4223, before the class exists.

**Failure scenario:** measured, both ways on HEAD:

```
python3 -m unittest discover -s tests   → Ran 233 tests   OK
python3 tests/test_review.py            → Ran 232 tests   OK
python3 tests/test_review.py QuotationMapTest
    → AttributeError: module '__main__' has no attribute 'QuotationMapTest'
```

Both print OK, and nothing says a test was skipped. The behaviour table that this round
installed as the guard of the block's top class — the one the changelog advertises as what
replaces the point fixes — is silently absent for anyone who runs the file directly. The fix
report's own gate line, "`python3 -m unittest discover -s tests` — OK (232 tests)", quotes the
number of the invocation that misses it.

**Why it is a defect:** invariant 2 — a check whose mechanism can be disabled while the suite
stays green is untested; here the mechanism is disabled by the invocation. CI and AGENTS.md
use `discover`, so the guard does hold on the documented path, which is why this is low and
not medium.

**Introduced by this round or present before:** introduced by this round.

**Confidence:** confirmed

### R5-005 · low · `import` accepts a row that `check` immediately refuses, and the defect is in no register row

**Location:** `skills/finetooth/scripts/review.py:129` / `:2974`

**What is wrong:** `CLAIM_MAX` (220) and `SCENARIO_MAX` (700) are enforced only in `cmd_check`
(line 2974). `cmd_import` validates neither, so a draft row over the limit is written into the
register and the next `check` goes red on it, with nothing said at import time about which
field to shorten or by how much.

**Failure scenario:** reproduced by this review twice without anyone filing it. Round 3
imported T1-033 with a 757-character scenario and trimmed it as bookkeeping; round 4 imported
T1-037 with 862 characters and left `check` red, which is finding R4-004 of the previous
round; this round trimmed that row. The journal entry of round 3 says the tool defect is
"still open as a finding of its own from round 2" — there is no such row in
`docs/review/findings.jsonl`. Since `docs/review/` is deleted when the review closes
(AGENTS.md banner), a defect recorded only in a journal sentence leaves with it.

**Why it is a defect:** invariant 3 — a refusal names the command that fixes it, and the
refusal arrives one command too late to name anything; and the register is the review's memory
by the kit's first rule, so a confirmed defect that is only in the journal is a defect the
review will forget.

**Introduced by this round or present before:** the tool behaviour is present before; leaving
it unfiled for a third round is this round's.

**Confidence:** confirmed

### R5-006 · low · three findings are recorded as fixed in a file that has nothing to do with them

**Location:** `docs/review/findings.jsonl:43-45`

**What is wrong:** T1-043 (`docs/review/journal.md`), T1-044 (`docs/review/findings.jsonl`)
and T1-045 (`CHANGELOG.md`) all carry
`"fixed_in": ["skills/finetooth/scripts/review.py"]`. None of them was fixed in `review.py`:
one is a missing fix report, one a register row over a length limit, one a changelog
paragraph. `fixed_in` exists for exactly one purpose — to let the gate at `review.py:2893`
accept a fix made in a file other than the finding's own — so what it records is a claim about
where the fix is.

**Failure scenario:** `5a8fa14` touches `journal.md`, `findings.jsonl` and `CHANGELOG.md`, so
the gate would have passed on the findings' own files with no `fixed_in` at all. The field was
added anyway, and it now says of the finding "this round left no fix report" that it was fixed
in the tool's source. A later reader — or the gate itself, after a rename — takes the register
at its word: the point of the mark, in the words of its own comment, is that "by hand nobody
checks that — and nobody did for half a year".

**Why it is a defect:** the register is read back by the tool and is the review's only memory;
a field whose purpose is to state where a fix lives, stating a file that holds none of the
three fixes, is the false state invariant 1 is about, in its bookkeeping form.

**Introduced by this round or present before:** introduced by this round.

**Confidence:** confirmed

## Checked and found correct

- **The close anchoring is right, and it is right for the reason given.** The rule
  `indent <= open_col + FENCE_SLACK` is CommonMark's closing-fence window measured from the
  opener once the list container's stripping is accounted for; I probed it with an outer fence
  at columns 0, 3, 4 and 7 against inner fences at 0…7 and found no case where it diverges
  from what a renderer does. R4-001's own input stays quoted, and the round-3 input keeps all
  its hypotheses. Both directions hold at once, which is what the previous three attempts
  could not manage.
- **The two-sided table is a real improvement over the source-shape guard**, and each of its
  ten rows is load-bearing: all three earlier variants of the rule are red on it, each on a
  different row. The complaint in R5-001 is not that the table is wrong but that it has no row
  for a fence whose closer does not match its opener — the case the round's own new fallback
  created.
- **The hunter report's verdicts were not changed by the `>` edits.** I checked every
  hypothesis: the verdicts in the report's own Hypotheses section (lines 40, 46, 60, 72, 94,
  99) all read "checked" before and after, and `hypotheses T1` prints 15/15 on both texts. The
  fix report's claim "every hypothesis keeps the one verdict the hunter gave it in its
  Hypotheses section" is true. What R5-003 objects to is the gate, not the verdicts.
- **R4-004 is genuinely closed.** `check` on this repository is red on exactly one thing, and
  it is the one left for acceptance: `restamp T1`. The scenario-length failure is gone and the
  shortened T1-037 row is a faithful, if compressed, account of the defect.
- **T1-038's restamp is legitimate.** The row was re-stamped to the current `review.py` blob
  with `restamped_at` set — that is what `restamp <finding>` is for, and its docstring names
  this exact situation (a deferred finding whose file moved under it for other reasons).
- **`_quoted_pass` in `QUOTE_TRACKERS` is an incidental change the fix report does not name**,
  which rule 6 would ordinarily make a finding. I am not filing it: the recognition genuinely
  moved into that function, the allowlist is by exact name so nothing else slips through, and
  I measured both halves of the guard still red on a fresh violation. It is worth one line in
  the next fix report all the same.
- **The unclosed-fence fallback helps as often as it hurts, and the hurt is one-sided.** Where
  the stray opener is a phantom — an inline code span at the start of a line — the fallback
  recovers the right map, and I confirmed a case where HEAD is correct and `879831b` is not.
  That is why R5-001 asks for the report/manifest asymmetry to be resolved rather than for the
  fallback to be reverted.

## Is another round needed

**Yes for R5-001 — and the condition the previous round set for stopping has now been met.**

By the measure of rule 11 the round did make the project better, and provably: the closing
fence is anchored to its opener, which is the first version of this rule that holds both
directions at once; the behaviour table replaces a guard that was green on all four earlier
defects; R4-003, R4-004 and R4-005 are closed and the round left the record it was faulted for
not leaving. Against that it reopened T1-001 and T1-033 by a new route, with `check` printing
"review state is consistent" over a report that says in its own words that it answered
nothing.

Of the six findings, **four are inside the code and the bookkeeping this round changed**
(R5-001, R5-002, R5-004, R5-006) and **two are outside it** (R5-003, R5-005). That ratio is
the same as the previous round's, and it is the second consecutive round whose top finding is
a regression from the round before — R4-001 was the round-4 fence rule, R5-001 is the round-5
fallback. Counting the whole block: the quotation class has produced a defect in **every**
round — T1-001, T1-032/033, R3-001, R4-001, R5-001 — five in a row.

Fix review round 4 wrote: "If round 5 produces another defect in these same three lines, the
parser is the wrong shape for the job and that is a decision for a human, not for another
round." Round 5 produced one, in those lines, and it produced it out of the *fix* for the
finding round 4 filed. The two-sided table did not prevent it, because the table can only hold
rows for shapes somebody already thought of, and the shape that broke it — a fence whose
closer does not match its opener — was created by the same commit that wrote the table. What
the next round has to settle is not a line of code but a question the code cannot answer on
its own: an unclosed fence must be read one way in a manifest (text, or hypotheses vanish) and
the other way in a report (quotation, or examples become answers), and `quoted_lines` currently
has no way of knowing which document it is reading. That is a design decision.

R5-002 and R5-006 are the round's own record and R5-004 is a test-harness slip; none of the
three should by itself buy a round, and the fixer of round 6 can close all three with the work
it will do anyway. R5-003 and R5-005 are real tool defects that belong in the register whether
or not they are fixed now — R5-005 especially, because the review has now hit it three times
and written it down nowhere the register can keep.
