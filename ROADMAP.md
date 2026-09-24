[Русская версия](ROADMAP.ru.md)

# Where to grow

The plan is derived from what has already been measured, not from wishes. Each direction answers
the question "what do we not know about the method" or "what breaks on transfer", and each has a
condition by which it can be considered closed.

State as of 24.09.2026: the kit has been run on **three projects** (587 findings, one review
brought to the end — 27 blocks of 27), compared with the methodology of audit firms, the practice
of Google and Meta, industrial AI reviewers, academic works and neighbours in the niche on
GitHub. The figures are in [`docs/measurements.md`](docs/measurements.md), the analysis of others'
solutions for each direction is in [`docs/prior-art.md`](docs/prior-art.md).

On 23.09 the plan was reassembled after a comparison of eight review methods the first project
was checked with (file by file, large files, lenses, cross-cutting audit, vertical slices, AI
review in PRs, skill review and this kit), and a check against external methods by primary
sources. The comparison and measurements are in
[`docs/review-methods.md`](docs/review-methods.md). From it came three new directions (11–13)
and corrections to 1, 3 and 9.

On 24.09, 0.5.0 came out based on the second version of the kit from its author: five defects of
our copy closed, the fix reviewer role, the block's proof kind, the gate "every file is named"
(that is half of direction 4), `inventory`/`sizes`/`coverage --no-write` added. What this closes
from the plan is marked in the table below.

## What we know about the method

| claim | how it is backed |
|---|---|
| the verifier does not let a fabrication through | 6 planted findings of 6 rejected, by two models independently |
| the hunter does not fabricate | 0 rejected of 18 findings on the money block |
| the pair "hunter + verifier" is cheaper than a pair of hunters | 41% saving with a comparable number of unique roots |
| verification by execution works, re-reading does not | our measurement + 433 real alarms at Tencent (precision 0.26 versus 0.83) |
| one hunter finds no more than ~half of a block's defects | two independent hunters on the money block: 10 and 8 findings, 4 shared → an estimate of ~19–20 defects; this is an **upper bound** (the hunters are correlated) |
| the method can search faster than the project fixes | the first project: 77 findings on 5 blocks, 9 fixed (12%) |
| blocks cut seams | 76% of file pairs that change together lie in different blocks; without shared hubs — 38 strong cross-block pairs |
| the cost of a block does not depend on its size | 782 lines — 557 thousand tokens, 4017 lines — 576 thousand: the spend goes on tool results, not on reading the block's files |
| fix review finds what neither the hunter nor the verifier found | at the kit's author the heaviest defect of the access block came from the third round of fix review and had been in the project from the start |
| the coverage map catches the forgotten | 89 route files with us, a whole microservice at the kit's author |

**And a first estimate of misses** — from the data of two finished reviews: the main pass gives
71–77% of all findings and **86–88% of the large ones**. The rest surfaces later, during fixing
and diff review, and it is mostly small stuff.

## What we do NOT know

**How much the method misses for good.** The estimate above is a lower one: its denominator is
"everything found in the end", not "everything there is". Defects found by nobody are not in it,
and how many there are is unknown. The industry is no help here: nobody publishes completeness.

## Fifteen directions

| № | what about | readiness |
|---|---|---|
| 1 | measure the misses for real | there is a lower estimate, a corpus is needed |
| 2 | portability to another language | confirmed between projects, the language is one |
| 3 | regression is caught by gates | the guard is checked for existence (0.3.0); no run of the gates by root |
| 4 | third layer of coverage | the files half done in 0.5.0: every file of a readable block is named in a report; the hypotheses side not started |
| 5 | the seeker's precision changes the prompt | data accumulates, no count |
| 6 | run archive | not started |
| 7 | a block over two repositories | not started, the pain is known |
| 8 | two people run the review at once | it is known what will break |
| 9 | economics and scale | there is a model, no calibration; token analysis — `docs/token-economy.md`, the first step is a measurement |
| 10 | what remains after deleting the directory | the contradiction removed, the summary not automated |
| 11 | fix phase as a gate | in 0.5.0 — a reason on `deferred` and fix review before `closed`; the gate on a new block itself not started |
| 12 | seams between blocks: a change coupling map | there is a measurement, no command |
| 13 | threat model as a block type | not started |
| 14 | lens bank — a source of hypotheses for manifests | 26 lenses with prompts exist in the first project; in the kit — none |
| 15 | open project: licence, scaffolding, skill catalogues | checklist in `docs/open-source.md`; waiting for the owner's decisions on licence and name |

---

## Direction 1. Measure the misses

**Why first.** Everything else is an improvement of something whose usefulness is not measured.

**The first thing to know: recall cannot be measured directly.** The denominator — all existing
defects — is unavailable. Any working method substitutes a sample with known answers for it, and
everything hinges on whether the sample resembles real defects. This is exactly where most
published figures fall apart:

- static analysers (Error Prone, Infer, SpotBugs) on **594 real** defects find **4.5%**; on
  synthetic sets the same tools claimed 64–99% (Habib & Pradel, ASE 2018);
- eight fuzzers over 80+ years of CPU time found **not one** of 50 organic CVEs, although they
  found synthetic ones (Bundt et al., ASIA CCS 2021);
- AI reviewers on a benchmark of real PR comments: 20–32% individually, **41.5%** all together
  (c-CRAB, arXiv 2603.23448).

**What cannot be used to measure — checked before us:**
- **the Mills remainder estimate** (`N̂ = S·n/k`) rests on equal difficulty of seeded and real
  defects, and this assumption is violated systematically and in one direction;
- **capture-recapture on two reviewers** — "one would be forgiven for concluding that CR
  models are not usable for two inspectors" (El Emam & Laitenberger, TSE 2001). For us it is
  doubly worse: identical agents miss the same things, the overlap comes out artificially high,
  and the formula will say "almost everything found" exactly where both are blind to a whole
  class;
- **mutation score as a reported figure** — 17% of real defects are coupled to no mutant at all
  (Just et al., FSE 2014), and the correlation of the score with catching real defects weakens
  when test suite size is controlled (Papadakis et al., ICSE 2018).

**What this means for our own measurement on two hunters.** The money block was passed by two
independent hunters: 10 and 8 findings, 4 shared. Lincoln–Petersen gives ~20 defects, Chapman
~19, i.e. one hunter finds ~40–50%. This is **an upper bound, not a measurement**: one model and
one prompt miss the same things, the overlap is inflated, and the true number of defects is
higher. If one counts anyway — with the Mh model with the Jackknife estimator and with verifiers
of **different** models (Briand et al., TSE 2000), and only as a reason to decide "re-pass or
not".

**A cheap upper bound that can be taken right now — sampling.** 59 random files from closed
blocks, a repeated deep pass by another model: if not a single new serious defect, then with 95%
confidence the share of files with a missed serious defect is no higher than 5%
(`n = ln 0,05 / ln 0,95`). Stratify the sample by change frequency, otherwise rare dangerous
places will not get into it. This is not recall but quality control of a batch — yet it is a
number that does not lie in its own favour.

**How to do it properly — two corpora that never fold into one number.**

*Corpus A, expensive and honest:* reverting real fixes from our own history in an isolated
worktree. The difficulty is real, there is no contamination (the code is private), the classes
are taken from the roots map. Target — 40–60 cases.

*Corpus B, cheap and frequent:* targeted mutants by lens (`cargo-mutants`, `Stryker`).

*The link between them:* `k = recall(B) / recall(A)`. All cheap measurements are divided by `k`
and published together with it. Without calibration the mutant figure is advertising.

**Run rules without which the figure will lie:**
- **blinding**: no file history, no diff, no telling branch name;
- **the scoring rule is written down BEFORE the run** (file and mechanism, not "roughly there");
- the judge is one who has not seen the list of seeds;
- the result is published **by defect class**, not as one number: the overall mean hides classes
  with zero recall;
- classes we cannot seed (architecture, concurrency, layout, localisation) are marked with a
  "not measured" row — not "100%";
- fewer than ~100 cases does not let you tell 50% from 70%: 20 seeds give ±20 points.

**Closed when:** there is a share of found by class on corpus A, `k` is computed, and from both
numbers it is clear what the result depends on — block size, hypothesis quality or defect type.

**Cost:** corpus A — mainly human work (selecting and reverting fixes); runs ≈ 1 million tokens
for three blocks.

## Direction 2. Check portability to another language

**What is already known.** The kit has been through three projects: A (27 blocks of 27, 313
findings), B (8 blocks of 13, 210 findings) and C. Portability **between projects is confirmed
by practice**, and the share of rejected findings coincided on all three — about 3%.

**Why a direction then.** All three projects are TypeScript, all by one author, and part of the
code in them was written by the same AI that then reviewed it. What remains unchecked is exactly
what makes the claim "in any project" strong: another language, someone else's code, someone
else's conventions.

**How.** Run one block on a live open-source repository in another language (Go or Rust),
someone else's and unfamiliar. Look not at the findings but at the tooling: where the readability
ceiling lied, where `git ls-files` gave the wrong thing, where the prompt demanded something the
project does not have.

**Closed when:** a block has been passed on someone else's repository **in another language**
without changes to the tool, and all discovered differences are either removed or named in the
README as limitations. Candidates for checking: the readability ceiling (6000 lines was derived
from TS — in Go and Rust the density of meaning per line is different), line count as a measure
of volume, the behaviour of `git ls-files` with submodules.

## Direction 3. Regression is detected by gates, not by a new review

**Why.** Today "the fixed thing broke again" is detected by nothing. The register learns about
it only if a person files the finding anew — that is, it does not learn. This is a hole in the
method's main promise: a defect class is closed by a guard, but nobody checks that the guard is
alive.

**What is already known.**

- **syzbot** closes a bug not by word but by fact: `#syz fix: <commit title>` — and then the bot
  itself tracks when the commit reaches all tracked branches. A defect's return creates a **new
  card**, not a silent reopening of the old one: "new similarly-looking crashes create a new
  bug". A separate detail — `#syz invalid` does not silence forever.
- **DefectDojo** solves this by re-import: create / ignore / close / **reopen**, where
  "previously closed findings reappearing in a new scan are automatically reopened", while
  accepted risk and false positives are not automatically resurrected. The similarity key is a
  `hash_code` from a set of fields **configurable per source**. ⚠️ Changing the set of fields is
  not retroactive.
- **ESLint bulk suppressions** give a ready form of the gate "the rule became unnecessary": a
  file `eslint-suppressions.json` with a counter per pair "file × rule" and **exit code 2 if a
  suppression is no longer needed**. Betterer commits `.betterer.results`: worse — an error,
  better — the snapshot is updated.
- **What nobody has:** a gate "the class is closed by a rule, and the rule disappeared". The
  closest is `Orphaned` in OpenFastTrace: "an item covers a non-existent one".

**How to do it.**

1. The `rule` field stops being a string and becomes a **checkable pointer**: the path to the
   guard file (a test, a linter rule, a gate script) plus, where possible, the rule name inside
   it.
2. `check` verifies that what is pointed at exists. Gone — the class has stopped being closed,
   and this fails the check, like `orphaned` at OFT.
3. Regression is caught not by review but by the ordinary run of the project's gates: the guard
   goes red — the defect is back. It is enough for the tool to be able to say **which class** is
   assigned to which guard, so that a red guard immediately names the root and the past
   findings.
4. A return is filed as a **new finding** with a link to the previous one, not by reopening the
   old one: that is how syzbot does it, and it is more honest — a returned defect usually came
   back by another route.

**A guard can be a variant-analysis query.** For a class that cannot be closed by a test, the
guard is a Semgrep rule or a CodeQL query in the repository: the found defect is turned into a
query, the query is run over all the code and in CI (the practice of Trail of Bits and GitHub
Security Lab). There are no peer-reviewed measurements of yield, but it is exactly the form
"third repeat → a rule". The pointer already supports any file; all that is needed is for the
project to run such rules in its gates.

**Done in 0.3.0:** the guard's path is checked for existence, a deleted guard fails the check.

**Closed when.** `check` distinguishes three states: the class is closed and the guard is in
place; the class is closed but the guard has disappeared (fails); the class is not closed (fails
from the third instance). And there is at least one case where a red guard led to a new finding
with a link to the previous one.

**Cost.** Small: one field, one existence check, an edit to the fixer's prompt. The main work is
agreeing how to write the pointer for different kinds of guards.

**Pitfalls.**
- The temptation to reopen the old finding: the history is lost and the count "how many times it
  came back" breaks.
- A pointer to a rule that exists but is disabled in the configuration: a file existence check
  will not catch that.

---

## Direction 4. Third layer of coverage: a file that no question touched

**Why.** Right now there are two denominators: files (what was opened) and hypotheses (which
questions were answered). There is no link between them. A file can lie in a block, count as
read — and fall under no hypothesis: formally covered, in substance not.

**What is already known.**

- **OpenFastTrace** has the richest vocabulary of states: outgoing `Covers`, `Predated`,
  `Outdated`, `Ambiguous`, `Unwanted`, `Orphaned`; incoming `Covered Shallow`, `Covered
  Unwanted`, `Covered Predated`, `Covered Outdated`; aggregates `Undercovered`, `Overcovered`,
  `Deep Coverage`. The main thing — **the cascade is solved**: an item with intact direct coverage
  but a broken descendant is marked "not ok (transitively)", and the total counts separately:
  `123 total, 5 direct, 2 transitive`. Their own honest limitation: the needed number of incoming
  links cannot be predicted, and they do not try.
- **spec-kit `/analyze`** gives a report form: a findings table with stable IDs, **Coverage
  Gaps in both directions** (a requirement without tasks AND a task without a requirement), an
  Unmapped section, metrics with Coverage %, a ceiling of "no more than 50 findings" with
  overflow.
- **DO-178C** gives what the others lack: three different diagnoses for code without a
  requirement — dead (an error, delete), deactivated (not an error, isolate and justify),
  extraneous. The conclusion is direct: "uncovered" cannot be kept as a single status.

**How to do it.**

1. A hypothesis verdict gets an optional field "proven by" as a list of files — the agent names
   them anyway, one only has to recognise them.
2. The coverage report prints **both sides**: a file named in no verdict, and a hypothesis that
   referred to no file. The second half is no less important: a hypothesis without files is a
   question answered in the air.
3. Transitive uncoveredness is counted separately from direct and printed as a separate line,
   otherwise the very first run will drown in the cascade.
4. A "residual" artefact appears — a file with the list of the uncovered, like `residual.diff`.

**Closed when.** The report prints both sides and the residual as a separate file, and
transitive defects are not mixed with direct ones.

**Cost.** Medium: recognising file references in verdicts is the most fragile part, because it
depends on how the agent writes.

**Pitfalls.**
- Demanding formal markup from the agent — it will start imitating it. Better to recognise how
  it writes now and refine the prompt by results.
- Confusing "the file is not named" with "the file is not relevant to this question": some files
  legitimately have no hypothesis of their own (configuration, types), and for them a status like
  DO-178C's deactivated is needed.

---

## Direction 5. The seeker's precision is measured and changes the prompt

**Why.** Rejected findings are stored with a reason but affect nothing. We do not know on which
block the hunter is more precise and on which the manifest asks for the wrong thing.

**What is already known.**

- **The only published formula with thresholds** — Google Tricorder:
  `not-useful rate = NOT USEFUL / (NOT USEFUL + PLEASE FIX + APPLY FIX)`; ≥10% — the analyser
  is on probation, >25% — may be switched off. The key thing in it is **the denominator**: only
  findings on which there was an action are counted; silence does not count. Acceptance of a new
  analyser — "actual issue at least 90% of the time".
- **The practice "fix the rule, do not punish the source" is confirmed**: Google AutoCommenter
  found that about 80% of predictions below the common confidence threshold were correct, and
  made **its own threshold per rule**, while muting bad subclasses without retraining.
- **Code4rena** counts `signal` = valid / all submitted (only High and Medium, `null` until
  three submissions) and limits by it **the right to submit**: up to 0.2 — one finding, 0.2–0.4 —
  two, above — ten.
- **HackerOne** counts a **signed** mean (−10 for spam, +7 for resolved) — harsher on junk than a
  share.

**How to do it.**

1. Count from the register the share of confirmed per block and print it in `status`. The
   denominator — after Tricorder: only findings that received a verdict; "did not get round to
   it" does not count.
2. Do not enable the metric while a block has fewer than three findings: on one or two it is
   noise.
3. The reaction is **an edit to the manifest or the prompt**, not a limitation of rights: we have
   one seeker, and there is nobody to punish. A low share means the hypotheses ask for the wrong
   thing.
4. Close the vocabulary of rejection reasons: only "does not reproduce" and "severity
   overstated" go into the metric, while "already fixed" and "outside the block's subject" do
   not, otherwise the metric measures the register, not the hunter.

**Closed when.** `status` prints the share of confirmed over the latest blocks, and at least one
decision to edit a manifest or a prompt has been made on it.

**Cost.** Small for the count, the main part is in the discipline of filling in rejection
reasons.

**Pitfall.** Google's thresholds are computed on tens of thousands of reviews a day. Our volume
is three orders of magnitude smaller, and the percentages themselves cannot be transferred — two
rules are transferable: do not enable the metric before three findings and do not count silence in
the denominator.

---

## Direction 6. Run archive: from a closed block the task can be reconstructed

**Why.** Today two questions cannot be answered: which wording in the manifest produced a
finding and why the agent walked past. The agent's report exists, but the task does not: the
prompt is assembled on the fly and saved nowhere. So editing the manifest by results can only be
done from memory.

**What is already known.**

- **revmux** writes a `manifest.json` stating which layer gave each piece of the prompt, **and
  the hash of its content**; variables are expanded in paths, not in content; the raw output of
  agents is saved verbatim, retries separately.
- **SWE-agent** replaced the `message` field in the trajectory format with `query`, because the
  former was approximate and pointed at the next step: from it one cannot reconstruct what the
  model saw at this one.
- **A cache key that includes the hash of prompt content** is found at Bazel, Nix, pre-commit and
  revmux: edit the template — everything saved is invalidated.

**How to do it.**

1. `prompt` can write the assembled task next to the block's report, not only to standard
   output.
2. The block state stores **the hash of the manifest and the role templates** at the time of the
   pass. Editing the manifest after the pass is the same case as editing files: the block is no
   longer the one that was passed, and `check` must notice (the mechanism already exists — the
   fingerprint of what was reviewed; it needs extending to texts).
3. The agent's report and the assembled task live as a pair: for any closed block exactly what the
   agent received can be reconstructed.

**Closed when.** For a closed block the exact task can be produced, and `check` catches an edit
to the manifest or the prompt after the pass.

**Cost.** Small. The main decision is whether to store the tasks in the repository (they are
bulky) or nearby, outside the tree.

**Pitfall.** The task contains the invariants and the manifest in full — when the repository is
published this carries the project's internal rules outside. Only the hash should be stored in the
tree, and the text itself — in the same place as the reports, with the same access mode.

---

## Direction 7. A block that looks at two repositories

**Why.** The most expensive mistake in the method's whole history: the verifier confirmed by
execution a defect in the neighbouring service on a working copy that was twelve days behind.
The rule is written into the prompt, there is a guard on freshness — but a block whose subject
lies in two repositories is not supported by the kit: coverage is counted from a single
`git ls-files`.

**What is already known.**

- The canon is the same for everyone who solves this task: **store the pinned SHA of the
  neighbour and check it at start**, refusing on divergence. A submodule (gitlink `160000`),
  `west.yml` (Zephyr), the `repo` manifest (Android), `MODULE.bazel.lock` (SHA-256),
  `flake.lock` (tree hash).
- `buf breaking --against '.git#branch=main'` stores no base at all — it pulls by reference,
  i.e. the comparison is always against the current state.
- **Contract testing** (Pact) moves the compatibility matrix into a broker and answers the
  question "can we deploy" with a separate command.
- There is no direct tool for "review coverage across several repositories". The closest in
  form are SonarQube portfolios (a list of "project, branch" pairs), in meaning — CodeQL MRVA.

**How to do it.**

1. The block declares external dependencies explicitly: repository, branch, and what exactly is
   the subject there (paths). Not the whole neighbouring repository, but its part.
2. Before issuing the prompt the tool requires a `fetch` and **checks freshness** — the already
   existing staleness gate is applied to every declared neighbour, not only to one's own tree.
3. The neighbour's coverage **is not counted**: its own review counts it. Our block is
   responsible for the seam, and in the report it must name which version of the neighbour it
   looked at (the pinned SHA).
4. A finding in the neighbouring repository is filed with a link to its commit and handed over
   there — it cannot be fixed here.

**Closed when.** The block "contract with the neighbouring service" is passed routinely, the
report names the neighbour's SHA, and an attempt to pass it on a stale copy fails the check.

**Cost.** Medium: the main work is deciding what to do with findings that live in someone else's
repository and are fixed not by us.

**Pitfall.** The temptation to pull the neighbouring repository into one's own coverage — then
the denominator becomes undefinable and the responsibility smeared. The seam is checked, the
neighbour's contents are not.

---

## Direction 8. Two people run the review at once

**Why.** The method was written for a single session going sequentially. As soon as there are
two participants — a human and an agent in another tree, or simply two people — the state in git
starts fighting itself. This is not a hypothesis: three specific files conflict, and one of them
conflicts always.

**What will break — by name.**

| file | how it is written | what will happen |
|---|---|---|
| `reports/<BLOCK>-*` | a file per block | **already safe** |
| `journal.md` | appending to the end | a conflict at the tail, cured by `merge=union` |
| `findings.jsonl` | **rewritten entirely** | a conflict on the whole file; `union` will not help — this is not appending |
| `state.json` | a whole snapshot | a conflict on every parallel status change; `union` on JSON gives invalid JSON |
| `coverage.tsv` | derived from the block definition | a conflict that carries not one bit of information |

Two things already work in our favour: the finding identifier is sharded by block (`H1-001`), so
participants on different blocks will not collide them, and the import has a rudiment of
optimistic locking — though one that sees only its own tree.

**What is already known.**

- **`merge=union` is fit only for line-based files that are appended to.** Two caveats: if both
  sides edit one line differently, union silently keeps both without a marker; and **GitHub does
  not apply a custom `.gitattributes` when merging via the web** — such files must be merged
  locally.
- **A workaround for the shared file, proven by practice:** towncrier (Twisted, pytest, pip) puts
  a fragment file per change instead of a shared journal — "two PRs adding two different files
  cannot conflict". In audit the same: Code4rena — an issue per finding, Spearbit — a branch per
  file, a finding is first a comment on a line.
- **git-bug** states the main lesson directly: a snapshot cannot be stored, what is stored is a
  **series of edit operations**, and the state is compiled from them; the order is by logical
  clocks, because system time cannot be trusted in distributed work.
- **Claiming a block needs no infrastructure:** `git update-ref <ref> <new> <old>` is a built-in
  compare-and-swap, and zeros in `<old>` mean "make sure the ref does not exist yet".
- **A stuck participant is everywhere cured by lease expiry, not by manual unlocking:**
  visibility timeout in queues, `SKIP LOCKED` in Postgres, TTR in beanstalkd. One condition — the
  heartbeat is more frequent than the lease term.
- **Being first in time is rewarded nowhere.** Code4rena splits the reward between duplicates
  with decay, and gives the bonus not to the first but to the one whose wording was taken into
  the report; a weak wording gets partial credit but goes into the denominator. Sherlock requires
  a duplicate to meet **all three conditions** — name the root, name at least medium impact and
  name a working path; the group is assigned the **highest** severity among its members.
- **Disagreements are everywhere arranged the same way:** a short window, a named decider, a
  deviation from the rule is documented by template, and disagreement **costs** — at Sherlock an
  escalation is paid for with reputation and is non-refundable.
- **About parallel agents Anthropic writes directly:** work must be split by context boundaries,
  not by roles; the split "planner / executor / tester / reviewer" spends more on coordination
  than on work, and what is worth parallelising is independent branches and **verification as a
  black box** — it does not need the implementation context.

**What follows from this for our scheme.** The pair "hunter → verifier" is exactly their
permitted case: the verifier works as a black box and does not need the hunter's context. And
"hunter and fixer in parallel on one block" is their forbidden case, and it is worth writing down
as a rule rather than leaving to discretion.

**How to do it — in ascending order of cost.**

1. **`.gitattributes`: merge the journal by union.** One line.
2. **Remove the coverage map from the repository.** It is derived from the block definition;
   it conflicts while carrying no information. Generate on demand.
3. **The rule "one block — one participant"** at the entry point. By agreement it removes most
   cases: block files do not overlap, identifiers are sharded.
4. **Claiming a block with a separate file** `claims/<BLOCK>.json`: who, when, until what
   deadline. Different files do not conflict. Deadline expired and not extended by a journal entry
   — the block is free; there is deliberately no manual unlocking.
5. **Stop rewriting the summary register.** More honest — remove it altogether, leaving
   `reports/<BLOCK>-findings.jsonl` as the only source, and generate the summary.
6. **Block state is also derived**, after git-bug: the truth is in the block files, and
   `state.json` is assembled. The minimal variant — split into a file per block.
7. **Deduplication by root**, grouping by the Sherlock rule, the group's severity is the highest
   of its members. Do not introduce first-in-time: it provokes haste instead of quality.
8. **An objection window with a named decider** and a template for deviating from the rule.
9. **A check against `origin/master` over the block's files at the start of a pass** — as a
   mandatory line in the journal. With two participants this stops being a recommendation and
   becomes a condition of correctness: someone else's fix is already in the shared branch, and
   your tree does not have it.
10. **Do not parallelise the hunter and the fixer on one block.** The verifier — only as a black
    box: it does not read the hunter's report before its own pass, and this also strengthens the
    method.

**Closed when.** Two participants pass two different blocks at the same time, merge without
manual conflict resolution, and a claimed block abandoned midway frees itself.

**Cost.** Items 1–4 are cheap and done in one go. Items 5–6 are a rework of the state format,
i.e. a breaking change with a migration; worth taking on only when there are three participants
or when two really go into one block.

**Pitfalls.**
- `union` on JSON is silent file corruption. Apply only to the line-based journal.
- A claim without a deadline turns into an eternal lock after the first session drop.
- The temptation to reward the first finder: all competitive audits abandoned it, because being
  first encourages speed, and what is needed is precision.

---

## Direction 9. Economics: what it will cost and when it stops paying off

**Why.** We know the cost of a block and do not know the cost of a review. To the question "how
much will it cost to pass a project of ten thousand files" there is no answer, and whether the
method gets taken up at all depends on it.

**What is already known.**

- **The traversal architecture decides the cost more strongly than the model.** On the same task
  set AutoCodeRover costs $0.43 per task, SWE-agent — $2.51 at comparable quality: the difference
  in tokens is 6.6×, in money 5.8×.
- **The spread matters more than the mean.** Agentic tasks spend roughly a thousand times more
  tokens than an ordinary dialogue; **runs of the same task differ up to 30 times**; the cost
  driver is input tokens, not output; accuracy **peaks at medium spend and then saturates**;
  models systematically underestimate their own spend.
- **There is no superlinear growth of cost with the number of files in the literature — there is
  a fall of quality at a fixed cost.** Growing the task width from one file to four drops
  solvability from over 70% to 23%; degradation with input length is monotonic for all tested
  models. Economically this is the same thing: to hold quality, the number of blocks must grow
  faster than just "files divided by 22".
- **The traversal order has a measured cost.** The 20% of files with the highest predicted number
  of defects contained 71–92% of those found, on average **83%** (Ostrand, Weyuker, Bell, IEEE
  TSE 31(4), 2005). Code with an alarming "health" level carries **15 times more defects** and
  requires **124% more time** per task (Tornhill & Borg, TechDebt 2022).
  ⚠️ The second metric is proprietary, its numbers do not transfer to a home-made surrogate.
- **An exhaustive pass is a decision that gets justified.** The audit sampling standard does not
  directly extend to an exhaustive check: it is not the default but a choice, and the sample size
  is derived from risk.
- **Our blocks are large by the standards of human review.** The recommendation from a study of
  2500 reviews is 200–400 lines per sitting, and at a pace faster than ~450 lines an hour the
  finding density is below average in 87% of cases. Our ceiling of 6000 lines is 15–30 times
  above that. Not a verdict — an agent reads differently — but it explains why a block "read" and
  "understood" can diverge.

**The cost model worth adopting.**

```
C_review = Σ over blocks [ C_hunter(b) + C_verifier(b)
                          + p_fixed(b) · r(b) · ( C_fix(b) + C_fix_review(b) ) ]

C_agent(b) = β + α · L(b)
```

where `β` is the block constant (invariants, manifest, role template — independent of size),
`α` is the spend per unit of readable, `r(b)` is the number of rounds "fixed → the diff was
read".

**Calibration is a hypothesis, not a measurement.** From our 400–700 thousand tokens on 17–27
files at `β ≈ 250 thousand` we get `α ≈ 15 thousand` per file. To separate `β` and `α` honestly, two
blocks of deliberately different size with token logging are needed — the smallest and the
largest. Until then any extrapolation remains a rough guess.

**A rough estimate on a large project** (at our own rates: an overview block — two agents, a
block with regressions — twelve, the share of fixable — one in thirteen): 1803 files → 67 blocks
≈ 184 agents ≈ 100 million tokens. **10,000 files → about 455 blocks ≈ 1260 agents ≈ 0.7
billion tokens**, roughly 190 hours at five parallel agents.

The linear term scales honestly. Three things break: `r(b)` — coupling grows faster than size;
`β` — the cross-cutting context swells; and quality, which at the same budget falls.

**The decision metric is not the cost but the cost of a finding.**

```
CPF = C_review / number of findings that survived to a fix
```

The denominator is exactly that: a rejected finding cost as much as an accepted one, and brought
no value.

**The stopping rule.** The method stops paying off not by the share reviewed, but when a block's
`CPF` exceeds the cost of catching the same defect by a guard in CI, a test or auto-review on
changes. The practical criterion: a block where three rounds in a row gave no finding **of a new
kind** (not another instance of a known root) is closed by an overview, not by a full pass.

**Where the tokens go — the analysis of 24.09** ([`docs/token-economy.md`](docs/token-economy.md)).
The cost of a block does not depend on its size, the static prompt prefix is units of thousands
of tokens out of hundreds; so the spend goes on tool results: run output, `grep`, repeated
reads. Eight hypotheses in order of expected saving, each with how to measure it:
a baseline measurement (without it the rest is guesswork) → cache misses by subagent TTL (35–50
minutes per block versus a TTL of 5 minutes) → filtering gate output with a hook → "one file —
one read" and notes on disk (by others' data −9…50% of input) → a delta pass for top-up import
and fix review → signatures instead of full `ref_paths` → a cheap model on the fixer, not on the
hunter → trim the verifier on blocks without serious findings. What not to do — there too: do
not compact the hunter's context, do not remove the verifier, do not move the hunter to a cheap
model, do not cut blocks smaller to save (the cost does not depend on volume, so more blocks are
more expensive).

**How to do it.**

1. **Log the spend per block** — tokens and time, into the journal, automatically. Right now
   this is done by hand and therefore not always.
2. **Measure `β` and `α`** on two blocks of deliberately different size.
3. **A per-block budget with auto-cutoff.** At a thirty-fold spread one block may cost as much as
   twenty, and we learn about it after the fact. The form is known: a soft limit → a warning, a
   hard one → a stop, plus a breaker by spend rate and by growing context.
4. **Traversal order: risk first, change frequency second.** Our current order is chosen by the
   cost of an error (access, core, writes, money) — that is more correct than going by hotspots:
   a hotspot catches a defect, the cost of an error catches **irreversibility**. Take change
   frequency as the secondary key within equal risk.
   **Measured 23.09 on the first project** — as a prediction, not in hindsight: the history was
   split in half, ranking from the first half, from the second — where the fixes landed. The top
   10% of files collect 34% of future fixes by change frequency, 29% by size, 6% at random; the
   product "frequency × size" added nothing to frequency. Agrees with the literature (Nagappan &
   Ball 2005, Moser 2008, Graves 2000). The `order` command prints blocks by risk, within — by
   the total change frequency of their files over a window.
5. **Compute `CPF` per block** and print it in the status. This is the only number by which one
   can decide whether to continue the exhaustive pass.

**Closed when.** `β` and `α` are known from a measurement, the spend is written automatically,
a block has a budget with auto-cutoff, and `CPF` is computed and takes part in the decision on the
next block.

**Pitfalls.**
- **The temptation to save with a cheap model.** On synthetic data the difference is nearly
  invisible, and on real changes the best result falls by 92% — the conclusion "the cheap one is
  no worse" holds only in a regime where both barely work.
- **Averaging the cost of a block.** At a 30-fold spread the mean describes nothing; planning must
  go by the upper quantile.
- **Counting `CPF` over all findings.** Only over those that survived to a fix, otherwise the
  metric rewards verbosity.
- **Extrapolating linearly beyond what was checked.** The formula is honest inside the range it
  was calibrated in, and `r(b)` in it is a stub.

---

## Direction 10. What remains when the review directory is deleted

**Why.** The method ends with deleting its own directory — and that is right: review documents
whose statuses nobody updates describe the fixed as open. The industry measures this trouble:
findings older than a year are called security debt, half of organisations carry it, and the mean
age of an open finding in some industries reaches 276 days.

But in the previous edition the method contradicted itself: the working procedure required **not
deleting** rejected findings — "otherwise the next review will find the same thing" — while the
finale deleted them together with the directory. The contradiction has been removed, and it is
worth keeping as a separate direction: deciding what exactly survives the deletion turned out to
be a substantive task.

**What is already known.**

- **Re-verification at auditors is a narrow and cheap phase, not a new pass.** The wording is
  direct: "retesting is only re-evaluating the previously reported issues, not searching for
  new issues". The numbers of one real case: the original audit — 45 days, the re-verification
  seven months later — **5 days**, about eleven percent of the effort. And the result is not a
  separate document: **the original report** is updated, each finding gets "fixed", "not fixed"
  or "risk accepted".
- **A threshold "N% of the code changed" does not exist, and this is written in plain text** in
  the assurance continuity standard: there is no way to determine from the size of a change how
  large its impact is. A broad edit may touch nothing important, a targeted one may change
  everything.
- From there, three things we did not have: **accumulation of small changes is a reason in its
  own right** for a re-examination; **elapsed time is a separate criterion**, regardless of the
  content of the edits; the result of a re-verification becomes **the new baseline for
  comparison**.
- **Regulation sets a cadence and a list of events, not a percentage:** "no less than once every
  twelve months and after significant changes", where significant is defined by a list.
- **Stale trackers are cured by automation**, and the best variant is not closing but returning:
  in Chromium findings older than 90 days go to the archive, and some — back to "untriaged".

**How to do it.**

1. **One immutable summary file survives the deletion.** It has no statuses that can go stale,
   because it describes the past:
   - the date and the **base commit** — from which revision everything was counted;
   - the blocks and their acceptance criteria — what exactly counted as checked;
   - **rejected findings with reasons** and accepted risks — exactly what will otherwise be found
     anew;
   - how each class is closed: a guard, a test, a rule.
2. **"Stale" becomes checkable:** `git log <base commit>..HEAD` over the block's files shows how
   much changed since they were read by eye. Without the base commit this is undefinable in
   principle.
3. **Reasons to pass again — as events, not percentages:** the system boundary changed; a new
   class of threats appeared; many small edits accumulated; the term elapsed (guideline — a year).
4. **A repeated pass opens a new block card**, not a reopening of the old one.

**Closed when.** There is a command that assembles the summary and prints it as one file, and
from the summary of a past review one can say within a minute which blocks have gone stale the
most.

**Cost.** Small: the summary is assembled from what already lies in the register and the state.

**Pitfalls.**
- Leaving a live tracker in place of the summary — a return to exactly the disease the method
  gets rid of by deleting the directory.
- Forgetting the base commit: without it the summary is pretty and useless.
- Assuming a repeated pass is cheap automatically: it is cheap **if** there is something to start
  from, and costs as much as the first if the summary was not saved.

---
## Direction 11. The fix phase as a gate

**Why.** The method finds faster than the project fixes, and this is not a peculiarity of one
project. The first project: 77 findings on 5 blocks, 9 fixed (12%). In the same project the
exhaustive file-by-file pass in its first variant brought not one of hundreds of cards to a fix,
and the AI reviewer's comments in PRs accumulated over two months to 1147 untriaged threads. A
finding that did not reach a fix is debt, and in a month the register describes code that no
longer exists.

**What is already known.** In the same project the wave rule worked: the next wave does not
start until the serious items of the previous one are in the main branch. The methods that bring
things to a fix best are those where the finding and the fix go in one pass (lenses, vertical
slices, an audit with a phase plan).

**How to do it.**

1. In `blocks.json` — a threshold `fix_gate` (default `high`).
2. `set-status <ID> running` refuses if the passed blocks have open findings at the threshold
   level and above, and names them. The way out — fix, defer with a reason (`deferred`) or
   reject; "deferred" requires a reason and goes into the summary.
3. `status` prints the fix debt as a separate line: how many are open by level and in how many
   blocks.
4. `check` warns if an open finding is older than N days (by `imported_at`).

**Closed when.** The gate is in place, the debt is visible in the status, and on the next project
the share fixed by the time the next block starts is no lower than 80% for the threshold.

**Cost.** Small: one check on status change and a line in the status.

**Pitfalls.**
- Turning `deferred` into a rubbish bin. Deferred with a reason is lawful, without a reason — a
  refusal, and in the summary the deferred are listed by name.
- Setting the threshold at `medium`: then the review will stall on small stuff, and people will
  start going around the gate.

---

## Direction 12. Seams between blocks: a change coupling map

**Why.** A block is a unit inside which the agent sees everything; the seam between two blocks
is seen by nobody. The measurement on the first project: of 553 file pairs that change together
at least three times, **423 (76%) lie in different blocks**. Most are shared hubs (the DB
schema, dictionaries), but even without them **38 strong pairs** remain, and among them — exactly
the places where the project has already been burnt: permissions between a token and an agent
tool, the domain model and its storage (silent loss of fields).

**What is already known.** Change coupling (Gall 1998; Zimmermann et al., ROSE, TSE 2005) finds
dependencies invisible to code analysis: in the three best suggestions — the needed place to
change in >70% of cases. Groups of coupled files explain 20–61% of maintenance effort (Xiao, Cai,
Kazman, ICSE 2016). Computed from `git log` in minutes, without dependencies.

**How to do it.**

1. A `coupling` command: file pairs from different blocks, joint changes ≥ K and a share ≥ 50%;
   mass commits (more than M files) and shared hubs (a file linked to ≥ 6 blocks) are cut off
   and printed separately.
2. For each pair — a suggestion: add the neighbour to the block's `ref_paths`, and to the
   manifest — a hypothesis about the transition ("value X, leaving A, reaches B without loss").
3. A cluster of pairs between two blocks is a signal to open a **seam block** (a vertical slice):
   one chain from input to storage, with one named instance of data along the whole path.
4. The map is recomputed on `coverage` and goes into the summary.

**Closed when.** The command exists, pairs go into `ref_paths` and hypotheses, and at least one
seam block has gone through the full cycle with findings.

**Cost.** Small: parsing `git log` and printing.

**Pitfalls.**
- The noise of mass changes (codemods, formatting) produces false pairs — a cut-off by commit
  size is mandatory.
- New code without history gives no pairs: the map complements the block cut, it does not
  replace it.
- Shared hubs are linked to everything; putting them into every block's `ref_paths` means
  bloating the context to no benefit.

---

## Direction 13. A threat model as a block type

**Why.** Access and trust-boundary blocks are currently passed with the same hypotheses as the
rest. For security there is an industry standard — a threat model by data flows: draw where the
data comes from and where it crosses trust boundaries, and walk each boundary by threat class
(STRIDE: spoofing, tampering, repudiation, information disclosure, denial of service, elevation
of privilege).

**What is already known.** Shostack, *Threat Modeling* (2014); the practice of Microsoft SDL.
The data is scant and sobering: on students recall 0.36 at precision 0.81 (Scandariato et al.,
2015, from a retelling). So the method does not replace reading code, but gives **a list of
questions** that otherwise would not be asked.

**How to do it.**

1. A manifest template `assets/threat-model.example.md`: a flow diagram as text (who → what →
   where, where the trust boundary is), and for each boundary — hypotheses across the six STRIDE
   classes.
2. The hypotheses are numbered as usual and go through the same verdict gate.
3. The block's output is not only the findings but the diagram itself: it outlives deleting the
   review directory and goes into the project's documentation.

**Closed when.** The template exists, and one access block has been passed with it, with findings
that were not there with an ordinary manifest.

**Cost.** Small for the kit, noticeable for the human: the flow diagram is drawn by someone who
knows the system.

**Pitfalls.**
- A diagram drawn from memory rather than from the code is a threat model for another system.
  The flows are checked against the code by the hunter, a divergence is a finding.
- Six classes per boundary quickly give a hundred hypotheses; take only the applicable ones, close
  the rest with a verdict "not applicable" with a reason.

---

## Direction 14. A lens bank — a source of hypotheses for manifests

**Why.** A lens is one property checked across all the code: access, money, privacy, data
integrity, reliability, performance, tests as an asset, truth of documentation. In the first
project lenses found in a day an elevation of privilege, a spend-limit leak and silent data loss.
The kit already has lenses in two forms — the cross-cutting blocks of phase 1 (the "access" block
is the security lens) and the threat model (direction 13) — but **the questions of each lens are
written into the manifest anew**. In the first project there are 26 of them (16 for the site,
10 for the core), with primary sources: OWASP ASVS, Google SRE, Google's review checklist, Rust
API Guidelines, protobuf Dos and Don'ts.

**What is already known.**

- **A checklist by itself is no better than reading without a method; scenarios are better**
  (Porter, Votta, Basili, TSE 1995; the meta-analysis of perspective-based reading — no clear
  effect, Ciolkowski 2009). Our lenses worked not as tick-boxes but as questions in the form
  "input → expectation → probe". The bank must store them in this form.
- **A lens does not exhaust an area:** the money lens gave 6 findings, a block with hypotheses on
  the same area two months later — 21, with no overlap (`docs/review-methods.md`, section 2).
  So the bank is a source of hypotheses for a block, not a replacement for the block.
- **The second coverage denominator already exists** — hypotheses with verdicts; the bank only
  simplifies writing them and makes them comparable between projects.

**How to do it.**

1. `references/lenses/<property>.md` — one file per property: 10–20 questions in hypothesis
   form (what to check, how to prove, what counts as a finding), each with a source. The first
   ones: access, money, privacy, data integrity, reliability, tests as an asset, truth of
   documentation, trust boundary.
2. The manifest template gets a section "which lenses the hypotheses are taken from"; `prompt`
   changes nothing — the hypotheses are already in the manifest.
3. The coverage report by hypotheses prints which lenses the block applied; a lens never applied
   by any block of the project is a warning at the end of the review (a property nobody checked).
4. A run on a PR: the same files work as a questionnaire for reviewing one diff — in the first
   project 12 lenses handed out to four agents on one PR gave 14 findings on top of the
   auto-review.

**Closed when.** A bank of eight lenses with sources lies in `references/lenses/`, at least two
blocks have written manifests from it, and the coverage report names the unapplied lenses.

**Cost.** Small for the tool; the main work is translating the 26 project lenses into a common
form and cleaning out the project-specific.

**Pitfalls.**
- Turning the bank into a checklist the agent ticks through — that is exactly what does not work
  by the data. A question without "how to prove" does not get into the bank.
- Counting a lens as passed because its hypotheses stand in the manifest: a hypothesis is closed
  by a verdict, not by presence.
- Dragging the project-specific into the bank ("the council limit — 20 a month"): the bank is
  shared, the number comes from the invariants.

---

## Small but measured: the speed of `check`

On a real review (1750 files, 5 passed blocks, 77 findings) `check` takes ~7 seconds: 2251 git
calls, of which 958 are `hash-object` one file at a time for fingerprints, another 1204 are
`ls-files` per path pattern. Tolerable for now, but it grows with the number of passed blocks
and the width of `ref_paths`. The cure is known and needs no new dependencies: fingerprints — a
single `git hash-object --stdin-paths` for all files at once, composition — a single
`ls-files --stage` with pattern parsing in Python (`fnmatch` with pathspec semantics). Do it when
`check` becomes longer than people are willing to wait before a commit.

## What not to do

- **Turning it into a change reviewer.** The niche is densely occupied, and the method is not
  about that: diff review and an exhaustive inventory are different tasks with different
  economics. The same analyser yields about zero fixes in a batch run over the codebase and over
  70% on changes; our place is a one-off inventory with an exit into a guard, not a continuous
  mode.
- **A package in a shared package registry.** Since 0.4.0 the kit is a skill and is installed as
  a copy (`npx skills add`), into the project — so that the tooling version is pinned to the
  repository together with the state: a review runs for months, and an update "by itself" here is
  a defect.
- **Meetings to consolidate findings.** Independent reading matters more than discussion:
  inspection meetings add almost nothing to individual reading (Votta 1993; Porter, Votta,
  Basili 1995). Consolidation with us is done by the verifier over the files, not by a discussion
  between agents.
- **An exhaustive "file by file through a directory" pass as a mode.** On the first project 90%
  of its findings turned out to be repeats of twenty roots, and there are no direct measurements
  of the yield of such a pass in the literature. Blocks with hypotheses solve the same
  completeness task cheaper.
- **Dependencies.** Each drags an environment into someone else's project. The boundary is the
  standard library and `git`.
- **A web interface and a database.** For findings registers with deduplication and a lifecycle
  there are already mature platforms. Our state lives in git because it must survive a session
  restart and be readable by eye in a diff.
- **Automatic search without a human in the loop.** The precision of an AI reviewer on real
  changes is 3.56%, the share of false on real vulnerabilities is 84.82%. Human acceptance is not
  a temporary measure but part of the design.
- **Rewarding being first.** All competitive audits abandoned it: being first encourages speed,
  and what is needed is precision.
- **Saving with a cheap model on verification.** On synthetic data the difference is invisible,
  on real code the best result falls by 92%.

---

## Order

Reassembled 23.09 after the comparison of methods: the main hole turned out to be not in the
search but in the fact that what is found does not reach a fix, and in the seams that blocks cut
by design.

**Now (cheap and closes what already hurts):**

0. **Direction 9, the token measurement** — one block as is, with the spend broken down by axis
   (cache, tool output, re-reads). Without it all the saving hypotheses are guesswork, and the
   cheapest of them (the subagent cache TTL) is closed by a single run.
1. **Direction 11** — the fix phase as a gate. One check; without it every next finding is debt.
   The reason on `deferred` and fix review before `closed` are already there (0.5.0).
2. **Direction 12** — the change coupling map. Minutes of computation, and the block cut gets
   data about seams.
3. **Direction 9, item 4** — the `order` command: risk first, change frequency second (the
   measurement exists).
4. **Direction 10** — the summary that outlives deleting the directory.

**Next (requires a measurement or human work):**

5. **Direction 1** — first the cheap sample (59 files of closed blocks, by another model), then
   the corpus with known answers.
6. **Direction 13** — a threat model for the nearest access block; **direction 14** — the lens
   bank: the first eight of the project's 26, in hypothesis form.
7. **Direction 8, items 1–4** — two people run the review at once.
8. **Direction 3** — a run of the gates by root; variant analysis as a guard.

**Later, as needed:**

9. Directions 2, 4, 5, 6, 7, 9 (the rest) — portability, the third layer of coverage, seeker
   calibration, the run archive, multi-repository, economics. Each is useful, but none closes the
   hole that hurts today.

---

## How to use this document

Every direction has one format: **why** (from a fact, not from a wish), **what is already
known** (our experience and others', with sources), **how to do it**, **closed when**, **cost**,
**pitfalls**. If you add a direction — keep the format: without a "closed when" section it turns
into a wish, and without "pitfalls" it will be repeated with the same mistakes.

The sources for each item are in [`docs/prior-art.md`](docs/prior-art.md), our figures are in
[`docs/measurements.md`](docs/measurements.md). Neighbours on GitHub for each direction and the
checklist for opening the repository are in [`docs/open-source.md`](docs/open-source.md). If a figure in this file diverges from them,
they are right: here it can go stale, there it was taken with a method.
