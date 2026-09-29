# T2 — verifier report

## What I ran myself

Three stand scripts, run once each (the role's "one file, run once" rule), against a tree at
`2e7c39f`, level with `origin/dev` after `git fetch` — `git log HEAD..origin/dev --oneline` is
empty and the only dirty paths are this review's own.

The stands built throwaway git repositories and drove `review.py` from the skill folder:

- a fresh copy of `examples/toy`, committed, then `check`, `coverage`, `refs` — and two
  mutations on it (exclude `README.md`; strip the finding id from `quota.ts`) to see which
  refusal belongs to which cause;
- `assets/blocks.example.json` installed as a real `docs/review/blocks.json`, with the paths it
  names created, then `init` and `check` — and the mutation of sorting its blocks by phase;
- a minimal two-file repository into which draft findings files were written by hand, imported
  and checked: a rejected finding whose `claim` is worded exactly as `verify.md:123` asks, the
  same finding with a claim that starts with the word the gate wants, three findings with and
  without a `root` field, a duplicate with and without `dup_of`, a 400-character claim;
- `prompt` for every role in both languages, and for `fix` and `fixreview` at rounds 1 and 2,
  with the report paths and the `{{FIX_REPORT}}` line read out of the assembled prompts;
- `make review init` against the shipped Makefile snippet;
- `setup --project … --lang ru` in an empty repository, to read the checklist it prints;
- a mechanical comparison of all five English/Russian template pairs (headings, ordered-item
  numbering, every number of two digits or more, every placeholder);
- `GateRegistryTest.GATES` parsed out of `tests/test_review.py` with `ast`, not with a regex.

`skills-ref` is not installed on this machine, so the Agent Skills validator was not run. That
is the one thing in this block I could not execute; everything below rests on a run.

## Verdicts on hunter findings

| id | verdict | severity after checking | justification |
|---|---|---|---|
| T2-001 | CONFIRMED | medium (was medium) | Reproduced. A finding with `"status":"rejected"` and the claim `No defect: the route is wrapped in RequirePermission…` — the shape `verify.md:123` and `verify.ru.md:123` ask for — imports cleanly and then `check` prints `finding B1-001: rejected, but the reject reason is not recorded` and exits 1. The same finding with the claim rewritten to start `Rejected: …` passes. A third, with the word `rejected` in the middle of the claim, fails too: `re.match` at `review.py:3084` is anchored, as the hunter said. The code's own comment at `review.py:3080-3082` says the claim form is "as the role template instructs" — no template instructs it, in either language. Severity kept: this fires on every block that rejects anything, which is most of them. |
| T2-002 | CONFIRMED | medium (was medium) | Reproduced in both directions. Three findings written in the exact JSON of `hunter.md:155` import, and `check` says nothing about roots while `review roots` prints `no roots recorded`. The same three with a `root` field added produce `root 'hand-written copy of the predicate': 3 instances (B1-004, B1-005, B1-006) and no guard`. So the mechanism works and only the prompt is missing. Same for duplicates: with `dup_of` the gate validates the target, without it `check` says `marked duplicate, but not of what exactly` — and the field appears in no template, while `verify.md:70-76` and lesson 16 both prescribe the practice. `set-finding` has `--rule`, `--dup-of` and `--reason` but no `--root`, so the draft file is the only road into the register. Severity kept: this is the block's most serious defect. |
| T2-003 | CONFIRMED | low (was medium) | Reproduced. `prompt B1 --role fix` tells the agent to write `…B1-one.fix.md`; `--role fix --round 2` tells it `…B1-one.fix-2.md`; `--role fixreview --round 2` opens with "the fixer … has written the report `docs/review/reports/B1-one.fix-2.md`". `SKILL.md:92` gives the fixer's command without `--round` while `SKILL.md:102` documents it for the reviewer, so a round-2 fixer run by the book overwrites round 1's report and the reviewer is pointed at a file nobody wrote. Severity lowered: `docs/review/` is committed, so the overwritten report is recoverable from `git log`, and `fixreview.md:12` tells the reviewer to read the diff and not the report, so the dangling path costs one failed open. It is a real gap, not a lost artefact. |
| T2-004 | CONFIRMED | low (was medium) | Reproduced. In a fresh copy of the toy, `review refs` prints `src/billing/quota.ts:1: H1-001` and exits 1; `check` reports it as a warning. Removing the id from the comment makes `refs` answer `no finding of the register is named outside docs/review/`. The cited id is indeed the wrong one — `H1-001` in the toy's register is "Empty role parses into a user session" in `src/auth/session.ts`. Severity lowered: it is a warning in `check`, it changes no behaviour of the tool, and its whole cost is that the reference example teaches a practice `fix.md:24-26` and `entry-point.md:64-65` forbid. That is a divergence from documentation, which the scale calls low. |
| T2-005 | CONFIRMED | low (was medium) | Reproduced. Copying `examples/toy` into a fresh repository and running `check` — exactly what `examples/toy/README.md:21-24` instructs — gives exit 1 with `1 files belong to no block`, and `coverage` exits 1 naming `README.md`. Adding `README.md` to the exclusions removes that line and nothing else. Severity lowered for the same reason as T2-004: the tool behaves correctly, the example's own claim that it passes is wrong. Note that this is only half of why the toy is red — see T2-013. |
| T2-006 | CONFIRMED | low (was low) | Reproduced. Installed as a real `blocks.json`, the sample gives `H13: phase 1 comes after phase 2 — the blocks array is ordered by phase, because that is the execution order`, and sorting its four blocks by phase removes exactly that line. The array order really is `H1`(1), `V1a`(2), `H13`(1), `E1`(3), and `check_definition` names this file as "the example" in three separate refusals. |
| T2-007 | CONFIRMED | low (was low) | Verified by reading both files out in one run: everything after the `---` in `agent-banner.ru.md` is byte-for-byte the English banner of `agent-banner.md`. Only the eight explanatory lines above it are Russian. |
| T2-008 | CONFIRMED | low (was low) | Reproduced. `setup --project Проект --lang ru` writes a Russian `blocks.json`, a Russian invariants skeleton and a Russian `docs/review/README.md`, and then prints a checklist naming `invariants.example.md`, `blocks.example.json`, `manifest.example.md` and `agent-banner.md` — the English four. A scan of every tracked file for the names of the four Russian samples finds them only in this review's own `coverage.tsv`: nothing in the kit points at them. The entry point in the same function is selected by language, which shows the selection was intended and simply not carried across. |
| T2-009 | CONFIRMED | low (was low) | Verified mechanically and then by reading the file. `entry-point.md` and `entry-point.ru.md` contain none of the strings `fixreview`, `fix_gate`, `--append`, `restamp`, `backfill`; step 8 is still "Diff review — by those who did not write it", the `prompts/` row lists three roles, and "What counts as finished" repeats the completion condition without the fix gate. All of it is in `SKILL.md`, which is not installed into the project. |
| T2-010 | PLAUSIBLE | low (was low) | Neither confirmed nor refuted, and I say what is missing. What is true and checked: `{{VOLUME}}` occurs only in `hunter.md` and `hunter.ru.md`; neither fix-review template names `--scope` or any measure of the diff; `{{SCOPE_LINE}}` is a sentence the tool injects only when the lead passes the flag, not a standing instruction; rule 1 says "the diff is pasted below in full — read it" with no condition. What cannot be shown from the code is the failure itself: whether an agent handed a 193 KB diff silently reports on the part it read. That needs a measured run of the role on a large diff, which is a `proof: measured` question and not this block's. |
| T2-011 | CONFIRMED | low (was low) | Verified by reading the three texts side by side in one run. `lessons.md:57-59` and `lessons.ru.md:53-55` say each deferred finding is fixed or rejected with a reason before the review ends. `review.py:176` renders the deferred ones under "Accepted risks (deferred with a reason)" and `review.py:177` has a message for the empty case, so the section exists for a non-empty one. `SKILL.md:143` and `entry-point.md:69-70` both state the completion condition without mentioning deferred findings at all. Two kit documents give opposite answers to "is the review finished". |
| T2-012 | CONFIRMED | low (was plausible) | Upgraded from plausible, because I ran it. The snippet defines `review-check`, `review-coverage`, `review-findings`, `review-import`, `review-init`, `review-next`, `review-prompt`, `review-status` and no `review`. With the snippet as the Makefile, `make review init` answers `make: *** No rule to make target 'review'. Stop.` and exits 2. `SKILL.md:28-30` offers `make review` as an example of what the `cli` field may hold, and `project_cli` at `review.py:81-86` builds every hint and refusal from that string. The `package.json` snippet does define the generic target, which is what makes `npm run review --` work. |

Nothing was rejected. That is unusual and worth stating plainly: the hunter's twelve findings all
survived execution, and the only corrections are four severities lowered and one confidence
raised. Its two acceptance tables were also largely right — see below for the two corrections.

## Verdicts on recorded findings

Nothing is recorded against T2 in the register yet, so this table is empty. The hunter's twelve
draft findings are not register records; they are ruled on above.

## Own findings

### T2-013 · low · The toy's `findings.md` can never equal the regenerated one, so `check` is red in every copy of the example
**Location:** `examples/toy/docs/review/findings.md:3` (and `examples/toy/docs/review/blocks.json`)
**What is wrong:** the generated header of the shipped `findings.md` reads "GENERATED from
`findings.jsonl` by `python3 <skill>/scripts/review.py findings`". `render_findings_md` writes
that line from `CLI`, and `CLI` is `project_cli()` — the `cli` field of `blocks.json`, or, when
there is none, `default_cli()`, which is `python3` plus the real absolute path of the tool. The
toy's `blocks.json` has no `cli` field. So the header on disk carries a literal placeholder that
the tool never produces, and the comparison at `review.py:3106-3107` — by content, deliberately
not by mtime — can never succeed.
**Failure scenario:** copy `examples/toy` into a fresh repository, commit, run `check`, as
`examples/toy/README.md:21-24` instructs. It exits 1 with `findings.md diverged from
findings.jsonl` in addition to the unowned `README.md` of T2-005. I ran it; regenerating with
`review findings` rewrites the header to this machine's path and the line goes away, which is
precisely the point — it will come back on the next machine. Adding `"cli": "python3
<skill>/scripts/review.py"` to the toy's `blocks.json`, together with T2-005's exclusion, makes
`check` exit 0. That single pair of edits is the whole fix and it is what proves both findings.
**Why it is a defect:** this is the second, independent reason the reference example of a green
review is not green, and unlike T2-005 it is invisible on inspection: the file looks generated
because it says it is.
**Confidence:** confirmed
**Root:** the kit's own gates are never run over examples/toy

### T2-014 · low · `roots` is named by no message of the tool, by `SKILL.md` and by the entry point, so the class view the guard gate rests on is undiscoverable
**Location:** `skills/finetooth/SKILL.md:126-139`
**What is wrong:** I extracted every `add_parser` name from `review.py` and matched it against
`SKILL.md` and `entry-point.md`. Of the 23 subcommands, four are absent from `SKILL.md`:
`hypotheses`, `refs`, `roots`, `version`. Of those, `hypotheses` and `version` are in the entry
point that `setup` installs into the project, and `refs` is named inside the `check` warning
that reports a reference in the code. `roots` is in none of the three: no refusal, no warning,
no document. The guard gate's own refusal names `set-finding <ID> <status> --rule`, not the
command that lists the class.
**Failure scenario:** a lead session meets `root 'X': 3 instances (…) and no guard` and wants to
see the class before deciding what guard closes it. `SKILL.md` and `docs/review/README.md` are
the two documents it has, and neither mentions `roots`; it reads the register by hand instead,
or skips the class view and records a guard on what the refusal happened to list — the refusal
names only the first four ids.
**Why it is a defect:** hypothesis 7 of the manifest, in the direction of a command a user
needs and cannot find. Together with T2-002 the whole defect-class mechanism is unreachable
from the prompts and from the documents: nothing asks an agent to write the field, and nothing
tells the lead how to look at the result.
**Confidence:** confirmed
**Root:** the defect-class mechanism is announced in no document an agent or a lead reads

### T2-015 · low · Both banner assets hardcode `make review-status`, and `setup` substitutes nothing in them
**Location:** `skills/finetooth/assets/agent-banner.md:13` (and `agent-banner.ru.md:13`)
**What is wrong:** the banner says "run `make review-status` to see where it stands". It carries
no `{{CLI}}` placeholder, and `cmd_setup` does not read the banner at all — step 5 of its
checklist only prints the path to the file. The sibling asset `entry-point.md` does carry
`{{CLI}}` and is substituted at `review.py:3488`, so the mechanism exists and this file does not
use it. Rule 5 of the kit's own `AGENTS.md` is that hints are assembled from `CLI` and that no
`make review-check` may sit in a string.
**Failure scenario:** a Go or Rust project with no Makefile runs `setup`, follows step 5, and
pastes the banner into its root instructions file. Every session of that project from then on
is told to run a command that does not exist, in the one document whose whole purpose is to
stop a new session from starting a parallel review. The kit's own `AGENTS.md` banner does not
use the sample's wording — it names the real path to the tool — which shows the author hit this
and worked around it by hand.
**Confidence:** confirmed
**Root:** shipped assets hardcode `make` as the project's CLI

## Note for the lead: the roots in the final findings file

The final file carries a `root` on fourteen of the fifteen findings, which groups them into six
classes. One of them has three instances — `the kit's own gates are never run over examples/toy`
(T2-004, T2-005, T2-013) — so `check` will demand a guard for it as soon as the block is
imported. That is the correct signal and the guard is obvious: a test that copies
`examples/toy` into a temporary repository and runs `check`, `coverage` and `refs` over it. The
three findings have separate fixes and one common cause, which is the definition this kit uses.

I only knew to write the `root` field at all because I read `roots_of` and the guard gate in the
tool. No template told me to, and the schema I was handed does not have the field. That is
T2-002, demonstrated on this very file.

## Hypothesis verdicts

T2.1 — checked: I parsed `GateRegistryTest.GATES` with `ast` and it holds 63 tuples, not the 64 the hunter's table claims; its table is one row long, which is harmless. The two holes it found are the real ones and both are reproduced by execution above (T2-001, T2-002). I rebuilt the riskiest cells independently rather than the whole table: the named-files gate at `review.py:3239-3258` scans the union of `<ID>-*.md`, so the hunter template naming the list satisfies it and the verifier template needs no file list of its own; `verify_report_problem` demands substance, a finding verdict and a coverage verdict, and `verify.md:54-59` and its report skeleton announce all three including the quotation rule; the coverage-limits gate and the freshness gate are announced in both hunter templates. I found no third hole.

T2.2 — checked: a regex for the round-6/7 wording ("a verdict is a clause with a basis", "plain text, not backticks", and the Russian equivalents) over all four role templates in both languages, the lessons, `SKILL.md` and every asset returns nothing but a table header in `verify.ru.md:108` that happens to contain the word for "justification". What the templates do say matches `unquote_verdicts` exactly: only a code span whose whole content is a vocabulary word is blanked, a span carrying a clause is kept. Nothing is left over from the reverted parser.

T2.3 — checked: all five English/Russian pairs compared mechanically in one run. Headings are equal in count for every pair (hunter 20/20, verify 18/18, fix 6/6, fixreview 13/13, lessons 8/8); ordered items are equal in count (7/7, 0/0, 15/15, 12/12, 42/42); the sets of placeholders are identical in every pair; and the sets of numbers of two digits or more are identical in every pair, so 220, 700, 329, 118, 165 and the rest are present in both. The drift is not in the role templates — it is in the assets, as T2-007, T2-008 and T2-015 record.

T2.4 — checked: I collected every `{{…}}` in `references/` and `assets/` and every key of the `subs` dictionary, and then assembled all four role prompts in both languages and grepped the output for survivors. No placeholder was left unfilled in any of the eight prompts, no key of `subs` is used by no template, and the only two placeholders `cmd_prompt` does not substitute are `{{CLI}}`, which `cmd_setup` fills in the entry point, and `{{DIFF}}`, which is filled after the placeholder check for the fix-review role. The full table is below.

T2.5 — checked: `blocks.example.json` loads and passes `check_definition` — the only thing wrong with it is the phase order, filed as T2-006. Both manifest samples parse: `hypotheses B1` counts 14 hypotheses in the English one and 14 in the Russian one, and a repository carrying the English manifest and the English invariants sample passes `check` with exit 0. Neither invariants sample holds an unfilled placeholder. `package-json-snippet.json` is valid JSON and does define the generic target the Makefile snippet lacks.

T2.6 — checked: confirmed by execution, and worse than the hunter thought. A fresh copy of `examples/toy` fails `check` for two independent reasons — the unowned `README.md` and the diverged `findings.md` — and fails `refs` for a third. Two mutations, one per cause, were needed to reach exit 0, which is what proves they are two findings and not one. T2-005 and T2-013.

T2.7 — checked: every file `SKILL.md` links to exists and sits one level deep, and every command and flag it names is real. In the other direction, four of the 23 subcommands are absent from it; three are reachable from the entry point or from a refusal and `roots` is reachable from nothing, filed as T2-014. `--round` for the `fix` role is real and undocumented, filed by the hunter as T2-003 and reproduced above.

T2.8 — checked, with one part not checked and recorded as a limit. Verified by running: the name equals the directory, the description says what it does and when to use it, the body is 160 lines against the 500 ceiling, `metadata.version` "0.7.0" equals `VERSION` at `review.py:60`, and `skills/finetooth/LICENSE` is byte-identical to the root `LICENSE`. The part I could not check is the frontmatter schema as the official validator sees it: `skills-ref` is not installed on this machine.

T2.9 — checked: both lessons files read in full against the gates as they stand. The lessons about the named-file rule, the claim and scenario caps, the fingerprints, the duplicate-by-root definition, the third-instance guard and the fix gate all match live mechanisms. One contradiction, the hunter's T2-011, confirmed above by reading lesson 13, the summary heading and the two completion conditions together.

T2.10 — checked: a diff containing braces is safe, because the placeholder pass runs on the template before the diff is pasted, and `--scope` adds a sentence without filtering. What is absent is any statement of the diff's size and any instruction for one that does not fit, which is the hunter's T2-010; I could confirm the absence but not the failure, so that finding stays at plausible.

## Acceptance tables

### 1. Gate → template

The hunter's table is the block's deliverable for this criterion and I did not rebuild all 63
rows; that would have been a re-reading of someone else's conclusion, which is the thing this
role exists not to do. What I did instead: I checked the registry's size with a parser (63
tuples, the hunter says 64), reproduced both of its empty cells by execution, and independently
rebuilt the four cells where a hole would cost the most. The result of those four:

| gate | artefact from | announced in English | announced in Russian | how I checked |
|---|---|---|---|---|
| `: of block files are not named by full path in any report` | hunter | `hunter.md:81-87` | `hunter.ru.md:82-87` | read `review.py:3239-3258`: the gate concatenates every `<ID>-*.md` of the block, so the hunter's list satisfies it for both reports and the verifier template correctly needs no list of its own |
| `verify_report_problem` (substance, finding verdict, coverage verdict) | verify | `verify.md:54-59`, `104-116` | `verify.ru.md:55-59`, `104-116` | read the function: three separate demands, all three announced, including the rule that a quoted line does not count |
| `: rejected, but the reject reason is not recorded` | verify | empty | empty | reproduced by import and `check`; the anchored form is announced nowhere — T2-001 |
| `root '': instances () and no guard` | hunter (field) + fix (guard) | empty for the field, `fix.md:80-99` for the guard | empty for the field, `fix.ru.md:80-99` | reproduced in both directions: the gate is silent on a template-shaped draft and fires as soon as `root` is present — T2-002 |

### 2. Placeholder map

Rebuilt mechanically, not read: every `{{…}}` occurrence in `references/` and `assets/` against
the keys of `subs`, then eight assembled prompts checked for survivors.

| placeholder | filled by `cmd_prompt` | where used |
|---|---|---|
| `{{PROJECT}}`, `{{BLOCK_ID}}`, `{{BLOCK_TITLE}}`, `{{REPORT_PATH}}`, `{{INVARIANTS}}`, `{{MANIFEST}}` | yes | all four roles, both languages |
| `{{BLOCK_ROLE}}`, `{{PROOF_RULE}}`, `{{FILES_HEADING}}`, `{{FILES}}`, `{{RECORDED}}` | yes | hunter, verify, both languages |
| `{{BLOCK_GOAL}}`, `{{FILE_COUNT}}`, `{{VOLUME}}`, `{{REF_FILES}}`, `{{NEXT_ID}}` | yes | hunter, both languages |
| `{{HUNTER_REPORT}}` | yes | verify, both languages |
| `{{FINDINGS}}`, `{{GATES}}` | yes | fix, both languages |
| `{{FIX_REPORT}}`, `{{ROUND}}`, `{{SCOPE_LINE}}`, `{{DIFF_RANGE}}` | yes | fixreview, both languages |
| `{{DIFF}}` | after the placeholder check, for the fix-review role only | fixreview, both languages |
| `{{CLI}}` | no — by `cmd_setup` at `review.py:3488` | entry-point, both languages |

No placeholder in any template is left without a value, and no key of `subs` is used by no
template. `{{DIFF}}` is exempted from the "nothing left over" check for every role and not only
for the fix reviewer, so a `{{DIFF}}` written into another template would reach the agent as
literal text; no template does today, so I note it here rather than filing it.

## Block coverage status

Complete. All 44 files of the block have been read in full by someone, and I read the
following myself rather than taking the hunter's word for them: `SKILL.md`, `references/hunter.md`,
`references/verify.md`, `references/fix.md`, `references/fixreview.md`, `references/lessons.md`,
`assets/entry-point.md`, `assets/invariants.example.md`, `assets/journal.example.md`,
`assets/agent-banner.md`, `assets/agent-banner.ru.md`, `assets/makefile-snippet.mk`,
`assets/package-json-snippet.json`, `assets/blocks.example.json`, `skills/finetooth/LICENSE`
(by byte comparison with the root one), and every file of `examples/toy` — its `.gitignore`,
`README.md`, `docs/review/README.md`, `blocks.json`, both block manifests, `coverage.tsv`,
`findings.jsonl`, `findings.md`, `invariants.md`, `journal.md`, `state.json`, both H1 reports,
`H1-findings.jsonl`, `src/auth/guard.ts`, `src/auth/session.ts`, `src/billing/quota.ts`,
`tests/guard.test.ts`. Both manifest samples were read through the tool's own hypothesis parser
in both languages. The six remaining Russian files — `hunter.ru.md`, `verify.ru.md`, `fix.ru.md`,
`fixreview.ru.md`, `lessons.ru.md`, `entry-point.ru.md`, `invariants.example.ru.md`,
`journal.example.ru.md` — I compared with their English counterparts mechanically rather than
reading as prose; see the limits below.

## Coverage limits

- **`skills-ref validate skills/finetooth` was not run.** The binary is not installed on this
  machine. Everything the Agent Skills contract requires that can be checked without it was
  checked by running: name, description, body length, version equality, link depth and
  existence, LICENSE equality. What remains unverified is the frontmatter schema as the
  official validator reads it, including the non-standard prose `license:` value. CI runs the
  same validator, so this is covered elsewhere; it is not covered here.
- **The Russian files were compared structurally, not read as prose.** Headings, ordered-item
  numbering, every number of two digits or more and every placeholder were compared
  mechanically for all five pairs, and the Russian manifest sample was run through the parser.
  A meaning shift inside a paragraph whose shape and numbers match would have survived that. As
  the hunter said, translation quality was not judged, and I did not judge it either.
- **The verdict and coverage regexes were not fuzzed.** I checked that the templates describe
  what the parsers do and that the toy's reports pass them. I did not construct adversarial
  reports to find a form of words the gates misread. That belongs to a measured block.
- **T2-010 was not settled.** Confirming or refuting it needs a measured run of the fix-review
  role on a diff of real size, which is a `proof: measured` question. It stays plausible, and
  the next pass over the fix-review role should settle it.
- **`assets/run-role.sh`, `assets/guard-grep.sh` and `scripts/axes.py` were not read.** They
  are T1's files, not this block's; I only confirmed that they exist and carry the flags
  `SKILL.md` promises.
- **`README.md` and `README.ru.md` of the repository were not read.** They are T4's. A
  divergence between them and `SKILL.md` would be found there.
