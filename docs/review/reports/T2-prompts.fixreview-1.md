# T2 — fix review, round 1

## What was checked and how

The diff was read in full. Its stated volume was 464 KB / 4091 lines; the prompt actually
delivered 1410 KB / 12553 lines, because the same diff is pasted three times — that is
finding **R1-002** and it was found by reading the assignment I was given.

The range `f1a44a0..HEAD` carries **two** fix series: T2's and T4's (the branches were
merged before this review, commits `82ade22` and `8b7129c`). Everything below is T2's —
the 24 non-register files touched by `2f95090..858a45e`. Where a T4 artefact bears on a T2
finding it is named as T4's and left to T4's own fix review.

**Run, not read:**

- Full suite from the repository root: `Ran 296 tests in 311.894s — OK`.
- Every T2 guard reverted to `f1a44a0` and re-run. Results, one line each:

| reverted | guard | verdict |
|---|---|---|
| the four **English** role templates | `TemplateContractTest` | RED on `dup_of`, `reject_reason`, `defer_reason` — **GREEN on `root`** (R1-001) |
| all eight role templates | `TemplateContractTest` | RED, 7 subtests (the failure count the fixer reports is right) |
| every JSON schema deleted from all eight templates | `TemplateContractTest` | **GREEN on all 13 agent fields, both languages** (R1-001) |
| `quota.ts` only | `ShippedSampleTest` | RED |
| the toy's `README.md` exclusion only | `ShippedSampleTest` | RED |
| the toy's `cli` field only | `ShippedSampleTest` | RED |
| `blocks.example.json` only | `ShippedSampleTest` | RED — `H13: phase 1 comes after phase 2`, exit 1 |
| both banners | `BilingualAssetTest` + `SetupLanguageTest` | RED, 4 subtests |
| `review.py` (asset/fill/setup) | `SetupLanguageTest` | RED, 5 subtests |
| `SKILL.md` + both entry points + `fix*.md` | `DocumentedSurfaceTest` | RED, 14 subtests |
| `SKILL.md` + snippet + tool | `CliContractTest` | RED, 3 |
| both `lessons*.md` | `DeferredIsAnAcceptedRiskTest` | RED, 2 |
| both `fixreview*.md` (with and without the tool) | the diff-volume test | RED |
| the deferral gate turned `problems` → `warnings` | the round's own negative test | **GREEN** (R1-004) |
| the refusal tail + `SKILL.md`'s completion sentence | whole suite | **GREEN**, 296 tests (R1-006) |

Each revert was checked to leave a buildable tree (the templates are text; the two
`review.py` reverts ran and printed their checklists in full). `git status` was clean after
every one.

**Reproduced live, not from the code:**

- `setup --lang ru --project Проект` in a throwaway Go repository with no Makefile: the
  checklist names `invariants.example.ru.md`, `manifest.example.ru.md`,
  `journal.example.ru.md`, `agent-banner.ru.md` (and the language-neutral
  `blocks.example.json`); the banner is printed ready to paste, in Russian, carrying
  `python3 ~/Projects/finetooth/skills/finetooth/scripts/review.py status` and no `make`
  anywhere; no `{{…}}` survives. The English run mirrors it with `npm run review -- status`.
  T2-007, T2-008 and T2-015 are genuinely closed.
- `prompt T2 --role fixreview` with and without `--scope` — measured byte for byte (R1-003).
- `prompt T1 --role hunter|verify|fix` — which roles actually receive a reading budget
  (R1-007).
- `prompt T2 --role fixreview --diff no-such-branch...HEAD` → exit 2 naming git's own error;
  `--diff HEAD..HEAD` → exit 2, "the fix reviewer has nothing to read". Moving `diff_text`
  ahead of the placeholder check did not open a silent-empty-diff hole.
- The kit on itself: `check` is clean of every T2 line (what is red is T1/T3/T4 findings and
  the four blocks' fingerprints — the lead's call); `refs` → nothing named outside
  `docs/review/`; `coverage` → 71/71; `roots T2` matches the fixer's table exactly.
- `docs/review/README.md` recomputed from the corrected asset with this project's `cli`:
  byte-identical to what is committed. The forward-port is exact.

**Not done, plainly:** `skills-ref validate` was not run at all — I did not install it, so
the skill-format side rests on `SkillFormatTest` (green), on `SKILL.md` being 186 lines
against the 500 ceiling, and on reading its frontmatter. Nothing was run on Python 3.12:
one interpreter here (3.14), which is T3-015's open finding, not this round's. I did not
re-hunt the block — no template was read against `check` for gates outside the fifteen
findings.

**Incidental fixes (rule 6):** all 24 files changed by the T2 commits map to a listed
finding or to an incidental the report names. Nothing unnamed. `review.py`'s 96 changed
lines split cleanly: `ASSET_*`/`asset()`/`fill()`/`cmd_setup` → T2-008/015, `diff_volume` +
`{{DIFF_VOLUME}}` + the `diff_vol` MSG pair → T2-010, the deferral refusal tail → T2-011,
the `default_cli` docstring → T2-012.

## Findings

### R1-001 · medium · `TemplateContractTest` is satisfied by prose, so the draft schemas it was written for are unguarded
**Location:** `tests/test_review.py:5014`
**What is wrong:** the guard's whole test is `any(field in body for body in bodies.values())`
— a plain substring over the entire template. Every one of the 13 agent field names is an
ordinary word that the templates use in prose: `root` in "Duplicates — by root, not by
text" (`verify.md:70`), "the whole root at once" (`fix.md:92`) and inside the path string
`"file":"path/from/repository/root"`; likewise `file`, `line`, `status`, `claim`, `block`,
`scenario`, `severity`, `confidence`, `invariant`; and this round added prose paragraphs
that name `reject_reason`, `dup_of` and `defer_reason` in backticks next to their schemas.
So the guard holds "the word occurs somewhere", not "the draft schema the agent copies
names it" — and the schema is the artefact both findings are about.
**Failure scenario:** measured twice.

1. All four **English** role templates reverted to `f1a44a0` — the exact state T2-002
   describes: `FAIL … field='dup_of'`, `field='reject_reason'`, `field='defer_reason'`;
   `Ran 2 tests — FAILED (failures=3)`. **`root` stays green.** The `root` half of T2-002 —
   the half its claim leads with, the one that left `roots` answering "no roots recorded"
   and the three-instance gate unable to fire — has no guard in English, the language this
   kit's own review runs in.
2. Every fenced block (i.e. every draft-findings schema) deleted from **all eight**
   templates: the guard is green on **all 13 fields in both languages**. A future edit can
   remove the whole schema from every role template and the suite stays green, while an
   agent following the templates writes findings the register cannot group.

`DraftByTheTemplateTest` does not cover it either: it writes its own draft rows and never
opens a template (green with the English templates reverted).
**Why it is a defect:** invariant 2 — a guard that can be holed with the suite green is not
a guard; the register records `tests/test_review.py::TemplateContractTest` as the closure of
T2-001, and the fixer's verdict table records it for T2-002 as well. The `_register_fields()`
half is sound — measured: it derives exactly the 21 finding keys from the source, nothing
extra, nothing missing, so a new field really must be classified. It is the *demand* on the
templates that is too weak, not the vocabulary it is made of.
**Also, a report/diff discrepancy:** the fix report quotes this mutation as
`FAIL (lang='en', field='root') … FAILED (failures=7)`. The count is right (4 ru + 3 en);
the English `root` line in it did not happen and cannot.
**Introduced by this round or present before:** introduced by this round — the guard is new.
**Confidence:** confirmed
**Root:** class guard keyed on incidental syntax

### R1-002 · medium · the volume the fix reviewer is told is a third of the volume it is handed
**Location:** `skills/finetooth/scripts/review.py:1893` (`body.replace("{{DIFF}}", diff)`),
measurement at `:1791`
**What is wrong:** `{{DIFF}}` is deliberately excluded from the one-pass `PLACEHOLDER.sub`
(`- {"{{DIFF}}"}` at `:1884`) and applied afterwards as a plain `str.replace` over the
**whole assembled body** — which by then contains the pasted `{{MANIFEST}}`. T2's own
manifest mentions `{{DIFF}}` twice (`docs/review/blocks/T2-prompts.md:45` in the placeholder
list, `:64` in hypothesis 10). Both mentions are replaced with the entire diff. So the round
that added a measurement of the diff added it to a prompt that carries the diff three times,
and the measurement counts one.
**Failure scenario:** reproduced on the running system, and on this very assignment.

```
$ python3 skills/finetooth/scripts/review.py prompt T2 --role fixreview --diff f1a44a0..HEAD
stated  :  464 KB,  4091 lines, ~104k tokens      <- {{DIFF_VOLUME}}
delivered: 1410 KB, 12553 lines, ~319k tokens     <- the prompt
factor   : 3.04x
times the diff is pasted: 3
```

The prompt I was given carries the diff twice inside the pasted block manifest — splitting
hypothesis 4 from hypothesis 10 — and once at its own place. A fix reviewer told "104k
tokens just to read it" is handed 319k; the budget the round exists to give is false by 3×
on the kit's own block, and the same sentence tells it to decide whether that fits.
**Why it is a defect:** the one-pass substitution exists precisely so that substituted text
is quotation and not a template — that is T1-021's fix ("prompt substitutes into the pasted
manifest text"). `{{DIFF}}` re-opens it, and this round pinned a number to the result.
Invariant 8 (a number that does not hold where it is applied) and the reasoning
`volume_note` was written on: the budget must be the real one.
**Introduced by this round or present before:** the triple paste was there before (the same
`replace` line, with `diff_text(...)` inline). The **false measurement is new**, and it is
the whole substance of T2-010. Hypothesis 10 of this block's own manifest names the
`{{DIFF}}` handling as the thing to check, so it is inside T2's scope, not T1's.
**Confidence:** confirmed
**Root:** substituted text re-substituted as a template

### R1-003 · low · the way out named where the volume stands does not reduce the volume
**Location:** `skills/finetooth/scripts/review.py:197` / `:249` (the `diff_vol` MSG pair)
**What is wrong:** the new sentence reads "If that does not fit what you can hold at once,
do not read half of it and report on the whole: say so in the report and take one half
through `--scope <half>`". `--scope` does not shrink the diff: it appends `{{SCOPE_LINE}}`
and renames the report. Measured on this repository:

```
prompt without --scope : 1444645 bytes
prompt with --scope    : 1444765 bytes   (+120)
```

and `{{SCOPE_LINE}}` then says "read the rest for context" — i.e. read all of it anyway.
**Failure scenario:** a lead reads the volume line, concludes the range is too big, and runs
two reviewers with `--scope first half` / `--scope second half`. Each is handed the same
319k-token prompt (R1-002). What halves is the *reporting* responsibility — which is real
value and does stop "read what fits, report on the whole" — but the remedy is offered for a
problem of size, and the size is unchanged.
**Why it is a defect:** the same shape this block hunts — a document naming a way out the
mechanism does not provide (invariant 9, read in the direction of the prompts).
**Introduced by this round or present before:** introduced by this round.
**Confidence:** confirmed
**Root:** a document names a way out the mechanism does not provide

### R1-004 · low · three new negative tests assert the gate's message, not its verdict
**Location:** `tests/test_review.py:5482` (and `:5083`, `:5059`)
**What is wrong:** the round's "other side" tests check `assertIn(<message>, run("check").stdout)`
and never the exit code:
`DeferredIsAnAcceptedRiskTest.test_отложенная_без_причины_по_прежнему_роняет_проверку`,
`DraftByTheTemplateTest.test_отказ_с_причиной_только_в_claim_по_прежнему_ловится`,
`DraftByTheTemplateTest.test_корень_из_образца_собирает_класс_и_зажигает_ворота_про_узду`.
`check` prints warnings and problems into the same stdout, so a gate moved from `problems`
to `warnings` still satisfies them while `check` exits 0.
**Failure scenario:** measured. The deferral gate changed from `problems.append(` to
`warnings.append(` in `cmd_check`; `test_отложенная_без_причины_по_прежнему_роняет_проверку`
→ **OK**. A deferral with no reason then leaves `check` green and the review closes with an
unsigned risk in it.
**Why it is a defect:** SECURITY.md's most serious class — `check` green on a wrong state —
and this is exactly the open medium T3-001. The round added three new addresses of it; the
positive tests in the same classes do assert `returncode == 0`, so the habit is one-sided.
**Introduced by this round or present before:** the class is T3-001 (open, medium, block T3);
these three instances are new.
**Confidence:** confirmed
**Root:** a gate whose test asserts its message, not its verdict

### R1-005 · low · the CHANGELOG's T2 section heading renders inside the previous bullet
**Location:** `CHANGELOG.md:77`, `CHANGELOG.ru.md:77`
**What is wrong:** the paragraph "Block T2 of the same review — … 15 findings, all closed
here." follows the last T4 list item with **no blank line**. In CommonMark that is a lazy
continuation: the sentence is absorbed into the `NOTICE.md` bullet and the T2 section loses
its heading. The T4 intro two screens up is separated correctly, so the two sections do not
read alike.
**Failure scenario:** RELEASING gate 4 takes the release notes from **Unreleased**
verbatim. A reader of the next release gets "…the paths a number needs to be traceable.
Block T2 of the same review — the role templates in both languages…" as one sentence of the
anonymity bullet, and the eight T2 entries below hang under a heading that is not there.
**Why it is a defect:** a public document that does not render what it says — the class T4
closed in the same series ("a number in a public document not checked against its source"
and the self-contradicting Unreleased section).
**Introduced by this round or present before:** introduced by this round (`858a45e`).
**Confidence:** confirmed

### R1-006 · low · two of the four places T2-011 fixed are held by nothing
**Location:** `skills/finetooth/scripts/review.py:3073` (the deferral refusal's tail),
`skills/finetooth/SKILL.md:157` (the completion sentence)
**What is wrong:** T2-011 was a contradiction spread over four texts. The lessons half is
held by `test_урок_про_отложенное_говорит_то_же_что_инструмент`; the entry points are held
by `DocumentedSurfaceTest`'s `deferred` token. The refusal's own tail and `SKILL.md`'s
completion sentence — the two that state the tool's answer to "is the review finished" — are
held by nothing, and the register records no `rule` for T2-011.
**Failure scenario:** measured — both reverted to their pre-fix wording, whole suite:
`Ran 296 tests in 328.767s — OK`. The refusal then tells the reader again that "by the end of the review
every deferred finding is fixed or rejected", which is the claim `check` does not hold and
`summary` contradicts — the defect back at two of its four addresses, silently.
**Why it is a defect:** invariant 2 as the kit applies it to itself, and lesson 36 the
finding was written against. The fix report's mutation note for T2-011 says "the other two
green (they test the tool, which did not change)" while the diff does change `cmd_check`'s
message — small, but it is why the gap went unnoticed.
**Introduced by this round or present before:** introduced by this round.
**Confidence:** confirmed
**Root:** a document fixed in one place and guarded in another

### R1-007 · low · the verifier is handed the same "read all" file list with no budget at all
**Location:** `skills/finetooth/references/verify.md:92`, `verify.ru.md:93`
**What is wrong:** found by grep, following rule 5 from T2-010's own reasoning ("the budget
must stand in the assignment, not in the lead session's head" — `volume_note`'s docstring).
`{{VOLUME}}` occurs in the two **hunter** templates and nowhere else. The verifier's template
carries `{{FILES_HEADING}}` and the full file list — the same list, produced by the same
`files_heading(proof, len(files))` — and no measure. The round gave the fix reviewer a
measure and left the second role that receives a whole block unmeasured.
**Failure scenario:** measured on block T1 of this repository:

```
role=hunter  Files: 4. Lines: 4100. Order of magnitude: ~41k tokens just to read …
role=verify  ABSENT
```

On a block at the 6000-line ceiling the verifier is told "Block files (N) — read all" with
no statement of what that costs, does its own independent pass, and is the role measured at
165 → 330 turns — the most expensive of the four. If it cannot hold the block it has no
sentence telling it to say so, which is precisely what the fix reviewer just got.
**Why it is a defect:** the same class as T2-010, at an address the fix did not reach and the
fix report does not name (its "Found, not fixed" list covers three other things).
**Introduced by this round or present before:** present before; the round fixed one of the
two addresses.
**Confidence:** confirmed
**Root:** the budget stands in one role's assignment and not in another's

## Checked and found correct

- **`ShippedSampleTest` is honest at every address.** Each of the three toy defects
  (T2-004 register id in a comment, T2-005 unowned `README.md`, T2-013 the `<skill>`
  header) was reverted **alone** and the guard went red alone each time. The definition
  sample's phase order goes red on its own too, with exit 1 and the gate's own sentence —
  the test asserts the return code, not just the message, so it is not R1-004's shape. The
  other side (`test_ворота_про_порядок_фаз_живы`) stayed green on old and new code: the fix
  reordered a sample and did not weaken the phase gate. The `state.json` change is a real
  `restamp` (a new `restamped_at`, a recomputed `refs_sha`), not a hand edit.
- **`_register_fields()`** derives exactly the 21 register keys from the tool's source —
  nothing unclassified, nothing in `TOOL_FIELDS`/`AGENT_FIELDS` that the source does not
  have. A field nobody has written yet genuinely has to be classified. Only the demand made
  of the templates is weak (R1-001).
- **The templates' new vocabularies match the tool.** `"confidence":"confirmed|plausible|rejected"`
  and `"status":"open|rejected|duplicate"` are subsets of `CONFIDENCE` and `FINDING_STATUS`;
  `reject_reason`, `defer_reason`, `dup_of` and `root` are the fields `cmd_check` reads. An
  honest report written by the new instructions imports and leaves `check` at exit 0, and a
  reason hidden in `claim` is still refused — both directions tested, both green.
- **English and Russian say the same thing** in all ten changed templates: the same rules,
  the same fields, the same `**Root:**` / `**Корень:**` line, the same numbers. No drift.
- **`--round` is coherent end to end.** `report_path` gives `…fix.md` for round 1 and
  `…fix-2.md` for round 2, the fixer's prompt states its round, and the round-N fix reviewer
  is pointed at the round-N fixer's report — proved by mutation, and it matches what
  `SKILL.md` and both entry points now document.
- **`asset()`'s fallback** is right for the one asset with no translation
  (`blocks.example.json` is offered to a Russian review in English, deliberately), and the
  other-side test forbids a Russian sample leaking into an English checklist.
- **`diff_text` still refuses an unusable range** after being moved ahead of the placeholder
  check: exit 2 on a bad revision, exit 2 on an empty range. No silent empty review.
- **The deferral flow end to end**: defer with a reason → `check` 0, `status` "all blocks
  closed", the reason in the summary's accepted risks. The mechanism now matches all four
  documents; only two of them are guarded (R1-006).
- **`make review` is gone from both addresses** and the snippet says why, with the offered
  `npm run review --` form proved to survive a real refusal with its flag intact.
- **Noted, not a finding.** `tests/test_review.py:2494` still installs with
  `--cli "make review"` — the value T2-012 established cannot work. There it is only an
  arbitrary "second, different value" and the assertion is that the configured `cli` is *not*
  overwritten, so nothing depends on it working and no user reads it; but if `CliContractTest`'s
  source rule is ever widened past `SKILL.md` and the tool — the natural next step for a rule
  of that shape — this is the fixture it will trip on.
- **Not a finding, but for the lead:** the fix report's leftovers for you (its items A–D and
  the `kit_version: 0.6.0` note) are all still true after the merge; the `check` output
  above is the same list. Two journal lines (`06:13:44Z` and `05:48:11Z`, both `— fix —`
  with empty text, the second out of order) are lead apparatus, not product.

## Is another round needed

**Yes** — two medium findings, by the measure of rule 11.

Neither is a wrong fix: all 15 findings are genuinely closed, reproduced closed on the
running tool, and the block's substance got much better — the Russian half of the kit is
reachable and translated for the first time, the shipped example passes the gates it points
at, the draft schema finally names the field the whole defect-class mechanism runs on, and
the samples are held by rules that read their subject from the tool rather than from a list.
What the round did not do is make two of its own guarantees hold: the template guard is
satisfied by prose rather than by the schema (**R1-001**), and the reading budget it
introduced states a third of the volume it delivers (**R1-002**). Both are cheap to close —
R1-001 by demanding the field inside a fenced block of the schema, R1-002 by substituting
`{{DIFF}}` in the same single pass as everything else (the exclusion exists only so the
diff's own `{{…}}` are not re-read, which one-pass substitution already guarantees). Whoever
takes R1-002 should re-measure this block's own prompt afterwards: it is the cheapest proof
that the stated number is the delivered one, and it goes from 1410 KB to about 480 KB.

The five low findings do not need a round of their own: R1-004 belongs with T3-001's fix,
which has to sweep all the sites of that class anyway — the three new ones are named above so
they are not missed; R1-003, R1-005 and R1-006 are one-line fixes for the fixer or the lead;
R1-007 is a `{{VOLUME}}` line in two templates and is the natural thing to do while R1-002 is
in hand, since both are about the same sentence being true.

**Where the findings sit:** 6 of 7 are inside what this round wrote (R1-007 is the address it
did not reach). For a first round that
is the expected shape — the fixes *are* the code under review — not a loop signal. The
signal to watch for is round 2 finding the same classes in the same places again: if
R1-001's class (a guard satisfied without exercising its subject) or R1-002's class
(substituted text read as a template) comes back in round 2's own changes, the next move is
a human's, not another round. Two of the six already carry classes that are open in
neighbouring blocks (T3-001, and T1-021's class re-opened through `{{DIFF}}`), which is the
one thing worth a human's attention now.
