"""The markdown summary: facts from the register and the journal."""

from __future__ import annotations

import json

from ..base import now
from ..git import all_files, git_files, git_head
from ..workspace import CLI, COUPLING_FILE
from ..model import FINDING_STATUS, ROLES, SEVERITIES
from ..i18n import T, review_lang
from ..blocks import block_index
from ..register import finding_file, root_guards, roots_of, shown_lines
from ..coverage import acceptance_of, coverage_map, review_scope, scope_files, scope_line
from ..journal import journal_spend, spend_sum
from ..report.sarif import sarif_report


SUMMARY_MARK = "<!-- finetooth-summary "


def summary_facts(defn: dict, st: dict, rows: list[dict]) -> dict:
    """Every number and list the summary shows — counted ONCE, here. The Markdown and the HTML
    renderings take their numbers from this and from nowhere else, so the two cannot disagree
    about what the review found or what it cost."""
    sha, branch = git_head()
    by_status = {k: 0 for k in FINDING_STATUS}
    for f in rows:
        by_status[f.get("status", "open")] = by_status.get(f.get("status", "open"), 0) + 1
    closed = sum(1 for b in defn["blocks"] if st["blocks"].get(b["id"], {}).get("status") == "closed")
    owned, excluded, unassigned = coverage_map()
    inside = scope_files(defn)
    universe = (all_files() if inside is None else inside) - excluded
    spend = journal_spend()
    idx = block_index(defn)
    blocks_out = []
    for b in defn["blocks"]:
        s = st["blocks"].get(b["id"], {})
        mine = [f for f in rows if f.get("block") == b["id"]]
        defects = [f for f in mine if f.get("status", "open") not in ("rejected", "duplicate")]
        blocks_out.append({
            "id": b["id"], "title": b["title"], "goal": b.get("goal", ""),
            "status": s.get("status", "todo"), "finished": (s.get("finished") or "")[:10],
            "files": len(git_files(b.get("paths", []))) if b.get("paths") else 0,
            "reviewed_sha": s.get("reviewed_sha") or "—", "acceptance": acceptance_of(b),
            "by_severity": {k: sum(1 for f in defects if f.get("severity") == k) for k in SEVERITIES},
            "statuses": {k: sum(1 for f in mine if f.get("status", "open") == k) for k in FINDING_STATUS},
            "spend": spend_sum([r for r in spend if r["block"] == b["id"]]),
        })
    rules: dict[str, list[str]] = {}
    for f in rows:
        if f.get("rule"):
            rules.setdefault(f["rule"], []).append(f.get("id", "?"))
    line_of = shown_lines()

    shown = [f for f in rows if f.get("status", "open") in ("open", "deferred", "rejected")]
    return {
        "project": defn.get("project", "?"), "date": now()[:10], "sha": sha, "branch": branch,
        "closed": closed, "total_blocks": len(defn["blocks"]), "total_findings": len(rows),
        "by_status": by_status, "scope_line": scope_line(defn, review_lang()),
        "coverage": {"total": len(universe), "covered": len(universe & set(owned)),
                     "unowned": len(unassigned), "excluded": len(excluded),
                     "outside": len(all_files() - excluded - universe) if inside is not None else 0},
        "blocks": blocks_out,
        "rejected": [f for f in rows if f.get("status") == "rejected"],
        "deferred": [f for f in rows if f.get("status") == "deferred"],
        "open": [f for f in rows if f.get("status", "open") == "open"],
        # Where each shown finding is: the line its code sits on now, and its block report.
        # Kept beside the records, not written into them: they are displays, not fields.
        "at": {f.get("id"): line_of(f) for f in shown},
        "report": {f.get("id"): sarif_report(idx.get(f.get("block", ""))) for f in shown},
        "fixed": [f for f in rows if f.get("status") == "fixed"],
        "rules": rules, "roots": roots_of(rows),
        "unrooted_rules": root_guards([f for f in rows if f.get("rule") and not (f.get("root") or "").strip()
                                       and f.get("status") not in ("rejected", "duplicate")]),
        "spend_roles": {role: spend_sum([r for r in spend if r["role"] == role]) for role in ROLES},
        "spend_total": spend_sum(spend),
    }


def render_summary(defn: dict, st: dict, rows: list[dict], facts: dict | None = None) -> str:
    fx = facts or summary_facts(defn, st, rows)
    sha, by_status = fx["sha"], fx["by_status"]
    cov = fx["coverage"]
    out = [T("sum_title", project=fx["project"]), "",
           T("sum_intro", cli=CLI), "",
           T("sum_base", date=fx["date"], sha=sha[:12], branch=fx["branch"], closed=fx["closed"],
             total=fx["total_blocks"], total_f=fx["total_findings"], fixed=by_status["fixed"],
             rejected=by_status["rejected"], deferred=by_status["deferred"],
             dups=by_status["duplicate"], open=by_status["open"]) + "  ",
           T("sum_coverage", covered=cov["covered"], total=cov["total"], unowned=cov["unowned"],
             excluded=cov["excluded"]), ""]
    # A partial review says so before anything else: the file outlives docs/review/, and a
    # reader who meets it a year later must not take one area's review for the whole.
    if fx["scope_line"]:
        out[1:1] = [f"> **{fx['scope_line']}**", ""]
    out += [T("sum_blocks"), "", T("sum_blocks_head"), "|---|---|---|---|---|---|---|"]
    for b in fx["blocks"]:
        out.append(f"| {b['id']} | {b['title']} | {b['status']} | "
                   f"{b['finished']} | {b['files']} | `{b['reviewed_sha']}` | "
                   f"{b['acceptance']} |")
    out.append("")

    def finding_line(f: dict, reason_key: str | None) -> str:
        at = fx["at"].get(f.get("id"))
        where = f"`{finding_file(f)}:{at}`" if at else f"`{finding_file(f)}`"
        line = f"- **{f.get('id')}** ({f.get('severity')}) {where} — {f.get('claim', '').strip()}"
        if reason_key and f.get(reason_key):
            line += f"  \n  *{f[reason_key].strip()}*"
        return line
    out += [T("sum_rejected"), ""]
    out += [finding_line(f, "reject_reason") for f in fx["rejected"]] or [T("sum_rejected_none")]
    out.append("")
    out += [T("sum_deferred"), ""]
    out += [finding_line(f, "defer_reason") for f in fx["deferred"]] or [T("sum_deferred_none")]
    out.append("")
    out += [T("sum_classes"), ""]
    rules, fixed = fx["rules"], fx["fixed"]
    if rules:
        out.append(T("sum_classes_rules"))
        out += [f"- `{rule}` — {', '.join(ids)}" for rule, ids in sorted(rules.items())]
        out.append("")
    if fixed:
        out.append(T("sum_classes_fixes"))
        out += [f"- {f.get('id')} → `{f.get('fix_commit') or ', '.join(f.get('fixed_in', []))}`"
                for f in fixed]
        out.append("")
    if not rules and not fixed:
        out += [T("sum_classes_none"), ""]
    out += [T("sum_open"), ""]
    out += [finding_line(f, None) for f in fx["open"]] or [T("sum_open_none")]
    out.append("")
    if COUPLING_FILE.exists():
        lines = COUPLING_FILE.read_text(encoding="utf-8").splitlines()[1:]
        if lines:
            out += [T("sum_seams"), ""]
            out += ["- " + " ↔ ".join(f"{c[1]} `{c[0]}`" for c in
                    [(x.split("\t")[0], x.split("\t")[1]), (x.split("\t")[2], x.split("\t")[3])])
                    + f" ({x.split(chr(9))[4]}×)" for x in lines[:50]]
            out.append("")
    # The journal dies with docs/review/; what the review cost is part of what it was.
    out += [T("sum_economy"), ""]
    total = fx["spend_total"]
    if total["runs"]:
        out += [T("sum_economy_head"), "|---|---|---|---|---|"]
        out += [f"| {role} | {s['runs']} | {s['unknown']} | {s['turns_text']} | {s['cost_text']} |"
                for role, s in fx["spend_roles"].items() if s["runs"]]
        out.append(f"| **{T('sum_economy_total')}** | {total['runs']} | {total['unknown']} | "
                   f"{total['turns_text']} | {total['cost_text']} |")
        if total["unknown"]:
            out += ["", T("sum_economy_unknown", n=total["unknown"])]
    else:
        out.append(T("sum_economy_none"))
    out.append("")
    machine = {"base": sha, **({"scope": review_scope(defn)} if review_scope(defn) else {}),
               "blocks": {b["id"]: {"title": b["title"], "paths": b.get("paths", [])}
                                        for b in defn["blocks"]}}
    out += [T("sum_machine"), "", SUMMARY_MARK + json.dumps(machine, ensure_ascii=False) + " -->", ""]
    return "\n".join(out)
