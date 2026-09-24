# T1 · The tool: review.py, axes.py, run-role.sh

## Why this block exists

`skills/finetooth/scripts/review.py` is 2,958 lines in one file: the state machine of a
review, the coverage map, six fingerprints, the prompt assembler with a bilingual string table,
the findings register with its moves, and `check` — 20+ gates that decide whether a review is
telling the truth. Two live projects trust its verdicts. Two false positives in the verdict
parser and a `git add` blind spot were found by the first block run on a real project; the
tool has never been read as a whole by anyone but its authors. `axes.py` (spend by axis) and
`run-role.sh` (headless role runner with a turn cap) are new and unreviewed.

## What counts as a finding, and what does not

**A finding:** a way to make `check` green on a wrong state; a gate that cannot go red
(mechanism removable with the suite green); a parser that takes a word in a path, code span or
fenced block for a verdict/status; a git interaction that reads the disk instead of the index
or breaks on a legal path (spaces, `[`, unicode, NUL-safe listing); a fingerprint that misses
part of its subject; a `die()` without the way out; a string present in `MSG["en"]` and absent
in `MSG["ru"]` (or vice versa); a non-idempotent re-run; a traceback reachable by a legal
command line; a magic number without its source.

**Not a finding:** the single-file layout, the absence of a library, argparse conventions,
wording that already names the fix.

## Hypotheses specific to this project

1. **`T()` is a run-time `KeyError` for any key missing in one language.** `MSG["en"]` and
   `MSG["ru"]` have grown separately (summary, aged, proof strings). Hypothesis: the key sets
   differ, and a Russian-language project hits the missing key on a code path the English
   tests never take. Verify by comparing key sets and by running each command with `lang: ru`.
2. **The verdict parser still has shape-based false positives.** After the `n/a` and table
   fixes: a hypothesis id inside a code span or a fenced block, `H1.1` matching inside
   `H1.10`/`H11.1` with `\b`, "not checked" as part of a longer phrase, a verdict word inside a
   URL. Build a table of inputs; expected verdicts vs actual.
3. **`section_body` / `section_items_full` treat headings inside fenced blocks as headings.**
   Both track fences, but a fence with an info string and indentation (`   ```json`), a `~~~`
   fence, or a heading-like line inside an indented code block may not be recognised.
4. **Fingerprints miss part of their subject.** `block_sha` over `git_files(paths)`: a file
   deleted from the block's patterns changes the set — does the sha change? `refs_sha` over
   `ref_paths`; `hypotheses_sha` over item text; `code_sha` per finding over `file:line` — a
   finding whose `line` is empty or out of range. Hypothesis: at least one fingerprint stays
   equal on a change it is meant to catch.
5. **git-pathspec assumptions.** `git_files` with a pattern containing `[`, `(`, spaces, a
   leading `./`, or a `:(exclude)` magic in `paths`; `coverage` when two blocks own the same
   file; `named_files` matching a path that is a prefix of another. Hypothesis: one of these
   silently drops or double-counts a file.
6. **`import` and `import --append` id assignment.** Ids `<block>-NNN` come from the count of
   existing rows; after a `rejected`/`duplicate` row is present, a second `--append` may reuse
   an id or renumber. Hypothesis: a collision or a gap is reachable.
7. **`set-finding` with several ids is not all-or-nothing.** If the third id is unknown, were
   the first two already written? Also `--commit` validation for `fixed` when the commit exists
   but the finding's file is renamed in that commit.
8. **`check` exit codes and ordering.** Warnings vs failures; a gate that `die()`s (exit 2) in
   the middle of `check` hides the remaining gates; the stale-tree gate when there is no
   `origin` at all. Hypothesis: a legal repository state produces a traceback or a partial
   `check`.
9. **`stale_tree` reads `refs/remotes/origin/HEAD`** — absent on a fresh clone without
   `remote set-head`, absent for a repository whose remote is not named `origin`. Hypothesis:
   the check silently never fires, or dies.
10. **`commit_file_sets` and renames.** `git log --name-only` prints the new path only; a
    file renamed mid-history splits its churn between two names, and `coupling` pairs the old
    name (no longer owned) with nothing. `order` undercounts. Hypothesis: measurable on this
    repository's own history (`docs/banner.png` → `.github/banner.png`).
11. **`mass_cutoff` on tiny histories.** With fewer than 20 commits the 95th percentile is the
    largest commit, so nothing is ever skipped — and the initial commit (everything) creates
    pairs between every file. Hypothesis: `coupling` on a young repository is all noise.
12. **`summary --aged` parses its own machine block with `text.index(" -->", i)`.** A path or
    title containing ` -->` breaks it; a summary edited by hand (the heading says "do not
    edit") silently changes `base`. Hypothesis: a legal title breaks `--aged`.
13. **`run-role.sh` trusts `claude` to honour `--max-turns` and writes the journal line even
    when the run failed (`RC != 0`)** — a cut-off run is then logged as a spend line without
    the word "cut off". Also `set -e` vs the `$REVIEW prompt` failure path: does a bad block id
    leave a stray prompt file and a journal entry?
14. **`axes.py` counts `output_tokens` from `result.usage` only.** A stream without a `result`
    event (killed run) reports output from per-message counts, which the stream sets to the
    first chunk (1–5 tokens). Hypothesis: a cut-off run reports near-zero output and looks
    cheap.
15. **Idempotence of `init` on an existing review** — does it reset `state.json` statuses,
    `started`, fingerprints? And `setup` on a repository that already has `docs/review/`.

## Acceptance criterion

The block is not closed without three tables built by reading (and running) the code:

1. **Gate → test → mutation.** For every gate in `check` (numbered comments 1…N plus the
   fingerprint, named-files, fix-gate and age checks): the test that covers it and the
   mutation that turns that test red. Gates without a test, or with a test that survives the
   mechanism's removal, are findings.
2. **`MSG` keys en vs ru.** The two key sets, their difference, and every `T()` call site whose
   key is missing on one side.
3. **Parser inputs → verdict.** A matrix of at least 20 report lines (both languages, tables,
   code spans, fenced blocks, ids that prefix other ids) with the expected and the actual
   verdict from `line_verdict` / `verdict_mentions`.
