[Русская версия](ru/review-methods.md)

# Comparing review methods: what each one catches, what it costs, how productive it is

> Moved from the knowledge base of the first project (23.09.2026). Links to its registers are
> replaced with file names: the registers themselves stay there, here are the conclusions and
> numbers. "The first project" is the one where the kit was installed as a skill; "the site" and
> "the core" are its two repositories.

**Date:** 23.09.2026 · **For:** those choosing what to check code with
**Owner's request:** "a comparative analysis: file by file through directories, from large to
small, by critical areas, by lenses, whole-repository review, Codex review in PRs, the skill — and
the finetooth method… not only by time, but by productivity; which other methods exist; take the
best and think through a roadmap".

## Boundaries

- Numbers come from registers and journals, with a reference at each. Where there is no number,
  "—" is written, not an estimate.
- **The units are not fully comparable.** A "card" of the file-by-file pass, a "finding" of a
  lens, a "comment" from Codex and a "finding" from finetooth are things of different weight; the
  code, the period and the performers differ between methods. The comparison shows orders of
  magnitude and character, not exact ratios.
- "Whole-repository review" is the **comprehensive audit along 12 axes**
  (`runbooks/project-health-audit.md`). "The skill at Codex" is **PR review by a skill on
  request** (`/code-review`); Codex reads the same skills standard.
- External methods (section 6) are from primary sources; where a number is taken from a retelling,
  this is marked. Such numbers must be rechecked before building a decision on them.

## 1. Methods the first project was checked with

| Method | Where described | Essence |
|---|---|---|
| **File by file** | line A, `runbooks/review-file-pass.md` | the directory tree top down, file by file, no selection |
| **From large to small** | line C, `runbooks/agent-mode.md` | the largest files first: that is where there is the least unification and reuse and the worst split into modules. A review of code structure, the output is a file split |
| **By critical areas** | the wave rule of line A, the block order of finetooth | first where an error costs the most — in tests and in general |
| **Lenses** | lines B and D, `runbooks/review-lenses/`, `review-lenses-core/` | one property across all the code |
| **Cross-cutting audit** | `runbooks/project-health-audit.md` | the whole repository along 12 axes |
| **Vertical slices** | line F, `runbooks/review-vertical/` | one user scenario through all layers |
| **Codex in CI** | `runbooks/review-lenses/15-review-debt.md` | the PR diff, automatically |
| **Skill review of a PR** | `reviews/core/README.md` | the PR diff on request |
| **finetooth** | `docs/review/` of the first project | block: a domain and its files, a file → block map, hypotheses with verdicts, three roles |

## 2. What it catches and what it cannot see by design

| Method | How completeness is proven | Catches best of all | Cannot see by design |
|---|---|---|---|
| File by file | percentage of files passed | everything visible inside a file | module seams; ~90% of findings are repeats of the same roots |
| From large to small | queue by size | lack of unification, duplicates, poor split into modules — for this purpose size is a good signal | behavioural defects in small files |
| By critical areas | list of areas with the cost of an error | defects where an error is irreversible | risks nobody named: the assessment repeats the team's blind spots |
| Lenses | the lens's questions are closed | violation of a property, proven by a probe | unread code: which files were never opened is unknown |
| Cross-cutting audit | axes are enumerated | the overall picture and P0s in a day | depth: this is reconnaissance |
| Vertical slices | list of scenarios | layer seams and an error in the design intent | everything outside the chosen scenario |
| Codex in CI | none | fresh errors in the diff | all the rest of the code; on tooling code it does not converge |
| Skill review of a PR | none | the same on the whole diff, on request | all the rest of the code |
| finetooth | **every file behind a block and every hypothesis with a verdict** | completeness and the fact that the work survives session changes | seams between blocks (measurement — section 7) |

**The sources do not overlap** — checked on one day of core review: Codex found 3 P1s, the
skill review 7 (6 of them in code of the same day), lenses — the rest
(`reviews/core/README.md`). On one PR (PR 975) twelve lenses, handed out to four agents, gave
14 confirmed findings on top of Codex's two P1s.

**A lens does not exhaust an area.** The money lens 03 (29.07) gave 6 findings
(`reviews/2026-07-29-money-ledger.md`). Block H5 of finetooth on the same area (21.09) gave
21 findings, and by key names (`freeGenQuota`, `council-run`, `embedTexts`, zero price for an
unknown model, `isPro` versus `isAdminHandle`) not a single one coincided. Caveat: the code
changed over two months, part of the H5 findings may be about new code.

## 3. Time

| Method | Time per unit | For the whole project | Source |
|---|---|---|---|
| Codex in CI | **4–10 min** per round, median ~6.5 | not applicable: diff only | 12 requests in PR 939 |
| Skill review of a PR | minutes, not measured | not applicable | — |
| Cross-cutting audit | **1 day** | 1 day, repeated once a quarter | core audit 20.07, `research/2026-07-20-core-audit.md` |
| Vertical slice | **2 days** including the fix in production | not computed: the list of scenarios was not drawn up | 27–28.08, `reviews/vertical/` |
| Lens | **~1 day** | ~2.5 weeks for the site, ~1 week for the core | site: 12 lenses 28.07–14.08; core: 10 lenses 19–26.08, `reviews/STATUS.md` |
| From large to small | **median 2 h** per file (0.5–12) | 4–5 days for the top 47, 14–18 days for the top 160 at 3–4 sessions | 12 PRs, `runbooks/agent-mode.md` |
| File by file | **13 files a day** (1.2% of the site) | **~80 sessions** for the site, ~10,000 cards; until each file is exhausted — 500+ days | first variant of line A; `agent-mode.md` |
| By critical areas | depends on the method inside the area | — | — |
| finetooth | **35–50 min** of agent work per block (400–700 thousand tokens); with the manifest and acceptance ~1 h | **≈ 70–100 h** for 69 blocks — 2–3 weeks in a single stream, without fixing | finetooth measurements `docs/measurements.md`; journal: 3 blocks in ~3 h on 20.09 |

In every row except Codex **there is no fixing time** — and that is the main one (section 8).

## 4. Productivity

Productivity is **genuine new defects brought to a fix, per hour**. Hence several axes.

| Method | Yield | Share of false | Share of new | Share of serious | Brought to a fix | Keeps it from returning |
|---|---|---|---|---|---|---|
| Codex in CI | ~0.9 comments per PR | ~4% (1 of 24 checked P1s) | high: fresh code | ~23% P1 | **debt**: 1147 threads, not one marked resolved; 195 open P1s as of 20.08 | no |
| Skill review of a PR | 7 in a core day; 14 on one PR with lenses | — | does not overlap with Codex | — | in the same PR | no |
| Cross-cutting audit | 9 P0/P1 in a day | — | high: first look | P0/P1 in the digest | high: 6 fix phases | via the phase plan |
| Lenses | ~4–5 a day | low: each proven by a probe | high within the property | noticeable (lens 08: 5 P1 of 11) | high, often the same day | mutation of every fix |
| Vertical slice | 5 in 2 days | — | **the highest**: 4 of 5 on seams | P1s present | **all 5 in production** | a test on the transition |
| From large to small | 17 files split; 2–4 incidental cards per file | — | medium | low | high: the breakdown is the fix | structurally, by the split |
| File by file | ~16 cards per file | 0 false, but 7 downgraded and 7 duplicates | **low: 20 roots per 154 cards** | P1s present | 34% (74 of 216); in the first variant — 0 | a guard for a root with 3+ repeats (since v2) |
| finetooth | ~50 a day on 5 blocks, ~19 per hour of agent work | 2.6% (2) and 4 duplicates | not computed: roots not labelled | 10% high | **12% (9 of 77)** | a guard from the third instance of a root — a gate |

Sources: Codex — `reviews/2026-08-20-review-debt-ledger.md`
(sample of 24 P1s: 10 live, 9 already fixed, 1 false, 3 outdated, 1 accepted as is);
file by file — `reviews/2026-08-09-state-and-handoff.md`,
`reviews/problems/CLUSTERS.md`; lenses, audit, vertical slice,
large files — `reviews/STATUS.md`; finetooth —
the first project's register as of 23.09 (5 blocks of 69: 178 files,
19 thousand lines, ~10% of the coverage map).

## 5. Conclusions about our methods

1. **We can search faster than we can fix — with every "searching" method.** finetooth and the
   file-by-file pass give the most findings per hour, and with both the fixing lags behind (12% and
   34%; in the first variant of file-by-file — zero). Codex is the worst of all. Lenses, the vertical
   slice and the audit bring things to the end better — there the finding and the fix go in one
   pass.
2. **The raw number of findings deceives.** The file-by-file pass looks the most fruitful, but
   recounted into new causes it is ~2–3 a day. The vertical slice gives 2.5 a day, but 4 of 5 are
   what the others will not find by design.
3. **Only finetooth proves completeness** — it alone answers "what was not looked at".
4. **From large to small is a method about structure, not about defects**, and for its purpose the
   order by size is correct. For finding defects the order by change frequency is better
   (section 7).
5. **Codex is the cheapest by invested time** and mostly accurate, but without triaging the
   answers it is a debt generator.

## 6. Which other methods exist — by primary sources

Selected are methods we do not have or have under another name. "Checked" — the number was
verified against the primary source; "secondary" — from a retelling.

### Where to look first

| Method | Primary source | What is shown | Cannot see |
|---|---|---|---|
| **Hotspots** — change frequency × complexity | Tornhill, *Your Code as a Crime Scene* (2015); Tornhill & Borg, "Code Red", TechDebt 2022 | low-quality code has 15 times more defects (39 codebases, checked). Concentration: 20% of files — 83% of defects (Ostrand, Weyuker, Bell, TSE 2005, checked) | rarely changed dangerous logic; new code without history |
| **Process metrics** — volume and frequency of changes, code age | Nagappan & Ball, ICSE 2005; Moser et al., ICSE 2008; Graves et al., TSE 2000 | relative change volume distinguishes defective modules with 89% accuracy (Windows Server 2003); process metrics beat code metrics; the number of changes predicts better than length (all checked) | the type of defect |
| **Change coupling** — files that change together | Gall et al., ICSM 1998; Zimmermann et al., ROSE, TSE 2005 | the 3 best suggestions contain the needed place to change in >70% of cases; the link is not visible by code analysis (checked). Architectural debt: 5 groups — 20–61% of maintenance effort (Xiao, Cai, Kazman, ICSE 2016, checked) | links not yet manifested in history; noise from mass changes |
| **Risk-based review** | ISO/IEC/IEEE 29119; Felderer & Ramler, STTT 2014 | only qualitative cases, no controlled comparisons | risks nobody named |
| **Defect-introducing changes** (SZZ) | Śliwerski, Zimmermann, Zeller, MSR 2005 | the labelling is noisy: half of the "fixes" are not fixes (Herbold et al., EMSE 2022, checked) | defects due to missing code |

### How to read

| Method | Primary source | What is shown |
|---|---|---|
| **Fagan inspection** | Fagan, IBM Systems Journal 1976 | 82% of product defects (secondary). **Meetings add almost nothing** — independent reading matters more than discussion (Votta 1993; Porter, Votta, Basili, TSE 1995, checked) |
| **Perspective-based reading** | Basili et al., EMSE 1996 | meta-analysis: no clear positive effect, there are signs of researcher bias (Ciolkowski, ESEM 2009, checked) |
| **Scenario-based reading** | Porter, Votta, Basili, TSE 1995 | better than a checklist and than reading without a method (checked); replications did not reproduce the effect (secondary) |
| **Threat modelling** (STRIDE, data flows) | Shostack, 2014 | recall 0.36 at precision 0.81 on students (secondary); 64% of new protection measures in a case study (secondary) |
| **ATAM** | Kazman et al., SEI 2000 | 3–4 days of meetings, ~75 person-days (secondary) |

### By machine across all the code

| Method | Primary source | What is shown |
|---|---|---|
| **Variant analysis** (CodeQL, Semgrep) | GitHub Security Lab, Trail of Bits | no peer-reviewed measurements, reports of found CVEs |
| **Mutation testing in review** | Petrović & Ivanković, ICSE-SEIP 2018; TSE 2021 | Google: 24,000+ developers, mutants on changed lines; mutants are linked to real defects (checked) |
| **Fuzzing, property-based tests** | OSS-Fuzz; OOPSLA 2025 | OSS-Fuzz: 13,000+ vulnerabilities and 50,000 defects (checked); a property test catches ~50× more mutants than a unit test (secondary) |
| **Executable architecture rules** | Ford, Parsons, Kua, 2017 | no data |
| **Core connectedness** (DSM) | MacCormack et al., 2006; 2016 | files of a densely connected core have three times more defect activity (secondary) |

### How to assess completeness

| Method | Primary source | What is shown |
|---|---|---|
| **Capture-recapture** | Eick et al., ICSE 1992; Briand et al., TSE 2000; El Emam & Laitenberger, TSE 2001 | with few reviewers no model is accurate; with correlated reviewers — a **systematic error** (checked). Agents of one model are correlated by design |
| **Sampling, as in audit** | AICPA Audit Sampling; ISO 2859-1 | no applications to code found. The mathematics: 59 random files without defects give, with 95% confidence, a defective share ≤5% |

### On diff review and AI reviewers

- Diff review mostly finds maintainability: defects are 14% of comments (Bacchelli & Bird,
  ICSE 2013, checked); 75% of found defects do not touch visible functionality (Mäntylä &
  Lassenius, TSE 2009, checked). But review coverage measurably reduces post-release defects
  (McIntosh et al., MSR 2014, checked).
- AI reviewers: best F1 19% on 1000 PRs, up to 7 false per PR; aggregating 5 runs raises it to
  24% (SWR-Bench, FSE 2026, checked). Precision 75% — only after a separate filter
  (BitsAI-CR, FSE 2025).
- **There are no direct measurements of the yield of an exhaustive file-by-file review in the
  literature.**

## 7. Three methods checked on our data

### Hotspots versus size (prediction, not hindsight)

The history of the first project was split in half by time (1219 commits, midpoint 22.07). From
the first half — file size and change frequency; from the second — which files the fixes landed in
(commits with the words "fix", "исправ", "почин" etc. — a rough label). 634 code files.

| Share of future fixes collected by the top files | 5% | 10% | 20% |
|---|---:|---:|---:|
| by size | 18% | 29% | 45% |
| by change frequency | 21% | 34% | 51% |
| by hotspots (frequency × size) | 20% | 34% | 51% |
| random | 3% | 6% | 15% |

**Change frequency predicts better than size, but not by much; the product adds nothing to
frequency.** This agrees with the primary sources (Nagappan, Moser, Graves). Caveats: the fix
label by words is rough (SZZ has ~50% noise); only files that survived to the end of the period
made it into the sample, and split large files dropped out.

### Change coupling — the seams that finetooth blocks cut

Pairs of files that change together at least three times (964 commits, mass changes over 12
files excluded): **553, of which 423 (76%) are between different finetooth blocks**. Most are
shared hubs: the DB schema, dictionaries, pages (a file linked to six or more blocks). Without
the hubs, **38 strong cross-block pairs** remain (at least half of the changes joint) in 33 pairs of
blocks. Four touch blocks already passed, two of them on point:

- `shared/auth/api-token.ts` (H1, access) ↔ `features/mcp/actions.ts` (H4b) — a seam in
  permissions;
- `core/domain/entities.ts` (H15) ↔ the list storage adapters (V1h) — exactly the class where
  there already was a silent loss of fields.

These are the "seams between blocks" from section 2, now with addresses.

### Capture-recapture on block H5

Two hunters went independently: A found 10, B — 8, 4 coincided
(calibration — [`measurements.md`](measurements.md), the section on two hunters).
The Lincoln–Petersen estimate is 20 defects in the block, Chapman — ~19; the hunters together found
14, the verifier added 3. **One hunter finds no more than ~40–50% of a block's defects.** This is
an **upper bound**: one model and one prompt are correlated, the overlap is inflated, and the
true number of defects is most likely higher (section 6).

## 8. Recommendation

| When | What | Cost |
|---|---|---|
| every PR | Codex + skill review of one's own diff before pushing, **with triage of the answers** | minutes |
| once a quarter | cross-cutting audit | a day |
| before a pass | a map: change frequency and change coupling from `git log` | minutes |
| a pass over all the code | finetooth in blocks in the order "risk first, change frequency second"; lenses as hypotheses in manifests; cross-block pairs from the coupling map into `ref_paths` and into hypotheses | 2–3 weeks + fixing |
| seams | vertical slices by scenario where the coupling map shows cross-block pairs | ~2 days per scenario |
| security | a threat model by data flows for access and trust-boundary blocks | — |
| code structure | splitting large files; then by hotspots, not only by size | ~2 h per file |
| do not keep | file by file through a directory: the most expensive of all, 90% of findings are repeats, no direct measurements of yield in the literature | — |

**The main lever is a mandatory fix phase:** the next block, lens or wave does not start until the
serious items of the previous one are closed. Right now, on the 5 finetooth blocks passed, 62
findings are open.

## 9. What finetooth takes

The best of sections 6–7 goes into the kit's development plan — [`ROADMAP.md`](../ROADMAP.md): the fix phase as a gate, the change coupling
map for cutting blocks and `ref_paths`, the order "risk × change frequency", the threat model as a
block type, variant analysis as a form of guard, and a correction to the completeness measurement:
capture-recapture is fit only as an upper bound.
