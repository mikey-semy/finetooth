"""Checks of the role reports: verdicts, confirmed hypotheses, named files, limits."""

from __future__ import annotations

from ..git import ROOT, git_files
from ..workspace import CLI, REVIEW
from ..model import POST_VERIFY, READ_STATUSES
from ..i18n import T
from ..text import names_file, section_body, unquoted
from ..blocks import block_findings_path, manifest_path
from ..verdicts import (
    LIMITS_HEADING, LIMITS_PLACEHOLDER, confirmed_without_finding, finding_ids_for, hypotheses,
    verdict_conflicts, verdict_reports, verdicts_for, verify_report_problem,
)
from ..coverage import ACCEPTANCE_HEADING
from ..gates import Refusals


def verifier_reports_present(defn: dict, st: dict, rows: list[dict], gates: Refusals) -> None:
    """A block past verification has a verifier report that carries verdicts."""
    # A block declared verified or closed must produce the VERIFIER's report.
    # Otherwise `set-status closed` closes a block with the hunter's report alone,
    # and unverified findings vanish from the remaining work.
    for b in defn["blocks"]:
        stt = st["blocks"].get(b["id"], {}).get("status", "todo")
        if stt in POST_VERIFY:
            rep = REVIEW / "reports" / f"{b['id']}-{b['slug']}.verify.md"
            if not rep.exists():
                gates.refuse(
                    "report/verify-missing",
                    f"{b['id']}: status {stt}, but there is no verifier report — "
                    f"the verification rests on the agent's own word"
                )
            elif why := verify_report_problem(rep, any(f.get("block") == b["id"] for f in rows)):
                gates.refuse("report/verify-weak", f"{b['id']}: {why}")


def hunter_reports_present(defn: dict, st: dict, rows: list[dict], gates: Refusals) -> None:
    """A block past the hunt has a hunter report."""
    # a block cannot be past `running` without a hunter report
    for b in defn["blocks"]:
        s = st["blocks"].get(b["id"], {})
        if s.get("status") in ("hunted", "verified", "triaged", "fixing", "closed"):
            hunter = REVIEW / "reports" / f"{b['id']}-{b['slug']}.hunter.md"
            if not hunter.exists():
                gates.refuse(
                    "report/hunter-missing",
                    f"{b['id']}: status {s['status']}, but there is no hunter report — the status is not backed by work"
                )


def hypotheses_have_verdicts(defn: dict, st: dict, rows: list[dict], gates: Refusals) -> None:
    """A manifest has hypotheses, and each gets one verdict."""
    # Hypotheses are the second denominator of coverage, next to the file map. A manifest
    # without hypotheses yields a review "by general impression", and a hypothesis without
    # a verdict gets lost in the report's prose: there will be nobody to ask "did you check this".
    for b in defn["blocks"]:
        stt = st["blocks"].get(b["id"], {}).get("status", "todo")
        if stt in ("todo", "blocked"):
            continue
        manifest = manifest_path(b)
        ids = hypotheses(b["id"], manifest)
        if not ids:
            gates.refuse(
                "manifest/no-hypotheses",
                f"{b['id']}: the manifest has no hypotheses — such a block yields a review "
                f"'by general impression'; a 'Hypotheses' section, one item per hypothesis"
            )
            continue
        if stt not in POST_VERIFY:
            continue
        for rp in verdict_reports(b):
            for h, vs in verdict_conflicts(rp.read_text(encoding="utf-8"), b["id"]).items():
                gates.refuse(
                    "report/verdicts-conflict",
                    f"{b['id']}: {rp.name} gives hypothesis {h} different verdicts "
                    f"({' / '.join(vs)}) — the outcome would depend on line order; leave one"
                )
        seen = verdicts_for(b)
        missing = [h for h in ids if h not in seen]
        if missing:
            gates.refuse(
                "report/hypothesis-without-verdict",
                f"{b['id']}: {len(missing)} of {len(ids)} hypotheses without a verdict "
                f"({', '.join(missing[:5])}{'…' if len(missing) > 5 else ''}) — "
                f"each is closed with the word 'checked', 'not checked' or 'not applicable'"
            )


def confirmed_are_findings(defn: dict, st: dict, rows: list[dict], gates: Refusals) -> None:
    """A hypothesis a report confirms is carried by a finding."""
    # A confirmed hypothesis that no finding carries is a defect the review saw and lost (see
    # CONFIRM_WORDS). From the hunt on: the hunter's draft is there, and the ids it will get
    # on import are known, so the refusal comes while the hunter's work is still fresh. Every
    # block, the closed ones of a review begun on an older kit included: on the kit's own
    # review (T1–T4, twelve hunter, fix and verifier reports) the rule refuses nothing, and a closed
    # block elsewhere that it does refuse holds exactly the defect the rule exists to recover.
    block_ids = [b["id"] for b in defn["blocks"]]
    for b in defn["blocks"]:
        if st["blocks"].get(b["id"], {}).get("status") not in READ_STATUSES:
            continue
        known = finding_ids_for(b, rows)
        draft = block_findings_path(b).relative_to(ROOT).as_posix()
        for rp in verdict_reports(b):
            for h, unknown in confirmed_without_finding(
                    rp.read_text(encoding="utf-8"), b["id"], known, block_ids):
                gates.refuse(
                    "report/confirmed-without-finding",
                    T("confirmed_unknown_finding" if unknown else "confirmed_no_finding",
                      block=b["id"], report=rp.name, h=h, ids=", ".join(unknown),
                      draft=draft))


def files_named_in_reports(defn: dict, st: dict, rows: list[dict], gates: Refusals) -> None:
    """Every file of a read block is named by path in one of its reports."""
    # "Read 25 of 25" is the agent's own word about its own work. The hunter of the first
    # block at the kit author's claimed all 25 files and named five; the top-up found 11
    # more defects. Therefore every file of a readable block must be named by FULL path in
    # at least one of the block's reports: the base name is not enough — 45 blocks out of
    # 59 had files with the same names, and "all page.tsx" would close six blocks at once.
    # The excluded is subtracted: it was not read on purpose, and demanding it in the
    # report would mean demanding imitation.
    if defn.get("named_files", True):
        excluded_all = git_files([e["pattern"] for e in defn.get("exclusions", [])])
        for b in defn["blocks"]:
            stt = st["blocks"].get(b["id"], {}).get("status", "todo")
            if stt not in ("hunted", *POST_VERIFY) or b.get("proof", "read") != "read":
                continue
            owned = sorted(git_files(b.get("paths", [])) - excluded_all)
            if not owned:
                continue
            text = "\n".join(
                rp.read_text(encoding="utf-8", errors="ignore")
                for rp in (REVIEW / "reports").glob(f"{b['id']}-*.md")
            )
            missing = [f for f in owned if not names_file(text, f)]
            if missing:
                gates.refuse(
                    "report/files-not-named",
                    f"{b['id']}: {len(missing)} of {len(owned)} block files are not named by full "
                    f"path in any report ({', '.join(missing[:4])}{'…' if len(missing) > 4 else ''}) "
                    f"— what was not read is named by path in 'Coverage limits', what was read — "
                    f"in the list of files read; or `named_files: false` in blocks.json, if the project "
                    f"deliberately opted out of this check"
                )


def closed_has_fix_review(defn: dict, st: dict, rows: list[dict], gates: Refusals) -> None:
    """A closed block with fixes has a fix reviewer report."""
    # Fixes are the only code the review produces, and it is written by the same AI that
    # hunted the defects. Closing a block with fixes without a review of the fixes by those
    # who did not write them is closing on the fixer's own word.
    for b in defn["blocks"]:
        if st["blocks"].get(b["id"], {}).get("status") != "closed":
            continue
        if any(f.get("block") == b["id"] and f.get("status") == "fixed" for f in rows):
            if not list((REVIEW / "reports").glob(f"{b['id']}-{b['slug']}.fixreview-*.md")):
                gates.refuse(
                    "state/closed-without-fix-review",
                    f"{b['id']}: closed with fixed findings, but there is no fix reviewer report — "
                    f"`{CLI} prompt {b['id']} --role fixreview --diff <range>`"
                )


def acceptance_artifacts(defn: dict, st: dict, rows: list[dict], gates: Refusals) -> None:
    """What the acceptance criterion asks for is in the hunter report."""
    # The manifest's acceptance criterion asks for artifacts — tables built by reading, a
    # mutation list — and the hunter delivers them under a heading of its own. In a field run
    # the hunter skipped them and nothing said so until the verifier did (#46). A warning,
    # not a refusal: the words of a criterion do not say which role must build its table,
    # and a review already past its hunts is not stopped retroactively. A closed block's
    # reports are history — asked of the blocks still in work.
    for b in defn["blocks"]:
        if st["blocks"].get(b["id"], {}).get("status", "todo") not in ("hunted", "verified",
                                                                       "triaged", "fixing"):
            continue
        manifest, hunter = manifest_path(b), REVIEW / "reports" / f"{b['id']}-{b['slug']}.hunter.md"
        if not (manifest.exists() and hunter.exists()):
            continue
        asked = section_body(manifest.read_text(encoding="utf-8"), ACCEPTANCE_HEADING)
        if not [ln for ln in unquoted(asked or [], "text") if ln.strip()]:
            continue
        given = section_body(hunter.read_text(encoding="utf-8"), ACCEPTANCE_HEADING, "quoted")
        if given is None or not [ln for ln in unquoted(given) if ln.strip()]:
            gates.warn(
                "report/no-acceptance-artifacts",
                f"{b['id']}: the manifest has an acceptance criterion, and the hunter report has "
                f"{'no' if given is None else 'an empty'} 'Acceptance criterion' section outside "
                f"a fence or a quotation — the tables or lists the criterion asks for go there; "
                f"what the hunter could not build is named there with the reason"
            )


def coverage_limits_written(defn: dict, st: dict, rows: list[dict], gates: Refusals) -> None:
    """The hunter report says what it did not read."""
    # The coverage-limits section is mandatory: completeness is proven by listing what was
    # NOT reviewed, and in audit reports that is a separate chapter. "No findings" without
    # it is indistinguishable from "skimmed".
    for b in defn["blocks"]:
        if st["blocks"].get(b["id"], {}).get("status", "todo") not in POST_VERIFY:
            continue
        hunter = REVIEW / "reports" / f"{b['id']}-{b['slug']}.hunter.md"
        if hunter.exists():
            body = section_body(hunter.read_text(encoding="utf-8"), LIMITS_HEADING, "quoted")
            if body is None:
                gates.refuse(
                    "report/no-coverage-limits",
                    f"{b['id']}: the hunter report has no 'Coverage limits' section outside a "
                    f"fence or a quotation — what was deliberately not read and why, as the "
                    f"report's own heading (a heading inside an example, or after a fence that "
                    f"never closes, is part of the example)"
                )
            elif not [ln for ln in unquoted(body)
                      if ln.strip() and not LIMITS_PLACEHOLDER.search(ln)]:
                # A heading without text is the same silence as no heading: neither what
                # was not reviewed is named, nor that there is nothing of the kind. A
                # section holding only the template's fenced example is that same silence.
                gates.refuse(
                    "report/empty-coverage-limits",
                    f"{b['id']}: the 'Coverage limits' section of the hunter report is empty — "
                    f"name what was not read or say outright that there is nothing, as an "
                    f"ordinary line and not inside a fence or a quotation"
                )
