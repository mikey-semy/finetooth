"""Bookkeeping for the full-project review.

The review spans dozens of blocks and many sessions; a context window does not.
Every piece of state therefore lives on disk and is read back through this tool,
so a session that knows nothing can resume exactly where the previous one stopped.

  definition  docs/review/blocks.json   what the blocks are (static, hand-edited)
  state       docs/review/state.json    how far each block got (mutable)
  findings    docs/review/findings.jsonl one line per finding, rewritten on import

Subcommands are described in main(). Standard library only, no dependencies.
"""

from __future__ import annotations

import argparse
import signal

from .base import die
from .git import IN_REPO
from .workspace import SUMMARY_DEFAULT, SUMMARY_HTML_DEFAULT
from .model import CONFIDENCE, ROLES, SEVERITIES
from .i18n import LANGS
from .history import COUPLING_MIN_SHARE, COUPLING_MIN_TOGETHER
from .seams import SEAMS_TOP
from .commands.setup import cmd_init, cmd_setup, cmd_version
from .commands.status import cmd_decide, cmd_log, cmd_next, cmd_set_status, cmd_status
from .commands.coverage import cmd_coverage, cmd_inventory, cmd_sizes
from .commands.history import cmd_coupling, cmd_order, cmd_seams
from .commands.findings import (
    cmd_backfill, cmd_findings, cmd_hypotheses, cmd_import, cmd_refs, cmd_restamp, cmd_roots,
    cmd_set_finding,
)
from .commands.prompt import cmd_prompt
from .commands.report import cmd_sarif, cmd_summary
from .commands.check import cmd_check


def main() -> int:
    # `review.py prompt H1 --role hunter | head` is the obvious way to look
    # at a prompt before handing it to an agent; without this, python answers a
    # closed pipe with a traceback and exit code 120, which reads like the tool
    # is broken.
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)

    p = argparse.ArgumentParser(prog="review", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="create/extend state.json from blocks.json").add_argument(
        "--force", action="store_true", help="rewrite the state from scratch"
    )
    sub.add_parser("version", help="version of the kit installed in this project")
    c = sub.add_parser("setup", help="set up the review in the project: blocks.json skeleton, invariants, entry point")
    c.add_argument("--project", default="", help="project name for the prompts and scaffolds")
    c.add_argument("--lang", default="en", choices=list(LANGS),
                   help="review language: role templates, scaffolds and docs/review artifacts (en by default)")
    c.add_argument("--cli", default="",
                   help="how the project calls the tool, if not directly (for example 'npm run review --'); "
                        "written to blocks.json and used in every hint")
    sub.add_parser("status", help="where we are now")
    sub.add_parser("next", help="id of the next unclosed block")

    c = sub.add_parser("coverage", help="file→block map; fails if there are unowned files")
    c.add_argument("--limit", type=int, default=40)
    c.add_argument("--no-write", action="store_true",
                   help="only check, do not rewrite coverage.tsv — gate mode in CI")

    c = sub.add_parser("prompt", help="assemble the prompt for an agent")
    c.add_argument("block")
    c.add_argument("--role", choices=ROLES, default="hunter")
    c.add_argument("--diff", help="fixreview: diff range of the fixes (main...HEAD)")
    c.add_argument("--round", type=int, default=1, help="round of fixing/fix review (from 1)")
    c.add_argument("--scope", help="fixreview: the half of the fixes this reviewer reports on "
                                   "(backend, ui…) — it names the half, it does not shrink the "
                                   "diff; narrow --diff for that")

    c = sub.add_parser("set-status", help="move a block to a new status")
    c.add_argument("block")
    c.add_argument("status")
    c.add_argument("--report", action="append")
    c.add_argument("--note")

    c = sub.add_parser("import", help="take a block's findings into the shared register")
    c.add_argument("block")
    c.add_argument("--force", action="store_true", help="overwrite the block's findings already taken into work")
    c.add_argument("--append", action="store_true",
                   help="top-up import: append new findings without touching the recorded and fixed ones")
    c.add_argument("--round", type=int,
                   help="with --append: the fix review round that found the new findings (recorded as found_in)")
    c.add_argument("--diff", help="with --round: the diff range that fix review read (pinned to commit ids)")
    c.add_argument("--dry-run", action="store_true",
                   help="only check the draft row by row (limits, vocabularies, reasons) — writes nothing; "
                        "the role runs it before handing the draft in")

    c = sub.add_parser("decide", help="record a human's decision on a block — the answer to the loop signal")
    c.add_argument("block")
    c.add_argument("text")
    c.add_argument("--round", type=int,
                   help="the fix review round the decision follows (default: the latest one in the register)")

    c = sub.add_parser("set-finding", help="move a finding (or several): fixed / rejected / duplicate / deferred; "
                            "--severity / --confidence record the verifier's verdict")
    c.add_argument("finding", nargs="+")
    c.add_argument("status")
    c.add_argument("--commit", help="fix commit; required for fixed")
    c.add_argument("--reason", help="reject reason; required for rejected")
    c.add_argument("--dup-of", dest="dup_of", help="id of the finding this one duplicates")
    c.add_argument("--rule", help="what closes the class: path to the guard, test or linter rule")
    c.add_argument("--clear-rule", dest="clear_rule", action="store_true",
                   help="remove the recorded guard (it does not go red on this finding's defect)")
    c.add_argument("--severity", help=f"the verifier's severity: {' / '.join(SEVERITIES)}")
    c.add_argument("--confidence", help=f"the verifier's confidence: {' / '.join(CONFIDENCE)}")
    c.add_argument("--fixed-in", dest="fixed_in", action="append",
                   help="where the fix was made, if not in the finding's file (repeatable)")

    c = sub.add_parser("hypotheses", help="the block's hypotheses and their verdicts")
    c.add_argument("block")

    c = sub.add_parser("restamp", help="confirm the edits were reviewed: of a block or of the code under a finding")
    c.add_argument("block", help="block (H1) or finding (H1-003)")
    c.add_argument("--line", type=int,
                   help="a finding only: the line the defect sits on now, when the code moved away from the cited one")
    c.add_argument("--file",
                   help="a finding only: the file its code is in now, when it moved to another file")

    sub.add_parser("backfill", help="stamp fingerprints on old blocks and findings (with a journal entry)")

    c = sub.add_parser("inventory", help="repository tree: files, lines, binaries, whose — for cutting blocks")
    c.add_argument("--depth", type=int, default=2)
    c.add_argument("--under", help="only under this directory")
    c.add_argument("--unassigned", action="store_true", help="only unowned files")
    sub.add_parser("sizes", help="size of every block against the readability ceiling")
    c = sub.add_parser("coupling", help="files that change together but sit in different blocks — the seams")
    c.add_argument("--since", help="only commits since this date (git --since)")
    c.add_argument("--min-together", type=int, default=COUPLING_MIN_TOGETHER, help="joint commits a pair needs")
    c.add_argument("--min-share", type=float, default=COUPLING_MIN_SHARE, help="share of one file's commits the pair must cover")
    c.add_argument("--write", action="store_true", help="also write docs/review/coupling.tsv")
    c = sub.add_parser("seams", help="pairs of files inside one block linked by an import or by joint changes")
    c.add_argument("block")
    c.add_argument("--top", type=int, default=SEAMS_TOP, help=f"how many pairs to print (default {SEAMS_TOP})")
    c.add_argument("--since", help="only commits since this date (git --since)")
    c.add_argument("--min-together", type=int, default=COUPLING_MIN_TOGETHER, help="joint commits a pair needs")
    c.add_argument("--min-share", type=float, default=COUPLING_MIN_SHARE, help="share of one file's commits the pair must cover")
    c = sub.add_parser("order", help="blocks in the order worth walking them: risk first, change frequency second")
    c.add_argument("--since", help="only commits since this date (git --since)")
    sub.add_parser("refs", help="finding ids of the register named in the code outside docs/review/")
    c = sub.add_parser("summary", help="the one file that outlives docs/review/; --aged <file>: drift since its base commit")
    c.add_argument("--out", help=f"where to write (default {SUMMARY_DEFAULT}, with --html {SUMMARY_HTML_DEFAULT}; outside docs/review/)")
    c.add_argument("--html", action="store_true", help="the same summary as one self-contained HTML file: tables, SVG charts, light and dark theme, no network")
    c.add_argument("--aged", metavar="FILE", help="read a summary and print how much each block changed since its base commit")

    c = sub.add_parser("sarif", help="open and deferred findings as SARIF 2.1.0 for GitHub code scanning")
    c.add_argument("--out", help="write to this file instead of stdout (for upload-sarif in CI)")

    c = sub.add_parser("roots", help="finding roots: how many instances and what closes the class")
    c.add_argument("block", nargs="?")

    sub.add_parser("findings", help="regenerate findings.md from findings.jsonl")
    sub.add_parser("check", help="check the state for consistency")

    c = sub.add_parser("log", help="append a line to the journal")
    c.add_argument("block")
    c.add_argument("text")

    args = p.parse_args()
    if IN_REPO is None and args.cmd != "version":
        die("not inside a git repository — run from the directory of the project under review: "
            "coverage is computed from `git ls-files`")
    return {
        "init": cmd_init, "version": cmd_version, "status": cmd_status, "next": cmd_next, "coverage": cmd_coverage,
        "prompt": cmd_prompt, "set-status": cmd_set_status, "findings": cmd_findings,
        "check": cmd_check, "log": cmd_log, "import": cmd_import, "decide": cmd_decide,
        "set-finding": cmd_set_finding, "hypotheses": cmd_hypotheses,
        "restamp": cmd_restamp, "roots": cmd_roots, "backfill": cmd_backfill,
        "inventory": cmd_inventory, "sizes": cmd_sizes, "coupling": cmd_coupling, "seams": cmd_seams, "order": cmd_order, "refs": cmd_refs, "summary": cmd_summary, "sarif": cmd_sarif,
        "setup": cmd_setup,
    }[args.cmd](args)
