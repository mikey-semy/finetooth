# T3 — verifier report

Block: **T3 — Tests as the gate: are the checks proven**. `proof: measured`, so everything below
rests on runs, not on reading. Baseline first: `python3 -m unittest discover -s tests` on the
working tree — **248 tests, OK, 192 s**. Every "survived" verdict is measured against that green
reference; without it a survivor would prove nothing.

## Tree freshness

`git fetch --all` ran; `git log HEAD..origin/dev` is empty. HEAD is `2e7c39f` on `review/t2`, two
commits ahead of `origin/dev`, both review manifests. There is no `origin/master` in this
repository — the main branch is `dev`, so the freshness check is `HEAD..origin/dev`. The working
tree equals `origin/dev` for `tests/test_review.py`, `skills/finetooth/scripts/review.py`,
`skills/finetooth/scripts/axes.py` and `skills/finetooth/assets/run-role.sh`. Nothing below was
measured on stale code.

## How this was measured

One stand file, one run. Per mutation: a fresh copy of `tests/`, `skills/`, `docs/` and `LICENSE`
into a temporary tree, one textual patch applied (the anchor is required to match exactly once,
so a silently-failed patch cannot be reported as a survivor), then the whole suite in that tree,
six at a time. 24 mutations, 6 environment cells, 6 direct probes. Machine: Python 3.14.7, git in
PATH, no alternative interpreter installed.

## Verdicts on hunter findings

| id | verdict | severity after checking | justification |
|---|---|---|---|
| T3-001 | CONFIRMED | low (was medium) | Measured: the guard enumerates 23 subcommands and only `set-status`, `set-finding` and `log` reach their body; the other 20 are refused by argparse with "unrecognized arguments" before `cmd_*` is entered. Downgraded because the class is held elsewhere — `check_definition` validates the block definition centrally for every command, and `test_блок_без_обязательного_поля_называет_поле` covers `status`, `check`, `order` and `summary` explicitly. What is wrong is the guard's promise, not an open hole. |
| T3-002 | CONFIRMED | medium | Mutation G1: a new gate in `cmd_check` written `problems += [...]` — suite green. G2: the same gate written `problems.extend([...])` — suite green. Control G3: the same gate written `problems.append(...)` — **killed** by `test_каждые_ворота_check_записаны_вместе_со_своим_тестом`. So the registry sees exactly one spelling. |
| T3-003 | CONFIRMED | medium | Mutation G4: the `': no manifest'` entry re-pointed from `test_манифест_пропал_а_блок_в_работе` to the unrelated `test_описание_в_пределах` — suite green. Nothing ties a gate to the test named beside it. |
| T3-004 | CONFIRMED | low (was medium) | Mutation O7: `MSG["ru"]["refs_cut"]` deleted — suite green. Downgraded because the tables are in sync today: measured directly, `MSG["en"]` and `MSG["ru"]` hold the same 58 keys, `en-only` and `ru-only` both empty. The defect is the missing guard, not a live `KeyError`. |
| T3-005 | CONFIRMED | medium | Mutation O1: `cmd_backfill`'s `if not stamped_blocks and not stamped_findings: return 0` removed — suite green, so nothing holds invariant 11 for `backfill`. Mutation O2: the register write moved inside `cmd_set_finding`'s loop over ids — suite green, so nothing holds "all-or-nothing on several ids". Both halves stand. |
| T3-006 | CONFIRMED | low | Four of the named mechanisms measured, all survivors: O3 `import`'s `claim` cap dropped from the limit loop; O4 `block_risk`'s refusal removed; O5 `review_lang`'s `if lang in LANGS` fallback removed; O6 `cmd_next` made to raise unconditionally. Each left the suite green. The remaining items in the omnibus (`restamp` on a vanished file, `coupling`'s share filters, `inventory --under/--unassigned`, `guard-grep.sh --exclude/--skip`) were not individually mutated — see Coverage limits. |
| T3-007 | CONFIRMED, narrowed | low (was medium) | One of the four accusations survives; three are refuted by mutation. Survivor W1: the commit-touches gate silenced for paths containing a space — `test_путь_с_пробелом_не_ломает_проверку_коммита` (1533) stays green, so it cannot fail. Killed W2: removing the "reject reason may live in the claim" mechanism **reddens** `test_причина_отказа_принимается_там_где_её_велит_писать_шаблон` (496). Killed W3: `ROOT_RULE_AT` 3 → 2 **reddens** `test_два_экземпляра_узду_ещё_не_требуют` (1743). Killed W4: counting rejected and duplicate rows as instances **reddens** `test_отвергнутые_и_дубли_не_считаются_экземплярами_класса` (1760). Those three tests do hold their mechanisms; the hunter argued from the shape of the assertion and got three of four wrong. |
| T3-008 | CONFIRMED, scenario corrected | low (was medium); confidence plausible → confirmed | The mechanism is real — `Stand.run` is the only call site that pins a locale; `_run_role` (3477), `_axes` (3347) and the five bare `["python3", str(TOOL), …]` calls inherit it. The hunter's command does **not** reproduce it: measured, `LANG=C LC_ALL=C python3 -m unittest discover -s tests` is **green**, because CPython auto-enables UTF-8 mode in the C locale (`sys.flags.utf8_mode` is 1 there, stdout encoding `utf-8`). With that safety net off — `PYTHONUTF8=0 PYTHONCOERCECLOCALE=0` — the same cell is **red: 15 failures, 195 errors of 248**, the first traceback being `UnicodeEncodeError: 'ascii' codec` from `cmd_prompt`'s `print(body)` reached through `run-role.sh`, exactly the inherited-locale path. Real, but it takes an environment where UTF-8 mode is off, not merely a C locale. |
| T3-009 | CONFIRMED | low; confidence plausible → confirmed | Both predicted cells reproduce. A global `core.excludesFile` holding `vendor/` reddens exactly the test the hunter named, `test_шаблон_по_нетрекнутым_файлам_зовёт_git_add`, and nothing else. A global `commit.gpgsign = true` reddens six: the three `coupling` tests, `test_order_ставит_часто_меняющийся_блок_выше_при_равном_риске`, `test_origin_по_прежнему_ловит_отставание`, `test_setup_предупреждает_про_байткод` — `Stand.commit` calls git with `check=False`, so the failed commits are silent and no message names the cause. |
| T3-010 | CONFIRMED | low | Measured by running `run-role.sh` against the suite's own stub. With `exit 0` the journal line is: `hunter — NO RESULT EVENT — the run was killed or the stream is truncated · spend: ? min, ? turns, 0 tool calls, … cost estimate unknown`. `test_успешный_прогон_записан_обычной_строкой` asserts only `"hunter — "` and the absence of `RUN FAILED`, so it accepts that as an ordinary completed run. The shape of a real spend line is produced by no test of `run-role.sh`. |
| T3-011 | CONFIRMED | low | Mutation G6: `untracked_files` rewritten as `["git", "-C", str(ROOT)] + ["ls-files", "--others", "--exclude-standard", "--", *specs]` with `-z` dropped and `splitlines()` in place of `split("\0")` — suite green, and `test_список_путей_у_git_всегда_запрашивается_NUL_разделённым` never sees it, because neither list literal now holds both `"git"` and a name-asking flag. The second half of the finding — `review_refs` running `git grep -n --full-name` without `-z` and splitting with `splitlines()` (review.py:1436-1449) — was read in the source, not reproduced with a non-ASCII fixture. |
| T3-012 | CONFIRMED | low | Mutation O8: `:(literal)` removed from `file_sha`'s pathspec (`index_rows([rel])`) — suite green. No fixture path in the suite contains `[`, so the magic that exists because git-pathspec reads `[handle]` as a character class can be deleted unnoticed. |

## Own findings

### T3-013 · medium · a gate demoted from `problems` to `warnings` keeps the whole suite green
**Location:** `tests/test_review.py:3951`
**What is wrong:** `GATES` records a gate by the literal skeleton of its message. `_check_gates`
does read which list the gate appends to — it returns `(lineno, "problems"|"warnings", key)` —
but the key thrown away is the list name, and the registry compares keys only. Meanwhile many
gate tests assert only that the message is printed and never assert the exit code. Together those
two facts mean a gate can stop refusing and start merely mentioning, with nothing red.
**Failure scenario:** five gates were moved from `problems.append(...)` to `warnings.append(...)`,
one per copy of the kit, and **every one left all 248 tests green**: the block-status vocabulary
gate (review.py:2876, test at 1613 asserts only `assertIn`), the empty-manifest gate (2907, test
at 1622 the same), the phase-order gate (2885, test at 2056), the "pattern matches no file" gate
(3122, test at 1824) and the three-instances-no-guard root gate (3315, test at 1700). After any of
them `check` prints the same sentence and exits **0** on the state it was written to refuse, and
the registry still reports 64 of 64 gates held.
**Why it is a defect:** invariant 1 and SECURITY.md — "any way to make `check` pass on a state
that is wrong is the most serious class of defect here"; invariant 12 — exit codes mean something.
This is the same class the registry was measured into existence to close (T1-007, medium), one
level deeper: the registry now proves a gate's wording, not its verdict.
**Confidence:** confirmed
**Root:** a gate whose test asserts its message, not its verdict

### T3-014 · low · the threshold guard sees only `NAME = <number>`
**Location:** `tests/test_review.py:4253`
**What is wrong:** `test_каждое_число_в_коде_названо_и_объяснено` walks only
`ast.parse(SOURCE).body`, and only `ast.Assign` whose `value` is an `ast.Constant` and whose
single target is an upper-case `ast.Name`. A threshold written any other way is invisible to it.
**Failure scenario:** mutation G5 added two bare module-level thresholds with no comment above
them — `FOO_LIMIT = 6 * 7` (an `ast.BinOp`, the natural way to write "42 days" or "6 × 1000
lines") and `BAR_MAX, BAZ_MAX = 12, 34` (a tuple target, the natural way to introduce a pair of
limits). The suite stayed green. Invariant 8 — every number carries its measurement — is held
only for one spelling of an assignment.
**Why it is a defect:** the same class as T3-002 and T3-011: a guard written against the shape of
today's code, which a natural rewrite walks past. The manifest names exactly this ("a guard that a
plausible new shape of code walks past").
**Confidence:** confirmed
**Root:** class guard keyed on incidental syntax

### T3-015 · low · the suite runs the tool under PATH `python3`, so the version matrix cannot be produced
**Location:** `tests/test_review.py:66`
**What is wrong:** `Stand.run` spawns `["python3", str(self.tool), *args]`, and six more call
sites do the same (1936, 1946, 1950, 2402, 2422, 2436) — seven in all — while `sys.executable` is
used for `axes.py` and for `REVIEW` in the `run-role.sh` tests (five occurrences). The interpreter
under test is therefore whatever `python3` resolves to in PATH, not the one running the suite.
**Failure scenario:** the block's acceptance criterion asks for the suite on Python 3.12 and 3.14.
`python3.12 -m unittest discover -s tests` would report 248 tests on 3.12 while every invocation
of the tool still ran on PATH `python3` — the cell would be a measurement of nothing, and a
version-specific defect in `review.py` (the `ast.unparse` quote style that reddened the registry in
CI is the precedent the file itself records at 3932) would stay invisible. Measured here: PATH
`python3` and `sys.executable` are the same 3.14.7 binary, and no other interpreter is installed,
so the second cell of the matrix cannot be produced at all on this machine.
**Why it is a defect:** the acceptance criterion of this very block is unobtainable as written, and
the mixed spawning makes the promise look obtainable. A `PYTHON=${PYTHON:-python3}` read from the
environment, used at all twelve sites, would make the cell real.
**Confidence:** confirmed
**Root:** guard enumerates its subject without exercising it

## Mutation table

Per mechanism: mutation → the test that went red, or "survived". Baseline is 248 tests green.
Everything outside `cmd_check` unless the row says otherwise.

| # | module | mechanism | mutation | result |
|---|---|---|---|---|
| G1 | review.py `cmd_check` | the gate registry's reach | a new gate written `problems += [...]` | **survived** |
| G2 | review.py `cmd_check` | the gate registry's reach | a new gate written `problems.extend([...])` | **survived** |
| G3 | review.py `cmd_check` | the gate registry's reach (control) | the same gate written `problems.append(...)` | killed — `test_каждые_ворота_check_записаны_вместе_со_своим_тестом` |
| G4 | tests `GATES` | gate → test mapping | one gate re-pointed at an unrelated existing test | **survived** |
| G5 | review.py module level | invariant 8, numbers carry their source | two bare thresholds as a BinOp and as a tuple target | **survived** |
| G6 | review.py `untracked_files` | invariant 5, paths NUL-separated | `-z` dropped, the git prefix split off into its own list | **survived** |
| O1 | review.py `cmd_backfill` | invariant 11, idempotence | the `nothing to stamp` early exit removed | **survived** |
| O2 | review.py `cmd_set_finding` | invariant 11, all-or-nothing | the register write moved inside the loop over ids | **survived** |
| O3 | review.py `cmd_import` | `import` holds `check`'s limits | `claim` dropped from the limit loop | **survived** |
| O4 | review.py `block_risk` | a refusal instead of a traceback | the `die` on an unknown `risk` removed | **survived** |
| O5 | review.py `review_lang` | a refusal instead of a `KeyError` | the `if lang in LANGS` fallback removed | **survived** |
| O6 | review.py `cmd_next` | the command works at all | made to raise unconditionally | **survived** |
| O7 | review.py `MSG["ru"]` | both languages carry every key | `refs_cut` deleted from the Russian table | **survived** |
| O8 | review.py `file_sha` | invariant 5, `[` is not a character class | `:(literal)` removed from the pathspec | **survived** |
| W1 | review.py `cmd_check` | the fix commit touches the finding's file | the gate skipped for paths containing a space | **survived** |
| W2 | review.py `cmd_check` | a reject reason may live in the claim | the claim-matching regex made to never match | killed — `test_причина_отказа_принимается_там_где_её_велит_писать_шаблон` |
| W3 | review.py `ROOT_RULE_AT` | two instances do not yet demand a guard | 3 → 2 | killed — `test_два_экземпляра_узду_ещё_не_требуют` |
| W4 | review.py `roots_of` | rejected and duplicates are not instances | the filter removed | killed — `test_отвергнутые_и_дубли_не_считаются_экземплярами_класса` |
| D1 | review.py `cmd_check` | the block-status vocabulary gate refuses | `problems` → `warnings` | **survived** |
| D2 | review.py `cmd_check` | the empty-manifest gate refuses | `problems` → `warnings` | **survived** |
| D3 | review.py `cmd_check` | the phase-order gate refuses | `problems` → `warnings` | **survived** |
| D4 | review.py `cmd_check` | the "pattern matches no file" gate refuses | `problems` → `warnings` | **survived** |
| D5 | review.py `cmd_check` | the three-instances-no-guard gate refuses | `problems` → `warnings` | **survived** |

20 survivors, 4 kills. The four kills matter as much as the survivors: they are the hunter's
claims that do not hold.

## Environment matrix

Full suite per cell, same tree, 248 tests each.

| cell | result |
|---|---|
| baseline, fresh copy, Python 3.14.7 | green |
| `LANG=C LC_ALL=C` | **green** — CPython auto-enables UTF-8 mode in the C locale |
| `LANG=C LC_ALL=C PYTHONUTF8=0 PYTHONCOERCECLOCALE=0` | **red: 15 failures, 195 errors** — `UnicodeEncodeError: 'ascii' codec` out of `cmd_prompt` via `run-role.sh` |
| global `core.excludesFile` containing `vendor/` | **red: 1** — `test_шаблон_по_нетрекнутым_файлам_зовёт_git_add` |
| global `commit.gpgsign = true` | **red: 6** — three `coupling` tests, `order`, `origin`-freshness, `setup` bytecode |
| global `init.defaultBranch = main` | green |
| Python 3.12 | **not produced** — no second interpreter on this machine, and see T3-015: the suite spawns the tool as PATH `python3`, so the cell would not measure 3.12 even with it installed |

Supporting encoding measurement, since the locale cell turns on it: with `LANG=C LC_ALL=C` the
child reports `utf-8` and `utf8_mode=1`; with `LC_ALL=C.UTF-8` (what `Stand.run` pins) `utf-8`,
`utf8_mode=0`; with UTF-8 mode and coercion both off and `LC_ALL=C`, `ascii`.

## Hypothesis verdicts

- T3.1 — checked: 24 mutations were run, each in its own copy of the kit against a green 248-test baseline; 20 survived. Survivors exist in `import` (O3), `set-finding` (O2), `backfill` (O1), `next` (O6), `block_risk` (O4), `review_lang` (O5), the `MSG` tables (O7), `file_sha` (O8), `untracked_files` (G6), the module-level thresholds (G5) and in `cmd_check` itself by two routes the registry cannot see (G1, G2, D1–D5). The table above is the artefact the acceptance criterion asks for.
- T3.2 — checked: one of the four suspected tests is green for the wrong reason and was proven so by mutation W1 (the space-path test at 1533 stays green when the gate it is named for is silenced for space paths), while W2, W3 and W4 killed the accusation against the tests at 496, 1743 and 1760 — each of those does redden when its mechanism is broken. Separately measured: `run-role.sh`'s own success test accepts a journal line reading `NO RESULT EVENT … ? turns … cost estimate unknown` as an ordinary run.
- T3.3 — checked: the matrix above was run. The git default branch decides nothing (`init.defaultBranch=main` green — the suite pushes explicit `HEAD:refs/heads/master` refs). The locale dependence is real but not at `LANG=C`: that cell is green because CPython turns on UTF-8 mode there, and it takes `PYTHONUTF8=0` to expose the unpinned call sites, which it does spectacularly (205 of 248 red). The developer's global git config decides the verdict in two common configurations. The kit's own `docs/review/` is genuinely protected — the byte comparison at 1933 holds, and every mutation copy ran with its own `docs/`. The one cell not produced is Python 3.12, recorded in Coverage limits and as finding T3-015.
- T3.4 — checked: three guards have measured blind spots. `GateRegistryTest` sees one spelling of an append (G1, G2 survived; G3, the same gate spelled `append`, was killed) and never exercises its gate→test mapping (G4 survived); it also cannot see a gate demoted to a warning (D1–D5 survived, finding T3-013). `SourceRuleTest`'s NUL rule is walked past by splitting the git prefix out of the literal (G6), and its number rule by a BinOp or a tuple target (G5). `QuotationMapTest` I could not fault: nine further shapes were put through `quoted_lines` directly — CRLF endings, a fence with an info string, a tab-indented fence inside a list item, `>` with no space, a nested blockquote, a multi-line html comment, a four-space line right under a list item, a fence closed by a longer fence, a four-backtick fence closed by three — and every mark came back correct, including the two `unclosed` policies.
- T3.5 — checked: the suite has no fixture path containing a pathspec metacharacter, and mutation O8 proves it — `:(literal)` can be deleted from `file_sha` with the suite green. The layouts the hypothesis suspected are covered: a nested `.git` and a real submodule (184), a symlink and a re-pointed symlink (213), a file live in the index but absent from disk (2801), paths with a space (1533) and with Cyrillic letters (2841), and a pathspec git refuses to parse (2911).
- T3.6 — checked by running the stub, not by reading it: `run-role.sh` was executed against the suite's own `claude` stub with `exit 0`, and the line it writes to the journal is `hunter — NO RESULT EVENT — the run was killed or the stream is truncated · spend: ? min, ? turns, 0 tool calls, … cost estimate unknown` — so all six `run-role.sh` tests exercise the no-result branch and none the ordinary one. The comparison with real streams could not be made: `$TMPDIR/finetooth-runs` and `~/finetooth-runs` hold no `*.stream.jsonl` on this machine, measured, not assumed.

## Verdicts on recorded findings

Nothing was recorded against T3 before this pass, so this table is empty. The findings register
holds 68 rows, all against T1, and none of them names `tests/test_review.py` as its file.

## Notes for the lead

- Three of my findings share the root **class guard keyed on incidental syntax** (T3-002, T3-011,
  T3-014). That is three live instances of one class, so `check` will ask for a guard on it. The
  demand is correct and the honest answer is one mechanism, not three patches: a mutation harness
  in CI that silences each registered gate in a copy and requires the named test to go red. That
  single mechanism would also close T3-003 and T3-013.
- T3-013 and T3-002/T3-003 are **not** duplicates by root: fixing the AST matcher does not make a
  demoted gate visible, and recording the list name in `GATES` does not make `+=` visible. They
  need three different edits, and only the CI harness above subsumes all of them.
- T3-007 is kept in the register as confirmed but narrowed to one test. The three refutations are
  worth keeping visible: arguing from the shape of an assertion produced three false accusations
  out of four, which is the cost this role exists to avoid.

## Block coverage status

**Complete.** The block's own file, `tests/test_review.py`, was read in full (4,465 lines, in four
passes), and both artefacts the acceptance criterion demands were produced by running: the mutation
table (24 mutations, per module, each against a green 248-test baseline) and the environment matrix
(six cells). Every hypothesis has exactly one verdict above, and all twelve hunter findings were
checked by execution rather than by rereading.

What remains unmeasured, named so the next pass does not assume otherwise:

- **The Python 3.12 cell of the matrix.** No second interpreter is installed here, and the suite
  would not have measured it anyway — finding T3-015. This is the one line of the acceptance
  criterion not delivered; it needs a machine with two interpreters and the `PYTHON` indirection
  that T3-015 asks for.
- **Four items inside the T3-006 omnibus** were not individually mutated: `restamp`'s refusal on a
  finding whose file is gone, `coupling`'s `min_share`/`min_together` filters,
  `inventory --under/--unassigned`, and `guard-grep.sh`'s `--exclude`, `--skip` and window bound.
  Four other items of the same finding were mutated and all survived, so the finding stands; the
  count of untested mechanisms it names is a lower bound, not a measurement.
- **The non-ASCII half of T3-011.** `review_refs` splitting `git grep` output with `splitlines()`
  was read in the source; no fixture with a non-ASCII path was built to see a C-quoted path come
  back from it. The guard-blindness half of that finding is measured.
- **Real `claude` streams.** T3-010 rests on the stub and on `axes.py` behaviour measured directly;
  no recorded stream from a live run exists on this machine to compare event order, `num_turns`
  placement or a missing `result` against.
- **Flakiness and parallel safety.** The two `time.sleep(1.1)` calls (3097, 3117) and the suite's
  behaviour under repetition were not probed. Incidentally measured: six copies of the suite ran
  concurrently for every mutation cell without cross-talk, and the baseline copy was green in that
  condition, which is evidence of fixture isolation but not a test of it.
