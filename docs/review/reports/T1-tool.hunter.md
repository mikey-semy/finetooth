# T1 — hunter report

## Coverage

- files read: 4 of 4 — each read in full, in one call per file (`review.py` in three
  consecutive pages because of the reader's 25k-token page cap, offsets 1/1099/2049).

Files read by name:

```
skills/finetooth/assets/guard-grep.sh
skills/finetooth/assets/run-role.sh
skills/finetooth/scripts/axes.py
skills/finetooth/scripts/review.py
```

Context files read (not my coverage, read to answer the hypotheses):

```
skills/finetooth/references/hunter.md
tests/test_review.py
docs/review/blocks.json
```

- not read: nothing from the block list.

## Hypotheses

- `T1.1 — checked: no defect.` `MSG["en"]` and `MSG["ru"]` (review.py:135–232) hold the
  same 56 keys in the same order, and every format placeholder matches on both sides
  (`sum_base` {date,sha,branch,closed,total,total_f,fixed,rejected,deferred,dups,open},
  `aged_row` {block,commits,files,title}, `vol_head` {n,lines,k}, `backfill_note`
  {head,blocks,n}, `md_open` {live,total}, `md_sev` {sev,open,total}, `refs_cut`/`vol_more`/
  `files_*` {n}, `scope_line` {scope}, `md_gen`/`sum_intro` {cli}, `sum_title` {project}).
  Every `T()` call site uses a key present in both; `cmd_setup` indexes `MSG[lang]` directly
  with `setup_note`, `excl_apparatus`, `excl_skill` — all present in both. Both
  `entry-point.md`/`entry-point.ru.md` and all four `references/<role>.md`/`.ru.md` exist,
  so the run-time `FileNotFoundError` paths in `cmd_prompt`/`cmd_setup` are not reachable
  today. Compared by reading, not by running a set difference (see Coverage limits).
- `T1.2 — checked: three live false positives remain.` `verdict_mentions` (review.py:2124)
  tracks neither fences nor code spans, so the role template's own example lines close
  hypotheses (T1-001); a numbered table **without** a header row is still read as a verdict
  table (T1-002, the 2151 fix only inspects the first row); ``n/a`` inside a code span is a
  verdict (T1-003). Matrix in table 3 below. `H1.1` inside `H1.10` is **not** a false
  positive: `\d+` is greedy, so the tagged regex matches `T1.10` whole.
- `T1.3 — checked: one hole.` ` ``` ` fences are tracked with `lstrip()`, so an indented
  ` ```json ` fence is handled and the case is tested
  (`test_блок_кода_в_гипотезах_не_обрывает_раздел`). `~~~` fences are not recognised at all
  in `section_body`, `section_items_full` or `demote` — a column-0 `#` line inside one
  truncates the Hypotheses section (T1-004). An indented (4-space) code block cannot produce
  a column-0 `#`, so that variant is safe.
- `T1.4 — checked: one fingerprint misses its subject.` `block_sha` hashes the path **and**
  the content of every file, so a file leaving the pattern changes the sha; `hypotheses_sha`
  covers the full item text including continuation lines (tested); `refs_sha` subtracts the
  block's own files and the exclusions. But all of them go through `file_sha`, which hashes
  the **working tree**: for a file that is in the index and not on disk (sparse checkout)
  it returns `None` and the fingerprint degrades to the file's name (T1-005). `code_sha` is
  a whole-file sha, so a finding with an empty `line` is fine and an out-of-range `line` is
  caught by its own gate.
- `T1.5 — checked: one silent drop, one false match.` Pathspecs go to git after `--`, so
  `[`/`*` keep git-pathspec semantics (read, not executed). Two blocks owning one file is
  handled (`owned.setdefault(...).append` + sort). Untracked files are reported with
  `git add` (tested). The `named_files` gate does **not** use pathspecs but a plain
  substring test, so a longer path containing an owned path satisfies it (T1-014). Non-ASCII
  paths are dropped wherever git's output is read without `-z` (T1-006, T1-013).
- `T1.6 — checked: a collision is reachable.` `--append` is safe (`max(taken)+1`, known ids
  skipped, re-run appends nothing — tested). The plain import assigns ids by **position**
  only to rows without one: a new unnumbered finding inserted **above** the numbered rows
  takes an id that already exists (T1-009). The existing test builds exactly that input
  (`test_идентификаторы_находок_не_разъезжаются`, rows2 = new + first) and asserts only on
  the two old rows.
- `T1.7 — checked: it is all-or-nothing.` `cmd_set_finding` mutates the in-memory rows and
  writes `findings.jsonl` **after** the loop; a `die()` on an unknown id (or a failed
  `--dup-of`/`--rule`/`--fixed-in` validation) exits before any write. The only blemish is
  cosmetic: the per-id `"<id>: <status>"` lines are printed before the failure. The rename
  case: `git show --name-only` prints the new path, so a fix commit that renames the
  finding's file reports "does not touch" — and the message names `--fixed-in`, which is the
  documented way out.
- `T1.8 — checked: no mid-check `die()`, but a traceback is reachable.` Inside `cmd_check`
  only `blocks()`/`state()`/`findings()` can `die()`, and each is a legitimate exit 2 before
  any gate has run; warnings never change the exit code; problems give exit 1. What does
  reach the user is a `KeyError` traceback on a hand-written block definition (T1-010).
- `T1.9 — checked: the gate silently never fires.` `stale_tree` returns `None` when
  `refs/remotes/origin/HEAD` is absent or the remote is not named `origin`, and says nothing
  (T1-011). Evidence that the ref is not automatic: the kit's own tests have to create it by
  hand (`self.s.git("symbolic-ref", "refs/remotes/origin/HEAD", ...)`, test_review.py:1609,
  1658). In this repository the ref exists (`origin/dev`), so the gate is live here.
- `T1.10 — checked, measured on this repository.` `git log --name-only` prints only the new
  path of a rename, so a file's churn splits across its names. `review.py` has **41**
  first-parent commits with `--follow` and **9** under its current path
  (`skills/review-kit/scripts/review.py` → `skills/finetooth/scripts/review.py` R099 in
  fbb3138, `review.py` → `skills/review-kit/scripts/review.py` R090 in 91e6ffb). `order`
  therefore ranks T1 on 9 commits out of 41 (T1-013).
- `T1.11 — checked: on a young history nothing is ever skipped.` `mass_cutoff` takes
  `sizes[min(len-1, (len*95)//100)]`; for any history of **20 commits or fewer** that index
  is the last element, i.e. the largest commit, and the guard is a strict `>` — so the
  initial commit (the whole tree) is counted as an ordinary change and pairs every owned
  file with every other (T1-015).
- `T1.12 — checked: a legal title breaks it.` `summary --aged` does
  `text.index(" -->", i)` and `json.loads` of the slice; a block title or path containing
  ` -->` truncates the JSON or removes the terminator — traceback, not a refusal (T1-016).
- `T1.13 — checked: the journal lies about a cut-off run.` `run-role.sh` captures `RC` and
  then writes the journal line unconditionally (lines 35–40); neither the line nor
  `axes.py` mentions the outcome (T1-012). A bad block id: `set -e` is still in force at
  line 29, so the shell exits after the redirect has already created a zero-byte prompt
  file in `$TMPDIR/finetooth-runs` — no journal entry, only the stray file.
- `T1.14 — checked by reading: a killed run reports as cheap.` Without a `result` event
  `turns` is `None`, `cost_usd` is 0 and `output` falls back to the sum of per-message
  counts that the code's own comment calls "a stream artefact" — all printed in the same
  format as a real measurement (T1-017). A truncated last line (a killed writer) makes
  `json.loads` raise, and under `set -e` that costs the journal line and the exit code.
- `T1.15 — checked: `init` is idempotent in substance, not on disk.` Statuses, `started`,
  `finished`, `reports` and all three fingerprints survive (`setdefault`), blocks deleted
  from the definition are pruned, `--force` resets. But `updated_at` is rewritten on every
  run, so a no-op `init` always dirties `state.json` (T1-018). `setup` on a live
  `docs/review/` touches nothing and says so (tested).

## Tree freshness

`git log HEAD..origin/dev --oneline` is empty — HEAD (`c5fd231`) contains everything on
`origin/dev`. The only modification in the working tree is `docs/review/state.json`
(T1 moved to `running` by the lead session). Every finding below was read on this tree.

## Coverage limits

- **No code was executed.** This role's tool allowlist has no `python3`, `bash` or `awk`
  (`run-role.sh:19`), so the parser matrix, the `MSG` comparison and every claim about
  `check` are hand-traced from the source, not run. What *was* executed is git: the
  quoting experiment (a scratch repository with `модуль.py` and `plain file.py`), the
  rename measurement on this repository's own history, and `origin/HEAD`. Two consequences:
  acceptance table 3 gives the verdict I derive from `line_verdict`'s rule (earliest
  vocabulary word wins, ties by alphabetical verdict), not an observed one; and the
  `MSG` key sets were compared by eye over the two literal tables rather than by set
  arithmetic.
- **Mutations were not run.** Table 1 names, for every gate, the test that covers it and
  the mutation that should turn that test red — I did not apply any mutation and did not
  run the suite. Proving the tests is T3's subject; what I claim here is only which gates
  have a test at all, and that is read off the full text of `tests/test_review.py`.
- **`skills/finetooth/references/*.ru.md` were not read** (T2 owns them). T1-001 is filed
  on the English template only; whether the Russian one has the same example lines is
  unverified, and the fix must cover both.
- **`run-role.sh` was never exercised end to end** — no `claude -p` run, no real
  stream-json file. T1-012 and T1-017 are read from the code and from the shapes the
  existing `axes.py` test builds.
- **git-pathspec edge cases** (`[`, `:(exclude)`, a leading `./`) were not executed; I read
  that the specs are passed after `--` and trusted git's documented semantics.
- **`skills/finetooth/assets/guard-grep.sh` was not run**, and neither was any Makefile
  gate built on it; T1-008 is read from the script.
- I did not attempt to measure performance of anything, per the invariants.

## Findings

### T1-001 · high · Hypothesis verdicts are counted inside fenced blocks, so the role template's own example closes three hypotheses
**Location:** `skills/finetooth/scripts/review.py:2137`
**What is wrong:** `verdict_mentions` walks the report line by line with no fence and no
code-span tracking (unlike `section_body`, which does track ` ``` `). The hunter template's
"Report structure" block is a ```` ```markdown ```` fence containing, with the block id
already substituted, the lines ``- `T1.1 — checked: <what exactly proves it>` ``,
``- `T1.2 — not checked: …` ``, ``- `T1.3 — not applicable: …` `` (references/hunter.md:85–87).
**Failure scenario:** a hunter pastes the report skeleton it was given into
`T1-tool.hunter.md` and answers hypotheses 4…15 for real. `verdicts_for` reads the three
template lines as verdicts on T1.1, T1.2 and T1.3; `check`'s hypotheses gate finds
`missing == []` and passes, `hypotheses T1` prints "closed 15/15". Three questions were
never answered and no gate is red. (When the pasted example contradicts a real verdict, the
conflict gate fires with a confusing message instead; when it does not, the gate is green.)
**Why it is a defect:** invariant 1 — a report that satisfies the regex without the content
is the most serious class here; invariant 4 — a word inside a code span or a fenced block is
not a verdict. The class is known: `LIMITS_PLACEHOLDER` exists because an agent copied this
very template into the coverage-limits section.
**Confidence:** confirmed
**Root:** report parser matches shape, not meaning

### T1-002 · medium · A numbered table without a header row is read as a table of hypothesis verdicts
**Location:** `skills/finetooth/scripts/review.py:2151`
**What is wrong:** `table_about_hypotheses` is decided from the table's **first** row:
either it names hypotheses, or its first cell is a digit. A table that starts straight with
data (`| 1 | … |`) therefore declares itself to be about hypotheses — the 2149 comment fixed
only the variant that has a `| # | … |` header.
**Failure scenario:** the T1 acceptance criterion asks for a "gate → test → mutation" table.
Written header-less — `| 1 | state vs definition | none | — |`, `| 2 | status vocabulary |
test_… | drop the check |` … — every row whose text contains `confirmed`, `verified`,
`checked` or `not checked` becomes a verdict on T1.1, T1.2, … So either hypotheses get
closed by rows that are not about them, or the report gets a spurious "gives hypothesis
T1.2 different verdicts" failure and the author is told to rewrite a correct report.
**Why it is a defect:** invariant 4; this is the same false positive as the numbered
acceptance table that was already reported from a live project, in the variant the fix
missed.
**Confidence:** confirmed
**Root:** report parser matches shape, not meaning

### T1-003 · medium · `n/a` inside a code span still decides the verdict
**Location:** `skills/finetooth/scripts/review.py:2037`
**What is wrong:** `verdict_word_at` protects `n/a` from `\w` and `/` on either side, which
kills the `curation/adapter.ts` false positive — but a backtick is neither, so `` `n/a` ``
matches, and `line_verdict` takes the **earliest** vocabulary word in the line.
**Failure scenario:** a hunter writes
``- T1.3 — the `n/a` token inside a path is no longer read as a verdict; checked by
test_n_a_внутри_пути`` . `n/a` stands earlier than `checked`, so the verdict recorded for
T1.3 is "not applicable". `hypotheses` prints it, `summary` inherits it, and the gate is
green — with the wrong answer to the question. The reverse is just as reachable with a line
that quotes `not checked` or `rejected` as a code span while stating the opposite.
**Why it is a defect:** invariant 4 — a word inside a code span is not a verdict.
**Confidence:** confirmed
**Root:** report parser matches shape, not meaning

### T1-004 · medium · A `~~~` fence is not a fence: a `#` line inside one truncates the Hypotheses section
**Location:** `skills/finetooth/scripts/review.py:2051`
**What is wrong:** `section_body`, `section_items_full` and `demote` recognise only
` ``` ` fences. CommonMark's other fence, `~~~` (used exactly when the content contains
backticks — a manifest quoting a markdown example), is invisible, so a column-0 `#` inside
it is treated as a heading.
**Failure scenario:** a manifest writes hypotheses 1–7, then a `~~~markdown` block whose
first line is `# heading` (or a shell example starting with `# comment`), then hypotheses
8–15. `section_body` closes the section at that `#`; `hypotheses()` returns 7 ids;
`check` demands seven verdicts, gets them, and passes. Eight hypotheses of the manifest were
never asked about, and `hypotheses_sha` freezes the truncated text, so later edits to
8–15 do not even show up as a change.
**Why it is a defect:** invariant 1 (green on a wrong state) and the hypotheses gate's own
purpose — it is the second denominator of coverage.
**Confidence:** plausible (read, not executed: no interpreter available in this role)
**Root:** report parser matches shape, not meaning

### T1-005 · medium · The block fingerprint and the readability ceiling read the working tree, not the index
**Location:** `skills/finetooth/scripts/review.py:340`
**What is wrong:** `file_sha` works on `ROOT/rel` (`is_file()`, then `git hash-object` on
the working-tree path) and returns `None` for anything not laid out on disk; `block_sha`
then folds `""` in its place. `block_lines` (review.py:1741) opens the same disk path and
swallows `OSError` as zero lines. `file_lines`, by contrast, reads `git show :path` and its
docstring names the case explicitly: "sparse-checkout does not lay out part of the tree at
all, yet `ls-files` prints it".
**Failure scenario:** a project reviewed in a sparse checkout (or with a file deleted from
the working tree but not committed). The block's unlaid files contribute only their names to
`reviewed_sha`; their contents can be rewritten upstream and `check` never reports "block
files changed after the review" — the block stays closed on code nobody compared. The same
checkout makes `block_lines` count those files as 0 lines, so a block far above the ceiling
passes "cannot be read in one session".
**Why it is a defect:** invariant 5 (git is the source of file truth, not the disk) and
invariant 6 (a fingerprint that misses part of its subject silently declares changed code
reviewed).
**Confidence:** confirmed
**Root:** file truth read from the disk instead of the index

### T1-006 · medium · The fix-commit gate compares a raw path against git's quoted output: a non-ASCII file name can never be marked fixed
**Location:** `skills/finetooth/scripts/review.py:2363`
**What is wrong:** the gate compares `f["file"]` with `set(git show --name-only …)`.
`ls-files -z` (how the register's paths are obtained) prints raw UTF-8; `git show
--name-only` obeys `core.quotePath`, which defaults to on, and prints
`"\320\274\320\276\320\264\321\203\320\273\321\214.py"`. Measured in a scratch repository:
`ls-files -z` → `модуль.py`, `show --name-only` → the quoted form.
**Failure scenario:** a Russian-language project (`lang: "ru"` is a first-class feature of
the kit) has a finding on `src/модуль.ts`; the fix commit touches exactly that file;
`set-finding H3-004 fixed --commit <sha>` succeeds, and `check` then reports for ever
"commit <sha> does not touch src/модуль.ts — either the mark belongs to another finding, or
the fix was made elsewhere". The gate is red on a truthful state and the only way out is a
`--fixed-in` that names a file the fix did not touch. `test_путь_с_пробелом_не_ломает_
проверку_коммита` covers spaces, which git does not quote, so the suite is green.
**Why it is a defect:** invariant 5 (paths are handled NUL-separated) and invariant 1 in its
mirror form — `check` must be trustworthy in both directions.
**Confidence:** confirmed (reproduced with git)
**Root:** git output parsed as plain text, without `-z`/`quotePath`

### T1-007 · medium · Fourteen `check` gates have no test at all
**Location:** `skills/finetooth/scripts/review.py:2224`
**What is wrong:** reading the whole of `tests/test_review.py` against the whole of
`cmd_check`, fourteen gates are exercised by nothing (table 1 below): state/definition
mismatch in both directions (2227, 2230); "declares report … not on disk" (2286); "status
X, but there is no hunter report" (2294); "stuck in running" red side and the unparsable
timestamp branch (2301, 2308); duplicate finding id (2322); empty mandatory field (2326);
`severity`/`confidence`/`status` outside the vocabulary (2330–2334); "rejected by the
verifier, but still open" (2384); "marked fixed, but no fix commit" (2378);
`claim`/`scenario` over the limit (2436, 2441); `findings.md` diverged from
`findings.jsonl` (2451); `proof` outside the vocabulary (2677).
**Failure scenario:** any of these mechanisms can be deleted and `python3 -m unittest
discover -s tests` stays green — e.g. drop the `findings.md != render_findings_md(rows)`
comparison and nothing fails, so the review's published findings table may silently
contradict the register it is generated from, and the gate that exists to notice it is gone.
**Why it is a defect:** invariant 2 — every check comes with a test, and a check whose
mechanism can be removed with the suite green is untested. `CONTRIBUTING`/`AGENTS.md` state
the rule as kept.
**Confidence:** confirmed
**Root:** a gate that cannot go red

### T1-008 · medium · guard-grep.sh goes green when the path it was told to scan no longer exists
**Location:** `skills/finetooth/assets/guard-grep.sh:69`
**What is wrong:** `[ -e "$path" ] || continue` drops a missing path without a word, and
`[ ${#files[@]} -gt 0 ] || exit 0` then exits clean. The script's own header claims the
opposite: "a path that does not exist is simply skipped — a gate must not go green because
someone moved a package".
**Failure scenario:** a Makefile gate reads `guard-grep.sh --pattern '\.Publish\(' --marker
'outbox-allowed:' -- internal/billing`. Someone renames `internal/billing` to
`internal/payments`. The gate prints nothing and exits 0; CI is green; every forbidden call
in the moved package is now unguarded, and the failure looks exactly like success.
**Why it is a defect:** invariant 1 — a gate that cannot go red on a wrong state; and
invariant 3 — silence where a refusal naming the fix ("no such path: …; the gate scanned
nothing") belongs.
**Confidence:** confirmed
**Root:** a gate that cannot go red

### T1-009 · medium · `import` hands a new finding an id that already exists
**Location:** `skills/finetooth/scripts/review.py:1465`
**What is wrong:** `f["id"] = f.get("id") or f"{args.block}-{i:03d}"` numbers by position,
and after the first import the block's file already carries ids. A row inserted **above**
them takes position 1 and therefore the id of the first existing finding.
**Failure scenario:** `import H1` numbers three findings H1-001…003 and writes the ids back.
The fixer finds another defect and prepends a line (no `id` field) to
`docs/review/reports/H1-findings.jsonl`. `import H1` → the new row becomes H1-001, the old
H1-001 keeps H1-001: `findings.jsonl` now holds two H1-001, both written back into the block
file. `check` reports "finding H1-001: duplicate id"; `set-finding H1-001 …` only ever
reaches `hit[0]`, so the other record cannot be moved except by hand.
**Why it is a defect:** invariant 11 (`import` is idempotent for the same draft) and
invariant 1. `test_идентификаторы_находок_не_разъезжаются_при_повторном_импорте` builds
precisely this input (`rows2 = [new] + first`) and asserts only on the two old rows, so the
collision passes the suite.
**Confidence:** confirmed
**Root:** none (single instance)

### T1-010 · medium · A hand-written block definition produces a traceback instead of a refusal
**Location:** `skills/finetooth/scripts/review.py:568`
**What is wrong:** block dictionaries are indexed directly: `b["phase"]` (`status`, 568,
983), `b["title"]`/`b["role"]`/`b["goal"]` (`prompt`, 1314–1317), `b['slug']`
(`manifest_path`, 369, reached by `check`, `restamp`, `verdicts_for`, `summary`). Nothing
validates the definition — `check` validates statuses written into `state.json` by hand but
never the blocks themselves, and `setup` writes `"blocks": []` for a human to fill in.
**Failure scenario:** a human adds `{"id": "H2", "title": "Payments", "paths": ["src/pay"]}`
to `blocks.json` by hand (the example file is the only schema) and runs `review.py status`
→ `KeyError: 'phase'`, a traceback and exit 1. `check`, the gate that exists to catch a
broken state, dies the same way at `manifest_path` as soon as the block leaves `todo`.
**Why it is a defect:** invariant 12 — a traceback reaching the user is a defect regardless
of the cause, and exit codes mean something (this one exits 1, which reads as "the state is
red"); invariant 3 — a refusal names the command that fixes it.
**Confidence:** confirmed
**Root:** hand-edited input validated for one file and not the other

### T1-011 · medium · The stale-tree gate silently never fires without `refs/remotes/origin/HEAD`
**Location:** `skills/finetooth/scripts/review.py:666`
**What is wrong:** `stale_tree` reads `symbolic-ref --short refs/remotes/origin/HEAD` and
returns `None` when it is empty — no warning, no note in `check`'s output. The ref is set by
`git clone`, but not by `git init` + `remote add` + `fetch` (the CI shape), and never for a
remote named anything but `origin`. The kit's own tests have to create it by hand
(test_review.py:1609, 1658), which is the clearest evidence it is not a given.
**Failure scenario:** a review runs in a CI checkout built with `git init && git remote add
upstream … && git fetch`. The tree is a month behind; `check` prints "review state is
consistent" every time; a verifier "confirms by execution" findings on code that was fixed
three weeks ago — the exact failure the threshold comment was written for.
**Why it is a defect:** invariant 2 — a gate whose mechanism is inert in a common
configuration, with nothing said about it, is not a gate.
**Confidence:** confirmed
**Root:** a gate that cannot go red

### T1-012 · medium · run-role.sh writes a spend line to the journal for a run that was cut off or failed
**Location:** `skills/finetooth/assets/run-role.sh:40`
**What is wrong:** `RC` is captured and then ignored until the final `exit $RC`: the journal
line is appended unconditionally, and neither the line nor `axes.py` carries the run's
outcome (`result.subtype`, `is_error` and the `--max-turns` trip are never looked at).
**Failure scenario:** a hunter hits the 110-turn cap. `claude` exits non-zero with a partial
report on disk; `review log T1 "hunter — spend: 34 min, 110 turns, …"` records a line that
reads exactly like a completed run. The journal — which the method treats as the record of
what happened, because state lives on disk and not in the conversation — says the block was
hunted for 110 turns and says nothing about the assignment being truncated. The next
session's lead reads it as a finished run.
**Why it is a defect:** the turn cap is called "the safety switch"; a switch whose trip is
not recorded cannot be acted on. Invariant: state on disk is the only memory there is.
**Confidence:** confirmed
**Root:** spend recorded without its outcome

### T1-013 · low · `coupling` and `order` undercount churn: renames split a file's history and non-ASCII paths never match
**Location:** `skills/finetooth/scripts/review.py:814`
**What is wrong:** `commit_file_sets` parses `git log --first-parent --no-merges
--name-only`, which (a) prints only the **new** path of a detected rename and (b) quotes
non-ASCII paths, while `owned` comes from `ls-files -z` and holds raw paths. Anything that
does not match `owned` is dropped by `{f for f in files if f in owned}`.
**Failure scenario:** measured on this repository: `review.py` has 41 first-parent commits
under `--follow` and 9 under its current path (renamed in 91e6ffb and fbb3138). `order`
ranks T1 — the block covering the file the whole kit turns on — on 9 commits, i.e. 22% of
its real change frequency, and the ranking is the product of the command. In a project with
Cyrillic file names those files are invisible to `coupling` and to `order`'s churn
altogether, so a seam between two blocks can never be reported.
**Why it is a defect:** the ranking is presented as a measurement ("the top 10% of files by
change frequency collected 34% of the later fixes"), and the measurement systematically
loses the history of every renamed and every non-ASCII-named file.
**Confidence:** confirmed (measured with git on this repository)
**Root:** git output parsed as plain text, without `-z`/`quotePath`

### T1-014 · low · The "every file named in a report" gate is satisfied by a substring
**Location:** `skills/finetooth/scripts/review.py:2596`
**What is wrong:** `missing = [f for f in owned if f not in text]` — plain substring
containment over the concatenated reports.
**Failure scenario:** a block owns `src/api.ts` and `src/api.ts.snap`. A report that names
only `src/api.ts.snap` marks both as named. More cheaply: the prompt hands the agent the
full file list in a fenced block, so pasting that list into the report closes the gate for
every file of the block without a single one being opened — which is the exact claim
("read 25 of 25") the gate was built to stop.
**Why it is a defect:** invariant 1 — the gate can be made green without the state it
asserts.
**Confidence:** confirmed
**Root:** report parser matches shape, not meaning

### T1-015 · low · On a history of 20 commits or fewer the mass-commit cutoff never skips anything
**Location:** `skills/finetooth/scripts/review.py:831`
**What is wrong:** `idx = min(len(sizes) - 1, (len(sizes) * percentile) // 100)`; for
`len <= 20` that is `len-1`, the largest commit, and the guard is a strict `>`.
**Failure scenario:** a young repository (12 commits) runs `coupling`: the initial commit
containing the whole tree is treated as an ordinary change and pairs every owned file with
every other; three formatting sweeps reach `together >= 3`. The output is a wall of pairs
that say nothing about a seam, and `order`'s churn counts every block as touched by every
mass commit. The threshold comment promises the opposite ("so a codemod or a formatting
sweep does not manufacture pairs").
**Why it is a defect:** the documented protection is absent exactly where blocks are first
being cut — on a new repository, which is when `coupling` is run.
**Confidence:** confirmed (by the arithmetic of `mass_cutoff`)
**Root:** threshold that does not hold at the edge of its range

### T1-016 · low · `summary --aged` breaks on a title or path containing ` -->`
**Location:** `skills/finetooth/scripts/review.py:1115`
**What is wrong:** the machine block is parsed as `text[i+len(MARK):text.index(" -->", i)]`
and handed to `json.loads`. The block contains every block's title and paths verbatim.
**Failure scenario:** a block is titled "Import --> export pipeline". `summary` writes it
into the machine block; `summary --aged docs/review-summary.md` slices at the first
` -->` inside the title, `json.loads` raises `JSONDecodeError`, and the user gets a
traceback instead of the drift table — on the one file that is supposed to outlive
`docs/review/`. A title that ends with `-->` and no trailing marker raises `ValueError` from
`.index` instead.
**Why it is a defect:** invariant 12 — a traceback reachable from a legal command line.
**Confidence:** confirmed
**Root:** hand-edited input validated for one file and not the other

### T1-017 · low · `axes.py` cannot tell a cut-off stream from a complete one, and dies on a truncated line
**Location:** `skills/finetooth/scripts/axes.py:63`
**What is wrong:** every headline number comes from the `result` event; without it `turns`
is `None`, `duration_s` 0, `cost_usd` 0, and `output` falls back to the sum of per-message
counts that the comment two lines above calls a stream artefact. Nothing in the output says
the stream was incomplete. Separately, `json.loads(line)` on every non-empty line raises on
the truncated last line a killed writer leaves.
**Failure scenario:** a run is killed (or the cap trips before the result event is written).
`axes.py stream.jsonl --journal` prints "spend: 0 min, None turns, …, output 0k, cost
estimate $0.00" and `run-role.sh` writes it to the journal: an expensive truncated run is
recorded as free. With a truncated final line the script raises instead, and under
`set -e` that costs the journal line and the agent's reply, leaving only `$TMPDIR`.
**Why it is a defect:** the spend measurement is what the turn caps are derived from;
a number that silently means "unknown" is worse than an absent one.
**Confidence:** plausible (read, not executed: no real stream available in this role)
**Root:** spend recorded without its outcome

### T1-018 · low · `init` is not idempotent on disk
**Location:** `skills/finetooth/scripts/review.py:480`
**What is wrong:** `st["updated_at"] = now()` is set on every run, including the run that
changes nothing else.
**Failure scenario:** CI runs `review.py init && review.py coverage --no-write && review.py
check` and then asserts a clean tree (the usual shape for a generated-artifact gate).
`state.json` is dirty after every run, so the gate fails on a correct state; the honest
workaround is to stop running `init` in CI, which is what the gate existed to guarantee.
**Why it is a defect:** invariant 11 names `init` among the commands that "re-run without
changing a correct state".
**Confidence:** confirmed
**Root:** none (single instance)

### T1-019 · low · The verifier's coverage verdict is satisfied by the word "complete" anywhere in the report
**Location:** `skills/finetooth/scripts/review.py:2013`
**What is wrong:** `COVERAGE_VERDICT` matches `coverage|complete|incomplete|охват|полн…`
anywhere in the body, minus the template placeholder line.
**Failure scenario:** a verifier writes "I completed the check of every finding; the code is
correct." — no statement about what was left unreviewed anywhere in the report — and the
gate passes, because "completed" contains "complete". The gate that is supposed to make
coverage a separate question from verdicts is answered by a verb about verdicts.
**Why it is a defect:** invariant 1 — the gate can be satisfied without the content it
demands; the neighbouring gate for the hunter (an empty limits section) is strict.
**Confidence:** confirmed
**Root:** report parser matches shape, not meaning

### T1-020 · low · Thresholds without a source
**Location:** `skills/finetooth/scripts/review.py:1169`
**What is wrong:** four numbers carry no measurement and no reference, in a file where
every other constant does: `REF_LIST_LIMIT = 80` (1169); the 200-character bound for
"manifest is empty or nearly empty" (2263); `CLAIM_MAX = 220` / `SCENARIO_MAX = 700`
(121–122 — the comment argues that a cap is needed, not why these values);
`COUPLING_HUB_BLOCKS = 6` (806 — the comment cites measurements for `MIN_TOGETHER` and
`MIN_SHARE`, and describes the hub rule without a number behind it).
**Failure scenario:** a project whose manifests are terse fails "manifest is empty or nearly
empty" at 199 characters and nobody can say whether 200 is defensible or whether the
manifest is; the same question about 80 reference files cannot be answered by reading.
Tuning them becomes taste, and the next number added follows the precedent.
**Why it is a defect:** invariant 8 — every number has a source next to it; a bare magic
number is a finding.
**Confidence:** confirmed
**Root:** threshold without its source

### T1-021 · low · `prompt` substitutes into the manifest's text and blames the template for the manifest's placeholders
**Location:** `skills/finetooth/scripts/review.py:1342`
**What is wrong:** substitutions are applied in dict order over the whole body, so anything
the manifest or the invariants text contains is itself subject to later substitutions
(`{{FILES}}`, `{{VOLUME}}`, `{{GATES}}` all come after `{{MANIFEST}}`), and the
leftover-placeholder check reports the **template** file name for a placeholder that came
from the manifest.
**Failure scenario:** the T2 manifest quotes a template placeholder that is not in the
substitution table — say `{{HUNTER_NOTE}}` — while explaining how templates work.
`review.py prompt T2 --role hunter` exits 2 with "template hunter.md has substitutions left
without a value: {{HUNTER_NOTE}}". `hunter.md` has no such placeholder; the author edits the
wrong file. The mirror case is quieter: a manifest quoting `{{FILES}}` gets the block's file
list pasted into its own prose.
**Why it is a defect:** invariant 3 — the message must lead to the fix, and this one leads
to the wrong file.
**Confidence:** confirmed
**Root:** hand-edited input validated for one file and not the other

## Acceptance tables

### Table 1 — gate → test → mutation

Every numbered gate of `cmd_check` (plus the fingerprint, named-files, fix-gate and age
checks). "Mutation" is what should turn the named test red; **no mutation was executed**
(see Coverage limits). Gates with "—" in the test column are finding T1-007.

| # | gate (review.py) | test | mutation that should turn it red |
|---|---|---|---|
| 1 | block in blocks.json missing from state (2227) | — | delete the loop |
| 2 | block in state missing from blocks.json (2230) | — | delete the loop |
| 3 | status outside the vocabulary (2233) | test_статус_блока_вписанный_руками | drop `status not in STATUSES` |
| 4 | phases do not decrease (2242) | test_фазы_в_массиве_не_убывают | always `prev = None` |
| 5 | blocked without a note (2251) | test_заблокированный_блок_не_значит_закончено | drop the note test |
| 6 | manifest missing (2261) | — | drop `if not manifest.exists()` |
| 7 | manifest shorter than 200 chars (2263) | test_куцый_манифест_роняет_проверку | raise the bound to 0 |
| 8 | verifier report missing (2274) | test_закрытие_с_починками (indirect) | drop `if not rep.exists()` |
| 9 | verifier report empty / no verdict / no coverage (1990–2017) | test_пустой_отчёт_проверяющего, test_без_находок_проверяющий, test_нетронутая_строка_шаблона | return `None` from `verify_report_problem` |
| 10 | declared report not on disk (2286) | — | drop the loop |
| 11 | no hunter report past `running` (2294) | — | drop the loop |
| 12 | running without a timestamp (2301) | — | drop the branch |
| 13 | running longer than 24 h (2311) | green side only (test_время_running_считается_от_последнего_старта) | raise `STALE_RUNNING_HOURS` — suite stays green |
| 14 | duplicate finding id (2322) | — | drop `seen_ids` |
| 15 | mandatory field empty (2326) | — | drop the loop |
| 16 | severity/confidence/status vocabulary (2330–2334) | — | drop the three branches |
| 17 | open/deferred finding on a missing file (2338) | test_починенная_находка_на_удалённом_файле | drop the `not in tracked` test |
| 18 | deferred without a reason (2343) | test_отложенная_находка_требует_причину | drop the branch |
| 19 | external fix commit form (2348) | test_починка_в_соседнем_репозитории | accept any `:` form |
| 20 | fix commit exists and touches the file (2363) | test_коммит_починки_обязан_касаться_файла, test_починка_в_общем_модуле, test_путь_с_пробелом | ignore `touched.stdout` |
| 21 | fixed without a commit (2377) | — | drop the branch |
| 22 | duplicate without `dup_of` / dangling (2379) | test_дубль_указывает_на_живую_находку | return `None` from `dup_problem` |
| 23 | confidence rejected but status open (2383) | — | drop the branch |
| 24 | status rejected, confidence not (2385) | test_отказ_меняет_и_уверенность | drop the branch |
| 25 | open finding without `code_sha` (2393) | test_старые_записи_без_отпечатков | drop the branch |
| 26 | `code_sha` changed since import (2399) | test_изменившийся_код_под_открытой_находкой, test_повторный_импорт_не_переснимает | compare against `file_sha` of a constant |
| 27 | cited line beyond the file (2412) | test_несуществующая_строка, test_строка_за_концом_файла (green side) | drop the comparison |
| 28 | rejected without a reason (2422) | test_отвергнутая_находка_без_причины, test_причина_отказа_принимается | accept an empty `said` |
| 29 | claim / scenario over the cap (2435, 2440) | — | raise `CLAIM_MAX` to ∞ |
| 30 | findings.md diverged from the register (2450) | — | drop the comparison |
| 31 | pattern matching nothing / only untracked (2458) | test_шаблон_который_ничего_не_нашёл, test_шаблон_по_нетрекнутым_файлам | drop the loop |
| 32 | unowned files (2474) | test_непокрытый_файл_роняет_карту, test_пустой_список_путей | return an empty `unassigned` |
| 33 | coverage.tsv stale (2489) | test_устаревшая_карта_покрытия | compare only line counts |
| 34 | manifest without hypotheses (2505) | test_манифест_без_гипотез | skip when `ids` is empty |
| 35 | contradictory verdicts in one report (2515) | test_противоречивые_вердикты, test_нумерованная_таблица (green side) | return `{}` from `verdict_conflicts` |
| 36 | hypothesis without a verdict (2523) | test_гипотеза_без_вердикта, test_проверки_не_выключаются_переводом, test_идентификатор_блока_с_буквенным_суффиксом | treat `missing` as empty |
| 37 | post-verify block without `reviewed_sha` (2540) | test_старые_записи_без_отпечатков | `continue` instead |
| 38 | block files changed after the review (2545) | test_блок_просмотренный_на_другой_версии, test_перенаправленный_симлинк, test_промежуточный_статус | make `changed_since_review` return `False` |
| 39 | ref_paths changed — warning (2559) | test_правка_контекста_предупреждает_но_не_роняет | drop the warning |
| 40 | hypotheses fingerprint missing / changed (2564, 2569) | test_правка_гипотез_после_проверки, test_правка_продолжения_гипотезы | compare only item counts |
| 41 | every block file named by full path (2596) | test_каждый_файл_блока_назван_полным_путём | treat `missing` as empty |
| 42 | closed with fixes but no fixreview report (2612) | test_закрытие_с_починками_требует_ревью_правок | drop the glob test |
| 43 | coverage-limits section missing / empty (2627) | test_отчёт_без_раздела, test_пустой_раздел, test_ограничения_охвата_требуются, test_английские_заглушки | return a non-empty body always |
| 44 | third instance of a root without a guard (2644) | test_третий_повтор_корня, test_два_экземпляра, test_отвергнутые_и_дубли | raise `ROOT_RULE_AT` |
| 45 | guard path does not exist (2650) | test_узда_обязана_существовать | return `None` from `rule_problem` |
| 46 | tree behind origin (2663) | test_отставшее_от_сервера, test_свежий_коммит_в_давней_ветке | raise `STALE_TREE_DAYS` |
| 47 | `proof` outside the vocabulary (2676) | — | drop the branch |
| 48 | block above the readability ceiling (2684) | test_блок_который_за_сеанс_не_прочитать, test_порог_размера_не_считает_исключённое, test_порог_читаемости, test_измеряемый_блок | raise `READABLE_LINES` |
| 49 | open findings older than 7 days — warning (2691) | test_check_предупреждает_о_находке_старше_недели | drop the warning |
| 50 | fix gate (set-status running only, **not in check**) | test_гейт_починки_не_пускает, test_гейт_починки_открывается, test_гейт_none | drop the `debt` branch |

### Table 2 — `MSG` keys, en vs ru

| set | count | difference |
|---|---|---|
| `MSG["en"]` | 56 | — |
| `MSG["ru"]` | 56 | — |
| en − ru | 0 | — |
| ru − en | 0 | — |

Call sites checked one by one: every `T(...)` key in `review.py` (`none`, `refs_cut`,
`vol_*`, `gates_missing`, `proof_*`, `files_*`, `scope_line`, `no_open_findings`, `f_*`,
`md_*`, `journal_head`, `sum_*`, `aged_*`, `backfill_note`) and the three direct
`MSG[lang][...]` lookups in `cmd_setup` (`setup_note`, `excl_apparatus`, `excl_skill`)
resolve on both sides. Format placeholders agree key-for-key, so no `T()` call can raise
`KeyError` on either language today. **No finding.** The exposure remains structural: the
tables are two hand-maintained literals with no test comparing them, and `T()` fails at run
time on the first project that takes an untested path in `ru`.

### Table 3 — report line → verdict

Derived by hand from `line_verdict` (lowercase the line, take the earliest occurrence of any
vocabulary word; ties go to the alphabetically smaller verdict) and `verdict_mentions`.
"Wrong" marks a divergence between what the sentence says and what the tool records.

| # | line | expected | actual | |
|---|---|---|---|---|
| 1 | ``- `T1.1 — checked: proven by running the code` `` | checked | checked | |
| 2 | `- T1.2 — not checked: no live system` | not checked | not checked | |
| 3 | `- T1.3 — not applicable: not about this code` | not applicable | not applicable | |
| 4 | `- T1.4 — гипотеза подтвердилась` | checked | checked | |
| 5 | `- T1.5 — не проверена` | not checked | not checked | |
| 6 | `- T1.6 — гипотеза не подтвердилась` | checked (negative outcome) | checked | |
| 7 | `the path features/curation/adapter.ts holds n/a` | none | none (the `/` guard works) | |
| 8 | `see https://example.com/not-applicable/x` | none | none (hyphen ≠ space) | |
| 9 | ``- T1.7 — the `n/a` token in a path is handled; checked by test`` | checked | **not applicable** | wrong |
| 10 | ``- T1.8 — `checked` is only a code span here, in fact not examined`` | none / not checked | **checked** | wrong |
| 11 | `- T1.9 — the block moves to verified after the report` | none | **checked** | wrong |
| 12 | `- T1.10 — checked` | T1.10 checked | T1.10 checked (greedy `\d+`) | |
| 13 | `T1.1 is contained in T1.10 — checked` | both named | both get "checked" | |
| 14 | `- T1.11 — the tree is complete and the fix is not checked` | checked (about the fix) | **not checked** | wrong |
| 15 | `hypothesis 2 refuted by experiment` | T1.2 checked | T1.2 checked | |
| 16 | `гипотеза №3 опровергнута` | T1.3 checked | T1.3 checked | |
| 17 | `- T1.12 — unverified area` | not checked | not checked | |
| 18 | `- T1.13 — not confirmed, the code is correct` | checked | checked | |
| 19 | `nothing here at all` | none | none | |
| 20 | fenced block containing ``- `T1.1 — checked: <what proves it>` `` | none (it is an example) | **checked** | wrong (T1-001) |
| 21 | fenced block containing `- T1.2 — not checked: <what got in the way>` | none | **not checked** | wrong (T1-001) |
| 22 | `\| # \| hypothesis \| outcome \|` then `\| 1 \| … \| refuted \|` | T1.1 checked | T1.1 checked | |
| 23 | header-less `\| 1 \| gate one \| test_a \| confirmed \|` | none (a gate table) | **T1.1 checked** | wrong (T1-002) |
| 24 | header-less `\| 3 \| gate three \| test_c \| not checked \|` | none | **T1.3 not checked** | wrong (T1-002) |
| 25 | `\| # \| place \| constraint \| n/a \|` header + `\| 1 \| a.ts \| uq_a \| n/a \|` | none | none (the 2151 fix holds) | |

## Checked and found correct

- **`listed()` / `untracked_files()`** use `ls-files -z` and split on NUL, and `--stage`
  lets submodules be told from files by mode. The symlink decision (kept as a file, hashed
  by link text) is deliberate, documented, and tested from both sides.
- **`set-finding` on several ids is all-or-nothing** — the register is written after the
  loop, so a `die()` on the third id leaves the file untouched (hypothesis T1.7).
- **`file_lines()`** is the careful one: index first, NUL sniff for binaries, disk only as a
  fallback. The defect is that `block_lines` did not inherit any of it (T1-005).
- **`verdicts_for` layering** (hunter → fix → verify, `update` not `setdefault`) really does
  let the verifier override, and is tested.
- **The `n/a`-inside-a-path and the headed-acceptance-table false positives are genuinely
  fixed** — both have tests, and my table-3 rows 7 and 25 confirm the fixes hold.
- **Greedy `\d+` in the tagged-id regex** means `T1.1` cannot be matched inside `T1.10`;
  the letter-suffix block ids (`V1d`) are handled by taking the id from the definition.
- **`signal.signal(SIGPIPE, SIG_DFL)`** — `prompt … | head` is a real usage and this is the
  right fix for it.
- **`repo_root()` from the working directory** is the correct call for a skill that lives
  outside the project, and the test that asserts the kit's own `state.json` is untouched
  while running in a foreign tree is the right shape of proof.
- **`render_findings_md` is a pure function of the rows** (no wall clock), which is what
  makes gate 30 comparable by content at all — the gate itself just has no test.
- **`import --append`** numbering is collision-free and the re-run really is a no-op.
- **`guard-grep.sh`'s awk contract**: the regexes travel through `ENVIRON`, not `-v`, and
  the marker is paired by line number inside one file — both are correct and the reasoning
  in the header is sound. The `name=value` operand hazard of awk is neutralised in practice
  because `find` prefixes every path with the scan root, so a file called `a=b.go` reaches
  awk as `internal/a=b.go`, which is not a valid assignment.
