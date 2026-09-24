[Русская версия](ru/comparison-with-practice.md)

# This method against world practice

The kit in this repository grew out of the experience of two projects and was checked against
nothing. Here it is checked: against the methodology of audit firms, the practice of companies
whose codebases are measured in millions of lines, industrial AI reviewers and academic
measurements. Verified 21.09.2026.

The purpose of the document is not to praise the method but to find where it rests on faith.

## The main thing in three lines

1. **Everyone else's coverage denominator is not files but questions, requirements or
   interfaces.** Not one audit report examined has a percentage of covered lines or files.
2. **A second, verifying agent is useless if it re-reads and valuable if it executes.**
   A bare LLM verifier on real alarms gives precision 0.26–0.29 at a true-positive base of 0.24.
3. **A whole-repository pass is justified as an inventory that ends in a rule, not as a
   mode.** The same analyzer yields ~0% fixes in a batch run and >70% on a diff.

---

## Eight claims of the method under scrutiny

| | claim | verdict |
|---|---|---|
| A1 | completeness is proven by the file coverage map | the denominator is wrong, but the map has no analogue |
| A2 | who searches does not fix, who fixed does not verify | confirmed, name: separation of duties |
| A3 | the verifier gives a gain | measured twice: 0 fakes get through, cheaper than a pair of hunters |
| A4 | state on disk matters more than context | confirmed |
| A5 | the acceptance criterion protects against retelling | confirmed indirectly, weaker than their variant |
| A6 | block size is limited by readability | **in doubt from both sides** |
| A7 | rejected findings are kept with a reason | confirmed strongly |
| A8 | a fix is verified by mutation | confirmed industrially |

### A1. The file coverage map

**Against.** The unit of coverage in professional auditing is never the file. Trail of Bits
cuts the work by questions to the system ("Are the authentication and authorization layers
implemented consistently across…"). Cure53 — by Work Packages, the package number is baked
into the ID of every finding. NCC Group — by components with a budget in person-days. OWASP
ASVS — by requirements, each with a binary outcome: "The requirement must be verifiable, and
the verification must result in a "fail" or "pass" decision". Common Criteria — by security
function interfaces (TSFI) and design subsystems. DO-178C — by requirements with two-way
tracing.

In eight reports examined (ToB ×3, NCC ×2, Cure53 ×3), a search for "lines of code | SLOC |
% of the code | % of files" produced not a single match.

**Two schemes that close the loop, and the difference between them.** Common Criteria requires
that **all** security function interfaces be tested (ATE_COV.2.2C), but does not require the
reverse check: the methodology explicitly reminds that not every test has to map to an
interface. That is, CC proves completeness of the **surface**, not of the content — and itself
admits that a full code walk-through is "impractical in almost all cases", preferring a
sample.

DO-178C is the only scheme found that closes the loop completely: forward (a requirement has
code and a test), backward (**code and test have a requirement**), structural coverage on
requirements-based tests, and a separate objective for the seams between components. And it
has a discipline directly applicable to our "unowned" files: code without a requirement is
**dead code**, a development defect, it gets deleted; code with a requirement that does not
execute in this configuration is **deactivated code**, it stays, but one is obliged to prove it
does not activate. The difference is precisely in the presence of a trace. With us, a file
belonging to no block currently just fails the check — without distinguishing "forgot" from
"deliberately not ours".

Worse: completeness there is proven by **enumerating what was not examined**. A
`Coverage Limitations` section is in every ToB report, and the wording can be blunt: "Because
of the size of the ExecuTorch codebase, we focused our manual review on identifying common
vulnerable code patterns across the codebase, **rather than obtaining full manual coverage**".
Even Common Criteria examines source code **by sampling** up to and including EAL6.

**For.** Their "coverage" is an adjective: "satisfactory coverage", "good coverage". It cannot
be checked without hiring a second auditor. A file map gives a reproducible number that cannot
be nudged with a word. And it catches what nothing else catches: for the kit's author — a
forgotten microservice, for us — 89 route files that belonged to no block.

Among industrial AI reviewers **nobody** has proof of completeness. The only approximation is
PR-Agent, which prints a list of files dropped for lack of tokens. All the others silently
truncate on budget overflow; Sourcery just marks "Skipped".

**Conclusion.** Keep the file map as a trap for the forgotten. Add a second denominator: the
manifest's hypotheses with a status "checked / not checked / not applicable" and a
justification for inapplicability — the ASVS 4.0.3 model: "In case of dispute, there should be
sufficient assurance evidence to demonstrate each and every verified requirement has indeed
been tested".

### A2. Separation of roles

Confirmed everywhere and has a name — separation of duties.

- **Linux:** the trailer chain `Reported-by` → `Fixes:` → `Reviewed-by`/`Tested-by` →
  `Signed-off-by`. Each participant's role is recorded in the commit.
- **syzbot:** a bot found it → a human fixed it → **a bot checked again** (`#syz test`), and the
  bug is closed only when the commit has reached all tracked branches.
- **Google:** three independent approvals per change — LGTM (correctness), OWNERS (ownership),
  Readability (language style, a certified human).
- **Big Sleep:** the agent found it → a human expert verifies **before** the report is sent.

Science adds a condition the kit did not have: **the verifier must think differently**. The
gain from verification falls monotonically as the solver and the verifier grow more similar
(37 models, 9 benchmarks, arXiv 2512.02304). With us the hunter and the verifier are the same
model.

### A3. The verifier's gain — the weakest point

Our measurement over three blocks: hunters produced 32 findings, verifiers added 10 (+31%) and
rejected 2 (6%).

The problem is that a gain in findings is not the same as a gain in usefulness:

- **CR-Bench** (584 defects from django, sympy, astropy, scikit-learn): a self-check loop raised
  recall from 27.0% to 32.8%, but crashed signal/noise from 5.11 to 1.95 and usefulness from
  83.6% to 66.1%. More findings at the price of reviews no longer being read.
- **Huang et al., ICLR 2024:** self-correction **without an external signal** is statistically
  harmful — GPT-4 loses 6.5 p.p. on GSM8K, Llama-2 — 25.5 p.p. The model breaks a correct answer
  more often than it repairs a wrong one.
- **Multi-agent debate loses to simple voting** at equal budget: 83.0 versus 88.2 over nine
  answers.
- **Greptile** publicly threw the LLM judge out of the product: "The LLMs judgment of its own
  output was nearly random". Replaced with an embedding filter: a comment is blocked if it is
  close to three or more previously downvoted ones.
- **Sourcery** measured a uniform post-filter: 43% against 42% without it — zero. The only thing
  that worked was a separate call with boolean checks by category Valid / Actionable /
  Specific / Valuable.

**But there is a flip side, and it is about us.** Tencent, 433 real static-analysis alarms
(true-positive base 24%): a bare LLM verifier — precision 0.26–0.29, i.e. nearly random. The
same LLM with path reachability analysis — **0.83–0.93**, removes 94–98% of false positives.
GPTScan: the static confirmation stage removes two thirds of false positives.

Our verifier **executes** rather than re-reads: it mutates guards, calls predicates on a value
matrix, runs tests, independently rebuilds the route table (and found 7 missed out of 38).
Exactly that moves it from "nearly random" to "working".

**The measurement was done 21.09.2026 — and the suspicion is lifted.** Six real findings were
mixed with six invented ones, each written so that execution would refute it (a rule on `dd`
supposedly missing, NBSP supposedly not covered by `\s`, `JavaScript:` supposedly getting
through because of case, and so on). The order was shuffled, the origin was not disclosed to
the verifier, the set was run by two models independently.

**Not one lie got through — 6 of 6 rejected by both**, with a statement of what the code does
instead of what was claimed. Our 6% rejection rate is explained not by the verifier's
compliance but by the hunter's precision.

As a side effect the measurement exposed something else: both models rejected two **real**
findings — and both were right, a commit had closed them, and the register did not know. A
review document goes stale within a day.

The models disagreed exactly once, and the analysis of that disagreement itself turned out to
be an error. One looked into the neighbouring repository and "confirmed by execution" a hole; I
checked with my own hands and agreed. The working copy of that repository was **twelve days**
behind — in `origin/master` the hole had long been closed. The conclusion "the cheap model
missed a live finding" is withdrawn: the finding is not live, and the model that rejected it
was the one that was right.

**This is the first counterexample to "the verifier does not make things up"** — and what let
us down was not reasoning but the freshness of the tree. Hence a rule that neither we nor the
practice examined had: checking beyond one's own repository goes against `origin/master`
after `fetch`. The tool now fails the check itself when the tree is older than its branch on
the server, and measures precisely **time, not commits**: in that case the lag was only two
commits — a number that would have alarmed no one.

**Second measurement, 21.09.2026: the scheme compared with the cheapest rival.** One block run
twice — by two independent hunters (the second read in reverse order, a cheap analogue of
"shuffling") and a verifier over their union, blind.

| | findings | tokens |
|---|---:|---:|
| hunter A | 10 | 204k |
| hunter B | 8 | 222k |
| verifier (over 18) | +3 of its own | 131k |

Verdicts: **17 confirmed, 1 plausible, 0 rejected**. The second hunter brought four new
findings, the other four turned out to be duplicates of the first by root. The verifier, for
half the money, checked all eighteen, found three of its own, corrected details in three and
merged four pairs of duplicates.

And it did what a pair of hunters cannot: **resolved a direct contradiction** between them. One
claimed the balance floor works only for one provider, the other that it hits all of them; the
fork, as it turned out, runs along the presence of a key, and both halves pointed at the same
omission. In the "two passes with a merge" scheme such a contradiction goes into the register
as two findings, and a human sorts it out.

**A conclusion stable over two measurements: the value of the second role is not in filtering
but in deepening.** Zero rejected in both runs means that a hunter obliged to present a failure
scenario and to check by execution brings no inventions — there is nothing to filter. But the
verifier is 41% cheaper than a second hunter and leaves a verified result behind it.

⚠️ Limits: one block, one model in both roles. On a block where the hunter errs more often the
ratio will change — the more inventions, the more valuable the filter.

### A4. State on disk

Confirmed. Spearbit keeps the audit in git: a private repository, branches in proportion to
the number of files in scope, discussion in PR comments, labels as a state machine,
`Verified by USERNAME`, and a finding becomes an issue **only after confirmation**. Code4rena
and Sherlock — labels on GitHub issues. A rules file in the repository has become the de facto
standard among AI reviewers: `.coderabbit.yaml`, `.greptile/config.json`, `.pr_agent.toml`,
`BUGBOT.md`, `AGENTS.md`; Devin reads even other tools' ones.

### A5. The acceptance criterion

No direct analogue; the closest is the Test Methodology chapter at Cure53, where a
**negative result** is documented: "we looked for prototype pollution, DOM XSS sinks,
postMessage without an origin check — did not find them, here is why". That is a verifiable
claim; a tick "file examined, 0 findings" is not.

Our acceptance criterion is stronger than a tick (a route table cannot be assembled without
reading the code), but weaker than their combination: we have no mandatory section on what was
deliberately not read.

### A6. Block size

In doubt from two sides at once.

**The threshold may be too large.** The "effective length" of context, where a model keeps
≥85% of its short-context quality: GPT-4o — 8K tokens, Claude 3.5 Sonnet — 4K, Gemini 1.5 Pro —
2K at a declared 128K+ (NoLiMa, ICML 2025). Our 6000 lines are 60–80K tokens.
⚠️ Measured on a synthetic "needle in a haystack", transfer to code reading is not proven.

**And at the same time the context may be too much.** SWE-PRBench: a structured diff with a
2000-token summary beat a 2500-token "full context" **on all eight models**. "Bigger Isn't
Always Better": quality falls exponentially with diff size, a 15× difference between small and
large.

**Cheaply testable:** take a 6000-line block and the same block cut in half, compare the
findings.

### A7. Rejected findings

Confirmed more strongly than we have implemented. Code4rena keeps the rejected **publicly and
forever**: in one contest 819 satisfactory, 658 unsatisfactory, 72 invalid — each with a
judge's comment and a JSON file. And it is not an archive for its own sake: from them is
computed `signal = findings / submissions`, which **limits a participant's right to submit
findings**.

Trail of Bits keeps the reason for refusal verbatim: "The ExecuTorch team has opted not to
address the issue, since the root cause is in the third-party implementation of XNNPACK".

With us the reason is now required by the tool, but there is no feedback on the finder's
precision.

### A8. Mutation checking

Confirmed industrially. Meta ACH: 10,795 classes → 9,095 mutants → 571 tests, **engineers
accepted 73%**. The equivalent-mutant detector: precision 0.79 / recall 0.47 baseline, 0.95 /
0.96 with preprocessing.

Our fact of the same kind: on the writes block eight mutations gave eight green runs — the test
suite guarded none of the findings — while two control changes went red, which proved the rig
was sound.

---

## The main external challenge to the method

**Meta, CACM 2019.** The same Infer, the same false-positive level. A batch run over the whole
base, findings handed out to developers — the share fixed **about zero**. Switched to the
diff — **over 70%**. The causes are named outright: context switching and addressing.

**Google, Fixit 2009.** 3,954 FindBugs warnings reviewed, **16%** fixed. The paper's
conclusion: manual triage and filing bugs do not scale.

The whole-repository pass has not gone anywhere, though — it has three roles, and all three
are ours:
1. **measuring** the false-positive share before switching on a new check;
2. **clean-up** of existing violations before the check becomes mandatory;
3. **inventory** of all occurrences of a freshly discovered defect class.

The third role in auditing is called **variant analysis**: from findings ToB wrote five
Semgrep rules, ran them over the whole base and found **26 additional variants**; the rules are
attached to the report and re-runnable. Completeness is guaranteed by the rule, not by the
walk: it survives refactoring and works on code that does not exist yet.

**Consequence for the method:** every block must end in a guard. A block closed with only a
list of findings does not pay for itself — the next pass will find the same thing.

**And why nobody chases completeness.** The Codex team published a finding-usefulness
function: `P(correct) × time saved − cost of human verification − P(incorrect) × price of a
false alarm`. Hence their decision: "we explicitly accepted a measured tradeoff: modestly
reduced recall in exchange for high signal quality and developer trust". Signal/noise first,
completeness second. The price of a miss is paid once, the price of noise — by every reader of
every report.

There too — a warning worth keeping in the manifest: "Over reliance is a serious risk.
Teams could start treating a clean review as a guarantee of safety".

---

## Neighbours in the niche on GitHub

Checked 21.09.2026 by sources and READMEs, metadata — via the API.

**There is no full analogue.** About fifteen projects cover two or three of our seven features,
but none combines whole-base coverage as a gate, prompt assembly by the tool from a manifest,
and state integrity checks in code. The overwhelming majority of "agentic code review" is diff
review with a fan-out by roles; a whole-repository pass is done by a handful, and their state
is either absent or a single markdown report.

Closest are three:

| project | what it has | what it lacks |
|---|---|---|
| [Faris-Alanazi/codebase-audit](https://github.com/Faris-Alanazi/codebase-audit) | a file manifest and the rule "every file in exactly one group", a register with the lifecycle `OPEN → FIXED → VERIFIED → REGRESSED`, matching between runs by fingerprint | no blocks with manifests, groups are cut on the fly by directories; state — markdown without a schema |
| [ncoevoet/claude-review-all](https://github.com/ncoevoet/claude-review-all) | the best finding lifecycle found (key = root + code hash, auto-return to `open` on regression), prompt assembly from sections, checkpoint key includes the prompt texts, 14 tests and 40 fixtures | works only on a diff, no whole-repository pass |
| [ChristopherKahler/aegis](https://github.com/ChristopherKahler/aegis) | phases, `STATE.md`, `/resume` and session hand-off, a disagreement protocol between agents | coverage by domains, not by files: "unowned file" is not caught; no tests |

**The most valuable thing was found not in the niche but next to it — at
[doorstop](https://github.com/doorstop-dev/doorstop)** (requirements as YAML under git). There
every requirement has a `reviewed:` field with a hash of its own text: editing the text itself
moves the requirement into "unreviewed changes", and `doorstop review` re-stamps. Plus
**suspect links** — a link stores the parent's fingerprint at the moment of linking, and
editing the parent marks the link suspect. Their gate is five lines of shell.

This is a direct answer to the hole that sat at the foundation of our method: the status
"block done" held forever, although the block's files could be rewritten entirely. **Taken and
implemented.**

What else was taken: the fingerprint of the code under a finding (doorstop + claude-review-all)
and the check that the line named in a finding exists in the file — the cheapest filter of
invention ([mergejury](https://github.com/iamEtornam/mergejury), where it is done without a
model at all).

Noted for the future but not taken: a context budget as a gate with a non-zero exit code
([repomix](https://github.com/yamadashy/repomix)) and marking what did not fit right in the
artifact ([ai-digest](https://github.com/khromov/ai-digest) leaves the path with a placeholder
instead of the content); a two-way coverage report with metrics
([spec-kit](https://github.com/github/spec-kit), the `/analyze` command); the coverage state
vocabulary from [OpenFastTrace](https://github.com/itsallcode/openfasttrace), where `outdated`
(an old version was examined) and transitive non-coverage are named separately.

⚠️ And an anti-example worth a separate mention:
[gitingest](https://github.com/coderamp-labs/gitingest), on exceeding its limits, silently
drops files into a debug log, and the digest itself says not a word about the omission.
Exactly the silent loss for which the coverage map was created.

## What nobody has

1. **Proof of completeness.** Not one AI reviewer claims "all changed lines examined" or
   presents an artifact. Closest — the coverage footer at PR-Agent.
2. **A published FP rate by a sound methodology.** The single exception is Semgrep, and only
   because their unit of work is a finding from a deterministic scanner, so there is something
   to compare against: 6.5M analysed findings, a 60% volume reduction, 96% human agreement.
   Everyone else gives surrogates: downvote share, share of comments acted on, resolution
   rate. These are usefulness metrics, not precision.
3. **Recall at all.** Nobody publishes how much they missed.
4. **A catalogue of past findings with deduplication between passes.** Learnings and Memories
   store rules and preferences, not "this same problem was in PR #412".
5. **Agreement between benchmarks.** In a practical run of four tools on 146 PRs **93.4% of
   flagged locations were found by exactly one tool** — they simply do not measure the same
   thing.

---

## What to change, by priority

**P1. Manifest hypotheses get a status.** `H1.3 | checked / not checked / not applicable |
how proven`. Gate: a block does not close while a hypothesis has no status. Source: ASVS.

**P2. A mandatory "what I did not examine" section in the report.** Not "did not read the file"
but "read it, but could not close the question, because". Source: Coverage Limitations at ToB
and NCC.

**P3. A block ends in a rule.** A field on the finding: what closes the class. A recurring
finding must become a guard, otherwise the work does not pay for itself. Source: variant
analysis, Zoncolan.

**P4. A negative result as an artifact.** "Looked for X by means of Y — did not find it,
because Z". Source: Cure53 Test Methodology.

**P5. The verifier — a different model.** Currently hunter and verifier are one Opus. Source:
arXiv 2512.02304. ⚠️ Measured on logic and mathematics, not on code.

**P6. Scope is pinned by a commit.** Write HEAD into the header of the coverage map and into
the block report. Source: ToB `Version c243e427`, Cure53 `Commit: 40c7ad84…`.
⚠️ Outcome of implementation (0.3): the commit in the map header was removed. There was nothing
to verify it with — the "same line of history" check let through a map assembled on a
different file set — and an auditor's report is signed once, whereas our map is rebuilt
constantly. The version is pinned by the fingerprints of blocks and findings; the map is
checked against a recompute line by line.

**P7. Measuring the hunter's precision.** Slip the verifier a control set of deliberately false
findings and count how many it rejects. Currently 6% rejected cannot be told apart from "the
verifier agrees". Source: `signal` at Code4rena.

**P8. A duplicate is defined through the root.** "If the root is fixed, the finding ceases to
exist" — a mechanically applicable definition. Source: Code4rena.

**P9. Closing a finding — by a green re-run, not by words.** Source: syzbot.

**P10. The cheapest verification mechanism, worth trying first.** Cursor BugBot runs several
search passes **over a shuffled diff** and keeps only what surfaced in several passes:
shuffling removes the position effect in context, and voting replaces the model's judgment of
itself. No index, no sandbox, no reaction history needed. This agrees with the academic result:
at equal budget voting beats debate. For us this is exactly the baseline from P7 — two
independent hunter passes instead of one plus a verifier.

---

## Numbers for calibrating expectations

| what | value | source |
|---|---|---|
| precision of an AI reviewer on real PRs | 3.56% | CR-Bench, arXiv 2603.11078 |
| false discovery rate on real CVEs | 84.82% | IRIS, ICLR 2025 |
| exact reproduction of a human review comment | 2.12% | Tufano, ICSE 2022 |
| comment density in production | 5.1 per review, 71% substantive | GitHub, 60M reviews |
| best tool on an independent set | no more than 63% of known problems | Martian Code Review Bench |
| all review agents together | ~40% of tasks | c-CRAB, arXiv 2603.23448 |
| same model: dirty dataset vs clean | F1 68% → 3% | PrimeVul, ICSE 2025 |
| synthetic mutations vs real bug fixes | F1 0.847 → 0.066 | arXiv 2606.15689 |
| Google in production | target precision 50%, success = 7.5% of comments closed | ICSE-SEIP 2024 |
| merge rate of PRs reviewed only by agents | 45.2% against 68.4% for humans | MSR 2026 |
| price of an audit by humans | 6–9 engineer-weeks per repository | Trail of Bits |
| our block | 2 agents, 446–679k tokens, 34–48 min | review journal |

The last row is the reason this method makes sense at all: what costs person-weeks costs an
hour here. At a precision several times below human.
