# T2 — fix review, round 3

Range `ffb8604...HEAD`, 117 KB / 1285 lines — read in full, no split needed.

## What was checked and how

**Read in full.** All six commits of the range (`2d52c50`, `336fb08`, `f4de51e`, `526d902`,
`a0722b8`, `53c35e3`), the diff of `review.py` and of `tests/test_review.py` line by line, and
then the surrounding code the diff does not show: `verify_report_problem`, the coverage-limits
gate in `cmd_check`, the over-the-ceiling refusal, `proof_rule`, `LIMITS_HEADING` /
`COVERAGE_VERDICT`, all four role templates in both languages, `SKILL.md`, `assets/*.md` and
`references/lessons*.md`.

**Reverting.** Both fixes were reverted on disk and the guards re-run:

- `review.py` restored from `336fb08^` (`ast.parse` first — `BUILD OK (reverted)`):
  `NamedExitTest::test_каждый_названный_агенту_выход_механизм_действительно_даёт`,
  `…::test_узда_краснеет_на_каждой_порче_сообщения`,
  `…::test_узда_пропускает_верно_названный_выход` and
  `ParallelKitLessonsTest::test_отчёт_написанный_по_предупреждению_об_объёме_проходит_ворота`
  went red — 4 failures, exactly the four the fix report names, with the gate's own sentence
  in the assertion message. The two mutation-helper tests go red only because the strings they
  patch vanish with the revert; the load-bearing pair is the first and the last, and both are
  real.
- the markdown rule with `and not cls.ENDS_LIST.match(line)` removed (the mutant parses —
  `BUILD OK`): `test_правило_про_склеенный_абзац_читается_на_выдуманном_документе` red on
  three subtests (heading, thematic break, HTML block) while
  `test_ни_один_абзац_не_приклеен_к_предыдущему_пункту_списка` stayed green — which is the
  fix report's own explanation of why the false half went unnoticed, and it holds.
- the guard run against the pre-round tool (`git show 336fb08^:…/review.py` fed to
  `_named_exits`) reports **exactly the four offenders** the fix report quotes, verbatim.

**Gates checked by violation, not by reading.** Nine mutations of my own, none of them in the
fix report's table, each applied to a copy and fed straight to `NamedExitTest._named_exits`:

| my mutation | guard |
|---|---|
| `references/hunter.md`: "the coverage-limits section below" → "the coverage section below" | RED, names the role and what `check` does read |
| `references/hunter.ru.md`: "раздел ограничений охвата ниже" → "раздел охвата ниже" | RED |
| `references/fix.md`: a sentence sending the fixer into "the coverage-limits section" | RED — "раздел, которого отчёт роли fix не имеет" |
| a refusal in `review.py` (not a `{{PLACEHOLDER}}` message) sending the fixer into "the coverage-limits section" | **GREEN — not caught** (R3-001) |
| the same refusal sending the fixer into "the block-coverage-status section" | **GREEN — not caught** (R3-001) |
| `SKILL.md`: a paragraph sending the fixer into "the coverage-limits section" | **GREEN — not caught** (R3-001) |
| `references/fix.md`: a correct sentence about the **hunter's** coverage-limits section | **RED — false positive** (R3-003) |
| `references/fixreview.md`: a correct sentence about the verifier's block-coverage-status section | **RED — false positive** (R3-003) |
| `vol_over_verify`, both languages: the clause "saying outright that the coverage is incomplete" deleted, section untouched | **whole suite green** (R3-002) |

The last one is a full-suite mutation, not a rule-level one: `BUILD OK`, then
`python3 -m unittest discover -s tests` → `Ran 343 tests … OK`.

**Reproduced live.** A stand (one 100-line file, ceiling 50) in both languages, both roles:

- `prompt H1 --role hunter` / `--role verify` — the two wordings arrive correctly split by role
  and by language; the verifier is sent to "block-coverage-status", the hunter to
  "coverage-limits", and the Russian half says the same thing as the English one.
- a verifier report written *exactly* by the new wording: with the trailing "saying outright
  that the coverage is incomplete" the coverage gate is silent; with the paths listed under
  `## Состояние охвата блока` and that clause dropped, `check` refuses
  `verifier report … has no coverage verdict`. So incidental fix #1 is load-bearing and
  correct — and (see R3-002) held by nothing.
- the register: only `T2-018` and `T2-023` carry the root `--rule` writes across, and only
  those two records changed. No other block's records were damaged, which the T2-024 mechanism
  made possible.
- `check` and `refs` on the tree as committed: the refusals are the eight open findings of the
  other blocks plus the four block fingerprints — no line about T2-023 or T2-025, and no new
  kind of line, exactly as the fix report states.

**Whole suite on the tree as committed:** `Ran 343 tests in 379.565s … OK` — the number the
round wrote into `README.md`, `README.ru.md` and `AGENTS.md` is the real one.

**What I did not do.** I did not rebuild the block's two acceptance tables (gate → template,
placeholder map) — that is the hunter's and verifier's deliverable, not this round's. I did not
run a CommonMark renderer (no dependency is available): the HTML-block reasoning in R3-004 is
derived from the CommonMark 0.31 definition of HTML block types 6 and 7, not from a render. I
did not check `skills-ref validate` (network install), and the round touches no skill file.

## Findings

### R3-001 · medium · the new guard sees only the messages a placeholder carries; everywhere else the class recurs silently

**Location:** `tests/test_review.py:6680` (`NamedExitTest._named_exits`, the `if who is None` branch)

**What is wrong:** the guard derives the reader of a text from the `{{PLACEHOLDER}}` that
carries it, which works for `MSG` keys printed by a function `cmd_prompt` substitutes. Every
other text in its own corpus — every `die()` and refusal string of `review.py`, every paragraph
of `SKILL.md` and of `assets/*.md` — gets `who = None`, and for those the rule only asks that
the named section be readable **in somebody's report**. A text that sends role X into role Y's
section is exactly the defect T2-023 was filed for, and in that half of the corpus it passes.

**Failure scenario:** measured, not argued. Mutations applied to a copy and fed to the guard:

```
[GREEN] review.py refusal: "Split the block, and the fixer names the rest in the
        coverage-limits section of the fix report"
[GREEN] review.py refusal: "… or name it in the block-coverage-status section of the
        fix report"
[GREEN] SKILL.md:          "The fixer names what is left in the coverage-limits section
        of the fix report."
```

All three send the fixer into another role's section; all three stay green because those
sections are readable in the hunter's and the verifier's reports. The control — the same
sentence in `references/fix.md`, which the guard *can* attribute to a role — goes red. So the
next refusal written by copying the neighbouring one re-introduces T2-023, the suite says
nothing, the agent follows the refusal, and `check` refuses the report it asked for.

**Why it is a defect:** invariant 2 — a guard that can be holed with the suite green is not a
guard — plus rule 1 of this review. The guard's docstring claims «Правило накрывает корень
целиком: все сообщения инструмента и все документы скилла, а не найденные места», and the fix
report repeats the claim. The measurement falsifies «целиком» for the majority of the corpus
by count, and the register now records **two** findings (`T2-018`, `T2-023`) as closed by this
class guard — the review's memory says a class is closed that is closed in part.

This is not the corpus limit the fix report already names under "Found, not fixed" #2. That one
is about *which files* are read (root documents vs the skill); this is about texts **inside**
the files the guard already reads, and the report does not mention it.

**Introduced by this round or present before:** introduced by this round — the guard is new.

**Confidence:** confirmed

**Root:** a guard recorded as closing a class that it closes in part

### R3-002 · medium · the verifier's new clause is held by nothing: deleting it leaves the whole suite green and re-creates T2-023 for the verifier

**Location:** `skills/finetooth/scripts/review.py:183` and `:236` (`MSG[en|ru]["vol_over_verify"]`)

**What is wrong:** `vol_over_verify` is two instructions, not one — *which section* (block
coverage status) and *what to say there* ("saying outright that the coverage is incomplete").
The second is what actually satisfies `COVERAGE_VERDICT`; a bare list of unread paths under
that heading does not. `NamedExitTest` checks only the first: it resolves the section name
against the role's skeleton and the gate pattern, and is indifferent to the rest of the
sentence. Nothing else touches this message.

**Failure scenario:** measured end to end.

1. Both clauses deleted (`, saying outright that the coverage is incomplete` and `, прямо
   сказав, что охват неполный`), nothing else changed, `ast.parse` → `BUILD OK`; whole suite:
   `Ran 343 tests … OK`.
2. On that same mutated tool, a stand over the ceiling, `prompt H1 --role verify`, and a
   verifier report written exactly by the resulting warning — unread paths named under
   `## Состояние охвата блока`, nothing else:

```
CHECK FAILED:
  · H1: verifier report H1-demo.verify.md has no coverage verdict — is it complete and
    what is left, as an ordinary line and not inside a fence or a quotation
```

Which is T2-023 verbatim, moved from the hunter to the verifier: the warning names a way out
the gate then refuses.

**Why it is a defect:** invariant 2 as the kit applies it to itself, and lesson 36 / the
`T2-021` class — "a document fixed in one place and guarded in another". Rule 6 of this review
requires an incidental fix to come with **its own** test; the fix report names this one (under
T2-023, "Incidental fix, named separately") and asserts it is covered: "Held by the same guard
for the section, and by `GateRegistryTest`/`GateMutationTest` for the gate itself;
`NamedExitTest`'s mutation of that message goes red." That mutation moves the *section*; the
clause is a different half of the same sentence, and the measurement above shows it is held by
nothing. A report claim that a fix is guarded, when the suite is green without the fix, is the
discrepancy rule 1 exists for.

**Introduced by this round or present before:** introduced by this round — the message is new.

**Confidence:** confirmed

**Root:** a document fixed in one place and guarded in another

### R3-003 · medium · the new guard refuses a correct cross-role sentence: naming another role's report section is read as naming your own

**Location:** `tests/test_review.py:6687` (`NamedExitTest._named_exits`, the `for role in sorted(who)` branch)

**What is wrong:** the guard takes every section name mentioned in role X's template as "the
section role X must write into". But these templates legitimately talk about *other* roles'
reports: the fixer reads the hunter's findings, the fix reviewer reads the fixer's report and
the verifier's. A sentence in `references/fix.md` that correctly points at the **hunter's**
coverage-limits section is reported as «coverage limits» — раздел, которого отчёт роли fix не
имеет — a true statement about the wrong thing, telling the author to fix correct text.

**Failure scenario:** measured — three sentences appended to real templates, guard run on each
(control on HEAD: `[]`):

```
[ПОМЕЧЕНО] fix.md:       "What the hunter did not read is listed in the coverage-limits
                          section of the hunter report."
[ПОМЕЧЕНО] fixreview.md: "The verifier states what is left in the block-coverage-status
                          section of its report."
[ПОМЕЧЕНО] hunter.md:    "The verifier will restate it in the block-coverage-status
                          section of the verifier report."
```

All three are correct statements about the real mechanism, and all three make the suite red.
The first is the shape `references/fix.md` naturally takes the next time the fix gate changes —
and by invariant 9 a gate change *must* be announced in a template, so this is on the path the
method itself prescribes.

**Why it is a defect:** rule 3 of this review — a rule that forbids needs a test for what it
must still allow, and the absence of that half matters more than the first.
`test_узда_пропускает_верно_названный_выход` has four innocents (a rewording, a section of the
invariants, a foreign program's flag, a real command); none is a cross-role reference, the
commonest legitimate case in a corpus of four role templates that describe each other's work.
The guard's own docstring names the consequence — «иначе первая же переформулировка сообщения
окажется „нарушением", и узду снимут» — and the register now rests two findings on this guard,
so weakening it reopens the class.

**Introduced by this round or present before:** introduced by this round — the guard is new.

**Confidence:** confirmed

**Root:** a guard with no test for what it must still allow

### R3-004 · low · the narrowed markdown rule exempts HTML that CommonMark does not treat as a block, so the glue it was written for goes unnoticed

**Location:** `tests/test_review.py:5494` (`RepositoryContractTest.ENDS_LIST`)

**What is wrong:** the comment beside the pattern says it exempts «html-блок типов 1–6», but
the pattern is `<[A-Za-z/!?]` — any line that merely *starts* with a tag-ish `<`. CommonMark
type 6 (the fixed list: `div`, `table`, `p`, …) can interrupt a paragraph and does end the
list, so exempting it is right. Type 7 — any other complete tag alone on a line — explicitly
**cannot** interrupt a paragraph, and a line with a tag followed by text is not an HTML block
at all. Both remain lazy continuations of the bullet, and both are now exempt.

**Failure scenario:** measured against the shipped function:

```
type 6 <div>            -> пропущено   (correct)
type 7 <img …> alone    -> пропущено   (wrong — cannot interrupt a paragraph)
inline <b> + текст      -> пропущено   (wrong — not an HTML block at all)
контроль: обычный абзац -> [2]         (correct)
```

So `- last bullet` followed with no blank line by `<b>Важно:</b> вводный абзац раздела`, or by
`<img src="docs/logo.svg" alt="…"> — the logo`, renders inside that bullet in both CHANGELOGs —
the exact rendering defect of T2-020, in the section release notes are taken from verbatim —
and the guard written to catch it is silent. Both READMEs already open with raw HTML, so the
shape is not invented.

**Why it is a defect:** the rule is the guard for T2-020, and a guard with a hole shaped like
its own defect is the class of invariant 2. Low, not medium: the consequence is a rendering
defect in a document, and the plain-paragraph case — how the defect actually arrived the first
time — is still caught.

**Introduced by this round or present before:** introduced by this round — before it the rule
flagged every line, this case included (together with the false positives the round removed).

**Confidence:** confirmed (from the CommonMark 0.31 definition of HTML blocks; no renderer is
available here without a dependency)

**Root:** — (single instance)

## Checked and found correct

- **The `vol_over` / `vol_over_verify` split itself.** Suspicious at first sight — a second
  message where one existed — but it is correct and it is the house idiom: `proof_rule` two
  functions below is written the same way, and one wording genuinely cannot serve both roles,
  because "Coverage limits" is not in the verifier's skeleton at all and "Block coverage
  status" is not read by the hunter's gate. Verified live in both languages.
- **The over-the-ceiling warning is reachable in a green state.** The fix report's "Found, not
  fixed" #3 worries that `check` refuses an oversized block outright, so the fixed warning
  fires only where the gate is red anyway. It is narrower than that: the refusal at
  `review.py:3465` skips blocks with `proof: measured` (`review.py:3458`), while `volume_note`
  does not — a
  measured block over the ceiling gets the warning and `check` stays silent. So the fix earns
  its keep; #3 is a real question about `read` blocks only, and the fixer was right to leave it
  to the lead.
- **The register edit outside the two findings.** `T2-018`'s `rule` moving from
  `ParallelKitLessonsTest::test_везде_где_назван_scope…` to `NamedExitTest` looked like more of
  the T2-024 damage. Checked against the file: exactly two records carry that root, both are
  T2, both were meant to move, the test really was moved into `NamedExitTest` verbatim, and no
  other block's record changed. Declared in the report. Correct.
- **The table row deliberately not exempted from the markdown rule.** The finding T2-025 names
  a table row among the constructs the rule should allow; the fixer refused, because GFM builds
  a table header out of a paragraph's last line. That is right, and refusing part of a finding
  with the reason written down is what the round is supposed to do.
- **The Russian declension fix.** `(\d+) сценари(?:ев|я|й)` reads 336/343/341 alike, still
  demands that a number be named at all, and both README.ru.md sites match. Not a loosening.
- **Widening the guard's corpus is not "one line".** The fix report's "Found, not fixed" #2
  says so; I ran the rule over the 22 tracked root documents and got 19 hits (git's own
  `--stage`, `--format`, `gh --latest`, CHANGELOG entries quoting the old wording). The idea is
  sound, the estimate is not — worth the lead knowing before it is picked up.

## Is another round needed

**Yes by the letter of rule 11 — three medium findings — but the more useful answer is that
this one should go to a human, not to a fourth round.**

All four findings sit **inside the code this round wrote**: three in the guard `NamedExitTest`
that closed T2-023, one in the markdown rule the round narrowed. None is in the product
behaviour the round set out to fix — that part is right, proven by revert, by live probe in
both languages, and by mutation against the pre-round source. The project did get better: a
warning that sent every over-sized hunter into a section the gate does not read now names the
right section per role, and a repo lint that refused correct CommonMark now refuses only real
glue.

The pattern is what matters. Round 2's top finding (T2-025) was "the guard the previous round
added has a false half, because it was only ever fed the repository's own files". Round 3's top
findings are "the guard this round added has a hole (R3-001) and a false half (R3-003), because
it was only ever fed the cases the defect arrived in". That is the same class two rounds
running, in the same place — the new guard — which is exactly the condition rule 11 describes
for handing the decision to a human rather than spending another round.

Counted as rule 11 asks: **4 of 4 findings are inside the code the previous round changed, 0
outside it.** Two rounds in a row where every finding is in the previous round's guard is a
loop. The three medium fixes are small and local (extend `_readers` to attribute role-less
texts, or make the `who is None` branch strict; add a cross-role innocent to the allow-side
test; give the verifier's clause a behaviour test like the hunter's already has) — a lead or
the fixer can close them without a new hunt.
