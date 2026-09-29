"""Which files belong to which block, and whether the tree is fresh enough to review."""

from __future__ import annotations

import re
from pathlib import Path

from .git import all_files, git, git_files, mainline_ref
from .workspace import REVIEW
from .model import ENUMERATION, STALE_TREE_DAYS, SWEEP_DIR_NAME
from .i18n import MSG
from .text import section_body, unquoted
from .fingerprint import file_lines
from .blocks import block_lines, blocks, ceiling_block, manifest_path, read_under_ceiling


def review_scope(defn: dict) -> dict | None:
    """The declared partial scope — `{"paths": [...], "reason": "..."}` — or None.

    A review of one risky area, a release gate or a first trial of the kit is not a
    whole-repository review, and the coverage rule used to know only the whole: the 0.8.0
    release gate walked one block of a ~2000-file repository and needed 183 exclusions to
    get `check` green. An exclusion says "this file is deliberately not a subject of review",
    for good; a scope says "THIS run reads only these files", and every output that could
    be taken for a whole-review result (`coverage`, `status`, `summary`, `sarif`) says so.
    The field is an INCLUSION list of git pathspecs — the vocabulary of a block's `paths` —
    with the reason beside it, so one object carries both and neither can drift from the
    other; a file added inside the scope is still refused until a block owns it.
    """
    return defn.get("scope")


def scope_files(defn: dict) -> set[str] | None:
    """Tracked files the declared scope covers (exclusions subtracted), or None — no scope."""
    sc = review_scope(defn)
    if sc is None:
        return None
    excluded = git_files([e["pattern"] for e in defn.get("exclusions", [])])
    return git_files(sc["paths"]) - excluded


def scope_line(defn: dict, lang: str) -> str | None:
    """One sentence that says the review is partial, names the scope and the reason."""
    sc = review_scope(defn)
    if sc is None:
        return None
    excluded = git_files([e["pattern"] for e in defn.get("exclusions", [])])
    inside = scope_files(defn) or set()
    total = len(all_files() - excluded)
    # One line whatever the reason holds: it becomes a `#` line of coverage.tsv, and a line
    # break in it would put a line into the map that the stale-map check reads as ownership.
    reason = " ".join(str(sc.get("reason") or "").split()) or "—"
    return MSG[lang]["scope_partial"].format(
        paths=", ".join(f"`{p}`" for p in sc["paths"]), n=len(inside), total=total, reason=reason)


def coverage_map() -> tuple[dict[str, list[str]], set[str], set[str]]:
    """file -> owning block ids, plus the excluded and the unassigned sets.

    With a declared scope, "unassigned" is counted inside the scope only: a file outside it
    is not part of this review and is not refused (see `review_scope`)."""
    defn = blocks()
    excluded = git_files([e["pattern"] for e in defn.get("exclusions", [])])
    inside = scope_files(defn)
    everything = (all_files() if inside is None else inside) - excluded
    owned: dict[str, list[str]] = {}
    for b in defn["blocks"]:
        for f in git_files(b.get("paths", [])) - excluded:
            owned.setdefault(f, []).append(b["id"])
    # Owners are sorted: reordering blocks in the array must not change the map.
    for f in owned:
        owned[f].sort()
    unassigned = everything - set(owned)
    return owned, excluded, unassigned


def shared_owners(owned: dict[str, list[str]]) -> dict[str, list[str]]:
    """Files two or more blocks own — usually one block's directory prefix capturing the files
    another block was cut for (`src/` over `src/billing/`), which nobody asked for: the file is
    counted into both blocks' volume, and each hunter takes it for the other's (#46)."""
    return {f: bs for f, bs in owned.items() if len(bs) > 1}


# What to do about files owned twice — one sentence, shared by `coverage` and `check`.
SHARED_OWNERS_ADVICE = (
    "a file is owned by exactly one block: narrow the wider block's `paths`, or subtract the "
    "other block's part from it with a pathspec such as `:(exclude)src/billing` in the same "
    "list (docs/review/blocks.json); if both blocks must read the file, the second one names "
    "it in `ref_paths`")


def freshness_inert() -> str | None:
    """Why the freshness gate cannot run here — or None when it can.

    A gate whose mechanism is silently inert is not a gate: with no `origin/HEAD` the check
    used to return None and say nothing, so a tree twelve days behind passed in silence,
    indistinguishable from a fresh one.
    """
    if mainline_ref():
        return None
    remotes = git("remote").out.split()
    if not remotes:
        return ("no remote in this repository, so the freshness of the tree cannot be "
                "checked at all — findings from a stale copy describe what is already "
                "fixed; if this is a copy of somebody else's repository, add it "
                "(`git remote add origin <url> && git fetch`) before filing findings")
    return (f"remote(s) {', '.join(remotes)} have no HEAD ref, so the freshness of the tree "
            f"is not checked — `git remote set-head {remotes[0]} -a` writes it once and the "
            f"gate starts working")


def stale_tree() -> tuple[float, str] | None:
    """How much fresher the server's tip is than ours — in days, if the gap is large.

    The network is not touched (`fetch` is the human's business); we look at what git
    already knows.
    """
    ref = mainline_ref()
    if not ref:
        return None

    def stamp(rev: str) -> int | None:
        # `show -s`, not `log`: reading a commit's date is not reading the history, and the
        # marked `git log` stream has exactly one reader (`log_records`).
        out = git("show", "-s", "--format=%ct", rev)
        return int(out.out.strip()) if out.code == 0 and out.out.strip() else None

    # Counted from the POINT OF DIVERGENCE, not from our own tip: a fresh commit in a
    # long-ago branch makes its tip newer than the remote one and hides the fact that the
    # branch contains not a single fix made by others in all that time.
    base = git("merge-base", "HEAD", ref)
    anchor = base.out.strip() if base.code == 0 and base.out.strip() else "HEAD"
    mine, theirs = stamp(anchor), stamp(ref)
    if mine is None or theirs is None:
        return None
    days = (theirs - mine) / 86400
    return (days, ref) if days > STALE_TREE_DAYS else None


def sweep_lines(b: dict) -> tuple[int, int]:
    """Files and lines the block's `sweep` covers beyond its own `paths`."""
    if not b.get("sweep"):
        return 0, 0
    own = git_files(b.get("paths", [])) if b.get("paths") else set()
    extra = sorted(git_files(b["sweep"]) - own)
    return len(extra), sum(file_lines(f) or 0 for f in extra)


def sweep_script(b: dict) -> Path | None:
    d = REVIEW / SWEEP_DIR_NAME
    if not d.is_dir():
        return None
    hits = sorted(p for p in d.iterdir() if p.is_file() and p.stem == b["id"])
    return hits[0] if hits else None


def enumerates_beyond(b: dict) -> bool:
    """Does the manifest's acceptance criterion ask to enumerate places program-wide?"""
    m = manifest_path(b)
    if not m.exists():
        return False
    body = section_body(m.read_text(encoding="utf-8"), ACCEPTANCE_HEADING) or []
    # what the criterion SAYS, not an example quoted in it
    return bool(ENUMERATION.search("\n".join(unquoted(body, "text"))))


def ceiling_mark(b: dict, s: dict, limit: int) -> tuple[str, bool]:
    """What the ceiling says of a readable block: the mark and whether it blocks the reading.

    Shared by `sizes` and `status`, so they say what `check` says: above the ceiling before
    the reading — split now; above it after — the report stands, the next review splits.
    """
    if not ceiling_block(b):
        return "", False
    _, lines = block_lines(b["paths"])
    if lines <= limit:
        return "", False
    if read_under_ceiling(s, limit):
        return (f"grew past the ceiling by {lines - limit} after the review — the next "
                f"review splits it", False)
    return f"⚠ above the ceiling by {lines - limit} — split by subject", True


ACCEPTANCE_HEADING = re.compile(r"^#{1,6}\s*.*(критери\w* приёмки|acceptance criteri)", re.IGNORECASE)


def acceptance_of(b: dict) -> str:
    """The manifest's acceptance criterion, collapsed to one line for the table."""
    m = REVIEW / "blocks" / f"{b['id']}-{b['slug']}.md"
    if not m.exists():
        return "—"
    body = section_body(m.read_text(encoding="utf-8"), ACCEPTANCE_HEADING)
    if not body:
        return "—"
    # What the criterion SAYS: a fenced example of a table inside it is not part of the
    # sentence, and pasted into a one-line cell it is a run of backticks and column bars.
    text = " ".join(ln.strip() for ln in unquoted(body, "text") if ln.strip())
    text = text.replace("|", "\\|")
    return text if len(text) <= 300 else text[:297] + "…"
