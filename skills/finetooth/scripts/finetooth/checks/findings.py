"""Checks of the findings register: rows, findings.md, drafts, roots, the loop signal, debt."""

from __future__ import annotations

from ..git import all_files
from ..workspace import CLI, FINDINGS_MD
from ..model import FIX_AGE_DAYS, FIX_PHASE, POST_VERIFY
from ..blocks import block_index
from ..register import (
    ROOT_RULE_AT, draft_not_imported, findings, findings_md_matches, open_findings_age,
    root_guards, roots_of, rule_problem,
)
from ..journal import last_review_round, loop_stop
from ..gates import Refusals, finding_gates
from ..refs import review_refs


def drafts_imported(defn: dict, st: dict, rows: list[dict], gates: Refusals) -> None:
    """A block past verification has no draft rows the register lacks."""
    # A block past verification whose draft holds rows the register does not: its findings
    # are missing from the summary, findings.md, SARIF and the fix gate, and nothing else here
    # would say so (#42). `set-status` refuses the same on the way in; this catches a block
    # that got there before the rule, or a draft written after it. Every status past
    # verification, not only verified/closed, for the reason POST_VERIFY gives.
    for b in defn["blocks"]:
        if st["blocks"].get(b["id"], {}).get("status", "todo") in POST_VERIFY:
            if why := draft_not_imported(b, rows):
                gates.refuse("findings/draft-not-imported", why)


def findings_well_formed(defn: dict, st: dict, rows: list[dict], gates: Refusals) -> None:
    """Every row of the register passes the finding gates."""
    idx = block_index(defn)
    # findings are well-formed and point at real code
    tracked = all_files()
    seen_ids: set[str] = set()
    for f in rows:
        finding_gates(gates, f, rows, idx, tracked, seen_ids)


def findings_md_fresh(defn: dict, st: dict, rows: list[dict], gates: Refusals) -> None:
    """findings.md says what findings.jsonl says."""
    # findings.md agrees with findings.jsonl. Compared by CONTENT, not by
    # mtime: a clone or a `git checkout` stamps every file with the moment it
    # was written, in whatever order, so mtimes say nothing about which of the
    # two is the newer truth.
    if FINDINGS_MD.exists():
        if not findings_md_matches(FINDINGS_MD.read_text(encoding="utf-8"), rows):
            gates.refuse("findings-md/stale",
                         f"findings.md diverged from findings.jsonl — run `{CLI} findings`")


def roots_have_guards(defn: dict, st: dict, rows: list[dict], gates: Refusals) -> None:
    """A class that repeated is closed by a guard."""
    # A defect class that repeated three times is closed by a guard, not by three fixes:
    # otherwise the next pass finds a fourth instance. A rule survives a refactoring, a
    # list of fixed places does not.
    for root, items in roots_of(rows).items():
        if len(items) < ROOT_RULE_AT:
            continue
        guards = root_guards(items)
        rules = set(guards) - {""}
        if rules:
            for r in sorted(rules):
                if why := rule_problem(r):
                    gates.refuse("root/guard-unusable", f"root '{root}': {why}")
            # A guard is recorded per finding (issue #28): one guarded instance no longer
            # stands for the rest. Instances without a guard are named, but not refused —
            # whether the recorded guard reaches them is a claim only a run on their own
            # defect can make, and the tool cannot make it for the fixer.
            if bare := guards.get(""):
                gates.warn(
                    "root/guard-partial",
                    f"root '{root}': {len(bare)} of {len(items)} instances carry no guard "
                    f"({', '.join(bare[:4])}) while others do — a guard holds only the findings "
                    f"it is recorded on; if it goes red on their defect too, record it on them "
                    f"(`{CLI} set-finding <ID>... <status> --rule <path>`), otherwise close "
                    f"them with a guard of their own; `{CLI} roots` shows who carries what")
            continue
        ids = ", ".join(f.get("id", "?") for f in items[:4])
        # The guard is recorded with `set-finding --rule` on a file that exists, i.e. by the
        # fixer; demanded before that, it made a block red for having been hunted and verified
        # well, and gate 3 of RELEASING.md ("hunter and verifier, and `check` green") could not
        # be passed on a block whose hunter found one class three times (the gate-3 run of
        # 0.8.0 on a live project). So the refusal waits for the fix phase: an instance
        # already fixed, or the block of one in `fixing`/`closed`. Before it the class is
        # named, so that whoever cuts the fix assignments plans a guard, not three edits.
        if not any(f.get("status") == "fixed"
                   or st["blocks"].get(f.get("block"), {}).get("status") in FIX_PHASE
                   for f in items):
            gates.warn(
                "root/guard-due",
                f"root '{root}': {len(items)} instances ({ids}) — a class that repeated "
                f"{ROOT_RULE_AT} times will be closed by a rule, not by a list of fixes; the "
                f"fix phase must record one: `{CLI} set-finding <ID>... <status> --rule "
                f"<path-to-guard>` (until an instance is fixed or its block reaches `fixing`, "
                f"this is a warning)")
            continue
        gates.refuse(
            "root/no-guard",
            f"root '{root}': {len(items)} instances ({ids}) and no guard — "
            f"a class that repeated {ROOT_RULE_AT} times is closed by a rule, not by a list of "
            f"fixes; record which: `{CLI} set-finding <ID> <status> --rule <path-to-guard>`"
        )


def loop_signal(defn: dict, st: dict, rows: list[dict], gates: Refusals) -> None:
    """The loop signal, as `prompt --role fix` would refuse it."""
    idx = block_index(defn)
    # The loop signal, as `prompt --role fix` will refuse it: said here too, because the lead
    # reads `check` after every import, and the stop belongs before the next round is cut, not
    # at the moment its prompt is asked for. A warning: the state is not wrong, the next
    # move is a human's. A closed block has no next round.
    for bid in idx:
        if st["blocks"].get(bid, {}).get("status") == "closed":
            continue
        if why := loop_stop(bid, last_review_round(bid, rows) + 1, rows):
            gates.warn("loop/top-finding-in-own-diff", f"{bid}: {why}")


def refs_in_code(defn: dict, st: dict, rows: list[dict], gates: Refusals) -> None:
    """Finding ids left in the code are named."""
    refs = review_refs()
    if refs:
        sample = ", ".join(f"{p}:{n} ({fid})" for p, n, fid, _ in refs[:4])
        gates.warn("refs/findings-named-in-code",
                   f"{len(refs)} reference(s) to findings in the code: {sample} — the ids die "
                   f"with docs/review/; `{CLI} refs` lists them")


def fix_debt_age(defn: dict, st: dict, rows: list[dict], gates: Refusals) -> None:
    """Open findings older than the fix-debt age are named."""
    old = open_findings_age(findings())
    if old:
        oldest = max(age for _, age in old)
        sample = ", ".join(f"{f.get('id')} ({age}d)" for f, age in sorted(old, key=lambda x: -x[1])[:5])
        gates.warn("findings/fix-debt-age",
                   f"{len(old)} open finding(s) older than {FIX_AGE_DAYS} days (oldest {oldest}d): "
                   f"{sample} — fix debt: fix, defer with a reason or reject; a register that "
                   f"outlives the code it describes stops being true")
