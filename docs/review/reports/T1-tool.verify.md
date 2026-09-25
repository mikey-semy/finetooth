# T1 — verifier report

## How this was checked

Everything below rests on what was **run**, not on what was read. The stand is four scripts,
each executed once:

- a parser stand that imports `review.py` and drives `line_verdict`, `verdict_word_at`,
  `verdict_mentions`, `section_items_full`, `hypotheses`, `demote`, `verify_report_problem`,
  `COVERAGE_VERDICT` and `mass_cutoff` over a matrix of inputs;
- an end-to-end stand that builds scratch git repositories and calls the tool the way a
  project does (17 scenarios: `init`, `import`, `check`, `set-finding`, `set-status`,
  `summary --aged`, `prompt`, `hypotheses`, plus `guard-grep.sh`, `run-role.sh` with a stub
  `claude`, and `axes.py` on three synthetic streams);
- a mutation stand: 39 mutants of the kit, one `check` gate silenced in each, the whole
  suite run against every one of them, plus a 16-at-once run and three controls;
- a loose-ends stand: `MSG` key and placeholder arithmetic over all 46 `T()` call sites,
  the `guard-grep.sh` marker window, and the git version.

**Tree freshness.** `HEAD` is `c5fd231`, identical to `origin/dev` (which
`refs/remotes/origin/HEAD` points at); `git log HEAD..origin/dev` is empty after a fetch.
Every verdict below was produced on that tree.

## Verdicts on hunter findings

All twenty-one hold up. That is an unusual outcome and it deserves a word: the hunter's
claims are narrow and anchored to a line of code, and where it was wrong it was wrong about
**scope or scale**, not about whether a defect exists. Those corrections are recorded in the
rows below and are carried into the final findings file rather than filed as rejections.
Two findings the hunter could only read (`T1-004`, `T1-017`) are now reproduced by
execution; one severity goes up, two go down.

| id | verdict | severity after checking | justification |
|---|---|---|---|
| T1-001 | CONFIRMED | high (unchanged) | Reproduced end to end. A scratch project whose hunter report quotes the template skeleton inside a ` ```markdown ` fence and answers nothing gives `hypotheses H1` → "closed 3/3" and `check` → exit 0, "review state is consistent". The location is right too: `references/hunter.md:85-87` sits inside the fence opened at line 69, with the block id already substituted. |
| T1-002 | CONFIRMED | medium (unchanged) | Run on the parser. A headed gate table yields `{}` — the 2151 fix holds — while the identical table written without a header row yields `{Z9.1: checked, Z9.2: not checked}`. The T1 acceptance criterion asks for exactly such a table. |
| T1-003 | CONFIRMED | medium (unchanged) | `verdict_word_at` admits `n/a` after a backtick, a quote, a paren and a bracket (positions 1, 1, 1, 1); only `/` and `\w` are refused. Four of a 25-line matrix diverge — see table 3. The hunter missed one of its own rows: "the block moves to verified after the report" scores **checked** on the bare word `verified`, with no code span involved. Folded into this finding's scenario. |
| T1-004 | CONFIRMED | medium (was plausible) | Executed: a manifest with a `~~~markdown` block between hypotheses 2 and 3 yields `['T1.1','T1.2']` — two of four — while the same manifest with a ` ``` ` fence yields all four. The hunter's guess about the 4-space indented code block is right (harmless). It missed that `demote()` has the same blind spot: it pushes the heading inside the `~~~` fence down a level when the manifest is pasted into a prompt. |
| T1-005 | CONFIRMED | medium (unchanged) | Executed. With the file laid out: `block_sha` `4cfb25c…`, `block_lines` (3, 5). After `rm src/api.ts` with the index untouched: `ls-files` still lists it, `file_lines` still returns 3 **from the index**, but `file_sha` → `None`, `block_sha` → `14f3f77…`, `block_lines` → (3, 2). From then on the file contributes only its name to the fingerprint. |
| T1-006 | CONFIRMED | medium (unchanged) | Reproduced end to end, not just with git. `set-finding H1-001 fixed --commit <sha>` succeeds on `src/модуль.ts`; `check` then prints "commit … does not touch src/модуль.ts" for ever, while the sibling finding on `src/plain file.ts` passes. `show --name-only` prints the octal-escaped form, `ls-files -z` the raw one. |
| T1-007 | CONFIRMED | medium (unchanged), **count corrected upward** | Proven by mutation, which the hunter did not run. Its list of 14 is an undercount and its table is wrong in five places: gates 8 (verifier report missing), 19 (external fix form), 22a (duplicate without `dup_of`), 32 (unowned files) and 40a (missing hypotheses fingerprint) are credited to tests that do not in fact detect their removal, and gates 6, 13 and "finding refers to a nonexistent block" are untested as well. The measured number is **24**. Three controls go red, so the harness works. |
| T1-008 | CONFIRMED | medium (unchanged) | Reproduced: exit 1 with the violation printed while `internal/billing` exists; after `mv internal/billing internal/payments` the same command prints nothing on stdout or stderr and exits 0. |
| T1-009 | CONFIRMED | medium (unchanged) | Reproduced. Two records both carrying `H1-001`; `check` reports "duplicate id" and names no way out; `set-finding H1-001 rejected` moves only the first and leaves the second open. Severity held at medium not because the state is silent — it is loud — but because the tool offers no way back out of it. The hunter's `root` field was empty; set to `hand-assigned ids without a uniqueness check`. |
| T1-010 | CONFIRMED | medium (unchanged) | Reproduced on four commands: `status` and `order` → `KeyError: 'phase'`, `summary` and `prompt` → `KeyError: 'slug'`, all exit 1; and `check` dies the same way once the block leaves `todo`. |
| T1-011 | CONFIRMED | **low** (was medium) | The gate really is silently inert — measured with no remote at all and with a remote named `upstream` (`symbolic-ref` → "fatal: not a symbolic ref"), `check` exits 0 either way. But the hunter's headline scenario is wrong on current git: on 2.55 `git remote add origin` + `git fetch` **does** create `refs/remotes/origin/HEAD`, so the CI shape it describes is protected. What remains is the no-remote vendored copy and the non-`origin` remote — real, but narrower. |
| T1-012 | CONFIRMED | medium (unchanged) | Reproduced with a stub `claude` that exits 1: run-role.sh prints "claude exit: 1" and then writes `hunter — spend: 0 min, None turns, … $0.00` to the journal anyway. The hunter's note about the bad block id is right too: exit 2 before the journal, a zero-byte prompt file left in `TMPDIR`. |
| T1-013 | CONFIRMED | low (unchanged) | The measurement reproduces exactly: 41 first-parent commits with `--follow`, 9 under the current path, renames `R090` and `R099`, and `show --name-only` on the rename commit prints only the new path. |
| T1-014 | CONFIRMED | low (unchanged), **claim narrowed** | The substring half is real and executed: with `owned = [src/api.ts, src/api.ts.snap, src/x.py]` and a report naming only the snapshot and `src/x.py`, `missing` is empty. The other half of the hunter's claim — that pasting the prompt's file list satisfies the gate — is true but is not a defect: no text gate can verify that a file was read, and the gate's stated job is to force the claim to be made per file. The claim is narrowed to the substring bug. |
| T1-015 | CONFIRMED | low (unchanged) | Arithmetic run over histories of 1…100 commits: cutoff equals the largest commit up to n = 20 (12→12, 19→19, 20→20) and only starts to bite from 21 (21→20, 100→96). |
| T1-016 | CONFIRMED | low (unchanged) | Reproduced: a block titled `Import --> export pipeline` makes `summary --aged` die with `JSONDecodeError: Unterminated string`, exit 1; a title ending in `-->` fails identically. |
| T1-017 | CONFIRMED | low (was plausible) | Both halves executed. Complete stream: "10 min, 42 turns, … output 21k, $3.41". The same stream with the `result` event removed: "0 min, None turns, … output 0k, $0.00", exit 0. The same stream with its last line cut short: `JSONDecodeError`, exit 1. |
| T1-018 | CONFIRMED | low (unchanged) | Two consecutive no-op `init` runs differ in `updated_at` and in nothing else. |
| T1-019 | CONFIRMED | **medium** (was low) | Raised, because this is the same class as T1-001 and I reproduced it end to end: a verifier report whose entire body is "I completed the check of every finding; nothing was confirmed." passes `verify_report_problem` and `check` exits 0 on the block. The hunter under-rated it. I also measured the mirror: the Russian half of `COVERAGE_VERDICT` matches neither "Проверка завершена полностью" nor "все находки проверены", so an honest `lang: ru` report is refused. Both halves are the one regex; folded in. |
| T1-020 | CONFIRMED | low (unchanged) | Read against every other constant in the file, each of which carries its source. The four named (lines 1169, 2263, 121–122, 806) carry none. |
| T1-021 | CONFIRMED | low (unchanged) | Reproduced: `{{HUNTER_NOTE}}` in the manifest makes `prompt` exit 2 blaming `hunter.md`; and with only `{{FILES}}` left, the manifest's own sentence renders as "The template uses src/api.ts / src/api.ts.snap / src/x.py as placeholders". |

### Hunter claims I checked and could not uphold as stated

These did not become findings, but the hunter asserted them and they are wrong or
incomplete:

- **"guard-grep.sh's awk contract is correct"** (Checked and found correct). It is not — see
  T1-022 below. This is the one place where the hunter's "found correct" list hides a defect.
- **Table 1's test column.** Five gates are credited to tests that do not detect their
  removal (listed under T1-007). A table of tests that was never run is a table of guesses.
- **T1-011's CI scenario.** `git init && git remote add origin && git fetch` does create
  `origin/HEAD` on git 2.55.
- **Table 3 row 11.** The hunter marked it "wrong" and then did not carry it into a finding;
  it is now part of T1-003.

## Own findings

Three places I read independently, without its conclusions: `guard-grep.sh`'s marker
pairing (the mechanism the script exists for), the boundary where hand-written
`blocks.json` text reaches git, and the finding-shape gates in `cmd_check`.

### T1-022 · medium · One marker exempts every hit in the window below it
**Location:** `skills/finetooth/assets/guard-grep.sh:95`
**What is wrong:** the awk loop `for (i = FNR - window; i < FNR; i++)` exempts a hit if the
marker stands anywhere in the `window` lines above it. With the default window of 3, one
marker therefore covers the next three hits, not the one it was written above.
**Failure scenario:** executed on a file with `// outbox-allowed:` on line 2 and
`broker.Publish(` on lines 3, 4, 5 and 6. Only line 6 is reported; three calls are
silently exempted by one escape hatch.
**Why it is a defect:** the script's header states this as its whole reason to exist — "grep
runs consecutive hits together into ONE block … a marker granted to the first call silently
exempts the second one three lines below it", and "here each hit is paired with the marker
by LINE NUMBER … so a marker covers exactly the call it was written above and nothing else".
The rewrite reproduces the defect it was written to replace. A project that adopted the gate
on that promise now lets through every forbidden call within three lines of an existing
hatch. (Pairing *within one file* by line number is genuinely fixed — the regression is only
the window's breadth; the honest fix is to bind a marker to exactly one hit.)
**Confidence:** confirmed (executed)
**Root:** a gate that cannot go red

### T1-023 · low · A pathspec git rejects reaches the user as a traceback
**Location:** `skills/finetooth/scripts/review.py:300`
**What is wrong:** `listed()` runs `git ls-files --stage -z -- <pathspecs>` with
`check=True`. Every pathspec in `blocks.json` — a hand-edited file — goes through it
unvalidated.
**Failure scenario:** executed with a `paths` entry of `:(nosuchmagic)src`, a typo in the
pathspec magic the kit itself invites projects to use: `check` exits 1 with
`subprocess.CalledProcessError`, `coverage` the same, while `status` exits 0 because it
never expands the pattern. git's own message ("Invalid pathspec magic") is swallowed.
**Why it is a defect:** invariant 12 — a traceback reachable from a legal command line, with
an exit code that reads as "the state is red". The neighbouring gate at 2458 handles a
pattern that matches *nothing*; a pattern git refuses to *parse* has no handler.
**Confidence:** confirmed (executed)
**Root:** hand-edited input reaches the code unvalidated

### T1-024 · low · A string line number skips the cited-line gate
**Location:** `skills/finetooth/scripts/review.py:2412`
**What is wrong:** the gate is guarded by `f.get("line") and isinstance(f["line"], int)`. A
draft findings file is hand-written JSONL, where `"line": "2137"` is an ordinary slip, and
`import` copies the field through untouched.
**Failure scenario:** executed with two identical open findings on a 3-line file, one citing
`9999` and one citing `"9999"`. `check` reports only the first; `findings.md` renders both
as `src/api.ts:9999`.
**Why it is a defect:** the gate's own comment calls it "the cheapest sign of fabrication".
A check that a wrong type silently switches off is not a check; the type belongs in the
vocabulary gates next to `severity` and `status`.
**Confidence:** confirmed (executed)
**Root:** report parser matches shape, not meaning

## Acceptance tables

### Table 1 — gate → test → mutation (built by execution)

Every gate of `cmd_check` was silenced in its own copy of the kit and the whole suite run
against it. "covered" means the suite went red and names the test that did; "NO TEST" means
it stayed green. Baseline on the untouched copy: OK.

| # | gate | outcome | test that went red / — |
|---|---|---|---|
| 1 | block in blocks.json missing from state (2227) | NO TEST | — |
| 2 | block in state missing from blocks.json (2230) | NO TEST | — |
| 3 | block status outside the vocabulary (2233) | covered | test_статус_блока_вписанный_руками_роняет_проверку |
| 4 | phases do not decrease (2242) | covered | test_фазы_в_массиве_не_убывают |
| 5 | blocked without a note (2251) | covered | test_заблокированный_блок_не_значит_закончено |
| 6 | manifest missing (2261) | NO TEST | — |
| 7 | manifest shorter than 200 chars (2263) | covered | test_куцый_манифест_роняет_проверку |
| 8 | verifier report missing (2274) | NO TEST | — (the hunter credited test_закрытие_с_починками) |
| 9a | verifier report empty (1990) | covered | test_пустой_отчёт_проверяющего_не_проводит_блок |
| 9b | verifier report: no finding verdict (2008) | covered | test_пустой_отчёт_проверяющего_не_проводит_блок |
| 9c | verifier report: no coverage verdict (2013) | covered | test_английские_заглушки, test_без_находок_проверяющий_говорит_об_охвате, test_нетронутая_строка_шаблона, test_пустой_отчёт |
| 10 | declared report not on disk (2286) | NO TEST | — |
| 11 | no hunter report past running (2294) | NO TEST | — |
| 12 | running without a timestamp (2301) | NO TEST | — |
| 12b | unparsable started timestamp (2308) | NO TEST | — |
| 13 | running longer than 24 h (2311) | NO TEST | — |
| 14 | duplicate finding id (2322) | NO TEST | — |
| 15 | mandatory field empty (2326) | NO TEST | — |
| 16 | finding refers to a nonexistent block (2328) | NO TEST | — (absent from the hunter's table) |
| 16a–c | severity / confidence / status vocabulary (2330–2334) | NO TEST | — |
| 17 | open finding on a missing file (2338) | covered | test_починенная_находка_на_удалённом_файле_не_роняет_проверку |
| 18 | deferred without a reason (2343) | covered | test_отложенная_находка_требует_причину |
| 19 | external fix commit form (2348) | NO TEST | — (the hunter credited test_починка_в_соседнем_репозитории) |
| 20a | fix commit does not exist (2367) | covered | test_коммит_починки_обязан_касаться_файла_находки, test_починка_в_соседнем_репозитории |
| 20b | fix commit does not touch the file (2369) | covered | test_коммит_починки_обязан_касаться_файла_находки, test_починка_в_общем_модуле_называется_явно |
| 21 | fixed without a commit (2377) | NO TEST | — |
| 22a | duplicate without dup_of (2379) | NO TEST | — (the hunter credited test_дубль_указывает_на_живую_находку) |
| 22b | dangling / self / dead duplicate (dup_problem) | covered | test_дубль_указывает_на_живую_находку |
| 23 | confidence rejected but status open (2383) | NO TEST | — |
| 24 | status rejected, confidence not (2385) | covered | test_отказ_меняет_и_уверенность |
| 25 | open finding without code_sha (2393) | covered | test_старые_записи_без_отпечатков_ловятся_и_дописываются |
| 26 | code_sha changed since import (2399) | covered | test_изменившийся_код_под_открытой_находкой, test_живая_находка_на_изменённом_файле, test_повторный_импорт_не_переснимает |
| 27 | cited line beyond the file (2412) | covered | test_несуществующая_строка_в_находке, test_строка_за_концом_файла_у_починенной_находки |
| 28 | rejected without a reason (2422) | covered | test_отвергнутая_находка_без_причины_роняет_проверку |
| 29 | claim / scenario over the cap (2435, 2440) | NO TEST | — |
| 30 | findings.md diverged from the register (2450) | NO TEST | — |
| 31a | pattern matches nothing (2467) | covered | test_шаблон_который_ничего_не_нашёл_роняет_проверку |
| 31b | pattern matches only untracked files (2461) | covered | test_шаблон_по_нетрекнутым_файлам_зовёт_git_add |
| 32 | unowned files (2474) | NO TEST | — (the hunter credited test_непокрытый_файл_роняет_карту, which covers `coverage`, not `check`) |
| 33 | coverage.tsv stale (2489) | covered | test_устаревшая_карта_покрытия_роняет_проверку |
| 34 | manifest without hypotheses (2505) | covered | test_манифест_без_гипотез_роняет_проверку |
| 35 | contradictory verdicts in one report (2515) | covered | test_противоречивые_вердикты_в_одном_отчёте |
| 36 | hypothesis without a verdict (2523) | covered | test_гипотеза_без_вердикта, test_проверки_не_выключаются_переводом_в_следующий_статус |
| 37 | post-verify block without reviewed_sha (2540) | covered | test_старые_записи_без_отпечатков_ловятся_и_дописываются |
| 38 | block files changed after the review (2545) | covered | test_блок_просмотренный_на_другой_версии_файлов, test_перенаправленный_симлинк, test_промежуточный_статус |
| 39 | ref_paths changed — warning (2559) | not measurable this way | the mutation silences `problems`, not `warnings` |
| 40a | hypotheses fingerprint missing (2564) | NO TEST | — (the hunter credited test_правка_гипотез) |
| 40b | hypotheses fingerprint changed (2569) | covered | test_правка_гипотез_после_проверки, test_правка_продолжения_гипотезы_ловится |
| 41 | every block file named by full path (2596) | covered | test_каждый_файл_блока_назван_полным_путём |
| 42 | closed with fixes but no fixreview (2612) | covered | test_закрытие_с_починками_требует_ревью_правок |
| 43a | coverage-limits section missing (2627) | covered | test_отчёт_без_раздела_про_непросмотренное, test_ограничения_охвата_требуются_и_после_проверки |
| 43b | coverage-limits section empty (2633) | covered | test_пустой_раздел_ограничений, test_английские_заглушки_шаблона_ловятся |
| 44 | third instance of a root without a guard (2644) | covered | test_третий_повтор_корня_требует_узду |
| 45 | guard path does not exist (rule_problem) | covered | test_узда_обязана_существовать |
| 46 | tree behind origin (2663) | covered | test_отставшее_от_сервера_дерево, test_свежий_коммит_в_давней_ветке |
| 47 | proof outside the vocabulary (2676) | NO TEST | — |
| 48 | block above the readability ceiling (2684) | covered | test_блок_который_за_сеанс_не_прочитать, test_порог_читаемости_задаётся_проектом |
| 49 | open findings older than 7 days — warning (2691) | not measurable this way | warnings are not silenced by the mutation |

**24 checks stay green when silenced** (rows marked NO TEST, counting the three vocabulary
branches and the two cap branches separately) → finding T1-007. The two warning-only gates
could not be measured by this mutation and are recorded as a coverage limit, not as a result.

### Table 2 — `MSG` keys, en vs ru (computed, not eyeballed)

| set | count | difference |
|---|---|---|
| `MSG["en"]` | 56 | — |
| `MSG["ru"]` | 56 | — |
| en − ru | 0 | — |
| ru − en | 0 | — |

Placeholder sets compared with `string.Formatter().parse` (which sees `{block:<6}`, unlike a
naive `\{(\w+)\}`): **no key differs**. All 46 `T(...)` / `MSG[lang][...]` call sites were
extracted from the source and checked against both tables — every key exists on both sides
and every call passes the keyword arguments its message needs, in both languages. Every
message was also run through `.format()` with its own fields: none raises. **No finding.**
The exposure the hunter names remains structural and is real: two hand-maintained literals
with no test comparing them.

### Table 3 — report line → verdict (run, not derived)

`Z9` stands in for the block id so these samples do not register as verdicts on this
report's own hypotheses — which is itself finding T1-001 in miniature.

| # | line | expected | actual | |
|---|---|---|---|---|
| 1 | `` - `Z9.1 — checked: proven by running the code` `` | checked | checked | |
| 2 | `- Z9.2 — not checked: no live system` | not checked | not checked | |
| 3 | `- Z9.3 — not applicable: not about this code` | not applicable | not applicable | |
| 4 | `- Z9.4 — гипотеза подтвердилась` | checked | checked | |
| 5 | `- Z9.5 — не проверена` | not checked | not checked | |
| 6 | `- Z9.6 — гипотеза не подтвердилась` | checked | checked | |
| 7 | `the path features/curation/adapter.ts holds the word` | none | none | |
| 8 | `see https://example.com/not-applicable/x` | none | none | |
| 9 | `` - Z9.7 — the `n/a` token in a path is handled; checked by test `` | checked | **not applicable** | wrong |
| 10 | `` - Z9.8 — `checked` is only a code span here, in fact not examined `` | not checked | **checked** | wrong |
| 11 | `- Z9.9 — the block moves to verified after the report` | none | **checked** | wrong |
| 12 | `- Z9.10 — checked` | Z9.10 checked | Z9.10 checked (greedy `\d+`) | |
| 13 | `- Z9.11 — the tree is complete and the fix is not checked` | not checked | not checked | |
| 14 | `hypothesis 2 refuted by experiment` | .2 checked | .2 checked | |
| 15 | `гипотеза №3 опровергнута` | .3 checked | .3 checked | |
| 16 | `- Z9.12 — unverified area` | not checked | not checked | |
| 17 | `- Z9.13 — not confirmed, the code is correct` | checked | checked | |
| 18 | `nothing here at all` | none | none | |
| 19 | `- Z9.14 — see docs/n/a-policy.md; checked` | checked | checked | |
| 20 | `` - Z9.15 — the report says `not checked` but I did check it `` | checked | **not checked** | wrong |
| 21 | `- see file curation/n/a.ts` | none | none | |
| 22 | `- Z9.16 — verified against production` | checked | checked | |
| 23 | `- рассмотрено, гипотеза неприменима` | not applicable | not applicable | |
| 24 | `- Z9.17 — n/a` | not applicable | not applicable | |
| 25 | fenced block quoting `` `Z9.1 — checked: <what proves it>` `` | none (an example) | **checked** | wrong (T1-001) |
| 26 | fenced block quoting `Z9.2 — not checked: <what got in the way>` | none | **not checked** | wrong (T1-001) |
| 27 | headed table `\| # \| gate \| test \| mutation \|` + numbered rows | none | none (the 2151 fix holds) | |
| 28 | header-less `\| 1 \| gate one \| test_a \| confirmed \|` | none | **.1 checked** | wrong (T1-002) |
| 29 | header-less `\| 2 \| gate two \| test_b \| not checked \|` | none | **.2 not checked** | wrong (T1-002) |
| 30 | headed `\| # \| hypothesis \| outcome \|` + `\| 1 \| … \| refuted \|` | .1 checked | .1 checked | |

Boundary probes for `n/a` (`verdict_word_at`): matched after a backtick, a double quote, a
paren and a bracket; refused inside `a/n/a` and `curation/n/a.ts`. The greedy `\d+` claim
holds: `Z9.1` is not matched inside `Z9.10`, and letter-suffix ids (`V1d.3`) work because
the id comes from the definition.

## Hypotheses

- `T1.1 — checked: computed, not eyeballed.` `MSG["en"]` and `MSG["ru"]` hold the same 56
  keys; placeholder sets agree key for key under `string.Formatter`; all 46 call sites
  resolve on both sides and pass the arguments their messages need; every message survives
  `.format()`. No defect. See table 2.
- `T1.2 — checked: three live false positives, one of them new.` 25-line matrix through
  `line_verdict` plus fence and table probes — see table 3 and findings T1-001, T1-002,
  T1-003.
- `T1.3 — checked: one hole, wider than reported.` `~~~` fences are invisible to
  `section_body`, `section_items_full` **and** `demote`; an indented ` ``` ` fence and a
  4-space code block are safe. Finding T1-004.
- `T1.4 — checked: one fingerprint misses its subject.` Executed both ways: an edit to a
  tracked file and a new file added to the block both turn the gate red, so the mechanism
  works; what it misses is any file not laid out on disk (T1-005) and the part of a
  manifest cut off by a `~~~` fence (T1-004).
- `T1.5 — checked: one silent false match and one traceback.` Pathspecs reach git after
  `--`; two blocks owning one file is handled. The named-files gate is a substring test
  (T1-014), and a pathspec git refuses to parse crashes the tool (T1-023).
- `T1.6 — checked: the collision is reachable and reproduced.` Finding T1-009; `--append`
  is collision-free and its re-run is a no-op.
- `T1.7 — checked: it is all-or-nothing, proven by running it.` `set-finding A B UNKNOWN
  rejected` printed both per-id lines, then died on the third, and the register was left
  untouched — both findings still `open`/`confirmed`. The rename case behaves as the hunter
  says and the message names `--fixed-in`, which is the documented way out.
- `T1.8 — checked: no mid-check die, but tracebacks are reachable.` Warnings never change
  the exit code and problems give exit 1; what reaches the user is `KeyError` on a
  hand-written block (T1-010) and `CalledProcessError` on a bad pathspec (T1-023).
- `T1.9 — checked: the gate is silently inert, in a narrower set of cases than reported.`
  Finding T1-011.
- `T1.10 — checked, measured on this repository.` 41 commits with `--follow` against 9 under
  the current path. Finding T1-013.
- `T1.11 — checked: on a history of 20 commits or fewer nothing is ever skipped.` Arithmetic
  run over 1…100. Finding T1-015.
- `T1.12 — checked: a legal title breaks it.` Reproduced twice (a title containing the
  marker and a title ending in it). Finding T1-016.
- `T1.13 — checked: the journal lies about a cut-off run.` Reproduced with a stub. Finding
  T1-012.
- `T1.14 — checked by execution this time: a killed run reports as free.` Three synthetic
  streams. Finding T1-017.
- `T1.15 — checked: idempotent in substance, not on disk.` Statuses, `started`, `finished`,
  `reports` and all three fingerprints survive; only `updated_at` is rewritten. Finding
  T1-018.

## Block coverage status

**The block is complete.** All four files were read in full by me, independently of the
hunter, and every one of them is executed somewhere in the stand:

```
skills/finetooth/assets/guard-grep.sh
skills/finetooth/assets/run-role.sh
skills/finetooth/scripts/axes.py
skills/finetooth/scripts/review.py
```

`review.py` was read in three consecutive pages (offsets 1 / 1000 / 2000) covering all 2 961
lines; the other three are short enough for one read each. The hunter's coverage limits are
closed: the code it could only trace is now run — the parser matrix, the `MSG` arithmetic,
the `check` gates, `guard-grep.sh`, `run-role.sh` end to end with a stub `claude`, `axes.py`
on real streams, and git-pathspec edge cases.

What remains unchecked, named rather than implied:

- **Two warning-only gates** (`ref_paths` changed, 2559; open findings older than 7 days,
  2691) could not be measured by the mutation, which silences `problems` and not
  `warnings`. Whether a test detects their removal is unknown.
- **The `.ru.md` role templates were not opened.** T2 owns them, and the fix for T1-001 must
  cover `references/hunter.ru.md` as well; whether its skeleton carries the same substituted
  example lines is unverified here.
- **`claude -p` was never run for real.** T1-012 and T1-017 rest on a stub that reproduces
  the shapes (non-zero exit, a stream with no `result` event, a truncated final line); the
  real client's behaviour at the `--max-turns` cap — in particular whether it writes a
  `result` event with `subtype: error_max_turns` — was not observed, and that is exactly the
  event a fix would key on.
- **Performance was not measured**, per the invariants.
- **Mutation proves a test detects a gate's removal, not that the test is good.** Rows
  marked "covered" in table 1 mean the suite goes red when the message is silenced; they do
  not mean the gate's boundary conditions are covered.

## One measured consequence for the lead session

Not a finding about the code — a live instance of T1-001/T1-002/T1-003 inside this very
review, and it will fail the state check the moment T1 leaves `running`.

`verdict_conflicts(T1-tool.hunter.md)` returns **six** conflicted hypotheses: its Table 3
quotes tagged ids next to verdict words (`… — checked`, `` `n/a` ``, "not applicable"), and
the parser reads those samples as verdicts on the block's own questions. One of them
collects three different verdicts from three sample rows. `check` will therefore print
"gives hypothesis … different verdicts … leave one" six times over an honest report, which
is the gate fighting the author rather than catching silence.

`verdict_conflicts` on this report returns none, and it gives exactly one verdict to each of
the fifteen hypotheses — but only because its tables use `Z9` instead of the real block id.
That is a workaround, not a fix: the hunter had no way to write a parser matrix about this
block without tripping the parser it was documenting.
