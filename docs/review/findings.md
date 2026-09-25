# Review findings

> This file is GENERATED from `findings.jsonl` by `python3 skills/finetooth/scripts/review.py findings`.
> Do not edit by hand — edit the jsonl and regenerate.

Open: **0** of 68 records.

## high (0 open / 5)

| id | block | status | location | what is wrong |
|---|---|---|---|---|
| T1-001 | T1 | fixed | `skills/finetooth/scripts/review.py:2137` | verdict_mentions tracks neither fences nor code spans, so hypothesis verdicts quoted from the role template's own skeleton close the hypotheses and check goes green with the questions unanswered |
| T1-041 | T1 | fixed | `skills/finetooth/scripts/review.py:1480` | [R4-001, fix review round 4] the new fence rule lets an indented inner fence close the outer one, and a quoted verdict becomes an answer again |
| T1-046 | T1 | fixed | `skills/finetooth/scripts/review.py:1529` | [R5-001, round 5] "an unclosed fence is text" hands the template's own skeleton back as the report's answers, and `check` goes green |
| T1-059 | T1 | fixed | `skills/finetooth/scripts/review.py:2674` | [R7-001, round 7] a finding write-up that opens a line with a hypothesis id is counted as a second verdict, and `check` goes red on an honest report |
| T1-060 | T1 | fixed | `skills/finetooth/scripts/review.py:2721` | [R7-002, round 7] the verifier's override is dropped when its basis is on the next line, and `check` reports the hunter's "checked" on a hypothesis the verifier called unproven |

## medium (0 open / 28)

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

## low (0 open / 35)

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

