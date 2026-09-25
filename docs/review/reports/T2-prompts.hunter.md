# T2 — hunter report

## Coverage
- files read: 44 of 44
- examples/toy/.gitignore
- examples/toy/README.md
- examples/toy/docs/review/README.md
- examples/toy/docs/review/blocks.json
- examples/toy/docs/review/blocks/H1-access.md
- examples/toy/docs/review/blocks/V1-billing.md
- examples/toy/docs/review/coverage.tsv
- examples/toy/docs/review/findings.jsonl
- examples/toy/docs/review/findings.md
- examples/toy/docs/review/invariants.md
- examples/toy/docs/review/journal.md
- examples/toy/docs/review/reports/H1-access.hunter.md
- examples/toy/docs/review/reports/H1-access.verify.md
- examples/toy/docs/review/reports/H1-findings.jsonl
- examples/toy/docs/review/state.json
- examples/toy/src/auth/guard.ts
- examples/toy/src/auth/session.ts
- examples/toy/src/billing/quota.ts
- examples/toy/tests/guard.test.ts
- skills/finetooth/LICENSE
- skills/finetooth/SKILL.md
- skills/finetooth/assets/agent-banner.md
- skills/finetooth/assets/agent-banner.ru.md
- skills/finetooth/assets/blocks.example.json
- skills/finetooth/assets/entry-point.md
- skills/finetooth/assets/entry-point.ru.md
- skills/finetooth/assets/invariants.example.md
- skills/finetooth/assets/invariants.example.ru.md
- skills/finetooth/assets/journal.example.md
- skills/finetooth/assets/journal.example.ru.md
- skills/finetooth/assets/makefile-snippet.mk
- skills/finetooth/assets/manifest.example.md
- skills/finetooth/assets/manifest.example.ru.md
- skills/finetooth/assets/package-json-snippet.json
- skills/finetooth/references/fix.md
- skills/finetooth/references/fix.ru.md
- skills/finetooth/references/fixreview.md
- skills/finetooth/references/fixreview.ru.md
- skills/finetooth/references/hunter.md
- skills/finetooth/references/hunter.ru.md
- skills/finetooth/references/lessons.md
- skills/finetooth/references/lessons.ru.md
- skills/finetooth/references/verify.md
- skills/finetooth/references/verify.ru.md
- not read: none

Read in addition, as the block's context file: `skills/finetooth/scripts/review.py` (in full, in
four calls) and `tests/test_review.py` lines 3940–4080 for `GateRegistryTest.GATES`. The
repository root `LICENSE` was read to compare it with the skill's copy.

## Hypotheses

- T2.1 — checked: the gate → template table below was built from all 64 entries of `GateRegistryTest.GATES` against the four role templates in both languages; two holes found and filed (the rejection-reason wording in T2-001, the draft schema in T2-002), the rest are announced or belong to the lead session.
- T2.2 — checked: no template and no line of `SKILL.md` describes the round-6/7 verdict rule; what `hunter.md:101-109`, `hunter.ru.md:101-108`, `verify.md:54-59` and `verify.ru.md:55-59` say ("a verdict word alone in backticks is a quotation of the word, a whole verdict line in backticks is a verdict") is exactly what `unquote_verdicts` at `review.py:2603-2618` does — only a code span whose entire content is a vocabulary word is blanked.
- T2.3 — checked: the four role-template pairs were compared section by section — same rules, same numbering, same measured figures (1% / 55 turns in the hunter, 118 calls / 165 turns / 2.6× in the verifier, 329 turns in the fixer, third instance for the guard) and the same placeholders; the drift is not in the role templates but in the assets, where the Russian banner carries the English text (T2-007) and four Russian samples are pointed at by nothing (T2-008).
- T2.4 — checked: the placeholder table below was built from every `{{…}}` occurrence in `references/` and `assets/` against the `subs` dictionary at `review.py:1765-1795`; every placeholder in every template has a value, and every key of `subs` is used by at least one template, so there is no dead substitution and none that would refuse a prompt.
- T2.5 — checked: `blocks.example.json` passes `check_definition` (all six required fields on all four blocks, `proof` values inside the vocabulary, ids unique, no separators) and the two manifest samples expose the sections the parsers look for — but the example's block array violates the phase-order gate, which is filed as T2-006; `invariants.example.md` and its Russian copy carry no placeholder at all.
- T2.6 — checked: refuted by reading the code paths — `examples/toy/README.md` is owned by no block and matched by no exclusion, so `coverage_map` at `review.py:748-761` puts it in `unassigned` and gate `review.py:3129-3131` fails the state, while `examples/toy/src/billing/quota.ts:1` names a register id and trips `review_refs` at `review.py:1428-1448`; filed as T2-005 and T2-004. The tool could not be executed in this session, which is recorded under coverage limits.
- T2.7 — checked: every command and flag `SKILL.md` names exists in `review.py` and every file it links to is on disk, including `assets/run-role.sh` and `scripts/axes.py` with the `--journal` and `--reply` flags it promises; the drift runs the other way — `--round` for the `fix` role is real and undocumented (T2-003), and `refs`, `roots`, `hypotheses` and `version` are never named, of which only `roots` is reachable from no message at all.
- T2.8 — checked: `name: finetooth` equals the directory, the description says what it does and when to use it, the body is 171 lines against the 500 ceiling, `metadata.version` "0.7.0" equals `VERSION` at `review.py:60`, every link goes one level deep to a file that exists, and `skills/finetooth/LICENSE` carries the same MIT text and both copyright lines as the root `LICENSE`; the `skills-ref` validator itself was not run in this session and is listed under coverage limits.
- T2.9 — checked: both lessons files were read against the method as the tool now implements it, and the lessons about the guard at the third instance, the claim and scenario caps, the named-file rule, the fingerprints and the fix gate all match live gates; one contradiction found and filed as T2-011 — lesson 13 requires every deferred finding to be fixed or rejected before the review ends, while `render_summary` at `review.py:1327-1329` and the closing section of `SKILL.md` treat a deferred finding with a reason as an accepted risk that ships in the summary.
- T2.10 — checked: a diff containing braces is safe, because `cmd_prompt` runs the placeholder pass first and pastes the diff afterwards (`review.py:1801`, `1806`, `1809-1810`), and `--scope` does not filter the diff but only adds a sentence; what is missing is any statement of size — `diff_text` at `review.py:1714-1724` pastes a range of any length while the hunter's file list gets `volume_note`, and neither `fixreview.md` nor `fixreview.ru.md` mentions `--scope` or what to do with a diff that does not fit. Filed as T2-010.

## Tree freshness

`git fetch` was run and `git log HEAD..origin/dev --oneline` is empty; the working tree is
clean and the branch `review/t2` is level with the server. Every finding below was read on
that tree.

## Coverage limits

What I deliberately did not do, and what I could not do:

- **The tool was never executed.** Every attempt to run `python3`, `bash` or a script in this
  session was refused by the permission layer ("requires approval"). So T2-004, T2-005 and
  T2-006 rest on reading the code path — the set arithmetic of `coverage_map`, the grep of
  `review_refs`, the phase loop of `cmd_check` — and not on a run. All three are mechanical
  and I state them as confirmed, but the verifier must reproduce them by execution, which is
  precisely its role; a hunter's reading is not a substitute.
- **`skills-ref validate skills/finetooth` was not run** for the same reason, so the part of
  the Agent Skills contract that only the validator checks (frontmatter schema, the
  non-standard prose `license:` value) is taken on faith.
- **The blob fingerprints of the toy were not recomputed.** `examples/toy/docs/review/state.json`
  carries `reviewed_sha`, `refs_sha`, `hypotheses_sha` and the findings carry `code_sha`; I
  assumed they match the shipped files, because the files have not changed since the example
  was generated. If one of them is stale, the toy has a second reason to go red that I did
  not catch.
- **`assets/run-role.sh`, `assets/guard-grep.sh` and `scripts/axes.py` were not read in full.**
  They belong to block T1 and are not in my list; I read only their usage banners, and only to
  check that what `SKILL.md` promises about them exists. A defect inside them is not mine.
- **`README.md` and `README.ru.md` of the repository were not read**, although they document
  the same assets. They are T4's. A divergence between `README.md` and `SKILL.md` would be
  found there, not here, and I did not look for one.
- **Translation quality was not judged.** I compared the Russian and English templates for
  rules, numbers and placeholders — not for style. A meaning shift subtle enough to survive a
  structural comparison would have been missed.
- **The verdict and coverage regexes were read, not fuzzed.** I checked that the templates
  describe what the parsers do; I did not construct adversarial reports to find a form of
  words the gates mis-read. That is a measured block's work, not a reading one's.
- **Added by the lead after the block closed (2026-09-25, direction 18, branch `feat/sarif`),
  not read by this hunter or by any agent of this review:**
  `skills/finetooth/assets/github-actions-snippet.yml` and
  `skills/finetooth/assets/gitlab-ci-snippet.yml` — the CI jobs for `check` and the SARIF
  upload. They entered T2 through `skills/finetooth/assets/*.yml` so that the coverage map has
  no unowned file; the review of the kit has closed, and they are covered by the suite
  (`test_действия_ci_закреплены_коммитом`), not by a reading.

## Findings

### T2-001 · medium · The verifier is told to write the rejection reason in `claim`, and `check` refuses the claim it asks for
**Location:** `skills/finetooth/references/verify.md:123` (and `skills/finetooth/references/verify.ru.md:123`)
**What is wrong:** the template's only instruction for a rejected finding is to put the reason
in `claim`. The gate at `review.py:3078-3090` accepts that reason only when the claim *begins*
with one of `отвергнут|отклонен|отклонён|не подтверд|rejected|not confirmed` (`re.match`, so it
is anchored), or when a separate `reject_reason` field is present — and no template mentions
either the anchoring or the field.
**Failure scenario:** the verifier of a block rejects a hunter finding and writes the row
exactly as the template instructs: `{"...","confidence":"rejected","status":"rejected","claim":"No defect: the route is wrapped in RequirePermission, so the scenario is unreachable", ...}`.
`import <ID>` accepts it; `check` then prints `finding <ID>-003: rejected, but the reject reason
is not recorded`. The register is red on a report written exactly by the instructions, and the
only way out is to edit a finished findings file by hand or re-run `set-finding` — a command
the verifier does not have.
**Why it is a defect:** invariant 9 — a gate that demands something the role template does not
tell the agent to produce turns an honest report red. The manifest names this shape first.
**Confidence:** confirmed
**Root:** check demands what no role template announces

### T2-002 · medium · The draft-findings schema in the templates is narrower than the register, and the three-instance guard gate can never fire
**Location:** `skills/finetooth/references/hunter.md:155` (and `hunter.ru.md:153`, `verify.md:118-126`, `verify.ru.md:118-126`)
**What is wrong:** the JSON line the templates give as "exactly this format" carries `block,
severity, confidence, status, file, line, claim, scenario, invariant`. It has no `root` and no
`dup_of`. `roots_of` at `review.py:2374-2385` groups findings by `root`, the gate at
`review.py:3305-3319` demands a guard from the third instance of a root, `cmd_roots` reports
roots, and `set_one_finding` at `review.py:2181-2185` propagates `--rule` to every finding of
the same root. All of them read a field no agent is ever told to write. The hunter template
asks for **Root:** in the *markdown* report (`hunter.md:138-141`) and then drops it on the way
to the file the tool actually reads.
**Failure scenario:** a hunter finds five instances of one defect class in a block, names the
class under **Root:** in each finding of the report, and writes the five JSON lines in the
prescribed format. `import <ID>` stores them without a `root`. `check` never reaches the
three-instance rule, `review roots` prints "no roots recorded — the `root` field of the
findings is not filled in", and the class is closed by five separate fixes — exactly the
outcome lesson 25 and the fixer's guard section exist to prevent. The same hole makes a
`duplicate` unusable: `verify.md:70-76` tells the verifier to mark a duplicate with a
reference to the primary finding, the schema gives it no field for it, and `check` answers
`marked duplicate, but not of what exactly`.
**Why it is a defect:** invariant 1 — a gate that cannot go red on the state it exists to
catch is a gate that is green on a false state; and invariant 9, in the direction of a
mechanism the prompts never feed.
**Confidence:** confirmed
**Root:** check demands what no role template announces

### T2-003 · medium · `SKILL.md` documents `--round` only for the fix reviewer, so a second fix round overwrites the first round's report and the reviewer is sent to a file that does not exist
**Location:** `skills/finetooth/SKILL.md:92`
**What is wrong:** step 7 gives the fixer's command as `review prompt <ID> --role fix`, with no
round. `report_path` at `review.py:1703-1711` names the fixer's report `<ID>-<slug>.fix.md` for
round 1 and `<ID>-<slug>.fix-<N>.md` from round 2 — but only when `--round N` is passed. Step 8
documents `--round N` for `fixreview` alone, and `{{FIX_REPORT}}` there is
`report_path(b, "fix", args.round)` (`review.py:1782`). Neither `fix.md` nor `fix.ru.md`
contains a round marker, so nothing else signals the round to the lead.
**Failure scenario:** round 1 completes; the fix reviewer files medium findings; the lead
starts round 2 exactly as `SKILL.md` step 7 says, `review prompt <ID> --role fix`. The
round-2 fixer is told to write `docs/review/reports/<ID>-<slug>.fix.md` and overwrites round 1's
fix report — the record of what was reproduced, reverted and run in round 1 is gone from the
tree. The lead then runs `review prompt <ID> --role fixreview --diff … --round 2`, and the
prompt opens with "The fixer has closed the block's findings and written the report
`docs/review/reports/<ID>-<slug>.fix-2.md`" — a file nobody was told to write.
**Why it is a defect:** an artefact of the review is destroyed silently and a prompt points at
nothing, because the flag that prevents both is real and undocumented.
**Confidence:** confirmed

### T2-004 · medium · The shipped example names a finding id in code, which the kit forbids and its own `refs` gate catches
**Location:** `examples/toy/src/billing/quota.ts:1`
**What is wrong:** the comment reads `// Monthly quota: counts attempts, not successes — see
finding H1-001.` Rule 5 of `fix.md` and `fix.ru.md`, the "Fixing rules" of `entry-point.md` and
`entry-point.ru.md` and `SKILL.md` all forbid exactly this: finding ids must not get into
comments, because they die with `docs/review/`. The cited id is also the wrong one — `H1-001`
is "Empty role parses into a user session" in `src/auth/session.ts`, nothing to do with quotas.
**Failure scenario:** copy `examples/toy` into a fresh repository as its README instructs and
run `review refs`: `review_refs` at `review.py:1428-1448` greps the tracked tree outside
`docs/review/` for every register id, matches `H1-001` in `quota.ts` (the trailing period is a
word boundary for both `git grep -w -F` and the `(?<![\w-])…(?![\w-])` re-check), prints the
hit and exits 1. `check` reports the same as a warning. The one example the kit ships of a
correct review state demonstrates the practice it forbids, and an agent shown the toy as a
model learns that citing finding ids in comments is normal.
**Why it is a defect:** the example contradicts a rule the tool enforces, and the reference
example of a green review is not green under `refs`.
**Confidence:** confirmed

### T2-005 · medium · `examples/toy` does not pass `check`: its own README belongs to no block
**Location:** `examples/toy/docs/review/blocks.json:12`
**What is wrong:** the toy's exclusions cover `docs/review/**` and `.gitignore`. They do not
cover `README.md`, and neither block's `paths` reaches it (`H1`: `src/auth`,
`tests/guard.test.ts`; `V1`: `src/billing`). `coverage_map` at `review.py:748-761` therefore
puts `README.md` in `unassigned`, and the gate at `review.py:3129-3131` turns the state red.
`examples/toy/docs/review/coverage.tsv` lists four files and does not mention it either.
**Failure scenario:** follow `examples/toy/README.md:21-24` — "copy this directory into a fresh
git repository, commit, and run `python3 <skill>/scripts/review.py check`: it passes". The copy
contains `README.md` (the file giving the instruction), `.gitignore`, `docs/review/`, `src/`
and `tests/`. `check` prints `1 files belong to no block — run … coverage` and exits 1, and
`coverage` exits 1 with the same file. A first-time user following the example's own
instructions sees the gate refuse the state the example exists to demonstrate, and cannot tell
a broken example from a broken tool.
**Why it is a defect:** the example documents a passing state that does not pass; that the
author excluded `.gitignore` with the reason "not code" and forgot `README.md` shows the toy
root is the intended repository, not an accident of my reading.
**Confidence:** confirmed

### T2-006 · low · The sample block definition violates the phase-order gate it is offered as a model for
**Location:** `skills/finetooth/assets/blocks.example.json:115`
**What is wrong:** the array runs `H1` (phase 1), `V1a` (phase 2), `H13` (phase 1), `E1`
(phase 3). The gate at `review.py:2881-2889` refuses a phase that decreases along the array,
because array order is execution order. This file is what `setup` prints in step 2 and what
three `die()` messages of `check_definition` name as "the example".
**Failure scenario:** a user sets up a review, opens the example the refusal points them at,
keeps its arrangement (cross-cutting blocks numbered H, vertical ones V, the late H-block after
the V-block), fills in their own paths and runs `check`: `H13: phase 1 comes after phase 2 —
the blocks array is ordered by phase, because that is the execution order`. The sample teaches
the arrangement the gate rejects.
**Why it is a defect:** a sample that the tool's own refusals point at must satisfy the tool's
own gates.
**Confidence:** confirmed

### T2-007 · low · The Russian banner asset carries the English banner
**Location:** `skills/finetooth/assets/agent-banner.ru.md:11`
**What is wrong:** the file's explanation (lines 1–8) is Russian; the banner itself, lines
11–21 — the part that is meant to be pasted — is the English text of `agent-banner.md`, word
for word. The `.ru.md` suffix exists for exactly one purpose, and this file does not serve it.
**Failure scenario:** a project runs `review setup --project X --lang ru`, works through the
setup checklist to step 5 ("The banner in the root instructions file"), opens the Russian
asset and pastes lines 11–21 into its Russian `CLAUDE.md`. The banner that is supposed to stop
a new session from starting a parallel review arrives in the wrong language, inside a document
whose language the team chose deliberately.
**Why it is a defect:** the bilingual contract of the invariants — a string that exists in one
language and not the other is a defect.
**Confidence:** confirmed
**Root:** the Russian half of the bilingual assets is unwired

### T2-008 · low · `setup --lang ru` sends a Russian project to the English samples, and four Russian samples are referenced by nothing
**Location:** `skills/finetooth/scripts/review.py:3509`
**What is wrong:** `cmd_setup` selects the entry point by language (`review.py:3486`) and then
hardcodes the English names in the five-step checklist it prints: `invariants.example.md`,
`blocks.example.json`, `manifest.example.md`, `agent-banner.md` (lines 3509, 3511, 3513, 3516).
A grep over the whole repository finds no reference anywhere to `invariants.example.ru.md`,
`manifest.example.ru.md`, `journal.example.ru.md` or `agent-banner.ru.md` — they ship and are
pointed at by nothing.
**Failure scenario:** `review setup --project X --lang ru` writes a Russian `blocks.json`, a
Russian invariants skeleton and a Russian `docs/review/README.md`, then instructs the user to
model their invariants on the English `invariants.example.md` and their first manifest on the
English `manifest.example.md`. The Russian samples that exist for exactly this moment are never
named, and the user has no way to discover them from the tool.
**Why it is a defect:** the same bilingual contract; the entry point in the same function
proves the selection was intended and simply not carried to the other four.
**Confidence:** confirmed
**Root:** the Russian half of the bilingual assets is unwired

### T2-009 · low · The entry point copied into every project is behind the tool it describes
**Location:** `skills/finetooth/assets/entry-point.md:46` (and `entry-point.ru.md:46`, and their copy at `examples/toy/docs/review/README.md:46`)
**What is wrong:** `setup` writes this file as `docs/review/README.md` and it calls itself the
first file an agent reads. It still describes step 8 as "Diff review — by those who did not
write it"; it never names the `fixreview` role, never says the report must be
`<ID>-<slug>.fixreview-<N>.md`, never mentions the fix gate on `set-status … running`, never
mentions `import --append` or why the plain import refuses, and its `prompts/` row (line 27)
lists `hunter.md`, `verify.md`, `fix.md` while `cmd_prompt` accepts an override for `fixreview`
too. All of this is in `SKILL.md`, which is not installed into the project.
**Failure scenario:** a lead session that knows nothing does what the file says — one command
and the full picture. It runs the diff review, writes the report under a name of its own, then
`set-status <ID> closed`, and `check` answers `closed with fixed findings, but there is no fix
reviewer report`. Earlier, moving the next block to `running`, it meets a fix-gate refusal the
entry point never warned it about. Both refusals name their fix, so the work is recoverable —
but the document that promises the full picture does not hold it.
**Why it is a defect:** invariant 9 applied to the scaffold: the mechanisms changed and the
document the project actually reads did not.
**Confidence:** confirmed

### T2-010 · low · The fix reviewer is handed a diff of any size with no statement of its size and no mention of `--scope`
**Location:** `skills/finetooth/references/fixreview.md:71` (and `fixreview.ru.md:70`)
**What is wrong:** the hunter's prompt carries `{{VOLUME}}` — `volume_note` at
`review.py:1643-1677` states the line count, the token order of magnitude, the readability
ceiling and where the budget line runs, on the reasoning that the budget must stand in the
assignment and not in the lead's head. The fix reviewer's prompt has no equivalent:
`diff_text` at `review.py:1714-1724` prepends `--stat` and pastes the whole range, and rule 1
says "the diff is pasted below in full — read it" with no condition. `--scope` exists and adds
only a sentence when the lead passes it; the template never tells the agent that it exists or
what to ask for.
**Failure scenario:** the kit's own T1 round-1 diff was 193 KB. A lead runs
`prompt <ID> --role fixreview --diff main...HEAD` on a range of that size or larger; the agent
receives an unconditional "read it in full" and no budget statement, reads what fits, and
reports on the whole diff — the same failure lesson 3 records for the file list, which is why
the file list got a budget note and the diff did not.
**Why it is a defect:** the assignment states a requirement it gives the agent no way to
measure, and the remedy (`--scope`, or a narrower range) is named in `SKILL.md` for the lead
and nowhere for the agent.
**Confidence:** plausible

### T2-011 · low · Lesson 13 requires every deferred finding to be resolved before the end; the tool and `SKILL.md` treat a deferred finding as an accepted risk that ships
**Location:** `skills/finetooth/references/lessons.md:58` (and `lessons.ru.md:54`)
**What is wrong:** the lesson reads "`deferred` requires a reason; before the review ends each
one is either fixed or rejected with a reason." But `render_summary` at `review.py:1327-1329`
writes deferred findings under the heading "Accepted risks (deferred with a reason)", the
`SKILL.md` completion condition (line 143) is "All blocks closed, no open findings, every
rejected one has a reason" — deferred ones are not mentioned — and `check` demands only the
reason, never the resolution.
**Failure scenario:** a lead reads the lessons before the first block, as `SKILL.md:161-162`
instructs, and holds the review open at the end to resolve a dozen deferred findings that the
tool and the summary consider settled; or, reading the two documents in the other order,
believes the summary's "accepted risks" section is a defect. Two documents of the kit give
opposite answers to "is the review finished".
**Why it is a defect:** a lesson that contradicts a live rule is worse than a missing lesson —
lesson 36 in the same file is about exactly that.
**Confidence:** confirmed

### T2-012 · low · The Makefile snippet defines no target that the `cli` value `SKILL.md` offers would call
**Location:** `skills/finetooth/assets/makefile-snippet.mk:17`
**What is wrong:** `SKILL.md:28-30` offers `make review` as an example of a project's own way
of calling the tool, written into the `cli` field of `blocks.json`; `project_cli` at
`review.py:81-86` then builds every hint from it. The snippet defines `review-status`,
`review-check` and so on, and no generic `review` target that takes a subcommand. The
`package.json` snippet does define one (`"review": "python3 …"`), which is why
`npm run review --` works.
**Failure scenario:** a project pastes `makefile-snippet.mk` into its Makefile and, following
`SKILL.md`, sets `"cli": "make review"`. Every refusal and hint the tool prints from then on —
`run … init`, `… coverage`, `… restamp H1`, `… set-finding <id> fixed --commit <sha>` — becomes
`make review init`, `make review coverage`, and each answers `No rule to make target 'review'`.
The invariant that a refusal names the command that fixes it is satisfied in form and empty in
practice.
**Why it is a defect:** two shipped artefacts of the kit disagree about what `cli` may contain,
and the disagreement surfaces as unrunnable hints.
**Confidence:** plausible

## Acceptance tables

### 1. Gate → template

All 64 entries of `GateRegistryTest.GATES`, in registry order. "lead" means the artefact is
the lead session's bookkeeping, not an agent's report, so no role template can announce it;
those cells are argued in the last column rather than left empty.

| gate (message skeleton) | artefact produced by | English template | Russian template |
|---|---|---|---|
| `: no record in state.json` | lead (`init`) | — lead bookkeeping; `SKILL.md:37` | — |
| `: present in state.json but missing from blocks` | lead | — lead bookkeeping | — |
| `: status '' is not in the vocabulary` | lead (`set-status`) | — lead bookkeeping | — |
| `: phase comes after phase` | lead (`blocks.json`) | — lead; `SKILL.md:51-53`; sample violates it, see T2-006 | — |
| `: blocked without a note` | lead | — lead; refusal names the fix | — |
| `: no manifest` | lead | `SKILL.md:73` | — |
| `: manifest is empty or nearly empty` | lead | `SKILL.md:73-76` | — |
| `: status , but there is no verifier report` | lead + verify | `SKILL.md:83`, `verify.md:102` | `verify.ru.md:102` |
| `verify_report_problem` (substance, finding verdict, coverage verdict) | verify | `verify.md:30-31`, `54-59`, `114-115` | `verify.ru.md:30-32`, `55-59`, `114-115` |
| `: state.json declares report , which is not on` | lead | — lead bookkeeping | — |
| `: status , but there is no hunter report` | hunter | `hunter.md:73` | `hunter.ru.md:74` |
| `: stuck in running without a timestamp` | lead | — lead bookkeeping | — |
| `: timestamp '' cannot be parsed` | lead | — lead bookkeeping | — |
| `: stuck in running for h` | lead | — lead bookkeeping | — |
| `finding : duplicate id` | hunter + verify | `hunter.md:151` (no `id` field — the tool assigns it) | `hunter.ru.md:149` |
| `finding : field is empty` | hunter + verify | `hunter.md:155` | `hunter.ru.md:153` |
| `finding : refers to nonexistent block` | hunter | `hunter.md:155` | `hunter.ru.md:153` |
| `finding : severity= is not in the vocabulary` | hunter + verify | `hunter.md:158-162`, `fixreview.md:104-107` | `hunter.ru.md:156-160`, `fixreview.ru.md:103-106` |
| `finding : confidence= is not in the vocabulary` | hunter + verify | `hunter.md:137,155`, `verify.md:121-124` | `hunter.ru.md:135,153`, `verify.ru.md:121-124` |
| `finding : status= is not in the vocabulary` | hunter + verify | `hunter.md:155`, `verify.md:123` | `hunter.ru.md:153`, `verify.ru.md:123` |
| `finding : file is not in the repository` | hunter | `hunter.md:155` | `hunter.ru.md:153` |
| `finding : deferred without a reason` | lead (`set-finding`) | `SKILL.md:95` | — |
| `finding : an external fix is written as` | lead | — lead; refusal names the form | — |
| `finding : commit is not in the repository` | lead | `SKILL.md:93`, `fix.md:91` | `fix.ru.md:92` |
| `finding : commit does not touch` | lead | `fix.md:91`, refusal names `--fixed-in` | `fix.ru.md:92` |
| `finding : marked fixed, but no fix commit` | lead | `SKILL.md:93`, `fix.md:91` | `fix.ru.md:92` |
| `finding : marked duplicate, but not of what` | verify | **empty** — see T2-002 (`verify.md:70-76` names the practice, not the field) | **empty** — `verify.ru.md:71-77` |
| `dup_problem` (duplicate of a dead or missing record) | verify | `verify.md:74-76` (point at the primary) | `verify.ru.md:75-77` |
| `finding : rejected by the verifier, but still open` | verify | `verify.md:123` | `verify.ru.md:123` |
| `finding : status rejected but confidence` | verify | `verify.md:123` | `verify.ru.md:123` |
| `finding : no code fingerprint` | lead (`backfill`) | `SKILL.md:136-137` | — |
| `finding : code in changed since import` | lead (`restamp`) | `SKILL.md:136-137` | — |
| `finding : line= is not a number` | hunter + verify | `hunter.md:155` (`"line":123`) | `hunter.ru.md:153` |
| `finding : line is cited, but has` | hunter | `hunter.md:133` | `hunter.ru.md:131` |
| `finding : rejected, but the reject reason is not` | verify | **empty** — see T2-001 | **empty** — see T2-001 |
| `finding : claim is characters against a limit` | verify | `verify.md:128-134` | `verify.ru.md:127-134` |
| `finding : scenario is characters against a limit` | verify | `verify.md:132-133` | `verify.ru.md:132-133` |
| `findings.md diverged from findings.jsonl` | lead | `SKILL.md:89` | — |
| `: pattern `` matches only untracked files` | lead | — lead; refusal names `git add` | — |
| `: pattern `` matches no file` | lead | — lead; `SKILL.md:59-62` | — |
| `files belong to no block` | lead | `SKILL.md:59-62`; the toy sample fails it, see T2-005 | — |
| `coverage.tsv is stale` | lead | `SKILL.md:89` | — |
| `: the manifest has no hypotheses` | lead | `SKILL.md:74` | — |
| `: gives hypothesis different verdicts` | hunter + verify | `hunter.md:91` | `hunter.ru.md:91` |
| `: of hypotheses without a verdict` | hunter + verify | `hunter.md:89-109` | `hunter.ru.md:89-108`, `verify.ru.md:50-59` |
| `: block in status without a fingerprint` | lead | `SKILL.md:136-137` | — |
| `: block files changed after the review` | lead (`restamp`) | `SKILL.md:136-137` | — |
| `: no context fingerprint (ref_paths)` (warning) | lead | `SKILL.md:136-137` | — |
| `: context files (ref_paths) changed` (warning) | lead | `SKILL.md:136-137` | — |
| `: no hypotheses fingerprint` | lead | `SKILL.md:136-137` | — |
| `: manifest hypotheses changed after verification` | lead | `SKILL.md:136-137` | — |
| `: of block files are not named by full path` | hunter | `hunter.md:82-87` | `hunter.ru.md:83-87` |
| `: closed with fixed findings, but there is no fix review` | lead + fixreview | `SKILL.md:101-111`; absent from the entry point, see T2-009 | — |
| `: the hunter report has no 'Coverage limits' section` | hunter | `hunter.md:124-129` | `hunter.ru.md:123-127` |
| `: the 'Coverage limits' section is empty` | hunter | `hunter.md:125` | `hunter.ru.md:124` |
| `rule_problem` (guard at a path that does not exist) | fix | `fix.md:93-95` | `fix.ru.md:93-95` |
| `root '': instances () and no guard` | fix | `fix.md:97-99`, `hunter.md:138-141` — announced, but the field never reaches the register, see T2-002 | `fix.ru.md:97-99`, `hunter.ru.md:136-139` |
| `the freshness gate is not running` (warning) | hunter + verify | `hunter.md:111-122` | `hunter.ru.md:110-121` |
| `the tree is behind by days` | hunter + verify | `hunter.md:111-122`, `verify.md:61` | `hunter.ru.md:110-121`, `verify.ru.md:61` |
| `: proof '' is not in the vocabulary` | lead | `SKILL.md:55-57` | — |
| `: files, lines — cannot be read in one session` | lead | `SKILL.md:53-55` | — |
| `open finding(s) older than days` (warning) | lead | `SKILL.md:135` | — |
| `reference(s) to findings in the code` (warning) | fix | `fix.md:25-27`; the toy sample violates it, see T2-004 | `fix.ru.md:25-27` |

Two cells argued rather than filed: the `claim` and `scenario` caps are announced in the
verifier's template and not in the hunter's, although `import` enforces them on a hunter draft
too (`review.py:1888-1891`). I did not file it, because the documented flow imports after
verification (`SKILL.md:87-89`), the hunter's schema says "in one line", and the refusal names
the fix. A verifier may disagree.

### 2. Placeholder map

Every `{{…}}` occurrence in `references/` and `assets/`, against the `subs` dictionary at
`review.py:1765-1795`. No placeholder is unfilled and no substitution is unused.

| placeholder | filled by `cmd_prompt` | templates that use it |
|---|---|---|
| `{{PROJECT}}` | yes, `defn["project"]` or the root name | hunter, verify, fix, fixreview (both languages) |
| `{{BLOCK_ID}}` | yes | hunter, verify, fix, fixreview (both) |
| `{{BLOCK_TITLE}}` | yes | hunter, verify, fix, fixreview (both) |
| `{{BLOCK_ROLE}}` | yes | hunter, verify (both) |
| `{{BLOCK_GOAL}}` | yes | hunter (both) |
| `{{PROOF_RULE}}` | yes, `proof_rule(proof, role, n_files)` | hunter, verify (both) |
| `{{FILES_HEADING}}` | yes, `files_heading` | hunter, verify (both) |
| `{{FILES}}` | yes | hunter, verify (both) |
| `{{FILE_COUNT}}` | yes | hunter (both) |
| `{{VOLUME}}` | yes, `volume_note` | hunter (both) |
| `{{REF_FILES}}` | yes, `render_refs` | hunter (both) |
| `{{RECORDED}}` | yes, `render_recorded_for` | hunter, verify (both) |
| `{{NEXT_ID}}` | yes, `next_finding_id` | hunter (both) |
| `{{INVARIANTS}}` | yes, demoted | hunter, verify, fix, fixreview (both) |
| `{{MANIFEST}}` | yes, demoted | hunter, verify, fix, fixreview (both) |
| `{{REPORT_PATH}}` | yes, `report_path(role, round, scope)` | hunter, verify, fix, fixreview (both) |
| `{{HUNTER_REPORT}}` | yes | verify (both) |
| `{{FINDINGS}}` | yes, `render_findings_for` | fix (both) |
| `{{GATES}}` | yes, from `defn["gates"]` | fix (both) |
| `{{FIX_REPORT}}` | yes, `report_path(b,"fix",round)` | fixreview (both) — see T2-003 |
| `{{ROUND}}` | yes | fixreview (both) |
| `{{SCOPE_LINE}}` | yes, empty string without `--scope` | fixreview (both) |
| `{{DIFF_RANGE}}` | yes | fixreview (both) |
| `{{DIFF}}` | yes, after the placeholder pass, fixreview only | fixreview (both) |
| `{{CLI}}` | yes, by `cmd_setup` (`review.py:3488`), not by `cmd_prompt` | entry-point, entry-point.ru |

`{{DIFF}}` is exempted from the "no substitution left" check for every role
(`review.py:1801`), not only for `fixreview`, so a `{{DIFF}}` written into a hunter, verify or
fix template would reach the agent as literal text. No template does today, so it is noted
here and not filed.

## Checked and found correct

- **The verdict-quotation rules of the templates match the parser exactly.** `unquote_verdicts`
  blanks a code span only when its entire content is a vocabulary word, and keeps a span
  carrying a whole clause; both hunter templates and both verifier templates say precisely
  that, including the nested-sub-item exemption that `quoted_lines` implements via the list
  content column. Nothing left over from the reverted parser.
- **The "Coverage limits" placeholder trap is closed on both sides.** `LIMITS_PLACEHOLDER`
  matches the hunter template's own sentence "Mandatory section, even if it is short" and its
  Russian twin, so a report that copies the heading and the instruction and adds nothing is
  read as empty. The two strings really are the ones in the templates; I compared them
  character by character.
- **The plain import refusing after a verifier rewrite is by design, not a hole.** The verifier
  is told not to put recorded findings into the final file, which guarantees the plain import
  refuses on a block that already carries records — but the refusal names `import --append` and
  `SKILL.md:87-89` documents the same path. The templates and the tool agree.
- **`--scope` deliberately does not cut the diff.** It only adds a sentence, and the sentence
  says so: read the rest for context, file findings for your half. I checked for a missing
  filter before concluding it was intended.
- **`report_path` and the check globs agree.** The fix reviewer writes
  `<ID>-<slug>.fixreview-<N>[-scope].md` and the closing gate globs
  `<ID>-<slug>.fixreview-*.md`; a scoped report satisfies it.
- **The manifest and invariants samples parse.** `ACCEPTANCE_HEADING` matches both "Acceptance
  criterion" and "Критерий приёмки", `HYPOTHESIS_HEADING` matches both "Hypotheses" and
  "Гипотезы", and the sample manifests are an order of magnitude above `MANIFEST_MIN_CHARS`.
- **The skill's LICENSE equals the root one** — same MIT text, same two copyright lines,
  same length.
- **`kit_version` in the toy is "0.6.0" against `VERSION` "0.7.0"**, which looked like a
  finding until I checked: no code path reads `kit_version`; `setup` writes it once and nothing
  compares it. Stale, but it cannot cause a wrong outcome, so it is not filed.
