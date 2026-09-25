# T4 — hunter report

## Coverage

- files read: 21 of 21 (plus the context file `skills/finetooth/SKILL.md`, read in its
  frontmatter and header only — see Coverage limits)

The list of files read, by name:

- `.github/ISSUE_TEMPLATE/bug.yml`
- `.github/ISSUE_TEMPLATE/config.yml`
- `.github/ISSUE_TEMPLATE/proposal.yml`
- `.github/ISSUE_TEMPLATE/trophy.yml`
- `.github/PULL_REQUEST_TEMPLATE.md`
- `.github/workflows/stale.yml`
- `.github/workflows/tests.yml`
- `.gitignore`
- `AGENTS.md`
- `CHANGELOG.md`
- `CHANGELOG.ru.md`
- `CLAUDE.md`
- `CODE_OF_CONDUCT.md`
- `CODE_OF_CONDUCT.ru.md`
- `CONTRIBUTING.md`
- `LICENSE`
- `NOTICE.md`
- `README.md`
- `README.ru.md`
- `RELEASING.md`
- `SECURITY.md`

Read whole in one call each; `CHANGELOG.ru.md` in two calls (579 lines, over the single-read
cap) — lines 1–455 and 455–579, so the whole file.

Files outside the block opened to check a claim against its source (not part of my coverage,
read in part): `skills/finetooth/SKILL.md` (frontmatter + header), `skills/finetooth/scripts/review.py`
(the constants, `coupling`, `summary`, the write sites, the argparse table),
`skills/finetooth/assets/run-role.sh` (whole), `tests/test_review.py` (the class and test-method
index), `docs/review/findings.jsonl` (statuses and counts), `docs/review/README.md`.

- not read: none.

## Hypotheses

T4.1 — checked: every entry of the Unreleased section was matched against the code it names. The
totals hold (68 findings in the register = the "68 findings" of `CHANGELOG.md:15`; 7 fix-review
report files on disk = "seven rounds"), and no entry describes the reverted round-6/7 verdict
rules — the parser entry (`CHANGELOG.md:19`) states outright that it stays at the round-3 rules
and names issue #17. One entry does contradict a later fix in the same section: the `coupling`
entry still gives the shared-node threshold as a fixed `≥ 6 blocks` (T4-006).

T4.2 — checked: each README-named command, flag, default and number was run down in
`skills/finetooth/scripts/review.py` and `assets/run-role.sh`. Correct: `coupling` support
(`COUPLING_MIN_TOGETHER = 3`) and confidence (`COUPLING_MIN_SHARE = 0.5`), `order`'s two keys
(risk then commit frequency), `summary --aged`, `fix_gate` default `high` with `"none"` to switch
it off, `run-role.sh` caps 110/330 against the measured 55/165, the 6000-line ceiling,
`coverage --no-write`, the status vocabularies. Wrong: the shared-node threshold (T4-005). Absent
from the README in both languages: the `refs` command (T4-012).

T4.3 — checked: the two CHANGELOGs are entry-for-entry equal in the Unreleased section (14 Added,
5 Breaking, 1 Removed, the same Fixed groups) and carry the same numbers throughout; both are
missing the same two compare links (T4-008) and both carry the same stale hub threshold (T4-006).
The READMEs diverge: `README.md:28-52` holds three blocks of substance with no counterpart in
`README.ru.md` (T4-011), and the shared numbers (67 blocks / 1691 files, 576k/446k/679k tokens,
76%, 34/29/6%, 77 findings / 9 fixed, 6 of 6 planted) all agree.

T4.4 — checked, and a rule is indeed unenforced: `.github/workflows/tests.yml` runs exactly what
CONTRIBUTING's "Before a PR" names (`unittest discover -s tests`, `skills-ref validate
skills/finetooth`), on push to `master`/`dev` and on every pull request, matching the branch-model
entry. But the DCO that CONTRIBUTING makes mandatory has no check anywhere (T4-010), and
`actions/checkout` is the one action taken by a mutable tag while its neighbour is pinned by
commit (T4-014). Branch protection itself I could not read (see Coverage limits).

T4.5 — checked, and the promise is false as written: `summary` with no arguments writes
`docs/review-summary.md` (`review.py:1271`, `1417-1421`), and `assets/run-role.sh:25-28` writes the
assembled prompt and the whole event stream into `$TMPDIR/finetooth-runs`. `SECURITY.md:3,15`
names neither, and its "sends nothing over the network" does not survive `run-role.sh:38` calling
`claude -p` (T4-003).

T4.6 — checked, and a live project's identifiers are published: `CHANGELOG.md:40` and
`CHANGELOG.ru.md:40` name `setfork H3` and the internal path `curation/adapter.ts`, against the
promise in `NOTICE.md:31`; the same path is also in `review.py:2636` and `tests/test_review.py:788,794`
(T4-002). I found no trace of the *other* author's project ("H5.12", the register rows) in any of
the 21 files: the "26 such rows in 15 unstarted blocks" of `CHANGELOG.md:87` is a count with no
identifier, which the NOTICE does allow.

T4.7 — checked: RELEASING's rules are consistent with the history it was written after (the four
releases of 24.09.2026 predate it, and the CHANGELOG says so), but the file oversells its own
enforcement — "Gates — all mechanical" is untrue of gates 1, 3 and 4, and the file itself says
gate 3 cannot be automated (T4-009). The cadence rule ("at most one release a week") is stated as
cadence, not as a gate, so it is not a defect; the consequence of nothing being mechanical is
already visible in the two missing compare links (T4-008). The version-bump step names paths that
do not exist (T4-013).

## Tree freshness

`git fetch` ran clean; `git log HEAD..origin/dev --oneline` is empty — the working tree is at
`origin/dev`'s tip, `2e7c39f` (2026-09-25), with only `docs/review/state.json` modified. Every
finding below was read at that revision, and each claim was checked against the code in this same
tree (`skills/finetooth/scripts/review.py` at `VERSION = "0.7.0"`), not against a remembered
version.

## Coverage limits

What I deliberately did not do, and what I could not do:

- **GitHub-side settings are unreadable from here.** Branch protection on `master` (RELEASING:37
  "Nobody pushes to it directly", CHANGELOG 0.7.0 "protection of the `master` branch by green CI"),
  the required-status-check list, whether Discussions is enabled for the URL in
  `ISSUE_TEMPLATE/config.yml`, whether a DCO GitHub App is installed outside the workflows
  directory, and whether the `v0.5.0`/`v0.5.1` tags exist. This session has no network and no `gh`
  auth. So hypothesis T4.4's "branch protection requires the check" is answered only for what is
  in the repository; T4-010 is filed on the absence of any in-repo mechanism, which is what I can
  see.
- **The test suite was not executed.** `python3 -m unittest discover -s tests` needs an approval
  this non-interactive session cannot get. The count in T4-004 is therefore static: 248 methods
  named `def test_` at class-body indentation, across 17 classes all deriving directly from
  `unittest.TestCase` (no mixin that would multiply or suppress them). The real `Ran N tests` line
  may differ from 248 by a few; it cannot plausibly be 98.
- **`skills-ref validate` was not run**, and I did not audit the skill against the Agent Skills
  specification — that is T2's subject. T4-001 is filed on the *content* of one frontmatter field
  contradicting `LICENSE`/`NOTICE.md`, not on the field's format.
- **Prose of the role templates, the lessons file and the assets** — not read. T2 owns them; where
  a repository-contract promise touches them (the `--rule`/journal wording) I took the CHANGELOG's
  word.
- **Outbound links were not resolved.** Every URL in the READMEs, the CHANGELOG's compare links,
  `agentskills.io`, the doorstop/mergejury/repomix references, the Contributor Covenant anchors —
  none were fetched. A dead or redirecting link would not have been noticed. The two missing
  compare links (T4-008) were found by reading the footer, not by resolving the others.
- **Measurements taken on faith.** Everything the README attributes to the author's projects (67
  blocks / 1691 files, the three spend rows, 76% of co-changing pairs, 34/29/6%, "587 findings" in
  0.2.0) cannot be reproduced here, and the README itself says the author's numbers were not
  verified. I checked only that the numbers agree between the two languages and with the
  CHANGELOG; I did not try to verify them.
- **The CHANGELOG's history before Unreleased** was read for contradictions with today's tree, but
  I did not treat a released section's reference to a file since deleted (`docs/open-source.md`,
  `docs/review-methods.md`, `ROADMAP.ru.md`) as a defect: a changelog describes the tree as it was.
  Only live guidance pointing at deleted files is filed (T4-007).
- **`examples/toy` and `docs/review/`** are not in my block; I read `docs/review/findings.jsonl`
  and `docs/review/README.md` only to check the CHANGELOG's totals.

## Findings

### T4-001 · medium · The installed skill still says the base code has no license
**Location:** `skills/finetooth/SKILL.md:4`
**What is wrong:** the frontmatter reads `license: MIT for the additions; the base was handed over
by its author without a license — full terms in LICENSE`. That is the pre-0.7.0 position. `LICENSE`
is now plain MIT with both holders, `NOTICE.md:20-27` records the 24.09.2026 grant of full rights,
`CHANGELOG.md:116-119` says the licence appendix was *removed* from `LICENSE`, and `README.md:98-103`
describes the boundary as history ("Until 24.09.2026 …").
**Failure scenario:** a team runs `npx skills add mikey-semy/finetooth` into a company repository;
the installed copy's `SKILL.md` is the one file their reviewer reads, and it states that part of the
kit was handed over without a licence. Legal review blocks the install, or the field is copied into
an inventory of third-party components as "licence unclear" — while `LICENSE`, three files away,
says MIT and names both rights holders. The tests pin the skill's `LICENSE` *file* to the root one
and the version string to `VERSION`, so nothing goes red on this field.
**Why it is a defect:** the repository's own rights statement (`NOTICE.md`, `LICENSE`) is
contradicted by the copy that actually travels to users; invariant "the `LICENSE` inside the skill
equals the root one" is met in the file and broken in the metadata.
**Confidence:** confirmed

### T4-002 · medium · A reviewed project's name and an internal path are published, against NOTICE
**Location:** `CHANGELOG.md:40`
**What is wrong:** `NOTICE.md:31` promises that "the names of the projects the method was
road-tested on, their internal details and the defects found are not published". `CHANGELOG.md:40`
and `CHANGELOG.ru.md:40` name the project and the block — "the first live block on the skill
(setfork H3)" — together with one of its source paths, `curation/adapter.ts`. The same path is in
`skills/finetooth/scripts/review.py:2636` and `tests/test_review.py:788,794`, so it also ships
inside the skill.
**Failure scenario:** a project owner lets the kit be run on a closed repository on the strength of
the NOTICE paragraph. The next release's CHANGELOG names the repository, the block id of the pass,
and a file inside it. Unlike `docs/review/`, the CHANGELOG is never deleted — it is the file the
review is designed to leave behind — so the disclosure is permanent, and `review.py`'s copy is
distributed to every project that installs the skill.
**Why it is a defect:** the block's own rule — private data that the NOTICE says is anonymised.
Two whole releases (0.4.1, 0.5.1) were spent removing exactly this class from examples and lessons;
the same class re-entered through the CHANGELOG and the tool's docstrings, which is why it needs a
guard rather than four edits.
**Confidence:** confirmed
**Root:** a live project's identifiers reach a public file (4 addresses today: `CHANGELOG.md:40`,
`CHANGELOG.ru.md:40`, `review.py:2636`, `tests/test_review.py:788,794`)

### T4-003 · medium · SECURITY.md's boundary is narrower than what the kit actually does
**Location:** `SECURITY.md:3`
**What is wrong:** the file states that the tool "reads the repository through `git`, writes to
`docs/review/` and sends nothing over the network", and then defines a vulnerability as "the tool
writes outside `docs/review/`". Both halves are untrue of shipped components. `summary` with **no
arguments** writes `docs/review-summary.md` (`review.py:1271` `SUMMARY_DEFAULT`, written at
`1417-1421`, parent directories created), and `--out` accepts any absolute path.
`skills/finetooth/assets/run-role.sh:25-28` writes the assembled prompt and the full event stream
into `$TMPDIR/finetooth-runs`, and line 38 runs `claude -p` — a network call carrying the block's
file contents.
**Failure scenario:** a user audits the kit before running it on a closed codebase, runs
`review summary`, and finds a file written outside the only directory SECURITY.md permits. By the
document's own definition that is a vulnerability, so it is reported through the private channel
and consumes the one-week triage window the single maintainer promises — for documented,
intended behaviour. The reverse is worse: a user who trusts "sends nothing over the network" and
"writes to `docs/review/`" runs `assets/run-role.sh` on a shared build machine and leaves the
prompt (which embeds the reviewed source) and the whole event stream readable in `$TMPDIR` after
the run, with no line in SECURITY.md that would have warned them.
**Why it is a defect:** invariant 7 — only `docs/review/` is written, plus what the user explicitly
asked for — is stated in the private invariants with `summary --out` as the named exception, and
the public SECURITY.md carries neither the exception nor the `$TMPDIR` write nor the network call.
A security boundary that is false in both directions cannot be the basis for a vulnerability report.
**Confidence:** confirmed

### T4-004 · low · README and AGENTS.md give the test count as 98; there are about 248
**Location:** `README.md:281`
**What is wrong:** "Ninety-eight scenarios, no dependencies other than `git`" (`README.md:281`,
`README.ru.md:228`, and the tree line `README.md:438` / `README.ru.md:377`), and "98 scenarios,
about a minute" in `AGENTS.md:68`. `tests/test_review.py` defines 248 test methods across 17
`unittest.TestCase` classes, none inherited. The figure tracked reality through 0.1.0 (25), 0.3.0
(67) and 0.4.0 (76) and stopped being updated after that.
**Failure scenario:** a contributor follows `AGENTS.md`'s "Check before committing", sees the runner
report roughly 250 tests instead of the 98 the file promises, and cannot tell whether they are
running the right suite, whether their checkout is wrong, or whether the document is. The same
number is the README's public evidence for the claim "tests proven by mutation": a reader who
counts gets a different answer than the claim, which devalues the numbers around it that *are*
measured.
**Why it is a defect:** AGENTS.md rule 4 and CONTRIBUTING's "numbers come from measurement" — a
published count that disagrees with its source.
**Confidence:** confirmed
**Root:** a number in a public document not checked against its source

### T4-005 · low · README states the coupling shared-node threshold as a fixed 6; the code derives it
**Location:** `README.md:457`
**What is wrong:** "drops mass commits (above the 95th percentile of files per commit in this
repository) and shared nodes (a file coupled with six or more blocks)" — `README.md:457-458` and
`README.ru.md:393-395`. In the code the hub threshold is `hub_blocks() = max(3, ceil(0.10 ·
n_blocks))` (`review.py:965-978`), and the mass cutoff falls back to Tukey's fence below 20 commits
(`review.py:1065-1084`, `mass_basis` prints which rule was used). 6 is only what a 59-block review
produces.
**Failure scenario:** a user runs `coupling` on a 26-block review, having read that a shared node is
"a file coupled with six or more blocks". The command prints `hub = coupled with ≥ 3 blocks` and
moves files with three partners out of the pairs list; the user reads the pair list as complete for
files below six partners and looks for a seam that the tool has already filtered away. On a young
repository the same sentence mispredicts the mass-commit cutoff, which is the Tukey fence there and
not the 95th percentile.
**Why it is a defect:** the README documents behaviour the tool no longer has; the constant it
quotes was replaced by a derived threshold in this very Unreleased section.
**Confidence:** confirmed
**Root:** a number in a public document not checked against its source

### T4-006 · low · The Unreleased CHANGELOG contradicts itself on the hub threshold
**Location:** `CHANGELOG.md:68`
**What is wrong:** under Added, the `coupling` entry says "a file coupled with ≥ 6 blocks is a
shared node" (`CHANGELOG.md:68`, `CHANGELOG.ru.md:68`), while under Fixed, 32 lines above, the same
section says the hub threshold became "a share of the review's blocks with a floor of three"
(`CHANGELOG.md:36`, `CHANGELOG.ru.md:36`). Both describe the same unreleased version.
**Failure scenario:** the release notes for 0.8.0 are taken from this section verbatim (RELEASING
gate 4 requires exactly that), so a user reading them is told the threshold is 6 in one bullet and
a share with a floor of 3 in another, and cannot tell which behaviour they are updating to. Anyone
reconstructing why a `coupling` run filtered a file has two mutually exclusive rules to choose
from.
**Why it is a defect:** an entry that describes a mechanism the same section has already changed —
the CHANGELOG is the only record of what a version does.
**Confidence:** confirmed
**Root:** a number in a public document not checked against its source

### T4-007 · low · The proposal template sends contributors to files that were moved out of the repository
**Location:** `.github/ISSUE_TEMPLATE/proposal.yml:16`
**What is wrong:** the "How to close it" field asks for "how the neighbours do it (see
docs/prior-art.md)", and the next field is "Which ROADMAP direction — the number, if one fits".
The Unreleased Removed entry (`CHANGELOG.md:83`) moved `docs/` and `ROADMAP.md` to the private
repository `finetooth-hq`; `git ls-files docs` now lists only `docs/review/`.
**Failure scenario:** an outside contributor opens a Change proposal. The form directs them to
`docs/prior-art.md` — 404 — and asks for a ROADMAP direction number that exists only in a private
repository they cannot read. They either leave the required-adjacent fields empty or invent a
number; the maintainer gets proposals that cannot be placed against the plan, which is the one
thing the form exists to collect.
**Why it is a defect:** live contributor-facing guidance pointing at files the repository no longer
has; the Removed entry changed the tree without following its references.
**Confidence:** confirmed

### T4-008 · low · Two released versions have no compare link in either CHANGELOG
**Location:** `CHANGELOG.md:594`
**What is wrong:** the link-reference footer defines `[Unreleased]`, `[0.7.0]`, `[0.6.0]`, `[0.4.0]`,
`[0.3.0]`, `[0.2.0]`, `[0.1.0]` — and not `[0.5.0]` or `[0.5.1]`, whose headings (`CHANGELOG.md:158`,
`180`) are written in the same reference form. `CHANGELOG.ru.md:572-578` has the identical gap.
`[0.6.0]` compares `v0.5.0...v0.6.0`, so the tag the missing links would point at is presumed to
exist.
**Failure scenario:** a user on 0.4.1 opens the CHANGELOG to see what 0.5.0 and 0.5.1 changed
before updating. Every other version heading is a link to a GitHub compare view; these two render
as literal `[0.5.1]` text (Keep a Changelog's format, which the file's header claims to follow),
so the diff for the release that introduced the fix-reviewer role and the block proof kind is the
one a reader cannot reach.
**Why it is a defect:** RELEASING gate 4 makes "the compare link is added" a condition of the tag;
two tags exist without it, which is the first visible consequence of T4-009.
**Confidence:** confirmed

### T4-009 · low · RELEASING calls its gates "all mechanical" when three of four are human steps
**Location:** `RELEASING.md:23`
**What is wrong:** the heading reads "Gates — all mechanical, all before the tag". Gate 1 requires
that every new check be "named in CHANGELOG together with the mutation"; gate 3 requires a run on a
live project with a journal entry linked from the release notes; gate 4 requires a complete
CHANGELOG section and compare link. Nothing in the repository checks any of the three — CI runs
tests and `skills-ref validate`, which is gate 2 — and `RELEASING.md:56-59` says as much: the tag
is created by hand because automation "would make gate 3 impossible to enforce".
**Failure scenario:** a maintainer (or the second one the CONTRIBUTING write-access rule invites)
reads "all mechanical" and takes the gates as enforced, then tags a release whose CHANGELOG section
is incomplete, whose compare link is missing and which no live project has run. Nothing fails, and
that is not hypothetical: 0.5.0 and 0.5.1 shipped without their compare links (T4-008).
**Why it is a defect:** the document claims an enforcement it does not have, in the one file that
decides what a version number means; a rule believed to be mechanical is not checked by the human
who believes it.
**Confidence:** confirmed
**Root:** a rule declared enforced with nothing enforcing it

### T4-010 · low · The DCO is mandatory and nothing checks it
**Location:** `CONTRIBUTING.md:75`
**What is wrong:** "Every commit is signed with the line `Signed-off-by: Name <email>`
(`git commit -s`)". The only verification is a self-reported checkbox in
`.github/PULL_REQUEST_TEMPLATE.md:13`; `.github/workflows/` contains no DCO job, and the only
workflow that runs on pull requests (`tests.yml`) checks tests and the skill format.
**Failure scenario:** an outside contributor commits without `-s`, ticks the checkbox (or does not —
nothing reads it), CI goes green, the PR satisfies the branch protection requirement and is merged.
The repository's stated licensing basis — "you have the right to hand over this code under the
project's license" — now has a commit it was never given for, and no artefact in the tree shows
which commits are covered. All 20 most recent commits are signed off, so the gap is purely
mechanical: the first unsigned commit will arrive from outside, where the habit does not exist.
**Why it is a defect:** a contract with contributors stated as a requirement, with no gate — the
same class as T4-009, in the file that defines how changes are accepted.
**Confidence:** confirmed
**Root:** a rule declared enforced with nothing enforcing it

### T4-011 · low · The Russian README is missing the section that states what the kit is
**Location:** `README.ru.md:16`
**What is wrong:** `README.md:28-52` carries three blocks of substance that have no counterpart in
`README.ru.md`: "Four roles, separate prompts" (what each role does), "What makes it different from
PR-review bots" (six claims: the coverage map that fails on an unowned file, hypotheses with
mandatory verdicts, fingerprints, the register in git, guards from the third recurrence, tests
proven by mutation) and the "Language" paragraph. The Russian file jumps from the one-paragraph
intro straight to "Зачем это нужно".
**Failure scenario:** a Russian-speaking user follows the `[Русская версия]` link at the top of
`README.md` — the one entry point offered — and reads a document from which the six properties the
kit is sold on are absent; the mandatory-verdict mechanism and the third-recurrence guard are never
stated in Russian at all. Deciding between finetooth and a PR-review bot, they have no comparison
to read, while the English reader does.
**Why it is a defect:** the two languages say different things about what the tool guarantees;
the kit's own rule is that a document exists in both languages with the same substance.
**Confidence:** confirmed

### T4-012 · low · The README's "What is inside" inventory omits four commands and two shipped scripts
**Location:** `README.md:421`
**What is wrong:** the line that enumerates the tool lists 19 subcommands (`version` … `log`,
`README.md:421-423`, `README.ru.md:360-362`); `review.py` registers 23 — `coupling`, `order`,
`summary` and `refs` are missing, though three of them are described in the README's own closing
paragraphs. The same tree omits `scripts/axes.py` and `assets/run-role.sh`, which the README
describes two sections later, and the root list omits `CHANGELOG.ru.md`, `CODE_OF_CONDUCT.ru.md`
and `LICENSE`.
**Failure scenario:** a user writes their project's `make` targets or audits what the skill
installs from this block, which is the only place the repository enumerates itself. `refs` — added
in this unreleased version, and the command that finds review ids left behind in code — appears
nowhere in either README, so it is never run; and the two files that write outside the repository
(`run-role.sh` into `$TMPDIR`, `axes.py` reading the stream) are absent from the list of what the
skill contains, which is where a security-conscious reader would look for them (see T4-003).
**Why it is a defect:** a section whose whole purpose is to enumerate the kit is incomplete in both
languages, and the omissions are exactly the recently added parts.
**Confidence:** confirmed

### T4-013 · low · The release procedure names two paths that do not exist
**Location:** `RELEASING.md:50`
**What is wrong:** "Bump `VERSION` in `scripts/review.py` and `version` in `SKILL.md` in the same
PR". There is no `scripts/` directory and no `SKILL.md` at the repository root; the files are
`skills/finetooth/scripts/review.py:60` and `skills/finetooth/SKILL.md:7`. The layout moved in
0.4.0; this step kept the pre-0.4.0 paths.
**Failure scenario:** a release is cut by following the step literally: `scripts/review.py` is not
found, so either the release stalls on a document that is wrong, or a new `scripts/review.py` is
created and the real version strings stay at the old number — at which point
`test_версия_в_шапке_равна_версии_инструмента` fails on a release PR for a reason the message does
not explain.
**Why it is a defect:** a mandatory release step pointing at files the repository does not have.
**Confidence:** confirmed

### T4-014 · low · One CI action is pinned by commit, the other by a mutable tag
**Location:** `.github/workflows/tests.yml:15`
**What is wrong:** `uses: actions/checkout@v5` — a tag the publisher can move. Its neighbour pins by
digest with the version in a comment (`stale.yml:19`, `actions/stale@4391f3da…  # v11.0.0`), and the
`skills-ref` install in the same file is pinned to a commit
(`tests.yml:31`, `…@69ef37e9424c0a7ea9dd2293b559e43ec8176379`), which `CHANGELOG.md` 0.4.0 records
as deliberate ("pinned to a commit").
**Failure scenario:** the `v5` tag is moved — by a compromised publisher account, the failure mode
of the 2025 `tj-actions/changed-files` incident, or simply by a breaking re-tag. Every push to
`master`/`dev` and every pull request then runs different code in the checkout step. A step that
controls the working tree can make the suite pass; since green CI is what branch protection
requires before a merge into `master`, the gate reports green on a tree whose tests were never
honestly run — the kit's own worst class of defect, applied to its own CI.
**Why it is a defect:** the repository pins actions by commit everywhere else in the same two
files; this one is the exception, and the thing it protects is the gate the release depends on.
**Confidence:** confirmed

### T4-015 · low · The CI workflow is written in Russian after the repository declared English
**Location:** `.github/workflows/tests.yml:16`
**What is wrong:** the step names and comments are Russian ("Настроить git", "Прогнать тесты",
"Проверить формат скилла", plus the three comment blocks). `AGENTS.md:56` requires content in
English with Russian copies only for the named `.ru.md` files; `CONTRIBUTING.md:8` says English for
code, commits, PRs and issues; 0.7.0 made English the primary language of the project. A workflow
has no `.ru` copy and no language switch.
**Failure scenario:** an outside contributor's PR goes red. The GitHub checks panel names the failing
step in a language they do not read, and so do the comments explaining why the step exists — so the
first thing a new contributor sees of this project's CI is unreadable, in a repository whose
CONTRIBUTING promises English. The same holds for the maintainer's own release gates, which are
read under time pressure.
**Why it is a defect:** an explicit repository rule (AGENTS.md rule 7) violated in a file that has
no bilingual form; not a style preference but the declared contract of the 0.7.0 release. I note
honestly that a reviewer could class this as style — the substance of the workflow is correct.
**Confidence:** confirmed

## Acceptance criterion — claim → source → verdict

Every numbered or behavioural claim in README (en, ru) and CHANGELOG Unreleased (en, ru).

| claim | where | source checked | verdict |
|---|---|---|---|
| single Python file, standard library only, plus git | README.md:21, ru:26 | `review.py` imports stdlib only; no requirements file | holds |
| installs with `npx skills add mikey-semy/finetooth` | README.md:25, ru:24 | SKILL.md frontmatter, skill layout; installer not run here | holds (not executed) |
| `coverage` fails if a tracked file is unowned | README.md:36, ru:38 | `cmd_coverage`; `test_непокрытый_файл_роняет_карту` | holds |
| `check` refuses to close a block until every hypothesis has a verdict | README.md:38, ru:179 | `test_гипотеза_без_вердикта_роняет_проверку` | holds |
| fingerprints turn `check` red on a block closed on other code | README.md:41, ru:146 | `test_блок_просмотренный_на_другой_версии_файлов_роняет_проверку` | holds |
| guard required from the third instance of a root | README.md:45, ru:168 | `test_третий_повтор_корня_требует_узду`, `test_два_экземпляра_узду_ещё_не_требуют` | holds |
| four roles, separate prompts | README.md:28 | `references/{hunter,verify,fix,fixreview}.md`; SKILL.md description | holds (en only — T4-011) |
| block readability ceiling 6000 lines, exclusions not counted | README.md:177, ru:134 | `READABLE_LINES = 6000`; `test_порог_размера_не_считает_исключённое` | holds |
| 220-character finding-title limit | README.md:120, ru:77 | `CLAIM_MAX = 220` (source noted: 82…202 on 24 findings) | holds |
| `restamp <BLOCK>` / `restamp <finding-ID>`, `backfill` | README.md:191-201, ru:146-156 | `cmd_restamp`, `cmd_backfill`; idempotence tests | holds |
| `set-finding <ID> <status> --rule <path>` applies to the whole root; non-existent path refused | README.md:215-219, ru:169-172 | `test_узда_записывается_на_весь_корень_сразу`, `test_узда_обязана_существовать` | holds |
| `roots` shows classes, instances, what closes each | README.md:220, ru:172 | `cmd_roots`; `test_команда_roots_показывает_состояние_классов` | holds |
| 98 test scenarios | README.md:281, ru:228, AGENTS.md:68 | 248 `def test_` methods in `tests/test_review.py` | **fails — T4-004** |
| a separate class checks the skill against the spec | README.md:284, ru:231 | `SkillFormatTest` (6 tests) | holds |
| CI adds `skills-ref validate` | README.md:287, ru:234 | `tests.yml:28-32` | holds |
| `setup --cli "npm run review --"` writes the `cli` field | README.md:324, ru:268 | `cmd_setup`; `test_подсказки_зовут_инструмент_как_его_зовёт_проект` | holds |
| `setup` does not copy tool or templates into the project | README.md:322, ru:267 | `cmd_setup` writes under `docs/review/` only | holds |
| repeated `setup` adds what is missing, keeps hand edits | README.md:326, ru:270 | `test_повторный_setup_не_затирает_работу` | holds |
| spend table: 576k / 446k / 679k tokens, ~35 / ~34 / ~48 min | README.md:360-362, ru:299-301 | the author's journal; not reproducible here; en = ru | holds (unverified by design) |
| 67 blocks, 1691 files, three blocks completed | README.md:170, ru:126 | same; en = ru | holds (unverified by design) |
| `coupling`: ≥ 3 joint commits, ≥ 50% share | README.md:457, ru:393 | `COUPLING_MIN_TOGETHER = 3`, `COUPLING_MIN_SHARE = 0.5` | holds |
| mass commits above the 95th percentile of this repository | README.md:457, ru:393 | `COUPLING_MASS_PERCENTILE = 95`, but Tukey's fence below 20 commits | **partly fails — T4-005** |
| shared node = a file coupled with six or more blocks | README.md:457, ru:394 | `hub_blocks() = max(3, ceil(0.10·n))` | **fails — T4-005** |
| `coupling --write` keeps pairs in `docs/review/coupling.tsv` | README.md:459, ru:397 | `COUPLING_FILE`; `test_coupling_write_пишет_tsv` | holds |
| 76% of co-changing pairs sit in different blocks | README.md:455, ru:392 | first project's measurement; en = ru | holds (unverified by design) |
| `run-role.sh` caps turns at twice the measured run | README.md:467, ru:405 | `CAP=110` / `CAP=330` vs measured 55 / 165 | holds |
| cost is turns × context; reading the block was 1% of spend | README.md:465, ru:403 | the measured T1 run; en = ru | holds (unverified by design) |
| `summary` writes one immutable file outside the directory | README.md:472, ru:409 | `SUMMARY_DEFAULT = docs/review-summary.md` | holds (and see T4-003) |
| `summary --aged <file>` answers from `git log` alone | README.md:474, ru:411 | `cmd_summary --aged`; `test_summary_aged_считает_дрейф…` | holds |
| `order`: risk first, change frequency second, ↑/↓ vs declared | README.md:477, ru:415 | `cmd_order`; `test_order_риск_важнее_частоты` | holds |
| top 10% by change frequency → 34% of later fixes (29% by size, 6% random) | README.md:479, ru:416 | Nagappan & Ball 2005; Moser et al. 2008; en = ru | holds (citation) |
| `set-status running` refuses on open findings at `fix_gate`; `high` default; `"none"` switches off | README.md:486, ru:423 | `FIX_GATE_DEFAULT = "high"`; `test_гейт_починки…`, `test_гейт_none_выключает_проверку` | holds |
| `status` prints the fix debt as its own line | README.md:489, ru:426 | `test_статус_показывает_долг_починки` | holds |
| `check` warns about open findings older than a week | README.md:490, ru:427 | `FIX_AGE_DAYS`, 7 days; `test_check_предупреждает_о_находке_старше_недели` | holds |
| the tool's commands, as listed in "What is inside" | README.md:421, ru:360 | 19 listed, 23 registered | **fails — T4-012** |
| statuses `todo → … → closed` (+ `blocked`); findings `open/fixed/rejected/duplicate/deferred` | README.md:450, ru:388 | `STATUSES`, finding vocabulary in `check` | holds |
| 6 planted findings out of 6 rejected | README.md:403, ru:344 | 0.1.0 Measured; en = ru | holds (unverified by design) |
| T1: 68 findings, seven rounds of fix review | CHANGELOG.md:15, ru:15 | 68 rows with `"block": "T1"`; 7 `fixreview` reports on disk | holds |
| …"all confirmed by execution" | CHANGELOG.md:15, ru:15 | register: 67 `confirmed`, 1 `rejected`; 63 fixed, 4 deferred, 1 rejected | holds only as "verified by execution"; the one rejected row is not confirmed — ambiguous wording, not filed |
| the verdict parser's open class is issue #17, rules stay at round 3 | CHANGELOG.md:19, ru:19 | text is self-consistent; issue not readable offline | holds (in-repo part) |
| `~~~` fences, nested fences, indent/`>`/html quotation handled in one place | CHANGELOG.md:20,47,55, ru: same | `quoted_lines`; `SourceRuleTest.test_цитаты_распознаются_одним_местом` | holds |
| four thresholds now carry a source (80 paths, 200, 220/700, coupling hub) | CHANGELOG.md:36, ru:36 | comments above each constant; `test_каждое_число_в_коде_названо_и_объяснено` | holds |
| 24 gates of `check` had no test; all 62 gate sites measured by mutation | CHANGELOG.md:37, ru:37 | `GateCoverageTest`, `GateRegistryTest` exist; the 62 not recounted here | holds (not recounted — T3's subject) |
| the hub threshold is a share with a floor of three | CHANGELOG.md:36, ru:36 | `COUPLING_HUB_SHARE = 0.10`, `COUPLING_HUB_FLOOR = 3` | holds |
| a file coupled with ≥ 6 blocks is a shared node | CHANGELOG.md:68, ru:68 | contradicts `CHANGELOG.md:36` and the code | **fails — T4-006** |
| `refs`: exact word-bounded ids outside `docs/review/`; `check` warns with the count | CHANGELOG.md:63, ru:63 | `cmd_refs`; warning at `review.py:3356`; `test_refs_находит_номер_находки_в_коде_и_только_его` | holds |
| prompts show recorded findings and the hunter's first new id | CHANGELOG.md:65, ru:65 | `test_охотник_и_проверяющий_видят_записанные_находки`, `test_номер_первой_новой_находки_тот_же_что_выдаст_append` | holds |
| guards: `GateRegistryTest`, `SourceRuleTest`, `HandWrittenInputTest…` | CHANGELOG.md:66, ru:66 | all three classes and the named test exist | holds |
| fixer template: version/release belong to the maintainer; gates once at the end | CHANGELOG.md:67, ru:67 | `test_шаблон_исполнителя_держит_правила_выпуска_и_расхода` | holds |
| `coupling` on the first live registry: 876 commits, 37 mass, 36 nodes, 79 pairs, 3 clusters | CHANGELOG.md:68, ru:68 | the author's run; not reproducible here; en = ru | holds (unverified by design) |
| `axes.py` counts usage once per message; `--max-turns` 110 / 330 | CHANGELOG.md:69, ru:69 | `run-role.sh:19-21`; `test_axes_считает_usage_раз_на_сообщение…` | holds |
| `summary --out` default `docs/review-summary.md`, outside the directory | CHANGELOG.md:70, ru:70 | `review.py:1271`, `3601` | holds |
| `fix_gate` values, debt line, 7-day warning | CHANGELOG.md:72, ru:72 | as above | holds |
| fix-review template prints N inside / M outside the previous round's diff | CHANGELOG.md:73, ru:73 | `references/fixreview.md` (T2's file, not read in full) | not checked — T2 |
| logo files exist and switch with the GitHub theme | CHANGELOG.md:74, ru:74 | `.github/logo-light.png`, `logo-dark.png` tracked; `README.md:4-7` `<picture>` | holds |
| branch model: `master` releases, `dev` default, CI on both | CHANGELOG.md:75, ru:75 | `tests.yml:4-6`; RELEASING:35-42; CONTRIBUTING:56 | holds in-repo (default branch is a GitHub setting — not checked) |
| RELEASING: four mechanical gates before a tag | CHANGELOG.md:76, ru:76 | three of the four are human steps | **fails — T4-009** |
| `docs/` and `ROADMAP.md` moved to the private knowledge base | CHANGELOG.md:83, ru:83 | `git ls-files docs` → only `docs/review/` | holds (but references left behind — T4-007) |
| Breaking: plain `import` no longer erases recorded rows | CHANGELOG.md:87, ru:87 | `RecordedFindingsImportTest` (10 tests) | holds |
| Breaking: block definitions validated on load, exit 2 with the field name | CHANGELOG.md:88, ru:88 | `HandWrittenInputTest.test_блок_без_обязательного_поля_называет_поле` | holds |
| Breaking: a quoted verdict no longer closes a hypothesis | CHANGELOG.md:89, ru:89 | `ReportShapeTest` (13 tests), `QuotationMapTest` | holds |
| Breaking: the named-files gate rejects a longer path containing a shorter | CHANGELOG.md:90, ru:90 | `test_соседний_файл_с_тем_же_началом_не_закрывает_гейт_имён` | holds |
| Breaking: the fix gate | CHANGELOG.md:91, ru:91 | as above | holds |
| the Breaking section holds only breaking changes, one heading per type, Breaking last | CHANGELOG.md:51, ru:51 | Unreleased order en and ru: Fixed, Added, Removed, Breaking; the 5 Breaking entries all require user action | holds |
| compare links for every version | CHANGELOG.md:594-600, ru:572-578 | `[0.5.0]`, `[0.5.1]` absent in both | **fails — T4-008** |
| SECURITY: the tool writes to `docs/review/` and sends nothing over the network | SECURITY.md:3 | `summary` default; `run-role.sh` `$TMPDIR` + `claude -p` | **fails — T4-003** |
| NOTICE: projects road-tested on are not named, internals not published | NOTICE.md:31 | `CHANGELOG.md:40` names `setfork H3` and `curation/adapter.ts` | **fails — T4-002** |
| LICENSE: clean MIT, two holders, no licence-boundary appendix | LICENSE:1-4, NOTICE.md:20 | `LICENSE` is unmodified MIT with both names; `SKILL.md:4` still carries the appendix | **fails — T4-001** |
| CONTRIBUTING: CI runs the tests and `skills-ref validate` | CONTRIBUTING.md:62-67 | `tests.yml:23-32` | holds |
| CONTRIBUTING: every commit signed off | CONTRIBUTING.md:75 | no DCO check; last 20 commits are signed | **fails as a gate — T4-010** |
| stale bot: PRs 21 + 9 days, issues never expire | CHANGELOG 0.7.0:128, CONTRIBUTING:48 | `stale.yml:21-24` (`-1` for issues, 21 + 9 for PRs) | holds |
| `.gitignore` carries `__pycache__/` | CHANGELOG 0.3.0 | `.gitignore:1` | holds |

## Checked and found correct

- **`stale.yml` against CONTRIBUTING.** "Closed after 30 days of inactivity" versus
  `days-before-pr-stale: 21` + `days-before-pr-close: 9` — 21 + 9 = 30, and issues are exempted
  with `-1`/`-1` exactly as "issues never expire" promises. `exempt-pr-labels: blocked` is not
  documented but contradicts nothing.
- **The `fix_gate` / debt / 7-day trio.** All three numbers in the README's closing paragraph match
  the code, and the 7 days is deliberately the same week as the stale-tree threshold, as the
  CHANGELOG claims — `FIX_AGE_DAYS` and `STALE_TREE_DAYS` are both 7 with the measurement noted
  above each.
- **The CHANGELOG's section ordering.** The Unreleased section really is one heading per type with
  Breaking last, in both languages, and all five Breaking entries do require user action — the
  defect that entry describes is genuinely fixed, not restated.
- **`VERSION` is still 0.7.0 with Unreleased open.** This looks like a missed bump but is the
  documented rule: RELEASING:50 puts the bump in the release PR, and the fixer's template forbids
  a fixer from touching `VERSION`. `SKILL.md`'s `metadata.version` agrees with `VERSION`, which is
  what the test pins.
- **Both codes of conduct carry a real enforcement contact** ("an issue in this repository or an
  email to the address in the owner's GitHub profile"), not the Covenant's `[INSERT CONTACT METHOD]`
  placeholder — the usual defect in an adapted 2.1 text. The two language versions match
  section for section.
- **`skills-ref` installed from git in CI is not a dependency violation.** AGENTS.md rule 1 binds
  the tool, not the CI runner, and the install is pinned to a commit in a throwaway venv.
- **"26 such rows in 15 unstarted blocks" and the other live-register figures** (`CHANGELOG.md:87`)
  are counts without identifiers, which the NOTICE's anonymisation promise permits; only the
  project *name* in `CHANGELOG.md:40` crosses the line.
- **`bug.yml` asks for state "without other people's data"** and `trophy.yml` asks for the defect
  "anonymised — without the project name and internal details" — the issue templates enforce the
  NOTICE promise on contributors, which is why the CHANGELOG breaking it is worth filing.
