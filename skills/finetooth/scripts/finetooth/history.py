"""What git history says: files that change together, churn, the order of blocks."""

from __future__ import annotations

import math
from collections.abc import Callable

from .base import die
from .git import git, log_records
from .model import SEVERITIES


# Files that change together but sit in different blocks: the seam nobody reads. The
# thresholds come from the first project's measurement (553 pairs co-changed ≥ 3 times,
# 76% across blocks, 38 strong pairs) and from change-coupling research (Zimmermann et al.,
# ROSE, TSE 2005: support and confidence over the commit history):
#   COUPLING_MIN_TOGETHER — a pair counts from this many joint commits (support);
#   COUPLING_MIN_SHARE    — and when the joint commits are at least this share of the
#                           commits of one of the two files (confidence, the stronger side);
#   hub_blocks()          — a file coupled with that many blocks is a shared node (schema,
#                           dictionary), printed apart: it explains most cross-block pairs
#                           and says nothing about a specific seam.
# The mass-commit cutoff is not a constant: it is the 95th percentile of files per commit
# IN THIS repository, so a codemod or a formatting sweep does not manufacture pairs.
COUPLING_MIN_TOGETHER = 3
COUPLING_MIN_SHARE = 0.5
COUPLING_MASS_PERCENTILE = 95
# Fewer commits than this and the percentile cannot separate anything at all: its rank,
# ceil(0.95·n), equals n for every n up to 20. See `mass_cutoff`.
COUPLING_MIN_SAMPLE = 20
# The hub threshold is a SHARE of the review, not a fixed count, and both halves are
# derived rather than chosen. A seam runs between two blocks; a file that reaches a third
# is no longer describing one seam, which is the floor. The share reproduces the number the
# kit has run with since the command appeared — 6 on the 59-block review it was measured on
# (59 × 10% = 5.9) — so a big review keeps the behaviour it was tuned to, while on a review
# of four blocks a "hub coupled with six of four blocks" cannot exist and the filter would
# be dead code.
COUPLING_HUB_SHARE = 0.10
COUPLING_HUB_FLOOR = 3


def hub_blocks(n_blocks: int) -> int:
    """How many blocks a file must be coupled with to count as a shared node."""
    return max(COUPLING_HUB_FLOOR, math.ceil(n_blocks * COUPLING_HUB_SHARE))


def commit_file_sets(since: str | None = None) -> tuple[list[set[str]], int]:
    """The set of files touched by every change that LANDED on the current line, UNDER
    TODAY'S NAMES — and how many of those changes are merges.

    The line is the first-parent history, and a merge on it is read as ONE change: the diff
    against its first parent, i.e. everything the merged branch brought (see #43). That is
    exactly the record a squash merge leaves, so a project gets the same numbers whether its
    pull requests are squashed, rebased or merged — and it is the unit the thresholds of
    `coupling` were measured on (the first project's history is squash commits). The reading
    used to be `--first-parent --no-merges`: a merge dropped whole, and with it every change
    of a project where all work lands by merge commits — a payment block showed 0 of its 24
    commits and `order` ranked it last.

    The format is named, `--diff-merges=first-parent` (git 2.31+), not left to `-m`: `-m`
    takes it from the user's `log.diffMerges`, and with `combined` there a merge that only
    one side touched came out with no files at all — measured, the history emptied again.

    The other way to see merged work, `--no-merges` without `--first-parent` (every commit
    of every branch), was measured and rejected. On eight repositories
    with merged branches, 6 to 60% of the file pairs it lifts over `together ≥ 3` rest on
    fewer than three landed changes — the WIP commits of one branch meeting the "three
    separate joint changes" floor on their own; and the same fix-up commits multiply a
    block's change count by however a team happens to split its work. The walk also stops
    being one line, and the rename translation below assumes one: a rename seen at a commit
    renames everything older ON THE SAME LINE.

    Nothing to detect, no mode: on a history without merges on the first-parent line (linear,
    squashed, rebased) the reading is the old one to the commit, and a merge counts as the
    one change it is. The price is named: a long-lived branch merged rarely (a release
    branch) lands as one wide change; the mass cutoff drops it when it is wider than the
    repository's own outliers.

    Two things `--name-only` alone gets wrong, both measured on this repository's own
    history. A rename is printed as the new path only, so a file's churn is cut at every
    move — `review.py` has 42 first-parent commits and 10 under its current path, and the
    block that owns it was ranked on a quarter of its real change frequency. And a non-ASCII
    path comes out C-quoted (`"src/\\320\\274…"`), so it never matches what `ls-files -z`
    reports and is invisible to `coupling` altogether.

    `--name-status -z -M` answers both: `-z` gives raw NUL-separated paths, and the rename
    records let the old name be translated into the current one. The log is walked
    newest-first, so a rename `old → new` seen at a commit renames everything OLDER than it.
    """
    args = ["--first-parent", "--diff-merges=first-parent", "--name-status", "-M"]
    if since:
        args.append(f"--since={since}")
    merge_run = git("rev-list", "--first-parent", "--merges", "HEAD")
    merge_shas = set(merge_run.out.split()) if merge_run.code == 0 else set()
    merges = 0
    sets: list[set[str]] = []
    # old path -> the name that path bears today
    alias: dict[str, str] = {}
    for sha, tokens in log_records(*args):
        current: set[str] = set()
        renames: list[tuple[str, str]] = []   # (old, new) of the commit being read
        i = 0
        while i < len(tokens):
            status, paths = tokens[i], []
            take = 2 if status[:1] in ("R", "C") else 1
            for j in range(1, take + 1):
                if i + j < len(tokens):
                    paths.append(tokens[i + j])
            i += 1 + len(paths)
            if not paths:
                continue
            if take == 2 and len(paths) == 2:
                old, new = paths
                renames.append((old, new))
                current.add(alias.get(new, new))
            else:
                p = paths[-1]
                current.add(alias.get(p, p))
        if current:
            sets.append(current)
            merges += sha in merge_shas
        for old, new in renames:
            alias[old] = alias.get(new, new)
    return sets, merges


def history_line(sets: list[set[str]], merges: int) -> str:
    """Which history the counts rest on — printed, because "0 commits" on a block means one
    thing on a linear history and another on a merge-commit one."""
    if not merges:
        return "history: the first-parent line, no merges on it — every commit is a change"
    return (f"history: the first-parent line; {merges} of {len(sets)} changes are merges, each "
            f"read as one change — the branch's diff against the first parent, as a squash "
            f"merge would record it")


def quantile(sorted_sizes: list[int], q: float) -> int:
    """Nearest-rank quantile: the smallest value at or below which at least `q` of the
    sample lies. Rank ceil(q·n), 1-based — the textbook definition, and the one that
    actually leaves the top of the distribution outside the cutoff."""
    return sorted_sizes[max(0, math.ceil(q * len(sorted_sizes)) - 1)]


def mass_cutoff(sets: list[set[str]], percentile: int = COUPLING_MASS_PERCENTILE) -> int:
    """How many files a commit may touch before it stops being a joint change.

    A 95th percentile needs a sample: its rank is ceil(0.95·n), which for n ≤ 20 equals n
    itself — the cutoff came out EQUAL to the largest commit and not a single one was ever
    skipped. A young repository is exactly where `coupling` is run first, and its initial
    commit holds the whole tree: it paired every file with every other, and three formatting
    sweeps were enough to push those pairs over the threshold.

    Below the sample floor the outlier is found instead by Tukey's fence — Q3 + 1.5·IQR
    (Tukey, Exploratory Data Analysis, 1977), the standard outlier rule, which asks for no
    large sample and leaves a history without outliers untouched.
    """
    sizes = sorted(len(s) for s in sets)
    if not sizes:
        return 0
    if len(sizes) >= COUPLING_MIN_SAMPLE:
        return max(quantile(sizes, percentile / 100), 2)
    q1, q3 = quantile(sizes, 0.25), quantile(sizes, 0.75)
    return max(int(q3 + 1.5 * (q3 - q1)), 2)


def mass_basis(sets: list[set[str]]) -> str:
    """What the cutoff rests on — printed, because a threshold nobody can trace is a guess."""
    if len(sets) >= COUPLING_MIN_SAMPLE:
        return f"the {COUPLING_MASS_PERCENTILE}th percentile of this repository"
    return (f"Tukey's fence over {len(sets)} commits — fewer than {COUPLING_MIN_SAMPLE}, "
            f"too few for a percentile")


def joint_changes(owned: dict[str, list[str]], sets: list[set[str]], cutoff: int,
                  keep: Callable[[str, str], bool]
                  ) -> tuple[dict[str, int], dict[tuple[str, str], int], int]:
    """How often each owned file changed, how often each pair `keep` accepts changed in one
    commit, and how many mass commits were skipped. ONE count for `coupling` (pairs across
    blocks) and `seams` (pairs inside one): the two differ only in which pairs they keep,
    so a mass cutoff or a share can never mean one thing in one command and another in the
    other."""
    changes: dict[str, int] = {}
    together: dict[tuple[str, str], int] = {}
    skipped = 0
    for files in sets:
        files = {f for f in files if f in owned}
        if not files:
            continue
        if len(files) > cutoff:
            skipped += 1
            continue
        for f in files:
            changes[f] = changes.get(f, 0) + 1
        ordered = sorted(files)
        for i, a in enumerate(ordered):
            for b in ordered[i + 1:]:
                if keep(a, b):
                    together[(a, b)] = together.get((a, b), 0) + 1
    return changes, together, skipped


def coupling_pairs(owned: dict[str, list[str]], sets: list[set[str]], cutoff: int,
                   min_together: int, min_share: float,
                   hub_at: int) -> tuple[list[dict], list[tuple[str, set[str]]], int]:
    """Cross-block pairs above the thresholds, the hub files, and the number of mass commits skipped."""
    # the same block reads both: not a seam between blocks
    changes, together, skipped = joint_changes(
        owned, sets, cutoff, lambda a, b: not set(owned[a]) & set(owned[b]))
    partners: dict[str, set[str]] = {}
    for (a, b), n in together.items():
        if n >= min_together:
            partners.setdefault(a, set()).update(owned[b])
            partners.setdefault(b, set()).update(owned[a])
    hubs = {f for f, bl in partners.items() if len(bl) >= hub_at}
    pairs = []
    for (a, b), n in together.items():
        if n < min_together or a in hubs or b in hubs:
            continue
        share_a, share_b = n / changes[a], n / changes[b]
        if max(share_a, share_b) < min_share:
            continue
        pairs.append({"a": a, "b": b, "blocks_a": owned[a], "blocks_b": owned[b],
                      "together": n, "share_a": share_a, "share_b": share_b})
    pairs.sort(key=lambda p: (-p["together"], -max(p["share_a"], p["share_b"]), p["a"], p["b"]))
    hub_rows = sorted((f, partners[f]) for f in hubs)
    return pairs, hub_rows, skipped


# Which block next: the cost of failure first, the change frequency second. Measured on
# the first project as a prediction (history split in half, ranking on the first half,
# fixes counted on the second): the top 10% of files by change frequency collected 34% of
# the later fixes, by size 29%, at random 6% — the same as the literature (Nagappan & Ball
# 2005; Moser et al. 2008; Graves et al. 2000). Frequency catches defects; the cost of
# failure catches IRREVERSIBILITY (access, money, the write path), so it stays the first
# key: `risk` on the block (the severity vocabulary), and without it the declared order
# of the blocks is the risk statement.
def block_risk(b: dict) -> int:
    r = b.get("risk")
    if r is None:
        return len(SEVERITIES)  # not stated: after every stated one, in declared order
    if r not in SEVERITIES:
        die(f"blocks.json: block {b['id']}: risk must be one of {', '.join(SEVERITIES)}, not `{r}`")
    return SEVERITIES.index(r)


def block_churn(owned: dict[str, list[str]], sets: list[set[str]], cutoff: int) -> dict[str, tuple[int, int]]:
    """Per block: how many commits touched at least one of its files, and how many of its
    files were touched at all. Mass commits are skipped as in `coupling`."""
    commits: dict[str, int] = {}
    files: dict[str, set[str]] = {}
    for fs in sets:
        fs = {f for f in fs if f in owned}
        if not fs or len(fs) > cutoff:
            continue
        touched: set[str] = set()
        for f in fs:
            for bid in owned[f]:
                touched.add(bid)
                files.setdefault(bid, set()).add(f)
        for bid in touched:
            commits[bid] = commits.get(bid, 0) + 1
    return {bid: (commits.get(bid, 0), len(files.get(bid, ()))) for bid in set(commits) | set(files)}
