# T2 — fixer report

Block: **T2 — Prompts, samples and the skill contract**. Fix round: 1.
15 findings handed over, **15 closed, 0 rejected**. Nothing was deferred.

## Finding → verdict → commit

| id | sev | verdict | commit | guard / test |
|---|---|---|---|---|
| T2-001 | medium | closed | `2f95090` | `TemplateContractTest`, `DraftByTheTemplateTest` |
| T2-002 | medium | closed | `2f95090` | `TemplateContractTest`, `DraftByTheTemplateTest` |
| T2-003 | low | closed | `deea162` | `DocumentedSurfaceTest` (recorded as the root's guard) |
| T2-004 | low | closed | `366ae94` | `ShippedSampleTest` (recorded as the root's guard) |
| T2-005 | low | closed | `366ae94` | `ShippedSampleTest` |
| T2-006 | low | closed | `366ae94` | `ShippedSampleTest` |
| T2-007 | low | closed | `6b132f6` | `BilingualAssetTest` |
| T2-008 | low | closed | `6b132f6` | `SetupLanguageTest` |
| T2-009 | low | closed | `deea162` | `DocumentedSurfaceTest` |
| T2-010 | low | closed | `fe7db10` | `ParallelKitLessonsTest::test_ревьюер_правок_знает_объём_диффа_и_про_scope` |
| T2-011 | low | closed | `a2eceb0` | `DeferredIsAnAcceptedRiskTest` |
| T2-012 | low | closed | `fe7db10` | `CliContractTest` |
| T2-013 | low | closed | `366ae94` | `ShippedSampleTest` |
| T2-014 | low | closed | `deea162` | `DocumentedSurfaceTest` |
| T2-015 | low | closed | `6b132f6` | `BilingualAssetTest` |

Commits, oldest first:

| sha | subject |
|---|---|
| `2f95090` | Role templates announce the register fields check reads |
| `366ae94` | The shipped samples pass the tool's own gates |
| `6b132f6` | Scaffolds in the review language, with the project's own command in them |
| `deea162` | SKILL.md and the entry point catch up with the tool |
| `a2eceb0` | A deferred finding is an accepted risk, and every document says so |
| `fe7db10` | The budget and the command stand in the assignment, not in the lead's head |
| `858a45e` | Changelog for block T2, and the register moved to fixed |

Every finding was reproduced on the current code before it was touched. The probes are
throwaway repositories built by script, not reasoning from the description.

---

## T2-001 · the verifier's rejection reason

**Probe before the fix.** A draft findings file holding exactly what `verify.md:123`
prescribes — `"status":"rejected"`, `"confidence":"rejected"`, the reason in `claim` — then
`import H1` and `check`:

```
H1: imported 1 records, 0 of them open
CHECK FAILED:
  · finding H1-001: rejected, but the reject reason is not recorded — `… set-finding H1-001
    rejected --reason '...'` or a claim that starts with 'Rejected: …' (in the review language)
exit= 1
```

The way out the refusal names is a lead command; the verifier writes a file and has no way
to satisfy the gate from where it stands.

**What was done.** `verify.md` and `verify.ru.md` now carry the draft's full JSON shape and
prescribe the dedicated field: `"reject_reason":"what exactly rules the scenario out"`,
with the sentence that `claim` stays a title. `fix.md` / `fix.ru.md` rule 1 gained the
register form of a rejection and of a deferral, which the fixer was never told either.

**Test that catches it.** `TemplateContractTest.test_каждое_поле_реестра_названо_в_шаблоне_
или_проставлено_инструментом` — see the guard below. Allowed side:
`DraftByTheTemplateTest.test_отказ_написанный_по_образцу_не_роняет_проверку` — a rejection
written by the new instruction imports and leaves `check` at exit 0. Forbidden side:
`test_отказ_с_причиной_только_в_claim_по_прежнему_ловится` — a reason hidden in the title is
still refused, so the fix did not soften the gate.

## T2-002 · `root` and `dup_of` in the draft schema

**Probe before the fix.** Five findings of one class written exactly in the format
`hunter.md:155` gives, imported:

```
roots: no roots recorded — the `root` field of the findings is not filled in
guard gate said: NOTHING
exit= 0
```

Five instances of one class, and the gate that exists to demand a guard from the third
cannot fire.

**What was done.** `root` is in the hunter's JSON schema in both languages, with the
sentence that it is the one field no report prose can replace and that the same string goes
into every instance. `verify.md` / `.ru.md` name `dup_of` where duplicates are defined, say
that the check refuses a duplicate that does not say of what, and separate a duplicate from
an instance of a class. The fix-review templates gained the `**Root:**` line their findings
reach the register by.

**Test.** `DraftByTheTemplateTest.test_корень_из_образца_собирает_класс_и_зажигает_ворота_
про_узду` — three findings written by the new schema group into a root and turn `check` red
with "and no guard". The measure of the defect sits next to it:
`test_без_поля_root_тот_же_черновик_ворота_не_зажигает`. Allowed side:
`test_дубль_написанный_по_образцу_не_роняет_проверку`.

**Guard for the class.** `TemplateContractTest` takes the finding's field vocabulary from
the tool's own source (`f.get("…")`, `f["…"]`, `f.setdefault("…")` across the module) and
splits it into what the tool stamps and what an agent writes; every agent field must be
named in some role template, in each language, and a field that is in neither list fails
the test — so a field nobody has written yet must be classified. **Mutation:** the eight
role templates reverted to their previous state:

```
FAIL (lang='en', field='root') … FAIL (lang='ru', field='reject_reason')
Ran 2 tests — FAILED (failures=7)
```

Red on `root`, `dup_of`, `reject_reason` and `defer_reason`, both languages. Templates are
text, so the revert has no build to break; the suite ran and collected normally.

## T2-004, T2-005, T2-013, T2-006 · the shipped samples

**Probe before the fix.** `examples/toy` copied into a fresh git repository and committed,
exactly as its own README instructs:

```
--- review check ---
  · 1 reference(s) to findings in the code: src/billing/quota.ts:1 (H1-001)
CHECK FAILED:
  · findings.md diverged from findings.jsonl — run `… findings`
  · 1 files belong to no block — `… coverage`
exit=1
--- review refs ---
src/billing/quota.ts:1: H1-001 — // Monthly quota: counts attempts, not successes — see finding H1-001.
exit=1
--- review coverage --no-write ---
NOT COVERED: 1 files — the review is incomplete:
  README.md
exit=1
```

And `assets/blocks.example.json` installed as a real definition:

```
CHECK FAILED:
  · H13: phase 1 comes after phase 2 — the blocks array is ordered by phase, because that
    is the execution order
exit= 1
```

**What was done.**
- `quota.ts`: the comment says what is wrong in the code's own words, with no register id.
- `blocks.json` of the toy: `README.md` excluded ("describes the example itself, not the toy
  app"), and `"cli": "python3 <skill>/scripts/review.py"` added — the exact string the
  example's README tells the reader to type, which is what makes the generated `findings.md`
  header reproducible in any clone.
- The toy's context fingerprint was re-taken through `restamp H1`, not edited by hand.
- `blocks.example.json`: the four blocks sorted by phase (H1, H13, V1a, E1). Nothing else in
  the file changed — the diff is 16 lines moved.

**Probe after the fix:** `check` exit 0, `refs` exit 0, `coverage` 4/4 covered, the only
remaining line being the freshness warning that any repository without a remote gets.

**Guard for the class.** The register already carried this root — *"the kit's own gates are
never run over examples/toy"*, three instances — so it is closed by a rule, recorded as
`tests/test_review.py::ShippedSampleTest` on all three. The rule runs the gates over what
actually ships: the example as its README says to use it, and the definition sample
installed as a real `blocks.json`. **Mutation:** the four files reverted:

```
AssertionError: 1 != 0 : `check` на примере: … 1 files belong to no block …
Ran 3 tests — FAILED (failures=2)
```

Both red; the third test — `test_ворота_про_порядок_фаз_живы`, a sample deliberately
reordered — stayed green on old and new code, which is the other side: the fix reordered a
sample, it did not weaken the gate.

## T2-007, T2-008, T2-015 · the scaffolds

**Probe before the fix.** `agent-banner.ru.md` lines 11–21 are byte-for-byte the English
banner; `setup --lang ru --project Проект` printed a checklist naming
`invariants.example.md`, `manifest.example.md`, `agent-banner.md`; and both banners told
every future session to run `make review-status`, substituted by nothing.

**What was done.**
- The Russian banner is Russian. Both banners take `{{PROJECT}}` and `{{CLI}}`.
- `setup` no longer spells asset names in its checklist text: they are constants, resolved
  through `asset(name, lang)`, which picks `x.<lang>.<ext>` when it exists and falls back to
  English (a definition sample is the same in any language).
- The banner is **printed ready to paste**, substituted the way the entry point already was.
  The tool does not write the project's root instructions file, so naming a path to a file
  with an unsubstituted placeholder was the whole defect; printing the finished text is the
  mechanism the sibling asset already had.
- The journal example got the checklist line it never had — that is what made
  `journal.example.ru.md` reachable at all.

**Probe after the fix:** `setup --lang ru` names `invariants.example.ru.md`,
`manifest.example.ru.md`, `journal.example.ru.md`, `agent-banner.ru.md` (and the
language-neutral `blocks.example.json`), and prints the Russian banner carrying the real
command. `setup --project Demo --cli "npm run review --"` prints the English one with
`npm run review -- status` in it.

**Guards.** `BilingualAssetTest` holds two classes at once: a `.ru` copy with English prose
left in it (lines with five or more Latin words, outside fences and code spans — the measure
gives 0 on every current Russian file and 9 on the old banner), and an asset handed to a
project naming a build command instead of `{{CLI}}`. `SetupLanguageTest` holds that the
checklist names the copies of the review language, that every shipped Russian asset is named
somewhere, and that the banner comes out substituted. **Mutation:** the two banners and the
tool reverted:

```
FAIL … (file='agent-banner.md')     make review … — подсказки собираются из CLI
FAIL … (file='agent-banner.ru.md')  make review …
FAIL … (file='agent-banner.ru.md')  ['> ## ⏳ A full-project review is in progr…'] != []
FAIL … 'npm run review -- status' not found in "…"
FAIL … 'invariants.example.md' != 'invariants.example.ru.md'   (and manifest, and banner)
Ran 6 tests — FAILED (failures=8)
```

The reverted tool built and ran (the checklist printed in full). The other side is held by
`test_английское_ревью_получает_английские_образцы` (a Russian sample must not leak into an
English checklist) and `test_образцы_целей_сборки_команду_называть_обязаны` (the build-target
snippets *are* those commands and must keep naming them) — both green on old and new code.

## T2-003, T2-009, T2-014 · the documents behind the tool

**Probe before the fix.** Of the 23 subcommands, `roots`, `refs`, `hypotheses` and `version`
were shown as a command nowhere in `SKILL.md`; `fixreview`, `--append`, `restamp`,
`backfill`, `fix_gate` and `deferred` appeared in neither entry-point asset; and
`prompt H1 --role fix` printed a report path of `H1-demo.fix.md` whatever the round, while
the round-2 fix reviewer was pointed at `H1-demo.fix-2.md`.

**What was done.** `SKILL.md` shows `review version`, `review hypotheses <ID>`,
`review roots` and `review refs` as commands where each belongs, and documents
`--role fix [--round N]` together with what happens without it. Both entry points gained the
fix-review step with its report name, the fix gate, the refusing plain import and
`--append`, the fingerprint section with `restamp` and `backfill`, the report naming scheme,
`fixreview.md` in the `prompts/` row and the deferral rule. This repository's own
`docs/review/README.md` was regenerated from the asset so the lead session reads the current
one.

The fix template now states its round in its opening line, as the fix-review template
already did — nothing else signalled the round to the fixer.

**Guard.** `DocumentedSurfaceTest`, recorded as the guard of the root *"the fix and
fix-review round mechanism is not carried into the kit's documents"*. It takes the
subcommand list from the source (so a command nobody has written yet falls under the rule),
demands each be shown **as a command** — the words `version` and `hypotheses` occur in
ordinary prose, and a rule that read those as a mention missed both — holds the tokens the
entry point cannot be silent about, and checks that the fixer's round is visible in its
prompt and in its report name and agrees with the fix reviewer of that round. **Mutation:**
the documents reverted:

```
AssertionError: Lists differ: ['hypotheses', 'refs', 'roots', 'version'] != []
AssertionError: 'Круг починки: **1**' not found in "…"
FAIL … (file='entry-point.md', token='fixreview') … and nine more tokens
Ran 3 tests — FAILED (failures=10)
```

## T2-011 · "is the review finished"

**Probe before the fix.** `lessons.md:58` and the tail of the refusal at `review.py:2988`
said every deferred finding is fixed or rejected before the review ends. `render_summary`
writes them under "Accepted risks (deferred with a reason)", `check` demands only the reason,
and the completion conditions of `SKILL.md` and both entry points did not mention deferred
findings at all.

**Which side was made to move, and why.** The mechanism is the contract: three of the four
places (the summary section, the completion conditions, the gate itself) treat a deferral
with a reason as a final state, and a rule that resolved every deferral before the end would
make the summary's own section dead. Adding a completion gate instead would be a new
mechanism a running review must act on — that is a maintainer's decision with a Breaking
section, not a fixer's. So the lesson, the refusal's tail and both completion conditions
were made to say what the tool does.

**Test.** `DeferredIsAnAcceptedRiskTest.test_отложенная_с_причиной_доживает_до_сводки_
принятым_риском` runs the flow end to end: defer with a reason, close the block, `check`
exit 0, `status` says "all blocks closed", and the reason appears in the summary's accepted
risks. Other side: `test_отложенная_без_причины_по_прежнему_роняет_проверку`. The document
side is held by `test_урок_про_отложенное_говорит_то_же_что_инструмент`, which finds the
lesson item that mentions `deferred` and requires it to name the answer the tool gives.
**Mutation:** the two lessons files reverted → that test red in both languages, the other
two green (they test the tool, which did not change).

## T2-010 · the fix reviewer's budget

**Probe before the fix.** `{{VOLUME}}` occurs only in the two hunter templates; the
fix-review prompt stated no size beyond git's own `--stat`, no token order of magnitude, and
named `--scope` nowhere, while rule 1 said "read it" without condition.

**What was done.** The diff is taken **once** in `cmd_prompt` (the volume line and the diff
must describe the same text) and measured by `diff_volume`: size in KB, line count, order of
magnitude in tokens on the same four-characters-per-token estimate `volume_note` uses, and
the instruction to say so and ask for `--scope <half>` rather than read what fits and report
on the whole. `{{DIFF_VOLUME}}` stands above the diff in both templates; rule 1 in both says
what to do when it does not fit. The `MSG` string exists in both languages.

**Test.** `ParallelKitLessonsTest.test_ревьюер_правок_знает_объём_диффа_и_про_scope`:
the prompt header matches `Дифф ниже: \d+ КБ, \d+ строк` and contains `--scope`. Other side,
in the same test: the hunter's prompt gets neither the measure nor an unfilled substitution.
**Mutation:** the tool and both fix-review templates reverted → red, with the prompt
rendering in full (the revert builds).

## T2-012 · `make review` as a `cli` value

**Probe before the fix.** `SKILL.md:29` and `review.py:70` offered `make review` as an
example value for `cli`. Every hint is assembled from that field, and the flags go after the
subcommand: `make review prompt H1 --role verify` makes `make` stop on an unrecognised
option, and `make review init` finds no target in the shipped snippet.

**What was done — and what was deliberately not done.** Adding a generic `review` target
would take a catch-all `%:` rule into somebody's Makefile, and it still would not carry
`--role` or `--reason`: `make` parses those as its own options. A target that works for
`status` and breaks for `set-finding` is the half-measure rule 2 forbids. So the
documentation stopped offering a value that cannot work: `SKILL.md` and the tool's docstring
name only forms that carry a flag (`npm run review --`, a shell wrapper), say that a project
on `make` leaves `cli` unset and gets the real path, and point at the snippet; the snippet
itself says why `make` is not a `cli` value and what to write instead.

**Test.** `CliContractTest.test_документация_не_предлагает_make_как_значение_cli` over
`SKILL.md` and the tool. Other side —
`test_предложенная_форма_cli_определена_образцом_и_доносит_флаги` — checks that the form the
documentation does offer exists in the `package.json` snippet and survives a real refusal:
with `"cli": "npm run review --"` the register answers
`npm run review -- set-finding H1-001 rejected --reason '...'`, subcommand and flag intact.
**Mutation:** `SKILL.md`, the tool and the snippet reverted → 3 failures across both
addresses; the other-side test stayed green.

---

## Incidental fixes, each named

1. **The fixer was never told how a rejection or a deferral is recorded.** `fix.md` and
   `fix.ru.md` rule 1 said "mark the finding as rejected with an explanation" and named no
   command or field; deferral — which the entry point's own fixing rules describe as the
   exception for a finding in an unreviewed block — was not mentioned at all. Both are now
   named with their register form and their field. Test: the same
   `TemplateContractTest` rule (`reject_reason`, `defer_reason` must be named in some
   template in each language), red on the reverted templates.
2. **The fix-review templates had no `**Root:**` line.** Their confirmed findings go into
   the register through `import --append` like any others, and the guard gate counts
   instances by `root`. Added in both languages; covered by the same guard.
3. **This repository's `docs/review/README.md` regenerated** from the corrected entry-point
   asset with this project's own CLI. It was byte-for-byte the substituted old asset, so
   this is a forward-port, not an edit: the lead session of this review reads the scaffold
   that matches the tool. No test — the file is review apparatus that dies with the
   directory; the asset it comes from is tested by `DocumentedSurfaceTest`.
4. **A guard with no defect behind it: `MSG` key parity.**
   `BilingualAssetTest.test_таблица_сообщений_одинакова_на_обоих_языках` compares the two
   tables key by key. `T()` raises `KeyError` at run time, not at import, so a string added
   to one language only breaks the role run of a project reviewing in the other — and this
   round added a key (`diff_vol`) to both. The tables were already equal; the rule is there
   so the next key cannot be added to one side alone.

## Found, not fixed — for the lead

**A. 22 findings of other blocks went stale on files this round touched.** `check` now says
"code in … changed since import" for T1-038, T1-048, T1-064, T1-066, T3-001…T3-015, T4-001,
T4-016, T4-017. All of them sit in `skills/finetooth/scripts/review.py`,
`tests/test_review.py` or `skills/finetooth/SKILL.md`, whose line numbering this round moved
(≈34 lines inserted in the tool before `cmd_check`, ≈25 inserted inside
`ParallelKitLessonsTest`, and the rest appended). None of the mechanisms those findings
describe was touched: the diff-header and fence gates (`review.py` 2481, 2727, 3195), the
`init` traceback on a definition without `review_id` (564) and the `SKILL.md` frontmatter
(lines 4–5) are unchanged. The decision is the lead's: `restamp <ID>` per finding after
re-reading, or a re-check. Their cited **line numbers** are now off by the drift and should
be corrected when they are re-read.

**B. Block fingerprints.** `check` is red on "T1/T2/T3: block files changed after the
review" and warns about the context fingerprints of all four blocks. Restamping a closed
block is a statement that the new text was seen — the lead's call at acceptance, not the
fixer's.

**C. Roots at two instances have guards, but no single test class covers both instances**,
so no `--rule` was recorded for them (the state check demands one only from the third
instance, and a rule that covers half a root would be a false record):

| root | instances | what actually guards each |
|---|---|---|
| the defect-class mechanism is announced in no document an agent or a lead reads | T2-002, T2-014 | `TemplateContractTest` / `DocumentedSurfaceTest` |
| the Russian half of the bilingual assets is unwired | T2-007, T2-008 | `BilingualAssetTest` / `SetupLanguageTest` |
| shipped assets hardcode `make` as the project's CLI | T2-012, T2-015 | `CliContractTest` / `BilingualAssetTest` |
| check demands what no role template announces | T2-001 | `TemplateContractTest` |

If the lead would rather have one rule per root, the natural move is to merge each pair into
one test class; it was not done here because splitting them by subject reads better and the
gate does not require it.

**D. Same class, other addresses, left alone.**

- `references/verify.md:153` and `verify.ru.md:152` name the tool as `review.py check` in a
  parenthetical. It is not a command the agent is told to type, and `cmd_prompt` has no
  `{{CLI}}` substitution for role templates at all, so fixing it means adding one — a
  mechanism change outside this assignment. **Candidate finding.**
- `assets/journal.example.md` and `.ru.md` quote a project's own journal line mentioning its
  `review-check` target. That is quoted history from a real review, not a hint the kit
  assembles; left as is.
- `assets/blocks.example.json`, `makefile-snippet.mk`, `package-json-snippet.json`,
  `guard-grep.sh` and `run-role.sh` have no Russian copy. `setup --lang ru` now falls back
  to the English `blocks.example.json`, whose `goal`, `note` and `reason` strings a Russian
  user reads. Whether the bilingual contract should cover a definition sample's prose is a
  decision for the lead. **Candidate finding.**

## Observations outside the assignment

- `examples/toy/docs/review/blocks.json` declares `"kit_version": "0.6.0"` while `VERSION`
  is `0.7.0`. Nothing checks the field — it is only written by `setup` — so this is not a
  gate failure, and correcting it is a claim about which version produced the example.
  Left for the lead.
- `AGENTS.md` still says "98 scenarios, about a minute" for the suite. It is 274 tests and
  about three minutes. That file belongs to block T4.

## What was run

Full gates, once, at the end of the series; the relevant test after each fix.

```
$ python3 -m unittest discover -s tests
......................................................................................
----------------------------------------------------------------------
Ran 274 tests in 184.982s

OK
```

26 of those 274 are new in this round: `TemplateContractTest` (2),
`DraftByTheTemplateTest` (5), `ShippedSampleTest` (3), `BilingualAssetTest` (4),
`SetupLanguageTest` (3), `DocumentedSurfaceTest` (3), `CliContractTest` (2),
`DeferredIsAnAcceptedRiskTest` (3), and one added to `ParallelKitLessonsTest`.

```
$ npx -y skills-ref validate skills/finetooth
Valid skill: skills/finetooth
```

```
$ python3 skills/finetooth/scripts/review.py roots T2
   3 × the kit's own gates are never run over examples/toy  — guard: tests/test_review.py::ShippedSampleTest
       T2-004     fixed     examples/toy/src/billing/quota.ts:1
       T2-005     fixed     examples/toy/docs/review/blocks.json:12
       T2-013     fixed     examples/toy/docs/review/findings.md:3
   2 × the defect-class mechanism is announced in no document an agent or a lead reads  — no guard, but few repeats
       T2-002     fixed     skills/finetooth/references/hunter.md:155
       T2-014     fixed     skills/finetooth/SKILL.md:126
   2 × the fix and fix-review round mechanism is not carried into the kit's documents  — guard: tests/test_review.py::DocumentedSurfaceTest
       T2-003     fixed     skills/finetooth/SKILL.md:92
       T2-009     fixed     skills/finetooth/assets/entry-point.md:46
   2 × the Russian half of the bilingual assets is unwired  — no guard, but few repeats
       T2-007     fixed     skills/finetooth/assets/agent-banner.ru.md:11
       T2-008     fixed     skills/finetooth/scripts/review.py:3509
   2 × shipped assets hardcode `make` as the project's CLI  — no guard, but few repeats
       T2-012     fixed     skills/finetooth/assets/makefile-snippet.mk:17
       T2-015     fixed     skills/finetooth/assets/agent-banner.md:13
   1 × check demands what no role template announces  — no guard, but few repeats
       T2-001     fixed     skills/finetooth/references/verify.md:123
```

`review check` is clean of every T2 line. What remains red belongs to other blocks (the
three-instance roots of T3 and T4) or is the lead's call (item B above); `review refs` says
no finding of the register is named outside `docs/review/`, and `review coverage` is 70/70.
