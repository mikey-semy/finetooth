# T1 — fix review, round 2

Seven findings closed by the fixer (1 medium, 6 low), 6 commits `6ae9c90…341c56d` plus the
report and the journal. **Five findings here: 2 medium, 3 low.** Two of them are inside the
code this round changed; three are older addresses of the class it was closing.

## What was checked and how

**The diff was read in full, and the claims were re-measured rather than taken.**

*Tests proven by reverting* — every one in a worktree copy, with the build checked (`ast.parse`
plus a real `--help` run) on each mutant; all seven mutants built:

| mutation | test | result |
|---|---|---|
| a gate `problems.append(why)` added to `cmd_check` — the shape of an existing gate | `GateRegistryTest` | **red** |
| same with `msg`, with `dup_problem(...)`, and with a literal message | `GateRegistryTest` | **red** (all three) |
| the registry fix reverted (literal-only key + set comparison) **and** the `why` gate added | `GateRegistryTest` | **green** — so the test does depend on the fix, not on something else |
| the three prefixes removed from `names_file` | `…приставкой_точки…` red, `…из_другого_каталога` **green** | both directions hold |
| the prefix widened to any directory | `…из_другого_каталога` **red** | both directions hold |
| `verdict_mentions` back to `fenced_lines` | 3 subtests red + `SourceRuleTest.test_цитаты…` red; `…под_своей_гипотезой…` **green** | both directions hold |
| `cmd_summary` back to its own parse of the log stream | `test_дрейф_не_считает_один_файл_дважды` red + `test_записи_коммитов…` red | ok |
| `axes` outcome back to the single longest result | `test_обрезка_во_втором_событии…` red; `…два_успешных…` **green** | both directions hold |
| the `axes` partial-result check silenced | `test_результат_короче_потока…` red; `…два_успешных…` **green** | both directions hold |
| rules 11 and 12 cut out of `fix.md` | `test_шаблон_исполнителя_держит_правила…` red | ok |

*Gates checked by violation, not by reading:* the gate registry (four shapes, above), the
`-z` rule, the commit-record rule, the quotation rule. The quotation rule was also violated
in the direction it does **not** cover — see R2-003.

*Reproduced live, through the CLI, on real stands* (not by calling the parser): the nested-fence
false pass (R2-001), the verifier-report false pass and the coverage-limits one (R2-002), the
`a/` prefix (R2-004), and the truncated-stream crash of `run-role.sh` (R2-005).

*Regression surface of the parser rewrite, measured independently of the fixer's claim:*
`verdict_mentions`, `section_items`, `demote` and `section_body(LIMITS_HEADING)` compared
old (`7a7b944`) vs HEAD over **32 real markdown files** — every report, manifest, invariants
file, role template, README and CHANGELOG in the tree: **0 differences**. `order` and
`coupling` on this repository's own history: byte-identical old vs HEAD, so the
`commit_file_sets` rewrite onto `log_records` is behaviour-preserving as claimed.

*Gates run:* `python3 -m unittest discover -s tests` → **217 tests, OK** (218 s), matching the
report's count; `npx skills-ref validate skills/finetooth` → **Valid skill**; `review check`
on the kit fails only on the two things the report leaves for acceptance (the stale block
fingerprint and the hunter report's own six contradictory verdicts); `coverage` and `findings`
re-run leave the tree clean (idempotent).

*Report vs diff:* every fix in the diff is in the report, every test the report claims exists,
and the four incidental fixes are named with their tests as rule 6 requires. The fixer's own
unfixed finding (`import` accepts a claim/scenario over the limit that `check` then refuses)
was reproduced and is accurate: `import` exits 0, `check` then says
`finding H1-001: scenario is 793 characters against a limit of 700`.

*What I did not do:* no `claude -p` run was made, so `axes.py` was exercised only on synthetic
streams (no retained real stream exists in the tree); the "a turn carries at most one assistant
message" premise behind `PARTIAL RESULT` is therefore reasoned from the journal's own lines
(80 turns / 79 tool calls, 186 / 185), not measured against a live stream.

## Findings

### R2-001 · medium · A verdict inside a fence nested in a list item still closes a hypothesis

**Location:** `skills/finetooth/scripts/review.py:1430` (`FENCE`), used by
`quoted_lines` at `skills/finetooth/scripts/review.py:1467`

**What is wrong:** `quoted_lines` learned the list-item content column for the *indented*
code block (`indent >= content_col + CODE_INDENT`) but `FENCE` still anchors at
`^\s{0,3}` absolutely. A fence opened inside a list item — indented 4 or 5 spaces, which
is where a fence belongs when it sits under a `- ` bullet — matches neither rule: too deep
for `FENCE`, too shallow for the indented-code rule. Everything inside it is read as the
report's own words.

**Failure scenario:** reproduced end to end, `check` rc 0. A hunter report whose hypotheses
section is

~~~
## Гипотезы

- Задание просило написать вердикт так:

    ```markdown
    - H1.1 — проверена: <чем доказано>
    - H1.2 — проверена: <чем доказано>
    ```

Ни на одну гипотезу я не ответил.
~~~

gives `hypotheses H1` → `H1.1 checked`, `H1.2 checked`, `closed 2/2`, and `check` prints
**"review state is consistent"** on a report that answers nothing. The same text with the
fence at the margin is correctly read as `{}`. Parser matrix, block id `T1`:

| shape | verdicts read | correct? |
|---|---|---|
| fence at the margin | `{}` | yes |
| `~~~` fence | `{}` | yes |
| four-space block after a blank line | `{}` | yes |
| `>` quote, `<!-- comment -->` | `{}` | yes |
| fence inside a **numbered** item (3-space indent) | `{}` | yes |
| **fence inside a `- ` item (4 spaces)** | `{'T1.1': ['checked']}` | **no** |
| **fence inside a `- ` item (5 spaces)** | `{'T1.1': ['checked']}` | **no** |
| sub-item indented under a verdict | `{'T1.1': ['checked']}` | yes |

**Why it is a defect:** invariant 1 — `check` green on a wrong state, the most serious class
here. It is the unclosed remainder of T1-001 (severity **high**), and the fix report claims
the opposite: "Checked on a matrix of 21 report shapes … all 21 agree with what the reader
of the report would see." The reader of that report sees an example; the parser sees an
answer. Weigh the severity accordingly — I set medium only because the general form is
closed and this one needs the quotation to be nested.

**Introduced by this round or present before:** present before (`FENCE` is untouched); the
fix of T1-028 claimed the class closed and did not reach it.

**Confidence:** confirmed

### R2-002 · medium · The gates that read a report's substance still count quoted text

**Location:** `skills/finetooth/scripts/review.py:2434` (`verify_report_problem`); the same
shape at `skills/finetooth/scripts/review.py:3120` (the coverage-limits gate)

**What is wrong:** `quoted_lines` was wired into the four markdown parsers, but the two gates
that judge whether a report *says* anything read it with `.splitlines()` and a regex.
A fenced skeleton satisfies them.

**Failure scenario:** reproduced end to end, `check` rc 0, twice.

1. A verifier report whose entire body is `Шаблон просит написать так:` followed by a
   ```` ```markdown ```` fence holding `- H1-001 — подтверждена: воспроизвёл.` and
   `Охват полный, непрочитанного нет.` — nothing verified, nothing stated — passes
   `verify_report_problem`, and the block stays `verified` with `check` printing
   "review state is consistent". This is the gate whose own docstring says "an empty
   `*.verify.md` alongside a full hunter report moved the block to `verified` without an
   independent check", and it is the same gate T1-019 (medium) was filed against.
2. A hunter report whose `## Ограничения охвата` section holds only a fenced example passes
   the "coverage limits are empty" gate the same way.

**Why it is a defect:** invariant 1, and rule 5 of the fix role — the fix goes to every
address of the defect. "A quotation is not an answer" was fixed in the verdict parser and
left standing in the two gates that ask the same question about the same files.

**Introduced by this round or present before:** present before; this round is where it should
have been found, because this round is what established that quotations are not answers.

**Confidence:** confirmed

### R2-003 · low · The new quotation guard cannot see a parser that does not exist yet

**Location:** `tests/test_review.py:3826` (`MARKDOWN_PARSERS`), used at
`tests/test_review.py:3851`

**What is wrong:** `SourceRuleTest.test_цитаты_распознаются_одним_местом` — written this
round to replace the `count("fenced_lines(") >= 4` threshold — checks that *four named*
functions call `quoted_lines`. A fifth markdown parser, written by copying its neighbour and
calling the weaker `fenced_lines`, references no detector constant and is not in the list, so
the guard is content. This is precisely the defect R1-001 described for `GateRegistryTest`,
in the guard this round wrote to close a different class — and the fix for R1-001 shows the
answer: derive the set from the source and compare counts, don't enumerate it by hand.

**Failure scenario:** measured. A new function added to `review.py`

```python
def report_sections(md: str) -> list[str]:
    out = []
    lines = md.split("\n")
    for line, fenced in zip(lines, fenced_lines(lines)):
        if not fenced and line.startswith("#"):
            out.append(line)
    return out
```

leaves `SourceRuleTest` **green** (4 tests, OK) — a parser that reads a `>` quote, an indented
example and an html comment as the report's own words, with nothing to say so. It is not
hypothetical: `verify_report_problem` (R2-002) is that parser today, and the guard does not
see it either.

**Why it is a defect:** the block manifest names "a gate that cannot go red (mechanism
removable with the suite green)" as a finding, and invariant 2 requires the mechanism to be
provable by mutation. A guard with a hand-written list of subjects goes stale the first time
someone adds a subject.

**Introduced by this round or present before:** **introduced by this round** — it replaced a
weaker rule with a stronger one that has the same blind spot in a new shape.

**Confidence:** confirmed

### R2-004 · low · `a/` and `b/` are accepted as prefixes, so a real `a/` directory closes the gate for a file nobody read

**Location:** `skills/finetooth/scripts/review.py:2692` (`names_file`)

**What is wrong:** the fix for T1-027 accepts `./`, `a/` and `b/` wherever the prefix itself
starts a path. `./` is unambiguous; `a/` and `b/` are only unambiguous when no such directory
exists. The second-direction test covers `lib/a/src/api.ts` (blocked by the lookbehind) but
not a top-level `a/`.

**Failure scenario:** reproduced end to end. A block owning `src/api.ts` and `a/src/api.ts`
(a repository with a top-level `a/` directory) whose report names only `a/src/api.ts`:
`check` exits **0** and says nothing about `src/api.ts`, which no report mentions. On
`7a7b944` the same report is correctly refused (`names_file("- a/src/api.ts", "src/api.ts")`
→ `False` before, `True` after).

**Why it is a defect:** the named-files gate exists to catch a file nobody opened; here it
credits one file for another. Narrow — it needs a root-level `a/` or `b/` — but the fix has
a form that does not need the ambiguity: the diff-header prefixes only ever appear after
`--- `/`+++ `/`diff --git `, and matching them in that position costs nothing.

**Introduced by this round or present before:** **introduced by this round**.

**Confidence:** confirmed

### R2-005 · low · `run-role.sh` dies on the truncated stream `axes.py` was taught to survive

**Location:** `skills/finetooth/assets/run-role.sh:58`

**What is wrong:** the inline reply printer does `json.loads(line)` on every line. `axes.py`
carries an explicit comment two calls earlier — "A killed run leaves its last line
half-written. Dying on it costs the journal line, the agent's reply and the run's exit code"
— and counts the unreadable lines instead. The wrapper then dies on exactly that line.

**Failure scenario:** measured on a stream whose last line is `{"type":"assis`. `axes.py
--journal` prints `1 unreadable line(s) · spend: …`; the same file through the run-role
snippet exits 1 with `json.decoder.JSONDecodeError`. Under `set -euo pipefail` that is the
script's last command, so `exit $RC` never runs: an operator whose run was killed (`claude`
exit 143) or cut off sees a Python traceback and the exit code 1, and anything scripted on
top of `run-role.sh` reads the wrong ending.

**Why it is a defect:** invariant 12 — a traceback reachable from a legal command line — in
the one code path that only runs when something already went wrong.

**Introduced by this round or present before:** present before, untouched by both rounds.

**Confidence:** confirmed

## Checked and found correct

- **The gate registry (T1-025).** The count-based comparison is the right call and is proven:
  with the fix reverted, a second `problems.append(why)` gate passes unnoticed; with the fix,
  all four shapes go red. The two re-keyed `GATES` entries match what `_check_gates` now
  produces.
- **`log_records` (T1-026).** One reader, and the newline is stripped from the first token
  only — which is right, because that is the only token git glues it to. The
  `commit_file_sets` rewrite onto it looked like the riskiest edit of the diff (rename aliasing,
  `-M` status pairs, the `close()` that is now implicit); `order` and `coupling` on this
  repository's 800+ commit history are byte-identical before and after.
- **The indented-code rule of `quoted_lines`.** The part I expected to break honest reports
  — proof written as a sub-item under a verdict — holds: the content column is taken from the
  enclosing list item, an indented block may only start after a blank line, and a paragraph at
  the margin closes the list. On 32 real files no parse changed.
- **`PARTIAL RESULT` in `axes.py`.** Reading the outcome from every result event while taking
  the numbers from the longest is sound, and the ties do not matter. One wording note, not a
  finding: the report says the line "says `PARTIAL RESULT …` instead of printing a spend" —
  `journal_line` prints both, the warning first. The behaviour is the better of the two; the
  sentence is just inaccurate.
- **The `./`-prefix fix itself (T1-027).** The lookbehind still refuses `docs/src/api.ts` and
  `lib/a/src/api.ts`; only the root-directory case of R2-004 is open.
- **The changelog restructure (T1-030/T1-031).** One heading per type, Breaking last, in both
  languages; the block-definition validation is described with what a running review must do,
  and I confirmed the behaviour it describes (`"phase": "1"` → rc 2 today, rc 0 on `dev`).
  No test is claimed for it, correctly.

## Is another round needed

**One more fix pass, yes; another full review round after it, probably not.**

By the measure in rule 11: of the five findings, **two are inside the code this round changed**
(R2-003, R2-004) and **three are outside it** (R2-001 — the same function, but a defect that
predates the round and survived it; R2-002 and R2-005 — older addresses). Round 1 produced six
findings in the round's own changes; this one produced two, both low and both narrow. That is
convergence, not a loop.

What makes the pass worth running is not the count but what is still open: R2-001 and R2-002
are ways to make `check` print "review state is consistent" on a review that answered nothing —
the class this block exists to close, and the class the last two rounds have been closing one
door at a time. Three doors have now been found by three different means (the fence, the
indent/quote/comment, the nested fence and the two gates); closing them by listing forms will
keep costing a round each. The lever is R2-003: make the guard derive its subjects from the
source instead of naming four, and the next parser that reads a quotation as an answer fails
the suite when it is written rather than when a review believes it.

Suggested order for the next fixer: R2-003 first (it is what finds the rest), then R2-001 and
R2-002 under it, then R2-004 and R2-005. After that I would close T1 on the diff review, not
on a fourth hunt.
