"""Commands: coupling, seams, order."""

from __future__ import annotations

from ..base import die
from ..git import ROOT
from ..workspace import CLI, COUPLING_FILE
from ..blocks import block_index, blocks, manifest_path, phase_name, state
from ..coverage import coverage_map
from ..history import (
    block_churn, block_risk, commit_file_sets, coupling_pairs, history_line, hub_blocks,
    mass_basis, mass_cutoff,
)
from ..seams import SEAMS_TOP, block_seams, seam_lines


def cmd_coupling(args) -> int:
    """Pairs of files that change together but belong to different blocks — the seams."""
    owned, _, _ = coverage_map()
    sets, merges = commit_file_sets(args.since)
    if not sets:
        print("no commits in the history — nothing to couple")
        return 0
    cutoff = mass_cutoff(sets)
    hub_at = hub_blocks(len(blocks()["blocks"]))
    pairs, hubs, skipped = coupling_pairs(owned, sets, cutoff, args.min_together,
                                          args.min_share, hub_at)
    print(f"commits: {len(sets)}; mass commits skipped (> {cutoff} files, "
          f"{mass_basis(sets)}): {skipped}")
    print(history_line(sets, merges))
    print(f"thresholds: together ≥ {args.min_together}, share ≥ {args.min_share:.0%}, "
          f"hub = coupled with ≥ {hub_at} blocks\n")
    if hubs:
        print(f"shared nodes ({len(hubs)}) — coupled with many blocks, excluded from the pairs; "
              f"they belong in ref_paths of everyone who touches them:")
        for f, bl in hubs:
            print(f"  {f}  ← {len(bl)} blocks: {', '.join(sorted(bl))}")
        print()
    if not pairs:
        print("no cross-block pairs above the thresholds")
    else:
        print(f"cross-block pairs ({len(pairs)}):")
        for p in pairs:
            ba, bb = "+".join(p["blocks_a"]), "+".join(p["blocks_b"])
            lead, other, lead_block = ((p["a"], p["b"], bb) if p["share_a"] >= p["share_b"]
                                       else (p["b"], p["a"], ba))
            print(f"  {p['together']:>3}×  {ba} {p['a']}  ↔  {bb} {p['b']}  "
                  f"({p['share_a']:.0%} / {p['share_b']:.0%})")
            print(f"        → add `{other}` to ref_paths of the block that reads `{lead}`; "
                  f"hypothesis: a value leaving `{lead}` reaches `{other}` unchanged")
        # a cluster of pairs between the same two blocks is a seam worth its own block
        clusters: dict[tuple[str, str], int] = {}
        for p in pairs:
            key = (p["blocks_a"][0], p["blocks_b"][0])
            clusters[key] = clusters.get(key, 0) + 1
        strong = sorted(((n, k) for k, n in clusters.items() if n >= args.min_together), reverse=True)
        if strong:
            print("\nclusters — several pairs between the same two blocks; a seam block "
                  "(one chain from input to storage, one named instance of the data) is due:")
            for n, (x, y) in strong:
                print(f"  {x} ↔ {y}: {n} pairs")
    if args.write:
        lines = ["a\tblocks_a\tb\tblocks_b\ttogether\tshare_a\tshare_b"]
        for p in pairs:
            lines.append(f"{p['a']}\t{'+'.join(p['blocks_a'])}\t{p['b']}\t{'+'.join(p['blocks_b'])}"
                         f"\t{p['together']}\t{p['share_a']:.2f}\t{p['share_b']:.2f}")
        COUPLING_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"\nwritten: {COUPLING_FILE.relative_to(ROOT)}")
    return 0


def cmd_seams(args) -> int:
    """Pairs of files INSIDE one block linked by an import or by joint changes."""
    defn = blocks()
    idx = block_index(defn)
    if args.block not in idx:
        die(f"unknown block {args.block}; known: {', '.join(idx)}")
    b = idx[args.block]
    if args.top < 1:
        die(f"--top must be at least 1, not {args.top}")
    found = block_seams(b, args.min_together, args.min_share, args.since)
    rows = found["rows"]
    n_imp = sum(1 for r in rows if r["imports"])
    n_co = sum(1 for r in rows if r["together"])
    n_both = sum(1 for r in rows if r["both"])
    print(f"block {b['id']}: {len(found['files'])} files; pairs linked by an import: {n_imp}, "
          f"by joint changes: {n_co}, by both: {n_both}")
    print(f"imports: {found['resolved']} resolved to a tracked file ({found['outside']} of them "
          f"outside the block), {found['unresolved']} not resolved — packages, aliases no config "
          f"declares, files not in the repository; skipped")
    for c in found["configs"]:
        print(f"aliases: {c}")
    sets = found["sets"]
    if sets:
        print(history_line(sets, found["merges"]))
        print(f"joint changes: together ≥ {args.min_together}, share ≥ {args.min_share:.0%} "
              f"(the thresholds of `coupling`); {found['skipped']} mass commits skipped "
              f"(> {found['cutoff']} files, {mass_basis(sets)})")
    else:
        print("no commits in the history — joint changes cannot be counted")
    if not rows:
        print("\nno two files of the block are linked — nothing to join across files")
        return 0
    top = rows[:args.top]
    print(f"\nseams ({len(top)} of {len(rows)}; both kinds first, then joint changes, then "
          f"imported names):")
    print("\n".join(seam_lines(top)))
    print(f"\nfor each: a hypothesis in the manifest ({manifest_path(b).relative_to(ROOT)}) on "
          f"what one side assumes about the other — the value, the state, the error it expects "
          f"— and the check that the other side holds it on every path. The hunter prompt "
          f"carries the top {SEAMS_TOP} (`{CLI} prompt {b['id']} --role hunter`).")
    return 0


def cmd_order(args) -> int:
    """Blocks in the order worth walking them: risk first, change frequency second."""
    defn, st = blocks(), state()
    owned, _, _ = coverage_map()
    sets, merges = commit_file_sets(args.since)
    cutoff = mass_cutoff(sets) if sets else 0
    churn = block_churn(owned, sets, cutoff)
    window = f"since {args.since}" if args.since else "whole history"
    print(f"commits: {len(sets)} ({window}); mass commits skipped (> {cutoff} files): "
          f"{sum(1 for fs in sets if len({f for f in fs if f in owned}) > cutoff)}")
    print(history_line(sets, merges))
    stated = sum(1 for b in defn["blocks"] if b.get("risk"))
    print(f"risk stated on {stated} of {len(defn['blocks'])} blocks"
          + ("" if stated else " — below, change frequency alone speaks; state `risk` on the blocks "
             "to put the cost of failure first, as the method wants"))
    print(f"\n{'':2}{'block':<6}{'risk':<10}{'status':<10}{'commits':>8}{'files':>7}  title")
    moved = 0
    phase = None
    for ph in sorted({b["phase"] for b in defn["blocks"]}):
        print(f"\n── Phase {phase_name(ph)} " + "─" * 40)
        group = [b for b in defn["blocks"] if b["phase"] == ph]
        declared = {b["id"]: i for i, b in enumerate(group)}
        ranked = sorted(group, key=lambda b: (block_risk(b), -churn.get(b["id"], (0, 0))[0], declared[b["id"]]))
        for pos, b in enumerate(ranked):
            status = st["blocks"].get(b["id"], {}).get("status", "todo")
            c, nf = churn.get(b["id"], (0, 0))
            mark = " "
            if status not in ("closed",) and declared[b["id"]] != pos:
                mark = "↑" if declared[b["id"]] > pos else "↓"
                moved += 1
            print(f"{mark:2}{b['id']:<6}{(b.get('risk') or '—'):<10}{status:<10}{c:>8}{nf:>7}  {b['title']}")
    if moved:
        print(f"\n{moved} block(s) would move against the declared order; the order is the human's — "
              f"reorder blocks.json if you agree, or state `risk` where the frequency is misleading")
    else:
        print("\nthe declared order already matches risk and change frequency")
    return 0
