# T3 · Tests as the gate: are the checks proven

## Why this block exists

CONTRIBUTING promises: every check comes with a test, and every test is proven by a mutation.
The suite grew from 98 to ~250 tests in two days, much of it written by fixer agents under
pressure; `GateRegistryTest` claims 62 of 62 gate sites are held. This block does not read the
tests for style — it **measures** them: a test that passes with its mechanism removed is not a
test. `proof: measured` — the artefacts are mutation runs, not a reading.

## What counts as a finding, and what does not

**A finding:** a mechanism of `review.py`, `axes.py` or `run-role.sh` whose removal leaves the
suite green; a test that is green for the wrong reason (it asserts on a message that is always
printed, it tests a helper the tool does not call, its fixture already satisfies the assertion);
a test that depends on the machine (Python version, locale, git version, `/tmp`, network, the
kit's own repository state) and would go red elsewhere — the gate registry went red in CI on a
quote style (T1); a test that cannot fail (`assertTrue(True)`, an `assertIn` on an empty string);
a guard (`GateRegistryTest`, `SourceRuleTest`, `QuotationMapTest`) that a plausible new shape of
code walks past.

**Not a finding:** test naming, duplication between tests, the suite's run time (unless a test is
slow for a reason that hides a defect).

## Hypotheses specific to this project

1. **Surviving mutants exist outside `cmd_check`.** T1 measured the 62 gate sites of `cmd_check`.
   Hypothesis: mechanisms in `import`, `set-finding`, `restamp`, `backfill`, `summary`,
   `coupling`, `order`, `refs` have survivors — remove one condition at a time and run the suite.
2. **Tests that pass for the wrong reason.** Hypothesis: some test asserts a substring that the
   tool prints in every run (a header, a hint), so the assertion holds whatever the mechanism does.
3. **Machine-dependent tests.** Hypothesis: a test depends on Python ≥ 3.13 behaviour, on the
   locale, on git's default branch name, or on the kit repository's own `docs/review/` (the
   working-directory test was one). Run the suite on Python 3.12 in a container and under
   `LANG=C`.
4. **The guards' blind spots.** `GateRegistryTest` keys a gate by its message; `SourceRuleTest`
   finds parsers by shape; `QuotationMapTest` is a table. Hypothesis: a new gate written in a
   third message shape, or a parser written without the markers the guard looks for, passes all
   three guards.
5. **Stand fidelity.** The test `Stand` builds repositories with a fixed layout; hypothesis: a
   behaviour that depends on a real layout (nested `.git`, submodules, sparse checkout, a path with
   `[`) is tested only on the happy layout.
6. **`run-role.sh` and `axes.py` tests stub `claude`.** Hypothesis: the stub's stream differs from
   a real stream in a way the tests rely on (event order, a missing `result`, `num_turns` placement).
   Compare with the real streams kept in `$TMPDIR/finetooth-runs/`.

## Acceptance criterion

1. **Mutation table**, per module outside `cmd_check`: mechanism → mutation → the test that went
   red (or "survived"). Every survivor is a finding or is argued in "Coverage limits".
2. **Environment matrix:** the full suite on Python 3.12 and 3.14, with `LANG=C` and with the
   default git branch set to `main` and to `master` — results per cell.
