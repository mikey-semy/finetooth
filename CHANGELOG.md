[Русская версия](CHANGELOG.ru.md)

# Changelog

The format is [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), versions follow
[semantic versioning](https://semver.org/). While the major version is zero, the on-disk state
format may change: breaking changes are marked separately, and for each it is said what to do
with a review already under way.

## [Unreleased]

### Removed

- `docs/` and `ROADMAP.md` moved to the private knowledge base `finetooth-hq`: measurements, prior art, method comparison, token economy, the open-source plan and the roadmap. The public repository keeps what a user of the kit needs. The banner moved to `.github/banner.png`.

### Added

- Branch model: `master` for releases, `dev` for integration (default branch), feature branches from `dev`; CI runs on both.
- `RELEASING.md`: semantic versioning with a zero major, at most one release a week, four
  mechanical gates before a tag (tests with mutations, `skills-ref validate`, a run on a live
  project, a complete CHANGELOG), no direct pushes to `master` for anyone. Written after four
  releases in one day showed that the version number had stopped meaning anything.

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
[0.6.0]: https://github.com/mikey-semy/finetooth/compare/v0.5.0...v0.6.0
[0.4.0]: https://github.com/mikey-semy/finetooth/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/mikey-semy/finetooth/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/mikey-semy/finetooth/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/mikey-semy/finetooth/releases/tag/v0.1.0
