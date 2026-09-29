"""SARIF 2.1.0 export of open findings, for code scanning."""

from __future__ import annotations

from urllib.parse import quote

from ..base import VERSION
from ..git import ROOT
from ..model import SEVERITIES
from ..i18n import T
from ..blocks import block_index, report_path
from ..register import finding_file, shown_lines
from ..coverage import review_scope


#
# The findings of the register as SARIF 2.1.0, for GitHub code scanning (the Security tab and
# the lines of a pull request). Every decision below is taken from one of two sources, and
# each names which:
#   OASIS SARIF 2.1.0 (errata 01) —
#     https://docs.oasis-open.org/sarif/sarif/v2.1.0/errata01/os/sarif-v2.1.0-errata01-os-complete.html
#   GitHub, "SARIF support for code scanning" —
#     https://docs.github.com/en/code-security/code-scanning/integrating-with-code-scanning/sarif-support-for-code-scanning
#
# What is exported: `open` and `deferred`. `fixed`, `rejected` and `duplicate` are closed —
# an alert for them would be a defect GitHub shows as present when the register says it is
# not. A deferred finding is still in the code: the kit calls it an accepted risk (it is
# published in the summary with its reason), and SARIF has the exact word for that — a
# `suppression` with `status: "accepted"` and a `justification` (§3.27.23, §3.35). `kind`
# is `external` because the decision lives in the register, not in a comment in the source
# (§3.35.2). GitHub does not read `suppressions` (they are not in its list of supported
# properties, and suppressed results are still shown as open alerts — acknowledged by GitHub
# in community discussion #156737), so the message also SAYS "accepted risk" in its first
# sentence, the one GitHub displays when space is short.
#
# `security-severity` is NOT written. GitHub reads it on the RULE ("if you include a value for
# this field, results for the rule are treated as security results"), a rule here is a defect
# class holding findings of different severities, and the register has no field that says a
# finding is a vulnerability — deciding it from the wording of the claim is guessing, and a
# guess would move code-quality findings into the security severity scale. Without it the
# alerts are shown with their `level` (error / warning / note), which the register does know.

# Severity → SARIF `level` (§3.27.10: none | note | warning | error). The fix gate treats
# high and above as what blocks the next block (FIX_GATE_DEFAULT), so both are `error`;
# `note` is the level for a finding that is worth knowing and not worth failing a build.
SARIF_LEVEL = {"critical": "error", "high": "error", "medium": "warning", "low": "note"}
# Statuses that leave the review with the defect still in the code. The others are closed.
SARIF_STATUSES = ("open", "deferred")
# GitHub: `shortDescription.text` and `fullDescription.text` are "limited to 1024 characters".
SARIF_TEXT_MAX = 1024
SARIF_SCHEMA = "https://json.schemastore.org/sarif-2.1.0.json"
KIT_URI = "https://github.com/mikey-semy/finetooth"


def sarif_text(text: str) -> str:
    return text if len(text) <= SARIF_TEXT_MAX else text[:SARIF_TEXT_MAX - 1] + "…"


def sarif_rule_id(f: dict) -> str:
    """The rule is the finding's defect class: the `root`, written the same way in every
    instance of the class, is exactly what a rule is — one id many results point at. A finding
    with no class gets its block's id: the finding still has to be filterable by something."""
    return (f.get("root") or "").strip() or f.get("block", "?")


def sarif_report(b: dict | None) -> str | None:
    """The block report the finding is argued in: the verifier's, whose verdict put it into
    the register, or the hunter's when there is no verifier's yet. A path from the root, like
    every path in the register; no link is built from a remote — the kit does not know the
    platform, and a relative `helpUri` would resolve against GitHub, not the repository."""
    if not b:
        return None
    for role in ("verify", "hunter"):
        rel = report_path(b, role)
        if (ROOT / rel).is_file():
            return rel
    return None


def render_sarif(defn: dict, rows: list[dict]) -> dict:
    idx = block_index(defn)
    live = [f for f in rows if f.get("status", "open") in SARIF_STATUSES]
    classes: dict[str, list[dict]] = {}
    for f in live:
        classes.setdefault(sarif_rule_id(f), []).append(f)
    rule_ids = sorted(classes)
    rules = []
    scope = review_scope(defn)

    def help_text(ids: str) -> str:
        # "Found by a whole-repository review" on a partial one is the one sentence of the
        # alert that would be false; the scope and its reason replace it.
        if not scope:
            return T("sarif_rule_help", ids=ids)
        return T("sarif_rule_help_partial", ids=ids, reason=str(scope.get("reason") or "").strip() or "—",
                 paths=", ".join(f"`{p}`" for p in scope["paths"]))
    for rid in rule_ids:
        items = classes[rid]
        first = items[0]
        if (first.get("root") or "").strip():
            short = T("sarif_rule_root", root=rid)
        else:
            b = idx.get(first.get("block", ""), {})
            short = T("sarif_rule_block", block=rid, title=b.get("title", "?"))
        guards = sorted({f["rule"] for f in items if f.get("rule")})
        full = short + (". " + T("sarif_rule_guard", rules=", ".join(guards)) if guards else "")
        # The rule's default is its most severe instance: a result overrides it anyway
        # ("this level overrides the default severity defined by the rule" — GitHub).
        worst = min((SEVERITIES.index(f["severity"]) for f in items
                     if f.get("severity") in SEVERITIES), default=SEVERITIES.index("medium"))
        rules.append({
            "id": rid,
            "shortDescription": {"text": sarif_text(short)},
            "fullDescription": {"text": sarif_text(full)},
            "help": {"text": help_text(", ".join(f.get("id", "?") for f in items))},
            "helpUri": KIT_URI,
            "defaultConfiguration": {"level": SARIF_LEVEL[SEVERITIES[worst]]},
            "properties": {"tags": ["finetooth", "review"]},
        })
    results = []
    review_id = defn.get("review_id", "")
    line_of = shown_lines()
    for f in live:
        fid = f.get("id", "?")
        report = sarif_report(idx.get(f.get("block", "")))
        deferred = f.get("status") == "deferred"
        parts = [(T("sarif_deferred") if deferred else "") + (f.get("claim") or "").strip()]
        if (f.get("scenario") or "").strip():
            parts.append(f["scenario"].strip())
        if deferred and (f.get("defer_reason") or "").strip():
            parts.append(T("sarif_deferred_why", reason=f["defer_reason"].strip()))
        if report:
            parts.append(T("sarif_report", path=report))
        rid = sarif_rule_id(f)
        result = {
            "ruleId": rid,
            "ruleIndex": rule_ids.index(rid),
            "level": SARIF_LEVEL.get(f.get("severity"), "warning"),
            "message": {"text": "\n\n".join(parts)},
            # GitHub: "code scanning only uses the `primaryLocationLineHash`" to match a
            # result across runs. Left out, `upload-sarif` fills it with a hash of the line's
            # text, and every edit of that line opens a new alert beside the old one. The
            # finding's identity is its id — prefixed with the review, because the next
            # review numbers from H1-001 again. The action logs a warning that the value is
            # not the hash it computed, and keeps ours (codeql-action src/fingerprints.ts).
            "partialFingerprints": {"primaryLocationLineHash": f"{review_id}/{fid}",
                                    "finetoothFinding/v1": f"{review_id}/{fid}"},
            "properties": {"finding": fid, "block": f.get("block"),
                           "severity": f.get("severity"), "confidence": f.get("confidence"),
                           "status": f.get("status", "open"),
                           **({"report": report} if report else {})},
        }
        if finding_file(f):
            # A relative reference from the repository root (GitHub: "interprets results
            # that are reported with relative paths as relative to the root of the GitHub
            # repository analyzed"), percent-encoded because `uri` is an RFC 3986 string
            # (§3.10.1): a space or a Cyrillic letter is not allowed in one raw, and
            # `upload-sarif` decodes it back with decodeURIComponent.
            uri = quote(finding_file(f).removeprefix("./"), safe="/")
            # GitHub lists `region.startLine` as required. A finding without a line is about
            # the whole file, and line 1 is what the action itself hashes for such a result.
            # The line is where the finding's code sits NOW (`shown_lines`): an alert
            # pointing at a line the code has left annotates the wrong line of the PR. The
            # alert keeps its identity across the move — that is `partialFingerprints`.
            at = line_of(f)
            line = at if isinstance(at, int) and not isinstance(at, bool) and at >= 1 else 1
            result["locations"] = [{"physicalLocation": {
                "artifactLocation": {"uri": uri},
                "region": {"startLine": line}}}]
        if deferred:
            why = (f.get("defer_reason") or "").strip()
            result["suppressions"] = [{"kind": "external", "status": "accepted",
                                       **({"justification": why} if why else {})}]
        results.append(result)
    return {
        "$schema": SARIF_SCHEMA,
        "version": "2.1.0",
        "runs": [{
            "tool": {"driver": {"name": "finetooth", "version": VERSION,
                                "semanticVersion": VERSION, "informationUri": KIT_URI,
                                "rules": rules}},
            "results": results,
            # The run's property bag (SARIF §3.8, "property bags"): a consumer reading the file
            # without the rules' help still sees that the review was partial, and of what.
            **({"properties": {"coverage": "partial", "scope": {
                "paths": list(scope["paths"]),
                "reason": str(scope.get("reason") or "").strip()}}} if scope else {}),
        }],
    }
