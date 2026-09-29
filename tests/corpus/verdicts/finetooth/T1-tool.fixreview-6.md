# T1 — fix review, round 6

Diff range `946b67d..HEAD` — two commits: `d5da45a` (the code, the tests, the templates, the
changelog, the hunter report, the two reports) and `092371a` (the register moves). Seven
findings: **four medium, three low.** Three of the four mediums are the round's own new rules
misfiring; two of the three lows are verbatim recurrences of findings this same round closed.

## What was checked and how

**The diff was read in full, then the code, and the fix report only afterwards.** Every claim
of `docs/review/reports/T1-tool.fix-6.md` was checked against the tree rather than taken on
trust. Two claims were checked and hold exactly: the hunter report is byte-identical to its
`879831b` text (`git diff 879831b HEAD -- docs/review/reports/T1-tool.hunter.md` is empty —
the lead's `>` marks are genuinely reverted), and `hypotheses T1` prints `closed 15/15` on the
report as the hunter wrote it, with `check` raising no verdict conflict.

**The suite on HEAD:** `python3 -m unittest discover -s tests` → **236 tests, OK** in 174 s,
which is the number the fix report gives.

**Every mutation the fix report names was run, one at a time, build checked with `ast.parse`,
the file restored after each and `git status --porcelain` verified clean:**

| mutant | build | red |
|---|---|---|
| baseline, no mutation | BUILDS | none — the selected tests pass, so every red below is the mutation's |
| `if char and unclosed == "text":` → `if char:` (the mode ignored) | BUILDS | `test_незакрытая_ограда_в_отчёте_остаётся_цитатой` |
| `INLINE_CODE.sub(" ", line)` → `line` (spans kept) | BUILDS | `test_вердикт_в_код_спане_прозы_и_таблицы_не_ответ` |
| the `if sectioned and not (…): continue` filter removed | BUILDS | `test_вердикт_в_код_спане_прозы_и_таблицы_не_ответ` |
| the `OLD_VERDICT_ITEM` branch → `if False:` | BUILDS | `test_вердикт_в_код_спане_прозы_и_таблицы_не_ответ` **and** `test_вся_строка_вердикта_в_кавычках_остаётся_вердиктом` |
| the `import` limit loop emptied | BUILDS | `test_import_держит_те_же_пределы_что_check` |

All five claims hold, measured. No mutation survived and none of them broke the build, so no
red came from a syntax error.

**The class guard was checked by violation, old form and new form in one run**
(`SourceRuleTest.test_цитаты_распознаются_одним_местом`, the file restored and verified clean
afterwards):

| probe appended to `review.py` | result |
|---|---|
| `report_headings_probe(md)` with its own `FENCE.match` loop | **RED** — `[('report_headings_probe', ['FENCE'])] != []` |
| `report_answers_probe(md)` that asks `quoted_lines` and then decides quotation on its own `INLINE_CODE` | **GREEN — the guard is blind** |

That second row is R6-007, and it is the door R6-001 walked through.

**Reproduced live, end to end, on throwaway repositories** — a real `blocks.json`, a real
manifest, the tool called from the skill folder, `946b67d` and HEAD side by side: the verifier
override of R6-002 (`hypotheses` prints a different verdict) and the backticked verdict line of
R6-003 (`check` rc 0 → rc 1). Both outputs are quoted in the findings below.

**The whole-repository effect of the parser change was measured, not argued:** `verdict_mentions`
under both tools over all 60 markdown files tracked by git. The final verdict of every
hypothesis of T1 is unchanged — everything the section filter drops here is a repeat mention,
and `verdicts_in` takes the first — which is why the hunter report needs no `>` marks any
more. The quotation map of every one of the 60 files is identical under the default mode: the
round changed no manifest behaviour.

**What was not done.** `skills-ref validate` could not be run (the validator is not installed
in this session); the diff touches `references/hunter.md` and `references/hunter.ru.md` but no
skill metadata, and `SKILL.md` is untouched. The fix report's "measured on live registers
(setfork-app 6 blocks, arch-dashboard 8)" could not be verified — those repositories are not
reachable from here; the equivalent measurement on this repository was made instead. No
`claude -p` was run: `run-role.sh` and `axes.py` are untouched by this diff. `MSG` key parity
was not re-measured — the diff adds no `MSG` key (the new `import` refusal is a bare English
`die`, like every other refusal in `cmd_import`).

## Findings

### R6-001 · medium · the exception for the old answer form strips every backtick in the line, and a quoted verdict word becomes the line's verdict again

**Location:** `skills/finetooth/scripts/review.py:2648-2651`

**What is wrong:** the exception that keeps the old template's answer form working does
`line.replace("`", "")` — it removes **all** backticks from the line, not the pair around the
hypothesis id. `line_verdict` then runs `unquote_verdicts` on a line that no longer has any
code spans, so the round-2 protection ("a span whose whole content is a vocabulary word is a
quotation") is switched off for exactly those lines. The class it was built for — `n/a` inside
a path, `` `not checked` `` quoted while stating the opposite — comes back.

**Failure scenario:** measured, the same text through both tools:

```
input:  ## Hypotheses
        - `H1.3` — the `n/a` token in a path is handled; checked by running the test
946b67d  {'H1.3': ['checked']}
HEAD     {'H1.3': ['not applicable']}

input:  ## Hypotheses
        - `H1.2` — the template says `not checked`, but in fact I confirmed it live
946b67d  {'H1.2': ['checked']}
HEAD     {'H1.2': ['not checked']}
```

The hunter says "checked", the tool records "not applicable"; `hypotheses` prints it, `summary`
inherits it, `check` counts the hypothesis as answered and stays green — with the wrong answer.
The shape is not invented: the live registers the fix report measured on are written in this
very form (`- ` + a span holding the id), and a hunter that quotes the vocabulary it is writing
about is what the whole `unquote_verdicts` docstring is made of.

**Why it is a defect:** invariant 4 — "a word inside a path, a code span or a fenced block is
not a verdict". It is T1-002 and the `n/a`-in-a-path false positive of the first live block,
reopened through the door this round opened, and no test covers the direction: the suite is
green with the defect in place.

**Introduced by this round or present before:** **introduced by this round.**

**Confidence:** confirmed

### R6-002 · medium · the hypotheses-section filter silently drops the verifier's overriding verdict, and the tool prints the hunter's word instead

**Location:** `skills/finetooth/scripts/review.py:2638` and `:2677-2678`

**What is wrong:** `verdicts_for` overlays the roles in order of seniority — "verify last — it
is the one that overrides" — and its docstring records what happens when that fails: "the
verifier could write 'not checked', and the tool kept showing 'checked'". The new `sectioned`
filter restores exactly that. If the verifier's report contains any heading matching
`HYPOTHESIS_HEADING`, every verdict it gives outside that section is discarded; the hunter's
verdict then stands unopposed. The verifier template does not ask for a hypotheses section — it
says the verdict must be "an ordinary line, outside code blocks and quotations", nothing more —
so a verifier that puts its disagreement under "Where I disagree with the hunter" is writing a
correct report by the prompt it was given.

**Failure scenario:** run end to end on a throwaway repository, same manifest, same two
reports, both tools:

```
hunter:  ## Гипотезы
         - H1.1 — проверена: …
         - H1.2 — проверена: путь входа прочитан целиком.
verify:  ## Гипотезы, которые я перепроверил сам
         - H1.1 — проверена: повторил замер.
         ## Где я не согласен с охотником
         H1.2 — не проверена: доказательство охотника — снимок экрана с другой ветки.

946b67d  H1.1 checked   H1.2 not checked   closed 2/2
HEAD     H1.1 checked   H1.2 checked       closed 2/2
```

`check` is rc 0 in both cases, so nothing goes red: the independent check said the hypothesis
is unproven, and the tool reports it as proven. The verifier's report is the one artefact of
the method that exists to catch a hunter who closed a question he did not answer.

**Why it is a defect:** invariant 9 — the mechanism now demands something the role template
does not tell the agent to produce, in either language; and the contract `verdicts_for`
documents for itself is broken without a gate noticing. The suite does not catch it because
its own `FULL_VERIFY` fixture has no hypotheses heading at all, so `sectioned` is `False` for
every verifier report in the tests.

**Introduced by this round or present before:** **introduced by this round.**

**Confidence:** confirmed

### R6-003 · medium · `check` refuses a report that writes its verdicts the way the hunter template still promises, and the template now contradicts itself in both languages

**Location:** `skills/finetooth/references/hunter.md:89` against `:100-101`
(`hunter.ru.md:89` against `:99-100`); the gate message at
`skills/finetooth/scripts/review.py:3099-3101`

**What is wrong:** the round narrowed the parser twice — a verdict inside an inline code span
is no longer a verdict unless it is a list item opening with the id, and a verdict outside the
hypotheses section is no longer a verdict at all — and updated one sentence of one template.
Eleven lines below the new sentence "Write the verdict as plain text, not in backticks", the
same section still says: "A verdict word alone in backticks is a quotation of the word, not a
verdict either; **a whole verdict line in backticks is one**" (`а вот вся строка вердикта в
кавычках — вердикт`). That promise is now true only for a list item; as a paragraph it is
false. Nothing was written for the second narrowing at all: no template says the verdict must
live under the Hypotheses heading, and the gate message names neither requirement — it says
"each is closed with the word 'checked', 'not checked' or 'not applicable'", which is what the
refused report already did.

**Failure scenario:** run end to end on a throwaway repository, the hunter report written
exactly as `hunter.ru.md:100` promises:

```
## Гипотезы

`H1.1 — проверена: посчитано, а не на глаз.`

`H1.2 — проверена: посчитано, а не на глаз.`

946b67d  H1.1 checked   H1.2 checked   closed 2/2   check rc=0
HEAD     H1.1 NO VERDICT H1.2 NO VERDICT closed 0/2  check rc=1
         · H1: 2 of 2 hypotheses without a verdict (H1.1, H1.2) —
           each is closed with the word 'checked', 'not checked' or 'not applicable'
```

The second narrowing is reachable the same way: a hunter that settles the last hypothesis
while writing up the finding it came from (`H1.3 — not applicable: the module was deleted last
month`, under `## Findings`) loses that verdict — `{'H1.1': 'checked', 'H1.2': 'checked',
'H1.3': 'not applicable'}` on `946b67d`, `{'H1.1': 'checked', 'H1.2': 'checked'}` on HEAD. The
`### Breaking` bullet of the Unreleased section covers fences, four-space indents, `>`, html
comments and bare numbered tables — neither inline code spans nor "any verdict outside the
hypotheses section" is named, so a review under way upgrading the kit meets a red gate with no
entry telling it what to do.

**Why it is a defect:** invariant 9 verbatim — "if `check` demands something the role template
does not tell the agent to produce (in both languages), the gate will go red on an honest
report — that is a defect of the kit, not of the agent"; invariant 3 — the refusal names a fix
that is not the fix; and the on-disk-contract rule that a change a running review has to act on
belongs in Breaking.

**Introduced by this round or present before:** **introduced by this round.**

**Confidence:** confirmed

### R6-004 · medium · the coverage-limits gate still reads a quoted section as the report's own words — the round's principle does not reach it

**Location:** `skills/finetooth/scripts/review.py:3202` with `:2549`

**What is wrong:** the round's principle is "in doubt, the gate goes red", implemented by
giving `quoted_lines` a mode: `"text"` for what defines the work, `"quoted"` for what reports
it. The split is by FUNCTION, not by document — and `section_body`, pinned to `"text"`, is the
function that finds the "Coverage limits" section **of a hunter report**. So in a report an
unclosed fence is still read as text while the section is being found, and only the extracted
body is then re-read in `"quoted"` mode — on a slice that no longer knows a fence was open.

**Failure scenario:** measured on both tools, identical result. The hunter report ends with a
four-line example — a fence with the info string `markdown`, the heading `## Coverage limits`,
one sentence, and no closing fence:

~~~
report-mode quotation map of those four lines: QQQQ   (all of them a quotation)
section_body(report, LIMITS_HEADING)
    → ['Everything in the block was read, nothing was left out.', '']
gate → GREEN on both 946b67d and HEAD
~~~

The only "Coverage limits" statement in the report is inside a quotation, the report says
nothing about what it did not read, and the gate that exists for exactly that passes. This is
the second half of T1-033 ("the gates that read a report's substance still count quoted text"),
at the section-extraction step the fix did not reach.

**Why it is a defect:** invariant 1 — a way to make `check` pass on a state that is wrong. Also
a factual error in the fix report, which describes the `"text"` callers as "manifests:
`section_body`, `section_items_full`, `acceptance_of`, `demote`": `section_body` reads reports.

**Introduced by this round or present before:** **present before** — the behaviour is identical
on `946b67d`. What is this round's is the claim that the question has been settled.

**Confidence:** confirmed

### R6-005 · low · the three register rows this round wrote carry a `fixed_in` naming a file that holds none of their fixes — including the row that records this defect

**Location:** `docs/review/findings.jsonl:47`, `:49`, `:51`

**What is wrong:** T1-051 (R5-006) said three findings were recorded as fixed in a file that
has nothing to do with them. The round corrected those three rows and then wrote six new ones,
all six with `"fixed_in": ["skills/finetooth/scripts/review.py"]` — correct for T1-046, T1-048
and T1-050, false for the other three:

```
T1-047 | CHANGELOG.md             | fixed_in ['skills/finetooth/scripts/review.py']
T1-049 | tests/test_review.py     | fixed_in ['skills/finetooth/scripts/review.py']
T1-051 | docs/review/findings.jsonl | fixed_in ['skills/finetooth/scripts/review.py']
```

**Failure scenario:** `d5da45a` touches `CHANGELOG.md`, `tests/test_review.py` and
`docs/review/findings.jsonl`, so the gate at `review.py:2934` would have passed on each
finding's own file with no `fixed_in` at all — the field was added anyway and is pure
misinformation, on the very row whose claim is "three findings are recorded as fixed in a file
that has nothing to do with them". A later reader, or the gate itself after a rename, takes the
register at its word; in the words of the gate's own comment, "by hand nobody checks that — and
nobody did for half a year".

**Why it is a defect:** the register is read back by the tool and is the review's only memory
(`docs/review/` is deleted when the review closes); a field whose whole purpose is to say where
a fix lives, saying a file that holds none of it, is invariant 1 in its bookkeeping form.

**Introduced by this round or present before:** **introduced by this round** — a verbatim
recurrence of the finding it closed.

**Confidence:** confirmed

### R6-006 · low · the round left `check` red on its own bookkeeping

**Location:** `docs/review/findings.jsonl:38` (T1-038)

**What is wrong:** T1-038 is the one deferred finding, pinned to `skills/finetooth/scripts/review.py`
by `code_sha`. Round 5 changed that file and re-stamped the row (`restamped_at` is in it).
Round 6 changed the same file and did not.

**Failure scenario:** `python3 skills/finetooth/scripts/review.py check` on HEAD, exit 1:

```
· finding T1-038: code in skills/finetooth/scripts/review.py changed since import — re-check …
· T1: block files changed after the review — … `restamp T1`
```

After round 5 the check was red on exactly one thing, the `restamp T1` left for acceptance;
now it is red on two, and the new one is bookkeeping. `SKILL.md` opens the paragraph with "A
red check means the work is not done, even if it looks done" — a red gate that is red for
bookkeeping is what teaches the reader to skim the list, which is R4-004 word for word.

**Why it is a defect:** invariant 1 by its converse — the state check must mean something; and
the round closed R4-004 while re-creating it.

**Introduced by this round or present before:** **introduced by this round.**

**Confidence:** confirmed

### R6-007 · low · a second code-span parser lives outside the one quotation tracker, and the class guard cannot see span parsers

**Location:** `skills/finetooth/scripts/review.py:1451` (`INLINE_CODE`) against `:2497`
(`CODE_SPAN`); `tests/test_review.py:4074` (`QUOTE_DETECTORS`)

**What is wrong:** the tool now has two regexes that decide whether a backtick run is a
quotation, in two functions, with different rules: `CODE_SPAN` (`` `+([^`]*)`+ ``, greedy,
blanks only a span whose whole content is a vocabulary word) inside `unquote_verdicts`, and
`INLINE_CODE` (matching run lengths, CommonMark 6.1) inside `verdict_mentions`. They disagree
on nested spans — on ``` ``- `H1.1 — checked` `` ``` `CODE_SPAN` matches ``` ``- ` ``` and
`INLINE_CODE` matches the whole thing. The class guard `test_цитаты_распознаются_одним_местом`
exists precisely to stop a second quotation parser appearing, and it lists only fence-shaped
detectors.

**Failure scenario:** checked by violation, one run, both forms (the file restored afterwards,
`git status --porcelain` clean):

```
probe with its own FENCE loop            → RED: [('report_headings_probe', ['FENCE'])] != []
probe that asks quoted_lines and then
decides on its own INLINE_CODE rule      → GREEN — the guard is blind
```

The second probe is the shape HEAD already has, which is why the suite is green over R6-001.

**Why it is a defect:** the invariants name the pattern outright — "fingerprint parsers that
diverged (two parses of one section)" — and invariant 2: a mechanism that can be disabled or
duplicated with the suite green is untested.

**Introduced by this round or present before:** the second detector is **this round's**; the
gap in the guard is older, and nothing was added to close it.

**Confidence:** confirmed

## Checked and found correct

- **The `unclosed` mode split is the right shape and is honestly two-sided.** `"text"` for the
  manifest, `"quoted"` for the report; both directions make a gate stricter, never looser, and
  the single new test asserts both maps of one document in one place. I probed the mode on
  every markdown file tracked by git: the default-mode map is identical to `946b67d` for all
  60, so no manifest behaviour moved. And R5-001's own input — the four-backtick fence closed
  out of habit with three, holding the template's skeleton — is refused: `verdicts_in` →
  `{'H1.1': 'checked', 'H1.2': 'checked'}` on `946b67d`, `{}` on HEAD. T1-046 is genuinely
  closed.
- **The `>` marks in the hunter report were genuinely reverted, not re-worded.** The file is
  byte-identical to its `879831b` text, and `hypotheses T1` reads `closed 15/15` with no
  conflict — the gate is green on the report as the hunter wrote it. The fix report's claim
  here is exact, and it is the substance of T1-048: the acceptance criterion can now be written
  without the gate refusing it.
- **The changelog totals are now right.** `findings.jsonl` holds 51 rows: 49 fixed, 1 deferred,
  1 rejected, ids unique — which is what both changelogs now say. T1-047 is genuinely closed.
- **The `import` limit is a real gate with a real message.** It refuses before the row reaches
  the register, names the field, the length and the limit, and says what to do ("shorten it in
  the draft; the evidence belongs in the report"); the mutation is red; and the allowed
  direction is held by the dozen existing `import` tests, which would all go red if the gate
  over-fired. Worth noting for the next editor: the check runs before the duplicate check, so a
  legacy draft holding an over-long row that is already in the register now refuses
  `import --append` until the draft is trimmed. That is fail-closed and the message names the
  fix, so it is not a finding.
- **`QuotationMapTest` moved above `if __name__ == "__main__"`, and it is collected both ways.**
  Measured on HEAD: `python3 -m unittest discover -s tests` → 236 OK, `python3
  tests/test_review.py` → 236 OK. T1-049 closed, and the invocation that used to miss the
  guard now runs it.
- **Every mutation the fix report claims is red, and every mutant still builds** — see the
  table above. None of the five reds came from a syntax error, which is the failure mode rule 2
  warns about.
- **`acceptance_of` pinned to `"text"` is correct**, not an unannounced change of meaning: the
  acceptance criterion is manifest text, and the pin keeps its behaviour identical to
  `946b67d`. It is named in the fix report's own T1-046 row.
- **No unnamed incidental code fix.** Every hunk of `review.py` and `tests/test_review.py` maps
  to a row of the fix report's table; the two truncated rows of the draft
  `docs/review/reports/T1-findings.jsonl` are named there too ("the first run of it caught two
  over-long rows of this very draft"). `docs/review/reports/T1-tool.fixreview-5.md` is round
  5's own report, committed here because round 5 did not commit it — bookkeeping, not a fix.

## Is another round needed

**The findings are real and about product behaviour — but another round of this loop is not
the answer, and that is now a decision for a human.**

By the measure of rule 11 the round did make the project better, and provably: the block's
acceptance criterion can finally be written without the gate refusing it, and the proof is that
the hunter report was restored to its original bytes and `check` is green on it; the changelog
finally states the register's real totals; `import` no longer hands `check` a row nobody can
fix through the tool; the behaviour table runs under both invocations. Against that, the round
put three new defects into the parser it was fixing (R6-001, R6-002, R6-003) and re-created two
of the bookkeeping findings it had just closed (R6-005 = R5-006, R6-006 = R4-004).

Of the seven findings, **six are inside the code and the bookkeeping this round changed**
(R6-001, R6-002, R6-003, R6-005, R6-006, R6-007) and **one is outside it** (R6-004). The
previous four rounds ran 6/7, 2/5, 4/4, 4/6; this one is 6/7 — the worst ratio of the block.
The quotation class has now produced a defect in **six consecutive rounds**: T1-001,
T1-032/033, R3-001, R4-001, R5-001, R6-001. Round 4 wrote that if round 5 produced another
defect in those lines the parser was the wrong shape for the job and the decision belonged to a
human; round 5 produced one, round 6 was that human decision (option 1, "in doubt the gate goes
red") — and the principle was right while its implementation produced three more.

What is different this time is *where* the defects are. The fence rule, which is what the
principle was chosen for, held: not one finding is about `quoted_lines`. All three new parser
defects are in `verdict_mentions`, which got a code-span rule, an exception to it and a section
filter in one commit, guarded by a single assertion over a single document — while the fence
rule next door is guarded by a ten-document behaviour table that has held for two rounds. The
remedy is the one that already worked: a two-sided table over `verdict_mentions` (document →
verdict map, both languages, the old answer form, a span in prose, a verdict in a later
section, a verifier report that overrides), built before the fixes and red on each of them. The
acceptance criterion already asks for that matrix and the hunter report already has 25 rows of
it; it belongs in the suite, not only in a report.

Concretely, for whoever fixes next: R6-001 is a two-line fix (blank only the id span, keep
`unquote_verdicts` working on the rest) and it must not be made without that table. R6-002 and
R6-003 are one decision — either the section filter and the span rule are relaxed, or the two
templates, the gate message and the Breaking section are written to match them; invariant 9
does not allow the third option, which is what HEAD is. R6-004, R6-005, R6-006 and R6-007 are
each closeable in the work the next fixer will do anyway.
