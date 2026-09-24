[Русская версия](ru/how-it-works.md)

# Whole-repository review of a project by AI agents — how it is built and how to set it up for yourself

> Text by **Georgiy Khudobandaev** (https://github.com/Georgiy-Khudobandaev),
> received 16.09.2026. The account is the author's own; only what identifies his project
> unambiguously has been anonymised — the name, the exact size and the stack. The analysis of
> what in the description was confirmed and what turned out to be broken is in `../README.md`
> and `comparison-with-practice.md`.
>
> ⚠️ The paths in the text are from the original kit: `review.py`, `prompts/`, `example/`.
> Since 0.4.0 the kit is a skill under the Agent Skills standard, and the same parts live in
> `skills/finetooth/`: `scripts/`, `references/`, `assets/` (the map is in `../README.md`,
> section "What is inside").

This is a description of a working system, not an idea. The first block of 29 went through it
on a large project (a backend, two clients and a separate service, hundreds of thousands of
lines): 15 access-rights defects were found, all closed, and another 51 defects were found
**in the fixes themselves** — caught by verifying agents that had not written those fixes.

Next to this file lie all the working parts; they can be taken as is and adapted:

- `README-ревью.md` — **the entry point**. Goes into the repository as `docs/review/README.md`;
  a cold agent reads it in full and then works on its own. The most important file after the
  tool.
- `review.py` — the tool, one file, standard library only.
- `prompts/` — three prompt templates: hunter, verifier, fixer.
- `example/agent-banner.md` — text placed at the top of the file that is read in every session
  of the project. Without it a new session will not know the review exists.
- `example/invariants.example.md` — the project's rules, pasted into every agent's prompt.
- `example/blocks.example.json` — three blocks of different types.
- `example/manifest.example.md` — a block manifest with hypotheses and an acceptance criterion.
- `example/journal.example.md` — the header of the decisions journal.
- `example/makefile-snippet.mk` — `make` targets.
- `example/guard-grep.sh` — the engine for grep gates in the build (see section 9).

---

## 1. What problem this solves

Asking an AI agent "review the project" does not work for three reasons, and each of them
kills the result in its own way.

**The context is shorter than the work.** Reviewing a large project is dozens of hours and many
sessions. The dialogue window runs out, the history gets compressed, and the agent loses what
it has already decided. Two days later, in a new window, it starts from zero and finds the same
things — or, worse, does not.

**There is nothing to prove completeness with.** "I looked at the code" is a claim, not a fact.
Without bookkeeping one cannot say whether a file was read, and especially whether there are
files nobody read.

**The agent that searches must not fix.** As soon as the model starts editing it stops
searching: attention goes into the edit. And whoever found the defect is the worst verifier of
their own fix, because they check the same thought they went wrong with.

The system is built around these three points.

---

## 2. Five principles — worth understanding before the files

### 2.1. State lives on disk, not in the dialogue

Not one finding, not one status, not one decision is kept in the conversation. Everything is
in files in the repository. An agent opening the project for the first time runs one command
and sees the whole picture: what is done, what is next, which findings are open.

A practical consequence: the project's root instructions file (`CLAUDE.md`, `AGENTS.md`,
`.cursorrules` — whatever is read in every session for you) gets a short banner: "a review is
in progress, read `docs/review/README.md`, the state is on disk, do not start your own parallel
survey". Without it a new session simply will not know the review exists.

### 2.2. Completeness is proven by the coverage map

Every file in the repository is assigned to some block. The command rebuilds the "file → block"
map and **fails** if even one tracked file belongs to no one. That is the proof that the review
is exhaustive: not "we looked at the important stuff" but "there are no uncovered files".

This check catches things you do not expect. For us it showed that an entire microservice
belonged to no block — it had simply been forgotten. And after the fix of the first block it
caught a file the agents had created during the edits, which also turned out to be unowned.

### 2.3. The prompt is assembled by machine, not written afresh

Nobody writes the agent's task by hand. The command assembles it from four versioned pieces:
the block manifest, the project's invariants, a mechanically expanded file list and the role
template. The same block a month later will ask exactly the same question, not whatever the
next session happens to remember.

### 2.4. Two roles for searching, a third for fixing

The **hunter** reads all the files of the block and puts forward findings. The **verifier**
checks each one against the current code and delivers a verdict: confirmed / plausible /
rejected — and makes its own independent pass over the riskiest places. The **fixer** fixes,
and is obliged to make sure anew that the defect exists.

Rejected findings are not deleted: they stay in the register with the reason for rejection.
Otherwise the next review will find the same thing and spend the time again.

### 2.5. The fix diff goes through an independent review before merging

This was not there from the start, and it cost dearly. The first security fix passed all the
gates: the linter clean, the tests green, the migrations valid — and **broke working things**.
The master stopped seeing his technicians' rounds. Escalation on an overdue ticket could have
reached no one.

The reason is simple and universal: all the new tests proved that an outsider no longer sees
too much, and not one checked that one's own still sees one's own.

So fixes go to verifying agents that did not write them, **before** the MR is opened. For us
that gave three rounds: 26 findings, then 13, then 8, then 4 trifles and the verdict "safe to
merge". Convergence is visible, and it is the only honest sign that it is time to stop.

---

## 3. What lies on disk

The `docs/review/` directory in the repository:

| File | What is in it | Who edits |
|---|---|---|
| `README.md` | the entry point: the agent reads it in full and then acts on its own | a human, rarely |
| `blocks.json` | the definition of all blocks: paths, reviewer role, purpose | a human, rarely |
| `state.json` | the status of each block | the tool only |
| `findings.jsonl` | the single findings register, one line per finding | the tool only |
| `findings.md` | a human-readable summary | generated |
| `coverage.tsv` | the "file → block" map | generated |
| `invariants.md` | the project's rules, pasted into every agent's prompt | a human |
| `journal.md` | the decisions journal: what was decided and why | appended to |
| `blocks/*.md` | the block manifest: why, hypotheses, acceptance criterion | a human |
| `prompts/*.md` | the prompt templates for the three roles | a human, rarely |
| `reports/*.md` | the agents' reports | the agents themselves |

**An important detail about reports: the agent writes them itself, straight to disk.** A
subagent's final answer reaches only the session that launched it, and dies with that
session's context. If the agent did not write the result to a file — there is no result.

---

## 4. The tool

`review.py` — one file, standard library only, no dependencies. Commands:

| Command | What it does |
|---|---|
| `init` | create/extend `state.json` from `blocks.json` |
| `status` | where we are: blocks by phase, findings counter, next block |
| `next` | the id of the next unclosed block |
| `coverage` | rebuild the coverage map; fails if there are uncovered files |
| `prompt BLOCK ROLE` | assemble the full prompt for an agent |
| `set-status BLOCK STATUS` | move a block |
| `import BLOCK` | pull the block's findings into the shared register |
| `findings` | regenerate `findings.md` |
| `check` | check the consistency of the whole state |
| `log BLOCK "text"` | append a line to the journal |

Block statuses: `todo → running → hunted → verified → triaged → fixing → closed`
(plus `blocked`).

On top — `make` targets, so as not to remember paths: `make review-status`, `review-prompt
BLOCK=H1 ROLE=hunter`, `review-import BLOCK=H1`, `review-check`, `review-coverage`. The
Makefile fragment is in `example/makefile-snippet.mk`.

### What exactly `check` checks — and why each check ended up there

This is the most valuable part of the tool, because every rule was born of a real mistake:

1. **State and block definitions are consistent** — no status for a non-existent block.
2. **Every block's manifest exists** — otherwise the prompt assembles empty.
3. **Declared reports are on disk** — a block cannot be "verified" without a report.
4. **No block past `running` without a hunter's report** — statuses are not moved "by eye".
5. **A block does not hang in `running` for more than a day** — almost always that is a broken
   session, the block must be restarted, not waited on.
6. **Findings are well-formed**: required fields filled, values from the vocabulary, no
   duplicate ids, the named file exists in the repository, "fixed" requires a commit,
   "duplicate" requires a reference, "rejected" cannot be open.
7. **`findings.md` matches `findings.jsonl`** — compared **by content**, not by file
   modification time: after `git clone` the modification time says only in what order things
   were written to disk.
8. **No path pattern is empty** — if a path in the manifest matches nothing (a typo, a folder
   renamed), the block silently shrinks, and the agent is not given half of its code.
9. **Coverage is complete** — no uncovered files.

---

## 5. How to cut the project into blocks

The main question of the whole undertaking, because what gets found depends on the split.
Three axes.

**Horizontal blocks — cross-cutting passes over one invariant.** "Authorisation",
"transactions and audit", "DB schema and migrations", "the contract between backend and
frontend", "clients' offline semantics", "concurrency", "internationalisation",
"observability", "infrastructure and build". Such a block reads a narrow set of "its own" files
in full, and walks the rest of the code selectively, looking for violations of its rule.

**Vertical blocks — slices by domain.** "Ticket lifecycle", "attachments", "notifications and
communications", "people and org structure", "analytics", "backups". Such a block reads its
domain in full: from the migration to the screen.

**Live-system blocks.** The API permissions matrix, scenarios by role, load and query plans, a
run of scanners. They own no files — they work against the running system.

Order: cross-cutting first, then vertical, then live-system. The reason — the cross-cutting
ones set the language: once the access-rights block has written out the full route table, the
vertical blocks read the code already knowing where the boundaries run.

**A trap we got burned on.** Blocks of the "live system" phase own no files, and the first
version of the tool decided that an empty path list meant "the whole repository". Coverage
came to 100% on the first run — fictitiously. An empty path list must mean the empty set.

**The second trap — ownership by directory.** If an entity's card is assembled from components
in one route folder, ownership by directory gives one block the whole interface: for us the
comment editor would have gone to the lists block, and the communications block would never
have opened it. Ownership had to be assigned by file, and the check "path pattern matched
nothing" added to `check`.

---

## 6. The block manifest

One file per block, `blocks/<ID>-<slug>.md`. Example — `example/manifest.example.md`. Four
parts:

**Why the block is needed** — one paragraph, in your own words.

**What counts as a finding and what does not** — the boundary matters more than the list.
Without it the agent brings stylistic nitpicks.

**10–15 hypotheses specific to the project.** Not "check security" but "a permission granted
in a migration via CROSS JOIN yields zero rows on a clean install, because migrations run
before seeds — check every resource/action pair". Hypotheses are the most valuable part: this
is where you put what you know about your own pitfalls. For us all 14 hypotheses of the
access-rights block were checked, and half of the findings came precisely from them.

**Acceptance criterion** — what the block must deliver besides findings for it to be closed.
For the access-rights block it was a full table of all routes with their gates and a
reconciliation table "migration ↔ seed". This is the strongest part of the construction: the
acceptance criterion cannot be met without reading the code. The verifier then rebuilds the
table mechanically and compares — for us it matched in all 321 rows, and that is the proof that
the hunter worked rather than retold.

---

## 7. Prompt templates

Three files in `prompts/`, placeholders are substituted (`{{BLOCK_ID}}`, `{{FILES}}`,
`{{MANIFEST}}`, `{{INVARIANTS}}` and others). What matters in them:

**To the hunter**: read every file in the list in full, not selectively; change nothing; a
finding must contain a concrete failure scenario (what data and actions → what wrong
behaviour), otherwise it is an opinion, not a finding; report honestly what was not done.

**A separate rule about "other people's" files.** The first version of the template forbade
filing findings on files read by another block. For a vertical slice that is right, for a
cross-cutting one it is exactly backwards: the access-rights block owns the router and the
roles model, but a missing ownership check lives in someone else's code. The rule was rewritten
around the block's **subject**: a missing access check in someone else's usecase is your
finding if your block is about access; a typo in a button in the same file is not.

**To the verifier**: the task is not to agree but to check; three verdicts; rejected findings
are kept with a reason; an independent pass of its own over the 3–5 riskiest places is
mandatory; the block's findings file is rewritten in full.

**To the fixer**: before every edit, make sure anew that the defect exists; no half-measures; a
regression test is mandatory, and **verify by reverting** that it goes red without the fix; run
the gates; do not commit — the lead session assembles the commit.

**One more small thing that spoiled the first run.** The verifier wrote the entire verification
protocol — a thousand characters — into the "what is wrong" field, and the findings summary
table stopped being a table. Now the length of that field is limited (220 characters), the
template says so, and `check` rejects a bloated title. Evidence goes into the report, that is
what the text is for.

---

## 8. Order of work on a block

```
make review-status                       # where we are and which block is next
make review-prompt BLOCK=H1 ROLE=hunter  # the full prompt for the hunter
```

1. **Hunter.** Launch an agent with this prompt. It writes the report and a draft of findings to
   disk. Move the block to `hunted`.
2. **Verifier.** `ROLE=verify`. Checks the findings, adds its own, rewrites the findings file.
   Move to `verified`.
3. **Acceptance.** Read both reports yourself. Compare against the acceptance criterion.
   Coverage incomplete — send the block back for a repeat pass, do not close it.
4. **Into the register.** `make review-import BLOCK=H1 && make review-findings`.
5. **Journal.** `review.py log H1 "what was decided and why"`.
6. **Commit.** As a separate commit. `git log -- docs/review` becomes the history of the work.
7. **Fixing.** `ROLE=fix`, by a separate agent. If there are many findings — split by groups of
   files so the agents do not get in each other's way, and tell each one explicitly which zone
   is not theirs.
8. **Fix review.** The diff is handed to verifying agents that did not write it. Only after that
   is the block closed and the MR opened.

On the number of agents: do not run more than two or three at once if CI is running on the
same machine — the processor is fully occupied.

---

## 9. What the first block taught (this is the most useful part)

**Green tests were not proof.** Twice a defect got past all the gates because **the test fake
behaved more leniently than the real system**: the database mock answered even on a cancelled
context, which the live driver never does; the permissions mock by default answered "sees
everything" where the real query answers "sees nothing". Hence a rule for the verifier: do not
believe that a test is green — check what exactly it asserts, and whether the fake is more
lenient than the original.

**A fix is verified by mutation, not by reading.** Our best verifier took every fix, broke it in
a temporary working copy and watched whether the new test went red. Six mutations — six reds.
That is the only way to know that a test really guards something.

**The pendulum.** A security fix closed too much, the next one restored access — and could
restore more than it should, i.e. reopen the closed leaks. On that round the verifier must be
asked exactly this question separately: has even one closed hole come back.

**The protection itself can be leaky.** We have six grep checks in the build that forbid
dangerous patterns, and an allowing comment next to the call lifts the ban. It turned out all
six were written so that the comment freed the **neighbouring** call, not its own: `grep -B 3`
glues nearby matches into one block. The hole was in the protection itself. The script that
fixes this class (matching by line number within the file) is in `example/guard-grep.sh`.

**A dead permission is worse than a missing one.** A checkbox "Close tickets" turned up that
had existed since the first migration and was checked nowhere. An administrator would untick
it to forbid — and nothing happened. Deleted, and along with it a test was added: every row of
the permissions catalogue must be mentioned in the code, otherwise a permission cannot exist
only in the interface.

---

## 10. How to set it up for yourself

1. Copy `review.py` into `scripts/review/`, the templates into `docs/review/prompts/`.
2. Write `docs/review/invariants.md` — the rules of **your own** project. This is the most
   important file: it is pasted to every agent, and what the agent counts as a defect depends
   on it. Our example (`example/invariants.example.md`) is worth looking at for the structure,
   not the content: it has a section "context that changes the assessment of findings" (for
   us — "no production, no legacy data, target scale such-and-such") and a section "what is
   NOT a finding".
3. Lay out the blocks in `blocks.json`. Start with horizontal, then vertical. Each has `paths`
   (ownership, counted into coverage) and `ref_paths` (context). Example — three blocks of
   different types in `example/blocks.example.json`.
4. Write the manifests. This is the longest part and it is worth it: a manifest without
   project-specific hypotheses gives a review "on general considerations".
5. `review.py init`, then `review.py coverage` — and deal with the uncovered files until there
   are zero. This is where everything forgotten surfaces.
6. Add the `make` targets and the banner in the project's root instructions file.
7. Run the first block in full and **do not be afraid to fix the rig along the way**: for us
   the first block produced six fixes to the tool, and all of them were needed.

What not to do: do not start with vertical blocks (they duplicate each other until the common
language is set); do not let one agent both search and fix; do not close a block whose
acceptance criterion is not met; do not leave findings only in the conversation.

---

## 11. How it ends

When all blocks are closed and there are no open findings in the register, **the `docs/review/`
directory is deleted in full in one MR**, and what is durable in it moves to where it really
lives: rules — into the root instructions file, architectural decisions — into ADRs, checks —
into tests and build gates.

This is not a formality. The project had already been burned by review documents whose status
tables nobody updated: they described long-fixed defects as open and misled everyone who opened
them. The review directory is the scaffolding around a building site, not part of the building.
