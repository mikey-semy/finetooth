"""Commands: coverage, inventory, sizes."""

from __future__ import annotations

from ..workspace import CLI, COVERAGE_FILE, STATE_FILE
from ..fingerprint import file_lines
from ..blocks import block_lines, blocks, readable_lines, state
from ..coverage import (
    SHARED_OWNERS_ADVICE, ceiling_mark, coverage_map, scope_files, scope_line, shared_owners,
    sweep_lines,
)


def cmd_coverage(args) -> int:
    owned, excluded, unassigned = coverage_map()
    lines = ["file\tblocks"]
    for f in sorted(owned):
        lines.append(f"{f}\t{','.join(owned[f])}")
    # `--no-write` — gate mode: CI checks that there are no unowned files without touching the tree.
    # The map says it is partial in its own first line: `check` reads past `#` lines, and a
    # consumer of the file alone must not take it for the whole repository's map.
    defn = blocks()
    partial = scope_line(defn, "en")
    if partial:
        lines.insert(0, f"# {partial}")
    if not args.no_write:
        COVERAGE_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")

    inside = scope_files(defn)
    # Under a scope a block may own files outside it (a block's `paths` are wider than this
    # run); the count is taken inside the scope, the denominator the gate uses.
    n_owned = len(owned) if inside is None else len(set(owned) & inside)
    total = n_owned + len(unassigned)
    if partial:
        print(partial)
    print(f"covered:     {n_owned}/{total} files{' of the declared scope' if partial else ''}")
    print(f"excluded:    {len(excluded)} (with a reason in blocks.json)")
    print(f"map:         docs/review/coverage.tsv{' (not rewritten: --no-write)' if args.no_write else ''}")
    # Owned twice is not a refusal here (the map is still complete), but it is said: the
    # map's own column shows it one line at a time, and nobody reads a map line by line.
    shared = shared_owners(owned)
    if shared:
        print(f"\nOWNED BY MORE THAN ONE BLOCK: {len(shared)} files")
        for f in sorted(shared)[: args.limit]:
            print(f"  {f}\t{', '.join(shared[f])}")
        if len(shared) > args.limit:
            print(f"  … and {len(shared) - args.limit} more")
        print(f"What to do: {SHARED_OWNERS_ADVICE}.")
    if unassigned:
        print(f"\nNOT COVERED: {len(unassigned)} files{' inside the declared scope' if partial else ''}"
              f" — the review is incomplete:")
        for f in sorted(unassigned)[: args.limit]:
            print(f"  {f}")
        if len(unassigned) > args.limit:
            print(f"  … and {len(unassigned) - args.limit} more")
        # ⚠️ A refusal must say WHAT to do. Flat directories are cut up by name on
        # purpose: let a human, not a pattern, choose the block for a new file — a glob
        # that silently matched means "the file counts as read" although nobody opened
        # it. But if the refusal stops at a list of paths, the human will append the file
        # to the first block that comes to hand, and the price of the decision is not repaid.
        print(
            "\nWhat to do: add the path to the block that is responsible FOR THIS AREA "
            "(docs/review/blocks.json, the paths field).\n"
            f"The list of blocks with their questions: {CLI} status.\n"
            "The choice is made by a human: a file that landed in a block by pattern match "
            "will count as read without having been read."
        )
        return 1
    print("\nno unowned files")
    return 0


def cmd_inventory(args) -> int:
    """The repository tree by directory: files, lines, binaries, whose — for cutting blocks.

    Blocks are cut by subject, not by directory, but it all starts with the tree anyway:
    without it neither the volume nor what remains unowned is visible.
    """
    owned, excluded, unassigned = coverage_map()
    files = sorted(set(owned) | unassigned)
    if args.under:
        prefix = args.under.rstrip("/") + "/"
        files = [f for f in files if f.startswith(prefix)]
    if args.unassigned:
        files = [f for f in files if f in unassigned]
    rows: dict[str, dict] = {}
    for f in files:
        parts = f.split("/")
        key = "/".join(parts[: args.depth]) if len(parts) > args.depth else "/".join(parts[:-1]) or "."
        r = rows.setdefault(key, {"files": 0, "lines": 0, "binary": 0, "unassigned": 0, "blocks": set()})
        r["files"] += 1
        n = file_lines(f)
        if n is None:
            r["binary"] += 1
        else:
            r["lines"] += n
        if f in unassigned:
            r["unassigned"] += 1
        else:
            r["blocks"].update(owned.get(f, []))
    print(f"{'directory':<48} {'files':>6} {'lines':>8} {'binary':>7} {'unowned':>6}  blocks")
    for key in sorted(rows):
        r = rows[key]
        print(f"{key:<48} {r['files']:>6} {r['lines']:>8} {r['binary']:>7} {r['unassigned']:>6}  "
              f"{','.join(sorted(r['blocks'])) or '—'}")
    print(f"\nexcluded files: {len(excluded)}; unowned: {len(unassigned)}")
    return 0


def cmd_sizes(args) -> int:
    """Size of every block against the readability ceiling: what to split before it is too late."""
    defn = blocks()
    # `sizes` is a cutting tool and runs before `init`; without a state every block is unread.
    st = state() if STATE_FILE.exists() else {"blocks": {}}
    limit = readable_lines()
    over = grown = 0
    print(f"{'block':<6} {'proof':<9} {'files':>6} {'lines':>8}  {'ceiling ' + str(limit)}")
    for b in defn["blocks"]:
        if not b.get("paths"):
            print(f"{b['id']:<6} {'stand':<9} {0:>6} {0:>8}  live system")
            continue
        n, lines = block_lines(b["paths"])
        proof = b.get("proof", "read")
        mark, blocking = ceiling_mark(b, st["blocks"].get(b["id"], {}), limit)
        if blocking:
            over += 1
        elif mark:
            grown += 1
        if proof == "measured":
            mark = "measured, the ceiling does not apply"
        sn, sl = sweep_lines(b)
        if sn:
            mark = (mark + "; " if mark else "") + f"+ sweep {sn} files / {sl} lines (mechanical, not read)"
        print(f"{b['id']:<6} {proof:<9} {n:>6} {lines:>8}  {mark}")
    if grown:
        print(f"\nblocks grown past the ceiling after their review: {grown} — the report "
              f"stands; split them before the next review of this code")
    if over:
        print(f"\nblocks above the ceiling: {over}")
        return 1
    if not grown:
        print("\nall readable blocks are within the ceiling")
    return 0
