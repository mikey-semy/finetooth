"""The journal (spend lines) and the loop signal: which round found what, when to stop."""

from __future__ import annotations

import json
import re
from collections.abc import Callable

from .base import die, now
from .git import ROOT, git
from .workspace import CLI, DECISIONS_FILE, JOURNAL_FILE
from .model import ROLES, ROUND_SEVERITY, SEVERITIES
from .i18n import T
from .text import DIFF_HUNK
from .register import finding_file


# One line of the journal that `assets/run-role.sh` writes for a role run: `<role> — spend: …`,
# possibly after the markers it puts in front (`RUN FAILED (…) · `, `TREE LEFT DIRTY (…) · `,
# the stream's own outcome). The wording is `axes.journal_line`'s; what it did not measure it
# prints as `?` and `unknown`, never as zero, and neither is read as zero here.
SPEND_LINE = re.compile(
    r"^- \*\*[^*]*\*\* · `(?P<block>[^`]+)` — (?P<role>" + "|".join(ROLES) + r") — "
    r"(?:.* · )?spend: (?P<minutes>\d+|\?) min, (?P<turns>\d+|\?) turns, "
    r".*?cost estimate (?:\$(?P<cost>\d+(?:\.\d+)?)|unknown)")


def journal_spend() -> list[dict]:
    """The measured role runs of the journal: block, role, turns, cost (None when unknown).
    The one reader of the spend lines — the Markdown and the HTML summary both count from it."""
    if not JOURNAL_FILE.exists():
        return []
    out = []
    for line in JOURNAL_FILE.read_text(encoding="utf-8").splitlines():
        m = SPEND_LINE.match(line)
        if m:
            out.append({"block": m["block"], "role": m["role"],
                        "turns": int(m["turns"]) if m["turns"] != "?" else None,
                        "cost": float(m["cost"]) if m["cost"] is not None else None})
    return out


def money(x: float) -> str:
    return f"${x:.2f}"


def bounded(known: list, fmt: Callable[[float], str]) -> str:
    """A sum over runs some of which did not report the number (`None`): the known part as a
    lower bound, `≥ N`, or "unknown" when none reported it. A plain sum of the known values
    printed 0 for a run cut off before its result — "free" to the reader — and a bare total
    under-reported by exactly the runs that went wrong."""
    have = [v for v in known if v is not None]
    if not have and known:
        return T("sum_not_known")
    text = fmt(sum(have))
    return T("sum_at_least", v=text) if len(have) < len(known) else text


def spend_sum(runs: list[dict]) -> dict:
    """Runs, turns and cost of a set of runs. `unknown` counts the runs a number is missing
    in; `turns_text` and `cost_text` are what every summary shows — see `bounded`."""
    costs = [r["cost"] for r in runs]
    return {"runs": len(runs),
            "turns": sum(r["turns"] for r in runs if r["turns"] is not None),
            "cost": round(sum(c for c in costs if c is not None), 2),
            "unknown": sum(1 for r in runs if r["turns"] is None or r["cost"] is None),
            "cost_known": any(c is not None for c in costs),
            "turns_text": bounded([r["turns"] for r in runs], lambda v: str(v)),
            "cost_text": bounded(costs, lambda v: money(round(v, 2)))}


#
# The kit's own review ran three blocks through two and three fix rounds each (T2–T4, issue
# #9). From round 2 on, almost every fix-review finding sat in the code the previous round
# had written — mostly inside the guard that round added to close a class — and each round's
# guard got its own hole found by the next. The round counter is not the signal; the place
# is: when the top finding of fix review N−1 lies on a line fix round N−1 changed, round N
# repeats the pattern, and what stopped it every time was a human's decision. So the tool
# asks for that decision before another round, and carries it into the next prompts.


def pinned_range(rng: str) -> str | None:
    """`A...B` or `A..B` as `<base>..<tip>` commit ids, or None when it is not a range of commits.

    `git diff A...B` is the diff from their merge base to B, so that is the base pinned. A
    symbolic range moves with the branch: `main...HEAD` read after the next round commits is
    another diff, and a finding would be judged against lines its round never wrote.
    """
    sym = "..." in rng
    a, sep, b = rng.partition("..." if sym else "..")
    if not sep or a.startswith("-") or b.startswith("-"):
        return None
    a, b = a or "HEAD", b or "HEAD"
    tip = git("rev-parse", "--verify", "--quiet", f"{b}^{{commit}}")
    base = (git("merge-base", a, b) if sym
            else git("rev-parse", "--verify", "--quiet", f"{a}^{{commit}}"))
    if tip.code != 0 or base.code != 0 or not base.out.split():
        return None
    return f"{base.out.split()[0]}..{tip.out.strip()}"


def diff_spans(rng: str, rel: str) -> list[tuple[int, int]] | None:
    """The lines of `rel` the range wrote, as `(first, last)` spans of the new side; None when
    git cannot read the range. Asked per file, so no path is parsed out of a patch."""
    out = git("diff", "--no-ext-diff", "--no-color", "-U0", rng, "--", f":(literal){rel}")
    if out.code != 0:
        return None
    spans = []
    for m in DIFF_HUNK.finditer(out.out):
        first, count = int(m.group(1)), int(m.group(2) or "1")
        if count:
            spans.append((first, first + count - 1))
    return spans


def found_round(f: dict) -> int | None:
    """The fix review round that found the finding, when `import --round` recorded one.
    Records from before the field — and anything hand-written in its place — have none."""
    fi = f.get("found_in")
    if not isinstance(fi, dict) or fi.get("role") != "fixreview":
        return None
    rnd = fi.get("round")
    return rnd if isinstance(rnd, int) and not isinstance(rnd, bool) else None


def last_review_round(block_id: str, rows: list[dict]) -> int:
    """The latest fix review round that put findings into the block's register; 0 if none."""
    return max((r for f in rows if f.get("block") == block_id
                and (r := found_round(f)) is not None), default=0)


def in_own_diff(f: dict) -> bool:
    """Does the finding's file:line lie on a line its round's diff wrote? By LINE, not by
    file: a finding elsewhere in a file the round touched is not the round's own code."""
    line, rng = f.get("line"), (f.get("found_in") or {}).get("diff")
    if not isinstance(line, int) or isinstance(line, bool) or not rng or not finding_file(f):
        return False
    return any(a <= line <= b for a, b in diff_spans(str(rng), finding_file(f)) or [])


def decisions() -> list[dict]:
    """The human's decisions, in the order they were taken."""
    if not DECISIONS_FILE.exists():
        return []
    out = []
    for n, line in enumerate(DECISIONS_FILE.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            die(f"{DECISIONS_FILE.relative_to(ROOT)} line {n}: not JSON — {exc}; it is written "
                f"by `{CLI} decide`, fix the line by hand")
        if isinstance(row, dict):
            out.append(row)
    return out


def loop_stop(block_id: str, rnd: int, rows: list[dict]) -> str | None:
    """Why fix round `rnd` is a human's move, not the next agent's — or None.

    The top finding of fix review `rnd − 1` (by severity, among its open ones) is medium or
    higher and lies inside the diff of fix round `rnd − 1`, and no decision was recorded
    after that review. Findings without `found_in` take no part: nothing says which round
    found them.
    """
    prev = rnd - 1
    if prev < 1:
        return None
    theirs = [f for f in rows if f.get("block") == block_id and f.get("status") == "open"
              and found_round(f) == prev]
    order = {s: i for i, s in enumerate(SEVERITIES)}
    top = min((order.get(f.get("severity"), len(order)) for f in theirs), default=len(order))
    if top > order[ROUND_SEVERITY]:
        return None
    inside = [f for f in sorted(theirs, key=lambda f: f.get("id", ""))
              if order.get(f.get("severity")) == top and in_own_diff(f)]
    if not inside:
        return None
    if any(d.get("block") == block_id and isinstance(d.get("round"), int)
           and d["round"] >= prev for d in decisions()):
        return None
    f = inside[0]
    return T("loop_stop", id=f.get("id"), sev=f.get("severity"), file=finding_file(f),
             line=f.get("line"), prev=prev, diff=f["found_in"]["diff"], cli=CLI, block=block_id)


def render_decisions_for(block_id: str) -> str:
    rows = [d for d in decisions() if d.get("block") == block_id]
    if not rows:
        return T("dec_none")
    return "\n".join(T("dec_row", date=str(d.get("at") or "")[:10], round=d.get("round", "?"),
                       text=d.get("text", "")) for d in rows)


def journal(block: str, text: str) -> None:
    """Append a dated line to the journal — the log a human reads. Every line the tool writes
    comes through here (`log`, `decide`, `backfill`; `run-role.sh` calls `log`), and it only
    appends, stamped now, so the tool cannot put a line out of time order. A journal edited on
    two branches can: resolving the merge keeps each branch's lines as a block, and in the kit's
    own review four such merges put a later line above an earlier one (fix review of the 0.8.0
    candidate) — merging a journal, keep its lines in time order."""
    if not JOURNAL_FILE.exists():
        JOURNAL_FILE.write_text(T("journal_head"), encoding="utf-8")
    with JOURNAL_FILE.open("a", encoding="utf-8") as fh:
        fh.write(f"- **{now()}** · `{block}` — {text}\n")
