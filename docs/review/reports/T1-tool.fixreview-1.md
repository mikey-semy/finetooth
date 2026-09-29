# T1 — fix review, round 1

## What was checked and how

The diff `dev...HEAD` (14 commits, 21 files) was read in full, the fix report second. Every
claim below was produced by running something, not by reading.

**Reverting (rule 2).** 27 mutations, each in its own copy of the kit, each compiled before
the test was run, each running the test the fix report names for it:

```
26 build=ok RED   — the fix is what the test depends on
 1 build=ok GREEN — my own bad mutation (see below), re-done and RED
```

Covered by revert: T1-001 (fence skip), T1-002 (bare numbered row as header), T1-003
(`unquote_verdicts`), T1-004 (`~~~` in `FENCE`), T1-005 (`file_sha` index fallback) and
T1-005b (`block_lines` own loop), T1-006 (`-z` in the fix gate), T1-008 (missing scan path),
T1-009/009b (id numbering, duplicate draft id), T1-010 (`check_definition`), T1-011/011b
(non-`origin` remote, the inert notice), T1-012/012b (exit code in the journal, the stray
prompt file), T1-013 (rename aliasing), T1-014 (named-files substring), T1-015 (percentile
index), T1-016 (cut at the first ` -->`), T1-017/017b (result event, truncated line),
T1-018/018b (`init`, `restamp`), T1-019 (coverage regex), T1-021 (multi-pass substitution),
T1-022 (marker spend), T1-023 (`check=True`), T1-024 (line type). Every mutant compiled, so
no green came from an absent build.

The one GREEN was mine: I first reverted `current.add(alias.get(new, new))`, which only
matters for a *chained* rename. Reverted at the address that carries the fix —
`current.add(alias.get(p, p))` — the test goes red. Recorded because it is also a coverage
note: the chained rename (a → b → c) is exercised by no test, though the code handles it —
measured live on this repository, `commit_file_sets` credits
`skills/finetooth/scripts/review.py` with **50** commits, exactly `git log --follow
--first-parent` through both of its renames.

**Gates by violation (rule 7).** Ten gates of `cmd_check` silenced one per copy, statement
replaced by `pass`, build checked, the test the registry names run against it — all ten RED,
including the two warning-only gates the verifier's table recorded as "not measurable"
(`ref_paths` changed, findings older than 7 days) and the three whose message is a helper's
return value. The registry itself was violated three ways: a new gate with a literal message
→ RED (the guard works for that shape); a new gate whose message is a variable, and one
whose message is a helper's return value → **GREEN, and the whole 205-test suite green with
it** (finding R1-001).

**Live (rule 8).** `check`, `summary --aged`, `prompt`, `status`, `coverage`, `set-status`,
`import`, `sizes` run against scratch repositories built for the case, and the same probes
run against `dev`'s `review.py` side by side wherever I claim a regression. `axes.py` driven
over seven synthetic streams (empty, no `result`, `result` without `usage`, two `result`
events either way round, truncated). The parser (`verdict_mentions`, `verdicts_in`,
`names_file`) driven directly over a matrix of report shapes and over the three real reports
of this block. Full suite: **205 tests, OK, 190 s**. `npx skills-ref validate
skills/finetooth`: **Valid skill**.

**Not done.** I did not re-run the full 62-gate mutation matrix (I sampled 10 of 62) nor
re-derive the `MSG` and parser acceptance tables in full (I checked `MSG` en/ru set equality
— 56 = 56, no difference — and ran the parser over the shapes that matter to the fixes). I
did not run `claude -p` for real: `run-role.sh` was exercised with a stub, as the fix report
already records. I did not measure on a 180k-line project.

## Findings

### R1-001 · medium · The new guard for "a gate that cannot go red" does not see a gate whose message is not a literal
**Location:** `tests/test_review.py:3477` (`GateRegistryTest.GATES`), `tests/test_review.py:3542`
**What is wrong:** `_check_gates()` keys a gate by the literal parts of its message. Three of
the tool's own gates append a value rather than an f-string (`verify_report_problem`,
`dup_problem`, `rule_problem`), so their keys are `':'`, `''` and `"root '':"` — and `''` is
now a registered key. Any new `problems.append(<anything that is not an f-string>)` therefore
matches an existing entry and the registry stays green.
**Failure scenario:** run against a copy of the kit. Adding to `cmd_check`

```python
if st.get("review_id") != defn.get("review_id"):
    msg = f"review_id mismatch"
    problems.append(msg)
```

— a gate with no test at all — leaves `GateRegistryTest` green (rc 0) and the whole suite
green (205 tests, OK). The same holds for `problems.append(dup_problem(...))`. Written with a
literal message instead, the identical gate turns `GateRegistryTest` red. So the guard covers
one of the two shapes the tool actually uses, and the shape it misses is the one three
existing gates are written in — the next gate added by copying its neighbour is untested and
nothing says so.
**Why it is a defect:** invariant 2 — "a check whose mechanism can be disabled while the suite
stays green is untested". This guard is the round's answer to the root class with four
instances (T1-007, 008, 011, 022); a guard that the natural next instance walks past does not
close the class. AGENTS.md rule 2 states the rule as kept.
**Introduced by this round or present before:** introduced by this round (`GateRegistryTest`
is new in `7b55f5c`).
**Confidence:** confirmed

### R1-002 · low · `summary --aged` now counts one file under two names — the opposite of what the change claims
**Location:** `skills/finetooth/scripts/review.py:1393`
**What is wrong:** incidental fix 2 of the fix report moved the drift query to `-z` with an
`\x01` commit marker. With `-z`, git glues the newline that terminates the `--format` line to
the **first path of every commit**: the stream is `\x01<sha>\0` + `\nsrc/a.ts\0src/b.ts\0`.
`commit_file_sets` strips that leading `\n` (`after_header`); `cmd_summary` does not, so
`files` holds both `"\nsrc/a.ts"` and `"src/a.ts"`.
**Failure scenario:** reproduced end to end. A repository whose base commit is followed by
two commits — one touching `src/a.ts` and `src/b.ts`, one touching `src/b.ts` — gives
`summary --aged`:

```
HEAD:  H1   commits: 2   files: 3      <- two files exist
dev:   H1   commits: 2   files: 2      <- correct
```

The same run against `dev`'s `review.py` prints 2. Every file that is first in one commit and
not first in another is counted twice, so the drift table over-reports on any real history,
in the one file that is meant to outlive `docs/review/`.
**Why it is a defect:** it is a regression in the number a user reads, and the change that
caused it was made without a test of its own — the fix report says the command "is exercised
by `test_итог_с_маркером_внутри_названия_блока_не_роняет_aged`", which asserts only exit 0
and the absence of a traceback, and `SourceRuleTest` only asserts that `-z` is passed, not
that its output is parsed. Rule 3: the forbidden direction got a test, the allowed one did not.
**Introduced by this round or present before:** introduced by this round (`83a41c1`).
**Confidence:** confirmed

### R1-003 · low · The named-files gate now refuses a report that writes `./src/api.ts`
**Location:** `skills/finetooth/scripts/review.py:2599` (`names_file`)
**What is wrong:** the lookbehind `(?<![A-Za-z0-9_./-])` exists to stop `docs/src/api.ts`
closing the gate for `src/api.ts`. It also stops `./src/api.ts` and `a/src/api.ts` — the
`./` form an agent writes by habit and the `a/`, `b/` prefixes of a pasted diff header.
**Failure scenario:** reproduced end to end. A block owning `src/api.ts` and `src/util.ts`,
with a hunter report whose coverage list is

```
- ./src/api.ts
- ./src/util.ts
```

gives `check` exit 1: "H1: 2 of 2 block files are not named by full path in any report
(src/api.ts, src/util.ts)". The same report passes on `dev`. The report is honest and
complete; the gate refuses it, and the author's only repair is to rewrite the paths.
**Why it is a defect:** the fix report's own weighing — "a gate that stops accepting honest
reports is discovered by the person whose work it refuses" — applies here, and the paired
"still allowed" test covers only a trailing period. `names_file` is used for the whole
coverage gate, so the refusal is total, not partial.
**Introduced by this round or present before:** introduced by this round (`242f88b`).
**Confidence:** confirmed

### R1-004 · low · A quoted verdict still closes a hypothesis when it is quoted by indentation or by `>`
**Location:** `skills/finetooth/scripts/review.py:2496` (`verdict_mentions`)
**What is wrong:** T1-001 was closed for fenced blocks only. Markdown has two other ways to
quote an example, and both still reach the parser as ordinary lines.
**Failure scenario:** run on the parser, block id `T1`:

| report body | verdicts read |
|---|---|
| ` ```markdown ` … `- T1.1 — checked: <what proves it>` … ` ``` ` | `{}` — fixed |
| a four-space indented block holding the same line | `{'T1.1': ['checked']}` |
| `> - T1.1 — checked: <what proves it>` | `{'T1.1': ['checked']}` |
| `<!-- - T1.1 — checked: … -->` | `{'T1.1': ['checked']}` |

A report that restates its assignment as an indented example, or quotes the template with
`>`, closes its hypotheses without answering them and `check` prints "review state is
consistent" — the same false pass T1-001 describes, through a neighbouring door.
**Why it is a defect:** invariant 1 and invariant 4; rule 5 — the fix must go to every address
of the defect. The role template now says "outside code blocks", which covers the fence but
not the two other forms a reader would also call a code block.
**Introduced by this round or present before:** present before; this round closed one of the
three addresses.
**Confidence:** confirmed

### R1-005 · low · `axes.py` changed which `result` event it measures, and this is in no report and under no test
**Location:** `skills/finetooth/scripts/axes.py:65`
**What is wrong:** the diff replaces "the last `result` wins" with "the `result` with the most
turns wins". That is a behavioural change to the measurement the turn caps are derived from.
It appears in no line of `T1-tool.fix.md` — neither among the 24 findings nor among the seven
incidental fixes — and in no line of `CHANGELOG.md`, and no test drives a stream with two
`result` events.
**Failure scenario:** a stream carrying a 40-turn `success` result and a 2-turn
`error_max_turns` result reports, in either order, `spend: 10 min, 40 turns … $5.00` with no
outcome word — the cut-off marker in the shorter event is dropped. The heuristic is defensible
(a capped run has the most turns by construction), which is exactly why it needs to be
written down: nobody re-derives it from the diff. In the same round the kit's own journal
gained `spend: 0 min, 2 turns, 329 tool calls … cost estimate $67.92` — a line that reads as a
measurement and cannot be one — and neither `axes.py` nor the guards added beside it say so.
**Why it is a defect:** rule 6 — an incidental fix not named in the report is a finding even
when it is correct; and AGENTS.md rule 2 — every new mechanism comes with a test.
**Introduced by this round or present before:** introduced by this round (`3230faa`).
**Confidence:** confirmed

### R1-006 · low · The changelog's Breaking section holds five fixes that are not breaking, and not the change that is
**Location:** `CHANGELOG.md:41`, `CHANGELOG.ru.md:41`
**What is wrong:** the new `### Breaking` heading was inserted in the middle of the existing
`### Fixed` list. Five bullets that belonged to Fixed — the `prompt` placeholder check, the
cited-line filter, the two verdict false positives from setfork H3, the `SKILL.md`
description, the untracked-pattern message — now sit under Breaking in both languages. The
same insertion happened to `### Added`.
**Failure scenario:** a user upgrading a running review reads the Breaking section to find what
they must act on and is told that "`SKILL.md` description said three roles" is a breaking
change, while the change that really does break a running review is not there: `blocks()` now
validates every block definition, so a `blocks.json` that worked yesterday can refuse every
command today. Measured, dev vs HEAD, same repository:

```
phase written as "1"   dev: status rc=0    HEAD: status rc=2  "has no whole-number `phase`"
goal written as ""     dev: status rc=0    HEAD: status rc=2  "has no `goal`"
```

Exit 2 on `status`, `order`, `summary`, `prompt` and `check` alike. The refusal itself is the
fix and is right; its absence from Breaking is not — the invariant says a change a running
review has to act on is recorded there.
**Why it is a defect:** the on-disk format of `docs/review/` is a contract, and the Breaking
section is how the contract's changes are delivered; here it is both wrong and incomplete.
**Introduced by this round or present before:** introduced by this round (`2ce050d`).
**Confidence:** confirmed

### R1-007 · low · Two new rules in the fix role template, recorded nowhere
**Location:** `skills/finetooth/references/fix.md:59`, `skills/finetooth/references/fix.ru.md:62`
**What is wrong:** rules 11 ("the version, the release and the history are not yours") and 12
("spend turns on fixes, not on ceremony") were added to the fix template in both languages in
`d1d2552`. There is no `CHANGELOG` entry, no journal line and no test — while the sibling
template change of the same round (where a verdict is written) got all three, including
`test_шаблоны_ролей_говорят_где_писать_вердикт`.
**Failure scenario:** a later editor reworks `references/fix.md` — the file is T2's subject and
T2 has not run yet — and drops either rule. Nothing goes red, nothing in the changelog says
the rules were ever there, and the next fix phase bumps the version again and re-runs the
suite in ten worktrees, which is the cost these two rules were written to stop (329 turns,
most of it ceremony, measured in this very round).
**Why it is a defect:** rule 6 — a change in the diff that is named in no report; and the
kit's own rule that a change to a mechanism is a change to a prompt, kept by a test.
**Introduced by this round or present before:** introduced by this round.
**Confidence:** confirmed

## Checked and found correct

- **The fix report matches the diff.** Every one of the 24 findings is touched at the place it
  names, every commit in the report's table exists with the content claimed, and the register
  (`findings.jsonl`), `findings.md` and the journal agree with each other and with `check`.
  The two deliberately unfinished halves (a bare "verified" in prose, T1-003; "все находки
  проверены", T1-019) are argued in the report rather than hidden, and I agree with both: the
  first cannot be separated from a legitimate verdict by any mechanical rule, and the second
  is the Russian of the sentence the same finding forbids.
- **The paired "still allowed" tests are there** for sixteen of the fixes — the freshness gate,
  guard-grep, the definition check, the pathspec, `import`, `init`, `restamp`, the percentile,
  `axes`, the fix-commit gate, the line type, one-pass substitution, the coverage regex, the
  fence, the table and `file_sha`. This is the part most easily skipped and it was not.
  The two places where it is missing are R1-002 and R1-003.
- **`commit_file_sets` is right, including the chained rename**, which I doubted: 50 commits
  for `review.py` against `git log --follow`, and no old name left in the sets.
- **`file_sha`'s index branch hashes a symlink the same way in both branches**, so the
  fingerprint really does not jump when a sparse checkout lays the link out.
- **`MSG` en/ru are still 56 keys each with no difference**, and `skills-ref validate` passes.
- **`block_lines` through `file_lines` costs a `git show` per file.** `sizes` on this
  repository: 0.23 s (dev) → 0.45 s (HEAD) for 85 files, i.e. linear with a ~2.6 ms constant,
  about +5 s on a 1,845-file project. Linear, so by the invariants not a finding — recorded so
  the number exists if someone later measures a slow `check`.
- **`SourceRuleTest.test_ограды_кода_распознаются_одним_местом` is weaker than it reads**: the
  source contains five occurrences of `fenced_lines(` (the definition and four callers) against
  a threshold of `>= 4`, so removing one caller keeps the guard green. It is not a finding
  because all four callers have a functional test of their own — but the threshold should be
  the number of callers, not four.
- **The hunter report's six contradictory verdicts and the block fingerprint** were correctly
  left to acceptance: I re-measured both — the six are identical before and after the parser
  change, and `restamp T1` is the only thing `check` still wants.

## Is another round needed

**Yes, but a narrow fix pass, not a new hunt.** The project plainly got better: twenty-four
defects that let `check` pass on a false state, crash on a legal command line or lie in the
journal are closed, and I proved twenty-seven of the fixes by reverting them with the build
intact — the tests are load-bearing, not decorative. The gate → test table holds on a
ten-gate sample including the two the verifier could not measure. Nothing found here
threatens that.

Of the seven findings above, **six are inside the code this round changed** and one (R1-004)
is an address of an old defect the round narrowed but did not close. That ratio would be
alarming if the findings were mechanisms; they are not — three are two-line parsing or
documentation slips, one is a guard's coverage, one is an unrecorded change, one is a
changelog heading in the wrong place. None is critical or high, and none reopens a closed
finding.

So: one fix pass over R1-001…R1-007, with no new mechanisms invented — R1-001 wants the
registry to key gates by line rather than by literal, R1-002 wants the `after_header` strip
`commit_file_sets` already has, R1-003 wants `./` and `a/`, `b/` allowed before a path,
R1-004 wants `fenced_lines` to know an indented block and a `>` quote. Then `restamp T1` and
close. If that pass produces findings again, that is the signal to stop fixing and to look at
why — but on this round's evidence the machine is working, not looping.
