# finetooth invariants

This file is pasted to EVERY review agent. It decides what the agent will count as a defect
and what as noise. Each rule stands behind something that already broke or was already
promised in public (AGENTS.md, CONTRIBUTING.md, SECURITY.md).

## Context that changes how findings are weighed

- **The tool is a single Python file, standard library only, plus `git`.** It is copied into
  projects on any stack (`npx skills add …`). A dependency, a second runtime, a build step —
  each is a defect, not a style choice.
- **Two live projects run on it** (TypeScript, ~180k lines; and the author's Go + TypeScript +
  Python, ~200k lines) plus the kit itself. The on-disk format of `docs/review/` is a contract:
  a change that a running review has to act on is a `0.X.0` with a Breaking section.
- **State lives on disk, never in the conversation.** `state.json`, `findings.jsonl`,
  `coverage.tsv`, `journal.md` are read back by the tool; the agent's memory is not.
- **The tool's own messages are English; what agents read is bilingual.** Prompt templates
  (`references/<role>.md` + `.ru.md`), assets (`.ru.md`) and the `MSG` table are selected by
  `lang` in `blocks.json`. A string that exists in one language and not the other is a
  defect (`T()` raises `KeyError` at run time, not at import).
- **Two reviews of real projects found: verdict false positives** (`n/a` inside a path,
  numbered acceptance tables read as hypothesis verdicts), **fingerprint parsers that
  diverged** (two parses of one section), **`[handle]` read as a character class by
  git-pathspec**, **paths with spaces breaking a commit check**, **untracked files invisible
  to `git ls-files`**. The pattern: the tool trusts text shape where it should parse.

## Rules whose violation is a finding

### The gate must not go green on a false state
1. **`check` is the product.** Any way to make it pass on a state that is wrong — a report
   that satisfies the regex without the content, a status set without the artefact, a
   fingerprint that does not change when the reviewed text changes — is the most serious
   class of defect here (SECURITY.md names it as a vulnerability).
2. **Every check comes with a test, and the test is proven by a mutation.** A check whose
   mechanism can be disabled while the suite stays green is untested. Look for checks with
   no test, and tests that pass with the mechanism removed.
3. **A refusal names the command that fixes it.** `die(...)` without the way out is a defect:
   the message is read by someone seeing the tool for the first time.

### Text is parsed, not matched
4. **Report parsing tolerates the live language of reports** (tables, free forms, both
   languages) — but a word inside a path, a code span or a fenced block is not a verdict.
   Verdict, coverage, finding-status detection: every regex is a suspect.
5. **git is the source of file truth, not the disk.** Files come from the index (`ls-files -z`,
   `show :path`), paths are handled NUL-separated, patterns go through git-pathspec (a `[` is
   a character class, `*` does not cross `/` without `**`). Any `os.listdir`/`Path.glob` for
   the subject's files, any `.splitlines()` on a path list, is a defect.
6. **Fingerprints cover the whole reviewed text.** `reviewed_sha`, `refs_sha`,
   `hypotheses_sha`, `code_sha` must change when the corresponding text changes and stay when
   it does not (block reordering, whitespace outside content). A fingerprint that misses part
   of its subject silently declares changed code reviewed.

### Contracts with the user
7. **Only `docs/review/` is written** — plus what the user explicitly asked for (`summary
   --out`). Writing elsewhere is a vulnerability by SECURITY.md.
8. **Every number has a source next to it.** Thresholds (7 days, 6000 lines, 3 co-changes,
   95th percentile, turn caps) carry the measurement or the reference in a comment. A bare
   magic number is a finding.
9. **A change to a mechanism is a change to a prompt.** If `check` demands something the role
   template does not tell the agent to produce (in both languages), the gate will go red on
   an honest report — that is a defect of the kit, not of the agent.
10. **The Agent Skills contract:** `SKILL.md` name = directory, description says what and when,
    body under 500 lines, `skills-ref validate` passes; `assets/` and `references/` are what
    `SKILL.md` links to; `LICENSE` inside the skill equals the root one.
11. **Idempotence.** `init`, `coverage`, `findings`, `backfill`, `restamp` re-run without
    changing a correct state; `import` is idempotent for the same draft and appends only with
    `--append`; `set-finding` on several ids is all-or-nothing.
12. **Exit codes mean something.** 0 clean, 1 the state is red (gates), 2 usage/argument
    error; a traceback reaching the user is a defect regardless of the cause.

## What is NOT a finding
- Style, naming, "could be split into modules". The file is one file by decision.
- "Should use a library" — the no-dependency rule is a decision, not an omission.
- A message that could be friendlier, when it already names the fix.
- Missing features from the roadmap (coupling into `coverage`, budget cut-off by rate): the
  review checks what the tool promises today, not what is planned.
- Performance without a measurement: `coverage` on 1,845 files runs in under a second; only a
  demonstrated super-linear path counts.
