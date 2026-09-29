"""Importing a block's draft into the register, and its dry run."""

from __future__ import annotations

import re
from pathlib import Path

from .base import now
from .git import ROOT, all_files
from .workspace import CLI
from .model import CLAIM_MAX, SCENARIO_MAX
from .fingerprint import CODE_FINGERPRINT_FIELDS, code_fingerprint, put_fingerprint
from .blocks import block_index, blocks
from .register import (
    file_problem, finding_file, finding_id, finding_number, findings, unimported_rows,
)
from .gates import Refusals, finding_gates


class ImportRefused(Exception):
    """`import` does not take the draft; the message names why and the way out."""


class ImportWouldReplace(ImportRefused):
    """The plain `import` would erase or overturn what the register holds of the block."""


def import_plan(block: str, name: str, numbered: list[tuple[int, dict]], existing: list[dict],
                *, append: bool, force: bool, found_in: dict | None = None,
                hold_rows: bool = True, refused: list[tuple[int, str]] | None = None,
                ) -> tuple[list, list[dict], list[dict]]:
    """What `import` writes, computed without writing it: (the rows of the block's file after
    the import, the register after it, the rows of the register that are new or rewritten).
    Raises ImportRefused where `import` refuses. ONE place: `import` writes what this returns,
    and `import --dry-run` asks `check`'s gates (`finding_gates`) of the same rows, so the dry
    run sees the defaults `import` fills in and the rejection it normalises — asked of the row
    as written, a `"confidence": null` or a `rejected` confidence with no reason passed the
    dry run and was refused by `check` a minute later (fix review of the 0.8.0 candidate).
    `hold_rows=False` is the dry run's: `check` holds the same two limits and the same rule
    for `file` (`file_problem`, the empty-field gate) and names every row that breaks them,
    where `import` stops at the first.

    `refused` is the dry run's too: a refusal that belongs to a row — an id numbered for
    another block, an id two rows carry — is added to it as (line, message) instead of
    raised, and the row is planned as it will be once fixed, without that id. Raised, the
    first such refusal stopped the dry run before a single row was asked (Codex on #66): a
    draft with two equal ids and a bad severity took two runs to fix."""
    line_of = {id(row): n for n, row in numbered}
    incoming = []
    for n, row in numbered:
        # The limits `check` holds are held here too: a draft that `import` accepted and
        # `check` then refused made every later gate red on a row nobody could fix through
        # the tool (the kit's own review hit it three times).
        for field, limit in (("claim", CLAIM_MAX), ("scenario", SCENARIO_MAX)):
            if hold_rows and len(str(row.get(field) or "")) > limit:
                raise ImportRefused(
                    f"{name} line {n}: {field} is {len(str(row[field]))} characters against a "
                    f"limit of {limit} — shorten it in the draft; the evidence belongs in the report")
        # So is the file, in the words of `check`: a row whose `file` is written but is not
        # a path went into the register, and every command that read it after that died
        # with a traceback or `check` refused a record the lead could fix only by hand. A row
        # with no `file` key at all is left as before — `check` names the empty field.
        if hold_rows and "file" in row:
            why = file_problem(row) or ("field file is empty — `check` refuses a finding without it"
                                        if not finding_file(row).strip() else None)
            if why:
                raise ImportRefused(f"{name} line {n}: {why}; `{CLI} import {block} --dry-run` "
                                    f"lists every problem of the draft at once")
        incoming.append(row)

    # A row numbered for ANOTHER block (`V2-001` in the file of H1) is refused on every
    # path: the top-up skipped it silently as "already known", and the plain import would
    # file it under this block with a foreign number (the kit author's review, 24.09).
    other = [f for f in incoming
             if isinstance(f.get("id"), str) and (m := re.fullmatch(r"(.+)-(\d+)", f["id"]))
             and m.group(1) != block]
    if other and refused is None:
        raise ImportRefused(
            f"{name}: rows numbered for another block — {', '.join(f['id'] for f in other)}; "
            f"a block's file holds that block's findings only: remove the rows or import them "
            f"with their own block")
    for f in other:
        refused.append((line_of[id(f)], f"id {f.pop('id')} is numbered for another block — a "
                        f"block's file holds that block's findings only: remove the row or import "
                        f"it with its own block"))

    if append:
        # TOP-UP IMPORT: findings found on top of what is already recorded. The regular
        # import replaces the block's findings wholesale, and for a block where part is
        # already fixed that would erase the fix marks — a neighbouring project got burnt
        # by this and started a separate consolidator. Here we only append, with the
        # block's next free numbers.
        taken = [n for f in existing if f.get("block") == block
                 and (n := finding_number(block, f.get("id"))) is not None]
        next_n = max(taken, default=0) + 1
        added = []
        # After the previous import the block's file holds the already recorded findings
        # with their numbers — the top-up appends new lines to it. What is recorded is
        # skipped: the register knows more about it (status, fix), and the block's file
        # does not override it. "Recorded" is decided in one place, `unimported_rows`, which
        # `set-status` and `check` ask too.
        for f in unimported_rows(incoming, existing):
            f.setdefault("block", block)
            if f["block"] != block:
                raise ImportRefused(f"the top-up file holds a finding of another block {f['block']} "
                                    f"— the import is stopped")
            f["id"] = finding_id(block, next_n)
            next_n += 1
            f.setdefault("status", "open")
            f.setdefault("confidence", "plausible")
            f.setdefault("fix_commit", None)
            f.setdefault("dup_of", None)
            if found_in:
                f["found_in"] = dict(found_in)
            f["imported_at"] = now()
            put_fingerprint(f, code_fingerprint(finding_file(f), f.get("line"))
                            or {"code_sha": None})
            added.append(f)
        return incoming, existing + added, added

    mine = [f for f in existing if f.get("block") == block]
    if mine and not force:
        # The plain import REPLACES the block's set with the file. A finding can be recorded
        # against the block before its pass — handed over by another block's fixer, left by
        # an earlier pass — and replacing wiped it: its id went to the hunter's new finding
        # and `check` stayed green (the kit author's register: 26 such rows in 15 unstarted
        # blocks). So the plain import refuses when the file would ERASE a recorded row or
        # OVERTURN a recorded decision; the file may still change a decision nobody stamped
        # — that is its own, not somebody else's.
        in_file = {f.get("id"): f for f in incoming if f.get("id")}
        missing = [f["id"] for f in mine if f.get("id") and f["id"] not in in_file]
        overturned = []
        for f in mine:
            g = in_file.get(f.get("id"))
            if g is None:
                continue
            stamped = bool(f.get("updated_at") or f.get("restamped_at"))
            decided = f.get("status") not in ("open", "rejected")
            if (stamped or decided) and any(
                    (g.get(k) or None) != (f.get(k) or None)
                    for k in ("status", "dup_of", "fix_commit", "defer_reason", "reject_reason")):
                overturned.append(f["id"])
        if missing or overturned:
            parts = []
            if missing:
                parts.append(f"recorded but not in the file: {', '.join(missing)}")
            if overturned:
                parts.append(f"decided in the register, decided otherwise in the file: {', '.join(overturned)}")
            raise ImportWouldReplace(
                f"block {block}: the plain import would replace what is recorded — "
                f"{'; '.join(parts)}. Add the new findings with `{CLI} import {block} --append` "
                f"(what is recorded stays, new rows get the next free numbers), or replace the "
                f"whole set deliberately with --force")

    kept = [f for f in existing if f.get("block") != block]
    before = {f["id"]: f for f in mine if f.get("id")}
    # Ids used to be handed out by POSITION in the file, so a finding inserted ABOVE the
    # numbered rows took an id that already existed: the register then held two H1-001,
    # `check` said "duplicate id" and named no way out, and `set-finding` reached only the
    # first of them. A number is taken from the free ones — never from the count of rows,
    # and never one that a record of this block already carries, even a retired one: that
    # id is quoted in the journal, in a commit message and in another block's report.
    taken = {f["id"] for f in incoming if f.get("id")} | set(before)
    seen_here: set[str] = set()
    for f in incoming:
        fid = f.get("id")
        if fid and fid in seen_here:
            why = (f"two rows carry the id {fid} — an id is unique within a block; delete the "
                   f"id field of the row that is new and the import will hand out a free number")
            if refused is None:
                raise ImportRefused(f"{name}: {why}")
            refused.append((line_of[id(f)], why))
            del f["id"]
            continue
        if fid:
            seen_here.add(fid)
    numbered_ids = [n for fid in taken if (n := finding_number(block, fid)) is not None]
    next_n = max(numbered_ids, default=0) + 1
    for f in incoming:
        f.setdefault("block", block)
        if not f.get("id"):
            f["id"] = finding_id(block, next_n)
            next_n += 1
        f.setdefault("status", "open")
        f.setdefault("confidence", "plausible")
        f.setdefault("fix_commit", None)
        f.setdefault("dup_of", None)
        f["imported_at"] = now()
        # Fingerprint of the code the finding talks about. The register goes stale faster
        # than it seems: a finding gets fixed, the status is not moved, and the next pass
        # argues with a description of code that no longer exists. That is what happened —
        # two verifiers independently "refuted" two findings closed the day before. The
        # fingerprint turns that from an argument into a question.
        #
        # A repeated import does NOT re-take the fingerprint of an already known finding:
        # otherwise it would silently declare the current code to match the description,
        # and a stale finding would vanish from `check` without re-verification. To confirm
        # it on the new code — `restamp <ID>`. A finding that moved to another file is a
        # new claim, and the fingerprint is new.
        #
        # A region fingerprint is carried WITH its line: the two are one anchor, and the
        # register's line may already be the one `restamp` moved it to while the block's
        # file still cites where it was when the hunter wrote it.
        prev = before.get(f["id"])
        if (prev and finding_file(prev) == finding_file(f)
                and (prev.get("code_sha") or prev.get("region_sha"))):
            put_fingerprint(f, {k: prev[k] for k in CODE_FINGERPRINT_FIELDS if k in prev})
            if prev.get("region_sha") and "line" in prev:
                f["line"] = prev["line"]
        else:
            put_fingerprint(f, code_fingerprint(finding_file(f), f.get("line"))
                            or {"code_sha": None})
        if f.get("confidence") == "rejected":
            f["status"] = "rejected"
    return incoming, kept + incoming, incoming


def import_dry_run(block: str, src: Path, numbered: list[tuple[int, dict]],
                   unreadable: list[tuple[int, str]], *, append: bool, force: bool,
                   found_in: dict | None) -> int:
    """`import --dry-run`: the role's own check of its draft before it hands it in. A verifier
    draft with a claim past the limit had the whole block refused at import, and a rejection
    with no reason turned `check` red — both found by the lead, after the role was gone (#46).

    Not a second copy of the rules: the draft goes through `import_plan` — what `import`
    would write, defaults filled in, ids handed out — and every row it would write is asked
    `check`'s own gates (`finding_gates`) against the register it would leave. Every row is
    named at once; nothing is written, not the register, not the draft.

    One refusal of `import` is not the draft's to fix: whether a plain import may replace
    what the register already holds of the block is the lead's call at import time
    (`--append` or `--force`). It is named as a note, and the rows are asked as `--append`
    would write them — the path SKILL.md gives a draft that holds only new findings on top of
    recorded ones."""
    rel = src.relative_to(ROOT)
    # (line, message); 0 for a message about the file as a whole.
    problems: list[tuple[int, str]] = list(unreadable)
    # A row whose `block` names another block: the plain import would file it there without
    # a word.
    for n, row in numbered:
        if row.get("block") not in (None, block):
            problems.append((n, f"`block` is {row['block']!r} — this is the draft of {block}"))
            # Asked below as it will be once fixed: named once here, not again by `check`
            # as a nonexistent block, nor by the top-up plan as a refusal of the whole file
            # that left every other row unasked.
            row["block"] = block
    rows = numbered
    line_of = {id(row): n for n, row in rows}
    note = ""
    # ONE list across both plans: the first may record a row's refusal and drop the id it
    # was about before it raises ImportWouldReplace, and the second plan no longer sees it.
    refused: list[tuple[int, str]] = []
    try:
        try:
            _, merged, new = import_plan(block, src.name, rows, findings(), append=append,
                                         force=force, found_in=found_in, hold_rows=False,
                                         refused=refused)
        except ImportWouldReplace as exc:
            note = str(exc)
            _, merged, new = import_plan(block, src.name, rows, findings(), append=True,
                                         force=force, found_in=found_in, hold_rows=False,
                                         refused=refused)
    except ImportRefused as exc:
        problems.append((0, f"`import` refuses the file as a whole — {exc}; the rows are "
                            f"checked once it takes the file"))
    else:
        asked = {id(f) for f in new}
        idx, tracked, seen = block_index(blocks()), all_files(), set()
        for f in merged:
            if id(f) not in asked:
                # A row the import leaves as it is: not the draft's to answer for, but its
                # id is taken, which the duplicate-id gate asks of the rows after it.
                seen.add(f.get("id", "<no id>"))
                continue
            gates = Refusals()
            finding_gates(gates, f, merged, idx, tracked, seen)
            # `check` names the finding by the id `import` would give it; the draft's author
            # knows the row by its line.
            own = f"finding {f.get('id')}: "
            problems += [(line_of[id(f)], m.removeprefix(own)) for m in gates.problems]
    problems += refused
    if note:
        print(f"note, the lead's call at import time: {note}; the rows are checked as "
              f"`--append` would write them")
    if problems:
        print(f"{rel}: {len(problems)} problem(s) — fix them in the draft and run this again "
              f"(the messages are `import`'s and `check`'s after it; fix the row in the draft):")
        # By line, so a row's problems stand together whichever check named them.
        for n, why in sorted(problems, key=lambda p: p[0]):
            print(f"  line {n}: {why}" if n else f"  {why}")
        return 1
    print(f"{rel}: {len(numbered)} row(s), nothing `import` or `check` would refuse"
          + (" in the rows" if note else ""))
    return 0
