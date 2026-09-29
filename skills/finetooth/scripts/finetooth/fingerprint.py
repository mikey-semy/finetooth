"""Fingerprints of code — whole files and the region around a cited line."""

from __future__ import annotations

import hashlib
import os
import re

from .git import NOT_A_FILE_MODES, ROOT, git, index_rows


def file_sha(rel: str) -> str | None:
    """Fingerprint of a file's contents — the same one git computes, without extra dependencies.

    Taken from the working tree while the file is laid out there (that is the text a human
    and an agent actually read), and FROM THE INDEX when it is not. The index branch is not
    an exotic case: a sparse checkout does not lay out part of the tree at all, and a file
    deleted without committing is still listed by `ls-files`. Without it such a file
    contributed only its NAME to the block fingerprint — its contents could be rewritten
    and `check` would never say "block files changed after the review".
    """
    # A finding's `file` comes from a hand-written record and may be any JSON value; a
    # non-string is refused by name (`location_problems`), and here it is simply no file.
    if not isinstance(rel, str) or not rel or rel.startswith("("):
        return None
    p = ROOT / rel
    if p.is_symlink():
        # `hash-object` would follow the link and hash the target: re-pointing to a file
        # with the same contents would go unnoticed. What is hashed is what the symlink is.
        return "link:" + hashlib.sha1(os.readlink(p).encode("utf-8")).hexdigest()
    if p.is_file():
        return git("hash-object", "--", rel).out.strip() or None
    # `:(literal)` — the path is a name, not a pattern: a `[handle]` in it is a directory,
    # not a character class.
    rows = index_rows([f":(literal){rel}"])
    entry = next((r for r in rows if r[2] == rel), None)
    if entry is None or entry[0] in NOT_A_FILE_MODES:
        return None
    if entry[0] == "120000":
        # A symlink not laid out on disk: the index holds its target as the blob. Hashed
        # the same way as the laid-out branch, so the fingerprint does not jump when a
        # sparse checkout lays the link out.
        blob = git("show", f":{rel}", binary=True).out
        return "link:" + hashlib.sha1(blob).hexdigest()
    return entry[1]


# How far the fingerprint of a finding reaches: its line and REGION_K lines above and below.
#
# A hash of the whole file re-flagged every deferred finding on every commit to its file —
# in the kit's own review five pull requests in a row turned `check` red on the same 15
# findings whose code nobody had touched (#37). A window around the line is what GitHub
# code scanning matches on too (`primaryLocationLineHash`, the context of the line). The
# size is measured on the kit's own history, not guessed:
#
#   * fixes seen — of the 148 fixed findings of the review that have a fix commit, the
#     window at the cited line (in the version the finding was imported on) is gone after
#     the fix commit for 67 at K=0, 95 at K=2, 98 at K=3, 103 at K=5, 111 at K=10; the
#     whole-file hash sees 141 (the other seven fix commits did not touch the file);
#   * edits elsewhere — over 61 commits to `review.py` and `tests/test_review.py`, the
#     window around a line the commit left untouched breaks in 0.9% of cases at K=1, 2.4%
#     at K=3, 3.5% at K=5, 5.7% at K=10; the whole-file hash breaks on every commit;
#   * uniqueness — at K=0 16 of 164 cited lines occur more than once in their file (`)`,
#     a blank line), at K=1 3, from K=2 on none.
#
# K=3 sits past the knee: up to 3 each step adds a handful of fixes seen, after it about
# two per step while the collateral rate keeps rising by half a point. The price is named:
# a fix made more than three lines from the cited line (the line is a function's head, the
# fix is in its body) goes unseen by this gate — it is a backstop for a status nobody moved,
# not the way fixes are recorded (`set-finding fixed --commit` is).
REGION_K = 3


def text_lines(rel: str) -> list[bytes] | None:
    """The file's lines as the region fingerprint reads them, or None where there are none.

    Read from the same place as `file_sha` (the working tree while the file is laid out,
    the index when it is not), so the two fingerprints never describe different versions.
    Trailing whitespace is dropped and every line ending counts the same: an editor that
    trims spaces or rewrites CRLF has not changed the code. Leading whitespace is kept —
    GitHub drops all of it, but in Python indentation IS code, and a line moved out of a
    `with` is a different program. A symlink, a binary file (a NUL near the start, as git
    itself decides) and a missing file have no lines: such a finding keeps the whole-file
    fingerprint.
    """
    if not isinstance(rel, str) or not rel or rel.startswith("("):
        return None
    p = ROOT / rel
    if p.is_symlink():
        return None
    if p.is_file():
        try:
            data = p.read_bytes()
        except OSError:
            return None
    else:
        rows = index_rows([f":(literal){rel}"])
        entry = next((r for r in rows if r[2] == rel), None)
        if entry is None or entry[0] in NOT_A_FILE_MODES or entry[0] == "120000":
            return None
        data = git("show", f":{rel}", binary=True).out
    if b"\0" in data[:8192]:
        return None
    return [ln.rstrip() for ln in data.splitlines()]


def region_hash(lines: list[bytes], start: int, count: int) -> str:
    return hashlib.sha256(b"\n".join(lines[start:start + count])).hexdigest()[:16]


def take_region(lines: list[bytes] | None, line) -> dict | None:
    """The region fingerprint of `line` (1-based) in these lines: the hash and how many lines
    above and below it the window took. The window is clipped at the file's edges, so the
    span is recorded, not derived from K — which also lets K change without invalidating
    the records stamped before."""
    if (lines is None or isinstance(line, bool) or not isinstance(line, int)
            or not 1 <= line <= len(lines)):
        return None
    above, below = min(REGION_K, line - 1), min(REGION_K, len(lines) - line)
    return {"region_sha": region_hash(lines, line - 1 - above, above + below + 1),
            "region_span": [above, below]}


def locate_region(f: dict, lines: list[bytes]) -> int | None:
    """Where the finding's window is in these lines — the line it now sits on, or None.

    Searched by CONTENT across the whole file: an edit above the finding moves it without
    touching it. When the same window occurs more than once, the one nearest the recorded
    line wins — that is the one the finding was about, give or take the shift.
    """
    span = f.get("region_span")
    if (not isinstance(span, list) or len(span) != 2
            or not all(isinstance(x, int) and not isinstance(x, bool) and x >= 0 for x in span)):
        return None
    above, below = span
    count = above + below + 1
    was = f["line"] if isinstance(f.get("line"), int) else above + 1
    hits = [s + above + 1 for s in range(0, len(lines) - count + 1)
            if region_hash(lines, s, count) == f.get("region_sha")]
    return min(hits, key=lambda at: (abs(at - was), at)) if hits else None


def line_follows_code(f: dict) -> bool:
    """Whether the line this finding is SHOWN at is looked up in the current file rather than
    read from the register: any finding with a region fingerprint and a line, whatever its
    status. A closed one is looked up too — a rejected finding's code is usually still there,
    and a fixed one's window is usually gone, which leaves the recorded line; a whole-file
    fingerprint has no window to look for, and a line that is not a line number (a gate of
    its own refuses it) is shown as written."""
    line = f.get("line")
    return (bool(f.get("region_sha")) and isinstance(line, int) and not isinstance(line, bool)
            and line >= 1)


def code_fingerprint(rel: str, line) -> dict:
    """The fingerprint a finding gets: its region when it cites a line the file has, the
    whole file when it does not (a finding about a file as a whole, a binary, a symlink)."""
    region = take_region(text_lines(rel), line)
    if region:
        return region
    sha = file_sha(rel)
    return {"code_sha": sha} if sha else {}


# Every field a finding's code fingerprint is written in: `code_sha` (the whole file — the
# only form before #37, and still the form of a finding without a line) or the region pair.
CODE_FINGERPRINT_FIELDS = ("code_sha", "region_sha", "region_span")


def put_fingerprint(f: dict, fp: dict) -> None:
    """Replace the finding's fingerprint: the old form goes, so a record never carries two."""
    for k in CODE_FINGERPRINT_FIELDS:
        f.pop(k, None)
    f.update(fp)


def file_lines(rel: str) -> int | None:
    """Line count — from the INDEX, not from disk.

    The file may be absent from disk while its index entry is alive (deleted without
    committing; sparse-checkout does not lay out part of the tree at all, yet `ls-files`
    prints it). Opening such a path means crashing for no reason or silently losing it
    from the denominator.
    """
    out = git("show", f":{rel}", binary=True)
    # A binary file is not lines: a "two-thousand-line" picture inflated the block and
    # the readability ceiling. The sign is a NUL byte near the start, as git itself does it.
    if out.code == 0 and b"\0" in out.out[:8192]:
        return None
    if out.code != 0:
        p = ROOT / rel
        if not p.is_file():
            return None
        try:
            with open(p, encoding="utf-8", errors="ignore") as fh:
                return sum(1 for _ in fh)
        except OSError:
            return None
    return out.out.count(b"\n") + (0 if out.out.endswith(b"\n") or not out.out else 1)


def cited_line_now(f: dict, lines: list[bytes]) -> int:
    """Where the line a whole-file record cites is in the current file.

    The old fingerprint is the blob the finding was last stamped on, and its line was cited
    on that version. When git still has the blob, the window around the line is taken there
    and looked for here; not found (the code under it changed, or the blob is gone) — the
    recorded line stands, and `restamp` prints what it reads so a human sees the anchor.
    """
    sha = f.get("code_sha")
    if isinstance(sha, str) and re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", sha):
        old = git("cat-file", "blob", sha, binary=True)
        if old.code == 0 and b"\0" not in old.out[:8192]:
            region = take_region([ln.rstrip() for ln in old.out.splitlines()], f.get("line"))
            if region:
                found = locate_region({**region, "line": f.get("line")}, lines)
                if found:
                    return found
    return f.get("line")
