# T2 · Prompts, samples and the skill contract

## Why this block exists

The tool is only half of the kit; the other half is what the agents read. Four role templates
in two languages (`references/<role>.md` and `.ru.md`), the lessons, the samples in `assets/`,
`SKILL.md` and the toy example. Every gate `check` holds must be announced to the agent by
its template — otherwise an honest report goes red (invariant 9). T1 changed a dozen gates and
four sets of template paragraphs in seven rounds; the templates were edited under pressure, in
both languages, by different hands. Nobody has read them side by side since.

## What counts as a finding, and what does not

**A finding:** a gate `check` holds that no template (in the review language) tells the agent
to satisfy; a template instruction that `check` refuses (the agent follows it and goes red);
the English and the Russian template of one role saying different things (a rule present in
one only, a different number, a different placeholder); a sample in `assets/` that `check`
would reject or that contradicts the tool (`blocks.example.json` with a field the tool refuses,
a manifest example without the sections the tool parses); `SKILL.md` promising a command, flag
or behaviour the tool does not have, or omitting one a user needs; a placeholder in a template
that `prompt` never fills (or fills with the wrong thing); `examples/toy` whose state `check`
does not pass.

**Not a finding:** wording that could be nicer when it is correct; the length of a template;
translation style where the meaning is the same.

## Hypotheses specific to this project

1. **Gate → template map has holes.** For every gate of `check` (the registry in
   `GateRegistryTest` lists them), the template of the role that produces the checked artefact
   says what to produce. Hypothesis: at least one gate added in T1 (named files by full path,
   quotation rules, the coverage-limits section outside a fence, verdicts outside code spans,
   the fix report shape) is announced in English and not in Russian, or in neither.
2. **The verdict form the hunter template prescribes is the one the round-3 parser reads.**
   After the revert of the parser (issue #17), the templates were taken back to `b43fd49`.
   Hypothesis: some other template or `SKILL.md` still describes the round-6/7 rule ("a verdict
   is a clause with a basis", "plain text, not backticks").
3. **ru and en of each role are the same text.** Section by section: the same rules, the same
   numbers (7 days, 6000 lines, the turn caps), the same placeholders. Hypothesis: they drifted —
   the fix template's rules 11–12 and the fixreview rules 11–12 were added in both, but earlier
   edits may not have been.
4. **Every `{{PLACEHOLDER}}` in every template is filled by `cmd_prompt`**, and every
   substitution `cmd_prompt` makes appears in some template (an unused substitution is dead
   code; a missing one refuses the prompt). `{{RECORDED}}`, `{{NEXT_ID}}`, `{{FINDINGS}}`,
   `{{DIFF}}`, `{{ROUND}}`, `{{SCOPE_LINE}}` in particular.
5. **Samples pass the tool.** `assets/blocks.example.json` loads through `blocks()` validation
   (required fields, `proof`, `risk`, `fix_gate`); `assets/manifest.example*.md` has the
   hypotheses and acceptance sections the parser finds; `invariants.example*.md` has no
   placeholder the setup leaves. Hypothesis: one of them is refused.
6. **`examples/toy` is a green review.** `check` inside it passes on the current tool.
   Hypothesis: it was built on 0.7.0 and the stricter gates (named files, verdict parsing,
   coverage limits) make it red — the example then teaches a broken state.
7. **`SKILL.md` promises only what exists.** Every command it names exists in `review.py`
   (`coupling`, `order`, `summary`, `refs`, `run-role.sh`, `axes.py`), every flag is real, every
   linked file exists. And every user-facing command of the tool is in `SKILL.md` or reachable
   from it. Hypothesis: something drifted either way.
8. **The Agent Skills contract.** `name` = directory, description says what and when, body
   under 500 lines, `LICENSE` inside the skill equals the root one, `metadata.version` equals
   `VERSION`. `skills-ref validate` catches only part of it.
9. **The lessons file matches the method as it is now.** `references/lessons*.md` was written
   before the fix gate, the stop rule for rounds and the verdict parser episode. Hypothesis: a
   lesson now contradicts a rule (for example, advising another round where the stop rule says
   a human decides).
10. **The fix-review template's `{{DIFF}}` handling.** A diff containing `{{SOMETHING}}` is
    pasted after the placeholder check; a diff larger than the context is pasted whole. The
    template says nothing about a diff that does not fit. Hypothesis: a real-size diff (T1's
    first round: 193 KB) makes the prompt larger than the model's useful context, and the
    template gives no instruction for `--scope`.

## Acceptance criterion

The block is not closed without two tables built by reading:

1. **Gate → template.** Every gate in `GateRegistryTest.GATES`: which role produces the
   artefact, the line of the English template that announces it, the line of the Russian one.
   Empty cells are findings or are argued in "Coverage limits".
2. **Placeholder map.** Every `{{…}}` in every template × whether `cmd_prompt` fills it, and
   every key `cmd_prompt` substitutes × which templates use it.
