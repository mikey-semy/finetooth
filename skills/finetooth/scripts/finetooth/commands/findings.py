"""Commands on the register: findings, set-finding, import, restamp, backfill, roots, refs,
hypotheses."""

from __future__ import annotations

import json

from ..base import die, now
from ..git import ROOT, git
from ..workspace import CLI, FINDINGS_FILE, FINDINGS_MD, STATE_FILE, named_file, save_json
from ..model import CONFIDENCE, FINDING_STATUS, HYPOTHESIS_HEADING, POST_VERIFY, SEVERITIES
from ..i18n import T
from ..text import section_items
from ..fingerprint import code_fingerprint, put_fingerprint
from ..blocks import (
    block_findings_path, block_index, block_sha, blocks, hypotheses_sha, manifest_path,
    refs_sha, stamp, state,
)
from ..register import (
    ROOT_RULE_AT, draft_rows, dup_problem, finding_file, findings, render_findings_md,
    restamp_finding, root_guards, roots_of, rule_problem, shown_lines,
)
from ..verdicts import hypotheses, verdicts_for
from ..journal import journal, pinned_range
from ..importing import ImportRefused, import_dry_run, import_plan
from ..refs import review_refs


def cmd_refs(args) -> int:
    """References to the review's findings in the code — they must not outlive the review."""
    hits = review_refs()
    if not hits:
        print("no finding of the register is named outside docs/review/")
        return 0
    for path, num, fid, text in hits:
        print(f"{path}:{num}: {fid} — {text[:120]}")
    print(f"\n{len(hits)} reference(s) to findings outside docs/review/ — the ids die with the "
          f"review directory: say the reason in the code's own words, the id stays in the register")
    return 1


def cmd_import(args) -> int:
    """Take a block's finished findings file into the single register."""
    defn = blocks()
    idx = block_index(defn)
    if args.block not in idx:
        die(f"unknown block {args.block}")
    src = block_findings_path(idx[args.block])
    if not src.exists():
        die(f"no findings file for the block: {src.relative_to(ROOT)}")
    # Which fix review found the new rows: the loop signal reads it. Written by the tool from
    # the command the fix reviewer's template assembles, not by a human — the leads of the
    # kit's own review appended "(fix review round N, RN-00M)" to the claim by hand, and a
    # claim is prose nothing can read back.
    found_in = None
    if (args.round is None) != (args.diff is None):
        die("--round and --diff go together: the fix review round that found the findings "
            "and the diff it read, as the fix reviewer's prompt names them")
    if args.round is not None:
        if not args.append:
            die("--round/--diff mark findings a fix review added on top of the register — "
                f"they go with --append: `{CLI} import {args.block} --append --round N --diff <range>`")
        if args.round < 1:
            die(f"--round {args.round}: rounds are counted from 1")
        pinned = pinned_range(args.diff)
        if not pinned:
            die(f"--diff {args.diff}: not a commit range git can resolve — name it as "
                f"`A..B` or `A...B`; the loop signal reads the lines that range changed, and "
                f"a diff against the working tree changes under it")
        found_in = {"role": "fixreview", "round": args.round, "diff": pinned}

    numbered, unreadable = draft_rows(src)
    if args.dry_run:
        return import_dry_run(args.block, src, numbered, unreadable, append=args.append,
                              force=args.force, found_in=found_in)
    if unreadable:
        die(f"{src.name}: " + "; ".join(f"line {n}: {why}" for n, why in unreadable)
            + f" — nothing is imported; `{CLI} import {args.block} --dry-run` lists every "
              f"problem of the draft at once")
    try:
        incoming, merged, new = import_plan(args.block, src.name, numbered, findings(),
                                            append=args.append, force=args.force,
                                            found_in=found_in)
    except ImportRefused as exc:
        die(str(exc))
    if args.append:
        # The numbers are written back into the block's file — as with the regular import.
        # A repeated run recognises them and appends nothing; renaming the file as
        # "consolidated" is unnecessary, and that rename used to carry the whole block's
        # file away.
        with FINDINGS_FILE.open("a", encoding="utf-8") as fh:
            for f in new:
                fh.write(json.dumps(f, ensure_ascii=False) + "\n")
        src.write_text(
            "\n".join(json.dumps(f, ensure_ascii=False) for f in incoming) + "\n",
            encoding="utf-8",
        )
        print(f"{args.block}: appended {len(new)} findings (top-up import)")
        print(f"do not forget: {CLI} findings && {CLI} check")
        return 0
    # Write the assigned ids back into the block's own file. Ids are handed out by
    # POSITION, so without this a finding appended later — one the fixer turned up
    # while working — would renumber everything under it on the next import, and
    # every id already quoted in the journal, in a commit message and in another
    # block's report would start pointing at a different defect.
    src.write_text(
        "\n".join(json.dumps(f, ensure_ascii=False) for f in incoming) + "\n",
        encoding="utf-8",
    )
    with FINDINGS_FILE.open("w", encoding="utf-8") as fh:
        for f in merged:
            fh.write(json.dumps(f, ensure_ascii=False) + "\n")
    live = sum(1 for f in incoming if f.get("status") == "open")
    print(f"{args.block}: imported {len(incoming)} records, {live} of them open")
    print(f"do not forget: {CLI} findings && {CLI} check")
    return 0


def cmd_set_finding(args) -> int:
    """Move a finding: fixed, rejected, duplicate, deferred — and record the verifier's
    severity and confidence on it (`--severity`, `--confidence`).

    The rule "findings.jsonl is edited only by the tool" rested on the agent's own word:
    the kit had no command that sets `fixed` and the fix commit — the register was edited
    by hand, and by hand one sets both `fixed` without a commit and `rejected` without a
    reason. Here the move passes the same checks as `check`, and the file is regenerated
    together with the record.
    """
    if len(args.finding) > 1 and args.dup_of:
        die("--dup-of takes one finding: several cannot meaningfully share the same duplicate target")
    # The verifier's verdict on a finding already in the register — "real, but medium, not
    # high" — had no way in: the template sent it to the lead as a table for `set-finding`,
    # and `set-finding` moved the status only, so the register kept the hunter's severity and
    # the fix gate counted findings the verifier had lowered (the gate-3 run of 0.8.0). The
    # values are the ones `import` and `check` accept, and the refusal names them.
    if args.severity is not None and args.severity not in SEVERITIES:
        die(f"--severity {args.severity}: unknown; known: {', '.join(SEVERITIES)}")
    if args.confidence is not None and args.confidence not in CONFIDENCE:
        die(f"--confidence {args.confidence}: unknown; known: {', '.join(CONFIDENCE)}")
    # A rejection is a verdict held by two fields (see set_one_finding); `--confidence` that
    # sets one without the other would write the contradiction `check` refuses.
    if args.confidence == "rejected" and args.status != "rejected":
        die(f"--confidence rejected with status `{args.status}` — a rejected finding is moved "
            f"with its reason: `{CLI} set-finding <ID> rejected --reason '…'`")
    if args.status == "rejected" and args.confidence not in (None, "rejected"):
        die(f"status `rejected` with --confidence {args.confidence} — a finding cannot be "
            f"rejected and {args.confidence} at once; drop --confidence or the rejection")
    rows = findings()
    for fid in args.finding:
        set_one_finding(args, rows, fid)
    with FINDINGS_FILE.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    FINDINGS_MD.write_text(render_findings_md(rows), encoding="utf-8")
    return 0


def set_one_finding(args, rows: list[dict], fid: str) -> None:
    hit = [f for f in rows if f.get("id") == fid]
    if not hit:
        die(f"finding {fid} is not in the register")
    f = hit[0]
    if args.rule and getattr(args, "clear_rule", False):
        die("--rule and --clear-rule together — record a guard or remove it, not both")
    if args.status not in FINDING_STATUS:
        die(f"unknown status {args.status}; known: {', '.join(FINDING_STATUS)}")
    # A finding already fixed keeps its commit: recording a guard on it later (`--rule`) names
    # its current status, and demanding `--commit` again would make one command overwrite the
    # different fix commits of several findings with one.
    already_fixed = f.get("status") == "fixed" and f.get("fix_commit")
    if args.status == "fixed" and not (args.commit or already_fixed):
        die("`fixed` without a fix commit — nothing confirms the defect is closed (--commit)")
    if args.status == "rejected" and not (args.reason or f.get("reject_reason")):
        die("`rejected` without a reject reason — the next review will find the same thing (--reason)")
    if args.status == "duplicate" and not (args.dup_of or f.get("dup_of")):
        die("`duplicate` without saying what exactly it duplicates (--dup-of)")
    if args.status == "deferred" and not (args.reason or f.get("defer_reason")):
        die("`deferred` without a reason — a deferred finding does not count as open and without "
            "a reason survives the whole review unnoticed (--reason)")
    if args.dup_of and (why := dup_problem(fid, args.dup_of, rows)):
        die(why)
    if args.rule and (why := rule_problem(args.rule)):
        die(why)
    # A fix does not have to touch the file where the defect shows: a route is fixed in the
    # shared guard. The place of the fix is named explicitly, not implied — otherwise the
    # check "the commit touches the finding's file" stops telling a fix made elsewhere from
    # a mark that belongs to another finding.
    for path in args.fixed_in or []:
        if not named_file(path):
            die(f"--fixed-in {path}: no such file in the repository")

    # A rejection is a verdict, and it lives in two fields: the status says what is done
    # with the finding, the confidence — what was decided about it. Changing one without
    # the other, the register would claim "rejected" and "confirmed" at once. Returning a
    # rejected finding to work means lifting the verdict: it waits for verification again
    # rather than inheriting "rejected".
    if args.status == "rejected":
        f["confidence"] = "rejected"
    elif f.get("status") == "rejected" and f.get("confidence") == "rejected":
        f["confidence"] = "plausible"
    if args.confidence:
        f["confidence"] = args.confidence
    if args.severity:
        f["severity"] = args.severity
    f["status"] = args.status
    if args.commit:
        f["fix_commit"] = args.commit
    if args.reason:
        f["defer_reason" if args.status == "deferred" else "reject_reason"] = args.reason
    if args.dup_of:
        f["dup_of"] = args.dup_of
    if args.fixed_in:
        f["fixed_in"] = sorted(set(f.get("fixed_in", [])) | set(args.fixed_in))
    if args.rule:
        # The guard is recorded on the NAMED finding only (issue #28). It used to go onto every
        # finding sharing the root — "the class is closed as a whole or not at all" — and one
        # root string turned out to carry defects that need different guards: three fixers in
        # one day rewrote the guards of other blocks' findings, fixed ones included, with tests
        # that stay green on those findings' own defects, and none of those rows got a new
        # `updated_at`. A guard is a claim about an instance; whoever records it names the
        # instances it goes red on, and `roots` shows a root whose instances disagree.
        f["rule"] = args.rule
    if getattr(args, "clear_rule", False):
        # A guard recorded on a finding it does not hold has to be removable: the self-review
        # measured a guard that stays green on its finding's defect, and without a way to clear
        # it the register kept asserting the class held (issue #28, T4-009).
        f.pop("rule", None)
    f["updated_at"] = now()

    print(f"{fid}: {args.status}")


def cmd_findings(args) -> int:
    defn, rows = blocks(), findings()
    live = [f for f in rows if f.get("status") == "open"]
    FINDINGS_MD.write_text(render_findings_md(rows), encoding="utf-8")
    print(f"findings.md regenerated: {len(live)} open, {len(rows)} total")
    for b in defn["blocks"]:
        n = sum(1 for f in rows if f.get("block") == b["id"] and f.get("status") == "open")
        if n:
            print(f"  {b['id']:<4} {n}")
    return 0


def cmd_restamp(args) -> int:
    """Confirm that the changes in the block's files were reviewed, and re-take the fingerprint.

    Exactly like `doorstop review`: not "switch the check off", but say on record that the
    new text was seen. That is why the command demands the block by name and prints what
    exactly it stamps.
    """
    defn, st = blocks(), state()
    idx = block_index(defn)
    if args.block not in idx:
        return restamp_finding(args.block, args.line, args.file)
    if args.line is not None or args.file is not None:
        flag = "--line" if args.line is not None else "--file"
        die(f"{flag} belongs to a finding, not to a block: {args.block} is a block — its "
            f"fingerprint covers all its files, there is no line to anchor")
    s = st["blocks"].get(args.block, {})
    if s.get("status") not in POST_VERIFY:
        die(f"{args.block} is in status {s.get('status', 'todo')} — nothing to stamp")
    was = {k: s.get(k) for k in ("reviewed_sha", "refs_sha", "hypotheses_sha")}
    stamp(idx[args.block], s)
    # Nothing moved — nothing to record. A stamp re-taken over the same fingerprints would
    # dirty state.json on a correct state, the same way `init` used to.
    if all(was[k] == s.get(k) for k in was) and all(was.values()):
        print(f"{args.block}: fingerprints already match the current files — nothing to stamp")
        return 0
    s["restamped_at"] = now()
    st["updated_at"] = now()
    save_json(STATE_FILE, st)
    print(f"{args.block}: fingerprint re-taken — changes in the block's files count as reviewed")
    return 0


def cmd_roots(args) -> int:
    """Roots: how many instances each has and which guard each instance is recorded under."""
    rows = findings()
    groups = roots_of(rows, args.block)
    line_of = shown_lines()
    if not groups:
        print("no roots recorded — the `root` field of the findings is not filled in")
        return 0
    for root, items in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        guards = root_guards(items)
        named = [g for g in guards if g]
        if not named:
            mark = "NO GUARD" if len(items) >= ROOT_RULE_AT else "no guard, but few repeats"
        elif len(guards) == 1:
            mark = f"guard: {named[0]}"
        else:
            # Several guards, or a guard on only part of the instances: neither is "the
            # root's guard". Said outright, with who carries what, so that nobody reads the
            # class as closed by a test that was recorded on one of its instances.
            unguarded = len(guards.get("", []))
            mark = ("GUARDS DIFFER" + (f", {unguarded} of {len(items)} instances without one"
                                       if unguarded else "")
                    + " — each guard holds only the findings it is recorded on:")
        print(f"  {len(items):>2} × {root}  — {mark}")
        if len(guards) > 1:
            for guard, ids in guards.items():
                print(f"       {guard or 'no guard'} — {', '.join(ids)}")
        for f in items:
            where = finding_file(f)
            if at := line_of(f):
                where += f":{at}"
            print(f"       {f.get('id','?'):<10} {f.get('status','?'):<9} {where}")
    return 0


def cmd_backfill(args) -> int:
    """Stamp fingerprints where they are missing: on blocks past verification and on open findings.

    Fingerprints appeared in the kit later than part of the review was done, and old
    records have none. Without them the freshness check silently skips exactly what is
    oldest. The snapshot is taken from the CURRENT code, not from the one the block was
    reviewed on — so every stamping is written to the journal with the commit: changes
    before this moment are not tracked, and that must be visible, not implied.
    """
    defn, st, rows = blocks(), state(), findings()
    idx = block_index(defn)
    head = git("rev-parse", "--short", "HEAD").out.strip() or "?"
    stamped_blocks, stamped_findings = [], []
    for bid, s in st["blocks"].items():
        if (s.get("status") in POST_VERIFY and bid in idx
                and not all(s.get(k) for k in ("reviewed_sha", "refs_sha", "hypotheses_sha"))):
            b = idx[bid]
            s.setdefault("reviewed_sha", block_sha(b))
            s.setdefault("refs_sha", refs_sha(b))
            s.setdefault("hypotheses_sha", hypotheses_sha(b))
            s["restamped_at"] = now()
            stamped_blocks.append(bid)
    for f in rows:
        if (f.get("status") in ("open", "deferred")
                and not f.get("code_sha") and not f.get("region_sha")):
            fp = code_fingerprint(finding_file(f), f.get("line"))
            if fp:
                put_fingerprint(f, fp)
                stamped_findings.append(f.get("id", "?"))
    if not stamped_blocks and not stamped_findings:
        print("fingerprints are in place — nothing to stamp")
        return 0
    if stamped_blocks:
        st["updated_at"] = now()
        save_json(STATE_FILE, st)
    if stamped_findings:
        with FINDINGS_FILE.open("w", encoding="utf-8") as fh:
            for f in rows:
                fh.write(json.dumps(f, ensure_ascii=False) + "\n")
        FINDINGS_MD.write_text(render_findings_md(rows), encoding="utf-8")
    note = T("backfill_note", head=head, blocks=", ".join(stamped_blocks) or "—", n=len(stamped_findings))
    journal("backfill", note)
    print(note)
    return 0


def cmd_hypotheses(args) -> int:
    """Show the block's hypotheses and their verdicts — what is closed, what hangs."""
    defn = blocks()
    idx = block_index(defn)
    if args.block not in idx:
        die(f"unknown block {args.block}")
    b = idx[args.block]
    manifest = manifest_path(b)
    ids = hypotheses(b["id"], manifest)
    if not ids:
        print(f"{b['id']}: the manifest has no 'Hypotheses' section or it is empty")
        return 1
    seen = verdicts_for(b)
    items = section_items(manifest.read_text(encoding="utf-8"), HYPOTHESIS_HEADING)
    for hid, text in zip(ids, items):
        mark = seen.get(hid, "NO VERDICT")
        print(f"  {hid:<8} {mark:<14} {text[:90]}")
    print(f"\nclosed {sum(1 for h in ids if h in seen)}/{len(ids)}")
    return 0
