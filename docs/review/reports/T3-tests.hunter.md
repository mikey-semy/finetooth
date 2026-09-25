# T3 — hunter report

## Coverage

- files read: 1 of 1
- the list of files read by name:

tests/test_review.py

- context files read in full (not in this block's coverage, read to judge what the tests hold):

skills/finetooth/scripts/review.py
skills/finetooth/scripts/axes.py
skills/finetooth/assets/run-role.sh
skills/finetooth/assets/guard-grep.sh
.github/workflows/tests.yml

- read in part: `CONTRIBUTING.md` (the promise under test, lines 10–18 and 38–41),
  `docs/review/findings.jsonl` (the ids, claims and roots already recorded, to avoid filing
  the same class twice).
- not read: nothing in the block's own file list.

## Hypotheses

- T3.1 — not checked: the block's artefact is a mutation run, and this session cannot execute anything — every `python3` invocation is refused by the permission layer (only `python3 --version` was allowed), and the session is non-interactive, so approval cannot be granted. What stands below instead is a static survivor analysis: for each mechanism outside `cmd_check` I looked for a test that could reach it and recorded a survivor only when, by reading, none can. Nine of the twelve findings are such survivors; that is weaker evidence than a red suite, and the acceptance criterion's mutation table is therefore **not** delivered.
- T3.2 — checked: four tests assert only that `check` does NOT print a message, with no positive control and with `Stand.commit`/`Stand.git` swallowing git's exit code, so a fixture that never reaches the state guarantees the assertion (T3-007); and the `claude` stub makes the test named "a successful run is written as an ordinary line" accept a `NO RESULT EVENT` measurement (T3-010).
- T3.3 — checked by reading rather than by the matrix run: the locale is pinned in `Stand.run` alone while twelve other subprocess sites inherit it (T3-008), and the developer's global git config is not isolated (T3-009). No dependence on the git default branch was found — every push in the suite is an explicit `HEAD:refs/heads/master` — no Python ≥ 3.13-only API is used, the one known interpreter dependence (`ast.unparse` quote style) already carries a fallback, and the kit's own `docs/review/` is guarded by a byte comparison at tests/test_review.py:1933.
- T3.4 — checked: three blind spots, each provable from the guards' own predicates — `GateRegistryTest` sees only `problems.append(...)`, so a gate written with `extend`/`+=` needs neither entry nor test (T3-002); its gate→test mapping is never exercised, so any existing test name satisfies it (T3-003); and the NUL-path rule inspects list literals, so factoring out the repeated `["git", "-C", str(ROOT)]` prefix blinds it (T3-011). `QuotationMapTest` I could not fault: it holds behaviour, in both directions, on ten cases.
- T3.5 — checked: no fixture path contains `[`, so the `:(literal)` magic that exists because git-pathspec reads `[handle]` as a character class can be deleted with the suite green (T3-012), and the Stand inherits the machine's git configuration (T3-009). The layouts the hypothesis suspected ARE covered: a nested `.git` and a real submodule (184), a symlink and a re-pointed symlink (213), a file live in the index but absent from disk (2801), paths with a space and with Cyrillic letters (1533, 2841).
- T3.6 — checked: the stub emits one assistant event and no `result` event at all, so every `run-role.sh` test exercises the `NO RESULT EVENT` branch of `axes.py` and none exercises the ordinary one (T3-010); the real streams kept under `$TMPDIR/finetooth-runs` could not be opened from this session — see coverage limits.

## Tree freshness

`git fetch` was run; `git log HEAD..origin/dev` is empty, so the working copy is level with
the main branch. HEAD is `2e7c39f` on `review/t2`, two commits ahead of `origin/dev`
(both of them review manifests). Everything below was read at that revision; the tool file
was read from the working tree, which equals `origin/dev` for both files concerned.

## Coverage limits

- **The block's acceptance criterion is not met, and this is the most important line of the
  report.** Neither artefact exists: no mutation table produced by running, and no
  environment matrix (Python 3.12 / 3.14, `LANG=C`, `init.defaultBranch` main/master). The
  cause is not the tree but the session: `Bash` refuses every `python3` call here
  (`python3 -m unittest discover -s tests`, `python3 -c "print(1+1)"` and
  `python3 skills/finetooth/scripts/review.py version` were all denied), the session is
  non-interactive, and there is no approval path. The block cannot be closed on this report;
  it needs a session that may run the suite. Concretely, what has to be run is:
  `python3 -m unittest discover -s tests` once per mutation, and the same under
  `LANG=C LC_ALL=C`, under Python 3.12, and with `git config --global init.defaultBranch main`.
- Every "the suite stays green" statement below is therefore **derived, not observed**. The
  method was: locate the mechanism in the source, then search the whole test file for any
  test that could reach it (fixtures, argv, assertions), and call it a survivor only when
  none can. Where the outcome depends on runtime behaviour I could not observe — the locale
  failures, the global-config failures — the finding is marked `plausible`.
- I did not verify that the baseline suite is green today. Every survivor claim assumes it is.
- The real `claude` streams the manifest points at could not be compared: the sandbox refuses
  to list or read outside the working directory, and `/tmp/finetooth-runs` does not exist here.
  So T3-010 rests on the stub's source and on `axes.py`, not on a real stream.
- The role templates (`skills/finetooth/references/*.md`) were not read. Four tests assert
  literal substrings in them (1034, 1043, 1064, 1082); I judged the shape of those assertions
  only, not whether the quoted rules are the rules the templates should carry — that is T2's
  subject.
- I did not examine flakiness or timing: the two `time.sleep(1.1)` calls (3097, 3117), whether
  the suite is safe to run in parallel, and the ~1 minute runtime are all untouched.
- `skills-ref validate` was not run (same execution block), and I did not check whether CI is
  currently green.
- The examples tree (`examples/toy/`) and the CI workflow's second job were read only as
  context for the matrix question; no finding was hunted there.

## Findings

### T3-001 · medium · the "no traceback" class guard runs 3 of 23 subcommands
**Location:** `tests/test_review.py:3059`
**What is wrong:** The guard that exists so that a NEW subcommand falls under the rule
automatically passes one fixed argv to every command; argparse rejects that argv for 20 of
the 23, so their bodies never execute and the guard asserts the absence of a traceback from
argparse's own usage error.
**Failure scenario:** tests/test_review.py:3070 runs `review <cmd> H1 s.md` for every name
taken from `--help`. Only `set-status`, `set-finding` and `log` declare two positionals; for
`check`, `init`, `coverage`, `prompt`, `import`, `hypotheses`, `restamp`, `roots`, `summary`,
`coupling`, `order`, `refs`, `findings`, `sizes`, `inventory`, `backfill`, `status`, `next`,
`setup`, `version` argparse exits 2 with "unrecognized arguments" before `cmd_*` is entered.
Add a command that reads `b["phase"]` on a hand-broken definition and it raises `KeyError`
with exit 1 — the guard stays green, and the class it was written to close (T1-010,
"hand-edited input reaches the code unvalidated") is open again.
**Why it is a defect:** Invariant 12 (a traceback reaching the user is a defect regardless of
cause) and the guard's own docstring: "the list of subcommands is taken from the tool itself,
so a new command falls under the rule without editing the test".
**Confidence:** confirmed
**Root:** guard enumerates its subject without exercising it

### T3-002 · medium · GateRegistry sees only `problems.append(...)`
**Location:** `tests/test_review.py:3925`
**What is wrong:** `_check_gates` matches exactly one syntactic shape — `ast.Call` whose
`func.attr == "append"` on a `Name` called `problems`/`warnings`. A gate that appends in any
other shape produces no key, so it needs no registry entry and no test, and the registry is
green.
**Failure scenario:** write in `cmd_check` either `problems += [f"{bid}: …"]` or
`problems.extend(finding_problems(rows))` — both natural next to the existing code, and the
second is the obvious way to split a 500-line function. `_check_gates` yields no key for it,
`in_source - registered` stays empty, `test_каждые_ворота_check_записаны_вместе_со_своим_тестом`
passes. The new gate can then be silenced entirely with the whole suite green — the state the
registry was measured into existence to prevent (T1-007: 24 gates, all mutable in silence).
**Why it is a defect:** The registry is the kit's guard for the root "a gate that cannot go
red" (4 instances in the register); a guard that a two-character change walks past does not
close its class.
**Confidence:** confirmed
**Root:** class guard keyed on incidental syntax

### T3-003 · medium · the gate→test mapping in GATES is never exercised
**Location:** `tests/test_review.py:4034`
**What is wrong:** `GATES` pairs every gate with the test that is supposed to go red when the
gate is silenced, but nothing ties the two: one test compares key counters against the source,
the other only looks the test name up in `globals()`. A gate can be registered against a test
that never touches it.
**Failure scenario:** add a gate to `cmd_check`, run the suite, read "gate without an entry in
GATES: write a test", and — the cheapest way to green — copy the neighbouring line's test name
into the new entry. `test_каждые_ворота_check_записаны…` sees a matching counter,
`test_каждый_названный_тест_существует` finds the name in `globals()`, both pass. The register
now records the gate as held; silencing it changes nothing in the suite. Today's 64 entries
look sound (I traced a dozen of them), so this is the next one, not a present miscount.
**Why it is a defect:** SECURITY.md's own class: a check that goes green on a state that is
wrong. The registry's docstring promises "the gate is listed together with the test that goes
red when it is removed", and that half is unverifiable as written.
**Confidence:** confirmed
**Root:** guard enumerates its subject without exercising it

### T3-004 · medium · nothing compares the two halves of the MSG table
**Location:** `tests/test_review.py:2250`
**What is wrong:** `T()` indexes `MSG[lang][key]` directly, the invariants name a string that
exists in one language and not the other as a defect that raises `KeyError` at run time — and
no test compares the key sets. Several keys sit on paths no test reaches, so deleting a
translation leaves the suite green.
**Failure scenario:** delete `MSG["ru"]["refs_cut"]`. No test gives a block more than
`REF_LIST_LIMIT = 80` ref_paths, so `render_refs` never takes that branch and the suite is
green. A Russian-language project whose block has 81 context files then gets
`KeyError: 'refs_cut'` and a traceback from `review prompt` — the command that hands an agent
its assignment. The same holds for `vol_more` (needs a volume above twice the ceiling; the
7000-line fixture at 283 stops just short), `sum_seams` (needs `coupling.tsv` present when
`summary` runs) and `f_invariant` (needs a finding with an `invariant` field — no draft in the
suite has one).
**Why it is a defect:** Invariants: "a string that exists in one language and not the other is
a defect (`T()` raises `KeyError` at run time, not at import)", plus invariant 12 on tracebacks.
**Confidence:** confirmed

### T3-005 · medium · invariant 11's promises for `backfill` and `set-finding` have no test
**Location:** `tests/test_review.py:611`
**What is wrong:** `IdempotenceTest` covers `init`, `restamp` and `import`, and the invariant
lists `backfill` beside them and demands `set-finding` over several ids be all-or-nothing.
`backfill` is run exactly once in the whole suite, and the multi-id path is tested only where
it succeeds.
**Failure scenario:** delete the `if not stamped_blocks and not stamped_findings: return 0`
early exit from `cmd_backfill` (review.py:2478): every re-run then rewrites `state.json` and
appends another journal line, and no test notices, because line 611 runs `backfill` once on a
state that needs stamping. The CI gate of the documented shape — regenerate, then require a
clean tree — goes red on a correct state, which is the failure `IdempotenceTest` was written
for. Separately, move the register write inside the loop of `cmd_set_finding` (review.py:2126):
`set-finding H1-001 H1-999 deferred --reason x` then leaves H1-001 written and H1-999 refused,
and the suite stays green — no test passes an unknown id among several.
**Why it is a defect:** Invariant 11 names both mechanisms by name.
**Confidence:** confirmed

### T3-006 · low · mechanisms outside `cmd_check` with no test at all
**Location:** `tests/test_review.py:3600`
**What is wrong:** The gate-coverage effort stopped at `cmd_check` (`GateCoverageTest`,
`GateRegistryTest`). Outside it, these mechanisms are reachable by no test and can each be
deleted with the suite green.
**Failure scenario:** `import`'s cap is tested for `scenario` only (1188, 701 characters), so
removing `claim` from the same loop (review.py:1888) lets a 300-character claim through import
and makes `check` red for ever — the very defect R5-005 recorded. `block_risk`'s refusal
(review.py:1206) has no test: drop it and an invalid `risk` reaches `SEVERITIES.index` as a
`ValueError` traceback from `order`. `review_lang`'s `if lang in LANGS` (review.py:253) has no
test either, and no gate in `check` validates the field, so a hand-written `"lang": "ru-RU"`
today silently yields English prompts and, without the guard, a `KeyError`. `cmd_next` is
never run by any test. `restamp`'s refusal on a finding whose file is gone (review.py:2349),
`coupling`'s `min_share`/`min_together` filters (no fixture has a pair they exclude),
`inventory --under/--unassigned`, and `guard-grep.sh`'s `--exclude`, `--skip` and window bound
are all unexercised.
**Why it is a defect:** CONTRIBUTING: "every new check comes with a test, and the test is
proven by mutation". The register already carries this for `cmd_check` (T1-007); outside it the
gap was never measured.
**Confidence:** confirmed

### T3-007 · medium · four gates proven only by the absence of a message
**Location:** `tests/test_review.py:1533`
**What is wrong:** These tests assert only that `check` does not print a particular string,
without asserting the state they depend on; and `Stand.commit`/`Stand.git` (60, 51) call git
with `check=False` and never look at the exit code. A fixture that silently fails to reach the
state makes the assertion true.
**Failure scenario:** `test_путь_с_пробелом_не_ломает_проверку_коммита` (1533) never checks
that `set-finding … fixed --commit` returned 0. Make `set_one_finding` refuse any path
containing a space: the finding stays `open`, `check` has no reason to print "does not touch",
the test passes, and the mechanism it is named for is gone. The same shape carries
`test_причина_отказа_принимается_там_где_её_велит_писать_шаблон` (496),
`test_два_экземпляра_узду_ещё_не_требуют` (1743) and
`test_отвергнутые_и_дубли_не_считаются_экземплярами_класса` (1760): if `import` refuses the
draft for any reason, the register is empty and the absent message is guaranteed. The
neighbouring Cyrillic-path test (2841) shows the fix — it asserts `set-finding`'s return code.
**Why it is a defect:** A test that cannot fail is named as a finding by this block's manifest;
here it is worse than a missing test, because the register counts it as coverage.
**Confidence:** confirmed
**Root:** gate proven only by the absence of a message

### T3-008 · medium · the locale is pinned in one call site of thirteen
**Location:** `tests/test_review.py:65`
**What is wrong:** `Stand.run` forces `LC_ALL=C.UTF-8` — the author knew the suite needs a
UTF-8 locale — but every other subprocess call site inherits the environment, and several of
them print or read Cyrillic. The suite's result therefore depends on the machine's locale, and
neither the CI workflow nor the test file pins it.
**Failure scenario:** run `LANG=C LC_ALL=C python3 -m unittest discover -s tests`.
`test_корень_берётся_по_рабочему_каталогу` (1936) spawns `review status` with no `env=`: the
child's stdout encoding becomes ASCII, printing the block title `Демоблок` raises
`UnicodeEncodeError`, the tool exits 1, and the assertion on return code 0 fails — while the
parent's `text=True` decode of the same bytes fails too. `_run_role` (3477) and `_axes` (3347)
inherit the locale the same way and read Russian journal and reply text. The CI workflow
(.github/workflows/tests.yml:18) pins the git identity and the default branch but not `LANG`,
so nothing catches it before someone else's machine does.
**Why it is a defect:** The suite is the gate (CONTRIBUTING), and a gate whose verdict depends
on the developer's locale is the defect that already bit the gate registry in CI on a quote
style — the comment at 3932 records it.
**Confidence:** plausible

### T3-009 · low · the Stand does not isolate the global git config
**Location:** `tests/test_review.py:47`
**What is wrong:** Each Stand repository sets `user.email`/`user.name` locally and nothing
else, so the developer's `~/.gitconfig` and `~/.config/git/ignore` still apply to every
`git init`, `git add` and `git ls-files` the suite runs.
**Failure scenario:** a global ignore file containing `vendor/` — a common entry — makes
`git ls-files --others --exclude-standard -- vendor/**` return nothing in
`test_шаблон_по_нетрекнутым_файлам_зовёт_git_add` (1826): `check` prints "matches no file"
instead of "matches only untracked files (1)", and the test goes red on code nobody touched.
With `commit.gpgsign = true` and no usable key, every `Stand.commit` fails silently (git is
called with `check=False`) and dozens of tests fail for a reason none of them names; a global
`core.hooksPath` pointing at a repository-specific hook does the same.
`GIT_CONFIG_GLOBAL=/dev/null` and `GIT_CONFIG_SYSTEM=/dev/null` in `Stand.git` would remove
the dependency.
**Why it is a defect:** Same class as T3-008: the gate's verdict depends on the machine, and
the failure mode is a red suite on correct code, which trains people to distrust the gate.
**Confidence:** plausible

### T3-010 · low · run-role.sh is only ever tested on a stream with no `result` event
**Location:** `tests/test_review.py:3508`
**What is wrong:** The `claude` stub writes one assistant event and exits; a real
`claude -p --output-format stream-json` run always ends with a `result` event, which is what
`axes.py` measures. So all six `run-role.sh` tests exercise the `NO RESULT EVENT` branch, and
the test named "the reply is printed from a whole stream" asserts the reply is **absent**.
**Failure scenario:** `_run_role` (3459) writes the stub. `axes.py` therefore reports
`NO RESULT EVENT — the run was killed or the stream is truncated`, and
`test_успешный_прогон_записан_обычной_строкой` (3546) accepts that line as an ordinary run: it
asserts only `"hunter — "` and the absence of `RUN FAILED`. Break the journal line's numbers
for a completed run and nothing goes red. `test_ответ_агента_печатается_из_целого_потока` (3508)
asserts `"no agent reply in the stream"` and then checks the reply through `axes.py` directly
on a hand-written file, so `run-role.sh`'s own `--reply` step is never run on a stream that has
a reply.
**Why it is a defect:** The journal is the only memory the next session has (review.py's own
statement), and the shape of an ordinary spend line — the one an operator reads as "the block
was hunted" — is produced by no test.
**Confidence:** confirmed

### T3-011 · low · the NUL-path rule is evaded by the obvious refactor
**Location:** `tests/test_review.py:4093`
**What is wrong:** The class guard for "git output parsed as plain text" looks for list
literals that contain both `"git"` and one of four flags. It therefore sees only calls written
inline with the prefix repeated, and its flag list omits `git grep`, which is the one place
left that parses git's path output line-wise.
**Failure scenario:** factor out the prefix that is repeated at twenty call sites —
`GIT = ["git", "-C", str(ROOT)]`, then `cmd = GIT + ["ls-files", "--others", "--exclude-standard"]`
— or wrap it in a helper `git_out("ls-files", "-o")`. The literal no longer contains `"git"`,
`offenders` stays empty, the `-z` rule is gone, and no test goes red. `review_refs`
(review.py:1436) already passes the guard today: it runs `git grep -n --full-name` without
`-z` and splits the output with `splitlines()`, so a finding id inside a file with a
non-ASCII name is reported under a C-quoted path, and no test covers that path.
**Why it is a defect:** Invariant 5 (git is the source of file truth, paths NUL-separated) and
the guard's own claim to hold "the calls that do not exist yet".
**Confidence:** confirmed
**Root:** class guard keyed on incidental syntax

### T3-012 · low · no fixture path contains `[`
**Location:** `tests/test_review.py:2801`
**What is wrong:** The suite covers paths with spaces and with Cyrillic letters, but not a
path with a pathspec metacharacter — although `[handle]` read as a character class is one of
the failures the invariants list, and `file_sha` carries a `:(literal)` prefix specifically
because of it.
**Failure scenario:** a Next.js tree — the kit's stated target is a ~180k-line TypeScript
project — owns `app/[id]/page.tsx`. Delete `:(literal)` from `file_sha` (review.py:387): with
that file live in the index but not laid out on disk (sparse checkout, or deleted without
committing), the pathspec `app/[id]/page.tsx` matches nothing, `file_sha` returns `None`, the
block fingerprint silently loses the file, and "block files changed after the review" can
never fire for it. Every path in the suite is plain ASCII, a space or Cyrillic, so nothing
goes red. The same untested distinction sits behind `rule_problem` and `--fixed-in`, which
pass a name to `git_files` as a pathspec.
**Why it is a defect:** Invariant 5 names `[handle]` read as a character class as one of the
defects two real reviews found; the fix landed without a fixture that would notice its removal.
**Confidence:** confirmed

## Checked and found correct

- **`QuotationMapTest`** is the strongest thing in the file: a table of ten documents with the
  expected mark for every line, held in both directions, plus the two `unclosed` policies. I
  tried to fault it by shape (CRLF endings, a fence with an info string, a tilde fence closed
  by backticks) and could not — `FENCE`, `CODE_INDENT` and the comment tracker handle those.
  Its use of `importlib` to import the tool as a module contradicts the file's opening
  docstring ("internals are deliberately not imported"), but for a line-classifier table that
  is the right call, not a defect.
- **`GateRegistryTest` comparing Counters rather than sets** (4021) is exactly right, and it
  has its own test for the case that motivated it (two gates collapsing into one key). The
  blind spot in T3-002 is a different shape, not this one.
- **The git default branch** does not decide anything: every remote in the suite is set up with
  an explicit `HEAD:refs/heads/master` push and an explicit `symbolic-ref`, so
  `init.defaultBranch=main` changes nothing. The hypothesis suspected this; it is clean.
- **The kit's own `docs/review/`** is protected by a byte comparison of `state.json` before and
  after a run in a foreign tree (1933–1941) — the one machine dependence the file anticipated.
- **`guard-grep.sh`'s `ENVIRON`-instead-of-`-v` fix** is genuinely proven by the existing
  tests: with `awk -v` the pattern `\.Publish\(` arrives as `.Publish(`, an unmatched paren,
  and awk dies with exit 2 where the test demands 1.
- **The `-z` on the fix-commit gate, symlink hashing by link text, and rename translation in
  `commit_file_sets`** are each carried by a test that would go red on removal (2841, 213,
  2886) — I traced the fixtures rather than assuming.
- **`import`'s refusal of a foreign block's id** is held on both paths by 4457, because the
  check sits above the `--append` branch.
- The two roots I filed (`class guard keyed on incidental syntax`,
  `guard enumerates its subject without exercising it`) are one family, and the honest fix for
  both is one mechanism rather than four patches: a mutation harness in CI that silences each
  registered gate in a copy and requires the named test to go red. I am naming them apart
  because the failure modes differ; whether they are one class is the lead session's call.
