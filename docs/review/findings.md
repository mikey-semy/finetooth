# Review findings

> This file is GENERATED from `findings.jsonl` by `python3 skills/finetooth/scripts/review.py findings`.
> Do not edit by hand — edit the jsonl and regenerate.

Open: **14** of 140 records.

## high (0 open / 5)

| id | block | status | location | what is wrong |
|---|---|---|---|---|
| T1-001 | T1 | fixed | `skills/finetooth/scripts/review.py:2137` | verdict_mentions tracks neither fences nor code spans, so hypothesis verdicts quoted from the role template's own skeleton close the hypotheses and check goes green with the questions unanswered |
| T1-041 | T1 | fixed | `skills/finetooth/scripts/review.py:1480` | [R4-001, fix review round 4] the new fence rule lets an indented inner fence close the outer one, and a quoted verdict becomes an answer again |
| T1-046 | T1 | fixed | `skills/finetooth/scripts/review.py:1529` | [R5-001, round 5] "an unclosed fence is text" hands the template's own skeleton back as the report's answers, and `check` goes green |
| T1-059 | T1 | fixed | `skills/finetooth/scripts/review.py:2674` | [R7-001, round 7] a finding write-up that opens a line with a hypothesis id is counted as a second verdict, and `check` goes red on an honest report |
| T1-060 | T1 | fixed | `skills/finetooth/scripts/review.py:2721` | [R7-002, round 7] the verifier's override is dropped when its basis is on the next line, and `check` reports the hunter's "checked" on a hypothesis the verifier called unproven |

## medium (3 open / 45)

| id | block | status | location | what is wrong |
|---|---|---|---|---|
| T1-002 | T1 | fixed | `skills/finetooth/scripts/review.py:2151` | A table whose first row is data rather than a header is taken for a table of hypothesis verdicts: every numbered row carrying a vocabulary word becomes a verdict on the hypothesis of that number |
| T1-003 | T1 | fixed | `skills/finetooth/scripts/review.py:2037` | A vocabulary word inside a code span decides the verdict: the lookaround around n/a guards \w and / but not backticks, brackets, quotes or parentheses, and the earliest word in the line wins |
| T1-004 | T1 | fixed | `skills/finetooth/scripts/review.py:2051` | A ~~~ fence is not recognised by section_body, section_items_full or demote: a column-0 # line inside one truncates the manifest's Hypotheses section and the hypotheses below it vanish |
| T1-005 | T1 | fixed | `skills/finetooth/scripts/review.py:340` | file_sha and block_lines read the working tree, not the index: for a file present in the index but not on disk the fingerprint degrades to the file's name and its lines drop out of the readability count |
| T1-006 | T1 | fixed | `skills/finetooth/scripts/review.py:2363` | The fix-commit gate compares a raw path with `git show --name-only` output, which quotes non-ASCII paths, so a finding on a Cyrillic-named file can never be marked fixed |
| T1-007 | T1 | fixed | `skills/finetooth/scripts/review.py:2224` | Twenty-four checks in cmd_check have no test: each was silenced in a copy of the kit and the suite stayed green, while silencing a covered gate turns it red |
| T1-008 | T1 | fixed | `skills/finetooth/assets/guard-grep.sh:69` | guard-grep.sh silently skips a scan path that does not exist and exits 0, so a gate goes green when a package is renamed — the opposite of what its own header promises |
| T1-009 | T1 | fixed | `skills/finetooth/scripts/review.py:1465` | import assigns ids by position to rows without one: a finding inserted above the numbered rows takes an id that already exists, and both records keep it with no way back through the tool |
| T1-010 | T1 | fixed | `skills/finetooth/scripts/review.py:568` | A block definition written by hand is never validated: a missing slug, phase, role or goal gives a KeyError traceback instead of a refusal naming the fix |
| T1-012 | T1 | fixed | `skills/finetooth/assets/run-role.sh:40` | run-role.sh writes the spend line to the journal whatever the run's exit code, so a run cut off by --max-turns is recorded as an ordinary completed run |
| T1-019 | T1 | fixed | `skills/finetooth/scripts/review.py:2013` | The verifier's coverage-verdict gate matches the bare word 'complete' anywhere in the report, so 'I completed the check' satisfies a gate meant to demand a statement about what was left unreviewed |
| T1-022 | T1 | fixed | `skills/finetooth/assets/guard-grep.sh:95` | One marker exempts every hit in the window below it, not just the call it was written above — the exact failure guard-grep.sh was written to replace grep -B with |
| T1-025 | T1 | fixed | `tests/test_review.py:3477` | [R1-001, fix review round 1] The new guard for "a gate that cannot go red" does not see a gate whose message is not a literal |
| T1-032 | T1 | fixed | `skills/finetooth/scripts/review.py:1430` | [R2-001, fix review round 2] A verdict inside a fence nested in a list item still closes a hypothesis |
| T1-033 | T1 | fixed | `skills/finetooth/scripts/review.py:2434` | [R2-002, fix review round 2] The gates that read a report's substance still count quoted text |
| T1-037 | T1 | fixed | `skills/finetooth/scripts/review.py:1487` | [R3-001, fix review round 3] the nested-fence fix silently truncates a manifest again, and `check` goes green on it |
| T1-042 | T1 | fixed | `skills/finetooth/scripts/review.py:1476` | [R4-002, fix review round 4] an unclosed fence inside a list item swallows the rest of the manifest, and `check` goes green on one hypothesis of four |
| T1-047 | T1 | fixed | `CHANGELOG.md:14` | [R5-002, round 5] the changelog entry restates the review's totals and gets them wrong, in both languages |
| T1-048 | T1 | deferred | `skills/finetooth/scripts/review.py:2481` | [R5-003, round 5] the block's own acceptance criterion cannot be written without making `check` red, and this round closed the gate by re-marking the report instead of filing it |
| T1-052 | T1 | fixed | `skills/finetooth/scripts/review.py:2648` | [R6-001, round 6] the exception for the old answer form strips every backtick in the line, and a quoted verdict word becomes the line's verdict again |
| T1-053 | T1 | fixed | `skills/finetooth/scripts/review.py:2638` | [R6-002, round 6] the hypotheses-section filter silently drops the verifier's overriding verdict, and the tool prints the hunter's word instead |
| T1-054 | T1 | fixed | `skills/finetooth/references/hunter.md:89` | [R6-003, round 6] `check` refuses a report that writes its verdicts the way the hunter template still promises, and the template now contradicts itself in both languages |
| T1-055 | T1 | fixed | `skills/finetooth/scripts/review.py:3202` | [R6-004, round 6] the coverage-limits gate still reads a quoted section as the report's own words — the round's principle does not reach it |
| T1-061 | T1 | fixed | `skills/finetooth/scripts/review.py:2700` | [R7-003, round 7] the hunter template's own indented-proof form yields no verdict at all, and the refusal names a requirement the report already meets |
| T1-062 | T1 | fixed | `skills/finetooth/scripts/review.py:2713` | [R7-004, round 7] the partial qualifier is searched over the whole clause whenever there is no colon, so an honest "checked" is recorded as "not checked" |
| T1-063 | T1 | fixed | `skills/finetooth/scripts/review.py:2662` | [R7-005, round 7] the round's central rule — no basis, no verdict — does not reach the table or the free form, so it is bypassed by writing the same answer as a table |
| T1-064 | T1 | deferred | `skills/finetooth/scripts/review.py:3195` | [R7-006, round 7] the file-map gate reads the report raw, so the block's file list can be satisfied entirely out of a quotation |
| T1-065 | T1 | fixed | `skills/finetooth/scripts/review.py:3229` | [R7-007, round 7] the R6-004 fix is untested: reverting the gate's `"quoted"` mode leaves the whole suite green |
| T2-001 | T2 | fixed | `skills/finetooth/references/verify.md:123` | The verifier template tells the agent to put a rejection reason in `claim`, but check accepts it only when the claim starts with a rejection word or a reject_reason field is present — neither is mentioned |
| T2-002 | T2 | fixed | `skills/finetooth/references/hunter.md:155` | The draft-findings JSON schema in every role template omits `root` and `dup_of`, so the three-instance guard gate and the duplicate gate can never be satisfied by an agent following the template |
| T2-016 | T2 | open | `tests/test_review.py:6062` | TemplateContractTest only checks that each agent field name occurs anywhere in a template, so prose satisfies it and the draft schemas it was written for are unguarded (fix review round 1, R1-001) |
| T2-017 | T2 | open | `skills/finetooth/scripts/review.py:1906` | {{DIFF}} is replaced over the assembled body, so the manifest's own mentions of it get the diff too: the prompt carries it three times while {{DIFF_VOLUME}} states one (fix review round 1, R1-002) |
| T3-001 | T3 | fixed | `tests/test_review.py:3951` | Five cmd_check gates moved from problems to warnings leave all 248 tests green: check exits 0 on the state it refused, because GATES keys a gate by its message and those gate tests never assert the exit code |
| T3-002 | T3 | fixed | `tests/test_review.py:3925` | _check_gates matches only `problems.append(x)` on a Name, so a gate written with `+=` or `extend` yields no key, needs no GATES entry and no test, and the registry stays green |
| T3-003 | T3 | fixed | `tests/test_review.py:4034` | GateRegistryTest checks only that the test named beside a gate exists; nothing ties the two, so a gate registered against any existing test name satisfies the guard with zero coverage |
| T3-004 | T3 | fixed | `tests/test_review.py:611` | backfill runs once in the whole suite and set-finding over several ids only on the happy path, so neither backfill's idempotence nor set-finding's all-or-nothing is held by a test |
| T4-001 | T4 | fixed | `skills/finetooth/SKILL.md:4` | The skill's frontmatter still says the base was handed over without a license, which LICENSE and NOTICE.md retired on 24.09.2026 |
| T4-003 | T4 | fixed | `SECURITY.md:3` | The stated security boundary ('writes to docs/review/', 'sends nothing over the network') is false for `summary` and for assets/run-role.sh |
| T4-016 | T4 | fixed | `skills/finetooth/scripts/review.py:564` | `init` answers a Python traceback on a blocks.json without the top-level review_id, and the guard test that forbids exactly that stays green |
| T4-019 | T4 | fixed | `.github/dco.sh:25` | dco.sh interpolates the author's email unescaped into a grep -E pattern, so a signed commit from an address with + is refused and a sign-off with a different address can match via . (fix review round 1, R1-001) |
| T4-020 | T4 | fixed | `docs/review/findings.jsonl:107` | The register's rule for T4-009, T4-010, T4-017 (and T4-004) names a guard covering one instance of the class, so the class is recorded closed yet reopens with the guard green (fix review round 1, R1-002) |
| T4-021 | T4 | fixed | `tests/test_review.py:5233` | test_каждые_объявленные_ворота_гоняет_ci matches each CONTRIBUTING command by two anchors anywhere in the workflow text, so CI can stop running the unittest suite with the guard green (fix review round 1, R1-003) |
| T4-026 | T4 | fixed | `.github/dco.sh:31` | dco.sh feeds git rev-list through process substitution, so an unresolvable range examines no commits and the script prints 'all commits are signed off' with exit 0 (fix review round 1, R1-008) |
| T4-027 | T4 | deferred | `docs/review/findings.jsonl:7` | The round rewrote the rule field of 16 earlier findings; 10 now name a guard green on the finding's own defect, 3 replacing a correct value (fix review round 2, R2-001) |
| T4-028 | T4 | open | `tests/test_review.py:3309` | BODY_ARGV gives set-finding an id absent from the stand, so it refuses before writing and the write-boundary sweep never reaches its register write (fix review round 2, R2-002) |

## low (11 open / 90)

| id | block | status | location | what is wrong |
|---|---|---|---|---|
| T1-011 | T1 | fixed | `skills/finetooth/scripts/review.py:666` | stale_tree returns None without refs/remotes/origin/HEAD and says nothing, so the freshness gate is silently inert for a checkout with no remote or with a remote not named origin |
| T1-013 | T1 | fixed | `skills/finetooth/scripts/review.py:814` | commit_file_sets parses `git log --name-only`, which prints only the new path of a rename and quotes non-ASCII paths: coupling and order undercount churn and drop files silently |
| T1-014 | T1 | fixed | `skills/finetooth/scripts/review.py:2596` | The named-files gate is a plain substring test, so a longer path that contains an owned path satisfies the gate for both: a report naming src/api.ts.snap marks src/api.ts as named |
| T1-015 | T1 | fixed | `skills/finetooth/scripts/review.py:831` | On a history of 20 commits or fewer mass_cutoff equals the largest commit, so no mass commit is ever skipped and the initial whole-tree commit pairs every file with every other |
| T1-016 | T1 | fixed | `skills/finetooth/scripts/review.py:1115` | summary --aged slices its machine block with text.index(' -->') and json.loads: a block title or path containing ' -->' gives a traceback instead of the drift table |
| T1-017 | T1 | fixed | `skills/finetooth/scripts/axes.py:63` | Without a result event axes.py reports turns None, cost $0.00 and an output count its own comment calls a stream artefact, in the format of a real measurement; a truncated last line raises |
| T1-018 | T1 | fixed | `skills/finetooth/scripts/review.py:480` | init rewrites updated_at on every run, so a no-op re-run always dirties state.json |
| T1-020 | T1 | fixed | `skills/finetooth/scripts/review.py:1169` | Four thresholds carry no measurement or reference: REF_LIST_LIMIT=80, the 200-character 'manifest nearly empty' bound, CLAIM_MAX=220 / SCENARIO_MAX=700 and COUPLING_HUB_BLOCKS=6 |
| T1-021 | T1 | fixed | `skills/finetooth/scripts/review.py:1342` | prompt substitutes into the pasted manifest text and blames the role template for a leftover placeholder that in fact came from the manifest |
| T1-023 | T1 | fixed | `skills/finetooth/scripts/review.py:300` | listed() runs git ls-files with check=True, so a pathspec in blocks.json that git rejects makes check and coverage die with a CalledProcessError traceback instead of naming the bad pattern |
| T1-024 | T1 | fixed | `skills/finetooth/scripts/review.py:2412` | The cited-line gate is guarded by isinstance(line, int), so a finding whose line is written as a string skips the check entirely while findings.md still renders it as a real location |
| T1-026 | T1 | fixed | `skills/finetooth/scripts/review.py:1393` | [R1-002, fix review round 1] `summary --aged` now counts one file under two names — the opposite of what the change claims |
| T1-027 | T1 | fixed | `skills/finetooth/scripts/review.py:2599` | [R1-003, fix review round 1] The named-files gate now refuses a report that writes `./src/api.ts` |
| T1-028 | T1 | fixed | `skills/finetooth/scripts/review.py:2496` | [R1-004, fix review round 1] A quoted verdict still closes a hypothesis when it is quoted by indentation or by `>` |
| T1-029 | T1 | fixed | `skills/finetooth/scripts/axes.py:65` | [R1-005, fix review round 1] `axes.py` changed which `result` event it measures, and this is in no report and under no test |
| T1-030 | T1 | fixed | `CHANGELOG.md:41` | [R1-006, fix review round 1] The changelog's Breaking section holds five fixes that are not breaking, and not the change that is |
| T1-031 | T1 | fixed | `skills/finetooth/references/fix.md:59` | [R1-007, fix review round 1] Two new rules in the fix role template, recorded nowhere |
| T1-034 | T1 | fixed | `tests/test_review.py:3826` | [R2-003, fix review round 2] The new quotation guard cannot see a parser that does not exist yet |
| T1-035 | T1 | fixed | `skills/finetooth/scripts/review.py:2692` | [R2-004, fix review round 2] `a/` and `b/` are accepted as prefixes, so a real `a/` directory closes the gate for a file nobody read |
| T1-036 | T1 | fixed | `skills/finetooth/assets/run-role.sh:58` | [R2-005, fix review round 2] `run-role.sh` dies on the truncated stream `axes.py` was taught to survive |
| T1-038 | T1 | deferred | `skills/finetooth/scripts/review.py:2727` | [R3-002, fix review round 3] the other address of T1-035: a diff header closes the gate for a real `a/…` file nobody read |
| T1-039 | T1 | rejected | `tests/test_review.py:4050` | [R3-003, fix review round 3] the rewritten quotation guard does not see the two gates it is recorded against |
| T1-040 | T1 | fixed | `skills/finetooth/assets/run-role.sh:47` | [R3-004, fix review round 3] the EXIT trap turns a lost journal line into a successful run |
| T1-043 | T1 | fixed | `docs/review/journal.md:16` | [R4-003, fix review round 4] the round left no fix report and no journal entry, so its incidental changes are recorded nowhere |
| T1-044 | T1 | fixed | `docs/review/findings.jsonl:37` | [R4-004, fix review round 4] the round left `check` red on a register row it wrote itself |
| T1-045 | T1 | fixed | `CHANGELOG.md:14` | [R4-005, fix review round 4] the new changelog bullet swallows the section's introduction, in both languages |
| T1-049 | T1 | fixed | `tests/test_review.py:4222` | [R5-004, round 5] the new guard does not run when the test file is run directly |
| T1-050 | T1 | fixed | `skills/finetooth/scripts/review.py:129` | [R5-005, round 5] `import` accepts a row that `check` immediately refuses, and the defect is in no register row |
| T1-051 | T1 | fixed | `docs/review/findings.jsonl:43` | [R5-006, round 5] three findings are recorded as fixed in a file that has nothing to do with them |
| T1-056 | T1 | fixed | `docs/review/findings.jsonl:47` | [R6-005, round 6] the three register rows this round wrote carry a `fixed_in` naming a file that holds none of their fixes — including the row that records this defect |
| T1-057 | T1 | fixed | `docs/review/findings.jsonl:38` | [R6-006, round 6] the round left `check` red on its own bookkeeping |
| T1-058 | T1 | fixed | `skills/finetooth/scripts/review.py:1451` | [R6-007, round 6] a second code-span parser lives outside the one quotation tracker, and the class guard cannot see span parsers |
| T1-066 | T1 | deferred | `tests/test_review.py:4074` | [R7-008, round 7] T1-058 is recorded `fixed` while the half of it about the class guard is untouched — a third span parser is still invisible |
| T1-067 | T1 | fixed | `CHANGELOG.md:19` | [R7-009, round 7] the changelog and the fix report say the new table holds 29 lines; it holds 28 |
| T1-068 | T1 | fixed | `skills/finetooth/scripts/review.py:3231` | [R7-010, round 7] a coverage-limits section swallowed by an unclosed fence is reported as a missing section, and the message does not name the cause |
| T2-003 | T2 | fixed | `skills/finetooth/SKILL.md:92` | SKILL.md documents `--round` only for the fix reviewer, so a second fix round overwrites round 1's fix report and the round-2 fixreview prompt points at a file nobody was told to write |
| T2-004 | T2 | fixed | `examples/toy/src/billing/quota.ts:1` | The shipped toy example names a register finding id in a code comment — the practice fix.md rule 5 and the entry point forbid — and the id it cites is the wrong finding |
| T2-005 | T2 | fixed | `examples/toy/docs/review/blocks.json:12` | examples/toy does not pass `check`: its own README.md is owned by no block and covered by no exclusion, contradicting the example's instruction that check passes on it |
| T2-006 | T2 | fixed | `skills/finetooth/assets/blocks.example.json:115` | The sample block definition violates the phase-order gate: the array runs phase 1, phase 2, phase 1, phase 3, and check refuses a phase that decreases along the array |
| T2-007 | T2 | fixed | `skills/finetooth/assets/agent-banner.ru.md:11` | The Russian banner asset carries the English banner verbatim: only the surrounding explanation is Russian, the text meant to be pasted is not translated |
| T2-008 | T2 | fixed | `skills/finetooth/scripts/review.py:3509` | `setup --lang ru` names the English samples in its checklist, and the Russian copies of invariants.example, manifest.example, journal.example and agent-banner are referenced by nothing in the kit |
| T2-009 | T2 | fixed | `skills/finetooth/assets/entry-point.md:46` | The entry point that setup copies into every project as docs/review/README.md is behind the tool: no fixreview role or report name, no fix gate, no import --append, and its prompts/ list omits fixreview.md |
| T2-010 | T2 | fixed | `skills/finetooth/references/fixreview.md:71` | The fix reviewer is handed a diff of any size with no statement of that size and no mention of --scope, while the hunter's prompt carries a measured reading budget |
| T2-011 | T2 | fixed | `skills/finetooth/references/lessons.md:58` | Lesson 13 requires every deferred finding to be fixed or rejected before the review ends, while the tool and SKILL.md treat a deferred finding with a reason as an accepted risk that ships in the summary |
| T2-012 | T2 | fixed | `skills/finetooth/assets/makefile-snippet.mk:17` | The Makefile snippet defines no generic `review` target, while SKILL.md offers `make review` as an example value for the cli field that every hint is built from |
| T2-013 | T2 | fixed | `examples/toy/docs/review/findings.md:3` | The toy's findings.md header holds the literal `<skill>` path while its blocks.json sets no `cli`, so the file can never equal the regenerated one and check is red in every copy of the example |
| T2-014 | T2 | fixed | `skills/finetooth/SKILL.md:126` | `roots`, the class view the three-instance guard gate rests on, is named by no message of the tool, by no line of SKILL.md and by no line of the entry point, so a lead cannot learn it exists |
| T2-015 | T2 | fixed | `skills/finetooth/assets/agent-banner.md:13` | Both banner assets hardcode `make review-status` with no {{CLI}} placeholder, and setup substitutes nothing in them, so a project without a Makefile pastes a dead command into every session |
| T2-018 | T2 | open | `skills/finetooth/scripts/review.py:197` | The diff_vol message tells a reviewer who cannot hold the diff to take one half through --scope, but --scope does not shrink the diff it is handed (fix review round 1, R1-003) |
| T2-019 | T2 | open | `tests/test_review.py:6533` | Three new negative tests (deferral without reason, reason only in claim, root from the sample) assert the gate's message in check's stdout, never its exit code (fix review round 1, R1-004) |
| T2-020 | T2 | duplicate | `CHANGELOG.md:77` | The T2 section's opening paragraph follows the last T4 bullet with no blank line in both CHANGELOGs, so it renders as part of the NOTICE.md bullet (fix review round 1, R1-005) |
| T2-021 | T2 | open | `skills/finetooth/scripts/review.py:3086` | Two of the four places T2-011 fixed — the deferral refusal's tail in check and SKILL.md's completion sentence — are held by no test, and the register records no rule for T2-011 (fix review round 1, R1-006) |
| T2-022 | T2 | open | `skills/finetooth/references/verify.md:92` | The verifier's template gets the same whole-block 'read all' file list as the hunter but no {{VOLUME}} reading budget (fix review round 1, R1-007) |
| T3-005 | T3 | fixed | `tests/test_review.py:3059` | The no-traceback class guard passes one fixed argv to every subcommand; argparse rejects it for 20 of the 23, so their bodies never run and the guard proves nothing about them |
| T3-006 | T3 | fixed | `tests/test_review.py:2250` | Nothing compares the key sets of MSG['en'] and MSG['ru'], so deleting a translation leaves the suite green while T() raises KeyError at run time on the path that needs it |
| T3-007 | T3 | fixed | `tests/test_review.py:3600` | Mechanisms outside cmd_check that no test reaches: import's claim cap, block_risk's refusal, review_lang's fallback and cmd_next — each removable with the whole suite green |
| T3-008 | T3 | fixed | `tests/test_review.py:1533` | The space-path test asserts only that check does NOT print 'does not touch' and never checks its fixture reached that state, so silencing the gate for paths with a space leaves the suite green |
| T3-009 | T3 | fixed | `tests/test_review.py:65` | Only Stand.run pins a UTF-8 locale; _run_role and the bare python3 calls inherit it, so the suite's verdict rests on CPython auto-enabling UTF-8 mode in the C locale |
| T3-010 | T3 | fixed | `tests/test_review.py:47` | The Stand repositories set only user.name and user.email locally, so the developer's global git config — ignore file, commit.gpgsign — decides whether the suite passes |
| T3-011 | T3 | fixed | `tests/test_review.py:3508` | The claude stub emits no result event, so all six run-role.sh tests exercise the NO RESULT EVENT branch and the test named 'a successful run is written as an ordinary line' accepts that as one |
| T3-012 | T3 | fixed | `tests/test_review.py:4093` | The NUL-path class guard inspects only list literals holding both 'git' and a name-asking flag, so splitting the repeated git prefix out of the literal blinds it and -z can be dropped unnoticed |
| T3-013 | T3 | fixed | `tests/test_review.py:2801` | No fixture path contains a bracket, so the :(literal) prefix in file_sha — there because git-pathspec reads [handle] as a character class — can be deleted with the suite green |
| T3-014 | T3 | fixed | `tests/test_review.py:4253` | The threshold guard walks only module-level `NAME = <number>`, so a bare threshold written as a BinOp or as a tuple assignment carries no source and the suite stays green |
| T3-015 | T3 | fixed | `tests/test_review.py:66` | The suite spawns the tool as PATH `python3` in seven places while using sys.executable in five, so running it under another interpreter does not test that interpreter |
| T4-002 | T4 | fixed | `CHANGELOG.md:40` | NOTICE.md's unqualified promise that road-tested projects are not named is contradicted by CHANGELOG.md:40, which names the owner's own project and one of its paths |
| T4-004 | T4 | fixed | `README.md:281` | README (en, ru) and AGENTS.md give the suite as 98 scenarios taking about a minute; measured, it is 248 tests in 201 seconds |
| T4-005 | T4 | fixed | `README.md:457` | README (en, ru) states the coupling shared-node threshold as a fixed six blocks and the mass cutoff as the 95th percentile; the code derives both |
| T4-006 | T4 | fixed | `CHANGELOG.md:68` | The Unreleased section contradicts itself: Added says a shared node is a file coupled with >= 6 blocks, Fixed says the threshold became a share with a floor of three |
| T4-007 | T4 | fixed | `.github/ISSUE_TEMPLATE/proposal.yml:16` | The proposal template sends contributors to docs/prior-art.md and asks for a ROADMAP direction number; both were moved to a private repository |
| T4-008 | T4 | fixed | `CHANGELOG.md:594` | Versions 0.5.1, 0.5.0 and 0.4.1 have no compare link in either CHANGELOG, though RELEASING gate 4 requires one before the tag |
| T4-009 | T4 | fixed | `RELEASING.md:23` | RELEASING calls its gates 'all mechanical' when three of the four are human steps that nothing checks |
| T4-010 | T4 | fixed | `CONTRIBUTING.md:75` | The DCO sign-off is mandatory and nothing verifies it: no workflow checks commits, only a self-reported PR checkbox |
| T4-011 | T4 | fixed | `README.ru.md:16` | README.ru.md has no counterpart to README.md:28-52 — the six claims that separate the kit from PR-review bots, and the Language paragraph |
| T4-012 | T4 | fixed | `README.md:421` | The README's 'What is inside' inventory is incomplete in both languages: 19 of 23 commands, no axes.py or run-role.sh, and none of the ten .ru.md templates |
| T4-013 | T4 | fixed | `RELEASING.md:50` | The release procedure names two paths that do not exist: `scripts/review.py` and a root `SKILL.md` |
| T4-014 | T4 | fixed | `.github/workflows/tests.yml:15` | actions/checkout is taken by the mutable tag v5 while every other action and install in the same two workflows is pinned by commit |
| T4-015 | T4 | fixed | `.github/workflows/tests.yml:16` | The CI workflow's step names and comments are in Russian, against AGENTS.md rule 7 and the 0.7.0 English-primary release |
| T4-017 | T4 | fixed | `skills/finetooth/SKILL.md:5` | SKILL.md states the tool is tested on Python 3.12 and 3.14, while the CI workflow pins no Python version and runs the suite on one |
| T4-018 | T4 | fixed | `CODE_OF_CONDUCT.md:1` | Neither code of conduct links to its other-language copy, against the 0.7.0 claim that the Russian copies are cross-linked at the top of each file |
| T4-022 | T4 | fixed | `CHANGELOG.md:76` | The T2 section's opening paragraph is swallowed into the preceding T4 NOTICE.md bullet in both CHANGELOGs for lack of a blank line (fix review round 1, R1-004) |
| T4-023 | T4 | fixed | `tests/test_review.py:3323` | WriteBoundaryTest calls each subcommand with () and ('H1',), so set-status, set-finding and log never get past argparse and are outside the write-boundary guard (fix review round 1, R1-005) |
| T4-024 | T4 | fixed | `README.md:281` | All five places stating the scenario count said 270 while the merged suite ran 296, and the guard was loosened to a nine-tenths band in the same range (fix review round 1, R1-006) |
| T4-025 | T4 | fixed | `docs/review/reports/T4-repo-contract.fix.md:16` | The T4 fix report names the guard test_число_сценариев_в_документах_равно_настоящему, which does not exist on HEAD after 2f29968 renamed it, and quotes 270 tests against the range's 296 (fix review round 1, R1-007) |
| T4-029 | T4 | open | `tests/test_review.py:5496` | _runs_command counts a wider step as running the gate, so '\|\| true', '-k' narrowing or a one-commit dco range neutralise the CI gate with the guard green (fix review round 2, R2-003) |
| T4-030 | T4 | open | `tests/test_review.py:5545` | _glued_to_list_item recognises only '-*+' bullets as list openers, missing numbered items and a one-space-indented continuation (fix review round 2, R2-004) |
| T4-031 | T4 | open | `CHANGELOG.md:102` | CHANGELOG (both languages) says the T4 fix review had six findings, all closed; the register closes eight (T4-019…T4-026), and T4-020/T4-025 appear in no entry (fix review round 2, R2-005) |
| T4-032 | T4 | open | `docs/review/reports/T4-repo-contract.fix-2.md:445` | The round-2 fix report claims twenty-three new tests; the suite goes from 325 at d33527c to 341 at HEAD, sixteen (fix review round 2, R2-006) |
| T4-033 | T4 | open | `docs/review/findings.jsonl:121` | T2-020 is the same glued-paragraph defect this round fixed as T4-022, yet stays open and review check is red on it (fix review round 2, R2-007) |
| T4-034 | T4 | open | `tests/test_review.py:5102` | ShellGateMutationTest.GATES is a hand-written two-script dict, not read from git ls-files; a new shell gate falls outside the rule with nothing failing (fix review round 2, R2-008) |
| T4-035 | T4 | open | `tests/test_review.py:5268` | _sweeps_without_body_check is satisfied by the text argparse_refused anywhere in the function and sees a sweep only when .run's first argument is a bare Name (fix review round 2, R2-009) |

