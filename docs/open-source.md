[Русская версия](ru/open-source.md)

# Opening finetooth as an open-source project: what is needed and who is nearby

An analysis of 24.09.2026 on the question from the method's author: "can't you just set it up as
an open-source project on GitHub?". The checklist is assembled along the path the owner has already
walked with the first project (there — "open edges around a closed centre", five layers, a
pre-flight check of repositories), plus what is particular to this kit. The catalogue of
neighbours is by the GitHub API as of 24.09.2026: stars and push dates were taken by query, not
from blogs.

## 1. What is particular about this repository

Two things the first project did not have, plus the choice of platform.

**The licence on the base.** The kit grew out of the method author's archive, handed over
without a licence; our `LICENSE` is MIT with an appendix "the base was handed over without a
licence", and because of the appendix GitHub shows the licence as **Other**. For an open project
this is the first thing a visitor sees, and it is a bad sign. The author himself proposed opening
the project — so his explicit consent to the licence is needed: one line from him (a message, a
commit with `Signed-off-by` or a comment in an issue), after which `LICENSE` becomes clean MIT
with two copyright holders, and the origin history moves to `NOTICE.md`.

**Platforms.** GitHub is the primary one. A mirror, if ever needed: GitLab.com or one's own server. Codeberg is in question: its terms require a free licence (after cleaning LICENSE — fine) and **forbid projects consisting mainly of AI-generated code** — by commit history `review.py` is exactly that.

**The name.** Until 0.6.0 the kit was called `review-kit`, and there were many neighbours with
similar names: `draft-review-kit` (87★, text review), `ReviewKit` (Swift, two projects),
`tender-review-kit`, `spec-kit-review` — it could not be found by name. On 24.09 the root of the
series was chosen: **finetooth** (from the idiom *go through with a fine-tooth comb*): free on npm
and PyPI, on GitHub — three tiny repositories; an organisation with that name is taken,
`finetooth-review` will do for the series. Rejected: `review-combine` (the author's word
"combine", but in English it is first of all a verb, and dozens of `review-*` sit nearby),
`codecensus` (precisely about a complete edition, but does not carry a series); `dragnet`,
`blockwise`, `muster` are taken on npm and PyPI. The series by review type: `finetooth`
(whole-repository by blocks), `-lens` (by property), `-slice` (by scenario), `-pr` (by change — a
light version, a bot or an Action), `-scan` (reconnaissance by axes), `-shape` (by structure:
large files, hotspots, coupling), `-threat` (threat model), `-gate` (gates in CI). One
repository, skills in `skills/`, each installed separately.

## 2. Opening checklist

**Owner's decisions (before everything else):**

1. Licence — MIT with two copyright holders; the author's consent was received 24.09 (through the owner) and recorded in `NOTICE.md`.
2. Repository name — decided: `finetooth` (see section 1).
3. Language. The kit is entirely in Russian — deliberately (the prompts and reports are read by
   Russian-speaking agents and people). For an open project at least an English first screen of the
   README and an English `description` in `SKILL.md` are needed (English trigger keywords for the
   skill are already there). Translating everything is a separate decision, not a condition of
   opening.
4. Contribution model — DCO (`Signed-off-by`), not CLA: we have nothing to protect with dual
   licensing, and a CLA scares people off.
5. The support line — honest: "the project is run by one person, PRs are triaged once a week".
   The absence of promises is better than broken ones.

**Pre-flight check — done 24.09, results:**

| Check | Result |
|---|---|
| names of people and projects in files | none found (after the clean-up for 0.1.0) |
| the same in commit history | 0 matches over the whole history |
| keys and server addresses | none; the repository has neither `.env` nor infrastructure |
| commit authors | two addresses of the owner — fine |
| `gitleaks detect` over the history | done 24.09: 58 commits scanned, no leaks |

**Repository scaffolding (what is missing — by comparison with the best neighbours, section 4):**

- [x] clean MIT `LICENSE`, `NOTICE.md` with the origin — 24.09, the author's consent received through the owner;
- [x] `CONTRIBUTING.md`: DCO, how to run the tests and `skills-ref validate`, the rule "every
      check — with a mutation" (it is already in `AGENTS.md`), Latin letters in file names;
- [x] `CODE_OF_CONDUCT.md` — Contributor Covenant 2.1, no home-brew;
- [x] `SECURITY.md`: where to write and a response time of "up to a week";
- [x] issue templates in `.github/ISSUE_TEMPLATE/*.yml` with `config.yml`; a separate template
      "found a defect with the kit" (Trail of Bits has `trophy-case.yml`: a link to the finding and
      which skill gave it — at the same time a denominator for direction 5);
- [x] a PR template with the checklist "test + mutation + CHANGELOG";
- [x] badges in the README: licence, tests (CI already exists), "works in Claude Code / Codex /
      Cursor / Gemini CLI" — all the neighbours list harnesses on the first screen;
- [ ] GitHub releases by tag with notes from the CHANGELOG (right now — tags only; notes can be
      assembled by release-drafter or by hand from the version section);
- [x] `examples/` — a ready `docs/review/` on a toy repository — `examples/toy`, 24.09: the visitor sees blocks, a
      manifest, a report and a register without installing anything;
- [ ] dog-fooding: `check` of our own repository in CI (the neighbours review themselves with their
      own tool on every PR — open-code-review, pr-agent, trailofbits);
- [x] protection of the `master` branch: PR and green CI mandatory;
- [x] repository description and topics (`agent-skills`, `code-review`, `claude-code`, `codex`,
      `llm-agents`, `security-audit`), Discussions enabled for questions.

**Opening and distribution:**

- [ ] `gh repo edit --visibility public`;
- [ ] `npx skills add mikey-semy/finetooth` will work as is; skills.sh telemetry is received only
      by public GitHub repositories — after opening, the kit will land in their catalogue;
- [ ] a submission to skill catalogues (the community has several; Anthropic has
      `anthropics/skills` with its own acceptance rules), an entry in awesome lists;
- [ ] a short screencast or GIF: `setup` → `coverage` → `prompt` → `check`;
- [ ] a mirror — optional: `git push --mirror` to a second address; an analysis of forge
      mirroring is in the first project's knowledge base.

## 3. Who is nearby: neighbours on GitHub

Projects from [`prior-art.md`](prior-art.md) are not repeated (doorstop, mergejury,
claude-review-all, repomix, aider, DefectDojo, syzbot, OpenFastTrace, spec-kit, ESLint,
Betterer). A "non-standard" licence — read `LICENSE` by hand.

### Whole-repository audit by an agent — our class

| Project | ★ / licence / push | What it does | They have, we don't | We have, they don't |
|---|---|---|---|---|
| [hadriansecurity/OpenHack](https://github.com/hadriansecurity/OpenHack) | 742 / MIT / 06.2026 | a file-based workspace for white-box security review: recon → routing → expert scenarios → triage → `findings/*.md`; each phase is a prompt-render command plus a recorder command that checks the agent's answer before the next step; a human approves every transition. **The closest in design.** | a coverage contract "unit × expert": skipping a pair must have a recorded `coverage_decision`; triage as a separate gate with an independent agent; evidence snippets must match the cited lines | a file→block map that fails on an unowned file, fingerprints of what was reviewed, roots with a guard, a fix reviewer, tests |
| [alibaba/open-code-review](https://github.com/alibaba/open-code-review) | 40,174 / Apache-2.0 / 09.2026 | Alibaba's internal reviewer: a deterministic pipeline (file selection, bundling, rules) plus an agent; can scan a whole directory, resumable sessions, JSON for CI. The OpenCodeReview paper (arXiv 2608.09290): the AACR-Bench benchmark, 5–15× fewer tokens than Claude Code | built-in rules by defect class; a benchmark measurement; OpenSSF Gold; a hygiene reference | no roles, blocks, hypotheses, file coverage — it is a tool, not a process |
| [PurCL/RepoAudit](https://github.com/PurCL/RepoAudit) | 444 / non-standard / 03.2026 | autonomous audit without compilation: tree-sitter + interprocedural data-flow, a validator against hallucinations; NPD/leaks/UAF in C/C++/Java/Python/Go. By the paper (ICML 2025): 40 real bugs, precision 78%, $2.54 and 0.44 h per project | **a corpus with known answers** in `benchmark/` by language — a ready form for direction 1 | process, roles, coverage |
| [KeygraphHQ/shannon](https://github.com/KeygraphHQ/shannon) | 48,325 / AGPL-3.0 / 09.2026 | a white-box pentester: sources → recon of the live application → exploitation agents → report; "no exploit, no report", 1–1.5 h per run | `COVERAGE.md` — a table by OWASP WSTG with an explicit "what we do not check" | everything beyond five classes of web vulnerabilities |
| [GitHubSecurityLab/seclab-taskflow-agent](https://github.com/GitHubSecurityLab/seclab-taskflow-agent) | 233 / MIT / 09.2026 | a YAML grammar of multi-agent "taskflows" with MCP tools (incl. CodeQL), checkpoints, a **run manifest** with model, time, outputs; 80+ vulnerability reports at GitHub | a run manifest (direction 6), a reproducible task | coverage, method |
| [Iron-Ham/claude-deep-review](https://github.com/Iron-Ham/claude-deep-review) | 38 / MIT / 03.2026 | 49 parallel "dimension" agents write findings into a temporary directory, a synthesis agent merges | — | a verifier, coverage, state in git |
| [taka-avantgarde/Due-diligence-engine](https://github.com/taka-avantgarde/Due-diligence-engine) | 14 / Apache-2.0 / 08.2026 | "AI technical due diligence": an assessment PDF along five axes for an investor. The class on GitHub is nearly empty, the rest is commercial | — | everything checkable |

### PR review — the neighbouring class, not ours

The diff, not an inventory; no coverage denominator; no separation of roles (except the
"independent reflection" at open-code-review).

- [The-PR-Agent/pr-agent](https://github.com/The-PR-Agent/pr-agent) — 13,125★, MIT: the first
  OSS PR reviewer; a compliance checklist as a file in the project's repository.
- [reviewdog](https://github.com/reviewdog/reviewdog) — 9,618★, MIT, not an LLM: transport of any
  linter's findings into PR comments with `fail_level` — a ready form of gates for a guard.
- [danger-js](https://github.com/danger/danger-js) — 5,511★, MIT: review rules as code.
- [mattzcarey/shippie](https://github.com/mattzcarey/shippie) — 2,502★, MIT; [kodus-ai](https://github.com/kodustech/kodus-ai) —
  1,414★, AGPL core, AST + LLM; [Nayjest/Gito](https://github.com/Nayjest/Gito) — 435★, MIT, can
  drive Claude Code and Gemini CLI as a backend.
- Closed, names only: CodeRabbit, Cursor Bugbot, Copilot review, Ellipsis, Greptile.

### Skills for review — our shelf

| Project | ★ / licence | What it contains | What it lacks |
|---|---|---|---|
| [trailofbits/skills](https://github.com/trailofbits/skills) | 7,218 / CC-BY-SA-4.0 | ~50 plugins. `c-review`: **a ledger per pair (unit × question)**, `ledger-gate.json` with the exact list of unchecked pairs, `coverage: null` = "not measured", not "complete". `code-improver`: a cycle review → fix → re-review with a ledger between rounds and **escalation on non-convergence**; strict separation of reviewer and fixer. `fp-check`: six mandatory gates before a verdict. `variant-analysis`, `semgrep-rule-creator`, `post-patch-validation`. Issue template `trophy-case.yml` | a single file map per project, block statuses, hypotheses with verdicts, a guard with a threshold; no evals |
| [obra/superpowers](https://github.com/obra/superpowers) | 290,650 / MIT | `requesting-code-review` (the reviewer gets a SHA and requirements, not the session history) and `receiving-code-review` ("check the comment against the code, do not agree out of politeness") | the whole repository, coverage, state |
| [mattpocock/skills](https://github.com/mattpocock/skills) | 268,451 / MIT | `improve-codebase-architecture` — the only "audit of the whole codebase" in the top of the catalogue: hotspots from commit history, a "deletion test", an HTML report, a stop at the human's choice | coverage |
| [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) | 98,694 / MIT | `code-review-and-quality`: five axes, an approval standard from the Google guide, severity | the whole repository |
| [anthropics/knowledge-work-plugins](https://github.com/anthropics/knowledge-work-plugins) | 25,491 / Apache-2.0 | `code-review`: four lenses, an Approve/Request Changes verdict; the built-in `/code-review` of Claude Code — four agents, a confidence threshold, the PR diff only. `anthropics/skills` (177,818★) has no review skill | the whole repository |
| [awesome-skills/code-review-skill](https://github.com/awesome-skills/code-review-skill) | 1,993 / MIT | 32 guides by language, six severity levels | tick-boxes without "how to prove" — an example of what not to take into the lens bank |

**What a review skill typically contains:** 4–5 axes, a severity vocabulary, an output format,
an instruction "check, do not re-read", sometimes rules by language. **What nobody has:** a
coverage denominator per project, state between sessions in git, a findings register with a
lifecycle. The closest are the Trail of Bits ledgers, but they live for one run.

### Review state and traceability in git

- [google/git-appraise](https://github.com/google/git-appraise) — 5,309★, Apache-2.0, **dead
  since 08.2023**: review as git notes. The lesson: state in git objects survives branches but is
  not readable by eye in a diff — our choice "in the tree" is deliberate.
- [Radicle](https://github.com/radicle-dev/heartwood) — patches and reviews as objects in git, append-only.
- [strictdoc](https://github.com/strictdoc-project/strictdoc) — 392★: requirements in text and
  **coverage of sources by requirements in both directions** (code without a requirement / a
  requirement on non-existent code) — this is exactly direction 4.
- [sphinx-needs](https://github.com/useblocks/sphinx-needs) — 304★, MIT: the same matrices.

## 4. Hygiene of the best: what all the good ones have

Compared: `alibaba/open-code-review`, `trailofbits/skills`, `obra/superpowers`, `OpenHack`,
`pr-agent` (plus reviewdog and shannon).

All have: `LICENSE`; a README with a one-line install on the first screen and a list of
harnesses; `AGENTS.md`/`CLAUDE.md` in the root; issue templates in yml with `config.yml`; CI that
checks **the skill format itself** (Trail of Bits also has a self-test of the validator, "so that
a check that stopped catching does not stay green forever" — our own mutation principle); tags and
releases with auto-assembled notes; **dog-fooding** — the repository reviews its own PRs with its
own tool.

None have: `CITATION.cff`; a tests badge on skill repositories; a CHANGELOG on skill repositories
(Trail of Bits has neither releases nor history — we have both).

finetooth already has: LICENSE, CHANGELOG, AGENTS.md, tests, `skills-ref validate` in CI.
What is missing — the list in section 2.

## 5. Parallels with the ROADMAP

| Direction | Who solved something similar | What to take |
|---|---|---|
| **1. Measure the misses** | RepoAudit `benchmark/` by language; AACR-Bench (200 PRs × 1505 expert comments, a metric by class); Shannon `COVERAGE.md` | the form of a corpus with known answers; publication by class, not as one number; a "not checked" row in the coverage table |
| **3. Regression by gates** | trailofbits `semgrep-rule-creator` + `variant-analysis` + `post-patch-validation`; reviewdog `fail_level`; seclab-taskflows in CI of Drupal and WordPress modules | a guard as a rule + "find the missed variants after the patch"; transport of the guard into CI. A gate "the rule disappeared" still exists nowhere |
| **4. Third layer of coverage** | trailofbits `c-review` — a ledger (unit × question) with the exact list of unchecked pairs; OpenHack — skipping a pair is lawful only with a recorded `coverage_decision`; StrictDoc — a two-way report | "hypothesis × file" as a ledger; a status "deliberately skipped with a reason" instead of "uncovered" |
| **6. Run archive** | seclab-taskflow-agent — a run manifest with model, time, outputs | the manifest form |
| **9. Economics** | OpenCodeReview — determinism at three points gives 5–15× token savings; RepoAudit — $2.54 per project as a reference for a narrow pass | filter tool output deterministically, rather than compacting the hunter's context; automatic logging of spend into the manifest |
| **11. Fix phase as a gate** | trailofbits `code-improver` — a ledger between rounds and **escalation on non-convergence** (repeat, non-decrease, "moved" → a design decision is needed, not another round); OpenHack — triage as a durable gate; superpowers `receiving-code-review` | a stopping rule for fix review rounds: convergence, not the number of findings |
| **12. Seams** | [adamtornhill/code-maat](https://github.com/adamtornhill/code-maat) — 2,631★: `coupling`, `soc`, a cut-off by commit size; mattpocock `improve-codebase-architecture` — hotspots as input | the algorithm and thresholds for the `coupling` command |
| **13. Threat model** | [OWASP/pytm](https://github.com/OWASP/pytm) — 1,169★, the model as code; [Threagile](https://github.com/Threagile/threagile) — a YAML model; OWASP threat-dragon — a rules engine generates threats | a textual flow diagram as a block artefact that outlives deleting the review directory; generate the "boundary × STRIDE" list by rule |
| **14. Lens bank** | trailofbits `sharp-edges`, `insecure-defaults`, `constant-time-analysis` — one skill per property with a verification workflow; addyosmani — five axes with a source | the form "what to check → how to prove"; awesome-skills — an example of what not to take |

**Which of this is our distinction, one that none of the neighbours has:** the file → block map
that fails on an unowned file, hypotheses with mandatory verdicts, fingerprints of what was
reviewed, a findings register with a lifecycle in git, roots with a guard from the third repeat,
four roles with a fix reviewer, and tests of the tool with mutations. This is what should go onto
the first screen of the README when opening.

⚠️ Not verified: the number of installs from skill catalogues — their count; RepoAudit "$2.54,
precision 78%" and OpenCodeReview "5–15×" — from the authors' papers on their own benchmarks;
OpenHack calls itself a research prototype and publishes no trophies.
