"""Commands: status, next, set-status, log, decide."""

from __future__ import annotations

import json

from ..base import die, now
from ..workspace import CLI, DECISIONS_FILE, STATE_FILE, save_json
from ..model import NEXT_ROLE, READ_LINES_KEY, READ_STATUSES, SEVERITIES, STATUSES
from ..blocks import (
    block_index, block_lines, blocks, ceiling_block, next_block, phase_name, readable_lines,
    stamp, state,
)
from ..register import draft_not_imported, findings, fix_debt, fix_gate
from ..coverage import ceiling_mark, scope_line
from ..journal import journal, last_review_round
from ..settings import deny_line


def cmd_status(args) -> int:
    defn, st = blocks(), state()
    rows = findings()
    open_by_block: dict[str, int] = {}
    for f in rows:
        if f.get("status") == "open":
            open_by_block[f.get("block", "?")] = open_by_block.get(f.get("block", "?"), 0) + 1

    limit = readable_lines()
    mark = {
        "todo": "·", "running": "»", "hunted": "h", "verified": "v",
        "triaged": "t", "fixing": "f", "closed": "✓", "blocked": "!",
    }
    phase = None
    for b in defn["blocks"]:
        if b["phase"] != phase:
            phase = b["phase"]
            print(f"\n── Phase {phase_name(phase)} " + "─" * 40)
        s = st["blocks"].get(b["id"], {})
        status = s.get("status", "todo")
        opened = open_by_block.get(b["id"], 0)
        tail = f"  open findings: {opened}" if opened else ""
        if size := ceiling_mark(b, s, limit)[0]:
            tail += f"  {size}"
        print(f"  {mark.get(status,'?')} {b['id']:<4} {status:<9} {b['title']}{tail}")

    total = len(defn["blocks"])
    closed = sum(1 for b in defn["blocks"] if st["blocks"].get(b["id"], {}).get("status") == "closed")
    print(f"\nblocks: {closed}/{total} closed")
    partial = scope_line(defn, "en")
    if partial:
        print(partial)

    by_sev = {s: 0 for s in SEVERITIES}
    for f in rows:
        if f.get("status") == "open":
            by_sev[f.get("severity", "low")] = by_sev.get(f.get("severity", "low"), 0) + 1
    print("findings open: " + ", ".join(f"{s}={by_sev.get(s,0)}" for s in SEVERITIES)
          + f"  (total records: {len(rows)})")
    gate = fix_gate(defn)
    if gate:
        debt = fix_debt(defn, rows)
        if debt:
            in_blocks = sorted({f.get("block", "?") for f in debt})
            print(f"fix debt (gate: {gate} and above): {len(debt)} open in {len(in_blocks)} block(s) — "
                  f"{', '.join(in_blocks)}; the next block will not start until they are fixed, "
                  f"deferred with a reason or rejected")
        else:
            print(f"fix debt (gate: {gate} and above): none")
    denied = deny_line(defn.get("gates", []))
    if denied:
        print(denied)

    blocked = [b for b in defn["blocks"] if st["blocks"].get(b["id"], {}).get("status") == "blocked"]
    if blocked:
        print("\nwaiting:")
        for b in blocked:
            print(f"  ! {b['id']:<4} {b['title']} — {st['blocks'][b['id']].get('note') or 'no note'}")

    nxt = next_block(defn, st)
    if nxt:
        cur = st["blocks"][nxt["id"]]["status"]
        role = NEXT_ROLE.get(cur, "hunter")
        print(f"\nnext block: {nxt['id']} ({nxt['title']}) — status {cur}")
        print(f"prompt:   {CLI} prompt {nxt['id']} --role {role}")
        print(f"manifest: docs/review/blocks/{nxt['id']}-{nxt['slug']}.md")
    elif blocked:
        # A blocked block is not a read one. It used to not prevent declaring the review
        # finished, and the directory was offered for deletion with an unread block inside.
        print(f"\nreview is NOT finished: waiting {', '.join(b['id'] for b in blocked)}")
    elif not defn["blocks"]:
        print("\nreview not started: blocks.json has no blocks")
    else:
        print("\nall blocks closed — time to consolidate the findings and delete docs/review/")
    return 0


def cmd_next(args) -> int:
    nxt = next_block(blocks(), state())
    print(nxt["id"] if nxt else "")
    return 0


def cmd_decide(args) -> int:
    """Record a human's decision on a block: the answer to the loop signal."""
    if args.block not in block_index(blocks()):
        die(f"unknown block {args.block}")
    text = " ".join(args.text.split())
    if not text:
        die("the decision is empty — write what was decided: the next fixer gets it as it is")
    rnd = last_review_round(args.block, findings()) if args.round is None else args.round
    if rnd < 0:
        die(f"--round {rnd}: rounds are counted from 1 (0 — before any fix review)")
    row = {"block": args.block, "round": rnd, "at": now(), "text": text}
    with DECISIONS_FILE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    # The journal is where a human looks for what was decided; the file is what the tool reads.
    journal(args.block, f"decision after fix review round {rnd}: {text}")
    print(f"{args.block}: decision recorded after fix review round {rnd} — "
          f"`{CLI} prompt {args.block} --role fix --round {rnd + 1}` carries it")
    return 0


def cmd_set_status(args) -> int:
    defn, st = blocks(), state()
    if args.block not in block_index(defn):
        die(f"unknown block {args.block}")
    if args.status not in STATUSES:
        die(f"unknown status {args.status}; known: {', '.join(STATUSES)}")
    s = st["blocks"].setdefault(
        args.block, {"status": "todo", "started": None, "finished": None, "reports": [], "note": ""}
    )
    if args.status == "running":
        debt = fix_debt(defn, findings(), except_block=args.block)
        if debt:
            ids = ", ".join(f"{f.get('id')} ({f.get('severity')})" for f in debt[:8])
            more = f" and {len(debt) - 8} more" if len(debt) > 8 else ""
            die(f"fix gate: {len(debt)} open finding(s) at `{fix_gate(defn)}` or above in the blocks "
                f"already passed — {ids}{more}. The next block does not start on top of unfixed "
                f"serious findings: fix them (`{CLI} set-finding <id> fixed --commit <sha>`), defer "
                f"with a reason (`deferred --reason \"…\"`) or reject (`rejected --reason \"…\"`). "
                f"To switch the gate off for this project: `\"fix_gate\": \"none\"` in blocks.json")
    b = block_index(defn)[args.block]
    if args.status in READ_STATUSES and ceiling_block(b):
        record_reading(args.block, b, s, args.status)
    if args.status in ("verified", "closed"):
        # A block passed with its draft outside the register passes with findings nobody
        # will see: the summary, findings.md and the fix gate read the register only (#42).
        if why := draft_not_imported(block_index(defn)[args.block], findings()):
            die(why)
    # A re-set of the status a block already has is not a transition: it is how a review older
    # than `read_lines` records the size (record_reading), and it must touch nothing else.
    repeat = s.get("status") == args.status
    closing = args.status == "closed" and not repeat
    s["status"] = args.status
    # The timestamp is set on EVERY entry into running, not only the first: a block
    # returned to work three weeks later would otherwise count as stuck at once, and the
    # check advised restarting exactly what was being worked on.
    if args.status == "running":
        s["started"] = now()
    # Only a real closing: a repeated `closed` must not rewrite the date.
    if closing:
        s["finished"] = now()
    # Fingerprint of WHAT exactly was reviewed. A "passed" status without it holds forever:
    # the block's files get rewritten, and the block still counts as closed — what was
    # reviewed turns out to be a different text. The form is taken from doorstop, where a
    # requirement has a `reviewed` field with a content hash, and an edit of the text by
    # itself moves it to "unreviewed changes".
    # Only at the points where the review is COMPLETE: verification (verified) and closing
    # after the diff review (closed). Moving to triaged or fixing is not a review; re-take
    # the fingerprint there, and any status change would silently declare the changed code
    # reviewed, bypassing `restamp`, which exists precisely so that this is said on record.
    # The same holds for a repeat of `verified`/`closed`: the CHANGELOG sends every review
    # under way to run one to record `read_lines`, and re-taking the fingerprint there made
    # a block closed on one version of the code certify another — no `restamped_at`, no
    # journal line, and the "block files changed" refusal gone (fix review of 0.8.0).
    if args.status in ("verified", "closed") and not repeat:
        stamp(block_index(defn)[args.block], s)
    if args.report:
        for r in args.report:
            if r not in s["reports"]:
                s["reports"].append(r)
    if args.note:
        s["note"] = args.note
    st["updated_at"] = now()
    save_json(STATE_FILE, st)
    print(f"{args.block}: {args.status}")
    return 0


def record_reading(bid: str, b: dict, s: dict, to: str) -> None:
    """Record the size a block is read at, or refuse a reading the ceiling does not allow.

    Entry into a read status from an unread one IS the reading: the block must fit the
    ceiling now, and its size is written, replacing a record of an earlier reading. A move
    between read statuses keeps the record; a block without one (a review older than the
    record) gets it only while it fits — so the honest backfill for such a block is
    `set-status <ID> <its current status>` while it is within the ceiling, and a block that
    has already grown past it without a record is split, not excused.
    """
    limit = readable_lines()
    _, lines = block_lines(b["paths"])
    fresh = s.get("status", "todo") not in READ_STATUSES
    if not fresh and isinstance(s.get(READ_LINES_KEY), int):
        return
    if lines > limit:
        how = ("a report on this volume would lie about coverage"
               if fresh else "the size it was read at was never recorded, and now it is "
                             "above the ceiling, so no reading within it can be vouched for")
        die(f"{bid}: {lines} lines against a ceiling of {limit} — cannot move to `{to}`: {how}. "
            f"Split the block by subject in blocks.json (`{CLI} sizes` shows the size), then "
            f"review the parts")
    s[READ_LINES_KEY] = lines


def cmd_log(args) -> int:
    """Append a dated line to the journal. Decisions are what a re-run cannot recover."""
    journal(args.block, args.text)
    print("written to journal.md")
    return 0
