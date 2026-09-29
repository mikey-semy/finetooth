"""Checks of coverage: patterns, scope, the file map, freshness, sweeps, the ceiling."""

from __future__ import annotations

from ..git import git_files, untracked_files
from ..workspace import CLI, REVIEW
from ..model import PROOFS, READ_LINES_KEY, READ_STATUSES, SWEEP_DIR_NAME
from ..blocks import block_index, block_lines, read_under_ceiling, readable_lines
from ..coverage import (
    SHARED_OWNERS_ADVICE, coverage_map, enumerates_beyond, freshness_inert, review_scope,
    shared_owners, stale_tree, sweep_script,
)
from ..gates import Refusals


def paths_match_files(defn: dict, st: dict, rows: list[dict], gates: Refusals) -> None:
    """Every pattern of a block matches a tracked file."""
    # a pattern that matches nothing silently shrinks a block's scope: the
    # manifest promises to read code that was never handed to the agent.
    for b in defn["blocks"]:
        for key in ("paths", "ref_paths"):
            for spec in b.get(key, []):
                if not git_files([spec]):
                    untracked = untracked_files([spec])
                    if untracked:
                        gates.refuse(
                            "paths/only-untracked",
                            f"{b['id']}: {key} pattern `{spec}` matches only untracked files "
                            f"({len(untracked)}) — the tool sees the index, not the disk: "
                            f"`git add -- {spec}`"
                        )
                    else:
                        gates.refuse(
                            "paths/matches-nothing",
                            f"{b['id']}: {key} pattern `{spec}` matches no file — "
                            "the block silently shrank"
                        )


def scope_declared(defn: dict, st: dict, rows: list[dict], gates: Refusals) -> None:
    """A partial review says why, and its patterns match files."""
    # the declared partial scope. Its reason is what tells a reader of the summary why
    #  the rest was not read; a scope pattern that matches nothing makes the coverage gate
    #  pass over files that are not there — the same silent shrinking as a block's.
    sc = review_scope(defn)
    if sc is not None:
        if not isinstance(sc.get("reason"), str) or not sc["reason"].strip():
            gates.refuse(
                "scope/no-reason",
                "blocks.json: `scope` has no `reason` — a partial review is published as "
                "partial, with the reason the rest was not read (a trial run, a release gate, "
                "one risky area); write it in `scope.reason`"
            )
        for spec in sc["paths"]:
            if not git_files([spec]):
                gates.refuse(
                    "scope/matches-nothing",
                    f"blocks.json: `scope` pattern `{spec}` matches no tracked file — the "
                    f"coverage gate would check nothing there; fix the pattern (they are git "
                    f"pathspecs, like a block's `paths`) or remove it"
                )


def coverage_complete(defn: dict, st: dict, rows: list[dict], gates: Refusals) -> None:
    """Every file belongs to a block; a file owned twice is named."""
    # coverage
    owned, _, unassigned = coverage_map()
    if unassigned:
        gates.refuse("coverage/unowned-files",
                     f"{len(unassigned)} files belong to no block — `{CLI} coverage`")
    # A warning, not a refusal: the map is complete, and a review already running with an
    # overlap should not stop over it — but the volume of both blocks is counted with the
    # file, and each hunter may leave it to the other.
    if shared := shared_owners(owned):
        pairs = sorted({", ".join(bs) for bs in shared.values()})
        gates.warn("coverage/multiple-owners",
                   f"{len(shared)} file(s) owned by more than one block ({'; '.join(pairs)}), "
                   f"e.g. {min(shared)} — {SHARED_OWNERS_ADVICE}; `{CLI} coverage` lists them")


def coverage_map_fresh(defn: dict, st: dict, rows: list[dict], gates: Refusals) -> None:
    """coverage.tsv on disk is the recount."""
    # The coverage map on disk must match the recount: otherwise the consumer reads
    # yesterday's ownership and does not know it. That is exactly how it diverged —
    # the review's own files appeared after the map was written.
    cov = REVIEW / "coverage.tsv"
    if cov.exists():
        owned, excluded, unassigned = coverage_map()
        fresh = {f"{f}\t{','.join(bs)}" for f, bs in owned.items()}
        on_disk = {
            ln.rstrip("\n")
            for ln in cov.read_text(encoding="utf-8").splitlines()
            if ln.strip() and not ln.startswith("#") and ln != "file\tblocks"
        }
        if fresh != on_disk:
            gates.refuse(
                "coverage/stale",
                f"coverage.tsv is stale: {len(on_disk)} lines on disk, "
                f"the recount gives {len(fresh)} — run `{CLI} coverage`"
            )


def tree_fresh(defn: dict, st: dict, rows: list[dict], gates: Refusals) -> None:
    """The tree under review is not behind the main line."""
    # A tree that fell behind the server shows the fixed as broken. The findings of such a
    # pass describe code that no longer exists, and "confirmed by execution" sounds just as
    # convincing as on a fresh tree.
    if inert := freshness_inert():
        gates.warn("freshness/inert", f"the freshness gate is not running: {inert}")
    stale = stale_tree()
    if stale:
        days, ref = stale
        gates.refuse(
            "freshness/tree-behind",
            f"the tree is behind {ref} by {days:.0f} days — the findings of such a pass may "
            f"describe what is already fixed; `git fetch` and compare with {ref} before "
            f"filing them"
        )


def sweeps_scripted(defn: dict, st: dict, rows: list[dict], gates: Refusals) -> None:
    """An enumerating criterion is a declared sweep with its script."""
    idx = block_index(defn)
    # An enumeration criterion is a sweep over the program: declared, and done by a script.
    for bid, b in idx.items():
        if enumerates_beyond(b) and not b.get("sweep"):
            gates.refuse(
                "sweep/undeclared",
                f"{bid}: the acceptance criterion enumerates places across the program "
                f"(\"every place…\", \"all calls…\"), but the block declares no `sweep` — the "
                f"ceiling then counts a tenth of the work; add `sweep` (the patterns the "
                f"enumeration covers) to blocks.json")
        status = st["blocks"].get(bid, {}).get("status", "todo")
        if b.get("sweep") and status not in ("todo", "running") and not sweep_script(b):
            gates.refuse(
                "sweep/no-script",
                f"{bid}: the block declares a sweep but there is no sweep script at "
                f"docs/review/{SWEEP_DIR_NAME}/{bid}.<ext> — the list of places is complete "
                f"only if a script produced it; commit the script the hunter used")


def blocks_readable(defn: dict, st: dict, rows: list[dict], gates: Refusals) -> None:
    """A block can be read in one session."""
    idx = block_index(defn)
    # A block that cannot be read in one session is a promise, not a block.
    for bid, b in idx.items():
        if not b.get("paths"):
            continue
        if b.get("proof", "read") not in PROOFS:
            gates.refuse("blocks/proof-unknown",
                         f"{bid}: proof '{b.get('proof')}' is not in the vocabulary: {', '.join(PROOFS)}")
            continue
        # The ceiling is a promise to read in full; a measured block makes no such promise.
        if b.get("proof", "read") == "measured":
            continue
        n, lines = block_lines(b["paths"])
        limit = readable_lines()
        if lines <= limit:
            continue
        # The split must come BEFORE the reading: after it the report already says what was
        # read, and refusing then made a closed block red for code added later (this kit's
        # own T1 grew past the ceiling with new commands, and every PR into review.py failed
        # `check`). What is left is a debt of the next review, said aloud.
        s = st["blocks"].get(bid, {})
        status = s.get("status", "todo")
        if read_under_ceiling(s, limit):
            gates.warn(
                "blocks/grew-past-ceiling",
                f"{bid}: {n} files, {lines} lines — grew past the ceiling ({limit}) after the "
                f"review (read at {s[READ_LINES_KEY]}, status {status}); the report stands for "
                f"what was read then, but the "
                f"next review of this code must split the block first: `{CLI} sizes`")
            continue
        # A status past the hunt without a reading recorded within the ceiling is no excuse:
        # the report of such a block was written on a volume nobody can read in one session.
        read = s.get(READ_LINES_KEY)
        why = ("" if status not in READ_STATUSES else
               f" Status {status} does not excuse it: the block was read at {read} lines."
               if isinstance(read, int) else
               f" Status {status} does not excuse it: the size at reading was never recorded "
               f"(a review older than the record), and only a block read within the ceiling "
               f"is let through.")
        gates.refuse(
            "blocks/too-big-to-read",
            f"{bid}: {n} files, {lines} lines — cannot be read in one session "
            f"(ceiling {limit}).{why} Split the block, or the report will lie about coverage"
        )
