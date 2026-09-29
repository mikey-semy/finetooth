# T3 — fix review, round 2

## What was checked and how

The diff (172 KB, 1932 lines) was read in full — no `--scope` split was needed.

**Baseline.** The whole suite at `HEAD` (39aa699), in a detached worktree:
`Ran 330 tests in 393.879s / OK`. The report's `330 / 389.792s` reproduces.
`npx skills-ref validate skills/finetooth` → `Valid skill` (nothing under `skills/` changed).

**What the owner asked for** — whether the root *"a class guard keyed on incidental syntax"*
is closed **as a class** — was tested the way this round itself says a guard must be tested:
by inventing spellings that are **not** in `SOURCE_MUTATIONS` and measuring whether the
rule's verdict survives them. Five such spellings were built and fed to the real source; three
were then applied as minimal hand mutations to real call sites, and the **whole suite** was run
on each mutant (~6.5 min per run).

| what was built | rule's verdict | whole suite |
|---|---|---|
| git argv through a wrapper `_git(*rest)` | 6 complaints → **0** | — |
| git argv accumulated with `.extend()` | 6 complaints → **0** | — |
| `untracked_files` with `.extend()`, `-z` dropped, `splitlines()` | silent | **330 OK** |
| `index_rows` through `_git(...)`, `-z` dropped, `splitlines()` | silent | **330 OK** |
| a **new** gate in a module helper whose refusal list is named `refusals` | 0 gates seen, no `UnknownGateSpelling` | **330 OK** |
| a new source rule fed the tool by path (`(SKILL / "scripts" / "review.py").read_text(...)`) | needs no mutation table | — |

**Reverting.** Six reverts were run, each on a copy whose Python still parses:

| reverted | result |
|---|---|
| the locale refusal text back to Russian | `test_отказ_набора_читается_в_той_локали_ради_которой_написан` **red**, with the escapes in the message; module still imports and still refuses; the other-side test green |
| `_nul_offenders` to its `e098508` shape | `SourceMutationTest` **red** (3 failures) |
| `_check_gates` to its `e098508` shape | **red** (`форма='часть с чужим списком'`, `'часть отдаёт свой список'`) |
| `_register_fields` | **red** (`форма='запись зовут иначе'`) |
| `_spawns` | **red** (3 forms) |
| `_log_mark_offenders` | **red** (2 forms) |

So the harness does work for the spellings it enumerates, and each revert fails as an
*assertion*, not as an import error.

**Gates checked by violation.** A new source rule added with no entry in `SOURCE_MUTATIONS` →
`SourceMutationTest` red, naming `SOURCE_MUTATIONS` and what to put in it. The promise holds
for the spelling the guard recognises (see R2-005 for one it does not).

**Live.** The NUL consequence was reproduced on a running stand (a fresh git repository with a
tracked Cyrillic-named file and a block declaring `paths: ["src/**"]`) before and after the
mutation — output in R2-001. `roots` and `check` were run on the real tree for R2-003.

**Register.** Every field of `findings.jsonl` was diffed between `e098508` and `HEAD` rather
than read from the report; the two records that gained a claimed guard were then tested by
replaying the findings' own scenarios.

**What was not done.** The environment matrix of the block's acceptance criterion (Python 3.12
*and* 3.14, `LANG=C`, git default branch `main`/`master`) was not re-run in full — only the
`LC_ALL=C PYTHONUTF8=0` cell, which is what this round touched. Only one interpreter (3.14.7)
exists on this machine, so the 3.12 cell cannot be produced here. `axes.py` and `run-role.sh`
were not exercised against real `claude` streams.

## Findings

### R2-001 · medium · The NUL rule is still blind to two more spellings, and the whole suite stays green with `-z` dropped

**Location:** `tests/test_review.py:5657` (`SourceRuleTest._nul_offenders`), table entry
`SOURCE_MUTATIONS["_nul_offenders"]` at `tests/test_review.py:6556`

**What is wrong:** `_nul_offenders` now reads argv through `_Values.built_lists()` — but
`built_lists` collects only lists that reach a name through `Assign`/`AugAssign`/`AnnAssign`,
plus list/tuple/`+` expressions. An argv grown with the list **methods**
(`cmd = ["git", "-C", str(ROOT)]; cmd.extend([...])`) and an argv returned by a **wrapper
function** (`def _git(*rest): return ["git", "-C", str(ROOT), *rest]`, called as
`_git("ls-files", "--stage")`) are both invisible: in each case the surviving literal holds
`git` but no name-asking option, so the rule skips it and never asks for `-z`.

**Failure scenario** (measured twice, on the real tool, whole suite each time):

1. `untracked_files` (`review.py:376`) rewritten as
   `cmd = ["git", "-C", str(ROOT)]` /
   `cmd.extend(["ls-files", "--others", "--exclude-standard", "--", *specs])`,
   `-z` dropped, `splitlines()` for `split("\0")` → `_nul_offenders` returns `[]`,
   **`Ran 330 tests in 402.773s / OK`**.
2. `index_rows` (`review.py:343`) — the function every block's file set, every coverage row
   and every block fingerprint goes through — rewritten as `cmd = _git("ls-files", "--stage")`
   with the repeated prefix hoisted into a one-line wrapper, `-z` dropped, `splitlines()` →
   `_nul_offenders` returns `[]`, **`Ran 330 tests in 380.633s / OK`**.

Live consequence of (2), on a fresh stand with a tracked `src/крыша.txt`:

~~~
### HEAD (-z present)             ### MUTANT (_git wrapper, no -z)
coverage.tsv:                     coverage.tsv:
  src/plain.txt     B1              "src/\320\272\321\200\321\213\321\210\320\260.txt"  B1
  src/крыша.txt     B1              src/plain.txt     B1
~~~

`coverage.tsv` — the on-disk contract other commands read back — names a path that does not
exist, C-quoted, with the quote characters inside the value. `coverage` exits 0, "no unowned
files", no gate fires, no test.

**Why it is a defect:** invariant 5 (paths are handled NUL-separated) and invariant 2 (a
mechanism that can be disabled while the suite stays green is untested). The round's stated
principle — *read the value where it is BUILT, not where it is written* — is not achieved:
`built_lists` reads where a value is **assigned**, which is one more spelling rather than the
building site. Method mutation is not exotic here: `_gate_messages`, in the same file and the
same commit series, treats `.extend()` as a spelling that must be expected.

**Introduced by this round or present before:** the blind spot is older (both spellings were
invisible before this round too). What this round introduced is the claim — in the fix report
and in both changelogs — that the class is now proved by mutation of the real source.

**Confidence:** confirmed
**Root:** class guard keyed on incidental syntax

### R2-002 · medium · The gate registry recognises the refusal list by the variable's name, so a new gate in a helper needs no entry and no test

**Location:** `tests/test_review.py:4735` (`_gate_messages`), `tests/test_review.py:4836`
(`_refuse_unknown_spelling`)

**What is wrong:** `_check_gates` was widened to walk the whole module instead of only
`cmd_check`, but both `_gate_messages` and `_refuse_unknown_spelling` still test
`node.value.id in ("problems", "warnings")`. The name of a local variable is exactly the kind
of incidental syntax this round was sent to stop keying on — `_register_fields` was rewritten
in the *same commit* to recognise a register record by its own fields rather than by the
variable being called `f`, and the same reasoning was not carried here. Every respelling in
`SOURCE_MUTATIONS["_check_gates"]` and every sample in `SPLIT_OUT_GATES` keeps the parameter
named `problems`.

**Failure scenario** (measured): a **new** gate added to the tool as a module-level helper —

~~~python
def _reserved_role_gate(b, refusals) -> None:
    if b.get("role") == "__never__":
        refusals.append(f"{b['id']}: role `__never__` is reserved")
~~~

— called from `cmd_check` right after `problems: list[str] = []`. `_check_gates` gives it no
key, `_refuse_unknown_spelling` raises nothing, `GateRegistryTest` is green (the 63 existing
keys still match `GATES` exactly), and **`Ran 330 tests in 389.570s / OK`**. The gate has no
`GATES` entry, no named test, and can be deleted later with the suite green — T3-017's
scenario, recorded as fixed, reproduced by renaming one parameter. Fed the honest tool with
every gate moved into such a helper, `_check_gates` returns **0 of 63** gates for parameter
names `refusals`, `errors` and `out`, and raises no `UnknownGateSpelling`.

**Why it is a defect:** invariant 2. The two halves behave differently and only one is a hole:
moving an *existing* gate fails closed (its key vanishes, `extra` is non-empty, the registry
goes red — though with the misleading message *"the gate was rewritten — check the test
against the new wording"*, whose cheapest resolution is to delete the `GATES` entry). Adding a
*new* gate that way fails **open** and silent. That is the defect.

**Introduced by this round or present before:** the name-keying predates the round; the round
widened the walk's scope and reported the class closed, which is what makes this a finding now
rather than a restatement of T3-017.

**Confidence:** confirmed
**Root:** class guard keyed on incidental syntax

### R2-003 · medium · The round wrote a guard onto two open findings of other blocks that the guard does not hold, and named neither in its report

**Location:** `docs/review/findings.jsonl` — records `T2-016` and `T4-021`

**What is wrong:** besides the four T3 findings it was sent to close, the round added
`"rule": "tests/test_review.py::SourceMutationTest"` to **T2-016** and **T4-021** — both
`status: open`, both belonging to other blocks. Neither is held by that guard, and neither is
named in the fix report: its *Register* line lists only T3-016/017 (`SourceMutationTest`),
T3-018 (`TestSuiteRuleTest`) and T3-019 (`--fixed-in`). Nothing in
`T3-tests.fixreview-1.md` asked for these writes either. `SOURCE_MUTATIONS` contains exactly
ten rules — `_bare_numbers`, `_check_gates`, `_log_mark_offenders`, `_msg_tables`,
`_name_as_pattern`, `_nul_offenders`, `_quote_offenders`, `_register_fields`,
`_rules_without_samples`, `_spawns` — and neither finding's mechanism is among them.

**Failure scenario** — each finding's own recorded scenario, replayed:

* **T4-021** — the `Run the tests` step deleted from `.github/workflows/tests.yml`, so CI no
  longer runs the suite at all: `SourceMutationTest` → `Ran 2 tests in 61.470s / OK`. Its
  mechanism, `test_каждые_объявленные_ворота_гоняет_ci`, reads workflow YAML inline in the
  test body and is not a source rule at all.
* **T2-016** — every fenced draft schema cut out of the role templates (6 files changed):
  `SourceMutationTest` → `Ran 2 tests in 54.219s / OK`. The guard proves `_register_fields`
  reads the tool's field vocabulary robustly; T2-016 is about the *template* side, where prose
  satisfies the check.

What a lead now reads on the real tree:

~~~
$ python3 skills/finetooth/scripts/review.py roots
   7 × class guard keyed on incidental syntax  — guard: tests/test_review.py::SourceMutationTest
       T3-002  fixed …   T3-012  fixed …   T3-014  fixed …
       T2-016  open   tests/test_review.py:6062
       T4-021  open   tests/test_review.py:5233
       T3-016  fixed …   T3-017  fixed …
~~~

The next fixer of T2 or T4 reads the `rule` field of its own finding, believes a guard exists,
and closes it without writing one.

**Why it is a defect:** this is the class T4-020 named and left **open** — *"a class recorded
as closed by a guard that does not close it"* — now committed onto two more records, from
outside the block being fixed. It also breaks fix-review rule 6 (an incidental change not
named in the report). Nothing catches it: the root gate is satisfied as soon as *any* instance
in a class carries a rule, and T3-002 already did, so `check`'s colour does not move.

**Introduced by this round:** yes.
**Confidence:** confirmed
**Root:** a class recorded as closed by a guard that does not close it

### R2-004 · medium · The rewritten `--format=` recognition lost a second parser the previous rule caught

**Location:** `tests/test_review.py:5829` (`SourceRuleTest._log_mark_offenders`),
`tests/test_review.py:281` (`_Values.flows_into`)

**What is wrong:** the rule that forbids reading the `git log` record marker outside
`log_records` used to exempt a *placement* by line number (`placed = {n.lineno for JoinedStr
containing "--format="}`). It now exempts it by value flow: `not vals.flows_into(n,
"--format=")`. `flows_into` walks up the parent chain and returns True as soon as **any
enclosing expression's source text contains `--format=`** — so a second parse written in the
same expression as the format string is exempted along with the placement.

**Failure scenario** (measured, fed to both rules directly):

~~~python
def churn(root):
    return subprocess.run(["git", "log", f"--format={LOG_MARK}%H"],
                          capture_output=True).stdout.split(LOG_MARK)
~~~

* round-1 rule (reverted copy): `[('churn', 6)]` — **caught**
* round-2 rule (HEAD): `[]` — **silent**

Split across two statements (`out = subprocess.run(...).stdout` then
`return out.split(LOG_MARK)`) the round-2 rule does catch it: `[('churn', 7)]`. So the loss is
specifically the compact one-expression form — the form a helper like this is normally written
in, and the form `log_records` exists to prevent.

**Why it is a defect:** this is a guard narrowed by a fix. The class it guards is named in the
project invariants as one that already broke twice — *"fingerprint parsers that diverged (two
parses of one section)"*. A second parser of the `git log -z` stream written compactly now
enters the tool with the suite green, and the two parsers drift apart exactly as before. The
mutation table does not notice, because its spoil (`_second_log_parser`) writes the second
parser as a **separate function with no `--format=` in it**, which both rule versions catch.

**Introduced by this round:** yes — this is a regression of `ce888ed`.
**Confidence:** confirmed
**Root:** class guard keyed on incidental syntax

### R2-005 · low · The guard over the guards recognises "a real source" by a three-string marker list, so a rule fed the tool by path escapes the mutation table

**Location:** `tests/test_review.py:5922` (`SourceRuleTest.SOURCE_MARKS` /
`_rules_without_samples`), used by
`SourceMutationTest.test_у_каждого_правила_по_исходнику_есть_таблица_мутаций`

**What is wrong:** the round's new meta-guard decides whether a rule is "fed a real source"
by looking for one of three literal strings in the argument's resolved text:
`("SOURCE", "TOOL.read_text", "__file__")`. Any other way of naming the same file is
invisible, and then the rule needs neither an invented sample nor a mutation-table entry.

**Failure scenario** (measured, on invented sources):

| how the rule is fed the tool | `reading` → needs a table? |
|---|---|
| `_new_rule(TOOL.read_text(encoding="utf-8"))` | `['_new_rule']` → yes |
| `src = (KIT / "skills/finetooth/scripts/review.py").read_text(...)` | `[]` → **no** |
| `src = (SKILL / "scripts" / "review.py").read_text(...)` | `[]` → **no** |

The second and third spellings are not invented idioms: `tests/test_review.py:36` defines
`TOOL` itself as `SKILL / "scripts" / "review.py"`. A contributor who writes the path out —
for instance to read a *second* file the tool ships — gets a rule proved by nothing, and the
suite stays green. The round's report states the meta-guard "covers rules nobody has written
yet"; it covers those written one particular way.

**Why it is a defect:** invariant 2, one level up. Rated low on the same scale as T3-014 (a
guard that misses a plausible spelling of something not yet written): the ten rules that exist
today are all in the table, so nothing is currently unproved by it.

**Introduced by this round or present before:** `SOURCE_MARKS` came in with round 1
(`f8007b3`); this round made it load-bearing for the mutation table.

**Confidence:** confirmed
**Root:** class guard keyed on incidental syntax

## Checked and found correct

* **The mutation harness itself is real, not decorative.** Five of the ten rules were reverted
  to their `e098508` shape and every one reddened `SourceMutationTest` with an assertion (not
  an import error) naming the form that broke. The fourth assertion — *spoiled and respelled
  must say exactly the same thing* — is the right property to test, and it is what actually
  caught the reverts. The meta-guard also holds by violation: a new untabled source rule
  reddens the suite with a message that names `SOURCE_MUTATIONS` and what to write in it.
  This is a genuine advance over "widen the pattern by one more branch".
* **T3-018 is closed properly and in both directions.** Reverting the text to Russian reddens
  the test with the escapes visible in the failure message; the reverted module still imports
  and still refuses, so the redness is about the text and not about a broken module; and
  `test_в_UTF_8_локали_набор_импортируется_молча` guards the other side. The refusal has
  exactly one address — line 49 is the only module-level `raise` in the suite — so rule 5 is
  satisfied.
* **`_register_fields` did not change what it produces.** The report claims the field set is
  unchanged; measured, it is 21 fields and none falls outside the template vocabulary, so
  recognising a record by `RECORD_MARKS` instead of by the variable name neither widened nor
  narrowed the vocabulary.
* **`review_refs` is not an address of R2-001.** T3-012 recorded it as passing the rule while
  splitting with `splitlines()`. On HEAD it runs `git grep -z … --full-name` and splits fields
  on NUL inside newline-separated records (`review.py:1513-1521`) — correct, and the comment
  above it says why.
* **The registry's own numbers hold.** 63 gates in the tool, 63 entries in `GATES`,
  `GateRegistryTest` 7 tests, `check` printing 20 `·` lines — all as the report states.
* **The `_quote_offenders` limitation is disclosed honestly.** The report's *Found, not fixed*
  explains why the rule still recognises a report parser partly by the parameter name `md`,
  and why making it shape-only would redden `read_register`. That reasoning checks out and is
  the right call for a fixer to leave to the lead.
* **Stale line numbers in the report** (`_Values` given as `:186`, actually `:201`;
  `SourceMutationTest` as `:6483`, actually `:6611`) are not counted as a finding: the names
  are correct and resolvable, which is what T4-025 was raised about.

## Is another round needed

**No. The next move is a human's, not another round.**

Five findings: **four medium, one low**. All five sit **inside the code this round changed** —
none outside it. That is the stop condition rule 11 describes, and the history makes it
sharper than a single count:

| round | top finding | location | root |
|---|---|---|---|
| hunter | T3-012 — NUL rule reads one literal | `_nul_offenders` | class guard keyed on incidental syntax |
| fix review 1 | R1-001 → T3-016 — blind to a hoisted prefix | `_nul_offenders` | same |
| fix review 2 | R2-001 — blind to `.extend()` and to a wrapper | `_nul_offenders` | same |

and in parallel, T3-002 → T3-017 → R2-002, all three on the gate registry, all the same root.
Three consecutive rounds, the heaviest finding each time in the same two functions, in one
class. Each round's fix was correct as far as it went and each was proved by a real mutation;
the class still reopens, because "read the value where it is built" keeps being implemented as
one more enumeration of spellings — `built_lists` enumerates assignment forms, `_gate_messages`
enumerates list-mutation forms and one variable name, `SOURCE_MARKS` enumerates three strings.
A fourth round would widen three more enumerations and a fifth reviewer would find the fourth
spelling. That is a loop, not progress.

What a human has to decide — and a fixer must not guess — is whether the tool should stop
being read by pattern at all on these three questions: a marked helper that is the *only* way
to spawn git (so "did it ask for `-z`" is one call site, not a shape), a marked container for
refusals (so a gate is a type, not a variable named `problems`), and a registry of source
rules that rules opt into explicitly rather than being discovered by markers. Each is a change
to the **tool and the suite's structure**, not to a guard — which is outside a fixer's remit
by this round's own reasoning in *Found, not fixed*.

Two things are independent of that decision and can be handled without a round:

* **R2-003** is a register correction, not a code change: drop the `rule` field from T2-016 and
  T4-021, or replace it with a guard that actually reddens under their scenarios. It should be
  done before either block is fixed, since a fixer reading those records will trust them.
* **R2-004** is a two-line regression in `_log_mark_offenders` introduced by `ce888ed` and can
  be fixed by the lead: exempt a `LOG_MARK` use only when the value it flows into *is* the
  `--format=` string, not when any enclosing expression mentions one, and add the compact
  one-expression second parser to the rule's spoil so the table notices next time.

Finally, on the merit of the round: it did make the project better. The suite grew five
scenarios and gained a mutation harness that proves ten rules by spoiling the real source, plus
a meta-guard that refuses an untabled rule — all of which I confirmed by reverting and by
violation. T3-018 and T3-019 are closed cleanly. The problem is not that the round did poor
work; it is that the work it was given cannot be finished by guard-widening, and the machine
has now demonstrated that three times.
