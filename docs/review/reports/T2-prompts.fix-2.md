# T2 — fixer report, round 2

Seven findings from the round-1 fix review of this block. All seven closed; none rejected,
none deferred.

## Verdicts

| finding | severity | verdict | commit | guard |
|---|---|---|---|---|
| T2-016 | medium | closed | `4da0304` | `tests/test_review.py::TemplateContractTest` |
| T2-017 | medium | closed | `cea1cd8` | — (two regression tests, named below) |
| T2-018 | low | closed | `cea1cd8` | `ParallelKitLessonsTest::test_везде_где_назван_scope_назван_и_флаг_уменьшающий_дифф` |
| T2-019 | low | closed | `4da0304` | — (the class already has `GateRegistryTest`; see below) |
| T2-020 | low | closed | `d258166` | `RepositoryContractTest::test_ни_один_абзац_не_приклеен_к_предыдущему_пункту_списка` |
| T2-021 | low | closed | `4da0304` | `tests/test_review.py::DeferredIsAnAcceptedRiskTest` |
| T2-022 | low | closed | `cea1cd8` | `ParallelKitLessonsTest::test_каждая_роль_с_полным_списком_файлов_получает_и_его_объём` |

`T2-011` was also given its guard and `rule` in the register — it is the finding T2-021 says
was fixed in four texts and held in two; the record had no rule at all.

## What was run

- `python3 -m unittest discover -s tests` — **`Ran 336 tests in 351.641s — OK`** (the run
  after the last change; an earlier full run of the same series gave `Ran 335 … FAILED
  (failures=1)` on the suite's own meta-rule, which is described under T2-018 below).
- `npx skills-ref validate skills/finetooth` — **`Valid skill: skills/finetooth`**.
- `python3 skills/finetooth/scripts/review.py check` — no T2 line in `CHECK FAILED`. What is
  red there is T1/T4 open findings and the four blocks' fingerprints, exactly as in round 1:
  the lead's call, not this round's.
- `python3 skills/finetooth/scripts/review.py refs` — `no finding of the register is named
  outside docs/review/`.
- The documented scenario count in `README.md`, `README.ru.md` and `AGENTS.md` moved 325 →
  336 (the number the suite now reports; the guard allows a lag of a tenth, so this is
  tidiness, not a red gate).

---

## T2-016 · the template contract was satisfied by prose

**Probe, on the code as it stood.** The claim is that deleting every fenced draft schema
from all eight templates leaves the guard green. Run against the templates at `HEAD`:

```
lang=en: current guard fails on []; with EVERY fenced schema deleted it fails on []
lang=.ru: current guard fails on []; with EVERY fenced schema deleted it fails on
          ['block', 'file', 'invariant']
```

English: green on all thirteen fields with no schema anywhere. Reproduced.

**What was done.** `AGENT_FIELDS` was one flat set checked with `field in body` — a substring
over the whole template, and every field name is an ordinary word. It is now two sets with
two different demands:

- `DRAFT_FIELDS` (twelve fields the agent writes as a line of JSON) must be named as a
  **schema key** — `"<field>"\s*:` — and inside code: a fenced block or a backtick span.
  `_code()` extracts exactly those two regions; prose and paths are not declarations.
- `COMMAND_FIELDS` (`defer_reason`, which no draft carries — the tool writes it from
  `set-finding --reason`) must be named **in the same paragraph** as the command that writes
  it. Paragraph, not line, deliberately: a re-wrap of the template must not turn the guard
  red.

`AGENT_FIELDS` is now the union of the two, so the "a new field of the register must be
classified" half is unchanged.

**Does it go red on the reverted fix.** Two mutations, both on the shipped templates, the
test file unchanged:

| mutation | before | after |
|---|---|---|
| every fenced block deleted from all eight templates | green on 13/13 en | `FAILED (failures=16)` |
| the four **English** templates back to `f1a44a0` | red on `dup_of`, `reject_reason`, `defer_reason`; **green on `root`** | `FAILED (failures=4)` — **`root` among them** |

The second is the exact hole the finding names: `root` is the half of T2-002 the claim leads
with, and it now goes red in the language this kit's own review runs in.

**The other side — what must still pass.** Three things, and all are tested:

- the real templates as they ship: `Ran 5 tests — OK` (the fields are declared in the
  schemas, and `reject_reason` / `dup_of` in backtick spans of the verifier's prose, which
  the rule accepts — it demands a schema key, not a fenced block);
- `test_проза_поле_не_объявляет_а_ключ_схемы_объявляет` — on invented templates: the word
  `root` in prose and inside the path `"file":"path/from/repository/root"` is **not** a
  declaration; the same field as a key in a fence, and `dup_of` as a key in a backtick span,
  **are**;
- `test_поле_по_флагу_требует_команду_в_том_же_абзаце` — the field and its command in two
  different paragraphs is not a declaration; in one paragraph it is.

---

## T2-017 · the prompt carried the diff three times and measured it once

**Probe, on the code as it stood.** `prompt T2 --role fixreview --diff f8007b3..HEAD`:

```
prompt size          : 2 003 416 bytes
`diff --git` lines   : 144          (the range has 48 files → pasted 3 times)
stated by {{DIFF_VOLUME}}: "The diff below: 646 KB, 5809 lines … ~148k tokens"
```

Reproduced: the manifest of this very block writes about `{{DIFF}}` twice, and the
after-the-fact `body.replace("{{DIFF}}", diff)` hit both mentions inside the pasted manifest.

**What was done.** The diff became a substitution like every other one, placed into `subs`
and applied by the single `PLACEHOLDER.sub` pass, so a placeholder that arrives *inside* a
substituted value stays a quotation. With that, the `- {"{{DIFF}}"}` exemption in the
unfilled-substitution check had no reason left and is gone: a template that names `{{DIFF}}`
in a role that has no diff is now refused by name instead of handing the agent the literal
text `{{DIFF}}` as an instruction.

After the fix, the same command:

```
prompt size          : 680 196 bytes   (was 2 003 416)
`diff --git` lines   : 48             (was 144)
`{{DIFF}}` in output : 17             — the manifest's two quotations and fifteen inside
                                        the pasted diff, which is itself about this code
```

**Which test catches it.** `ParallelKitLessonsTest::test_дифф_вклеивается_один_раз_даже_если_манифест_о_нём_пишет`
— a stand whose block manifest names `` `{{DIFF}}` ``; the prompt must contain exactly one
` ````diff ` fence, must still contain `+починено`, and must still contain the manifest's
quotation verbatim.

**Does it go red on the reverted fix.** The three edits undone (the `subs` entry removed, the
exemption restored, the trailing `replace` put back): `python3 -c "import ast; ast.parse(…)"`
→ **BUILD OK**, then `Ran 2 tests — FAILED (failures=2)`. Both new tests red on a mutant that
builds.

**The other side.** `test_подстановка_диффа_в_чужой_роли_это_отказ_а_не_текст` holds both
directions of the tightening: a project template for a role **without** a diff that names
`{{DIFF}}` gets exit 2 with the placeholder named in the refusal, while the same placeholder
in the fix-review template is still filled with the whole diff (`+починено` present, nothing
left unfilled above the fence). The pre-existing
`test_ревьюер_правок_получает_дифф_и_своё_имя_отчёта` keeps guarding that the ordinary case —
a manifest that says nothing about placeholders — still gets the diff whole.

---

## T2-018 · the way out named beside the volume did not reduce the volume

**Probe, on the code as it stood.** The message said "take one half through `--scope <half>`".
Measured on this repository in round 1 and re-measured here: the prompt with `--scope` is
**larger** than without it (the flag adds `{{SCOPE_LINE}}` and renames the report), and
`{{SCOPE_LINE}}` then said "read the rest for context" — i.e. read all of it anyway.

**What was done.** The only thing that makes the pasted diff smaller is a narrower `--diff`
range, and the range is already a parameter: a series of fixes is a series of commits. Both
`diff_vol` strings now name `--diff <first part>` / `--diff <second>` as the way out and say
plainly what `--scope` does instead (names the half in the report and in its file name).

Per rule 10, the same claim was hunted down at every other address (`grep`), not taken from
the finding:

| address | what it said | now |
|---|---|---|
| `MSG["en"]["diff_vol"]`, `MSG["ru"]["diff_vol"]` | take one half through `--scope` | the range is split with `--diff`; `--scope` names the half |
| `references/fixreview.md` rule 1, `.ru.md` rule 1 | "ask for one half through `--scope <half>`" | "ask for a narrower range (`--diff <part>`)" + what `--scope` does |
| `MSG[*]["scope_line"]` | "read the rest for context" — assumes the rest is in the prompt | "whatever else is in the diff below, read it for context" |
| `SKILL.md` step 8 | "two agents on two halves of the diff is fine" | `--scope` names the half without shrinking it; split by `--diff` |
| `--help` of `--scope` | "the half of the diff for this reviewer" | "the half of the fixes this reviewer reports on … narrow `--diff` for that" |
| `diff_volume()`'s design note | "`--scope` is the way out" | the way out is a narrower `--diff`; `--scope` divides the reporting |

**Which test catches it.**
`test_названный_рядом_с_объёмом_выход_действительно_уменьшает_дифф` builds a stand with two
commits of fixes and proves the named way out works: the volume line must contain `--diff`,
and the prompt for the first half of the range must be under three quarters of the prompt for
the whole. `test_правило_шаблона_называет_тот_же_выход_что_и_замер` holds rule 1 of both
templates.

**Does it go red on the reverted fix.** The Russian `diff_vol` restored → the volume test red
(`'--diff' not found in 'Дифф ниже: 14 КБ, 611 строк … возьми одну половину через
`--scope <половина>`'`). Rule 1 of both templates restored → the template test red on
`fixreview.md` and `fixreview.ru.md`.

**The other side.** The same test asserts, in the same run, that `--scope` still does its own
job: the prompt with `--scope первая` still carries `**первая**` and still points at
`H1-demo.fixreview-1-первая.md`, and is not smaller than the unscoped one. The round-1 test
`test_ревьюер_правок_знает_объём_диффа_и_про_scope` is untouched and still green: the measure
is still stated, `--scope` is still named, and no other role receives the measure.

**Guard for the class** (a document naming a way out the mechanism does not provide, in this
flag pair): `test_везде_где_назван_scope_назван_и_флаг_уменьшающий_дифф` — every string
constant of the tool longer than a flag name that mentions `--scope` must mention `--diff`,
and so must every paragraph of every `.md` in the skill. Mutation: the measure and both
templates restored → red at three addresses at once (`review.py:249`, `fixreview.md`,
`fixreview.ru.md`). Both sides of the rule itself run on an invented source
(`test_правило_про_scope_читается_на_выдуманном_исходнике`): the guilty string is caught, the
bare flag name in `add_argument` and a string naming both flags are not.

**One honest gap.** The guard does **not** catch the `SKILL.md` sentence that was fixed here:
reverted, the suite stays green, because the paragraph around it names `--diff main...HEAD`
anyway. "Two agents on two halves of the diff is fine" is a prose claim, and no mechanical
rule distinguishes it from a true one. Named here rather than left for the next round to
find.

**Also caught by the suite's own meta-rule.** The first full run after writing that guard was
`Ran 335 … FAILED (failures=1)`: `SourceRuleTest::test_у_каждого_правила_по_исходнику_есть_выдуманный_образец`
refused a source rule written inline in a test body. The rule was extracted into
`_scope_without_diff()` and given its invented-source test; the next full run is the green
one quoted above. Recorded because it is a gate this round tripped, not a gate it changed.

---

## T2-019 · three negative tests asserted the gate's message, not its verdict

**Probe, on the code as it stood.** Each of the three gates moved from `problems.append` to
`warnings.append` in turn, the mutant parsing (`BUILD OK` checked each time), then the named
test alone:

| gate | test | before the fix |
|---|---|---|
| `deferred without a reason` | `test_отложенная_без_причины_по_прежнему_роняет_проверку` | OK on the mutant |
| `rejected, but the reject reason is not recorded` | `test_отказ_с_причиной_только_в_claim_по_прежнему_ловится` | OK on the mutant |
| `… instances … and no guard` | `test_корень_из_образца_собирает_класс_и_зажигает_ворота_про_узду` | OK on the mutant |

**What was done.** All three read `refused(out)` — the helper that returns the `CHECK FAILED`
section and only on exit 1 — instead of the raw stdout, which carries refusals and warnings
in one stream.

**Does it go red on the reverted fix.** The same three mutations, after: each named test
`FAILED (failures=1)`, on a mutant that builds. Shown one by one above.

**The other side.** The negative assertions of the same classes stay `assertNotIn` over the
**whole** output — `test_без_поля_root_тот_же_черновик_ворота_не_зажигает`,
`test_отказ_написанный_по_образцу_не_роняет_проверку`,
`test_дубль_написанный_по_образцу_не_роняет_проверку` — which is the stronger form for "the
gate did not fire at all", and the last two also assert `returncode == 0`. A draft written
exactly by the templates still imports and still leaves `check` at exit 0.

**Why no new class guard.** The class is `a gate whose test asserts its message, not its
verdict` — root shared with T3-001, which is fixed. `roots` reports it as `2 × … no guard, but
few repeats`, i.e. below the three-instance gate. And the gates themselves are already held:
`GateRegistryTest` pairs every gate of `cmd_check` with a named test and `GateMutationTest`
proves each by silencing the gate **and** by moving it to the neighbouring list — the three
gates above each have such a test elsewhere in the file. The three assertions fixed here were
redundant, not the last line of defence. See "Found, not fixed" for the remaining instances of
the same writing habit.

---

## T2-020 · a section's opening paragraph rendered inside the previous bullet

**Probe, on the code as it stood.** `CHANGELOG.md:76` is the last `NOTICE.md` bullet of the T4
section and `:77` is the T2 paragraph, with no blank line between them; the same at `:76/:77`
of `CHANGELOG.ru.md`. In CommonMark that is a lazy continuation: the paragraph is absorbed
into the bullet and the eight T2 entries below hang under no heading. The T4 and T3 intros two
screens away are separated correctly, so the file does not even read alike.

**What was done.** A blank line before each of the two paragraphs — and the same before the
new round-2 paragraph added to both files in `d258166`.

**Which test catches it.**
`RepositoryContractTest::test_ни_один_абзац_не_приклеен_к_предыдущему_пункту_списка` — over
**every tracked `*.md`** of the repository (`git ls-files -z '*.md' ':!docs/review'`; the
review's own reports are written by agents and die with the directory), no non-indented,
non-quoted, non-list line may follow a list item directly. Fenced blocks are skipped, and both
backtick and tilde fences are recognised.

**Does it go red on the reverted fix.** Both blank lines removed → `FAILED`, naming
`CHANGELOG.md:77` and `CHANGELOG.ru.md:77` with the offending text. Restored → OK.

**The other side.** The guard is green over the whole repository as it stands — 60-odd
markdown files including every template, asset, README and the toy example — so it forbids the
lazy continuation without forbidding the legitimate neighbours: an indented continuation line,
a quotation, a nested list, a fence opening right after a bullet.

---

## T2-021 · two of the four texts about a deferred finding were held by nothing

**Probe, on the code as it stood.** Both addresses restored to their pre-fix wording (the
refusal's tail in `cmd_check` back to "by the end of the review every deferred finding is
fixed or rejected with a reason"; `SKILL.md`'s completion sentence back to "All blocks
`closed`, no open findings, every rejected one has a reason."), the mutant parsing — and the
class's own test file was green. Reproduced.

**What was done.** Two guards, and the register given the rule it lacked:

- `test_отказ_ворот_говорит_то_же_что_сводка` — a real run: defer without a reason, and the
  refusal must name the accepted risk and must **not** promise a fix or a rejection by the end
  of the review.
- `test_все_тексты_набора_дают_один_ответ_об_отложенной` — the seven texts that answer "what
  is a deferred finding at the end of the review", each with the anchor the answer must stand
  at: both lessons, both fixer templates, both entry points and `SKILL.md`'s completion
  section. The window is 300 characters — measured: the farthest of the seven answers stands
  128 characters from its anchor (`SKILL.md`), the nearest 43; 300 is about a paragraph, and
  an answer that has drifted further than a paragraph reads as no answer.

The old `test_урок_про_отложенное_говорит_то_же_что_инструмент` is subsumed by the second and
removed — its two addresses are rows one and two of the table.

**Does it go red on the reverted fix.** The refusal restored → `test_отказ_ворот_говорит_то_же_что_сводка`
red, on a mutant that parses (`BUILD OK`). `SKILL.md` restored → the table test red with
`файл='SKILL.md'`. Both lessons restored from `a2eceb0^` → the same test red with
`файл='references/lessons.md'` and `файл='references/lessons.ru.md'`, so the coverage the old
test gave is not lost.

**The other side.** `test_отложенная_с_причиной_доживает_до_сводки_принятым_риском` is
untouched and green: a deferral **with** a reason still leaves `check` at exit 0, `status` at
"all blocks closed", and the reason in the summary's accepted risks. Deferring is not
forbidden; deferring in silence still is
(`test_отложенная_без_причины_по_прежнему_роняет_проверку`, now reading the refusals section).

---

## T2-022 · the verifier was handed the block whole with no reading budget

**Probe, on the code as it stood.** `{{VOLUME}}` occurred in the two hunter templates and
nowhere else, while `grep '{{FILES}}'` returns four files — the two hunter templates and the
two verifier ones, all fed by the same `files_heading(proof, len(files))`. On block T1 of this
repository the hunter prompt states `Files: 4. Lines: 4100. ~41k tokens just to read`; the
verify prompt states nothing.

**What was done.** Both verifier templates carry a "Volume of work" / "Объём работы" section
with `{{VOLUME}}`, in the same place as the hunter's — above the file list.

And an address the fix uncovered: `vol_over`, the over-the-ceiling warning, told the reader to
name the rest "in the coverage-limits section" — the **hunter's** heading. The verifier's
report has `Block coverage status` instead, and `LIMITS_HEADING` does not match it. Pasting
the hunter's instruction into the verifier's prompt would have been invariant 9 in the other
direction: an instruction the reader cannot follow. Both languages now say "the coverage
section of your report", which is true of both roles. Named here as part of this fix, not
as a separate one — it is the same sentence.

**Which test catches it.**
`test_каждая_роль_с_полным_списком_файлов_получает_и_его_объём`, in two halves: a rule over
the templates (any template containing `{{FILES}}` must contain `{{VOLUME}}` — so a role
nobody has written yet falls under it), and a run (`prompt H1 --role hunter|verify` must both
print `Файлов: N. Строк: M` and leave no substitution unfilled).

**Does it go red on the reverted fix.** The two verifier templates restored → `FAILED
(failures=3)`: `файл='verify.md'`, `файл='verify.ru.md'`, and `роль='verify'` on the prompt
itself.

**The other side.** The hunter's half of the same test stays green throughout, and
`test_ревьюер_правок_знает_объём_диффа_и_про_scope` still asserts that the **diff** measure
does not leak into roles that have no diff. The verifier gets the file-list measure, not the
hunter's report headings: `{{FILES_HEADING}}`, `{{PROOF_RULE}}` and the report skeleton are
untouched.

---

## Incidental fixes

Each is named with its own test; none is a silent extra.

1. **`{{DIFF}}` is no longer exempt from the unfilled-substitution refusal** (in
   `cea1cd8`, part of T2-017's fix). Once the diff is substituted in the single pass, the
   exemption has nothing left to protect, and the comment right above it calls an unfilled
   `{{SOMETHING}}` reaching the agent a defect. Test:
   `test_подстановка_диффа_в_чужой_роли_это_отказ_а_не_текст`, both directions.
2. **`{{SCOPE_LINE}}` no longer promises that the rest of the diff is in the prompt**
   (`cea1cd8`, part of T2-018). It said "read the rest for context", which is false as soon as
   a lead splits the range instead of the responsibility. Held by the same
   `test_названный_рядом_с_объёмом_выход_действительно_уменьшает_дифф`, which asserts the line
   is present and names the scope, and by `test_ревьюер_правок_получает_дифф_и_своё_имя_отчёта`
   (`**backend**` in the prompt).
3. **`vol_over` names the reader's own coverage section** (`cea1cd8`, described under
   T2-022). Held by the verify half of
   `test_каждая_роль_с_полным_списком_файлов_получает_и_его_объём`.
4. **`--help` of `--scope` says what the flag does** (`cea1cd8`). Held by
   `test_везде_где_назван_scope_назван_и_флаг_уменьшающий_дифф` via the string rule over the
   tool's source.
5. **`T2-011` given its guard in the register** (`4da0304`). The finding was recorded fixed
   with no `rule`, which is what let two of its four addresses go unheld; it now carries
   `tests/test_review.py::DeferredIsAnAcceptedRiskTest` and `--fixed-in tests/test_review.py`.
6. **The documented scenario count 325 → 336** in `README.md`, `README.ru.md`, `AGENTS.md`.
   Held by the existing `test_число_сценариев_в_документах_не_больше_настоящего`, which reads
   the real count from the suite.

## Found, not fixed — for the lead

- **The same writing habit at fourteen more addresses.** `assertIn(<message>, self.s.run("check").stdout)`
  in `tests/test_review.py` at lines 308, 569, 571, 640, 654, 758, 825, 1238, 1451, 1585,
  1588, 1640, 3255 (and a few more behind `out = self.s.run("check").stdout`). Every one of
  those gates is separately held by `GateRegistryTest` + `GateMutationTest`, which move the
  gate to the neighbouring list and demand the named test go red — so these are redundant
  assertions, not open holes. Converting them to `refused()` / `warned()` is a sweep through
  block T3's file and its root (`a gate whose test asserts its message, not its verdict`,
  T3-001, fixed); left to the lead rather than done from inside T2.
- **`tests/test_review.py:2494` still installs with `--cli "make review"`** — the value T2-012
  established cannot work. Round 1's fix review already flagged it as "noted, not a finding";
  it is still there, and it is the fixture `CliContractTest` would trip on if its source rule
  is ever widened past `SKILL.md` and the tool.
- **`--scope` with a space produces a report file name with a space** (`report_path`
  interpolates the value verbatim: `H1-demo.fixreview-1-первая часть.md`). Everything
  downstream handles paths with spaces by invariant, and nothing refuses it, so it is not a
  defect as things stand — but it is how a lead would naturally write `--scope "first half"`,
  and the name it produces is not the one anybody would type back.

## Observations outside the assignment

- `docs/review/README.md` (this repository's copy of the entry point) is generated from
  `assets/entry-point.md` and was not touched by this round; nothing in the round changed the
  asset, so the two are still level. Worth a `diff` before the block closes.
- The register's `check` is red on four blocks' fingerprints and on six T1/T4 findings whose
  code has moved. Unchanged from round 1 and untouched here: `restamp` is the lead's decision,
  and doing it from inside a fix round would declare code reviewed that this round rewrote.
