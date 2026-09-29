"""The review's vocabulary: statuses, severities, roles and the numbers of its process."""

from __future__ import annotations

import re


# A block moves forward only through these, in this order. `blocked` is the one
# side exit: a block that cannot proceed until another one lands.
STATUSES = ["todo", "running", "hunted", "verified", "triaged", "fixing", "closed", "blocked"]
SEVERITIES = ["critical", "high", "medium", "low"]
CONFIDENCE = ["confirmed", "plausible", "rejected"]
FINDING_STATUS = ["open", "fixed", "rejected", "duplicate", "deferred"]
# The fix gate: the next block does not start while findings of this severity or above
# are open in the blocks already passed. The method finds faster than a project fixes
# (first project: 77 findings on 5 blocks, 9 fixed), and a finding that never reaches a fix
# is debt — a month later the register describes code that no longer exists. "high" by
# default: at "medium" the review stalls on small things and the gate gets bypassed.
# "none" switches the gate off (a project decision, recorded in blocks.json).
FIX_GATE_DEFAULT = "high"
# An open finding older than this is a warning in `check`: the same week the stale-tree
# check uses — a review that lets findings sit longer than its own tree is allowed to lag
# is accumulating the debt the gate exists to stop.
FIX_AGE_DAYS = 7
# `claim` is the headline of a finding: it is what the summary table prints, one
# row per finding, and a row has to be readable at a glance. Evidence, line
# numbers and the reasoning that establishes the defect belong in the block
# report, which is prose and has room for them. Without a cap the field drifts
# into a paragraph — the verifier of the first block pasted its whole
# verification into it — and the table it feeds stops being a table.
#
# The two numbers are the measured ceiling of honest findings, not round figures: over the
# 24 findings of this kit's own first block the claim runs 82…202 characters (median 178,
# 90th percentile 194) and the scenario 452…690 (median 586, 90th percentile 665). Both
# caps sit just above the longest real one — they cut a field that has turned into a
# report, not a field that is thorough.
CLAIM_MAX = 220
SCENARIO_MAX = 700
ROLES = ["hunter", "verify", "fix", "fixreview"]
# The roles whose reports carry hypothesis verdicts, in the order they are overlaid: the
# verifier last, because its template tells it to override a verdict it disagrees with. One
# list for every reader of a verdict — `verdicts_for`, the conflict gate and the gate on a
# confirmation without a finding: while the last read two of the three, a hypothesis confirmed
# in the fix report answered the verdict gate and escaped the finding gate (fix review of the
# 0.8.0 candidate). The fix reviewer writes no hypothesis verdicts.
VERDICT_ROLES = ("hunter", "fix", "verify")
# The severity from which a fix-review finding earns another round — rule 11 of the fix
# reviewer's template, from the method author's own review: low ones are fixed by the lead
# without a round. The loop signal asks the same question of the previous round's top finding.
ROUND_SEVERITY = "medium"
# How many open findings one fixer run is handed as its assignment. A field run of the kit
# measured it: 16 of 46 fixer runs ended on the turn cap on batches larger than 3–4
# findings, and each left its edits uncommitted for the next run to start on. The cap is the lower edge of that range — the batch size no capped run had —
# not a round figure. A block with more open findings is closed in several runs; the prompt
# names which ones this run takes.
FIX_BATCH = 3
# The block's proof kind. `read` — every file is read in full and named in the report;
# `measured` — reading proves nothing (180 thousand lines of tests, performance,
# scanners), the proof is the artifacts from the manifest. A block without `paths` is a
# live system.
PROOFS = ("read", "measured")
# A cross-cutting block's acceptance criterion is usually an enumeration — "every place that
# changes data", "every call and its constraint" — and that is a sweep over the whole program,
# not the block's files. The readability ceiling counted only `paths`, so a block "within the
# ceiling" demanded ten times more (a live review: 5.7k lines in the block, 47k in the sweep;
# setfork H3: 8 files by the counter, 89 by the criterion). The sweep is declared, sized apart
# and done by a script, not by attention.
SWEEP_DIR_NAME = "sweeps"
ENUMERATION = re.compile(
    r"\b(?:все|всех|всем|каждый|каждое|каждого|каждую)\s+(?:мест|вызов|точк|пут|маршрут|запис|обращен|использован|вхожден)"
    r"|\b(?:every|all)\s+(?:places?|calls?|sites?|routes?|writes?|paths?|quer(?:y|ies)|callers?|usages?|occurrences?)\b",
    re.IGNORECASE)
# Which role comes next given the block status — the hint in `status`.
NEXT_ROLE = {"todo": "hunter", "running": "hunter", "hunted": "verify", "verified": "fix",
             "triaged": "fix", "fixing": "fixreview"}
# A block left `running` for longer than this almost certainly means a session
# died mid-flight rather than that an agent is still reading.
STALE_RUNNING_HOURS = 24
# A block that passed verification does not stop being verified when it moves on. While
# the condition was "verified or closed", moving to triaged turned the hypotheses gate and
# the coverage-limits gate green without adding anything: the status changed, the gap stayed.
POST_VERIFY = ("verified", "triaged", "fixing", "closed")
# The statuses in which fixes are being made or have been accepted. `triaged` is not one of
# them: triage decides WHAT to fix, and a guard is recorded when the fix is made.
FIX_PHASE = ("fixing", "closed")
# The statuses in which the block has been read: a hunter report stands behind each of them
# (gate 4 of `check`). `todo`, `running` and `blocked` are not — "a blocked block is not a
# read one" (`status`). The readability ceiling is a promise about a reading still to come:
# once the reading happened, the report was written on the volume of that day, and growth
# of the code afterwards is caught by the block fingerprint, not by the ceiling.
READ_STATUSES = ("hunted", *POST_VERIFY)
# ⚠️ The status alone does not say the block was read UNDER the ceiling: `set-status hunted`
# on a block above it turned the refusal into a warning without splitting anything (Codex on
# #57). So the reading records its size — `read_lines`, counted as `sizes` counts — and only a
# block read within the ceiling earns the warning. A block without the record (a review
# started before it existed) is not presumed to have been.
READ_LINES_KEY = "read_lines"
# What a block definition must carry for the tool to be able to do anything with it. The
# file is written BY HAND — `setup` leaves `"blocks": []` for a human to fill in — and a
# missing field used to surface as `KeyError: 'phase'` with exit 1, which reads as "the
# state is red" rather than "your definition is malformed". Each field is used somewhere
# with no default: `slug` names the manifest and the reports, `phase` orders the array,
# `role` and `goal` are pasted into every prompt.
BLOCK_FIELDS = ("id", "slug", "phase", "title", "role", "goal")
# How far behind in TIME the tree must be for that to mean "it has gone stale".
#
# Time is what must be measured, not commits: in the case this check was created for, the
# copy of the neighbouring service was only TWO commits behind — and twelve days. Two
# commits would alarm nobody, while in twelve days the hole had been closed, and the
# verifier "confirmed by execution" a defect that no longer existed.
#
# The threshold is below that measurement (12 days) and above the usual life of a working
# branch: a branch lives days, a stale copy — weeks. Counting commits is deliberately not
# used: a branch cut an hour ago is a dozen commits behind master and not stale at all.
STALE_TREE_DAYS = 7
# How many lines an agent really reads in one session. The number is not invented: a
# neighbouring project went through a 1727-line block in six runs and two hours, while an
# 87-thousand-line block reported on 4 files out of 14 — that is, it lied about coverage
# without breaking a single check. The ceiling is three times what was read, with margin,
# to catch what is plainly impossible.
READABLE_LINES = 6000  # default; overridden by the `readable_lines` field in blocks.json
# Below this a manifest holds nothing but its own headings. Measured on the scaffold the
# kit itself hands out: the six headings of `assets/manifest.example.md`, with the title,
# come to 171 characters, and a manifest copied and not filled in is exactly that file with
# the text deleted. 200 is the first round number above it, so the gate catches the empty
# copy and not a terse real one — the shortest real manifest measured here is 4 743
# characters, more than twenty times the bound.
MANIFEST_MIN_CHARS = 200
# The second denominator of coverage. The file map answers "the file was opened", and
# that is not enough: a file can be opened and nothing understood. A professional audit
# counts coverage not in files but in questions to the system — in OWASP ASVS a
# requirement must be closed by a "pass or fail" decision, and an inapplicable one is
# closed by a written justification, not by silence. The manifest's hypotheses are our
# questions, and each must receive one of three verdicts.
HYPOTHESIS_HEADING = re.compile(r"^#{1,6}\s*.*(гипотез|hypothes)", re.IGNORECASE)
HYPOTHESIS_WORD = re.compile(r"гипотез|hypothes", re.I)
