"""Commands: summary (markdown and --html), sarif."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from ..base import die
from ..git import ROOT, git, log_records
from ..workspace import CLI, SUMMARY_DEFAULT, SUMMARY_HTML_DEFAULT
from ..i18n import T
from ..blocks import blocks, state
from ..register import findings
from ..report.sarif import render_sarif
from ..report.summary import SUMMARY_MARK, render_summary, summary_facts
from ..report.html import render_summary_html


def cmd_summary(args) -> int:
    """The one file that outlives docs/review/: what was checked, against which revision,
    what was rejected and why, what closes each class. With --aged: how far each block has
    drifted from the summary's base commit — the only thing a re-run needs to start from."""
    if args.aged and args.html:
        die("--aged reads a Markdown summary and --html writes one as HTML — give one of them: "
            f"`{CLI} summary --aged <file>` or `{CLI} summary --html`")
    if args.aged:
        path = Path(args.aged)
        if not path.is_absolute():
            path = ROOT / path
        if not path.exists():
            die(f"no such summary: {path}")
        text = path.read_text(encoding="utf-8")
        i = text.find(SUMMARY_MARK)
        if i < 0:
            die(f"{path.name} carries no machine block — was it written by `summary`?")
        # The machine block is one line: `<!-- finetooth-summary {…} -->`. Cut at the LAST
        # `-->` of that line, not at the first ` -->` in the file: a block whose title holds
        # the marker (`Import --> export pipeline`) is written into the block verbatim, and
        # cutting at the first one left half a JSON object and a traceback in the user's
        # face — on the one file that is meant to outlive docs/review/.
        raw = text[i + len(SUMMARY_MARK):].split("\n", 1)[0].rstrip()
        if not raw.endswith("-->"):
            die(f"{path.name}: the machine block is not closed with `-->` — "
                f"it is generated, not written by hand; regenerate it with `{CLI} summary`")
        try:
            machine = json.loads(raw[:-3].strip())
        except json.JSONDecodeError as exc:
            die(f"{path.name}: the machine block is not valid JSON ({exc}) — "
                f"it is generated, not written by hand; regenerate it with `{CLI} summary`")
        base = machine["base"]
        n = git("rev-list", "--count", f"{base}..HEAD").out.strip() or "0"
        print(T("aged_head", sha=base[:12], n=n))
        drift = []
        for bid, info in machine["blocks"].items():
            if not info.get("paths"):
                continue
            records = log_records("--name-only", f"{base}..HEAD", "--", *info["paths"])
            files = {p for _sha, paths in records for p in paths}
            if records:
                drift.append((len(records), len(files), bid, info.get("title", "")))
        if not drift:
            print(T("aged_none"))
            return 0
        for commits, files, bid, title in sorted(drift, reverse=True):
            print(T("aged_row", block=bid, commits=commits, files=files, title=title))
        return 0
    defn, st, rows = blocks(), state(), findings()
    # One count for both renderings: the HTML is the same summary, not a second tally.
    facts = summary_facts(defn, st, rows)
    if args.html:
        text = render_summary_html(facts).rstrip("\n")
    else:
        text = render_summary(defn, st, rows, facts)
    out = Path(args.out or (SUMMARY_HTML_DEFAULT if args.html else SUMMARY_DEFAULT))
    if not out.is_absolute():
        out = ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text + "\n", encoding="utf-8")
    print(f"written: {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}")
    return 0


def cmd_sarif(args) -> int:
    """The open and deferred findings of the register as SARIF 2.1.0 — for GitHub code
    scanning, uploaded by `github/codeql-action/upload-sarif`. Printed to stdout; `--out`
    writes a file instead, wherever it says (the one other place the tool writes outside
    docs/review/, beside `summary` — SECURITY.md names both)."""
    defn, rows = blocks(), findings()
    text = json.dumps(render_sarif(defn, rows), ensure_ascii=False, indent=2) + "\n"
    if not args.out:
        sys.stdout.write(text)
        return 0
    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"written: {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}")
    return 0
