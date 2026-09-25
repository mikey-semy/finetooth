# T2 — fix review, round 2

## What was checked and how

The diff (`d33527c...HEAD`, 171 KB / 1262 lines) was read in full — it fits in one context,
so no split was requested. Five commits: `cea1cd8`, `4da0304`, `d258166`, `3c3e7d7`,
`ce57a13`.

**Reverted with the fix undone, in a copy of the tree, every regression test the report
claims** (mutants checked to parse before running — `BUILD OK` where the tool was touched):

| finding | mutation | result |
|---|---|---|
| T2-016 | every fenced block deleted from all eight templates | `FAILED (failures=16)` |
| T2-016 | the four English templates back to `f1a44a0` | `FAILED (failures=4)` — **`root` among them**, the half that stayed green before |
| T2-017 | `subs["{{DIFF}}"]` removed, the exemption restored, the trailing `replace` put back (BUILD OK) | both new tests red |
| T2-018 | `diff_vol` en+ru restored, rule 1 of both templates restored | 4 red: the class guard at three addresses + the behaviour test |
| T2-019 | the deferral gate → `warnings` (BUILD OK) | `test_отложенная_без_причины_по_прежнему_роняет_проверку` red |
| T2-019 | the reject-reason gate → `warnings` (BUILD OK) | `test_отказ_с_причиной_только_в_claim_по_прежнему_ловится` red |
| T2-019 | the three-instances gate → `warnings` (BUILD OK) | `test_корень_из_образца_собирает_класс_и_зажигает_ворота_про_узду` red |
| T2-021 | the deferral refusal's tail restored (BUILD OK) | `test_отказ_ворот_говорит_то_же_что_сводка` red |
| T2-021 | `SKILL.md`'s completion sentence restored | the table test red, `файл='SKILL.md'` |
| T2-021 | both lessons restored from `a2eceb0^` | the table test red on both files |
| T2-022 | the "Volume of work" section removed from both verifier templates | `FAILED (failures=3)` — both files and the prompt |

Every claimed mutation reproduces. No test in this round is green on the old code.

**Reproduced live**, not only read:

- `prompt H1 --role hunter` on a stand with a 7000-line block, over the 6000-line ceiling:
  the warning the round rewrote, the report skeleton it points into, and then `check` on a
  hunter report written by that instruction — exit 1. This is R2-001 below.
- `prompt T2 --role fixreview` without `--diff` — exit 2 with
  `the fix reviewer needs a diff: --diff <range>, for example main...HEAD`. The tightening of
  the unfilled-substitution check (incidental fix 1) therefore cannot strand a lead who
  forgot the flag; checked because removing an exemption is how that usually happens.
- The guard the round recorded against the class `class guard keyed on incidental syntax`,
  run against an instance of that class (a bare module-level `FOO_LIMIT = 6 * 7`): green,
  while the guard it replaced is red. This is R2-002 below.

**Searched for other addresses myself** (`grep`), not from the fixer's list: every mention of
`--scope` in the tool, the skill, the assets, both entry points, both READMEs and both
CHANGELOGs; every mention of `{{DIFF}}`/`{{VOLUME}}`; the `LIMITS_HEADING` /
`COVERAGE_VERDICT` gates against the wording of `vol_over`.

**Not done.** The full suite was not re-run end to end (the fixer's run is quoted as
`Ran 336 tests — OK`; every class this round touches was run individually, all green on the
unmutated tree). `skills-ref validate` was not re-run. The T3/T4 findings still open are
outside this block and were not examined except where this round wrote to their register
records.

## Findings

### R2-001 · medium · the over-the-ceiling warning now names a section the gate does not read

**Location:** `skills/finetooth/scripts/review.py:182` (en), `:234` (ru)

**What is wrong:** `vol_over` used to end "**name the rest by path** in the coverage-limits
section" — the exact name of the hunter report section that `check` parses with
`LIMITS_HEADING`. This round rewrote it to "in the coverage section of your report" (ru: "в
разделе своего отчёта про охват"). The hunter's report skeleton has **two** sections:
`## Coverage` / `## Охват` (files read) and `## Coverage limits` / `## Ограничения охвата`
(what was not read). Only the second is the one the gate reads, and the new wording names the
first.

The change was made as an incidental of T2-022, on the stated ground that `LIMITS_HEADING`
does not match the verifier's `## Block coverage status`. It does not — but `check` never
applies `LIMITS_HEADING` to a verifier report: the verifier's coverage gate is
`COVERAGE_VERDICT` (`review.py:2661`), which matches the bare word `coverage`/`охват` anywhere
in the body. Nothing had to be taken away from the hunter to serve the verifier.

**Failure scenario:** reproduced end to end on a stand with one 7000-line file (over the
6000-line ceiling, so `vol_over` fires):

```
⚠️ The block is larger than one session can read — 7000 lines against a ceiling of 6000.
… the only honest way out is to read as much as you can and **name the rest by path** in
the coverage section of your report.

report skeleton in the same prompt:  ## Coverage … ## Coverage limits …
```

A hunter that does exactly that — names the unread rest by path under `## Coverage`, leaves
`## Coverage limits` at the skeleton line — gets:

```
check exit: 1
  · H1: the 'Coverage limits' section of the hunter report is empty — name what was not
    read or say outright that there is nothing …
```

Both languages: the Russian `## Охват` is equally unmatched by `LIMITS_HEADING`
(`ограничени|не проверено|не прочитано|не сделал|не смотрел|не дошёл`).

**Why it is a defect:** invariant 9 — a gate demands something the prompt does not tell the
agent to produce, so the gate goes red on an honest report. It is the exact class T2-001 and
T2-002 of this block were about, re-created in the other direction. The hunter template itself
still says "the coverage-limits section below" (`hunter.md:108`), so the prompt now
contradicts itself.

**Introduced by this round:** yes — `cea1cd8`, named in the fix report under T2-022 as "the
same sentence", not as a finding of its own.

**Confidence:** confirmed

**Root:** a document names a way out the mechanism does not provide

---

### R2-002 · medium · a five-instance class across three blocks re-pointed at a guard that cannot go red on it

**Location:** `docs/review/findings.jsonl` (records `T3-002`, `T3-012`, `T3-014`, `T4-021`)

**What is wrong:** `set-finding --rule` writes the guard onto **every** finding sharing the
root ("the class is closed as a whole or not at all", `review.py:2284-2288`). Recording
`tests/test_review.py::TemplateContractTest` for T2-016, whose root is
`class guard keyed on incidental syntax`, therefore overwrote the guard of every other member
of that class:

| id | block | status | rule before `d33527c` | rule now |
|---|---|---|---|---|
| T3-002 | T3 | fixed | `SourceRuleTest` | `TemplateContractTest` |
| T3-012 | T3 | fixed | `SourceRuleTest` | `TemplateContractTest` |
| T3-014 | T3 | fixed | `SourceRuleTest` | `TemplateContractTest` |
| T4-021 | T4 | **open** | — | `TemplateContractTest` |

`TemplateContractTest` reads the eight role templates and the register's field names. It
cannot see any of those three defects. The guard that can — `SourceRuleTest` — is no longer
recorded anywhere.

**Failure scenario:** measured. A bare module-level threshold with no source beside it —
`FOO_LIMIT = 6 * 7`, the exact shape T3-014 recorded — added to `review.py`:

```
TemplateContractTest  -> OK
SourceRuleTest        -> FAILED (failures=1)
```

The register says that class is closed by the test that is green. `rule_problem`
(`review.py:2529`) validates only that the named file exists, so `check` cannot tell the
difference and stays silent. A later round deletes `SourceRuleTest`'s threshold rule, the
class reopens, and the register still reports it held — with three of its instances already
marked `fixed` and never re-read.

T4-021 is worse in kind: it is **open**, it belongs to another block, this round neither
hunted nor fixed it, and it now carries a guard it was never given.

**Why it is a defect:** invariant 2 — a guard that can be holed with the suite green is not a
guard; and this is verbatim the open finding T4-020, "a class recorded as closed by a guard
that does not close it", to which this round added four instances. Rule 6 as well: the change
to four register records outside this block appears nowhere in the fix report, whose only
register line is the one about T2-011.

**Introduced by this round:** yes — `4da0304` / `3c3e7d7`.

**Confidence:** confirmed

**Root:** a class recorded as closed by a guard that does not close it

### R2-003 · low · the new markdown rule refuses correct CommonMark, and is the one rule in the file with no invented sample

**Location:** `tests/test_review.py:5480` (`test_ни_один_абзац_не_приклеен_к_предыдущему_пункту_списка`)

**What is wrong:** the rule flags *any* non-indented, non-quoted, non-list line following a
list item. A lazy continuation is a **paragraph** continuation; an ATX heading, a table or an
HTML block in that position is not one — it ends the list and renders exactly as written.
Rendered with a real parser:

```
- a bullet                    - a bullet
## A heading right after it   A paragraph right after it
→ <ul><li>a bullet</li></ul>  → <ul><li>a bullet
  <h2>A heading…</h2>              A paragraph right after it</li></ul>
```

The guard reports both, with the message "the markup makes it a continuation of that list
item" — untrue of the left-hand one.

**Failure scenario:** measured. A bullet followed directly by `## A heading right after it`
appended to `CONTRIBUTING.md`: `FAILED — CONTRIBUTING.md:99: ## A heading right after it`.
The document renders correctly; the suite is red, and the message tells the contributor the
markup does something it does not do.

Secondly, this rule is written **inline in the test body** and run only over the repository's
own files. `SourceRuleTest::test_у_каждого_правила_по_исходнику_есть_выдуманный_образец` —
the meta-rule that exists to stop exactly this, and that this round tripped once and obeyed
for `_scope_without_diff` — keys on `ast.parse`/`ast.walk` calls, so it does not see a rule
over file text. The false-positive half was therefore never fed anything, which is why it was
not noticed.

**Why it is a defect:** the kit's own rule 3 for this role — a narrowing fix needs a test that
what is still allowed still passes. The rule has a violation test and no innocent-sample test,
and the innocent sample it would have been given is the one it gets wrong. Against
`RepositoryContractTest` this is friction, not a green-on-wrong-state hole, hence low.

**Introduced by this round:** yes — `d258166`.

**Confidence:** confirmed

**Root:** class guard keyed on incidental syntax

## Checked and found correct

- **Every one of the seven closures reverts red.** The table above is the whole of it: eleven
  mutations, each on a mutant that parses, each producing the failure the report names — down
  to the detail that matters most, T2-016 going red on `root` in English, the half that stayed
  green before the fix.
- **T2-017's fix works live, not just in the test.** `prompt T2 --role fixreview --diff
  d33527c...HEAD`: 16 `diff --git` lines against 16 files in `git diff --stat`, one `````diff`
  fence for the pasted range, 194 KB of prompt against a stated 171 KB of diff. The manifest's
  own `{{DIFF}}` quotations survive as quotations outside the fence — which is the point.
- **Removing the `{{DIFF}}` exemption cannot strand a lead who forgets `--diff`.** That was my
  first suspicion of the change; `cmd_prompt` refuses earlier, by name:
  `the fix reviewer needs a diff: --diff <range>, for example main...HEAD`, exit 2.
- **`dup_of` and `reject_reason` are declared only in inline backtick spans, never in a fenced
  draft schema** — measured across all eight templates, both languages. The new guard accepts
  a span, so this is within the rule as written; and it is correct as written, because the
  spans (`verify.md:147`, `:143`) sit in the section that tells the verifier how to write the
  final file and are copyable as they stand. Not a finding, but it is the residue of T2-002,
  and a future tightening of the guard to "fenced schema only" would land on it.
- **`ANSWER_WINDOW = 300` is derived, not invented.** The comment's measurement reproduces:
  the farthest of the seven anchors is `SKILL.md` and the nearest `entry-point.ru.md` (my
  measurement reads 115 and 30 from the end of the anchor, the comment's 128 and 43 from the
  end of the matched answer — the same two files, the same distances).
- **The scenario count is real.** `unittest discover` collects **336**; `README.md`,
  `README.ru.md` and `AGENTS.md` all say 336. T4-024's class did not reopen.
- **`docs/review/README.md` is still level with `assets/entry-point.md`** — the fixer's own
  open observation. Diffed: identical apart from `{{PROJECT}}` and `{{CLI}}` substitution.
- **T2-019 correctly has no new class guard.** `roots` reports `2 × a gate whose test asserts
  its message, not its verdict — no guard, but few repeats`; the three-instance gate does not
  apply, and the fourteen further `assertIn`-over-stdout sites the report hands to the lead
  are each separately held by `GateRegistryTest` + `GateMutationTest`. That disclosure is
  accurate.
- **The `--scope` class guard reaches further than the four places fixed**: every string
  constant of the tool over 40 characters and every paragraph of every `.md` under
  `skills/finetooth/`. I grepped the rest of the repository for `--scope`: the two entry points
  and both CHANGELOGs mention the flag, but none of them claims it shrinks anything, so there
  is no fifth address. The report's own admission that the `SKILL.md` sentence is not held by
  the guard is correct and honestly stated.
- **The fence-toggle in the new markdown rule inverts inside a ````-wrapped example**, which
  could blind it. Measured across all 43 tracked markdown files against a fence-aware
  reimplementation: zero divergence, no file left with an odd fence count. Latent, not live —
  not a finding.

## Is another round needed

**Yes — for R2-001 and R2-002, both medium.** R2-001 makes `check` refuse an honest hunter
report on any block over the readability ceiling, in both languages, and was reproduced end to
end. R2-002 leaves the register asserting that a five-instance class — three of them already
closed in block T3, one still open in block T4 — is held by a test that is green on the very
defect the class names, and `rule_problem` cannot see it. Neither is something the lead fixes
by hand: R2-002 in particular cannot be repaired with a second `set-finding --rule`, because
`--rule` rewrites the whole root class, which is how it broke.

R2-003 is low and does not itself call for a round.

**Where the findings sit.** All three are inside the code this round changed — none is a defect
of the original subject that this round failed to fix. Round 1 of this block's fix review
reported seven findings, all about round 1's fixes; this round reports three, all about round
2's fixes. That is the shape rule 11 warns about, and one of the two mediums makes it sharper:
**R2-001 carries the same root as T2-018 of round 1** — "a document names a way out the
mechanism does not provide". Round 1 found the volume message naming `--scope`, which does not
shrink the diff; fixing it, round 2 rewrote the neighbouring volume message to name a section
the gate does not read. Same class, two rounds running, in text edited by the same hand under
the same pressure.

**The tripwire round 1 set has fired, at low severity.** Its report named the two classes to
watch for in round 2's own changes: R1-001's — a guard satisfied without exercising its
subject — and R1-002's — substituted text read as a template. R1-002's class did not come
back. R1-001's did: **R2-003 carries the root `class guard keyed on incidental syntax`
verbatim**, a new guard written under one form of the thing it judges, with the innocent half
never fed anything. And R2-002 is that class one level up — a guard recorded against a class
it cannot exercise. Round 1 predicted the shape and it appeared; what did not appear is the
severity it predicted it at, so this is a signal, not yet the stop condition.

That stop condition, as written, is not met — round 1's *top* findings were
`class guard keyed on incidental syntax` and `substituted text re-substituted as a template`,
while my top two are a different pair, so no single class leads two rounds running. My
recommendation is therefore: **run round 3, but scope it tightly** — the two mediums and nothing else, no new guards, no incidental
rewording of any message in `MSG`. If round 3's top finding is again inside round 3's own
changes and again in `a document names a way out the mechanism does not provide` or
`class guard keyed on incidental syntax`, the next move is a human's: the pattern would then
be that every message this block touches acquires a new mismatch with the gate it describes,
and what is missing is the gate → template table the block's acceptance criterion already asks
for — built once, by hand, over every message of `MSG` that instructs an agent, rather than
repaired message by message.

One thing for the lead regardless of the round: **R2-002 must be settled before `T2` is
closed**, because closing it freezes a register that misreports block T3's and T4's classes,
and T4-020 — still open — is the finding that says so.

