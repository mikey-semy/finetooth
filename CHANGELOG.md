[Русская версия](CHANGELOG.ru.md)

# Changelog

The format is [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), versions follow
[semantic versioning](https://semver.org/). While the major version is zero, the on-disk state
format may change: breaking changes are marked separately, and for each it is said what to do
with a review already under way.

## [Unreleased]

### Fixed

The whole-repository review of the kit itself, block T1 (`review.py`, `axes.py`,
`run-role.sh`, `guard-grep.sh`): 68 findings over the hunt and seven rounds of fix review, all confirmed by execution — the rest of each is in the register with its status and reason; the verdict parser's open class moved to issue #17.

- **The verdict parser read the shape of a report, not its content.** A hypothesis verdict inside a ``` fence counted as an answer — and the hunter template hands the agent exactly such a skeleton, with the block id already substituted, so a report that copied it and answered nothing closed every hypothesis of the block while `check` printed "review state is consistent". A vocabulary word quoted in backticks ("the report says `not checked` but I did check it") counted as the line's verdict. Any numbered table row anywhere in the report counted as a verdict on the hypothesis of that number — including the gate → test → mutation table the acceptance criterion itself asks for. Now: fenced blocks are skipped, a code span whose whole content is a vocabulary word is a quotation, and a table is a verdict table only where it says so (its first row names hypotheses) or inside the hypotheses section. Mutations: fence skip removed → `test_вердикт_внутри_ограды_кода_не_вердикт` red; code spans not blanked → `test_слово_вердикта_в_обратных_кавычках_цитата` red; a bare numbered row a header again → `test_нумерованная_таблица_вне_раздела_гипотез_не_вердикт` red.
- **Quotation, decided by one principle: in doubt, the gate goes red.** A fence opens at any indentation and closes only near the column it opened at. A fence that never closes is read as text in what DEFINES the work (a manifest: more hypotheses to answer) and as a quotation in what REPORTS it (a report and its coverage-limits section: fewer answers counted) — both directions stricter. Held by `QuotationMapTest`, red under each earlier variant.
- **The verdict parser stays at its round-3 rules; the redesign is issue #17.** Four fix-review rounds changed its rules to answer the previous finding and each reopened an earlier one at a new address. Its known defects are all strict (the gate goes red on an honest report, never green on a false one); the redesign starts from a golden corpus of live reports and template forms. One code-span parser instead of two. `import` refuses a draft row over the limits `check` holds. The coverage-limits gate reads a hunter report in quotation mode and names a heading hidden behind an unclosed fence. `run-role.sh` exits 3 when the run succeeded but the journal line was lost.
- **A `~~~` fence was invisible to every markdown parser in the tool.** A `#` line inside one cut the manifest's Hypotheses section short: a manifest with four hypotheses yielded two, `check` demanded two verdicts, got them and passed, and the fingerprint covered only the truncated text. `demote` pushed a heading inside such a fence down a level in the prompt. Fence detection now lives in one place (`quoted_lines`) that `demote`, `section_body`, `section_items_full` and the verdict parser all call. Mutation: `~~~` dropped from the fence pattern → `test_тильда_ограда_в_манифесте_не_обрывает_гипотезы` red.
- **The verifier's coverage gate was satisfied by "I completed the check".** `complete` matched inside `completed`, so a verb about verdicts answered the question about coverage; the Russian half failed the other way and refused "проверка завершена полностью". Both halves are the one regex. Mutation: the old regex restored → `test_завершил_проверку_не_оценка_охвата` red.
- **`file_sha` and `block_lines` read the disk, not the index.** A file listed by `ls-files` but not laid out (sparse checkout, deleted without committing) contributed only its NAME to the block fingerprint — its contents could be rewritten and "block files changed after the review" never fired — and its lines dropped out of the readability count. `block_lines` also counted binary files as lines, which `file_lines` was taught not to do. Mutations: index fallback removed → `test_файл_из_индекса_не_выложенный_на_диск_даёт_отпечаток_и_строки` red; `block_lines` counting by itself again → `test_двоичный_файл_не_считается_строками_в_пороге` red.
- **git output was parsed as plain text in three places.** `git show --name-only` C-quotes a non-ASCII path, so a finding on a Cyrillic-named file could never be marked fixed — the gate stayed red on a truthful state for ever. `git log --name-only` prints only the new path of a rename: `review.py` has 42 first-parent commits and 10 under its current path, and `order` ranked the block that owns it on a quarter of its real change frequency. `summary --aged` counted the same file under two names. All three now go through `-z` and NUL-separated paths, and `commit_file_sets` follows renames back into today's names. Mutations: `-z` dropped from the fix gate → `test_находка_на_пути_с_кириллицей_закрывается_коммитом` red; rename aliasing removed → `test_переименование_не_обрывает_историю_изменений_блока` red.
- **The named-files gate was a substring test.** A report naming `src/api.ts.snap` closed the gate for `src/api.ts` too — as did any `.map`, `.test.ts` or `index.ts` under a longer directory. A path must now be named whole. Mutation: substring test restored → `test_соседний_файл_с_тем_же_началом_не_закрывает_гейт_имён` red.
- **The cited-line gate was switched off by a wrong type.** `"line": "9999"` skipped the check entirely while `findings.md` rendered it as a real location. The type is now part of the vocabulary, next to `severity` and `status`. Mutation: the gate silenced → `test_номер_строки_строкой_а_не_числом` red.
- **The freshness gate was silently inert without `refs/remotes/origin/HEAD`.** A checkout with no remote, or with a remote not named `origin` — the vendored copy the threshold was written for — passed in silence however far behind it was. Every remote is asked now, and when no main line can be found the gate says so and names the command. Mutations: only `origin` asked → `test_удалённый_не_origin_ловит_отставание` red; the notice removed → `test_без_удалённого_репозитория_ворота_объявляют_себя_неработающими` red.
- **`guard-grep.sh` let a marker exempt every hit in its window** — the exact `grep -B` defect the script was written to replace, reproduced in its own rewrite: one escape hatch silently freed three calls below it. A marker is now spent on the first hit it covers. And a scan path that does not exist was skipped with exit 0, so a renamed package turned the gate green; it is now a refusal (exit 2) that names the fix. Mutations: the spend removed → `test_один_маркер_освобождает_один_вызов` red; the existence check removed → `test_переименованный_пакет_роняет_ворота_а_не_молчит` red.
- **`import` handed out ids by position.** A finding inserted above the numbered rows took an id that already existed; the register then held two `H1-001`, `check` said "duplicate id" and named no way out, and `set-finding` reached only the first. Numbers come from the free ones now, and a draft with two rows under one id is refused. Mutations: positional numbering restored → `test_импорт_не_выдаёт_занятый_номер` red; the duplicate refusal disabled → `test_две_строки_с_одним_номером_в_черновике_отказ` red.
- **A hand-written block definition reached the code unvalidated.** A block without `phase`, `slug`, `role` or `goal` — the shape `setup` invites, since it leaves `"blocks": []` for a human — answered `KeyError` and exit 1, which reads as "the state is red". Definitions are checked once, on load, with a message that names the field and the file. Mutation: validation removed → `test_блок_без_обязательного_поля_называет_поле` red.
- **A pathspec git refuses to parse crashed the tool.** A typo in the pathspec magic the kit invites projects to use made `check` and `coverage` exit with `CalledProcessError` and git's own message swallowed. Mutation: `check=True` restored → `test_шаблон_который_git_отказывается_разобрать_объясняет_себя` red.
- **`summary --aged` cut its machine block at the first ` -->`.** A block titled `Import --> export pipeline` is written into it verbatim, and the one file meant to outlive `docs/review/` answered with a traceback. Mutation: the old cut restored → `test_итог_с_маркером_внутри_названия_блока_не_роняет_aged` red.
- **`prompt` substituted into what it had already substituted.** A manifest paragraph about `{{FILES}}` came out rewritten with the file list, because MANIFEST was substituted before FILES. One pass now. Mutation: the loop restored → `test_подстановка_в_тексте_манифеста_остаётся_текстом` red.
- **A cut-off role run was written to the journal as an ordinary one.** `run-role.sh` wrote the spend line whatever the exit code, and `axes.py` reported "0 min, None turns, output 0k, cost estimate $0.00" — in the format of a real measurement — for a stream with no `result` event, and died outright on a truncated last line. The journal is the only memory the next session has. A run now carries its outcome, unmeasured numbers print as `?`, and a failed `review prompt` no longer leaves a zero-byte file in `TMPDIR`. Mutations: exit code dropped from the line → `test_упавший_прогон_записан_в_дневник_как_упавший` red; the result-event branch removed → `test_поток_без_события_result_не_выдаётся_за_измерение` red; the truncation guard removed → `test_обрезанная_последняя_строка_не_роняет_замер` red.
- **`init` rewrote `updated_at` on every run**, so a CI gate of the usual shape — regenerate, then require a clean working tree — went red on a correct state. A re-run on an unchanged definition now leaves the file alone to the byte; the same was done for `restamp`, of a block and of a finding. Mutations: the early return removed → `test_повторный_init_не_меняет_состояние_ни_на_байт` red (and `test_повторный_restamp_блока_ничего_не_пишет`).
- **The mass-commit cutoff did not hold on a young history.** The 95th percentile's rank is `ceil(0.95·n)`, which equals `n` for every n up to 20, so nothing was ever skipped and the initial whole-tree commit paired every file with every other — on exactly the repository where `coupling` is run first. The percentile is now taken by nearest rank, and below the sample floor the outlier is found by Tukey's fence. Mutation: the old index restored → `test_на_молодой_истории_стартовый_коммит_считается_массовым` red.
- **Four thresholds carried no source** while every other constant in the file carries one: the reference-list ceiling (80 paths ≈ 2.5k characters, measured), the "manifest nearly empty" bound (200, against the 171-character scaffold of headings), `CLAIM_MAX` / `SCENARIO_MAX` (220 / 700, against the measured 82…202 and 452…690 of 24 real findings) and the coupling hub threshold, which is a share of the review's blocks with a floor of three — a seam runs between two blocks, a third makes it a node — set so that it reproduces the 6 the command was measured with on the 59-block review it came from (59 × 10% = 5.9), while on a review of four blocks "coupled with six of four" cannot happen and the filter would be dead code.
- **Twenty-four gates of `check` had no test**: each could be silenced with the whole suite green. Every one now has a test, and all 62 gate sites of `cmd_check` were measured by mutation — silencing any of them turns its test red.
- `prompt`: the "substitution left without a value" check ran on the assembled text, so a finding that quotes `{{FILES}}` refused the fix prompt (the kit's own review, block T1). It now checks the template. Mutation: check moved back after substitution → `test_подстановка_в_тексте_находки_не_роняет_prompt` red.
- `check`: "line N is cited, but the file has M" fired on fixed findings, whose file legitimately shrank after the fix (first migrated registry: three fixed findings flagged). The check now applies to open and deferred findings only. Mutation: status filter removed → `test_строка_за_концом_файла_у_починенной_находки_не_ошибка` red.
- Hypothesis verdict parser, two false positives from the first live block on the skill (setfork H3): `n/a` was found inside a path (`curation/adapter.ts`) and turned a checked hypothesis into "not applicable"; and any numbered table row anywhere in a report counted as a verdict on that hypothesis — the acceptance table "| 4 | place | constraint | ✓ |" produced verdicts on hypotheses 4 and 5. Now `n/a` is a standalone sign, and a table row is a verdict only inside the hypotheses section, under a header that names hypotheses, or in a bare numbered table. Mutations: `n/a` back to substring → `test_n_a_внутри_пути_не_вердикт` red; table rows counted anywhere → `test_нумерованная_таблица_приёмки_не_вердикт_гипотезы` red.
- `SKILL.md` description said three roles; there are four (the fix reviewer was added in 0.5.0). The description is what an agent reads to decide whether to apply the skill.
- `check`: a `paths`/`ref_paths` pattern that matches only untracked files now says so and names the `git add`, instead of "matches no file". Seen on the first live migration: `npx skills add` writes the skill outside the index, and the block that owns it looked empty. Test proven by mutation: `untracked_files` returning `[]` turns the test red.

The fix review of that round, six more findings, all closed here.

- **The guard for "a gate that cannot go red" did not see a gate whose message is not a literal.** Three gates of `check` get their whole message from a helper or a variable, so the registry keyed them by an empty skeleton — and any new gate written in that shape, the shape a neighbour is copied from, matched an existing entry and passed with no test at all. A gate whose message carries no wording of its own is now named by the expression that produces it, and the registry compares counts rather than sets. Mutations: `problems.append(msg)` and `problems.append(dup_problem(...))` added to `cmd_check` → `GateRegistryTest` red, where both were green before.
- **A verdict quoted by an indent, by `>` or inside an html comment still closed a hypothesis.** The fence was closed; markdown's three other ways to quote an example were not, and a report that restated its assignment in any of them answered nothing while `check` printed "review state is consistent". Recognising a quotation now lives in `quoted_lines`, which all four markdown parsers call; an indented code block is measured from the enclosing list item's content column, so a proof written as a sub-item under a verdict is still that verdict's text. Mutations: the parser back to the fence-only tracker → `test_вердикт_внутри_отступа_или_цитаты_не_вердикт` red and the class guard red with it.
- **`summary --aged` counted one file under two names.** `git log -z` leaves the newline that ends the `--format` line glued to the first path of every commit; the drift query, written later than `commit_file_sets`, did not strip it, and two commits over two files printed as three. One reader (`log_records`) for both callers. Mutation: the reader replaced by its own parse → `test_дрейф_не_считает_один_файл_дважды` red.
- **The named-files gate refused `./src/api.ts`.** The lookbehind that stops `docs/src/api.ts` closing the gate for `src/api.ts` also stopped the `./` an agent writes by habit and the `a/`, `b/` of a pasted diff header — a complete, honest report with no repair but rewriting its paths. The three prefixes are accepted where they themselves start a path. Mutations: the prefixes removed → `test_путь_с_приставкой_точки_или_заголовка_диффа_засчитывается` red; the prefix widened to any directory → `test_приставка_не_делает_названным_файл_из_другого_каталога` red.
- **`axes.py` dropped the cut-off of a second `result` event.** A run can emit several; the numbers are taken from the longest, and so was the outcome, so a stream carrying a 40-turn success and a 2-turn `error_max_turns` reported the spend of a completed run in either order. The outcome is now read from every result event. And a result can describe part of the run — a turn carries at most one assistant message, so eleven messages against two turns is not a measurement; that is how the journal got "0 min, 2 turns, 329 tool calls, cost estimate $67.92", and the line now says so. Mutations: the outcome back to one event → `test_обрезка_во_втором_событии_result_не_теряется` red; the consistency check silenced → `test_результат_короче_потока_не_выдаётся_за_замер_прогона` red.
- **The Breaking section held five fixes that are not breaking, and not the change that is.** A `### Breaking` heading inserted in the middle of `### Fixed` swept five bullets out of it, and the change a running review really has to act on — the validation of block definitions — was not recorded at all. One heading per type in both languages, Breaking last, and the validation written up with what to do.

The second round of fix review, five more findings, all closed here.

- **A fence nested in a list item was not a fence.** Fences were looked for no further than three spaces from the margin, while a report nests them in a list item, where they start at the fourth space and beyond — and the verdict skeleton the role template hands the agent, copied into such an item, closed every hypothesis of the block while `check` printed "review state is consistent". Where a fence may open depends on the list item it sits in, so the fence is now tracked in the same pass as the list context, three spaces past the content column; `fenced_lines`, which could only measure from the margin, is gone into `quoted_lines`. Mutations: the fence back to an absolute indent → `test_ограда_внутри_пункта_списка_остаётся_оградой` red; the verdict after a nested fence still read → `test_вердикт_после_вложенной_ограды_по_прежнему_вердикт` proves the other direction.
- **The gates that read a report's substance still counted quoted text.** A verifier report whose whole body was the template's example inside a ```markdown fence — nothing verified, nothing stated — passed `verify_report_problem`, and the block stayed `verified`; the hunter's coverage-limits section passed the same way on a section holding only a fence. Quotations are dropped before the substance is weighed (`unquoted`), the refusals name where the answer belongs, and both role templates say in both languages that the rule covers everything the state check reads, not the hypothesis verdicts alone. Mutations: `unquoted` removed from either gate → `test_отчёт_проверяющего_из_одних_цитат_не_проводит_блок` and `test_раздел_ограничений_из_одной_цитаты_роняет_проверку` red; the other direction is held by `test_отчёт_проверяющего_с_образцом_рядом_со_словами_проходит`.
- **The quotation guard could not see a parser that does not exist yet.** It held a hardcoded list of markdown parsers; three shapes were measured against it — a document read line by line by hand, lines paired with a flag that is not the quotation flag, and the raw lines of a section read as the report's own words — and the suite stayed green on every one. A markdown parser is now recognised by its shape: a document parameter (`md`), a structural pattern of the markup, a section's lines, or a per-line flag zipped with them; delegation counts, but `section_body` hands back the lines as they stand, so reading them obliges its caller to ask the tracker itself. The rule found one place no finding named: the acceptance criterion went into the summary's cell with a fenced example table pasted into it. Mutation: the rule back to the list of names → `SourceRuleTest.test_узда_видит_разборщика_которого_ещё_нет` red on all three shapes.
- **`a/` and `b/` were accepted as prefixes anywhere, and they are also directory names.** A block owning both `src/api.ts` and `a/src/api.ts` passed `check` with exit 0 on a report that named only the second, and said nothing about the first — which no report mentioned. The prefix is now read only after a diff header marker on the same line (`diff --git`, `---`, `+++`), where it cannot mean anything else; `./` keeps being accepted everywhere. Mutations: the prefix accepted anywhere again → `test_каталог_a_не_закрывает_ворота_за_файл_которого_никто_не_читал` red; the other direction is held by `test_заголовок_диффа_в_том_же_дереве_по_прежнему_называет_файл`.
- **`run-role.sh` died on the truncated stream `axes.py` was taught to survive.** The script parsed the stream a second time, inline, to print the agent's reply — with a bare `json.loads` per line — and a killed run leaves its last line half-written. Being the last command under `set -euo pipefail`, it took `exit $RC` with it: an operator whose run was cut off (`claude` exit 143) read a Python traceback and the exit code 1. The reply now comes from `axes.py --reply`, the one reader of the stream, and an EXIT trap keeps the script's code the run's code whatever a report does with its own. Mutations: the inline reader back → `test_обрезанный_поток_не_роняет_запуск_роли` red; the trap removed → `test_отказ_шага_отчёта_не_подменяет_код_возврата_прогона` red.

The whole-repository review of the kit itself, block T4 (the documents, the workflows, the
issue templates — what the repository promises to people who will never read `review.py`).

- **The security boundary in `SECURITY.md` was false in both directions.** It promised that the tool "writes to `docs/review/` and sends nothing over the network", while `summary` writes `docs/review-summary.md` — outside the directory, deliberately, because the summary is meant to outlive it — and `--out` writes wherever it is told, including outside the repository; and `run-role.sh` keeps the assembled prompt and the whole event stream in `$TMPDIR/finetooth-runs` and sends the prompt over the network through `claude -p`. By the file's own definition the first was a reportable vulnerability for intended behaviour. The promise now says what each part of the kit writes and sends, and `run-role.sh` is named as the opt-in exception (`review.py prompt` prints the same prompt and sends nothing). Held by a run, not by proof-reading: `WriteBoundaryTest` snapshots the project tree, calls every subcommand and fails on anything created or changed outside `docs/review/` — a new command falls under the rule by itself. Mutation: one write site pointed at the repository root → `test_ни_одна_команда_не_пишет_вне_каталога_ревью` red; the old text restored → `test_обещание_безопасности_называет_то_же_исключение` red; the other direction — the summary still written where asked, including outside the repository — is held by `test_итог_пишется_туда_куда_сказали_и_только_туда`.
- **The skill's own frontmatter still said part of the kit had no licence.** `license:` in `SKILL.md` read "MIT for the additions; the base was handed over by its author without a license" — the statement 0.7.0 retired, when the author of the base granted the rights and `LICENSE` became plain MIT with both holders. That line is what a reviewer reads in the installed copy, and it said the kit could not be cleanly licensed. The field is now the licence's identifier and nothing else; prose belongs in `LICENSE` and `NOTICE.md`, which travel with it. Mutation: the old sentence restored → `test_поле_лицензии_это_её_обозначение_и_ничего_сверх` red — the identifier is read out of `LICENSE`, so the field cannot drift from it again.
- **`init` answered a traceback on a `blocks.json` a human wrote by hand.** The definition was validated block by block, while three shapes a hand-written file takes reached the code unchecked: no top-level `review_id` (`init` alone — the first command anyone runs — ended in `KeyError`, exit 1, which reads as "the state is red"), an exclusion written with `reason` and no `pattern` or the whole list written as one object (six commands died in git), and `paths` written as one string instead of a list (the pathspec list was spliced a character at a time). All three now answer exit 2 naming the field and the file. The guard that forbids exactly this was green throughout: it called every subcommand with a block id and a file name, so `init`, which takes neither, never got past argparse. It now runs each command with and without those arguments, over a table of damaged definitions. Mutations: each of the three checks removed → `test_ни_одна_команда_не_роняет_трейсбек_на_битом_определении` and `test_отказ_на_битом_определении_называет_поле_и_файл` red; the other direction — an exclusion with extra keys, a block without `paths`, a definition without `exclusions` — is held by `test_целое_определение_по_прежнему_принимается`.
- **Two rules were declared enforced with nothing enforcing them.** CONTRIBUTING says every commit is signed off: nine files in `.github/` and not one of them a DCO job, the only artefact a checkbox in the pull request template that the author ticks and nobody verifies. And RELEASING called its four gates "all mechanical" while three are a human's — which is how 0.5.1, 0.5.0 and 0.4.1 shipped without their compare links. Now: `.github/dco.sh` checks every commit of a pull request (the sign-off must name the commit's own author; merge commits carry nobody's authorship and are skipped) and is run by a CI job and by hand; RELEASING says of each gate who runs it and what in it cannot be automated. Mutation: the sign-off no longer required to name the author → `test_подпись_с_чужой_почтой_не_засчитывается` red; the other direction — several authors in one branch, an address typed in another case, a merge commit — is held by `test_подписанные_коммиты_проходят` and `test_коммит_слияния_подписи_не_требует`.
- **CI took `actions/checkout` by the moving `v5` tag, spoke Russian, and pinned no Python.** The tag can be re-pointed, and the step that lays out the working tree can make the suite pass — while green CI is what branch protection requires before a merge into `master`; everything else in the two workflows has been pinned by commit since 0.4.0. The step names an outside contributor reads in the checks panel were Russian, in a repository whose rule is English with `.ru.md` copies. And `SKILL.md` said "tested on 3.12 and 3.14" while the job called whatever `python3` the runner image carried. Now: every action pinned by commit, every step and comment in English, and a matrix over exactly the versions the skill declares. **The check names change** — `unittest (3.12)`, `unittest (3.14)`, `skill`, `dco` — so the required checks in branch protection have to be updated with this. Mutations: `checkout@v5` restored → `test_действия_ci_закреплены_коммитом` red; the Russian workflow restored → `test_в_github_нет_кириллицы` red and `test_рабочий_процесс_зовёт_эти_ворота` red; a version dropped from the matrix → `test_версии_python_из_шапки_скилла_прогоняются_в_ci` red.
- **Live guidance pointed at files the repository does not have.** Release step 2 sent the releaser to `scripts/review.py` and a root `SKILL.md` — the layout moved into `skills/finetooth/` in 0.4.0 — so a release either stalls or creates a second `scripts/review.py` while the real version strings stay where they were. The change-proposal template sent an outside contributor to `docs/prior-art.md`, which went to the private knowledge base, and then asked for a roadmap direction number from a plan they cannot read; it now asks how the proposal would be proven, which is what the project actually wants. Mutation: either file restored → `test_живое_руководство_ведёт_на_существующие_пути` red (the rule reads the paths out of the documents themselves, so a new one falls under it).
- **The documents' numbers had stopped being measurements.** README (both languages) and AGENTS.md gave the suite as 98 scenarios in about a minute; measured, 248 in over three. The figure tracked reality at 0.1.0, 0.3.0 and 0.4.0 and was then left behind, while it is the README's public evidence for "tests proven by mutation". The README also described `coupling` with the constants it no longer has: the shared-node threshold as a fixed six blocks (it is a tenth of the review's blocks with a floor of three, and the run prints the one it used) and the mass cutoff as the 95th percentile with no mention of Tukey's fence below twenty commits. Numbers corrected, the thresholds described as the rules they are. Mutation: any of the three documents left at the old count → `test_число_сценариев_в_документах_не_больше_настоящего` red — the count is taken from the suite itself; the document may not claim more than exists nor lag by more than a tenth (exact equality broke every PR that added a test). The runtime is measured, not held by a test: it depends on the machine.
- **The "What is inside" inventory did not enumerate the kit.** It is the one place the repository lists itself — it named 19 of the 23 commands, and `refs` appeared nowhere in either README, so nobody ran it; it omitted `scripts/axes.py` and `assets/run-role.sh` (the two files that write outside the repository), all ten `.ru.md` templates and assets the `lang` switch selects, and at root `.gitignore`, `CLAUDE.md`, `LICENSE`, `CHANGELOG.ru.md` and `CODE_OF_CONDUCT.ru.md`. Mutations: a command or a file dropped from the list → `test_опись_набора_называет_все_команды` / `test_опись_набора_называет_все_файлы_скилла_и_корня` red; both read the truth from `--help` and from `git ls-files`, so a new command or a new asset falls under the rule by itself.
- **The Russian README was missing what the kit guarantees.** `README.ru.md` had no counterpart to the six claims that separate the kit from PR-review bots — the coverage map that fails on an unowned file, mandatory hypothesis verdicts, fingerprints, the register in git, guards from the third recurrence, mutation-proven tests — and no "Language" paragraph, while the `[Русская версия]` link at the top of `README.md` is the only entry point offered to a Russian reader. Both are there now, in the same place as in the English file. No test holds this one: prose parity is not mechanically checkable, and a guard that compared headings would pass on exactly this defect.
- **Two versions of the CHANGELOG's own rules, and three releases with no diff to read.** The Unreleased section said in *Added* that a shared node is a file coupled with six or more blocks, and in *Fixed* that the threshold had become a share with a floor of three — release notes are taken from this section verbatim, so a reader had two mutually exclusive rules for one mechanism. And 0.5.1, 0.5.0 and 0.4.1 had no compare link in either language, so their headings rendered as plain bracketed text — the releases that added the fix-reviewer role, the block proof kind and the depersonalised templates. Both fixed, and `[0.6.0]` now compares from `v0.5.1` rather than skipping it. Mutation: a link reference removed → `test_у_каждой_версии_в_истории_есть_ссылка_на_сравнение` red, in both languages.
- **The codes of conduct did not know about each other.** 0.7.0 recorded that the Russian copies are "cross-linked at the top of each file"; both READMEs and both CHANGELOGs were, both codes of conduct were not — and `CODE_OF_CONDUCT.md` is the file GitHub surfaces in the community profile, so a translation that was written and committed was unreachable. Mutation: either link removed → `test_у_двуязычных_файлов_ссылка_друг_на_друга_в_первой_строке` red; the rule walks the `.ru.md` pairs, so a new pair falls under it.
- **Two classes closed by a rule, not by a list of places.** *A number in a public document not checked against its source* (the test count, the coupling thresholds, the CHANGELOG contradicting itself): the thresholds the documents state are now read out of `review.py` by the test, so changing a constant without changing the text turns the suite red — mutation: `COUPLING_HUB_SHARE` moved to 0.25 → `test_пороги_из_документов_читаются_из_кода` red in both READMEs. *A rule declared enforced with nothing enforcing it* (the release gates, the DCO, the Python versions): every command CONTRIBUTING tells a contributor to run must be run by a workflow — mutations: the DCO job removed → `test_каждые_объявленные_ворота_гоняет_ci` red; the validator step replaced by `true` → red.
- **`NOTICE.md` promised an anonymity it does not keep.** It said the names of the projects the method was road-tested on, their internals and the defects found are not published — while the CHANGELOG cites `setfork H3` and a file from it as the source of two verdict-parser defects. The project is the owner's own, so nobody else's data is disclosed, but the sentence as written was false, and a CHANGELOG is never deleted. The promise is now scoped to what the repository actually does: someone else's project is never named; the owner's own are, with the paths a number needs to be traceable.
Block T2 of the same review — the role templates in both languages, the samples in `assets/`,
`SKILL.md` and the toy example: 15 findings, all closed here.

- **The gates asked the agent for fields no template named.** The verifier was told to put a rejection reason in `claim`, while `check` reads `reject_reason` or a claim that opens with a rejection word: a report written exactly by the instructions turned the register red, and the way out was a command the verifier does not have. `root` was in no draft schema at all — the hunter named the defect class in prose, the register stored nothing, `roots` answered "no roots recorded" and the three-instance guard gate could not fire on a single honest run; `dup_of` was missing the same way, and the fixer was never told how a rejection or a deferral is recorded. Guard: `TemplateContractTest` takes the finding's field vocabulary from the tool's own source and demands that every field an agent writes be named in some role template, in each language — a field nobody has written yet has to be classified too. Mutation: the templates restored → red on `root`, `dup_of`, `reject_reason` and `defer_reason`, both languages.
- **The shipped samples did not pass the tool's own gates.** `examples/toy`, the one example of a correct review state, failed `check` on its own unowned `README.md` and on a `findings.md` header carrying a `<skill>` placeholder the tool never writes; its `quota.ts` named a register finding id in a comment — the practice the kit forbids — and cited a finding about another file; `assets/blocks.example.json`, the file three of the tool's own refusals point at, ran phase 1, 2, 1, 3 and was refused by the phase-order gate. Guard: `ShippedSampleTest` runs the gates over what actually ships — the example as its README says to use it, and the definition sample installed as a real one. Mutation: the four files restored → both red; the other side is a sample deliberately reordered, which still trips the phase gate.
- **The Russian scaffolds were English, and the banner named a command a project may not have.** `agent-banner.ru.md` carried the English banner word for word — only the explanation around it was translated — in the one document whose job is to stop a new session from starting a parallel review; `setup --lang ru` named the English samples in its checklist, which left four Russian files of the kit reachable from nowhere at all; and both banners hardcoded `make review-status`, so a Go or Rust project without a Makefile sent every future session to a command that does not exist. Asset names are constants now, picked by language with a fallback to English, and the banner is printed ready to paste, substituted like the entry point. Guards: `BilingualAssetTest` (a `.ru` copy with English prose left in it; an asset handed to a project naming a build command instead of `{{CLI}}`) and `SetupLanguageTest`. Mutation: the banners and the tool restored → 8 subtests red across all four addresses.
- **`SKILL.md` and the entry point were behind the tool.** `roots` — the class view the guard gate rests on — together with `refs`, `hypotheses` and `version` was named by no line of either, and by no message of the tool. `--round` was documented for the fix reviewer only, so a second fix round started as `SKILL.md` said wrote over round 1's report, and the round-2 fixreview prompt then pointed at a file nothing had written. The entry point `setup` copies into every project as `docs/review/README.md` knew nothing of the fixreview role or its report name, of the fix gate, of `import --append`, `restamp` or `backfill`. Guard: `DocumentedSurfaceTest` takes the subcommand list from the source and demands each be shown as a command. Mutation: the documents restored → red on four commands, on ten entry-point tokens and on the fixer's round.
- **The kit gave two answers to "is the review finished".** Lesson 13 required every deferred finding to be fixed or rejected before the end, while `check` demands only the reason and `summary` publishes deferred findings under "Accepted risks"; the completion conditions mentioned them nowhere, and the refusal's own tail repeated the claim the tool does not hold. The lesson, the refusal and both completion conditions now say what the mechanism does — a deferral is a decision that leaves the review; what stays forbidden is deferring in silence. Test: the whole flow leaves `check` green, `status` finished and the reason in the summary; the other side holds that a deferral without a reason is still refused.
- **The fix reviewer was handed a diff of any size with no budget and no way out.** Rule 1 said "the diff is pasted below in full — read it" with no condition, nothing stated the volume, and `--scope` was named in neither template, while the hunter's prompt carries a measured reading budget; the first round of the kit's own T1 diff was 193 KB. The diff is taken once and measured: `{{DIFF_VOLUME}}` states its size, its line count and the order of magnitude in tokens, and names the way out where the volume stands. Test: the fixreview prompt states the measure and names `--scope`; the other side is that no other role gets the measure and no substitution leaks.
- **`SKILL.md` offered `make review` as a value for `cli`, which cannot work.** Every hint and refusal is assembled from that field — `<cli> prompt H1 --role verify`, `<cli> set-finding H1-003 rejected --reason …` — and `make` reads `--role` as its own option and stops; the Makefile snippet defines no generic target either. The documentation now names only forms that carry a flag, and the snippet says why `make` is not one of them. Guard: `CliContractTest`, whose other side runs the offered form through a real refusal and requires the subcommand and the flag to come back out of it.
- The `MSG` tables of the two languages are now compared key by key: `T()` raises `KeyError` at run time, not at import, so a string added to one language only breaks the role run of a project reviewing in the other.

The whole-repository review of the kit itself, block T3 (the tests as a gate): 15 findings, measured by mutation. The suite is the gate, and the rules it holds itself by turned out to hold one spelling each.

- **A gate of `check` moved from the refusals to the warnings left the whole suite green.** Measured across all 63 gates of `cmd_check`: 47 of them survived it — `check` printed the same sentence and exited 0 on the state it had refused, while the registry still reported every gate as held. A refusal and a warning ARE the same sentence, told apart by the exit code, and a test that looks for the message anywhere in the output cannot see the difference; the exit code alone is not enough either, because on a fixture where a second gate also fires the run fails regardless. Gate tests now assert WHICH section the message landed in (`refused()` / `warned()`), and the registry proves each of them by mutation: every gate is silenced in a copy of the tool, and the test named beside it must go red; a second mutation moves the gate to the neighbouring list and demands the same. Mutations: the five gates the review names moved to `warnings` → each named test red; the `: no manifest` entry re-pointed at an unrelated test → the mutation guard red.
- **A gate written `problems += [...]` or `problems.extend([...])` needed no test at all.** The registry knew one spelling, `append`, so a gate written any other way produced no key, required no entry, and could be removed later with the suite green — and splitting a 500-line `cmd_check` into parts, the obvious refactor, collects refusals in a list. Every spelling is read now, and one the registry does not know is a refusal naming the line, not silence. Mutations: the same gate added with `+=` and with `.extend` → the registry red both times.
- **The suite's verdict depended on the machine it ran on.** Only one of the three dozen child processes pinned a UTF-8 locale; the rest rested on CPython turning UTF-8 mode on by itself in the C locale, and with that safety net off the suite was red at 195 errors, none of which named the cause. The developer's global git config decided the rest: `core.excludesFile` holding `vendor/` reddened one test, `commit.gpgsign` without a key reddened six — silently, because the stand never looked at the exit code of its own commit. Every child now gets one environment (`child_env()`): UTF-8, and git with no global or system config; the stand names its branch itself and fails loudly when a commit cannot happen; a source rule over the suite holds the class for the spawns nobody has written yet; CI pins the locale instead of a git identity. Mutations: a spawn written without the shared environment, and one with an interpreter from PATH → the rule red on both.
- **Three class guards were blind to a plausible shape of the code they guard.** The NUL rule inspected single list literals, so splitting the repeated `["git", "-C", str(ROOT)]` prefix out of one blinded it completely and `-z` could be dropped unnoticed; it now assembles argv per call, across concatenation and across a variable built up in steps, and asks about `git grep` too. The threshold rule read only `NAME = <number>`, so `6 * 1000` — the natural way to write a derived limit — and a pair assigned together carried no source. The no-traceback rule fed one argv to every subcommand, and argparse refused it for 20 of the 23 before their bodies started; it carries an argv per command now and refuses a command that has none. Mutations: the git prefix split out and `-z` dropped; a threshold written as an expression and as a pair; a command body raising, and a new subcommand with no argv → red in every case.
- **`review_refs` parsed `git grep` output as plain text**, found by the widened NUL rule: a reference in a file with a non-ASCII name reached the operator C-quoted, and a path containing `:` was cut at the colon — an address that leads nowhere, from the command whose whole job is to say where a finding id is named in the code. Now `-z`. Mutation: `-z` removed → `test_refs_называет_не_ASCII_путь_как_он_есть` red.
- **A file NAME was handed to git as a pattern, and a pattern matches the neighbours.** `app/[id]/page.tsx` is an ordinary Next.js route and a character class to git-pathspec: measured, the pathspec `app/[id].tsx` matches `app/i.tsx`, so `--rule` and `--fixed-in` accepted paths with no such file in the repository — and the guard-exists check is there precisely because a typo in the path made a defect class "closed" without a rule. Names go through `named_file()` (`:(literal)`) now, and a source rule keeps the next name out of a pathspec. Mutation: `:(literal)` dropped → both the behaviour test and the rule red.
- **A string that exists in one language and not the other was held by nothing.** `T()` takes the key from the table of the CHOSEN language and fails at run time, not at import: deleting the Russian `refs_cut` left the whole suite green, and a Russian-language project with 81 context files would get a traceback out of `prompt` — the command that hands an agent its assignment. The two tables are compared whole, keys and substitution fields alike, and every role template and scaffold must have its twin. Mutations: a Russian string deleted, a Russian substitution renamed, `hunter.ru.md` removed → red.
- **Mechanisms outside `cmd_check` that no test reached**, each now with a test named for it: `import`'s claim cap (a draft that `import` accepted and `check` then refused made every later gate red on a row nobody could fix through the tool), `block_risk`'s refusal (a hand-written `risk` outside the vocabulary reached `SEVERITIES.index` as a traceback), `review_lang`'s fallback (a hand-written `ru-RU` became a `KeyError`, and no gate validates the field), `restamp` on a vanished file, `cmd_next`, `backfill`'s idempotence, `set-finding`'s all-or-nothing over several ids, and `guard-grep`'s `--exclude`, whose value could be dropped with the whole suite green.
- **The `claude` stub was softer than the real client.** It emitted no `result` event, so all six `run-role.sh` tests exercised the "no measurement at all" branch, and the test named "a successful run is written as an ordinary line" accepted `NO RESULT EVENT … ? turns … cost estimate unknown` as one: the line an operator reads as "the block was hunted" was produced by no test. The stub now emits the stream of a whole run, from the same source as the `axes.py` fixtures. Mutation: the stub back to a stream without a `result` event → `test_успешный_прогон_записан_обычной_строкой` red.

### Added

- `refs`: finding ids of the register named in the tracked tree outside `docs/review/` (exact ids, word-bounded — the register knows them, so no guessing); `check` warns with the count. The rule "no references to the review in code" was only text in the role templates; the kit author found about forty such references in his tree by hand. Mutations: the `docs/review/` exclusion removed → red; the warning removed → red.
- Process rules in the role templates (en, ru), from the kit author's review and the kit's own T1: a new fix-review round only for a finding of medium or higher, low ones fixed by the fixer or the lead (a lead's fix marked as having no independent review); when the top finding sits inside the previous round's diff two rounds in a row, in one class, the next move is a human's; the reviewer writes its report as it goes. The fixer's report: a finding → verdict → commit table, a probe reproducing each defect before the fix, the revert red and the allowed side held, "found, not fixed" grouped for the lead.
- The hunter's and the verifier's prompts show the findings already recorded against the block (open and deferred, with the date) and the id of the hunter's first new finding — the same `import --append` will give. The verifier gives its verdict on recorded findings in a separate table of its report; the lead moves them with `set-finding`. From the kit author's review: without it the hunter numbered from 001 and hunted again for what was already written down. Mutations: deferred rows hidden → red; the next id counted from the number of rows instead of the highest → red.
- Guards over the source, each red on the defect it exists to stop, for the classes that repeated three times or more (`tests/test_review.py`): `GateRegistryTest` keeps the gate → test table alive — a new gate of `check` without a registered test fails the suite, whether its message is a literal or comes from a helper; `SourceRuleTest` holds the rules that a git command asking for file names passes `-z`, that the records of `git log -z` are parsed in one place, that recognising a quotation (fence, indent, `>`, html comment) lives in one place and every markdown parser calls it, and that every numeric constant carries its source above it; `HandWrittenInputTest.test_ни_одна_команда_не_роняет_трейсбек_на_битом_определении` takes the subcommand list from the tool itself, so a new command falls under the rule without the test being edited.
- Two rules in the fix role template, in both languages, from the kit's own first fix run: the version, the release and the history belong to the maintainer — a fixer writes under "Unreleased" and does not bump `VERSION`; and turns are spent on fixes, not on ceremony — the full gates once at the end of the series, the relevant test after each fix, not the whole suite in ten worktrees (that run: 329 turns, most of them ceremony). A test keeps both sentences in both templates.
- `coupling`: pairs of files that change together (`git log --first-parent --no-merges`) but belong to different blocks — roadmap direction 12. Thresholds from the first project's measurement and change-coupling research (Zimmermann et al., ROSE 2005): together ≥ 3 commits, share ≥ 50% of one file's commits; mass commits above the 95th percentile of files per commit in this repository are skipped (below twenty commits, where the percentile separates nothing, above Tukey's fence); a file coupled with a tenth of the review's blocks, and never fewer than three, is a shared node, printed apart. Both cutoffs are printed by the run that used them. Each pair comes with the `ref_paths` entry and the manifest hypothesis; clusters of pairs between two blocks point at a seam block. `--since`, `--min-together`, `--min-share`, `--write` (`docs/review/coupling.tsv`). On the first live registry: 876 commits, 37 mass commits skipped, 36 shared nodes, 79 pairs, 3 clusters. Mutations: mass cutoff removed → `test_coupling_находит_пару_через_блоки_и_отсекает_массовые_коммиты` red; hub threshold removed → `test_coupling_выносит_общий_узел_отдельно` red; same-block exclusion removed → the pair test red.
- Spend, measured and capped — roadmap direction 9, items 1 and 3. `scripts/axes.py` breaks a `claude -p --output-format stream-json` stream down by axis (input from cache / to cache / uncached, output, turns, tool calls and their output bytes, re-reads; usage counted once per message — the stream repeats it per event). `assets/run-role.sh <ID> <role>` runs a role headless, keeps the stream and writes the spend line to the journal; `--max-turns` at twice the first measured run (hunter 55 → 110, verifier 165 → 330). Role templates: the hunter reads a file whole in one call and batches independent tool calls; the verifier writes the stand as one script and runs it once — the measured lever is turns × context, not files read. Mutation: usage counted per event instead of per message → `test_axes_считает_usage_раз_на_сообщение…` red.
- `summary`: the one file that outlives `docs/review/` — roadmap direction 10. Date and base commit, the blocks with status, fingerprint and the manifest's acceptance criterion, rejected findings with reasons, accepted risks (deferred with a reason), what closed each class (guards by `--rule`, fixes by commit), still-open findings, seams from `coupling.tsv`, and a machine block with the base commit and the blocks' paths. `--out` (default `docs/review-summary.md`, outside the directory). `summary --aged <file>` reads that block and prints, per block, commits and files changed since the base — the drift an auditor's re-test starts from. Text follows `lang`. Mutations: rejected section dropped → `test_summary_пишет_итог…` red; base commit ignored in `--aged` → `test_summary_aged_считает_дрейф…` red.
- `order`: the blocks in the order worth walking them — `risk` on the block first (`critical|high|medium|low`, optional), commits touching the block's files second (mass commits skipped as in `coupling`), with ↑/↓ against the declared order. Roadmap direction 9, item 4; measured as a prediction on the first project (top 10% by change frequency → 34% of later fixes). Mutations: frequency key removed → `test_order_ставит_часто_меняющийся_блок_выше…` red; risk key removed → `test_order_риск_важнее_частоты` red.
- `fix_gate` in `blocks.json` (`critical|high|medium|low|none`, default `high`); `status` prints the fix debt as its own line (how many open at the gate level, in which blocks); `check` warns about open findings older than 7 days by `imported_at` — the same week the stale-tree check allows. Mutations: gate check disabled → `test_гейт_починки_не_пускает_следующий_блок…` red; debt line removed → `test_статус_показывает_долг_починки` red; age warning removed → `test_check_предупреждает_о_находке_старше_недели` red; same-block exception removed → the gate test red on re-entering the block.
- Fix-review template: "of the findings above, N inside the code the previous round changed, M outside" — the number a human needs to stop a loop of rounds (issue #9).
- Logo (`.github/logo-light.png`, `.github/logo-dark.png`), shown in the README with the GitHub theme switch.
- Branch model: `master` for releases, `dev` for integration (default branch), feature branches from `dev`; CI runs on both.
- `RELEASING.md`: semantic versioning with a zero major, at most one release a week, four
  mechanical gates before a tag (tests with mutations, `skills-ref validate`, a run on a live
  project, a complete CHANGELOG), no direct pushes to `master` for anyone. Written after four
  releases in one day showed that the version number had stopped meaning anything.

### Changed

- **`set-finding --rule` records the guard only on the findings named in the command** (issue #28). It used to write the guard onto every finding sharing the root — "the class is closed as a whole or not at all" — and one root string turned out to carry defects that need different guards. In the kit's own review three fixers in one day, each right about its own block, rewrote the guards of other blocks' findings, open and already fixed, with tests that stay green on those findings' own defects; `check` saw nothing, and 13 of the rewritten records kept their old `updated_at`, so the rewrite did not show by date either. Now the guard lands on the named findings only, and every change of `rule` stamps `updated_at`. A finding already `fixed` can be named again with its status to record a guard on it: it keeps its own fix commit, so one command no longer needs a `--commit` that would overwrite several. `roots` prints every guard a root's instances carry and which findings carry it, and flags a root whose instances disagree (`GUARDS DIFFER`, with how many carry none); `check` warns — not refuses — about a root of three or more where some instances carry a guard and some do not; the summary heading says a guard is listed with the findings it is recorded on. The fix and fix-review templates, `SKILL.md`, the entry point and both READMEs say the same. **If you relied on the old behaviour** — recording one guard on one finding to close the whole class — name every instance the guard goes red on (`set-finding <ID>... <status> --rule <path>`); a register written by the old code may carry guards its findings never saw, and `roots` is where to look. Mutations: the root-wide write restored → `test_узда_записывается_только_на_названные_находки` red on the neighbour in its own block, the one in another block and the fixed one; the `updated_at` stamp dropped → the same test red on the named findings; the old `roots` (the first guard found is the root's) → `test_roots_показывает_узды_каждого_экземпляра` red; the warning removed or turned into a refusal → `test_корень_с_уздой_не_на_всех_экземплярах_предупреждает` red (registered in `GateRegistryTest`); `--commit` required again on a fixed finding → `test_узда_на_починенную_находку_без_повторного_коммита` red.

### Removed

- `docs/` and `ROADMAP.md` moved to the private knowledge base `finetooth-hq`: measurements, prior art, method comparison, token economy, the open-source plan and the roadmap. The public repository keeps what a user of the kit needs. The old banner is gone with it — replaced by the logo.

### Breaking

- **The plain `import` no longer replaces what is recorded.** A finding recorded against a block before its pass (handed over by another block's fixer, left by an earlier pass) was erased by the block's first import, its id went to the hunter's new finding, and `check` stayed green — found in the kit author's live register (26 such rows in 15 unstarted blocks). Now the plain import refuses, naming the rows, when the file would erase a recorded row or overturn a decision recorded by a command or a closed status; the file may still change a decision nobody stamped. The way out is `import <ID> --append` (recorded rows stay, new ones get the next free numbers), or `--force` to replace the set deliberately. A row numbered for another block is refused on every import path. A review in progress: a re-import that used to pass may now be refused — read the named rows, then `--append` or `--force`. Held by `RecordedFindingsImportTest` (the author's forbidden/allowed list), each of four mechanisms red under mutation.
- **A block definition is validated on load, so a `blocks.json` that worked yesterday can refuse every command today.** `"phase": "1"` instead of `1`, an empty `goal`, a missing `slug` or `role` — shapes the old code walked past with a `KeyError` on some paths and silently on others — now answer `status`, `order`, `summary`, `prompt` and `check` alike with exit 2 and the name of the field. A review under way: open `docs/review/blocks.json`, fix the field the message names (the example is `assets/blocks.example.json`), and the commands work again. Nothing on disk has to be regenerated.
- **A verdict inside a code fence or any other quotation no longer closes a hypothesis, and a numbered table outside the hypotheses section is no longer a verdict table.** A review under way whose report put its verdicts inside a ``` block, in a block indented by four spaces, behind a `>`, inside an `<!-- html comment -->`, or in a bare `| 1 | … | checked |` table under some other heading, will now show those hypotheses as unanswered. Move the verdicts into ordinary lines of the report (the role templates say so now), or put the table under the "Hypotheses" heading, and re-run `check`. A sub-item indented under a verdict is still part of it: proof written that way keeps its verdict.
- **The named-files gate no longer accepts a longer path that contains a shorter one.** A block whose report named only `src/api.ts.snap` will now be told that `src/api.ts` is not named. Name the file, or set `"named_files": false` if the project opted out of the check.
- **The fix gate.** `set-status <ID> running` now refuses while findings of `high` severity or above are open in the blocks already passed. A review in progress with such findings: fix them (`set-finding … fixed --commit`), defer with a reason, reject — or record the decision to run without the gate as `"fix_gate": "none"` in `blocks.json`. Roadmap direction 11: the method finds faster than a project fixes (first project: 77 findings on 5 blocks, 9 fixed).

## [0.7.0] — 2026-09-24

The release that makes the kit an open-source project: English is the primary language,
Russian is a switchable copy, and the repository carries everything a stranger expects.

### Changed

- **English is the primary language.** README, CONTRIBUTING, SECURITY, NOTICE, AGENTS.md,
  ROADMAP, CHANGELOG and every document in `docs/` are in English; Russian copies live as
  `README.ru.md`, `ROADMAP.ru.md`, `CHANGELOG.ru.md`, `CODE_OF_CONDUCT.ru.md` and `docs/ru/`,
  cross-linked at the top of each file. Commits, PRs and issues are in English from now on.
- **The tool speaks English.** Every message, hint and help string of `review.py`; the
  report parsers understand both languages (hypothesis verdicts `checked / not checked /
  not applicable` and their Russian forms, "Coverage limits", coverage verdicts, template
  placeholders). Verdict labels in `check` and `hypotheses` output are English.
- **The skill gets a review-language switch.** `blocks.json` field `lang` (`en` default,
  `ru`) selects the role templates (`hunter.md` / `hunter.ru.md`), the assets and the
  language of what the tool writes into `docs/review/` (prompt rule 1, reading budget,
  `findings.md`, the journal). `setup --lang ru` starts a Russian review. A project's own
  templates in `docs/review/prompts/` override both.

### Added

- **The licence is clean MIT with two copyright holders**: Georgiy Khudobandaev and Mikhail
  Toshkin. On 24.09.2026 the author of the base handed the owner the full right to dispose of the
  kit and publish it; the appendix on licence boundaries is removed from `LICENSE`, the origin and
  the record of consent are in `NOTICE.md`. GitHub now recognises the licence.
- Open-project scaffolding: `CONTRIBUTING.md` (DCO, test + mutation, no dependencies),
  `CODE_OF_CONDUCT.md` (Contributor Covenant 2.1, the official translation), `SECURITY.md`,
  issue templates (defect, trophy, proposal) and a PR template, badges and an English paragraph
  in the README, repository topics and description, discussions, protection of the `master`
  branch by green CI.
- `examples/toy` — a real `docs/review/` produced by the tool on a three-file toy app: one
  block through hunter and verifier, findings register, coverage map, fingerprints, journal.
- `CLAUDE.md` imports `AGENTS.md`: one set of rules for every agent.
- A stale bot for PRs whose author went silent (21 + 9 days); issues never expire.
- CONTRIBUTING: how changes are accepted — issue first for features, one PR one problem,
  trivial PRs closed, a test or an explanation of verification, AI use disclosed and the PR
  description written by a human, silence is a no, write access for work done.
- Pre-flight check for publication: names, keys and addresses — none; `gitleaks` over the
  history — 58 commits, no leaks.

### Breaking

- Tool output is English only; scripts that grep Russian phrases of `check` must be updated.
- Hypothesis verdict labels are `checked / not checked / not applicable`.
- New reviews are English by default: add `"lang": "ru"` to `blocks.json` (or run
  `setup --lang ru`) to keep Russian templates and artifacts.

## [0.6.0] — 2026-09-24

### Changed

- **The kit is renamed: review-kit → finetooth.** The name comes from the idiom *go through with
  a fine-tooth comb*: comb through without missing a single file. Chosen as the root of a series
  of editions by review type (`-lens`, `-slice`, `-pr`, `-scan`, `-shape`, `-threat`, `-gate`) —
  the analysis is in `docs/open-source.md`. The GitHub repository is renamed, old links redirect.

### Breaking

- The skill folder is `skills/finetooth`; an installed copy will land in
  `.claude/skills/finetooth/`. In projects with a `review-kit` copy: reinstall with
  `npx skills add mikey-semy/finetooth`, fix the paths in `package.json`/`Makefile` (or the
  `cli` field in `blocks.json`) and the skill folder exclusion in `blocks.json`.

## [0.5.1] — 2026-09-24

### Changed

- **Lesson 6 in `references/lessons.md` is depersonalised.** The "incident card" named the
  subject domain of the home project — exactly the phrase 0.4.1 had already removed from the
  journal example, and the new lessons file brought it back. The meaning of the lesson is
  unchanged. The script and the state format are the same: updating from 0.5.0 is a reinstall.

### Documents

- ROADMAP: marked what the 0.5.0 release closes (half of direction 4, part of 11), the token
  analysis added to direction 9, the spend measurement put into the order of work as item zero.
- `docs/review-methods.md` — a comparison of eight review methods (coverage, time,
  productivity, external methods by primary sources, three measurements on the first project's
  history), moved from the project's knowledge base and depersonalised.
- ROADMAP: direction 14 — a lens bank as a source of hypotheses for manifests.
- `docs/open-source.md` — what is needed to open the repository (the licence on the base, the
  author under GitHub restrictions, the name, scaffolding by comparison with the best neighbours),
  a catalogue of 24 similar projects on GitHub and parallels with the ROADMAP directions;
  direction 15.

## [0.5.0] — 2026-09-24

A release based on the second version of the kit, which the method's author Georgiy
Khudobandaev developed in parallel and handed over on 23.09.2026 (the `review-combine-kit`
archive). His tool was compared with ours line by line: five defects of our copy he had already
closed, he has a role and a gate we did not have; our fingerprints, hypotheses, guards and
commit checks are absent in his. The mechanisms were carried over, the texts rewritten in our own
words; his project's data was not carried over.

### Fixed — after his version

- **A fixed finding on a deleted file failed the check forever.** File existence was required of
  every finding; now — only of open and deferred ones.
- **Deferring was possible without a reason** — and the finding dropped out of the review
  unnoticed. Now `deferred --reason` is mandatory, `check` catches what was written in by hand.
- **Phases in `blocks.json` were not checked for order**: a phase 2 block before phase 1 passed,
  and `next` issued it first.
- **`status` declared the review finished with a block in `blocked`** and suggested deleting the
  directory with an unread block inside. Now: "the review is NOT finished: waiting …", blocked
  blocks are listed with their notes, `blocked` without a note is a `check` refusal.
- **The `running` time was counted from the first start**: a block returned to work three weeks
  later was immediately declared stuck.

### Added — after his version

- **The fix reviewer role** (`prompt <ID> --role fixreview --diff <range> [--round N]
  [--scope half]`): the diff is pasted into the prompt in full, the report gets the name of the
  round and the half, at the end — an explicit verdict "is another round needed". A block with
  fixed findings cannot be closed without such a report.
- **The block's proof kind** — `"proof": "read" | "measured"`; a block without `paths` is a live
  system. The prompt's first rule and the file list heading are derived from it; for `measured`
  the line ceiling does not apply.
- **The gate "every file of a readable block is named by full path in at least one report".**
  "Read 25 of 25" is the agent's own word; at the author's, a top-up after such a claim found 11
  more defects. Excluded files are not required; switched off with `named_files: false`.
- **The `inventory` command** (the repository tree: files, lines, binaries, whose) **and
  `sizes`** (each block against the ceiling), **`coverage --no-write`** — the gate mode for CI.
- **`set-finding` accepts several findings at once.**
- **Binary files are not counted as lines**, neither in the ceiling nor in the prompt.
- **An unfilled substitution in a template** (`{{SOMETHING}}`) is a `prompt` refusal, not text
  for the agent.
- **The fixer's prompt**: compatibility with old data is decided by the invariants; an
  incidental edit is allowed if named as a separate line with its own test; the revert when
  checking a test must compile; the fix goes to all addresses of the defect; the commit style is
  the project's.
- `references/lessons.md` — 42 lessons from two reviews with stories; `SKILL.md` — the rules of
  the lead session (stopping at a block boundary, a fresh agent for a repeated fix).
- `docs/token-economy.md` — where the tokens go: the cost of a block does not depend on its
  size, so it goes on tool results; eight hypotheses with how to measure them, and a list of what
  not to do.

### Breaking

- Projects with passed blocks: the full-path gate will turn red the blocks whose reports do not
  name files. Either add the lists to the reports, or `named_files: false` in `blocks.json`
  until the blocks are re-passed.
- `deferred` without `defer_reason` is now a refusal — fill in the reasons.

### Documents

- **ROADMAP reassembled** after the comparison of eight review methods and the check against
  external methods by primary sources. New directions: the fix phase as a gate (11), a seams map
  by change coupling (12), the threat model as a block type (13). Directions 1, 3, 9 are
  supplemented with measurements: change frequency predicts fixes better than size (34% versus
  29% in the top 10% of files), capture-recapture on two hunters is fit only as an upper bound,
  a sample of 59 files is a cheap upper bound. The order of work: first fixing and seams.
- `docs/prior-art.md` — the sources for this check.

## [0.4.1] — 2026-09-23

### Changed

- **Examples and templates are depersonalised to the end.** `c4f2dd2` rewrote the invariants
  example and generalised the block paths, but `assets/manifest.example.md` and
  `assets/journal.example.md` stayed as in the original archive, and the blocks example and the
  `fix.md` template kept marks of the home project: the name of one of its resources together
  with the history of a permissions defect, the names of internal files and types, the subject
  domain and the client layout. All of that travelled into every project where the skill is
  installed — including public repositories. The subject domain of the examples is replaced with
  a neutral one ("orders"), the defect history became an example of what to write in that
  section; the hypotheses, the acceptance tables and the lesson from `fix.md` are kept in full.
- The script and the state format did not change: updating from 0.4.0 is simply a reinstall.

## [0.4.0] — 2026-09-23

The kit became **a skill under the [Agent Skills](https://agentskills.io/specification)
standard**. Before, it lived by the linter model: the installer copied the tool and templates into
the project and wrote a hint string into the tool. Every update meant a manual transfer into every
project — in the very first project that was ten transfers in one PR, a diverged version string
and bytecode that leaked into a commit. Now there is one copy, installed by the standard
installer and read by any agent that knows the standard; the agent finds it by itself, by the
description.

### Changed

- **Layout.** Everything installed to the agent is in `skills/review-kit/`: `SKILL.md` (when to
  apply and the working procedure), `scripts/review.py`, `references/` (templates of the three
  roles), `assets/` (the former `example/`), `LICENSE`. Documents, tests and the plan stay in the
  repository root and are not installed to the agent.
- **The project root is by the working directory**, not by where the tool lies. A skill in
  `~/.claude/skills/` would otherwise take its own directory as the root — or `~/.claude`, were
  it under git — and write the state there. Outside a git repository the tool refuses; `version`
  answers from anywhere.
- **Role templates are taken from the skill.** One's own version in
  `docs/review/prompts/<role>.md` is optional and, if present, is taken instead of the skill's.
- **The hint string** is the `cli` field in `blocks.json`; without it — the real path to the tool
  (relative inside the project, via `~/` in the home directory). Writing it into the code is no
  longer needed.

### Added

- **`review.py setup`** instead of `install.py`: a skeleton `blocks.json`, `invariants.md`, an
  entry point. It does not copy the tool and templates into the project. If the skill is
  installed inside the project, its folder is excluded from coverage right away — otherwise from
  the first commit it would turn the map red.
- **Skill format check.** In CI — `skills-ref validate` from the standard's repository (pinned
  to a commit); in the tests — the name equals the directory, the description is within limits,
  links from `SKILL.md` lead to files, the version in the header equals the tool's version, the
  skill's `LICENSE` equals the root one. 76 tests; every new check comes with a mutation that
  breaks it.
- Checked with the standard installer `npx skills add` in both modes — into the project and into
  the home directory (`-g`): the installed copy starts a review, builds the map and names itself
  in the hints by its own path.

### Removed

- `install.py` — its work is done by `npx skills add` and `review.py setup`.

### Breaking — migrating a project from 0.3.0

1. Install the skill into the project and commit: `npx skills add mikey-semy/review-kit`. The
   copy in the repository pins the version for CI.
2. Delete your own copy of the tool (`scripts/review/review.py`) and move the calls
   (`package.json`, `Makefile`, CI) to the skill's path — or keep them, writing into
   `blocks.json` a `cli` field with how the project calls the tool.
3. `docs/review/prompts/`: delete the templates that were not edited — they will be taken from
   the skill; keep the edited ones — they still take precedence.
4. Put the skill folder into the `blocks.json` exclusions (or into a block, if the tooling is
   reviewed) — `setup` does this only for a new review.
5. `check` and `coverage` — verify that the map and the fingerprints agree.

## [0.3.0] — 2026-09-23

A release about the gates ceasing to let things through silently. The first transfer into a live
project and ten rounds of external auto-review showed: almost every check in 0.2.0 had a silent
bypass — an old record without a fingerprint, an intermediate status, an empty section, a typo in
a reference. Here they are closed, and every fix is proven by a mutation (67 tests). New
commands: `backfill`, `restamp <finding ID>`, `set-finding … --fixed-in`.

### Fixed

- **Verdicts of blocks with a letter suffix were lost.** The hypothesis identifier was guessed by
  the regex "letters, digits, dot", and `V1d.1` did not match it — and more than half of the
  blocks of a real review have such names. Now the identifier is built from the block's real
  name.
- **A status change turned the gates green.** The checks of hypotheses, coverage limits and the
  fingerprint were in force only in `verified` and `closed`; moving to `triaged` switched them
  off, adding nothing. Now they hold in all states after verification.
- **The rejection reason was required not where the role template tells you to write it.** The
  template puts it into the finding's title, while the check required a separate field — and
  failed every finding formatted exactly by the instruction. Both are accepted; the template is
  supplemented.
- **Tree staleness is measured from the divergence point.** A fresh commit in a long-diverged
  branch made its tip newer than the remote's and hid the fact that the branch contains not one
  of others' fixes.
- **A fix in a neighbouring repository** is written as `repository:commit` and checked for form,
  not for existence.
- **Records without a fingerprint dropped out of the check silently.** A block passed before
  fingerprints appeared, and a finding imported before them, were skipped — that is, exactly the
  oldest went unchecked. Now this is a refusal; the new `backfill` command stamps fingerprints
  from the current code and writes to the journal the commit from which changes are tracked.
- **`set-status triaged` re-stamped the fingerprint.** Any transition after verification took the
  file hash anew and thereby confirmed a review of edits nobody had looked at. The fingerprint is
  set only by `verified` and `closed`; confirming edits is, as before, `restamp`.
- **The coverage map no longer writes a commit into its header.** The check "a snapshot from the
  same line of history" let through a map assembled on a different set of files — the commit
  name proved nothing. The map's freshness is checked by line-by-line comparison with a
  recomputation, as before.
- **Editing hypotheses after verification credited old verdicts to new questions.** The
  hypothesis identifier is an ordinal number; reorder the items or replace a question with
  another, and "H1.2 checked" silently applied to the new text. Now, together with the file
  fingerprint, a fingerprint of the hypotheses' text is taken, and its divergence is a refusal
  (`restamp` if the meaning did not change).
- **A sub-item of a hypothesis counted as a separate hypothesis** and demanded a verdict on a
  question the prompt did not ask. Only top-level items count.
- **A guard was accepted as any string.** A typo in the path closed a defect class without any
  rule. Now the path must be a file of the repository (the suffixes `::test`, `#anchor`, `:line`
  are cut off), and a guard in a neighbouring repository is written as
  `repository:path/to/file`. A deleted guard is caught in `check`.
- **An empty verifier report moved a block into `verified`.** Only the file's existence was
  checked. Now it must contain text besides headings and at least one verdict on findings
  (confirmed / plausible / rejected / duplicate or in plain language), and for a block without
  findings — a verdict on coverage. A table form is not required: reports are written
  differently.
- **A live finding on a changed file could not be confirmed with anything.** A file also changes
  when a neighbouring finding is fixed, and there were two ways out, both false: close the live
  defect or edit the register by hand. Now `restamp <finding ID>` — the same as for a block.
- **The coverage assessment in the verifier's report is always required**, not only for a block
  without findings: verdicts on what was found say nothing about what was not looked at.
- **Contradictory verdicts in one report** ("H1.1 — checked" and below in the table "not
  checked") were resolved by line order, and differently for different forms of notation. Now
  this is a refusal; the first mention across all forms is taken.
- **`--dup-of` accepted any string.** A typo or a reference to itself removed a live defect from
  the remaining work. A duplicate must point to another existing finding that is itself neither
  a duplicate nor rejected; `check` also catches what was written in by hand.
- **An edit to a block's context passed unnoticed.** The fingerprint took only `paths`, while the
  prompt also gives a block its `ref_paths`. Now a fingerprint of the context is taken too; its
  divergence is a **warning**, not a refusal, like the "suspect link" at doorstop. The measurement
  of why not a refusal: the context of one block in the very first project — 229 files and 12
  commits in two weeks; a refusal would go red almost daily and would train people to hit
  `restamp` without looking.
- **An untouched template line "Complete / incomplete — …" counted as a coverage assessment.**
- **A fix in a shared module could not be marked honestly.** The commit had to touch the
  finding's file, whereas a route, for instance, is fixed in a shared guard. The place of the fix
  is now named explicitly — `set-finding <ID> fixed --commit <sha> --fixed-in <path>`; the path
  is checked, and the commit must touch the finding's file or one of the named ones.
- **A caveat in a line flipped the verdict.** "Checked by the code … not checked with a live
  request" read as "not checked": the words were searched in dictionary order, not in line
  order. Now the verdict is the word that comes earlier. On a real review, of 73 verdicts exactly
  two changed, both had been read wrongly.
- **A rejection changed only the status.** The finding stayed both `rejected` and `confirmed` at
  once. Now `set-finding … rejected` also sets the confidence, a return to work resets it to
  `plausible` (awaits a new verification), and `check` catches a divergence written in by hand.
- **The hypotheses fingerprint took only the first line of an item.** The scenario and the
  expectation written under the hypothesis with an indent were edited unnoticed. Now the whole
  item goes into the fingerprint.
- **An empty "Coverage limits" section passed the check** — a heading without text, as did the
  copied template instruction. Now text is needed: what was not looked at, or a direct "none".
- **A repeated import re-took the code fingerprint of a known finding** — and a stale finding
  vanished from `check` without re-verification. Now the fingerprint for the same id and file is
  kept; to confirm the finding on the new code — `restamp <ID>`.
- **`import --append` crashed on a block file.** After a regular import the file holds the
  already recorded findings with numbers, and the top-up stopped at the first of them; it worked
  only with a file holding a single delta. On top of that it renamed the block file to
  `.jsonl.merged`. Now the recorded ones are skipped, new lines get free numbers, the numbers are
  written back into the file; a repeated run appends nothing.
- **Symlinks dropped out of the review entirely** — no owner, no "uncovered", no fingerprint,
  and the link could be redirected unnoticed. The exclusion in 0.2.0 cured the double count the
  wrong way. Now a symlink is a file of the block; the lines and the fingerprint are taken from
  the link's text, not from the target, so there is no double count, and a redirect is caught
  even to a target with the same content. Submodules are still excluded: their code is reviewed
  in their own repository.
- **A path with a space broke the fix-commit check**: the commit's file list was split on
  spaces, and a commit touching `src/my file.ts` was declared "not touching".
- **Hypotheses were counted by one parser and fingerprinted by another.** The counting one did
  not know about code blocks: `# comment` in an example cut the section short, `- line` in it
  became a hypothesis. Now there is one parser, and it skips code blocks.
- **The installer warns if `.gitignore` lacks `__pycache__/`.** Bytecode appears as soon as
  somebody imports the tool as a module, and leaks into a commit — in the very first project that
  is what happened.
- **Deliberately not changed:** "not checked" remains a lawful verdict even in `closed`.
  Completeness is proven by listing the unchecked, not by its absence (coverage limits at Trail
  of Bits, "pass, fail or a written justification" in ASVS); a ban would push people to write
  "checked" where they did not check.

⚠️ What the report check does NOT do: it does not match the verdict on each finding against the
report. The numbers in the register are issued by `import` after the verification, and the
report does not have them. The verdict on each finding is its `confidence` field, which `check`
requires of every record; but that it was set by the verifier rather than the hunter is proven by
nothing. This is an open question, not settled by the form.

### Breaking

- A check passed on 0.2.0 may go red: blocks after verification and open findings without
  fingerprints (of files, hypotheses, the code under the finding) are now a refusal. What to do:
  `backfill` once after updating. A guard recorded as a rule name without a file — rewrite it as
  a path to the linter config or a test. The `coverage.tsv` header with a commit is still read;
  it will be overwritten at the next `coverage`.
- Symlinks are now part of the composition: in a repository that has them, `coverage` will show
  them as uncovered until they are assigned to a block, and passed blocks with links will get a
  changed fingerprint — `restamp`, if the links were not touched after verification.
- The hypotheses fingerprint formula changed: for blocks stamped earlier, `check` will report
  that the hypotheses changed. If `git log` over the manifests since the stamp is empty — it is
  only the formula: `restamp <BLOCK>` and a journal line (`log <BLOCK> "…"`) with that reason.

## [0.2.0] — 2026-09-22

A release about the method ceasing to rest on attention: three mechanisms that lived as text in
prompts became checks, and claims about the method itself became measurements with a method.
Plus the first real portability bug, found before it bit anyone.

### Added

- **The reading budget stands in the task itself.** The hunter's prompt prints the block's
  volume — files, lines, the order of magnitude in tokens — and if the block is larger than what
  is readable in a session, shows where the boundary runs: files by descending size with a
  running total and a mark of what is overboard. This is not a ban on opening them but a duty to
  name the unread by name.
- **A defect class is closed by a guard, not by a list of edits.** A finding got a `root` field
  (the class name) and `rule` (what the class is closed by); from the third instance the check
  requires a guard. The guard is set on the whole root at once — `set-finding <ID> <status>
  --rule <path>`. The new `roots` command shows the classes, the number of live instances and the
  state of each. Rejected findings and duplicates do not count as instances.
- **Top-up import of findings** — `import --append`: appends the new without touching what is
  already recorded and fixed, and marks the top-up file as merged. A regular import replaces the
  block's findings entirely, and for a block in progress that erased the fix marks.
- **A configurable readability ceiling** — `readable_lines` in `blocks.json`. The default of
  6000 was derived from TypeScript, and the median change size differs between languages by two
  to three times.
- **Checks carried over from the experience of neighbouring projects**: the fix commit must
  exist and touch the finding's file; a block status written in bypassing `set-status`; a manifest
  shorter than two hundred characters; `running` without a timestamp or with an unreadable one.
- Documents: `measurements` (knowledge base) — all measurements with the method
  and the limits of transfer; `prior-art` (knowledge base) — who has already solved
  the plan's tasks and how it went for them, including the section "what cannot be used to
  measure"; the roadmap (knowledge base) — seven directions and what is not worth doing.
- A banner in the README: the three roles the method stands on.

### Measured

- **The experience of three projects, 587 findings.** The first — 27 blocks of 27 (313
  findings, 256 fixed), the second — 8 of 13 (210 findings), the third — 4 blocks. The share of
  rejected coincided on all three: **2.6%, 3.8% and about 3%** — the same result the measurement
  with planted findings gave, but on a sample fifty times larger.
- ⚠️ What this does not prove: all three projects are TypeScript, all by one author, and part of
  the code in them was written by the same AI that then reviewed it.

### Fixed

- **`git ls-files` returns what cannot be opened.** A submodule crashes the line counter, a
  symlink is counted twice, a sparse checkout prints paths that are not on disk, LFS hands over
  a pointer instead of the file. Now the composition is taken from `ls-files --stage` without
  modes `160000` and `120000`, and the content is read via `git show :path`. In our three projects
  none of this was present — in the very first foreign repository the coverage denominator would
  have drifted silently.

## [0.1.0] — 2026-09-21

The first release of this repository. The kit came ready-made from the author of a neighbouring
project (an archive of 16.09.2026, the analysis is in `how-it-works` (knowledge base));
here it is brought into a state where it can be installed into any project, and checked against
world practice.

### Added

- **The installer** `install.py`: installs the tool, the templates and the entry point, starts a
  skeleton of the block definition and the invariants, writes the `CLI` string from which all the
  hints are assembled. A repeated run adds what is missing and does not touch what was edited by
  hand.
- **Tests** — 25 scenarios via the command line, only `git` and the standard library. Proven by
  mutation: every edit to the tool breaks exactly one test.
- **Hypotheses as the second coverage denominator.** The manifest's hypotheses are numbered, each
  is closed by a verdict "checked / not checked / not applicable"; `check` requires a verdict on
  all, `hypotheses <BLOCK>` shows what is closed. The report's plain language is parsed too: a
  summary table, "hypothesis 2 was not confirmed", "refuted".
- **A mandatory coverage-limits section** in the hunter's report: what was deliberately not read
  and why. The headings "Coverage limits", "Not read from the block", "What I did NOT do" are
  recognised.
- **The fingerprint of what was reviewed** (the idea — [doorstop](https://github.com/doorstop-dev/doorstop)).
  Moving a block to `verified`/`closed` remembers the fingerprint of the composition and content
  of its files; `check` catches a block closed on a different version of the code. To confirm a
  review of edits — `restamp <BLOCK>`.
- **The fingerprint of the code under a finding.** An open finding remembers the hash of the file
  it speaks about: the code moved on — so either it was fixed or the description is stale, and
  the check requires a decision.
- **Line number check**: a reference to a line the file does not have is caught without a model
  (the idea — [mergejury](https://github.com/iamEtornam/mergejury)).
- **Tree freshness check**: if the server's tip is older than ours by more than a week, the check
  fails. Time is measured, not commits.
- **The `set-finding` command**: moves a finding and does not allow setting `fixed` without a
  commit, `rejected` without a reason, `duplicate` without a reference.
- **The coverage map names the commit** it was assembled from, and `check` verifies that the
  snapshot is from this line of history.
- **The `{{PROJECT}}` and `{{GATES}}` substitutions** from `blocks.json` — the prompt template
  no longer greets the agent on behalf of someone else's project.
- **`make` targets** (`example/makefile-snippet.mk`) and the same list for `package.json`.
- Documents: `comparison-with-practice` (knowledge base) — a check of
  the method against the methodology of audit firms, the practice of Google and Meta, industrial
  AI reviewers, science and neighbours in the niche on GitHub.

### Changed

- **The repository root is asked from git**, not counted from a file: the tool can be put
  wherever suits the project.
- **The prompt subtracts the exclusions** — the same as the coverage map and the readability
  ceiling. Before, a block was given to work on what was not counted in its size.
- **The verifier's verdict overrides the hunter's verdict**: reports are read by role, `verify`
  is applied last.
- **The manifest is asked only of a block that has reached work**, not of all at once: otherwise
  the check is red from the first day and people stop reading it.
- **The block's readability ceiling** (6000 lines) is counted without excluded files.
- **A coverage refusal says what to do**, and why the choice of block is made by a human.
- Prompts: the verifier verifies by execution and defines a duplicate through the root; the fixer
  closes the defect class with a guard and presents a green run instead of the word "fixed"; the
  hunter checks against `origin` before filing a finding, and in a neighbouring repository — via
  `git fetch` and `git show origin/master:<file>`.
- File names — in Latin letters.

### Fixed

- `example/makefile-snippet.mk` contained not the review targets but a fragment of another
  project's SAST targets: **not one** `make review-*` command from the documentation existed.
- The documentation called `prompt BLOCK ROLE`, the tool requires `prompt BLOCK --role`.
- A block was closed with one hunter's report, without the verifier's report.
- A stale coverage map was not caught.
- The findings register was edited by hand contrary to its own rule: a command for moving a
  finding did not exist.
- The rejection reason was declared a condition of finishing the review but was demanded by
  nothing.
- The hints in messages called now `make`, now `npm run` — the tooling was transferred between
  projects and not proofread.

### Measured

- **The verifier was slipped six deliberately false findings mixed with six real ones** — all six
  rejected, by both models. The suspicion "the verifier agrees" is lifted.
- **The pair "hunter + verifier" against two independent hunters** on one block: the verifier
  came out 41% cheaper than the second hunter, checked all the findings, found its own and
  resolved a direct contradiction between the hunters. Zero rejected of 18 — a hunter obliged to
  present a failure scenario brings no fabrications.
- ⚠️ The first counterexample to this: the verifier confirmed by execution a defect that does not
  exist — the working copy of the neighbouring repository was 12 days behind. What failed was not
  the reasoning but the tree's freshness; hence the freshness check and the rule in the prompts.

[Unreleased]: https://github.com/mikey-semy/finetooth/compare/v0.7.0...HEAD
[0.7.0]: https://github.com/mikey-semy/finetooth/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/mikey-semy/finetooth/compare/v0.5.1...v0.6.0
[0.5.1]: https://github.com/mikey-semy/finetooth/compare/v0.5.0...v0.5.1
[0.5.0]: https://github.com/mikey-semy/finetooth/compare/v0.4.1...v0.5.0
[0.4.1]: https://github.com/mikey-semy/finetooth/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/mikey-semy/finetooth/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/mikey-semy/finetooth/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/mikey-semy/finetooth/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/mikey-semy/finetooth/releases/tag/v0.1.0
