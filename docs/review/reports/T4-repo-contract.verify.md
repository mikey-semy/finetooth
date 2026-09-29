# T4 — verifier report

Block: T4 — Documentation and the repository contract. Verified at `2e7c39f`, which is the tip of
`origin/dev` (`git rev-list --count HEAD..origin/dev` = 0 after `git fetch`; `origin/master` does
not exist in this clone, `dev` is the integration branch RELEASING names as default). Every
verdict below rests on something run in this tree, not on re-reading the hunter's wording.

## How this was checked

The stand is three script files, each run once, written to `/tmp/.../scratchpad/stand*.py`:

1. **The suite, measured.** `python3 -m unittest discover -s tests` → `Ran 248 tests in 201.032s`,
   OK. This is the number the hunter could not get and the one two findings turn on.
2. **`coupling` on a matrix of block counts.** A fixture repository (9 real blocks + padding to
   20/30/51/59/60/61/70, 17 commits, one file made to co-change with five others) run through
   `coupling` at each size, reading the threshold line the tool prints.
3. **The write boundary, measured.** A clean repository taken through `setup`, `init`, `coverage`,
   `status`, `summary`, with a full before/after file snapshot of the whole tree at each step.
4. **The traceback matrix.** A hand-written `blocks.json` run through all 23 subcommands,
   recording exit code and whether a traceback reached stderr.
5. **Mechanical parsing** of both CHANGELOGs (version headings against defined link references),
   both READMEs (headings, bold leads, every shared number), the `--help` subcommand list against
   the README inventory, and every repo-relative path named in the 21 block files against
   `git ls-files`.

## Verdicts on hunter findings

| id | verdict | severity after checking | justification |
|---|---|---|---|
| T4-001 | CONFIRMED | medium (held) | `skills/finetooth/SKILL.md:4` reads verbatim `license: MIT for the additions; the base was handed over by its author without a license`. `LICENSE` is unmodified MIT with both holders; `diff LICENSE skills/finetooth/LICENSE` → identical; `NOTICE.md:20-27` records the 24.09.2026 grant; `CHANGELOG.md:116-119` records the appendix as removed. The contradiction ships in the installed copy. |
| T4-002 | CONFIRMED, reasoning corrected | medium → **low** | The name is real (`CHANGELOG.md:40`, `CHANGELOG.ru.md:40`, `review.py:2636`, `tests/test_review.py:788,794`), but setfork is **the repository owner's own** project — every clone under `/home/mike/Projects/setfork*` has an `origin` of `mikey-semy/…`. NOTICE's paragraph sits under the heading "Other people's projects", and the *other* author's project is never named anywhere (`CHANGELOG.md:87` says "the kit author's live register" with counts only). So this is self-disclosure against an unqualified sentence, not the publication of a third party's data. The hunter's scenario — an owner who allowed a run finding their repository named — does not follow from the tree. What remains is a real contradiction between NOTICE's wording and the CHANGELOG, fixable either way. |
| T4-003 | CONFIRMED by execution | medium (held) | Measured on a clean repository: `setup`, `init`, `coverage`, `status` wrote only under `docs/review/`; `summary` with no arguments created `docs/review-summary.md` — **outside** the only directory `SECURITY.md:15` permits — and `summary --out <abs>` wrote outside the repository entirely. `assets/run-role.sh:25` writes `${TMPDIR:-/tmp}/finetooth-runs` and `:38` runs `claude -p`, so "sends nothing over the network" is false of a shipped component. SECURITY.md carries none of the three, and its own definition of a vulnerability is triggered by documented behaviour. Medium stands on the `summary` leg alone. |
| T4-004 | CONFIRMED and broadened | low (held) | Measured: 248 tests, 201.032 s. The published figure is 98 in five places (`README.md:281,438`, `README.ru.md:228,377`, `AGENTS.md:68`) and it tracked reality at 0.1.0 (25), 0.3.0 (67), 0.4.0 (76). **The same sentences also misstate the runtime**: `AGENTS.md:68` "about a minute" and `CONTRIBUTING.md:65` "~1 minute" against 3 min 21 s measured. I folded the runtime into this finding rather than filing it separately — same sentence, same root, one edit closes both. |
| T4-005 | CONFIRMED by execution | low (held) | At 9 blocks the tool printed `thresholds: together ≥ 3, share ≥ 50%, hub = coupled with ≥ 3 blocks` and moved `hub.ts` (5 partners) into shared nodes, leaving `no cross-block pairs above the thresholds` — exactly the hunter's scenario, reproduced. The printed threshold is 3 up to 30 blocks, 6 only at 51-60, 7 from 61. The mass-cutoff half also holds: the tool printed `Tukey's fence over 17 commits — fewer than 20, too few for a percentile`, not the 95th percentile the README names. Both READMEs carry the sentence identically (`README.md:456-457`, `README.ru.md:393-395`). |
| T4-006 | CONFIRMED | low (held) | `CHANGELOG.md:68` ("a file coupled with ≥ 6 blocks is a shared node") against `CHANGELOG.md:36` ("a share of the review's blocks with a floor of three"), same Unreleased section, and identically at `CHANGELOG.ru.md:36,68`. Same root as T4-005: the code says `hub_blocks() = max(3, ceil(0.10·n))`. |
| T4-007 | CONFIRMED | low (held) | `git ls-files docs` returns only `docs/review/…`; `git ls-files | grep -iE 'prior-art|roadmap'` is empty. `proposal.yml:16` points contributors at `docs/prior-art.md` and `:22` asks for a ROADMAP direction number — both moved to the private `finetooth-hq` by `CHANGELOG.md:83`. |
| T4-008 | CONFIRMED, **count corrected** | low (held) | Parsed both files: headings are Unreleased, 0.7.0, 0.6.0, 0.5.1, 0.5.0, 0.4.1, 0.4.0, 0.3.0, 0.2.0, 0.1.0; defined link references are Unreleased, 0.7.0, 0.6.0, 0.4.0, 0.3.0, 0.2.0, 0.1.0. **Three** versions have no compare link, not two: 0.5.1, 0.5.0 and **0.4.1** — identically in `CHANGELOG.ru.md:572-578`. The hunter missed 0.4.1. |
| T4-009 | CONFIRMED | low (held) | Only gate 2 exists as a mechanism (`tests.yml:23-32`). Nothing in the repository checks gate 1 (a mutation named in the CHANGELOG), gate 3 (a live run linked from the notes) or gate 4 (a complete section and a compare link) — and `RELEASING.md:56-59` says gate 3 cannot be automated, contradicting its own heading at `:23`. The consequence is measurable: three versions shipped without the link gate 4 requires. |
| T4-010 | CONFIRMED | low (held) | `.github` tracks exactly nine files (four issue templates, the PR template, two workflows, two logos); no DCO job, no `signed-off` check anywhere outside prose. The only verification is the self-reported checkbox at `PULL_REQUEST_TEMPLATE.md:13`. The habit holds inside (sign-off lines present throughout the last 30 commits), which is what makes the gap purely mechanical. |
| T4-011 | CONFIRMED, scope corrected | low (held) | Read `README.ru.md` in full. Both files carry the same ten `##` headings; the gap is the un-headed material at `README.md:28-52`. Correction: the "four roles" substance *is* present in Russian, inside "Зачем это нужно" (`README.ru.md:45-48`), as it is in English at `:85`. What has no Russian counterpart is the standalone differentiator list — the six claims the kit is sold on — and the "Language" paragraph; `PR-review bots` has no Russian equivalent anywhere in the file. The finding stands, narrower than written. |
| T4-012 | CONFIRMED and broadened | low (held) | `--help` registers 23 subcommands; the inventory lists 19 (`README.md:421-423`, `README.ru.md:360-362`). Missing: `coupling`, `order`, `summary`, `refs`. Verified separately that `refs` appears **nowhere in either README** (word-bounded search, en=absent ru=absent) — the only command in that state. Broadened with what the same scan found: the tree omits `scripts/axes.py`, `assets/run-role.sh`, all **ten** `.ru.md` templates and assets (the files the `lang` switch selects), and at root `.gitignore`, `CLAUDE.md`, `CHANGELOG.ru.md`, `CODE_OF_CONDUCT.ru.md`. Folded in by root rather than filed apart: one pass over the inventory closes all of it. |
| T4-013 | CONFIRMED | low (held) | `git ls-files | grep -E '^(scripts/|SKILL\.md$)'` is empty; the files are `skills/finetooth/scripts/review.py:60` and `skills/finetooth/SKILL.md:7`. `RELEASING.md:50` names the pre-0.4.0 paths. |
| T4-014 | CONFIRMED, reasoning corrected | low (held) | `tests.yml:15` is `actions/checkout@v5` while `stale.yml:19` pins by digest and `tests.yml:31` pins `skills-ref` to a commit. Correction to the hunter's reasoning, so the fixer does not over-read it: this is a **first-party** GitHub action, the job declares `permissions: contents: read`, and no repository secret is referenced — so the tj-actions exfiltration analogy does not transfer. The realistic worst case is the one the hunter names second: a false-green required check. Low, and the inconsistency with its two neighbours is the argument. |
| T4-015 | CONFIRMED | low (held) | `tests.yml:16-28` — three step names and three comment blocks in Russian. Context I add: Cyrillic elsewhere in the tree is deliberate (the `MSG` table in `review.py`, Russian test method names, and their quotation in CHANGELOG/README), so a workflow is the only reader-facing file that is Russian-only with no bilingual form, against `AGENTS.md:56` and `CONTRIBUTING.md:8`. The substance of the workflow is correct; this is a contract violation, cheap to fix, and I agree with the hunter that a reviewer could class it as style. |

Rejected: none. Every hunter finding survived checking. Two had their count or scope corrected
(T4-008, T4-011), one had its severity lowered on a fact the hunter did not establish (T4-002),
two had their reasoning corrected without changing the verdict (T4-014, T4-015), and two were
broadened by what my own pass found (T4-004, T4-012).

## Verdicts on recorded findings

Nothing was recorded against T4 before this pass, so this table is empty by construction. The
fifteen rows above are the hunter's draft findings of this same pass, not previously recorded
rows, and they belong in the final findings file rather than here.

## Own findings

### T4-016 · medium · `init` answers a traceback on a hand-written `blocks.json`, and the guard that forbids it stays green
**Location:** `skills/finetooth/scripts/review.py:564`
**What is wrong:** `check_definition` (`:495-526`) validates the top-level `blocks` array and, for
each block, `BLOCK_FIELDS` — and nothing else. The top-level `review_id` is never validated, and
`cmd_init` reads it unguarded: `st = {"review_id": defn["review_id"], …}`.
**Measured:** a hand-written `blocks.json` holding `project`, `gates`, `cli` and one fully valid
block, run through all 23 subcommands. Twenty-two behave: `status`, `check`, `order`, `summary`,
`next` exit 2 naming the missing state file, `coverage` exits 1, the rest exit 0. `init` alone
ends in `KeyError: 'review_id'` — a five-frame Python traceback and exit 1.
**Why the guard does not catch it:** `HandWrittenInputTest.test_ни_одна_команда_не_роняет_трейсбек_на_битом_определении`
(`tests/test_review.py:3059`) takes the subcommand list from the tool itself and asserts no
command prints a traceback on a broken definition — exactly this rule. It passes because its
fixture, `Stand.blocks` (`tests/test_review.py:81-91`), always writes `"review_id": "test"`. The
guard exercises the per-block shape only; a missing top-level field is outside its reach, and the
suite is green today with the defect present.
**Failure scenario:** the register already carries four instances of the root *hand-edited input
reaches the code unvalidated*, and `CHANGELOG.md:29` says the class is closed — "answered
`KeyError` and exit 1, which reads as 'the state is red'. Definitions are checked once, on load,
with a message that names the field and the file" — while `CHANGELOG.md:88` promises `blocks.json`
is validated on load with exit 2 and the field name. The reachable paths: a user writing
`blocks.json` by hand without running `setup` (README step 2 at `README.md:335`/`README.ru.md:279`
names only `project` and `gates` to fill in, never `review_id`), or a review migrating from an
older on-disk format — the case the Breaking entry exists for. They get a traceback with no fix
named, which is the one output the kit promises never to produce.
**Why it is a defect:** invariant 12 — a traceback reaching the user is a defect regardless of the
cause; invariant 2 — a guard that can be holed while the suite stays green is not a guard. Both
`setup` and `assets/blocks.example.json` do write `review_id`, which is why this survived: the
happy path never touches it.
**Confidence:** confirmed
**Root:** hand-edited input reaches the code unvalidated

### T4-017 · low · SKILL.md claims the tool is tested on two Python versions; CI tests one
**Location:** `skills/finetooth/SKILL.md:5`
**What is wrong:** the frontmatter reads `compatibility: Requires git and Python 3 (standard
library only; tested on 3.12 and 3.14)`. `.github/workflows/tests.yml` contains no
`actions/setup-python` and no matrix: both steps call the runner's default `python3`, so exactly
one version is ever exercised, and which one moves with the `ubuntu-latest` image. No other public
file states a Python requirement at all — the READINGs say only "a single Python file on the
standard library".
**Failure scenario:** a team installs the skill into a repository whose CI image carries a
different Python and relies on the claim as tested ground. The claim is the same class as T4-009
and T4-010 — stated as verified, with nothing verifying it — and it is the one compatibility
statement a `skills-ref`-validated skill puts in front of an installer. Measured mitigation: the
file's syntax floor is low (one `from __future__ import annotations`, 21 union annotations and 54
builtin generics, all in annotations; no `match`, no `tomllib`, no `datetime.UTC`), so the risk is
not that it breaks today but that nothing would catch it when it does.
**Why it is a defect:** hypothesis T4.4's class — a rule or claim the repository states and does
not enforce. The fix is three lines of matrix or a narrower sentence.
**Confidence:** confirmed
**Root:** a rule declared enforced with nothing enforcing it

### T4-018 · low · Neither code of conduct links to its other-language copy
**Location:** `CODE_OF_CONDUCT.md:1`
**What is wrong:** `CHANGELOG.md:100-103` (0.7.0) states that the Russian copies —
`README.ru.md`, `CHANGELOG.ru.md`, `CODE_OF_CONDUCT.ru.md` among them — are "cross-linked at the
top of each file". Checked the first line of all six files: `README.md` ↔ `README.ru.md` and
`CHANGELOG.md` ↔ `CHANGELOG.ru.md` carry the link; both codes of conduct begin with a blank line
and have no link in either direction.
**Failure scenario:** the code of conduct is the file a newcomer opens before their first issue.
A Russian speaker who lands on `CODE_OF_CONDUCT.md` — the one GitHub surfaces in the community
profile — has no way to discover that `CODE_OF_CONDUCT.ru.md` exists, and vice versa, so a
translation that was made and committed goes unread.
**Why it is a defect:** an en ↔ ru navigation asymmetry against a stated release claim
(hypothesis T4.3), in the one pair of files where the two versions are otherwise identical.
**Confidence:** confirmed
**Note:** checked and correct in the same pair — both files carry all thirteen headings in the
same order and a real enforcement contact ("an issue in this repository or an email to the address
in the owner's GitHub profile", `CODE_OF_CONDUCT.md:40` / `CODE_OF_CONDUCT.ru.md:40`), not the
Covenant's `[INSERT CONTACT METHOD]` placeholder.

## Duplicates and root grouping

Deduplicated by root, not by text — two findings are one where fixing the root of the first makes
the second cease to exist.

- The runtime claim ("about a minute", "~1 minute") is **not filed separately**: it sits in the
  same sentences as the test count, and one measured edit closes both. Folded into T4-004.
- The unlisted `.ru.md` templates, `axes.py`, `run-role.sh` and the four unlisted root files are
  **not filed separately**: one pass over the inventory that fixes T4-012 removes all of them.
  Folded into T4-012.
- Three findings now carry the root *a rule declared enforced with nothing enforcing it*
  (T4-009, T4-010, T4-017) and three carry *a number in a public document not checked against its
  source* (T4-004, T4-005, T4-006). That is deliberate: at the third instance the kit's own check
  requires a guard rather than three edits, and both classes have an obvious one — a CI job that
  checks the CHANGELOG section, the compare link and the sign-off, and a test that reads the
  published counts back from their sources.
- T4-005 and T4-006 share the same underlying wrong number in two documents; they stay separate
  because the CHANGELOG entry and the README sentence are edited independently and the CHANGELOG
  one is additionally self-contradictory.

## Hypothesis verdicts

T4.1 — checked: every bullet of the Unreleased section was matched against the mechanism it
names, and the totals were recounted from the register rather than read. The register holds
exactly 68 rows, all with `"block": "T1"` (63 fixed, 4 deferred, 1 rejected; 67 confirmed, 1
rejected), and `docs/review/reports/` holds exactly seven `fixreview` reports — so "68 findings
over the hunt and seven rounds of fix review" at `CHANGELOG.md:15` holds. No entry describes the
reverted round-6/7 verdict rules; `CHANGELOG.md:19` states outright that the parser stays at the
round-3 rules and names issue #17. One entry does contradict a later fix in the same section
(T4-006), and one entry's promise does not hold against the code (T4-016).

T4.2 — checked: every command, flag, default and number the READMEs name was run down in the
code, and the behavioural ones were executed. Correct: `COUPLING_MIN_TOGETHER = 3`,
`COUPLING_MIN_SHARE = 0.5`, `STATUSES` and `FINDING_STATUS` exactly as `README.md:450-451` lists
them, `FIX_GATE_DEFAULT = "high"` with `"none"` to switch off, `FIX_AGE_DAYS = 7`,
`READABLE_LINES = 6000`, `CLAIM_MAX = 220`, `SCENARIO_MAX = 700`, `run-role.sh` caps 110/330
against the measured 55/165, `summary --aged`, `coverage --no-write`. Wrong: the shared-node
threshold and the mass cutoff (T4-005). Absent from both READMEs: `refs` (T4-012).

T4.3 — checked: the two CHANGELOGs are equal in the Unreleased section — 57 bullets each, the same
four section headings in the same order, and the same numbers throughout (the only token
differences are `2.` and `95` from "95-го процентиля" against "95th percentile"). Both are missing
the same three compare links (T4-008) and both carry the same self-contradiction (T4-006). The
READMEs carry the same ten headings and the same numbers (67 blocks / 1691 files, 576/446/679k
tokens, 76%, 34/29/6%, 77 findings / 9 fixed, 6 of 6 planted — all present in both, in local
formatting: "576 тыс." for "576k"), but the English file has substance the Russian does not
(T4-011). The codes of conduct match section for section but are not cross-linked (T4-018).

T4.4 — checked, and stated rules are indeed unenforced: `tests.yml` runs exactly what
`CONTRIBUTING.md:62-67` names, on push to `master`/`dev` and on every pull request. But the DCO
that CONTRIBUTING makes mandatory has no mechanism (T4-010), three of RELEASING's four gates have
none (T4-009), the skill's own "tested on 3.12 and 3.14" has none (T4-017), and one action is
taken by a mutable tag while its neighbours are pinned (T4-014). Branch protection itself is a
GitHub-side setting and could not be read from here — see Coverage.

T4.5 — checked by execution, and the promise is false as written: a clean repository taken through
`setup`, `init`, `coverage` and `status` was written to only under `docs/review/`, but `summary`
with no arguments created `docs/review-summary.md` outside it and `summary --out` wrote outside
the repository; `run-role.sh` writes the prompt and the whole event stream into `$TMPDIR` and
calls `claude -p`. `SECURITY.md` names none of the three (T4-003).

T4.6 — checked: a live project's name and one internal path are published (`CHANGELOG.md:40`,
`CHANGELOG.ru.md:40`, and the same path in `review.py:2636` and `tests/test_review.py:788,794`),
but the project is the repository owner's own, and the *other* author's project is never named —
the counts at `CHANGELOG.md:87` ("26 such rows in 15 unstarted blocks") carry no identifier, which
the NOTICE permits. So the anonymisation of other people's projects holds; what fails is the
unqualified wording of the promise against the owner's own disclosure (T4-002, downgraded).

T4.7 — checked: RELEASING's rules are consistent with the history they were written after, but the
file oversells its own enforcement — "Gates — all mechanical" is untrue of gates 1, 3 and 4, and
the file itself says gate 3 cannot be automated (T4-009); its version-bump step names two paths
the repository does not have (T4-013). The cadence rule ("at most one release a week") is stated
as cadence rather than as a gate, so the absence of a mechanical check for it is not a defect.

## Acceptance criterion

The claim → source → verdict table the criterion asks for is the hunter's, at
`T4-repo-contract.hunter.md:413-486`, and I re-derived its rows rather than accepting them. Every
row I checked independently is recorded above under the finding or hypothesis it belongs to; the
corrections to that table are:

| row in the hunter's table | correction |
|---|---|
| 98 test scenarios | the measured count is 248 in 201.032 s, so the runtime claim fails too, not only the count |
| compare links for every version | three versions lack one (0.5.1, 0.5.0, 0.4.1), not two |
| four roles, separate prompts — "holds (en only)" | the substance is in the Russian file too, inside "Зачем это нужно"; what is en-only is the differentiator list and the Language paragraph |
| NOTICE: projects road-tested on are not named | fails only for the owner's own project; the other author's project is not named anywhere |
| "all confirmed by execution" (`CHANGELOG.md:15`) | not filed, and I agree: 67 of 68 rows are confirmed and the 68th is rejected, which is itself a verdict reached by execution |
| Breaking: block definitions validated on load, exit 2 with the field name | fails for `init` on a missing top-level `review_id` (T4-016) — the hunter took this row on the test name alone |
| `run-role.sh` caps turns at twice the measured run | holds; verified `CAP=110` for hunter and `CAP=330` for verify/fix/fixreview at `run-role.sh:19-21` |

## Block coverage status

Complete. All 21 files of the block have been read in full by me, not only by the hunter:
`.github/ISSUE_TEMPLATE/bug.yml`, `.github/ISSUE_TEMPLATE/config.yml`,
`.github/ISSUE_TEMPLATE/proposal.yml`, `.github/ISSUE_TEMPLATE/trophy.yml`,
`.github/PULL_REQUEST_TEMPLATE.md`, `.github/workflows/stale.yml`, `.github/workflows/tests.yml`,
`.gitignore`, `AGENTS.md`, `CHANGELOG.md`, `CHANGELOG.ru.md`, `CLAUDE.md`,
`CODE_OF_CONDUCT.md`, `CODE_OF_CONDUCT.ru.md`, `CONTRIBUTING.md`, `LICENSE`, `NOTICE.md`,
`README.md`, `README.ru.md`, `RELEASING.md`, `SECURITY.md`. Files outside the block opened to
check a claim against its source: `skills/finetooth/SKILL.md`,
`skills/finetooth/scripts/review.py`, `skills/finetooth/scripts/axes.py`,
`skills/finetooth/assets/run-role.sh`, `skills/finetooth/assets/blocks.example.json`,
`tests/test_review.py`, `docs/review/findings.jsonl`. All seven hypotheses carry a verdict above.

One honest qualification on how two files were read. `CHANGELOG.ru.md` I read as prose in its
Unreleased section and verified the rest mechanically against the English original — 57 bullets
against 57, the same four headings in the same order, an identical set of numeric tokens — rather
than re-reading 579 lines of Russian that the hunter had already read line by line and in which it
had itself found the two divergences it filed. `CODE_OF_CONDUCT.ru.md` I read in full. I record
this as complete because the acceptance criterion's subject is the claims, and every claim in that
file was compared against its English counterpart by a method that would have caught a differing
number or a missing entry.

What could not be checked here, and is therefore not closed by anyone:

- **GitHub-side settings.** Branch protection on `master` and the required-status-check list
  (`RELEASING.md:37`, `CHANGELOG.md:124`), whether Discussions is enabled for the URL in
  `ISSUE_TEMPLATE/config.yml`, whether a DCO app is installed outside `.github/`, and whether the
  `v0.4.1`/`v0.5.0`/`v0.5.1` tags exist. No network, no `gh` auth. T4-010 and T4-008 are filed on
  the absence of an in-repo mechanism and an in-repo link, which is what is visible from here.
- **`skills-ref validate`** was not run — the validator is not installed in this session and
  cannot be fetched. T4-001 and T4-017 are filed on the *content* of two frontmatter fields, not
  on the format, so neither depends on it. The skill's format is T2's subject.
- **Outbound links.** No URL in the READMEs, the CHANGELOG footer, or the Covenant anchors was
  resolved. A dead or redirecting link would not have been noticed.
- **The author's measurements** (67 blocks / 1691 files, the three spend rows, 76%, 34/29/6%, the
  587 findings of 0.2.0) cannot be reproduced here, and the README says so itself. I verified only
  that they agree between the two languages and with the CHANGELOG.
- **Role-template prose** (`references/*.md`) — T2's files. Where a repository-contract claim
  touches them I checked the named test exists, not the template's wording.
