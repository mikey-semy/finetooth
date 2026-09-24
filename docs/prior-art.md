[Русская версия](ru/prior-art.md)

# Who has already solved this

For each direction in [`../ROADMAP.md`](../ROADMAP.md) — what was found at others: working
mechanisms, published numbers, and methods recognised as unfit. Reconnaissance of 21.09.2026
over primary sources; full reports with URLs and dates are in the history of this commit.

Read it like this: **first the "what must not be used for measuring" section**, then the rest.
The costliest thing is not missing mechanisms but the ones that look working and lie.

---

## Direction 1. Measure the misses

### The main thing: recall cannot be measured directly

The denominator — all existing defects — is unavailable. Any working method substitutes a
sample with a known answer for it, and then everything hinges on one question: **does the
sample resemble real defects**. This is where most published numbers fall apart.

| measurement | result |
|---|---|
| Error Prone + Infer + SpotBugs on **594 real** defects (Habib & Pradel, ASE 2018, DOI 10.1145/3238147.3238213) | **4.5%** found, found by no one — 95.5%. Earlier work on synthetic sets claimed 64–99% |
| 8 fuzzers, 80+ years of CPU time, 50 organic CVEs (Bundt et al., ASIA CCS 2021, arXiv 2208.11088) | **not one** found, while the synthetic ones were being found |
| AI reviewers on a benchmark of real PR comments (c-CRAB, arXiv 2603.23448) | Claude Code 32.1%, Devin 24.8%, PR-Agent 23.1%, Codex 20.1%, **all together 41.5%** |

### What must not be used for measuring

- **Mills' remaining-defect estimate** (bebugging, IBM FSC-72-6015, 1972): `N̂ = S·n/k`. Rests on
  planted and real defects being equally hard — an assumption violated systematically and in
  one direction. Only the left half is usable: `recall = k/S` for a specific class.
- **Capture-recapture with two reviewers.** "One would be forgiven for concluding that CR
  models are not usable for two inspectors" (El Emam & Laitenberger, IEEE TSE 27(9), 2001).
  You need **≥4 substantially different** reviewers (Petersson et al., JSS 72(2), 2004). ⚠️ For
  us it is doubly dangerous: identical agents miss the same things, the overlap comes out
  artificially high, and the formula will say "almost everything found" exactly where both
  are blind to a whole class.
- **Mutation score as a reporting number.** 17% of real defects are coupled to no mutant at
  all (Just et al., FSE 2014); the correlation of the score with catching real defects
  weakens when test-suite size is controlled for (Papadakis et al., ICSE 2018). Mutations are
  an improvement tool, not a reporting one.
- **Synthetic SAST sets.** NIST itself on Juliet/SARD: "users should not extrapolate
  statistics… to production code". SWE-bench Illusion (arXiv 2506.12286): 76% solved without
  repository context, 32.67% of successes — the solution leaked in the task text.
- **SRGM** (reliability growth models) — about a different object, the assumptions do not hold.

### What works

- **Two corpora that do not add up to one number.** Expensive and honest: reverting real fixes
  from your own history (real difficulty, no contamination). Cheap and frequent: targeted
  mutants (`cargo-mutants`, `Stryker`, PIT, mutmut).
- **A calibration coefficient** `k = recall(cheap) / recall(honest)`; cheap measurements are
  divided by `k` and published together with it.
- **Detection efficiency** (Capers Jones): the share found before delivery in a 90-day window —
  the only metric with an honest denominator. Reference points: inspections >85%, static
  analysis >65%, a single form of testing <35%. ⚠️ The base is proprietary and not
  independently reproduced.
- **An LLM detector of equivalent mutants** (Meta ACH, arXiv 2501.12862): precision 0.79 /
  recall 0.47, with preprocessing 0.95 / 0.96. Equivalence in general is undecidable
  (Budd & Angluin, 1982), TCE catches about 30%.

---

## Direction 2. Transferability

### A myth worth debunking

The common numbers "400 lines in 60–90 minutes" and "70–90% defect detection" are attributed
to the Cisco/SmartBear study. **They are not in the primary source** — that is a marketing
page. In the chapter itself (2500 reviews, 3.2M lines, 50 developers, 2005–2006): volume under
review **<200 lines, ceiling 400**; pace **<300 lines/hour**; time **<60 minutes, ceiling 90**;
recommendation — **100–300 lines in 30–60 minutes**. Plus: **61% of reviews found nothing**,
and not a single review over 250 lines yielded more than 37 defects per thousand lines.

### A line threshold does not transfer between languages

826,259 pull requests, 10 languages (Kudrjavets, Nagappan, Rastogi, MSR 2022, arXiv 2203.05045).
Median lines per change: Shell 8, Ruby 13, JS/PHP 15, C/C++/Python 21, **TypeScript 35**,
C# 40, Java 43 — a two-to-threefold spread, significant. **Go and Rust are in none of these
works.**

→ Our threshold of 6000 lines is derived from TypeScript and transfers silently only to
TypeScript. Made configurable (`readable_lines` in `blocks.json`), the origin of the number is
recorded next to it.

### What breaks `git ls-files` — verified by experiment

| case | what happens |
|---|---|
| submodule (mode `160000`) | one entry in `ls-files`, a directory on disk → `IsADirectoryError` |
| symlink (mode `120000`) | read as a file, the target's content is counted **twice** |
| sparse-checkout | prints paths that are not on disk (visible only via `ls-files -t`, flag `S`) |
| file deleted from the tree but alive in the index | `FileNotFoundError` |
| Git LFS pointer | one line instead of the file |

→ **Fixed:** the file set is taken from `ls-files --stage` with submodules (`160000`) dropped,
content is read via `git show :path`, not `open()`. In 0.2.0 the symlink was dropped too, but
that way it fell out of the review entirely, and it could be redirected unnoticed. Now it is
in the set. There is no double counting: `git show :path` returns the link text for it, and the
fingerprint is also taken from the link text.

### Cross-repository freshness

The canon is the same everywhere: **store the pinned SHA of the neighbour and check it at
start-up**, refuse on mismatch. Submodule (gitlink `160000`), `west.yml` (Zephyr), the `repo`
manifest (Android), `MODULE.bazel.lock` (SHA-256), `flake.lock` (tree `narHash`).
`buf breaking --against '.git#branch=main'` stores no base at all — it pulls by reference.

There is no direct tool for "review coverage across several repositories". Closest in form —
SonarQube Portfolios (a portfolio = a list of "project, branch" pairs), in meaning — CodeQL
MRVA (up to 1000 repositories).

---

## Direction 3. Regression is caught by gates

- **syzbot.** `#syz fix: <commit title>` — from there the bot itself watches for the commit to
  reach all tracked branches, and **only then** closes. A returning defect creates a **new
  card**, not a silent reopen of the old one. `#syz invalid` does not mute forever.
  Bisection starts only if the defect has not reproduced for 30 days.
- **DefectDojo.** Four deduplication algorithms (`unique_id_from_tool`, `hash_code`, combined,
  `legacy`); hash fields are set **per source of findings** (`HASHCODE_FIELDS_PER_SCANNER`).
  Re-import is a ready-made regression gate: create / ignore / close / **reopen**; accepted
  risk and false positives are not resurrected automatically. ⚠️ Changing the hash fields is
  not retroactive — a recompute is needed.
- **Ratchets.** ESLint bulk suppressions: a file `eslint-suppressions.json`, a counter per
  "file × rule" pair, and **exit code 2 if a suppression has become unnecessary** — a direct
  model for the "rule has vanished" gate. Betterer commits `.betterer.results`: worse — error,
  better — the snapshot is updated. Sonar computes the Quality Gate over new code only.

**What nobody has:** a gate for "class closed by a rule, and the rule has vanished". Closest —
`Orphaned` in OpenFastTrace ("an item covers a non-existent one") and ESLint's return code 2.

---

## Direction 4. Two-way tracing

**OpenFastTrace** — the richest vocabulary and a ready answer about the cascade.

Outgoing states: `Covers`, `Predated`, `Outdated`, `Ambiguous`, `Unwanted`, `Orphaned`.
Incoming: `Covered Shallow`, `Covered Unwanted`, `Covered Predated`, `Covered Outdated`.
Aggregates: `Undercovered`, `Overcovered`, `Deep Coverage`, **`Direct Defect` versus
`Transitive Defect`**, `Forwarding`.

The cascade is solved in two ways at once: an item with intact direct coverage but a broken
descendant is marked "not ok (transitive)", and the total counts separately — `123 total,
5 direct, 2 transitive`. The authors' own honest limitation: "OFT cannot predict the exact
number of required incoming links… So OFT does not try to".

**spec-kit `/analyze`** gives the report form: a findings table `| ID | Category | Severity |
Location(s) | Summary | Recommendation |`, a **Coverage Summary Table**, a separate
**Unmapped Tasks** section, metrics with Coverage %, a ceiling of "no more than 50 findings"
with overflow.

**DO-178C** gives what the rest lack: three different diagnoses for code without a
requirement — dead (an error, delete), deactivated (not an error, needs isolation and
justification), extraneous (a certification finding regardless of whether the code works).
Conclusion: "uncovered" cannot be kept as one status.

---

## Direction 5. Calibrating the finder

**The only published formula with thresholds** — Google Tricorder (ICSE 2015, §IV-E):

```
not-useful rate = NOT USEFUL / (NOT USEFUL + PLEASE FIX + APPLY FIX)
≥10% — analyzer on probation
>25% — may be disabled immediately
```

The key thing in it is the **denominator**: only findings that were acted on are counted;
silence does not count. Admission of a new analyzer — "actual issue at least 90% of the time".
The system-wide background is about 5%, good analyzers 0–3%.

**The practice of "fix the rule, not punish the source" is confirmed**: Google AutoCommenter
found that about 80% of predictions below the global confidence threshold were correct, and
made **its own threshold per rule**, while muting bad subclasses without retraining.

**Code4rena `signal`** = valid / all submitted (High and Medium only, from finalised audits,
`null` until three submissions). It limits not money but **the right to submit**: null or <0.2 →
1 finding, 0.2–0.4 → 2, ≥0.4 → 10.

**HackerOne**: Signal — average reputation per report on a −10…7 scale (spam = −10,
resolved = +7), i.e. a **signed** average, not a share — harsher on junk.

**Sherlock**: the right to judge at 10 signal, to comment on others' at 100, a comment costs 2,
escalation is paid and non-refundable. There is a ready **Deviation Template**: applicable rule →
what would be normal → reasons for the deviation → final verdict.

⚠️ A caveat of scale: Google's thresholds are computed on ~50,000 reviews a day. Our volume is
three orders of magnitude smaller, so what matters is not the percentages themselves but two
rules — do not switch the metric on until three findings, and do not count silence in the
denominator.

---

## Direction 6. The run archive

- **revmux** (Go): `manifest.json` records which layer produced each piece of the prompt, **and
  a hash of its content**; variables are expanded into the path, not into the content; the raw
  output of agents is stored verbatim, retries separately.
- **SWE-agent** replaced the `message` field with `query` in the trajectory format in version
  1.1.0: the former was approximate and pointed to the next step, so it was impossible to
  reconstruct what the model saw at this one.
- **The cache key includes a content hash** — Bazel, Nix, pre-commit, revmux; at Anthropic the
  cache is keyed on the exact prefix `tools → system → messages`.

---

## Direction 8. Parallel work

**Merging state.** `merge=union` is suitable only for line-based files that are appended to,
and with two caveats: if both sides change the same line differently, union silently keeps
both without a conflict marker; and **GitHub does not apply a custom `.gitattributes` when
merging via the web** — such files must be merged locally.

**Avoiding the shared file.** towncrier (Twisted, pytest, pip) puts a fragment file per change
instead of a shared changelog: "two PRs adding two different files cannot conflict".
In auditing the same: Code4rena — an issue per finding, Spearbit — a branch per file (files
over 500 lines are split), a finding starts as a comment on a line.

**git-bug** states the main lesson outright: "it's not possible to store the current state…
Instead of storing the final bug data directly, we store a series of edit Operations".
Ordering — by logical clocks, because system time cannot be trusted in distributed work;
parallel edits yield a graph from which the state is **compiled**.

**Claiming without infrastructure.** `git update-ref <ref> <new> <old>` — a built-in
compare-and-swap; forty zeros in `<old>` mean "make sure the ref does not exist yet".

**A hung participant.** Everywhere it is cured by lease expiry, not by manual unlocking:
visibility timeout in queues (30 seconds by default, extension ceiling 12 hours),
`SKIP LOCKED` in Postgres, TTR in beanstalkd. The condition — a heartbeat more frequent than
the lease.

**Deduplication and precedence.** Code4rena splits the reward between duplicates with decay
(`10·0.85^(n−1)/n` for highs), and the 30% bonus goes not to the first but to the one **whose
text is selected for the report**; a weak write-up gets partial credit of 25/50/75% but enters
the denominator. Wardens do not see others' submissions — duplicates are built into the
process. Sherlock requires a duplicate to meet **all three conditions**: name the root, name at
least a medium impact, name a working attack path; the group is assigned the **highest**
severity among its members. DefectDojo recomputes fingerprints retroactively
(`manage.py dedupe`), i.e. a late duplicate is cured by regeneration, not by rewriting history.

⚠️ The wording "the machine proposes the grouping of duplicates, a human approves" **could not**
be confirmed by a primary source: such labels are visible in contest repositories, but the
process is not described in the documentation. It cannot be treated as fact.

**Parallel agents.** Anthropic says it directly: work must be split **along context
boundaries, not by roles**; a "planner / implementer / tester / reviewer" split spends more on
coordination than on work; what is worth parallelising is independent branches and
**black-box checking** — it does not require the implementation context. The price of a
multi-agent scheme — about 15× the tokens of a plain conversation.

→ For us: "hunter → verifier" is exactly their permitted case. "Hunter and fixer in parallel on
one block" — the forbidden one.

---

## Direction 9. Economics

**The price of a task is decided by the traversal architecture, not the model.** On one set:
AutoCodeRover $0.43 per task (37k tokens) versus SWE-agent $2.51 (245k) at comparable
quality — a 6.6× difference in tokens, 5.8× in money (arXiv 2404.05427). Agentless — $0.34 at
27.3% and $0.70 at 32.0%.

**Spread matters more than the mean.** Eight frontier models on SWE-bench Verified (arXiv
2604.22750): agentic tasks spend roughly 1000× more tokens than a plain conversation;
**runs of the same task differ up to 30-fold**; the driver is input tokens; accuracy **peaks at
medium spend and saturates**; models underestimate their own consumption (correlation up to
0.39).

**There is no superlinearity in the number of files in the literature — there is a drop in
quality.** SWE-bench Pro (arXiv 2509.16941): growing the task width from one file to 4.1 drops
solvability from over 70% to 23.3%. Degradation with input length is monotonic across all 18
tested models.

**The traversal order has a measured price.** The 20% of files with the highest predicted
number of defects contained 71–92% of those found, on average **83%** (Ostrand, Weyuker, Bell,
IEEE TSE 31(4), 2005). Code with an alarming "health" level carries **15 times more defects**
and requires **124% more time** (Tornhill & Borg, TechDebt 2022, arXiv 2203.04374). ⚠️ The
second metric is proprietary — its numbers do not transfer to a home-made surrogate.

**A whole-repository pass is a reasoned decision, not a default.** The audit sampling standard
explicitly does not extend to exhaustive examination; the sample size is derived from risk.

**Budget as a mechanism.** A catalogue of 63 overspend incidents (arXiv 2606.04056): causes —
infinite loops, context accumulation, injection; measures — a per-task budget, a circuit
breaker, degradation. The typical design: a label on every request, a soft and a hard limit, a
forecast by the 95th percentile, three layers — a token bucket, a breaker on spend rate, a
fallback cheap model.

⚠️ The last layer does not suit us: on synthetic data the cheap model barely trails, but on
real changes the best result drops by 92% (arXiv 2606.15689).

---

## Direction 10. Lifecycle

**Re-verification is a narrow phase, not a new pass.** NCC Group: "Retesting is only
re-evaluating the previously reported issues, not searching for new issues". Live numbers from
one audit: original — 45 days, repeat seven months later — **5 days** (about 11% of the
effort), of 8 findings 6 checked: one fixed, one partially, **four accepted as risk**. The
result is not a separate document — the original report is updated. Trail of Bits adds a
second criterion: "without introducing new problems". Cure53 writes a `Fix Note` straight into
the body of the finding.

**A "N% of code" threshold does not exist.** The assurance continuity standard (Common
Criteria Assurance Continuity, edition 2024-02-29) states outright: "there is no fixed method
for identifying whether the security impact of a change is major or minor". From the same
place, three rules: the size of a change does not equal its impact; **accumulation of small
changes is a reason in its own right** for a reassessment; elapsed time is a separate
criterion. And: the result of a reassessment becomes the **new baseline**.

**Regulation sets the cadence and the list of events.** PCI DSS 4.0.1: "at least once every
twelve months **and after significant changes**", where significant is defined by a list, not
a threshold. ISO surveillance audits — yearly, a full recertification every three years. A SOC
2 report does not expire but is considered stale after 12 months **from the end of the
observation period**.

**Stale trackers are a measured misery.** Veracode State of Software Security 2025 (1.3M
applications): findings older than a year — "security debt", carried by **half of
organisations**; the half-life at leaders — 5 weeks, at laggards — over a year; in the financial
sector the average age of an open finding is **276 days**.

**How it is treated.** Kubernetes: 90 days → "stale", another 30 → auto-close (a practice
disputed within the project itself). Chromium offers a third path: older than 90 days → to the
archive, and some — **back to "untriaged"**, i.e. neither keep nor delete but return to the
queue.

---

## Direction 7. State in someone else's repository

⚠️ **Not one of the tools examined writes state into the working tree of someone else's
repository.** `buf` pulls the base by reference, `oasdiff` returns an exit code, Pact moves the
matrix out to a broker, revmux writes to its own task directory.

For us this is not a verdict — state in git is the very idea of the method — but the list of
what it will break against in someone else's project is worth keeping in view: a protected
branch, mandatory commit signing, other people's pre-commit hooks, `.gitattributes` with
normalisation, and a merge conflict on the state file with every second proposal.

Only a **pinned reference** belongs in the tree: the SHA of the neighbouring repository, a hash
of the prompts, a fingerprint of what was reviewed.

## Review methods as a whole — cross-check of 23.09.2026

A cross-check of the eight methods by which the first project was reviewed against external
methods. Numbers marked "secondary" are taken from retellings — recheck before building a
decision on them.

**Where to look first (directions 9 and 12).**
- Defect concentration: 20% of files — 83% of defects (Ostrand, Weyuker, Bell, TSE 2005). Low
  quality code has 15 times more defects, 39 codebases (Tornhill & Borg, "Code Red", TechDebt
  2022, https://arxiv.org/abs/2203.04374).
- Process metrics beat size and complexity: relative churn distinguishes defective modules
  with 89% accuracy (Nagappan & Ball, ICSE 2005,
  https://doi.org/10.1145/1062455.1062514); Moser et al., ICSE 2008
  (https://doi.org/10.1145/1368088.1368114); the number of changes beats length (Graves et al.,
  TSE 2000, https://doi.org/10.1109/32.859533). Cross-project prediction barely transfers
  (Zimmermann et al., FSE 2009, secondary).
- Change coupling: ROSE — the right place to change is in the top three suggestions in >70% of
  cases, the link is invisible to code analysis (Zimmermann et al., TSE 2005,
  https://doi.org/10.1109/tse.2005.72); architectural debt — 20–61% of maintenance effort
  (Xiao, Cai, Kazman, ICSE 2016).
- SZZ: half of commits labelled as fixes are not (Herbold et al., EMSE 2022,
  https://doi.org/10.1007/s10664-021-10092-4) — any "fix" label based on the commit message is
  crude.

**How to read.**
- Inspection meetings add almost nothing to individual reading (Votta, FSE 1993,
  https://doi.org/10.1145/167049.167070; Porter, Votta, Basili, TSE 1995,
  https://doi.org/10.1109/32.391380).
- Perspective-based reading: no clear positive effect, signs of researcher bias (Ciolkowski,
  ESEM 2009, https://doi.org/10.1109/esem.2009.5316026).
- Threat model (direction 13): Shostack, *Threat Modeling* (2014); completeness 0.36 at
  precision 0.81 on students (Scandariato et al., 2015, secondary).

**Completeness (direction 1).**
- Capture-recapture with few reviewers is imprecise; the recommendation is the Mh model with
  Jackknife (Briand et al., TSE 2000, https://doi.org/10.1109/32.852741); with two it is useful
  only for the decision "re-pass or not" (El Emam & Laitenberger, TSE 2001,
  https://doi.org/10.1109/32.950319). Correlated reviewers produce a systematic error.
- Sampling: 59 files without defects → the defective share is ≤5% with 95% confidence
  (AICPA *Audit Sampling*; ISO 2859-1). No applications to code found.

**Diff review and AI reviewers (what the method does NOT replace).**
- Defects are 14% of diff-review comments (Bacchelli & Bird, ICSE 2013,
  https://doi.org/10.1109/icse.2013.6606617); 75% of defects found in review do not touch
  visible functionality (Mäntylä & Lassenius, TSE 2009); review coverage reduces post-release
  defects (McIntosh et al., MSR 2014).
- AI reviewers: best F1 19% on 1000 PRs, aggregation of 5 runs — 24% (SWR-Bench, FSE 2026,
  https://arxiv.org/abs/2509.01494); 75% precision only after a filter (BitsAI-CR, FSE 2025,
  https://dl.acm.org/doi/10.1145/3696630.3728552).
- Exhaustive file-by-file review as a method: no direct measurements of its payoff found.
