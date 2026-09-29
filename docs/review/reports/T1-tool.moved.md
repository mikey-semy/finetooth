# T1 — files moved after the review (#56)

Written by the lead, not by a role. The block was reviewed when the tool was one file,
`skills/finetooth/scripts/review.py`; every report of this block read that file. On 2026-09-29
it was split into the `finetooth` package next to it, mechanically: a generator copied every
top-level statement verbatim with the comments above it and derived the imports from the
symbol table. The output of 24 commands on this register was compared before and after — identical except
where it names the tool's own files — and
the three deferred findings of this block moved with `restamp --file` onto windows identical
to the ones they had in `review.py`.

So the code of the files below was read — as `review.py`. What was NOT reviewed is the new
code the split added: the imports of each module, `finetooth/__init__.py` (`LAYERS`), the new
`review.py` (a four-line command), and `SKILL_DIR`/`default_cli`, which now compute the paths
from the module's location. The next review of this code splits T1 into blocks along
`LAYERS` first — the block is past the readability ceiling.

## Files read as scripts/review.py

- skills/finetooth/scripts/finetooth/__init__.py
- skills/finetooth/scripts/finetooth/base.py
- skills/finetooth/scripts/finetooth/blocks.py
- skills/finetooth/scripts/finetooth/cli.py
- skills/finetooth/scripts/finetooth/commands/__init__.py
- skills/finetooth/scripts/finetooth/commands/check.py
- skills/finetooth/scripts/finetooth/commands/coverage.py
- skills/finetooth/scripts/finetooth/commands/findings.py
- skills/finetooth/scripts/finetooth/commands/history.py
- skills/finetooth/scripts/finetooth/commands/prompt.py
- skills/finetooth/scripts/finetooth/commands/report.py
- skills/finetooth/scripts/finetooth/commands/setup.py
- skills/finetooth/scripts/finetooth/commands/status.py
- skills/finetooth/scripts/finetooth/coverage.py
- skills/finetooth/scripts/finetooth/fingerprint.py
- skills/finetooth/scripts/finetooth/gates.py
- skills/finetooth/scripts/finetooth/git.py
- skills/finetooth/scripts/finetooth/history.py
- skills/finetooth/scripts/finetooth/i18n.py
- skills/finetooth/scripts/finetooth/importing.py
- skills/finetooth/scripts/finetooth/journal.py
- skills/finetooth/scripts/finetooth/model.py
- skills/finetooth/scripts/finetooth/refs.py
- skills/finetooth/scripts/finetooth/register.py
- skills/finetooth/scripts/finetooth/report/__init__.py
- skills/finetooth/scripts/finetooth/report/html.py
- skills/finetooth/scripts/finetooth/report/sarif.py
- skills/finetooth/scripts/finetooth/report/summary.py
- skills/finetooth/scripts/finetooth/roles.py
- skills/finetooth/scripts/finetooth/seams.py
- skills/finetooth/scripts/finetooth/settings.py
- skills/finetooth/scripts/finetooth/text.py
- skills/finetooth/scripts/finetooth/verdicts.py
- skills/finetooth/scripts/finetooth/workspace.py
