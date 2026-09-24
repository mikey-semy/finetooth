# Review findings

> This file is GENERATED from `findings.jsonl` by `python3 skills/finetooth/scripts/review.py findings`.
> Do not edit by hand — edit the jsonl and regenerate.

Open: **7** of 31 records.

## high (0 open / 1)

| id | block | status | location | what is wrong |
|---|---|---|---|---|
| T1-001 | T1 | fixed | `skills/finetooth/scripts/review.py:2137` | verdict_mentions tracks neither fences nor code spans, so hypothesis verdicts quoted from the role template's own skeleton close the hypotheses and check goes green with the questions unanswered |

## medium (1 open / 13)

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
| T1-025 | T1 | open | `tests/test_review.py:3477` | [R1-001, fix review round 1] The new guard for "a gate that cannot go red" does not see a gate whose message is not a literal |

## low (6 open / 17)

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
| T1-026 | T1 | open | `skills/finetooth/scripts/review.py:1393` | [R1-002, fix review round 1] `summary --aged` now counts one file under two names — the opposite of what the change claims |
| T1-027 | T1 | open | `skills/finetooth/scripts/review.py:2599` | [R1-003, fix review round 1] The named-files gate now refuses a report that writes `./src/api.ts` |
| T1-028 | T1 | open | `skills/finetooth/scripts/review.py:2496` | [R1-004, fix review round 1] A quoted verdict still closes a hypothesis when it is quoted by indentation or by `>` |
| T1-029 | T1 | open | `skills/finetooth/scripts/axes.py:65` | [R1-005, fix review round 1] `axes.py` changed which `result` event it measures, and this is in no report and under no test |
| T1-030 | T1 | open | `CHANGELOG.md:41` | [R1-006, fix review round 1] The changelog's Breaking section holds five fixes that are not breaking, and not the change that is |
| T1-031 | T1 | open | `skills/finetooth/references/fix.md:59` | [R1-007, fix review round 1] Two new rules in the fix role template, recorded nowhere |

