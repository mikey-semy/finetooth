"""Checks of the review's state against its definition: records, statuses, manifests, stamps."""

from __future__ import annotations

import datetime as dt

from ..git import ROOT
from ..workspace import CLI
from ..model import MANIFEST_MIN_CHARS, POST_VERIFY, STALE_RUNNING_HOURS, STATUSES
from ..blocks import block_index, changed_since_review, hypotheses_sha, manifest_path, refs_sha
from ..gates import Refusals


def state_matches_definition(defn: dict, st: dict, rows: list[dict], gates: Refusals) -> None:
    """Every block of the definition has a state record, and every record a block and a known status."""
    idx = block_index(defn)
    # state and definition agree
    for bid in idx:
        if bid not in st["blocks"]:
            gates.refuse("state/no-record", f"{bid}: no record in state.json — run `{CLI} init`")
    for bid in st["blocks"]:
        if bid not in idx:
            gates.refuse("state/block-not-in-definition",
                         f"{bid}: present in state.json but missing from blocks.json")
        # `set-status` checked the vocabulary, but nobody checked what was written in by hand.
        status = st["blocks"][bid].get("status")
        if status not in STATUSES:
            gates.refuse("state/status-unknown",
                         f"{bid}: status '{status}' is not in the vocabulary — written in past set-status")


def phases_in_order(defn: dict, st: dict, rows: list[dict], gates: Refusals) -> None:
    """Phases in the blocks array do not decrease: the array order is the execution order."""
    # Array order is execution order, and the phases must not decrease: a phase-3 block
    # written in between the first and the second, `next` hands out ahead of time, and
    # nobody notices.
    prev = None
    for b in defn["blocks"]:
        ph = b.get("phase")
        if prev is not None and ph is not None and ph < prev:
            gates.refuse(
                "blocks/phase-order",
                f"{b['id']}: phase {ph} comes after phase {prev} — the blocks array is ordered by "
                f"phase, because that is the execution order"
            )
        prev = ph if ph is not None else prev


def blocked_has_note(defn: dict, st: dict, rows: list[dict], gates: Refusals) -> None:
    """A blocked block says what it is waiting for."""
    # A blocked block without a note is a block about which, a week later, nobody can say
    # what it is waiting for.
    for bid, s in st["blocks"].items():
        if s.get("status") == "blocked" and not (s.get("note") or "").strip():
            gates.refuse("state/blocked-without-note",
                         f"{bid}: blocked without a note — waiting for what? `{CLI} set-status {bid} blocked --note '...'`")


def manifests_present(defn: dict, st: dict, rows: list[dict], gates: Refusals) -> None:
    """A block that got to work has a manifest with something in it."""
    idx = block_index(defn)
    # The manifest is asked only of a block that GOT to work: the manifest is written
    # before its block, and demanding it of all at once fails the check always — then it
    # stops being a gate and starts being ignored.
    for bid, b in idx.items():
        if st["blocks"].get(bid, {}).get("status", "todo") == "todo":
            continue
        manifest = manifest_path(b)
        if not manifest.exists():
            gates.refuse("manifest/missing", f"{bid}: no manifest {manifest.relative_to(ROOT)}")
        elif len(manifest.read_text(encoding="utf-8").strip()) < MANIFEST_MIN_CHARS:
            # An empty file passed the "manifest exists" check.
            gates.refuse("manifest/too-short",
                         f"{bid}: manifest {manifest.relative_to(ROOT)} is empty or nearly empty")


def declared_reports_exist(defn: dict, st: dict, rows: list[dict], gates: Refusals) -> None:
    """Reports state.json declares are on disk."""
    # declared reports exist
    for bid, s in st["blocks"].items():
        for r in s.get("reports", []):
            if not (ROOT / r).exists():
                gates.refuse("report/declared-missing",
                             f"{bid}: state.json declares report {r}, which is not on disk")


def running_not_stale(defn: dict, st: dict, rows: list[dict], gates: Refusals) -> None:
    """A running block has a start time, and it is not a session that died."""
    # a session that died mid-block
    for bid, s in st["blocks"].items():
        if s.get("status") == "running" and not s.get("started"):
            gates.refuse("state/running-without-timestamp",
                         f"{bid}: stuck in running without a timestamp — when it started is unknown")
        if s.get("status") == "running" and s.get("started"):
            try:
                started = dt.datetime.strptime(s["started"], "%Y-%m-%dT%H:%M:%SZ").replace(
                    tzinfo=dt.timezone.utc
                )
            except ValueError:
                gates.refuse("state/timestamp-unparsable",
                             f"{bid}: timestamp '{s['started']}' cannot be parsed")
                continue
            hours = (dt.datetime.now(dt.timezone.utc) - started).total_seconds() / 3600
            if hours > STALE_RUNNING_HOURS:
                gates.refuse(
                    "state/running-too-long",
                    f"{bid}: stuck in running for {hours:.0f} h — the session probably died; restart the block"
                )


def reviewed_code_unchanged(defn: dict, st: dict, rows: list[dict], gates: Refusals) -> None:
    """A block past verification is closed on the code it was reviewed on."""
    # A block reviewed on another version of the files is closed only on paper. The
    # fingerprint is taken on the move to verified/closed; it can diverge in one way only —
    # the block's files changed after the review.
    for b in defn["blocks"]:
        s = st["blocks"].get(b["id"], {})
        if s.get("status") not in POST_VERIFY:
            continue
        if not s.get("reviewed_sha"):
            # Skipping silently is not allowed: then any edit to such a block's files passes
            # unnoticed while the check stays green. That was the case for every block
            # verified before the fingerprint appeared.
            gates.refuse(
                "state/no-reviewed-fingerprint",
                f"{b['id']}: block in status {s.get('status')} without a fingerprint of what was reviewed — "
                f"edits to its files are not tracked; `{CLI} backfill` or `{CLI} restamp {b['id']}`"
            )
            continue
        if changed_since_review(b, s["reviewed_sha"]):
            gates.refuse(
                "state/files-changed",
                f"{b['id']}: block files changed after the review — the block is closed on another "
                f"version of the code; re-run it or, if the edits do not concern the block's subject, "
                f"re-stamp: `{CLI} restamp {b['id']}`"
            )
        # Context is a warning, not a refusal, like doorstop's "suspect link": what changed
        # is not the block's subject but what it leaned on. Reference directories are wide
        # (in the first project — 229 files and a dozen commits in two weeks), and a refusal
        # on each of their edits would go red daily, training people to hit `restamp`
        # without looking — then the fingerprint of the block's own files stops working too.
        if b.get("ref_paths"):
            if not s.get("refs_sha"):
                gates.warn("state/no-refs-fingerprint",
                           f"{b['id']}: no context fingerprint (ref_paths) — `{CLI} backfill`")
            elif s["refs_sha"] != refs_sha(b):
                gates.warn(
                    "state/refs-changed",
                    f"{b['id']}: context files (ref_paths) changed after verification — "
                    f"if the block's conclusions leaned on them, re-check; otherwise `{CLI} restamp {b['id']}`"
                )
        if not s.get("hypotheses_sha"):
            gates.refuse(
                "state/no-hypotheses-fingerprint",
                f"{b['id']}: no hypotheses fingerprint — an edit of the manifest after verification is not "
                f"tracked; `{CLI} backfill`"
            )
        elif s["hypotheses_sha"] != hypotheses_sha(b):
            gates.refuse(
                "state/hypotheses-changed",
                f"{b['id']}: manifest hypotheses changed after verification — the verdicts by "
                f"number were given to the previous questions; re-check the new ones or, if the "
                f"meaning did not change, re-stamp: `{CLI} restamp {b['id']}`"
            )
