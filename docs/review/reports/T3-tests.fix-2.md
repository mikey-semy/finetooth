# T3 — fixes, round 2

Four findings, four closed, none rejected and none deferred. The owner's decision for this
round was the mechanism, not the count: the two mediums are the third and fourth instance of
one root — *a class guard keyed on incidental syntax* — and widening a guard by one more
spelling was forbidden. So the guards are now proved the way the gates are: by mutation of
the real source.

| finding | verdict | commit |
|---|---|---|
| T3-016 · the NUL rule is blind to a hoisted prefix | **closed** | `ce888ed` |
| T3-017 · the gate registry walks only `cmd_check` | **closed** | `ce888ed` |
| T3-018 · the locale refusal is unreadable in its own locale | **closed** | `91d22d8` |
| T3-019 · a class guard named in no document | **closed** | `1f063d1` |

Register: `T3-016`, `T3-017` → `--rule tests/test_review.py::SourceMutationTest`;
`T3-018` → `--rule tests/test_review.py::TestSuiteRuleTest`; `T3-019` →
`--fixed-in CHANGELOG.md --fixed-in CHANGELOG.ru.md --fixed-in docs/review/reports/T3-tests.fix.md`.

---

## The mechanism this round installs

The owner's instruction: every bridle that reads a source is to be proved the way
`GateMutationTest` proves the gates — on **deliberately spoiled real sources**, with a
mutation table per rule and a control run on the unspoiled copy; and where a rule cannot
see a spelling in principle (a gate outside `cmd_check`), the place it looks at is to be
changed — to where the value is BUILT, not where it is written.

Both halves are done.

**Where the value is built.** `_Values` (`tests/test_review.py:186`) is one resolver over
the module's scopes: what was ever put into a name, in which scope, where it is read, and
where a value flows on to. Every source rule now stands on it, and none of them keys on a
shape of writing any more:

| rule | what it used to look at | what it looks at now |
|---|---|---|
| `_nul_offenders` | a literal argv passed to `subprocess.<…>` | every git argv **wherever it is assembled** and whoever runs it |
| `_name_as_pattern` | a literal list as the first argument | the argument's elements, resolved |
| `_check_gates` | statements inside `cmd_check` | every statement that fills the refusal list, anywhere |
| `_bare_numbers` | the module's top level | every assignment in the module |
| `_log_mark_offenders` | placement recognised as an f-string on one line | placement recognised by **where the value flows** (`--format=`) |
| `_msg_tables` | `MSG = {…}` at the top level | the table however it is declared and from however many pieces |
| `_register_fields` | a record recognised by the variable's name (`f`, `row`) | a record recognised **by its own fields** |
| `_spawns` | `subprocess.<attr>(…)` written out | the module under an alias, a name pulled in from it — and NOT a name shadowed locally |
| `_rules_without_samples` | the real source named directly in the call | the argument resolved through the variable it came in |
| `_quote_offenders` | unchanged (see Coverage limits) | unchanged |

**The proof.** `SourceMutationTest` (`tests/test_review.py:6483`) runs each of the ten rules
four times per spelling against the real source of the tool and of the suite:

1. honest source → the rule must be **silent** (the control: otherwise "it went red" means
   nothing);
2. honest source **respelled** → silent (otherwise the rule forbids a refactor, not a defect);
3. spoiled source → the rule must **speak**;
4. spoiled **and** respelled → it must say **exactly the same thing**.

The fourth is the property: the verdict depends on what the code does and not on how it is
written. A second test (`test_у_каждого_правила_по_исходнику_есть_таблица_мутаций`) refuses
a new source rule that has no mutation table, so the mechanism covers rules nobody has
written yet.

---

## Finding by finding

### T3-016 — the NUL rule folded `[…] + […]` but not a hoisted prefix

**Reproduced on the code as it stood.** Fed the pre-fix rule directly, with the prefix in a
module constant and `-z` dropped from `untracked_files`:

~~~
=== _nul_offenders: argv только у subprocess и только литералом
    FAIL … (форма='приставка в модуле')  AssertionError: [] != ['git -C grep -n … --full-name …']
    FAIL … (форма='приставка в функции')
    FAIL … (форма='звёздочкой')
~~~

— three spellings, each of which makes a missing `-z` invisible. The finding named two of
them; the measurement added a third address it did not: **the rule never looked at an argv
handed to a wrapper instead of to `subprocess` at all.** `coupling` and `summary --aged`
build `["git", …, "--name-status", "-z", …]` and `["git", …, "--name-only", "-z", …]` and
pass them to `log_records`, so `-z` could be dropped from either with the suite green — the
same defect, at two addresses the finding did not list (rule 10).

**Done.** `_nul_offenders` walks every list the module builds (`_Values.built_lists`),
resolves names, concatenation and star-unpacking, and asks for `-z` of every one that
contains `git` and a name-printing option, regardless of who consumes it.

**The test that catches it:** `SourceMutationTest.test_каждое_правило_по_исходнику_доказано_мутацией`,
entry `_nul_offenders` (spoil: `-z` removed from every git argv; respellings: as written,
prefix in a module constant, prefix in a local, star-unpacked).

**Red on revert, and the revert builds:** yes — output above; the reverted rule parses and
runs (the failure is an assertion, not an error), and the other three rules' entries stay
green in the same run, so the redness is this rule's.

**The other side — what must still pass.** Assertion 2 of the harness: the same three
respellings applied to the **honest** tool must leave the rule silent. Plus the invented
samples that were already there (`test_узда_видит_вызов_собранный_по_частям`), where each
shape is also fed with `-z` present and must produce no complaint.

### T3-017 — the gate registry walked one function

**Reproduced on the code as it stood.** With `_check_gates` restricted to `cmd_check` again:

~~~
=== _check_gates: обход только cmd_check
    FAIL … (форма='часть с чужим списком')  AssertionError: [': block files changed after the review —…'] != []
    FAIL … (форма='часть отдаёт свой список')
~~~

— all 63 keys vanish from the registry the moment `cmd_check` is split into helpers, which
is exactly T3-002's own scenario and the reason the register recorded it as fixed against a
scenario that still reproduced.

**Done.** `_check_gates` walks the whole module: a gate is a statement that fills
`problems`/`warnings`, wherever it is written. `_refuse_unknown_spelling` now names the
function it found the unknown spelling in. Today all 63 gates still live in `cmd_check`, so
the registry contents are unchanged — checked by the harness's control run.

**The test that catches it:** the `_check_gates` entry of the mutation table (spoil: one
gate deleted; respellings: as written, the gate moved into a module helper that takes
`problems`, into a helper that returns its own list, into a helper nested in the command),
plus an invented-source test that reads as documentation:
`GateRegistryTest.test_ворота_вынесенные_из_команды_видны_реестру`.

**Red on revert:** yes — output above. Note the verdict used here is "keys that went
MISSING against the honest tool": a refactor may add keys (a helper that returns a list
gives the call site a key of its own — the registry then demands one more test, which fails
closed), but it may never lose one.

**The other side.** `GateRegistryTest` in full (7 tests) and `GateMutationTest` (63 gates ×
2 mutations, each in its own process) run against the widened rule and stay green: every
gate is still keyed, still registered, and still dies with its named test.

### T3-018 — the refusal was written in the one locale that cannot print it

**Reproduced on the code as it stood**, importing the suite under `LC_ALL=C LANG=C
PYTHONUTF8=0 PYTHONCOERCECLOCALE=0`:

~~~
=== до починки: rc=1
RuntimeError: кодировка файловой … ascii, …
          `PYTHONUTF8=1 python3 -m unittest discover -s tests`
=== сейчас: rc=1
RuntimeError: filesystem encoding is ascii, and this suite speaks Russian: test names, stand
paths and commit messages are non-ASCII, and argv is encoded by the PARENT process. Run it in
a UTF-8 locale or with PYTHONUTF8=1: `PYTHONUTF8=1 python3 -m unittest discover -s tests`
~~~

**Done.** The refusal is English and ASCII-only — the only such text in the suite — and the
comment above it says why that one text is not in the suite's language.

**The test that catches it:**
`TestSuiteRuleTest.test_отказ_набора_читается_в_той_локали_ради_которой_написан`. It does
not read the source: it imports the module in a child under that locale and requires the
stream to name the cause, name the command that lifts it, and contain no `\xNN`/`\uNNNN`.
It skips itself if the interpreter turns UTF-8 mode on regardless (macOS), so the verdict
does not depend on the machine.

**Red on revert, and the revert builds:** yes — the Russian text back:

~~~
AssertionError: First list contains 106 additional elements. First extra element 0: '\\u043a'
 : в отказе есть символы, которые эта локаль печатать не умеет …
Ran 2 tests in 0.271s
FAILED (failures=1)
~~~

The reverted module still imports and still refuses (the child's rc is 1 and the refusal is
in the stream) — the redness is about the text, not about a broken module.

**The other side:** `test_в_UTF_8_локали_набор_импортируется_молча` — in a UTF-8 locale the
import must exit 0 and say nothing. Without it, "the suite refuses" could become normal.

### T3-019 — a standing rule named in no document

**Reproduced:** `grep -n "_rules_without_samples\|RULE_SHAPES\|SOURCE_MARKS"` over
`docs/review/reports/T3-tests.fix.md`, `CHANGELOG.md` and `CHANGELOG.ru.md` returned
nothing, while the guard was live in the tree and had already reddened two existing rules.

**Done.** The fix report's "Incidental fixes" gains item 4 naming the guard, its two tests
and what it demands; both changelogs gain a paragraph that names it together with this
round's mutation harness. The documented scenario count and run time are re-measured
(330 scenarios, 408 s).

**What holds it:** `RepositoryContractTest.test_число_сценариев_в_документах_не_больше_настоящего`
holds the number. Nothing holds "the changelog names what a change gates" — that is a
tradition of `AGENTS.md` rule 2, not a gate, and turning it into one is not a fixer's call
(see *Found, not fixed*).

---

## Incidental fixes

Each was found by a mutation of this round, each is a defect of its own kind, each has its
own entry in the mutation table (that is its test), and each is listed here by name.

**1. `_nul_offenders` ignored argv handed to a wrapper** (`log_records`). Two real call
sites, `coupling` and `summary --aged`, could lose `-z` with the suite green. Covered by the
`_nul_offenders` entry: the spoil removes `-z` from *every* git argv literal, those two
included. Red on revert: yes (the same run as T3-016 — the offenders list the reverted rule
fails to produce includes the `--name-status` and `--name-only` ones).

**2. `_name_as_pattern` read only a literal list.** `want = [rel]; git_files(want)`, a
tuple, and a concatenation all returned `[]`. Entry `_name_as_pattern`.
Red on revert: `FAIL … (форма='имя в переменной'|'кортежем'|'склейкой') [] != ["f'{rel}'"]`.

**3. `_bare_numbers` looked only at the module's top level.** A threshold moved inside the
function that uses it carried no source requirement. Entry `_bare_numbers`, respelling
"порог внутри функции". Red on revert: `[] != ['SPOILED_LIMIT']`. The group-comment scan
also had to learn `lstrip()`, or an indented group of constants would have been read as
uncommented.

**4. `_log_mark_offenders` recognised placement only as an f-string.** Written
`"--format=" + LOG_MARK + "%H"`, or with the format tail assembled a line earlier, the
legitimate placement became an offender and the rule went red on honest code — while the
thing it exists to catch, a second parser of the stream, went unnoticed behind the noise.
Placement is now recognised by where the value flows (`_Values.flows_into`). Entry
`_log_mark_offenders`. Red on revert: `['cmd_summary', 'commit_file_sets'] != []`.

**5. `_msg_tables` read one declaration of `MSG`.** Declared with a type, or assembled from
per-language constants, the table became invisible — and an invisible table is a language
check that silently stops checking (`literal_eval` on a name raises, so the second spelling
was an error, not even a verdict). Entry `_msg_tables`. Red on revert: one FAIL
("в исходнике нет таблицы MSG") and one ERROR.

**6. `_register_fields` recognised a register record by the variable's name.** `f` → `record`
across the tool and the whole field vocabulary vanished, with it the guard that every field
is named in a role template. A record is recognised by its own fields now (`RECORD_MARKS`).
Entry `_register_fields`. Red on revert: `[] != ['verdict_note']`. The field set produced
for today's tool is unchanged — 21 fields, compared before and after.

**7. `_spawns` recognised a child process only as `subprocess.<attr>`.** Under
`import subprocess as sp`, or with `run` pulled in by name, every spawn in the suite left
the rule's sight. Entry `_spawns`. Red on revert:
`[] != ['без env=child_env(): …; python3 из PATH …']`.

**8. `_spawns` read the interpreter name only as a literal.** `_PY = "python3"` hid it.
Same entry, respelling "интерпретатор в переменной". Red on revert: the complaint loses its
second half.

**9. `_spawns` would have flagged a locally shadowed name.** Found by mutation 7 above: with
`from subprocess import run` added, the `run = lambda …` inside
`test_setup_ставит_точку_входа…` was read as a spawn with no environment. A name is a spawn
only when nothing local stands in front of it — otherwise the rule would demand an
environment of something that is not a child process at all. Held by the same entry's
assertion 2 (honest + respelled must stay silent).

**10. `_rules_without_samples` read the source only where it was named directly.** A rule fed
`src = self.SOURCE` looked as if it had an invented sample, and the suite's own class guard
quietly stopped applying to it. Both halves of the rule now resolve the argument. Entry
`_rules_without_samples`; the verdict also reports rules the guard has lost sight of, which
is what proves the second half. Red on revert, per half:
`[] != ['в тесте: …']` and `['потеряно из виду: _msg_tables', …] != []`.

---

## Found, not fixed

Grouped; the decision is the lead's.

**`_quote_offenders` recognises a markdown parser partly by the name of its parameter
(`md`).** It is in the mutation table with two spellings (as written; the tracker reached
through a relay) and both hold — but the table deliberately does not contain "rename the
document parameter". The rule's own innocent-side sample is why: `read_register` splits a
JSONL file into lines and tests `line.startswith("#")`, exactly the shape of a markdown
parser, and the parameter name is the only thing that tells them apart. Making the rule
shape-only would redden an honest reader of the register; making it name-only is what it
already is. Closing this properly means giving the tool a marked type for "a document of
report markup", which is a change to the tool, not to its guard.

**`section_body` and the `RAW_LINES` exemption** (carried over from round 1, unchanged): the
set is a list of names inside an otherwise shape-based rule. A second function handing out
raw section lines would have to be added by hand.

**Nothing holds "the changelog names what a change gates".** T3-019 is the second time the
public record undercounted what a release started enforcing (the first was the scenario
count, T4). A guard is conceivable — a gate demanding that every new class-guard test name
appear in `CHANGELOG.md` — but it would key on a naming convention, which is the very root
this round was sent to close. Recorded here rather than guessed at.

**`coupling`'s share filter and `inventory --under` are still unmeasured** (carried over
from round 1; nothing in this round touched either).

**Observations outside the assignment.** The suite now runs three mutation harnesses
(`GateMutationTest`, and the two tests of `SourceMutationTest`). The new one costs ~62 s and
spawns no child processes — it is pure AST work in-process — so the recursion guard that
protects `GateMutationTest` does not apply to it and is not needed. Total run time went from
~295 s to 408 s on this machine, and the documents were updated to say seven minutes.

---

## Rejected, deferred

None. All four findings reproduced on the current code before the fix, and all four are
closed by a green run.

---

## What was run

**The whole suite, unmutated:**

~~~
$ python3 -m unittest discover -s tests
.................................................................................
Ran 330 tests in 389.792s

OK
~~~

The run before the last fix (`test_ворота_вынесенные_из_команды_видны_реестру`) said
`Ran 329 tests in 408.075s / OK`.

**The skill format:**

~~~
$ npx skills-ref validate skills/finetooth
Valid skill: skills/finetooth
~~~

Nothing under `skills/` changed in this round; the validator was run anyway.

**The mutation harness alone, eleven times, once per reverted rule** (the table in
*Finding by finding* and *Incidental fixes* quotes each). Summary: every revert reddens the
harness, every reverted copy parses and runs, and the unmutated copy is green:

~~~
$ python3 -m unittest discover -s tests -k SourceMutationTest
..
Ran 2 tests in 60.309s
OK
~~~

**The state check.** `check` is red, with exactly the same twelve findings and four blocks
as before this round — measured by running the pre-round tool in a worktree at `e098508`
and comparing: 20 lines with `·` before, 20 after, the same ones. All of them are
`code_sha`/`block_sha` drift belonging to T1, T2 and T4, left where they are: restamping
another block's findings is not this round's business. No T3 finding appears in the refusal
list.
