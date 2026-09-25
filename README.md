[Русская версия](README.ru.md)

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset=".github/logo-dark.png">
    <img src=".github/logo-light.png" alt="finetooth" width="360">
  </picture>
</p>

# finetooth — whole-repository code review by AI agents

[![tests](https://github.com/mikey-semy/finetooth/actions/workflows/tests.yml/badge.svg)](https://github.com/mikey-semy/finetooth/actions/workflows/tests.yml)
[![license: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Agent Skills](https://img.shields.io/badge/Agent%20Skills-SKILL.md-blue.svg)](https://agentskills.io)
Works in Claude Code, Codex, Gemini CLI, Cursor and any agent that reads the skills standard.

finetooth is an [Agent Skill](https://agentskills.io) that turns "review the whole project"
into work with a provable result. The repository is cut into blocks, every tracked file is
owned by exactly one block, every block carries numbered hypotheses that must each get a
verdict, and four roles — hunter, verifier, fixer, fix reviewer — work through it with all
state kept on disk in `docs/review/`, not in the chat. The tool is a single Python file on the
standard library, no dependencies.

```sh
npx skills add mikey-semy/finetooth
```

**Four roles, separate prompts.** The *hunter* reads the block's files and raises findings.
The *verifier* makes its own independent pass and gives each finding a verdict. The *fixer*
fixes, proves the fix with a test and runs the project's gates. The *fix reviewer* reads the
whole diff — someone who did not write it — before the pull request opens, not after the
merge.

**What makes it different from PR-review bots:**

- a **coverage map** (file → block) that is rebuilt by `coverage` and **fails** if a single
  tracked file is unowned — proof is "no unowned files", not "we looked at the important bits";
- **hypotheses with mandatory verdicts**: each block's manifest lists numbered questions about
  *this* project, and `check` refuses to close the block until every one is checked, not
  checked or marked not applicable;
- **fingerprints**: a block closed on one version of the code, or a finding whose code has
  moved, turns `check` red until someone re-stamps it;
- a **findings register in git** — every finding, status and decision lives in files under
  `docs/review/`, so the next session (or the next month) starts where the last one stopped;
- **guards from the third recurrence**: findings carry a root cause, and the third instance of
  the same root cannot be closed without a guard — a test, lint rule or CI check that keeps
  the class from coming back;
- **tests proven by mutations**: for every check the tool makes there is a change that breaks
  it and a test that goes red on that change.

**Language.** Docs, prompts and reports are available in English and Russian; see
[README.ru.md](README.ru.md).

The kit turns the request "review the project" into work with a provable result: the code
is cut into blocks, every file is assigned to a block, the state lives on disk rather than in
the conversation, and one agent hunts for defects, a second verifies them, a third fixes them,
and a fourth — one that did not write them — reads the fixes. The name comes from the idiom
*go through with a fine-tooth comb*: comb through without skipping a single file. Before
0.6.0 the kit was called review-kit.

The kit is **a skill under the open [Agent Skills](https://agentskills.io) standard**: it is
installed with one command, `npx skills add mikey-semy/finetooth`, and works in any agent that
reads the standard. The tool inside is a single file on the Python standard library, no
dependencies.

## Why it is needed

The request "review the project" does not work for three reasons, and each kills the result in
its own way.

**The context is shorter than the work.** Reviewing a large project takes dozens of hours and
many sessions. The window runs out, the history is compressed, and two days later the agent in
a new window starts from scratch.
→ Here not a single finding, status or decision lives in the dialogue: only in files.

**There is no way to prove completeness.** "I looked at the code" is a claim, not a fact. You
cannot tell whether a file was read, and especially whether there are files nobody read.
→ Here the `coverage` command rebuilds the file → block map and **fails** if even one tracked
file belongs to nobody. That is the proof: not "we looked at what matters" but "there are no
unowned files".

**Whoever hunts must not fix.** As soon as the model starts editing, it stops searching. And
the one who found the defect is the worst reviewer of their own fix: they check the very
thought they got wrong.
→ Here there are four roles with separate prompts — hunter, verifier, fixer, fix reviewer —
and a rule: the fix diff is read by agents who did not write it, **before** the pull request
opens, not after the merge. For the kit's author, the heaviest defect of the access block came
on the third round of fix review and had been in the project from the very beginning.

## Where it came from

The kit arrived ready-made: the archive `finetooth.zip` dated 16.09.2026. The author,
**[Georgiy Khudobandaev](https://github.com/Georgiy-Khudobandaev)**, is the founder of the
method: the kit was born on his large project, and the whole design came from there. The first
commit of this repository is that archive byte for byte, without a single change, so that
everything changed afterwards — and why — stays visible.

⚠️ **The archive carried no license.** Until 24.09.2026 the MIT in [`LICENSE`](LICENSE)
covered only the changes made here, and the repository stayed private: the author's
description and examples named internal details of his project, including the access-rights
defects found in it. Since then the author has granted full rights to the kit, both authors
are named in `LICENSE`, and everything that identified his project has been anonymised — see
[`NOTICE.md`](NOTICE.md).

**How it was created is the main thing in it.** The kit was not designed up front. It was
pulled out of one block that was really worked through: the author ran an access-rights review
on his project, rewrote the tool six times along the way and assembled the result into a kit.
That is why almost every rule in it is the trace of a specific mistake, not a general
consideration:

- **An empty list of paths meant "the whole repository".** Blocks that run against the live
  system own no files — and coverage came out at 100% on the first run, fictitiously. Now an
  empty list means an empty set.
- **Ownership by directory handed over someone else's files.** A comment editor sitting in the
  lists route folder would have gone to the lists block, and the communications block would
  never have opened it. Ownership is assigned per file, and "the path pattern matched nothing"
  is a separate check: otherwise a block silently shrinks and the agent is not given half of
  its code.
- **The verifier wrote the entire verification protocol into the finding's title**, a thousand
  characters of it, and the summary table stopped being a table. A 220-character limit and a
  check for it appeared.
- **A security fix passed every gate and broke what worked.** Lint clean, tests green,
  migrations valid — and the foreman stopped seeing his technicians' rounds. The cause is
  universal: all the new tests proved that an outsider no longer sees too much, and not one
  proved that an insider still sees their own. Hence the rule "a test is written in both
  directions" and an independent review of the diff before the merge.
- **The hole was in the protection itself.** Six grep gates in the build forbade dangerous
  calls, and an allowing comment next to a call lifted the ban — and all six were written so
  that the comment freed the **neighbouring** call: `grep -B 3` glues nearby matches into one
  block. The engine that matches a finding to its allowance by line number lives in
  `skills/finetooth/assets/guard-grep.sh`.
- **A dead permission is worse than a missing one.** A checkbox "Close requests" turned up
  that had existed since the first migration and was checked nowhere: the administrator
  unticked it to forbid, and nothing happened.

The author's full description is `how-it-works` (in the knowledge base), Georgiy's
text, given as is. The numbers in it are the author's account; we have not verified them.
Everything marked as verified below has been verified by running it here.

## What was broken in the kit

The kit was sent as working, and it is — but installing it by its own instructions stumbles.
Everything listed was reproduced on a clean repository, not spotted by eye.

| What | What it turns into |
|---|---|
| `example/makefile-snippet.mk` contains not review targets but pieces of SAST targets from another project | **not one** `make review-*` command from the documentation exists; installation is done blind |
| the documentation calls `prompt BLOCK ROLE` | the tool requires `prompt BLOCK --role`; the command from the instructions answers `unrecognized arguments` |
| `check` requires a manifest for **all** blocks at once | a manifest is written before its own block, so the check is red from day one — and people start ignoring it |
| a block closes with only a hunter's report | `set-status H1 closed` passes without a verifier's report: unverified findings disappear from the remaining work, the check is green |
| a stale `coverage.tsv` is not caught | the map on disk diverges from the recount, and the consumer reads yesterday's ownership without knowing it |
| no block size ceiling | a block that physically cannot be read in one session reports coverage that never happened |
| no command to move a finding | the README demands "edited only by the tool" and "set `fixed` and the commit", and there is no command for it — the register is edited by hand |
| the rejection reason is demanded by nothing | the review's completion condition requires a reason for every rejected finding, nothing checks it, the field stays empty |
| the repository root is "two directories above the file" | a tool placed anywhere other than `scripts/review/` does not fail but silently looks for state in the wrong place and starts a second set |
| a coverage failure prints only a list of paths | a human appends the file to the first block at hand, and it counts as read without having been read |

Separately — installation pitfalls, not the author's but ours, from another language and
another keyboard layout:

- **`[handle]` in a git pathspec is a character class.** The pattern
  `src/app/[handle]/[slug]/edit/**` matches nothing: the glob reads the brackets as "one of
  the characters h,a,n,d,l,e". A directory without `**` works. The "pattern matched nothing"
  check catches this — without it 46 files would have stayed unowned unnoticed.
- **`exclusions` is a list of objects** `{pattern, reason}`, not strings. A list of strings
  crashes `coverage` with `TypeError`.

## What is fixed in this version

Some changes were road-tested on a live review (67 blocks, 1691 files, three blocks
completed), some were added here and proven by mutation — break the state and make sure the
check goes red.

**Road-tested on a live review:**
- `check` requires a **verifier's** report for a block in status `verified`/`closed`;
- `check` compares `coverage.tsv` with a recount — a stale map no longer stays silent;
- a manifest is asked of only the block that has reached work, not all at once;
- a block readability ceiling: 6000 lines, exclusions are **not** counted (otherwise the
  ceiling measures `package-lock.json`, not the code the agent will read);
- a coverage failure says what to do and why the choice is made by a human, not by a pattern;
- the hunter's report must contain a **file-by-file list** of what was read: without it the
  report cannot be told from a retelling. In a neighbouring project this is exactly what
  exposed padding — 15 blocks out of 26 counted as reviewed, and 56 files were never named
  once.

**Taken from neighbours in the niche** (analysis in `comparison-with-practice` (in the knowledge base)):
- **a fingerprint of what was reviewed** — from [doorstop](https://github.com/doorstop-dev/doorstop),
  where a requirement stores a hash of its text and an edit itself moves it to "unreviewed
  changes". Here: on moving to `verified`/`closed` a block remembers a fingerprint of the
  composition and contents of its files, and `check` catches a block closed on a different
  version of the code. To confirm that the changes were reviewed — `restamp <BLOCK>`, exactly
  like `doorstop review`. A block or finding without a fingerprint (recorded by a kit version
  that had none) is also a failure, not a skip: `backfill` stamps fingerprints from the current
  code and writes to the journal from which commit changes are tracked;
  The same fingerprint is taken of the manifest's hypothesis text: verdicts are given by
  number, and reordering or replacing a question after verification would otherwise credit
  the old answers to the new one;
- **a fingerprint of the code under a finding** — from the same place (suspect links) and from
  [claude-review-all](https://github.com/ncoevoet/claude-review-all), where a finding's key
  includes a hash of the code. Here: an open finding whose code has moved fails the check —
  either it has already been fixed, or the description is stale, or the defect is still there
  and `restamp <finding-ID>` confirms it;
- **a cheap fabrication filter** — from [mergejury](https://github.com/iamEtornam/mergejury):
  a reference to a line that does not exist in the file is caught without any model;
- **a budget inside the assignment itself** — from [repomix](https://github.com/yamadashy/repomix)
  (exceeding it fails the build) and [ai-digest](https://github.com/khromov/ai-digest) (what
  did not fit stays in the output as a stub — path visible, contents absent). Here the prompt
  prints the block's size and, if it is larger than what can be read in a session, shows
  **where the boundary runs**: files in descending order of size with a running total and a
  mark of what is over the line. Not a ban on reading — an obligation to name what was not
  read;
- **from a class to a rule** — the variant-analysis mechanic at Trail of Bits, where a rule is
  written from a finding and run across the whole codebase. Here: a finding carries a `root`
  (the class name), and from the **third** instance the check requires a guard —
  `set-finding <ID>... <status> --rule <path>`, recorded only on the findings named in the
  command (a root string can carry defects that need different guards). A
  guard is a path to a file in the repository (a test, a linter config, a CI gate) or
  `repository:path` for a neighbouring one; a non-existent path is a failure. The threshold
  comes from practice: a second recurrence can still be a coincidence, a third means the
  defect is produced by the structure of the code. The `roots` command shows the classes, the
  number of instances and which guard each instance carries, and flags a class whose
  instances disagree or where some carry none; `check` warns about the latter.

**Added after checking against world practice** (see `comparison-with-practice` (in the knowledge base)):
- **a second coverage denominator — hypotheses.** The file map answers "the file was opened";
  a professional audit counts coverage in questions asked of the system, and OWASP ASVS
  requires every requirement to have a "pass or fail" outcome and a written justification of
  non-applicability. The manifest's hypotheses are numbered in order, each is closed with a
  verdict "checked / not checked / not applicable", `check` requires a verdict for all of
  them, `hypotheses <BLOCK>` shows what is closed and what is hanging;
- **a mandatory "Coverage limits" section** in the hunter's report: completeness is proven by
  listing what was not reviewed — in audit firms' reports this is a separate chapter;
- **the coverage map is compared against a recount**, not against a signature: without this
  the figure "1691 of 1691 covered" stays true-looking when the repository has already moved
  on. At first the map named the commit in its header — but a commit name proves nothing
  (there is nothing to compare it against, and a matching line of history does not mean a
  matching composition), so the code version is pinned by the fingerprints of blocks and
  findings, and the map is compared with a fresh recount line by line;
- the verifier's prompt requires verification **by execution**, not by re-reading, and defines
  a duplicate through the root: "if fixing the root makes the second finding cease to exist";
- the fixer's prompt requires closing the **class** of defect with a guard, not a list of
  places.

**Added during the transfer:**
- the repository root is asked of git — the tool can be placed wherever convenient;
- the project name and gates became the substitutions `{{PROJECT}}` and `{{GATES}}` from
  `blocks.json`: a template copied without proofreading greeted the agent in the name of
  someone else's project;
- the command `set-finding <ID> <status>` — moves a finding and refuses `fixed` without a
  commit, `rejected` without a reason, `duplicate` without a reference;
- `check` requires a rejection reason for every rejected finding;
- the hints in messages are gathered into one constant, `CLI` (in the original half of them
  called `make`, half `npm run` — the rig was carried between projects and never proofread);
- the `make` targets snippet finally contains review targets, and next to it lies the same
  list for `package.json` (both in `skills/finetooth/assets/`).

**Taken from the second version of the kit by its author** (handed over 23.09.2026, developed
in parallel; the mechanisms were carried over, the texts rewritten, his project's data was not
carried over — details in [`CHANGELOG.md`](CHANGELOG.md), 0.5.0):
- **the fix reviewer role** — the diff is pasted into the prompt whole, rounds and halves of
  the diff get their own report names, and at the end an explicit verdict "is another round
  needed"; a block with fixed findings cannot be closed without such a report;
- **a block's proof kind** — `read` (every file read) or `measured` (test quality,
  performance, scanners: the proof is the manifest's artifacts, not reading); the prompt's
  first rule is derived from it, a block without `paths` is a live system;
- **the gate "every file of a readable block is named by full path in at least one report"** —
  "read 25 of 25" turned out to be the agent's own word: it named five, and a top-up found
  11 more defects;
- the commands `inventory` (the repository tree for cutting) and `sizes` (blocks against the
  ceiling), `coverage --no-write` for gates in CI;
- **five defects of our copy** that his tool already refused: a fixed finding on a deleted
  file, a deferred one without a reason, phases out of order, "review finished" with a
  blocked block, the `running` time from the first start;
- `references/lessons.md` — 42 lessons from two reviews with the stories of where each came
  from.

## Tests

```sh
python3 -m unittest discover -s tests
```

384 scenarios, about nine minutes, no dependencies other than `git`. Each one creates a fresh temporary
repository and calls the tool **from the skill folder**, with the working directory in that
repository — the way the agent calls it. Behaviour is checked through the command line, not by
importing internals. A separate class checks the skill itself against the specification: the
name equals the directory, the description is within limits, the links from `SKILL.md` lead to
existing files, the version in the header equals the tool's version. In CI this is joined by
`skills-ref validate` — the validator from the standard's repository.

The tests are proven by mutation: for every check the tool makes there is a change that breaks
it and a test that goes red on that change.

## How to install

The kit is **a skill under the open [Agent Skills](https://agentskills.io) standard**: it is
read by Claude Code, Codex, Gemini CLI, Cursor and other agents. It is installed with the
standard installer:

```sh
npx skills add mikey-semy/finetooth                   # into the project: .claude/skills/finetooth/ and the like
npx skills add mikey-semy/finetooth -g                # into the home directory, for all projects
```

The agent finds the skill on its own — by the description, when asked for a whole-repository
review or when the repository already has `docs/review/`. The tool runs from the skill folder
and reviews the repository it was started in.

**Install into the project, not only into the home directory**, if CI runs the check: a copy
of the skill in the repository pins the tool's version to the commit, and `check` in CI runs
with exactly the version the review was done with. A skill installed into the project is
committed along with it.

The project is maintained by one person, and PRs are looked at roughly once a week; how to
contribute — [`CONTRIBUTING.md`](CONTRIBUTING.md), origin and rights — [`NOTICE.md`](NOTICE.md).

Then, in the project root:

```sh
python3 .claude/skills/finetooth/scripts/review.py setup --project "Name"
```

`setup` creates a skeleton of the block definitions, the invariants and the entry point
`docs/review/README.md`. The tool itself and the role templates are **not copied** into the
project — they are in the skill. A project that calls the tool its own way passes
`--cli "npm run review --"`: the string is written to the `cli` field in `blocks.json` and
goes into all hints. Without it the hints name the real path to the tool. A repeated run adds
what is missing and does not touch what was edited by hand.

Next comes the work nobody will do for you:

1. **`docs/review/invariants.md` — the rules of your project.** The most important file: it
   is pasted to every agent and decides what the agent will count as a defect. The sample in
   `assets/invariants.example.md` is someone else's — look at it for the structure, not the
   content: it has a section "context that changes the assessment of findings" and a section
   "what is NOT a finding".
2. Lay out the blocks in `docs/review/blocks.json` — cross-cutting first, domain next,
   live-system last (`assets/blocks.example.json`). Fill in `project` and `gates`.
3. Write the first block's manifest: 10–15 hypotheses **about your project** and an acceptance
   criterion that cannot be met without reading the code. The longest part, and it cannot be
   cut short: a manifest without project-specific hypotheses gives a review "on general
   considerations".
4. `inventory` — the repository tree with sizes and ownership, to cut by; `init`, then
   `coverage` — and deal with the unowned files until there are zero. This is where
   everything forgotten surfaces: for the author — a whole microservice, for us — 89 route
   files. `sizes` shows the blocks above the ceiling — split them by subject, not
   alphabetically.
5. Add the `make` targets (or `package.json` scripts) and the banner to the project's root
   instructions file — without the banner a new session will not know the review is in
   progress and will start its own in parallel.
6. Run the first block all the way through and **do not be afraid to adjust the rig as you
   go**. Put your own version of a role template in `docs/review/prompts/<role>.md` — it is
   used instead of the skill's.

## What it costs

Full measurements with the method and caveats are in `measurements` (in the knowledge base).
In short, from the review journal:

| block | outcome | spend |
|---|---|---|
| access and visibility, 58 files / 4017 lines | 12 findings | 2 agents, 576k tokens, ~35 min |
| domain core, 13 files | 14 findings | 2 agents, 446k tokens, ~34 min |
| writes and versions, 42 files | 17 findings | 2 agents, 679k tokens, ~48 min |

A block with nothing to fix closes with two agents. What is expensive is not the search but
the fix rounds: for the author, fixing one block went through three rounds of "fixed → the
diff was read" — 26 findings, then 13, then 8, then four trifles and the verdict "safe to
merge". By our estimate such a block costs about twelve agents against two for a survey one.
Convergence is the only honest sign that it is time to stop — the stopping rule is set in
advance, and not by the number of findings but by their kind.

## Where it is going

The detailed roadmap — with measurements, sources and the order of work — lives in the
maintainer's knowledge base; this is the short version. Directions, roughly in order:

- **A fix-phase gate.** The next block does not start while the previous one has open
  high-severity findings; deferring needs a reason. The method finds faster than a project
  fixes — this is the lever.
- **Seams between blocks.** A `coupling` command over `git log`: files that change together
  but live in different blocks become `ref_paths` and hypotheses; clusters become a
  cross-block slice.
- **Order by risk, then by churn.** A command that ranks blocks by cost of failure first and
  change frequency second.
- **Measuring what is missed.** A corpus of real past defects with a known answer; cheap
  sampling of closed blocks by a different model as an upper bound.
- **A lens bank.** Property question sets (access, money, privacy, data integrity,
  reliability, tests, documentation truth) as sources of hypotheses for manifests — in the
  form "what to check → how to prove it", never as a checklist.
- **Threat model as a block kind.** A textual data-flow diagram per trust boundary with STRIDE
  hypotheses; the diagram outlives the review directory.
- **Token economy.** The cost of a block does not depend on its size, so the spend goes to
  tool output and re-reads: measure first, then cache TTL, output filtering, one-read rule.
- **The summary that outlives the review directory**, a run manifest, two reviewers at once,
  a block spanning two repositories, portability to another language.

What we will not do: turn the kit into a diff reviewer, add dependencies, build a web UI or a
database, automate finding without a human accepting each one, reward being first. Each has
a reason in the knowledge base.

## What not to do

Briefly, on the near term: the method's main blind spot is **how much it misses**. We know
that what it finds is real (6 planted findings out of 6 rejected), and we do not know what
share of what exists that is.


- do not start with domain blocks: until the cross-cutting ones have set the language, they
  duplicate each other;
- do not let one agent both hunt and fix;
- do not close a block whose acceptance criterion is not met;
- do not leave findings only in the conversation;
- do not keep more than two or three agents at once if a build is running on the same
  machine.

## What is inside

```
skills/finetooth/                THE SKILL — this is what gets installed into the agent
  SKILL.md                        when to apply and the order of work (read by the agent)
  LICENSE                         terms — travel with the skill
  scripts/review.py               the tool, 23 commands: version, setup, init, status, next,
                                  inventory, sizes, coverage, coupling, order, roots, prompt,
                                  import, set-status, set-finding, hypotheses, restamp,
                                  backfill, refs, findings, summary, check, log
  scripts/axes.py                 the spend of a headless run, broken down by axis
  references/hunter.md            hunter: reads the block's files and raises findings
  references/verify.md            verifier: its own independent pass, three verdicts
  references/fix.md               fixer: fixes, proves with a test, runs the gates
  references/fixreview.md         fix reviewer: reads the whole diff, rounds, verdict on the next one
  references/lessons.md           lessons from two reviews, from which the rules grew
  references/*.ru.md              the same five in Russian — hunter.ru.md, verify.ru.md,
                                  fix.ru.md, fixreview.ru.md, lessons.ru.md; `lang` in
                                  blocks.json picks the language of the pair
  assets/entry-point.md           template of docs/review/README.md for the project
  assets/blocks.example.json      three blocks of different kinds + exclusions with justification
  assets/manifest.example.md      block manifest: hypotheses and acceptance criterion
  assets/invariants.example.md    someone else's invariants — as a sample of the structure
  assets/journal.example.md       header of the decisions journal
  assets/agent-banner.md          banner for the project's root instructions file
  assets/*.ru.md                  the Russian copies of those five — entry-point.ru.md,
                                  manifest.example.ru.md, invariants.example.ru.md,
                                  journal.example.ru.md, agent-banner.ru.md
  assets/makefile-snippet.mk      make targets
  assets/package-json-snippet.json the same for an npm project
  assets/guard-grep.sh            grep-gate engine: allowance by line number
  assets/run-role.sh              runs a role headless through `claude -p` and writes the
                                  spend to the journal — the one part that leaves the machine
tests/test_review.py              tests of the tool and the skill format: 384 scenarios
examples/toy                      a real docs/review/ after one block, on a toy app
.github/                          CI (tests on 3.12 and 3.14, skills-ref validate, the DCO
                                  check), issue and PR templates, the logo
README.md, README.ru.md           this file and its Russian copy
AGENTS.md                         rules for whoever edits the kit itself
CLAUDE.md                         points the agent at AGENTS.md — one source, two names
CONTRIBUTING.md                   how to contribute: DCO, test + mutation, no dependencies
RELEASING.md                      how versions are numbered and what a release must prove
NOTICE.md                         origin and rights: two authors, consent to MIT
SECURITY.md                       what the kit writes and sends, and how to report a hole
LICENSE                           MIT, two copyright holders
CODE_OF_CONDUCT.md                Contributor Covenant 2.1 (+ CODE_OF_CONDUCT.ru.md)
CHANGELOG.md                      version history (+ CHANGELOG.ru.md)
.gitignore                        the tool's bytecode must not reach a commit
```

Block statuses: `todo → running → hunted → verified → triaged → fixing → closed` (plus
`blocked`). Finding statuses: `open`, `fixed`, `rejected`, `duplicate`, `deferred`.

**Seams between blocks.** A block is the unit inside which an agent sees everything; the seam
between two blocks is seen by nobody. On the first project 76% of the file pairs that change
together sit in different blocks. `review coupling` reads `git log`, drops mass commits and
shared nodes, and prints the cross-block pairs with a ready `ref_paths` entry and a hypothesis
for the manifest; clusters of pairs between the same two blocks are where a seam block is due.
`--write` keeps the pairs in `docs/review/coupling.tsv`. Both cutoffs are derived from the
repository rather than fixed, and the run prints the ones it used: a commit is a mass commit
above the 95th percentile of files per commit **here** — or, on a history of fewer than twenty
commits, where the percentile cannot separate anything, above Tukey's fence; a file is a
shared node when it is coupled with a tenth of the review's blocks, never fewer than three
(a seam runs between two, so a third means it no longer describes one seam).

**What a run costs, measured.** `assets/run-role.sh <ID> <role>` runs a role headless through
`claude -p`, keeps the event stream and writes one line to the journal: turns, tool calls,
input tokens and the share from cache, output, re-reads. `scripts/axes.py` breaks any such
stream down by axis. The first measured block: the cost is **turns × context** — reading the
block whole was 1% of the spend; the verifier's 118 shell calls were most of the rest. The role
templates now say so (one file — one read; the stand is one script, run once), and the runner
caps turns at twice what the measured run needed.

**What outlives the review directory.** The method ends by deleting its own directory — a
register nobody updates describes fixed things as open. `review summary` writes one immutable
file outside it: the date and the **base commit**, the blocks with their acceptance criteria and
fingerprints, the rejected findings with reasons (so the next review does not find them again),
the accepted risks, and what closed each class (guards, commits). `review summary --aged <file>`
answers, from `git log` alone, how far each block has drifted since that commit — an auditor's
re-test starts from there, not from zero.

**Order of walking.** `review order` ranks the blocks by the cost of failure first (`risk` on
the block) and by change frequency second — measured on the first project as a prediction:
the top 10% of files by change frequency collected 34% of the later fixes, by size 29%, at
random 6% (Nagappan & Ball 2005; Moser et al. 2008). Frequency catches defects; the cost of
failure catches irreversibility, so it stays the first key. The command reports; the order in
`blocks.json` is the human's.

**The fix gate.** The method finds faster than a project fixes (the first project: 77 findings
on 5 blocks, 9 fixed), and a finding that never reaches a fix is debt — a month later the
register describes code that no longer exists. So `set-status <ID> running` refuses while
findings at `fix_gate` severity or above (`high` by default; `"fix_gate": "none"` in
`blocks.json` switches it off) are open in the blocks already passed. The way out is to fix,
defer with a reason or reject — never to ignore. `status` prints the debt as its own line, and
`check` warns about open findings older than a week.
