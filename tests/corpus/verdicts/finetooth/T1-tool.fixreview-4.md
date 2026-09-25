# T1 — fix review, round 4

Diff range `ee0e6ce..HEAD` — two commits: `d731e8a` (the code) and `879831b` (the register
moves). Five findings: **one high, one medium, three low.** The high one is a regression this
round introduced, in the class the round was fixing.

## What was checked and how

**The diff was read in full, and there is no report to compare it against.** The role brief
names `docs/review/reports/T1-tool.fix-4.md`; that file does not exist in the working tree and
does not exist in any commit (`git log --all -- docs/review/reports/T1-tool.fix-4.md` is
empty). The journal has no entry for this round either — its last line is the spend of fix
review round 3. The only account of the round is the message of `d731e8a`. So instead of
checking claims against the diff, every claim in that commit message and in the two changelog
bullets was checked against the code directly. That is finding R4-003.

**The suite on HEAD:** `python3 -m unittest discover -s tests` → **232 tests, OK** in 185 s
(230 before this round, +2 — the count in the commit message is right).

**Both fixes proven by reverting, one mechanism at a time, with the build intact:**

| mutant | build | tests that go red | the rest |
|---|---|---|---|
| `review.py` from `ee0e6ce` (the `FENCE_SLACK` column arithmetic back) | `ast.parse`: BUILDS | `ReviewToolTest.test_ограда_при_любом_отступе_не_режет_манифест` — `AssertionError: 'H1.4' not found in … closed 0/1` | the two round-3 fence tests (`test_ограда_внутри_пункта_списка_остаётся_оградой`, `test_вердикт_после_вложенной_ограды_по_прежнему_вердикт`) stay **green**, as they must |
| `run-role.sh` from `ee0e6ce` (the `trap 'exit $RC' EXIT` back) | the file is a committed version and the 14 tests executed it | `SpendTest.test_потерянная_запись_в_журнал_не_выдаёт_себя_за_чистый_прогон` — `AssertionError: 0 != 3` | the other 13 SpendTest tests stay green, including the allowed direction `test_успешный_прогон_записан_обычной_строкой` (rc 0 → exit 0, an ordinary journal line) and `test_отказ_шага_отчёта_не_подменяет_код_возврата_прогона` (rc 7 → exit 7) |

Both fixes are therefore genuinely tested, and both directions of the run-role change are held
(forbidden: a lost journal line is not exit 0; allowed: a clean run is still exit 0). `bash -n`
could not be run in this session (the call is not permitted here); the reverted script is a
committed version that the suite executed, which is the same evidence.

**The quotation guard was checked by violation**, in both of the forms it promises to catch —
two runs, the file restored after each, the tree verified clean with `git status --porcelain`:

| violation appended to `review.py` | `SourceRuleTest` |
|---|---|
| `report_fences(lines)` matching `FENCE` itself | **red**: `Lists differ: [('report_fences', ['FENCE'])] != []` — "своё распознавание цитаты" |
| `limits_said(md)` reading the document's lines without asking the tracker | **red**: `Lists differ: ['limits_said'] != []` — "разборщик markdown не спрашивает общий трекер" |

The removal of `FENCE_SLACK` from `QUOTE_DETECTORS` is therefore not a weakening: the name no
longer exists in the tool, and both halves of the rule still fire.

**The rejection of T1-039 was checked, not taken on trust.** Its reason is that the two gates
the source-shape guard does not reach are held by behaviour tests. Measured: `unquoted(...)`
silenced in `verify_report_problem` (raw `splitlines()` instead) → `ReviewToolTest` goes red on
`test_отчёт_проверяющего_из_одних_цитат_не_проводит_блок`, 1 failure of 95. The rejection
holds.

**Reproduced live, end to end, on throwaway repositories** (a stand built on the suite's own
`Stand`, the tool called from the skill as an agent calls it): the three inputs of R4-001 and
R4-002, each run through `hypotheses`, `set-status` and `check` on HEAD and on `ee0e6ce`. And
on this repository itself: `review.py check` (red, see R4-004), `hypotheses T1` (15/15 — the
block's own manifest is intact under the new rule), `review.py findings` (idempotent, the tree
stays clean).

**The whole-repository effect of the parser change was measured**, not argued: `quoted_lines`
run under both parsers over all 39 markdown documents of the repository (`docs/review/**`,
`skills/finetooth/**`, the root files). One document's quotation map changes —
`docs/review/reports/T1-tool.fixreview-3.md:97` — and it changes in the wrong direction. That
is R4-001, found in the project's own text before it was reduced to a test case.

**What was not done.** No `claude -p` was run: `run-role.sh` was exercised with the suite's
stub, as in every round of this block. `axes.py` was not re-read as a whole (the diff does not
touch it). `MSG` key parity was not re-measured — the diff adds no `MSG` key, and the one new
human-facing string is a shell `echo` in `run-role.sh`, where the kit's own messages are
English by rule. `skills-ref validate` was not run (the diff touches no skill metadata; the
round before ran it).

## Findings

### R4-001 · high · the new fence rule lets an indented inner fence close the outer one, and a quoted verdict becomes an answer again

**Location:** `skills/finetooth/scripts/review.py:1480`

**What is wrong:** the round dropped the closing-fence indentation rule together with the
opening one. CommonMark's two rules are not symmetric on purpose: an opening fence may sit at
any indentation, but a fence indented more than three spaces past the *opening* fence is
content, not a closer. With the check gone, the first indented fence inside a fenced block
closes it, and the lines after it are read as the report's own words.

**Failure scenario:** a hunter report that quotes another document whole — the shape every
report of this review uses — where the quoted document itself contains an indented example:

~~~
Я привожу целиком отчёт, который разбирал, — вот он:

```markdown
## Гипотезы

- Задание просило написать вердикт так:

       ```
       - H1.1 — проверена: <чем доказано>
       - H1.2 — проверена: <чем доказано>
       ```

- Ни на одну гипотезу автор не ответил.
```

Ни на одну гипотезу я не ответил.
~~~

The 7-space fence closes the `markdown` fence; the two verdict lines leak out as the report's
own words. Run end to end on a throwaway repository, the same manifest and the same report
through both tools:

```
=== ee0e6ce (before this round)
H1.1 NO VERDICT   H1.2 NO VERDICT   closed 0/2
check rc=1 · H1: 2 of 2 hypotheses without a verdict (H1.1, H1.2)
=== HEAD
H1.1 checked      H1.2 checked      closed 2/2
check rc=0 · review state is consistent
```

**The same defect has a second address, also reproduced end to end:** the verifier substance
gate (T1-033). A `*.verify.md` whose entire body is one quoted example, with an indented inner
fence inside it, passes — `check` rc **0**, "review state is consistent" — where `ee0e6ce`
refuses it with "verifier report H1-demo.verify.md is empty — there is a file, there is no
verification". The coverage-limits gate reads its section through the same `unquoted()` and is
fooled by construction; I measured the two above and reasoned the third. `demote` and
`section_body` are the same tracker, so prompt assembly is exposed too.

**It is not a hypothetical shape.** Of the 39 markdown documents in this repository exactly one
changes its quotation map under the new rule, and it changes this way:
`docs/review/reports/T1-tool.fixreview-3.md:97` — the line `       - H1.1 — проверена`, inside
the very failure-scenario listing of R3-001 — is a quotation on `ee0e6ce` and the report's own
words on HEAD. `check` does not read fixreview reports, so nothing is red today; the shape is
the point.

**Why it is a defect:** invariant 1 ("any way to make `check` pass on a state that is wrong …
is the most serious class of defect here", named a vulnerability by SECURITY.md) and invariant
4 ("a word inside a path, a code span or a fenced block is not a verdict"). It is the class of
T1-001, T1-032 and T1-033 — the fourth round in which it produces a defect.

**A direction, not a fix** (rule 9 — measured on a scratch copy of the file, nothing in the
repository touched): keep the opening fence at any indentation and give the closer back its
window, measured from the *opening* fence rather than from the content column —
`indent <= open_col + 3`, with `open_col` remembered when the fence opens. On that copy the
R3-001 input keeps all its hypotheses **and** the input above stays quoted; both directions
hold at once. The two-sided test this needs is a table (input → quoted map), not another case:
the class has now survived three point fixes.

**Introduced by this round or present before:** **introduced by this round** — `ee0e6ce`
refuses all three inputs.

**Confidence:** confirmed

### R4-002 · medium · an unclosed fence inside a list item swallows the rest of the manifest, and `check` goes green on one hypothesis of four

**Location:** `skills/finetooth/scripts/review.py:1476`

**What is wrong:** the tracker ends a fence only at an explicit closer. A fence opened inside a
list item therefore runs to the end of the document, even past lines at column 0 that no
container can hold — where markdown ends the item and the block with it. This is the failure
R3-001 described ("four hypotheses became one and `check` went green"), by a different trigger,
and the round's "one symmetric rule" does not close it.

**Failure scenario:** a manifest whose first hypothesis shows what an unbalanced fence looks
like — a hypothesis *about* fences, which this block's own manifest has four of:

~~~
## Гипотезы
1. Гипотеза номер 1: разборщик путает ограду с текстом. Пример из живого отчёта:

    отчёт открывает ограду строкой
    ```
    и на этом пример кончается.

2. Гипотеза номер 2: …
3. Гипотеза номер 3: …
4. Гипотеза номер 4: …
~~~

`hypotheses H1` → `closed 1/1`; hypotheses 2, 3 and 4 are gone from the count, from `check` and
from `hypotheses_sha`. A hunter report answering only H1.1 passes: `check` rc **0**, "review
state is consistent". The acceptance criterion, which lives in a later section, vanishes with
them.

**Why it is a defect:** invariants 1 and 6 — a fingerprint that covers only the truncated text
silently declares three unreviewed hypotheses reviewed, and the gate that exists to catch that
is the one going green.

**Introduced by this round or present before:** **present before** — `ee0e6ce` gives the same
`closed 1/1` and the same rc 0. It is named here because the round's changelog entry says the
column arithmetic is what let a manifest be swallowed, and one way in survived the replacement:
the class is not closed, whatever the entry says.

**Confidence:** confirmed

### R4-003 · low · the round left no fix report and no journal entry, so its incidental changes are recorded nowhere

**Location:** `docs/review/journal.md:16`

**What is wrong:** `docs/review/reports/T1-tool.fix-4.md` does not exist in the tree or in any
commit, and `journal.md` ends at the round-3 fix-review spend. Rounds 1, 2 and 3 each produced
both. What the missing report would have had to name: the mutation proofs (I re-measured them),
the two changelog bullets (R4-005), the register rows left over the gate's limit (R4-004), and
one changed guard — `SpendTest.test_отказ_шага_отчёта_не_подменяет_код_возврата_прогона` now
asserts the opposite of what it asserted before (`exit_code=0` → `exit_code=7`), which is
correct for the new contract but is a guard rewritten, not a test added. Its harness comment,
`tests/test_review.py:3417-3418`, still states the old invariant ("код возврата обязан остаться
кодом ПРОГОНА") beside the mechanism that now contradicts it.

**Failure scenario:** the next session reads `docs/review/` — "state lives on disk, never in
the conversation" — and finds four register rows with statuses, no account of how any of it was
proven, and a guard whose comment says the inverse of what it guards. `SKILL.md` step 6 says
the journal line is written "right away: this cannot be recovered".

**Why it is a defect:** the on-disk state is the review's only memory (the kit's own first
rule), and rule 6 of the fix-review brief — an incidental change that nobody named is the
danger, not the change itself. `check` does not catch it: only a *fixreview* report is gated
(`review.py:3138`), never a fix report.

**Introduced by this round or present before:** introduced by this round.

**Confidence:** confirmed

### R4-004 · low · the round left `check` red on a register row it wrote itself

**Location:** `docs/review/findings.jsonl:37`

**What is wrong:** T1-037 was imported with a scenario of 862 characters against the gate's
limit of 700, so `python3 skills/finetooth/scripts/review.py check` fails on it:
`finding T1-037: scenario is 862 characters against a limit of 700`. Round 3 hit the same thing
with T1-033 (757 characters) and trimmed the row as bookkeeping, naming it in its report; this
round left it.

**Failure scenario:** anyone running `check` after this round reads a red state check whose
first failure is not about the code at all, next to the reds that were deliberately left for
acceptance (the hunter report's verdict conflicts, `restamp T1`). A red gate that is red for
bookkeeping teaches the reader to skim the list.

**Why it is a defect:** invariant 1 by its converse — the gate must mean something. The tool
defect underneath it (`import` accepts a row `check` then refuses, saying nothing at import
time) is already open from round 2 and is not this finding; leaving the red is.

**Introduced by this round or present before:** introduced by this round (the row did not exist
at `ee0e6ce`).

**Confidence:** confirmed

### R4-005 · low · the new changelog bullet swallows the section's introduction, in both languages

**Location:** `CHANGELOG.md:14` (and `CHANGELOG.ru.md:14`)

**What is wrong:** the bullet was inserted directly above the two lines that introduce the
whole `### Fixed` section, with no blank line between them. In markdown those two lines are a
lazy continuation of the bullet, not a paragraph of their own.

**Failure scenario:** rendered — on the repository page, in a release note, anywhere the file is
read as markdown — the new entry ends with "… `run-role.sh` exits 3 … Mutations: … red. The
whole-repository review of the kit itself, block T1 (`review.py`, `axes.py`, `run-role.sh`,
`guard-grep.sh`): 24 findings, all confirmed by execution, all closed here." None of that
clause is true of the new entry: it is the section's heading sentence, the 24 findings are the
block's first pass, and of the four findings this round moved one is deferred and one rejected.
The section itself is left with no introduction.

**Why it is a defect:** the changelog is the public account of a `0.X` on-disk format (AGENTS.md
rule 7, both languages kept in step) — and this is not a formatting preference: the rendered
text asserts something false.

**Introduced by this round or present before:** introduced by this round.

**Confidence:** confirmed

## Checked and found correct

- **The fence fix does what it claims for its own input, and does not disturb the rest.** The
  new test is red on the reverted code with the build intact; the two round-3 fence tests stay
  green under the revert; `hypotheses T1` is 15/15 on HEAD; of 39 documents in the repository
  exactly one changes, and only in the way R4-001 describes. The direction of the fix — an
  opening fence at any indentation — is right; only the closer needed to keep its window.
- **The `run-role.sh` rewrite is right and complete.** No trap, `set +e` left in force, every
  reporting step guarded with `|| REPORT_RC=$?` so the agent's reply reaches the operator even
  after a failed journal write, and the run's own code still wins over 3. `axes.py main()`
  returns 0 on a truncated stream and on a stream with no result event (it returns 2 only for a
  missing argument), so `REPORT_RC` cannot be set by a cut-off run that `axes.py` was taught to
  survive — the new exit 3 does not fire on the case R2-005 was about. Grep found no second
  address: `$REVIEW log` appears nowhere else, and neither `makefile-snippet.mk` nor
  `package-json-snippet.json` wraps `run-role.sh`.
- **The stub `claude` is not softer than the real client on the property under test.** It writes
  no `result` event, so `axes.py` reports "NO RESULT EVENT" even for the exit-0 runs — harsher
  than reality, not softer, and the exit code under test does not depend on it.
- **A failing `axes.py --journal` now leaves a journal line with no spend** (`hunter — `) where
  the old trap aborted before the write. Not filed: it is reachable only by a crash in
  `axes.py`, and exit 3 plus the traceback on stderr say so — the silent hole R3-004 was about
  is what is closed.
- **T1-039's rejection is sound**, measured above: silencing `unquoted()` in
  `verify_report_problem` turns the suite red, so invariant 2 is met with or without the
  source-shape rule.
- **T1-038's deferral is a defensible call.** A pasted `diff --git a/src/api.ts b/src/api.ts`
  is genuine evidence that `src/api.ts` was read, and in a tree that also has a real
  `a/src/api.ts` the header names both; refusing the header would red honest reports on every
  project, and the reason field says exactly that and when to revisit. Not re-filed.
- **`review.py findings` is idempotent** on the current register (the tree stays clean), and
  `findings.md` matches `findings.jsonl` — 40 records, 0 open.

## Is another round needed

**Yes — for R4-001, and narrowly.** The measure of rule 11: the round made the project better
in two places, and both are proven, not claimed — the manifest-truncating fence asymmetry is
gone (red on revert, the old tests still green) and a lost journal line no longer hides behind
exit 0 (red on revert, the clean-run direction still green). Against that it reopened the
block's top class in a third place: a quoted verdict counts as an answer again, and a verifier
report of pure quotation passes `check` — reproduced end to end on both, and present in this
repository's own text. That cannot be released, and it is one line to put back.

Of the five findings, **four are inside the code and the bookkeeping this round changed**
(R4-001, R4-003, R4-004, R4-005) and **one is outside it** (R4-002, present before and
untouched). That ratio is the loop signal, and it is worth saying plainly: the quotation class
has now produced a defect in every round of this block — T1-001, T1-032/T1-033, R3-001,
R4-001 — and each time it was closed by a point fix plus a *source-shape* guard, which checks
where the recognition lives, not what it decides. That guard is green on every one of the four
defects. Round 5 should therefore not be another point fix: the fence rule needs a two-sided
behaviour table (document → quoted map: fence at column 0 / 4 / 7, inside a list item, inside
another fence, `~~~` around backticks, unbalanced, closer deeper than its opener), and R4-001's
direction should be measured against that table rather than against a new case. R4-002 belongs
in the same table, not in a separate round.

If round 5 produces another defect in these same three lines, the parser is the wrong shape for
the job and that is a decision for a human, not for another round.

R4-003, R4-004 and R4-005 are not about product behaviour and should not by themselves buy a
round: they are the round's own record, and the fixer of round 5 can close them with the report
it will write anyway.
