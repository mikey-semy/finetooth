# T2 — fix round 3

Two findings in the round, both closed. `T2-024` is the owner's deferral (issue #28) and was
not touched: neither its record nor the register records of other blocks were edited by hand.

| finding | verdict | commit | guard |
|---|---|---|---|
| T2-023 · medium · the over-the-ceiling warning names a section `check` does not read | closed | `336fb08` | `tests/test_review.py::NamedExitTest` |
| T2-025 · low · the glued-paragraph rule refuses correct CommonMark and has no invented sample | closed | `2d52c50` | `RepositoryContractTest::test_правило_про_склеенный_абзац_читается_на_выдуманном_документе` |

Two more commits belong to the round: `f4de51e` (the changelog, both languages) and `526d902`
(the documented scenario count, and the incidental fix named under it).

---

## T2-023 — the warning names the section the gate reads, per role

### The probe that reproduced it on the current code

A stand (one block, one 7000-line file, ceiling 6000), the hunter prompt, a hunter report
written **exactly** as the warning tells it to — the unread rest named by path under the
section the warning names, the other coverage section left at the template's skeleton line —
and `check`:

```
=== warning to the hunter:
⚠️ **The block is larger than one session can read** — 7000 lines against a ceiling of 6000.
… and **name the rest by path** in the coverage section of your report. Do not pretend you read it.
=== the report skeleton it points into:
## Coverage
## Hypotheses
## Tree freshness
## Coverage limits
…
=== check exit: 1
  · H1: the 'Coverage limits' section of the hunter report is empty — name what was not read
    or say outright that there is nothing, as an ordinary line and not inside a fence or a quotation
```

The same in Russian (`в разделе своего отчёта про охват` → `## Охват`, the limits section
untouched, the same refusal). The defect is exactly as recorded.

### What was done

`volume_note` takes the role, as `proof_rule` already does, and the warning names the section
of the reader's **own** report that `check` reads for it:

- hunter — the coverage-limits section (`LIMITS_HEADING`), which is the section the gate reads
  and the one the hunter template has pointed at all along;
- verifier — the block-coverage-status section, the only coverage section its report skeleton
  has, and the one its gate (`COVERAGE_VERDICT`, over the body) is satisfied from.

One wording for both roles cannot be right: the hunter's section is not in the verifier's
report at all, and the verifier's is not read by the hunter's gate. Both languages, new key
`vol_over_verify` in both halves of `MSG`.

### The guard for the class (the owner's condition for this round)

`tests/test_review.py::NamedExitTest` — every message of the tool and every paragraph of the
skill that names an agent **a report section, a flag or a command** must name what the
mechanism actually gives:

- a section — resolved against the report skeleton of the role the text reaches, and readable
  by the gate `check` applies to that role's report (the gate patterns are read out of
  `review.py`, not copied into the test);
- a flag — declared by an entry point of the kit (`review.py` by `add_argument`, `axes.py` by
  the literal it matches in `sys.argv`);
- a command — a real subcommand (`add_parser`).

Who reads a message is **derived, not declared**: the `MSG` key is printed by a function,
`cmd_prompt` calls that function under the name of a substitution, and the substitution is
carried by the templates of particular roles (the role-conditional `T("…_verify" if role ==
"verify" else "…")` is read as well). That is what makes the drift catchable from the other
side too — the substitution moved into a role whose report has no such section.

The `--scope` rule of the previous round (`_scope_without_diff`, the same root: a flag that exists but
does not do what it is named for) was **moved into this class unchanged**, so the register's
guard for the root covers both of its instances. See "Register" below.

### The mutation table (the guard goes red on each, green on the unspoiled source)

Every mutation is applied to a **copy** of the source and parsed before the rule runs
(`ast.parse` — a mutant that does not build is not a measurement):

| mutation | what the guard says |
|---|---|
| the message re-pointed at the neighbouring section, en | MSG[en][vol_over]: «coverage» — раздел отчёта роли hunter, которого check не читает; читает: Coverage limits, Hypotheses |
| the same, ru | MSG[ru][vol_over]: «охват» — раздел отчёта роли hunter, которого check не читает; читает: Гипотезы, Ограничения охвата |
| the verifier's message re-pointed at the hunter's section | MSG[en][vol_over_verify]: «coverage limits» — раздел, которого отчёт роли verify не имеет |
| a flag that does not exist (--scope-half) | MSG[en][diff_vol]: флага `--scope-half` не объявляет ни одна точка входа набора |
| a command that does not exist ({cli} finding-list) | MSG[en][md_gen] and MSG[ru][md_gen]: команды `finding-list` у инструмента нет — и перечисляет настоящие |
| {{VOLUME}} added to references/fix.md (the message untouched) | MSG[en][vol_over] / MSG[ru][vol_over]: «coverage limits» / «ограничениях охвата» — раздел, которого отчёт роли fix не имеет |
| the control: the unspoiled source | `[]` — `test_каждый_названный_агенту_выход_механизм_действительно_даёт` green |

**On the code as it was before this round** (`git show HEAD:…/review.py` fed to the rule) the
guard reports four offenders — both languages, both roles:

```
MSG[en][vol_over]: «coverage» — раздел отчёта роли hunter, которого `check` не читает; читает: Coverage limits, Hypotheses
MSG[en][vol_over]: «coverage» — раздел, которого отчёт роли verify не имеет
MSG[ru][vol_over]: «охват» — раздел отчёта роли hunter, которого `check` не читает; читает: Гипотезы, Ограничения охвата
MSG[ru][vol_over]: «охват» — раздел, которого отчёт роли verify не имеет
```

### Does it go red on the reverted fix

`review.py` restored from `HEAD` (`BUILD OK (reverted)`, the tests untouched):

```
FAIL: test_каждый_названный_агенту_выход_механизм_действительно_даёт (NamedExitTest)
FAIL: test_узда_краснеет_на_каждой_порче_сообщения (NamedExitTest)
FAIL: test_узда_пропускает_верно_названный_выход (NamedExitTest)
FAIL: test_отчёт_написанный_по_предупреждению_об_объёме_проходит_ворота (ParallelKitLessonsTest)
Ran 6 tests in 2.318s
FAILED (failures=4)
```

The behaviour test names the defect in the words of the gate itself:

```
AssertionError: "'Coverage limits' section of the hunter report is empty" unexpectedly found in
  "\n\n  · H1: the 'Coverage limits' section of the hunter report is empty — …"
  : охотник написал непрочитанное туда, куда послало предупреждение, и ворота отказали:
    сообщение называет не тот раздел, который они читают
```

### The other side — what the fix must still allow

- **A report written by the warning passes the gate, and a report that ignores it still does
  not.** `ParallelKitLessonsTest::test_отчёт_написанный_по_предупреждению_об_объёме_проходит_ворота`
  reads the section out of the warning itself (it is not spelled into the test), writes the
  unread rest there — the limits refusal is absent — and then writes the same report with the
  unread rest in the neighbouring section, where the refusal must come back. Both halves in
  one test: the gate did not get weaker, only the message stopped sending the agent past it.
- **The rule does not fight legitimate wording.**
  `NamedExitTest::test_узда_пропускает_верно_названный_выход` feeds four innocents: the same
  section said in other words ("in the section on coverage limits of your report"), a section
  of the **invariants** in quotes ("What is NOT a finding"), a foreign program's flag
  (`git log … --oneline`) and a real command with a real flag (`{cli} coverage --no-write`).
  All green.
- **`--scope` still divides the report and the responsibility** — the moved
  `test_правило_про_scope_читается_на_выдуманном_исходнике` and the behaviour test of round 2
  are unchanged and green.

### Every address (checked by grep, not from the finding)

`grep` over the tool, the skill and both entry points for texts that tell an agent where the
unread rest goes:

| address | state |
|---|---|
| `MSG[en/ru][vol_over]` | fixed (hunter wording) |
| `MSG[en/ru][vol_over_verify]` | new (verifier wording) |
| `references/hunter.md:108`, `hunter.ru.md:108` | already correct — "the coverage-limits section below" |
| `references/verify.md` §3, its skeleton `## Block coverage status` | already correct — the gate is announced |
| `references/lessons.md:41`, `lessons.ru.md:39` | already correct — "Coverage limits" |
| `SKILL.md:148`, `assets/entry-point.md:37` and its `.ru` | already correct |

All of them are now inside the guard's corpus, so the next edit of any of them is checked
rather than read.

### Incidental fix, named separately (rule 4)

**The verifier's warning also says what its gate demands.** `COVERAGE_VERDICT` is satisfied by
a coverage word in the body, and a verifier that only listed unread paths under
`## Block coverage status` would still be refused. The verifier's wording therefore ends with
"saying outright that the coverage is incomplete" (ru: "прямо сказав, что охват неполный") —
which is what the gate reads. Held by the same guard for the section, and by
`GateRegistryTest`/`GateMutationTest` for the gate itself; `NamedExitTest`'s mutation of that
message goes red.

---

## T2-025 — the markdown rule refuses only what the markup really glues

### The probe that reproduced it on the current code

A bullet followed directly by each construct, appended to a tracked document, the rule run
after each (the file restored afterwards):

```
FLAGGED  заголовок: ## A heading right after it
FLAGGED  тематический разрыв: ---
FLAGGED  html-блок: <div>a block right after it</div>
FLAGGED  абзац (настоящее склеивание): A paragraph right after it
```

After the fix, the same probe:

```
ok       заголовок: ## A heading right after it
ok       тематический разрыв: ---
ok       html-блок: <div>a block right after it</div>
FLAGGED  абзац (настоящее склеивание): A paragraph right after it
```

The first three end the list in CommonMark and render exactly as written; the message told the
author the markup makes them a continuation of the bullet.

### What was done

- The rule moved out of the test body into `RepositoryContractTest._glued_to_list_item(text)`
  — a function, so it can be fed something other than the repository's own files.
- Lazy continuation belongs to a **paragraph**; a line that opens a block of its own ends the
  list. `ENDS_LIST` exempts an ATX heading, a thematic break and an HTML block (CommonMark
  types 1–6); a fence was already skipped by the fence toggle.
- **A table row is deliberately not exempt**, although the finding names it: GFM builds a
  table header out of the last line of a paragraph, so `| a | b |` written directly after a
  bullet stays inside that bullet. Exempting it would blind the rule to a real swallow.

### Which test catches it, and does it go red on the reverted rule

`RepositoryContractTest::test_правило_про_склеенный_абзац_читается_на_выдуманном_документе`
— two glued samples, nine innocent ones. With `and not cls.ENDS_LIST.match(line)` removed (the
mutant parses — `BUILD OK`):

```
BUILD OK (the rule back to what it was)
test_правило_про_склеенный_абзац_читается_на_выдуманном_документе -> FAILED (failures=3)
test_ни_один_абзац_не_приклеен_к_предыдущему_пункту_списка        -> OK
```

Three red: the heading, the break and the HTML block. The repository-wide test stays green on
the old rule — which is exactly why the false half went unnoticed: fed only the repository's
own documents, a rule that refuses correct markup has nothing to trip over.

### The other side — what the fix must still allow, and what must still be refused

The same test's second half: a paragraph directly after a bullet (`-` and `1.`) is still
reported (`[2]`), and nine innocents stay silent — heading, thematic break, HTML block, code
fence, an indented continuation, a blockquote, the next list item, a paragraph after a blank
line, and a glued paragraph **inside** a fenced example.

---

## Incidental fixes of the round, each named separately (rule 4)

1. **The verifier's warning says what its gate demands** — under T2-023 above.
2. **The Russian scenario count could not be written grammatically** (`526d902`). The number in
   the documents follows the suite (336 → 343), and a number ending in three takes
   "сценария", not "сценариев" — but the pattern that reads the number back out of
   `README.ru.md` knew one ending, so a truthful document had to be an illiterate one. All
   three endings are read now. Checked both ways: `336 сценариев`, `343 сценария` and
   `341 сценарий` all yield their number, a document that names no number at all still yields
   nothing and the gate still refuses it
   (`test_число_сценариев_в_документах_не_больше_настоящего`, green on the new wording).

---

## Register

- `T2-023 fixed --commit 336fb08 --rule tests/test_review.py::NamedExitTest`
- `T2-025 fixed --commit 2d52c50 --rule …::test_правило_про_склеенный_абзац_читается_на_выдуманном_документе`
  — its root is empty, so the guard is recorded on that finding alone.

**A register change outside these two records, named here deliberately** (the omission of
exactly this is what T2-024 was filed for): `--rule` writes the guard onto every finding
sharing the root, so `T2-018` — the other instance of "a document names a way out the
mechanism does not provide" — now names `NamedExitTest` instead of
`ParallelKitLessonsTest::test_везде_где_назван_scope_назван_и_флаг_уменьшающий_дифф`. That is
accurate and not a loss: the `--scope` rule and its invented-source test were **moved into
`NamedExitTest`** verbatim in this round for that reason, so the recorded guard holds both
instances. No other block's records were touched.

---

## Found, not fixed — for the lead

**1. The meta-rule "every rule over a source has an invented sample" does not see a rule over
TEXT.** `SourceRuleTest._rules_without_samples` keys on `ast.parse` / `ast.walk`, so a rule
that reads the repository's documents is invisible to it — that is how T2-025 reached the
register. The rules it cannot see today, all in `RepositoryContractTest`:

- `test_в_github_нет_кириллицы`
- `test_живое_руководство_ведёт_на_существующие_пути`
- `test_действия_ci_закреплены_коммитом`
- `test_у_каждой_версии_в_истории_есть_ссылка_на_сравнение`
- `test_опись_набора_называет_все_команды`
- `test_число_сценариев_в_документах_не_больше_настоящего`

Extending the meta-rule to text rules would land on all six at once, each needing a function
and an invented document. That is a change to the suite's own contract, not a fix inside
T2-025, and this round was scoped to two findings — so it is left to the lead. The one rule
the round did touch is a function with both sides fed.

**2. The new guard's corpus stops at the skill.** `NamedExitTest` reads every `.md` under
`skills/finetooth` and every message of the tool and `axes.py`. The repository's own documents
(`README*.md`, `CONTRIBUTING.md`, `RELEASING.md`) name commands and flags too, and are held
only by `DocumentedSurfaceTest` (which asks the opposite question: is every command
documented). Widening the corpus is one line and a decision about where the class's boundary
runs — the skill is what installs into someone else's project, the root documents are not.

**3. `check` refuses a `read` block over the ceiling outright**, so the warning that this
round fixed fires in `prompt` for a state `check` already calls red ("split the block, or the
report will lie about coverage"). The warning is still the only thing the agent reads, and the
lead may knowingly run an oversized block — but the two mechanisms say different things about
the same state (one says "split it", the other "read what you can and name the rest"). Not a
defect of either taken alone; a question about the method, and outside this round's scope.

---

## What was run, and with what result

```
$ python3 -m unittest discover -s tests
.....................................................................................
----------------------------------------------------------------------
Ran 343 tests in 395.882s

OK
```

(the run after the last change, on the four commits of the round; 336 → 343 scenarios, the
seven new ones being the five of `NamedExitTest`, the behaviour test of the warning and the
markdown rule's invented-sample test)

```
$ npx --yes skills-ref validate skills/finetooth
Valid skill: skills/finetooth
```

```
$ python3 skills/finetooth/scripts/review.py check
CHECK FAILED:
  · finding T1-038 / T1-048 / T1-064 / T1-066 — code changed since import
  · finding T4-020 / T4-021 / T4-022 / T4-023 / T4-024 — code changed since import
  · finding T2-024 — code in docs/review/findings.jsonl changed since import
  · T1 / T2 / T3 / T4: block files changed after the review
```

**No line about T2-023 or T2-025**, and no new kind of line. What is red there is the open
findings of the other blocks and the four blocks' fingerprints — the same list as after rounds
1 and 2, the lead's call and not this round's. The `T2-024` line is one of those: its subject
file is the register itself, so every write to `findings.jsonl` (the previous round's own
deferral commit included) re-fires it; it was already red before this round touched anything,
and restamping a finding the owner deferred is not the fixer's to do.

```
$ python3 skills/finetooth/scripts/review.py refs
no finding of the register is named outside docs/review/
```
