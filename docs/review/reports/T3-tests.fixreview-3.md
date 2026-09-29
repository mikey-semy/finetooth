# T3 — fix review, round 3

## What was checked and how

The diff (237 KB, 3316 lines) was read in full — no `--scope` split was needed.

**Behaviour parity, measured, not read.** Two skill trees were built side by side: `bbc395d`
(the tool as it stood) and HEAD. Both were run over the same stands, output and exit codes
compared line by line.

* A stand with `src/крыша.txt`, `src/имя с пробелом.ts`, `src/[handle]/a.ts` and a plain
  ASCII neighbour, through `init · status · coverage · check · findings · refs · next ·
  coverage · check · summary · prompt --role hunter`, plus the resulting `coverage.tsv` and
  `state.json`: **identical** apart from the tool's own path in a hint and the `updated_at`
  stamp.
* The **real repository** (140 findings, 20 refusals, 4 warnings), through `check · status ·
  findings --dry-run · refs · coverage --no-write · summary · roots · order · coupling`:
  **byte-identical** between the two tools. The refusal order, the warning section, the exit
  codes — all unchanged. Ask (1) of the brief is answered: the user-visible behaviour of this
  refactor is the same, including on non-ASCII paths and on a red register.
* The one path the battery misses, `diff_text` — `prompt T3 --role fixreview --diff <range>`
  on a real range, on an unknown revision and on an empty range: identical stdout hash and
  length, identical exit codes (0 / 2 / 2) and identical refusals on both error paths.

**Fixes proven by reverting** — each revert applied to a copy of the real tool, `ast.parse`
asserted before the run so that "no failures" cannot mean "the copy does not build":

| reverted | result |
|---|---|
| the `-z` that `git()` inserts | `GitTruthTest` **7 failures of 11**, the new Cyrillic coverage test among them |
| the `OSError` branch of `git()` (missing git) | `test_без_git_инструмент_отказывает_а_не_роняет_трейсбек` **red**, `FileNotFoundError` traceback |
| `untracked_files` spawning directly, argv grown with `.extend()` (T3-020's own spelling) | `test_процесс_запускают_в_одном_месте` **red**, names `untracked_files` |
| `cmd_check` printing and returning on its own again | `test_приговор_check_выносит_только_контейнер` **red**, names both exits |

The `-z` result is the round's real gain and it is worth stating plainly: before this round
the same consequence (a C-quoted path in `coverage.tsv`) left the whole suite green; now it
costs seven tests. The property moved from a source rule to behaviour.

**Gates checked by violation, not by reading.** I built my own bypasses and fed them to the
round's three guards straight from the suite's own source, then took the strongest to the real
tool as a mutant and ran the whole suite against it (`FINETOOTH_TOOL`). The baseline was
measured first, so "OK" on a mutant means something: **the honest tree is 334 tests, OK, in
471 s** — the fixer's count and claim both hold. Results in the findings below.

**Register and table checked:** 63 refusal keys in the source, 63 in `GATES`, no duplicates
on either side, exact set match; `test_каждые_ворота…` compares Counters, so a copied key is
caught too. Every `--fixed-in`/`--rule`/`--commit` stamp in `findings.jsonl` was compared
with the diff; the four closed findings are genuinely closed by the commits named.

**Every address searched by hand:** `axes.py` and the `assets/` shell scripts were grepped
for process starts and for `ls-files/--name-only/--name-status/--others/grep` — neither
starts a process nor reads a path list, so `review.py` is the only address of the NUL class.

**What I did not do.** I did not run the full suite on Python 3.12 or under `LANG=C` (the
block's environment matrix belongs to the hunter, and nothing in this diff touches the
locale code). I did not re-run `GateMutationTest`'s 63 mutations one by one — I checked the
table's completeness and the flip mechanism by reading and by the reverts above.

## Findings

### R3-001 · medium · `git()` reads the subcommand out of any argument, so a file named `grep` silently drops out of every fingerprint

**Location:** `skills/finetooth/scripts/review.py:85-87` (`git()`), consumed at
`skills/finetooth/scripts/review.py:478` (`file_sha`)

**What is wrong:** `git()` decides whether to add `-z` with
`any(a in GIT_PRINTS_PATHS for a in rest)` — it scans *every* argument, data included,
instead of the subcommand position. A path argument that happens to equal `grep` (or
`ls-files`) therefore turns an unrelated run into a `-z` run. `git hash-object -z -- grep`
does not exist: git exits 129 with ``unknown switch `z'``, `file_sha` returns `None`, and
`block_sha` folds an empty string in place of that file's contents.

**Failure scenario:** a repository with a tracked file named `grep` at its root (a shell
wrapper — an ordinary thing to have). Measured live, both tools on the same stand, the block
stamped and then each file rewritten in turn:

~~~
### OLD bbc395d
  reviewed_sha stamped: b0ef5ce9d698fceb
  edited 'grep'       -> check notices the change: True
  edited 'plain.txt'  -> check notices the change: True

### NEW HEAD
  reviewed_sha stamped: dd40e8e8c2bb212e
  edited 'grep'       -> check notices the change: False    ← regression
  edited 'plain.txt'  -> check notices the change: True
~~~

The block is rewritten after verification and `check` says the review state is consistent.
The same call is the second address: `file_sha` fills `code_sha` for findings
(`review.py:2065, 2162, 2474, 2600`), so an open finding on that file gets no code
fingerprint — and the gate that would complain, `finding/no-code-fingerprint`, is itself
conditioned on `file_sha(...)` being truthy, so it stays silent too.

**Why it is a defect:** invariant 6 — "a fingerprint that misses part of its subject silently
declares changed code reviewed" — and invariant 1, the gate going green on a state that is
wrong. It is also the named project pattern: the tool trusts the *shape* of a text where it
should parse. The fix is small (look at `rest[0]` and at arguments that start with `-`, or
stop at the first `--`), but it is a decision about `GIT_PRINTS_PATHS`, not a rewrite.

**Introduced by this round or present before:** **introduced by this round** — before it,
`-z` was written out at each call site and `hash-object` never received one.

**Confidence:** confirmed (reproduced live, before and after).

**Root:** — (the only one of its kind in this diff)

### R3-002 · medium · a gate split into a helper that prints its own refusal is invisible to both new guards

**Location:** `tests/test_review.py:4774` (`_own_verdict`), `tests/test_review.py:4735`
(`_check_gates`)

**What is wrong:** `_own_verdict` is introduced by this round precisely to stop "a gate that
printed its own refusal and returned by itself" (`review.py:3027`, the `Refusals.report`
docstring, says so). It looks only inside `cmd_check`:
`fn = next(… n.name == "cmd_check")`, and returns `[]` if the offence is anywhere else. A
gate moved into a module-level helper — the refactor this round's own mutation table
rehearses three ways (`_gates_split_out`) — and written to print and exit on its own touches
the container nowhere, so `_check_gates` sees no gate, `_own_verdict` sees no exit, and the
gate needs no key, no `GATES` entry and no test. It can then be deleted with the suite green,
which is exactly what T3-017 and T3-021 were about.

**Failure scenario:** applied to the real tool — a gate that refuses a reserved role, split
into `_reserved_role_gate(defn)` called from the first lines of `cmd_check`, printing
`CHECK FAILED:` and `sys.exit(1)` itself. The copy parses (`ast.parse` asserted). No rule of
the suite sees it:

~~~
gates counted: 63   (unchanged)      own_verdict: []
spawns: []          log: []          bare numbers: []
~~~

and the guard classes run green on the mutant:

~~~
=== mutant `gate-helper-prints-and-exits`
    -k SourceRuleTest GateRegistryTest SourceMutationTest DocumentedSurfaceTest
    Ran 26 tests in 135.577s
    OK
~~~

The whole suite, measured against a green baseline:

~~~
honest tree, no mutation:                Ran 334 tests in 471.387s   OK
mutant, skill copied to <tmp>/finetooth: Ran 334 tests in 394.068s   FAILED (failures=2)
    the two are test_английское_ревью_получает_английские_образцы and
    test_русское_ревью_получает_русские_образцы — they fail on the UNMUTATED tool under
    the same harness (R3-006 below), not on the gate
mutant, harness corrected:               Ran 334 tests in 389.972s   OK (skipped=3)
~~~

The gate survives the whole suite. Nothing in the kit would notice if it were deleted again.

A second spelling with the same outcome: a refusal pushed onto the container's own list,
`gates.said.append((True, "blocks/reserved-role", "…"))` → `_check_gates` returns `[]`.

**Why it is a defect:** invariant 2 — a mechanism that can be disabled while the suite stays
green is untested — and the block's own definition of a finding: "a guard that a plausible
new shape of code walks past".

**Introduced by this round or present before:** the guard `_own_verdict` is **introduced by
this round**; the hole it leaves is the third re-appearance of the class it was written to
close.

**Confidence:** confirmed (measured on the real tool, guard classes green).

**Root:** class guard keyed on incidental syntax

### R3-003 · low · the spawn rule recognises `subprocess` only as an import name, not as a value

**Location:** `tests/test_review.py:5611` (`SourceRuleTest._spawns_outside_git`)

**What is wrong:** the rule collects module aliases from `import subprocess as X` and names
from `from subprocess import run`, then matches `<alias>.<spawner>` and `<name>(…)`. A module
bound by an ordinary assignment, or a spawner bound to a name, is not a spelling it knows —
and the round's whole argument is that the question is now the *fact* of a spawn, not how it
is written.

**Failure scenario:** fed to the rule directly (all three silent, `[]`):

~~~
sp = subprocess            →  def churn(): sp.run(["git","log","--name-only"])      → []
P  = subprocess.run        →  def churn(): P(["git","log","--name-only"])           → []
getattr(subprocess,"run")  →  def churn(): getattr(subprocess,"run")([...])         → []
~~~

Applied to the real tool as `untracked_files` spawning through `_sp = subprocess` with the
`-z` dropped and the output split on newlines, the rule stays silent. The live consequence is
smaller than it was in round 2 — `untracked_files` is the one reader whose caller prints a
count, not the paths, so nothing else notices — but a *new* reader written the same way would
have neither a guard nor a behaviour test.

**Why it is a defect:** invariant 2, and the block's "a guard that a plausible new shape of
code walks past". Weighted down to low because the seven behaviour tests added this round now
hold `-z` for every existing reader, so this is a hole in the backstop, not in the property.

**Introduced by this round or present before:** introduced by this round (the rule is new).

**Confidence:** confirmed.

**Root:** class guard keyed on incidental syntax

### R3-004 · low · the history rule recognises `git log` only as a literal first argument

**Location:** `tests/test_review.py:5847` (`SourceRuleTest._log_stream_outside_reader`)

**What is wrong:** the rule's second half —"is `git log` ordered outside `log_records`" —
tests `isinstance(n.args[0], ast.Constant) and n.args[0].value == "log"`. The same file reads
a command name *where it is built* two hundred lines further down
(`DocumentedSurfaceTest.subcommands`, changed by this round for exactly that reason, using
`_Values.literal`); this rule does not.

**Failure scenario:** a second reader of the history stream whose subcommand comes from a
module constant, or is splatted, is silent:

~~~
_LOG = "log"
def churn(paths): return git(_LOG, "--name-only", "--", *paths).out.split("\n")   → []
args = ["log", "--name-only"]; git(*args)                                         → []
~~~

Such a reader gets an unmarked `-z` stream and meets the newline-glue trap `log_records`
exists for — the drift over-count that `summary --aged` had. (The marker half of the rule is
sound: any `LOG_MARK` read outside `log_records` is caught.)

**Why it is a defect:** invariant 2; and the inconsistency with `subcommands` in the same
round's diff means one rule is proved against the class and the other is not.

**Introduced by this round or present before:** introduced by this round.

**Confidence:** confirmed.

**Root:** class guard keyed on incidental syntax

### R3-005 · low · the gate registry reads the standard library's `warnings.warn` as a 64th gate

**Location:** `tests/test_review.py:4735` (`_check_gates`), `tests/test_review.py:4723`
(`GATE_VERBS`)

**What is wrong:** the rule matches *any* attribute call named `refuse` or `warn` anywhere in
the tool, whatever the object owns it. That widening is right for the container and it is what
closes T3-021; but nothing tells the container apart from anything else with a `warn`, and in
a standard-library-only tool the obvious other owner is `warnings`. The reverse side of rule 3
— what is still allowed must still pass — is not held: `test_чтение_отказов_воротами_не_считается`
covers *reading* the container, and nothing covers a same-named method on another object.

**Failure scenario:** one ordinary stdlib line added to the tool, measured against the real
source and the real `GATES` table:

~~~
real tool + `warnings.warn("coupling is experimental")` in cmd_check:
  gates counted: 64
  missing from GATES: ['coupling is experimental']      ← test_каждые_ворота… red

and with a computed message:
  GateWithoutKey: cmd_lint, строка 3: отказ добавлен без ключа-литерала
  (`warnings.warn(f'{path} is experimental')`) — реестру нечем назвать эти ворота…
~~~

A contributor who deprecates a flag with `warnings.warn` is told to give their line a gate key
and register a test for it, about something that is not a gate; with an interpolated message
the whole guard class errors out instead.

**Why it is a defect:** rule 3 of this review — a fix that narrows or widens something needs a
test that what is allowed still passes. Low, because it costs a future contributor a puzzle,
not a wrong review state; but it is the one place where this round's widening overshot, and it
is cheap to hold (the container is a known type — ask whether the receiver is a `Refusals`).

**Introduced by this round or present before:** introduced by this round.

**Confidence:** confirmed (measured on the real source and the real table).

**Root:** —

### R3-006 · low · two tests require the skill to be installed under a directory literally named `skills`

**Location:** `tests/test_review.py:7385` (`named_assets`), used at
`tests/test_review.py:7387` and `7410`

**What is wrong:** `named_assets` finds the assets `setup` names with the regex
`/skills/finetooth/assets/([\w.\-]+)`. The kit's own contract (AGENTS.md: "the skill lives
apart from the repository under review — in its `.claude/skills/`, in the home directory,
**anywhere**") does not promise that parent segment. Both tests then `assertTrue(named)`, so
an installation the kit explicitly allows turns the assertion into a failure about nothing.

**Failure scenario:** the **unmutated** tool, copied to two shapes and run through
`FINETOOTH_TOOL`:

~~~
honest tool copied to <tmp>/finetooth:        Ran 2 tests  FAILED (failures=2)
honest tool copied to <tmp>/skills/finetooth: Ran 2 tests  OK
tool in place:                                Ran 2 tests  OK
~~~

The first shape is not hypothetical: it is the shape the suite's own mutation harness uses —
`GateMutationTest._run_on_copy` copies to `Path(d, SKILL.name)`. The two tests are therefore
red inside every gate mutation the suite runs, and nobody sees it only because that harness
runs one named test per mutant. Anyone doing what this block asks for — a whole-suite run on a
mutant — reads two failures that are the harness's, and may take them for a killed mutant.

**Why it is a defect:** the block's own wording — "a test that depends on the machine
(Python version, locale, git version, `/tmp`, network, the kit's own repository state) and
would go red elsewhere". Here it is the install path.

**Introduced by this round or present before:** **present before** — neither test nor
`_run_on_copy` is touched by this diff. It surfaced because this is the first round to run
the whole suite against a mutant.

**Confidence:** confirmed.

**Root:** —

## Checked and found correct

* **`GIT_PRINTS_PATHS` and the `-z` position.** `rest.insert(1, "-z")` puts the option after
  the subcommand and before any `--` for every converted call site — twenty of them, not the
  twenty-two the fix report counts; the count is wrong, the conversion is not (the spawn rule
  answers `[]` on the real tool, so `git()` is the only spawner). I compared the resulting
  argv with the pre-round argv for each of them, and the option sets are equivalent
  (`ls-files -z --stage` vs `ls-files --stage -z`, `log -z --format=… --name-status` vs
  `log --name-status -z … --format=…`). The one thing the position does not survive is a *data*
  argument that looks like a subcommand — R3-001, and that is the collision, not the position.
* **`log_records(*args)` writing its own `--format`.** Every caller was checked: both pass a
  path-printing option, so the `-z` the helper adds is always present and `.fields` is a real
  NUL split. A call with neither would silently read a newline stream; there is none today and
  the rule forbids a second caller of `git("log", …)`, so I did not raise it.
* **`review_refs` through `GitRun.records`.** The record layout (`path NUL line NUL text`) is
  unchanged from the hand-rolled `partition` pair, and the `(record + ["", ""])[:3]` guard
  genuinely removes a traceback on a short record. Both `refs` tests go red under the `-z`
  revert, so the fields are held by behaviour.
* **`stale_tree` moved from `git log -1 --format=%ct` to `git show -s --format=%ct`.**
  Equivalent for a single revision, and it is what lets `log_records` be the only caller of
  `git log`. Named as an incidental fix with its mutation; `FreshnessGateTest` holds it.
* **The incidental-fix list is complete.** I diffed the round's six declared incidental fixes
  against the whole diff looking for a seventh; the only unlisted changes are the mechanical
  consequences of the three entry points (the move of `die()` above `git()`, comment rewrites,
  the scenario count in four documents). Nothing is fixed that the report does not name.
* **The register stamps.** T3-020/021/023/024 are marked `fixed` with `--commit c0ee0ec`,
  `--fixed-in skills/finetooth/scripts/review.py`, `--rule …SourceMutationTest`; `c0ee0ec` does
  touch that file, the rule does exist, and T3-022 is left `deferred` with its reason intact.
  The three T2 findings the round says it made stale (T2-017/018/021) are indeed on
  `review.py` and indeed newly stale — the report disclosing that unprompted is the right call.
* **63 gate keys.** Unique, exactly matched to `GATES`, compared by Counter so a duplicated key
  is caught, and every named test exists. The keys are a genuine improvement over message
  skeletons: they do not move when a message is reworded, which is what reddened CI in T1.

## Is another round needed

**No — and the reason matters more than the answer.**

Six findings: **2 medium, 4 low.** Rule 11 would call a medium a reason for another round.
Here is why it is not.

Four of the six (R3-002…R3-005) sit **inside the code this round changed**, and three of them
carry one root: *a class guard keyed on incidental syntax* — the same root as T3-016, T3-017,
T3-020, T3-021, T3-023, T3-024. This is the **fourth round running** in which the heaviest
finding of the block is that root, and the third in which the answer was "the guard now asks
the fact, not the form" — and each time the next form was found within the hour. The round
before answered with a longer list of spellings; this round answered with a single entry point,
which is a genuinely better answer — and a guard over a single entry point is still a
recognition rule, and recognition rules are what this loop consumes. By the practice the brief
names, the next move here is a **human's decision about how much guard is enough**, not another
fixer round. My recommendation: accept R3-003, R3-004 and R3-005 as known limits of the guards,
record them in the block's "Coverage limits" rather than fixing them, and spend nothing more on
widening recognition.

R3-002 is the one I would not simply file away, because it is not about a spelling of argv but
about a gate that touches the container nowhere at all — and `_own_verdict` was written this
round to catch exactly that, and looks in one function. Extending it from `cmd_check` to every
function reachable from it is a small, bounded change, not another widening of a pattern; it is
the sort of thing the lead can direct without a round.

**R3-001 is outside the guard class and outside the loop**, and it is the one thing here that
changes what the tool does to a user: a fingerprint that silently stops covering a file. It is
a one-line decision in `git()`. It should be fixed, and it does not need a round of its own —
the fixer or the lead can close it directly.

**Of the findings above: 4 inside the code the previous round changed, 2 outside it** (R3-001, a live regression in `git()`; R3-006, a path-dependent pair of tests that predates the round).

What the round got right, said plainly: the behaviour is provably unchanged, on the real
register and on awkward paths; `-z` stopped being a promise held by a source rule and became a
property held by seven behaviour tests; 63 gates acquired stable names that survive a reworded
message; and the report's own "Found, not fixed" section named three consequences (the
`restamp` convergence problem, the stale T2 findings, `untracked_files` having no observable
NUL consequence) that a less honest report would have left for me to find.
