# T4 · Documentation and the repository contract

## Why this block exists

The public face of the kit: README (en, ru), CHANGELOG (en, ru), CONTRIBUTING, RELEASING,
SECURITY, NOTICE, the codes of conduct, AGENTS.md, CI workflows and issue templates. They
promise behaviour, a release discipline and a security boundary to people who will never read
`review.py`. In two days the CHANGELOG's Unreleased section grew by dozens of entries written
under deadline, some by agents; one of them carried wrong totals (T1, R5-002). A promise the
tool does not keep is a defect of the kit, whoever reads it.

## What counts as a finding, and what does not

**A finding:** a claim in README or CHANGELOG that the tool does not do (a command, a flag, a
default, a number); a number that disagrees with its source (a measured cost, a test count, a
finding count); the English and the Russian text saying different things; a CHANGELOG entry in
the wrong section (a breaking change under Added, a fix under Breaking); CI that does not run
what CONTRIBUTING says it runs; a workflow action not pinned by commit where the policy pins;
a release rule in RELEASING that the repository settings do not enforce; a SECURITY promise the
tool breaks (it writes outside `docs/review/` — `summary --out` is the documented exception);
private data (a person, a project's internals) that the NOTICE says is anonymised.

**Not a finding:** prose style; length; typos that do not change meaning.

## Hypotheses specific to this project

1. **CHANGELOG Unreleased vs the code.** Every entry names a mechanism; hypothesis: some entries
   describe the round-6/7 verdict rules that were reverted (issue #17), or totals that no longer
   hold.
2. **README promises vs the tool.** Commands, flags and defaults named in README (both languages)
   exist and behave as described: `coupling` thresholds, `order` keys, `summary --aged`,
   `fix_gate`, `run-role.sh` caps, `refs`.
3. **en ↔ ru divergence** in README and CHANGELOG — a section present in one only, a different
   number.
4. **CI vs CONTRIBUTING.** CONTRIBUTING says tests + `skills-ref validate`; the workflow pins
   actions by commit; branch protection requires the check. Hypothesis: a stated rule is not
   enforced (e.g. the DCO sign-off is asked for but not checked).
5. **SECURITY boundary.** "Only `docs/review/` is written" — `summary --out` writes elsewhere by
   request; `run-role.sh` writes to `$TMPDIR`; `axes.py` reads streams. Hypothesis: a write outside
   the promised places exists that SECURITY does not mention.
6. **NOTICE and anonymisation.** Hypothesis: a project name or internal detail of a reviewed
   project (the author's or the owner's) reached a public file — CHANGELOG entries quote live
   registers ("setfork H5.12", "26 rows in 15 blocks").
7. **RELEASING vs what happened.** RELEASING says at most one release a week, the fixer does not
   bump versions, gate 3 is a live run. Hypothesis: a rule is described that the process cannot
   check (there is no mechanical gate for "one a week").

## Acceptance criterion

A table **claim → source → verdict** for every numbered or behavioural claim in README (en, ru)
and in CHANGELOG Unreleased (en, ru): the file and line of the claim, where it is checked (code,
test, measurement), and whether it holds.
