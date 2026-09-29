"""Command: check — every gate of the review in one pass."""

from __future__ import annotations

from ..blocks import blocks, state
from ..register import findings
from ..gates import Refusals
from ..checks.state import (
    blocked_has_note, declared_reports_exist, manifests_present, phases_in_order,
    reviewed_code_unchanged, running_not_stale, state_matches_definition,
)
from ..checks.findings import (
    drafts_imported, findings_md_fresh, findings_well_formed, fix_debt_age, loop_signal,
    refs_in_code, roots_have_guards,
)
from ..checks.coverage import (
    blocks_readable, coverage_complete, coverage_map_fresh, paths_match_files, scope_declared,
    sweeps_scripted, tree_fresh,
)
from ..checks.reports import (
    acceptance_artifacts, closed_has_fix_review, confirmed_are_findings,
    coverage_limits_written, files_named_in_reports, hunter_reports_present,
    hypotheses_have_verdicts, verifier_reports_present,
)

# The checks in the order their messages are printed: definition and state first, then the
# register, coverage and reports, the loop signal and the debts last. Each adds refusals and
# warnings to the container and returns nothing — the verdict is the container's alone.
CHECKS = (
    state_matches_definition,
    phases_in_order,
    blocked_has_note,
    manifests_present,
    verifier_reports_present,
    drafts_imported,
    declared_reports_exist,
    hunter_reports_present,
    running_not_stale,
    findings_well_formed,
    findings_md_fresh,
    paths_match_files,
    scope_declared,
    coverage_complete,
    coverage_map_fresh,
    hypotheses_have_verdicts,
    confirmed_are_findings,
    reviewed_code_unchanged,
    files_named_in_reports,
    closed_has_fix_review,
    acceptance_artifacts,
    coverage_limits_written,
    roots_have_guards,
    tree_fresh,
    sweeps_scripted,
    blocks_readable,
    loop_signal,
    refs_in_code,
    fix_debt_age,
)


def cmd_check(args) -> int:
    defn, st, rows = blocks(), state(), findings()
    gates = Refusals()
    for check_one in CHECKS:
        check_one(defn, st, rows, gates)
    return gates.report()
