"""Command: check — every gate of the review in one pass."""

from __future__ import annotations

import datetime as dt

from ..git import ROOT, all_files, git_files, untracked_files
from ..workspace import CLI, FINDINGS_MD, REVIEW
from ..model import (
    FIX_AGE_DAYS, FIX_PHASE, MANIFEST_MIN_CHARS, POST_VERIFY, PROOFS, READ_LINES_KEY,
    READ_STATUSES, STALE_RUNNING_HOURS, STATUSES, SWEEP_DIR_NAME,
)
from ..i18n import T
from ..text import names_file, section_body, unquoted
from ..blocks import (
    block_findings_path, block_index, block_lines, blocks, changed_since_review, hypotheses_sha,
    manifest_path, read_under_ceiling, readable_lines, refs_sha, state,
)
from ..register import (
    ROOT_RULE_AT, draft_not_imported, findings, findings_md_matches, open_findings_age,
    root_guards, roots_of, rule_problem,
)
from ..verdicts import (
    LIMITS_HEADING, LIMITS_PLACEHOLDER, confirmed_without_finding, finding_ids_for, hypotheses,
    verdict_conflicts, verdict_reports, verdicts_for, verify_report_problem,
)
from ..coverage import (
    ACCEPTANCE_HEADING, SHARED_OWNERS_ADVICE, coverage_map, enumerates_beyond, freshness_inert,
    review_scope, shared_owners, stale_tree, sweep_script,
)
from ..journal import last_review_round, loop_stop
from ..gates import Refusals, finding_gates
from ..refs import review_refs


def cmd_check(args) -> int:
    defn, st, rows = blocks(), state(), findings()
    idx = block_index(defn)
    gates = Refusals()

    # 1. state and definition agree
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
    # A blocked block without a note is a block about which, a week later, nobody can say
    # what it is waiting for.
    for bid, s in st["blocks"].items():
        if s.get("status") == "blocked" and not (s.get("note") or "").strip():
            gates.refuse("state/blocked-without-note",
                         f"{bid}: blocked without a note — waiting for what? `{CLI} set-status {bid} blocked --note '...'`")

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

    # A block declared verified or closed must produce the VERIFIER's report.
    # Otherwise `set-status closed` closes a block with the hunter's report alone,
    # and unverified findings vanish from the remaining work.
    for b in defn["blocks"]:
        stt = st["blocks"].get(b["id"], {}).get("status", "todo")
        if stt in POST_VERIFY:
            rep = REVIEW / "reports" / f"{b['id']}-{b['slug']}.verify.md"
            if not rep.exists():
                gates.refuse(
                    "report/verify-missing",
                    f"{b['id']}: status {stt}, but there is no verifier report — "
                    f"the verification rests on the agent's own word"
                )
            elif why := verify_report_problem(rep, any(f.get("block") == b["id"] for f in rows)):
                gates.refuse("report/verify-weak", f"{b['id']}: {why}")

    # A block past verification whose draft holds rows the register does not: its findings
    # are missing from the summary, findings.md, SARIF and the fix gate, and nothing else here
    # would say so (#42). `set-status` refuses the same on the way in; this catches a block
    # that got there before the rule, or a draft written after it. Every status past
    # verification, not only verified/closed, for the reason POST_VERIFY gives.
    for b in defn["blocks"]:
        if st["blocks"].get(b["id"], {}).get("status", "todo") in POST_VERIFY:
            if why := draft_not_imported(b, rows):
                gates.refuse("findings/draft-not-imported", why)

    # 3. declared reports exist
    for bid, s in st["blocks"].items():
        for r in s.get("reports", []):
            if not (ROOT / r).exists():
                gates.refuse("report/declared-missing",
                             f"{bid}: state.json declares report {r}, which is not on disk")

    # 4. a block cannot be past `running` without a hunter report
    for b in defn["blocks"]:
        s = st["blocks"].get(b["id"], {})
        if s.get("status") in ("hunted", "verified", "triaged", "fixing", "closed"):
            hunter = REVIEW / "reports" / f"{b['id']}-{b['slug']}.hunter.md"
            if not hunter.exists():
                gates.refuse(
                    "report/hunter-missing",
                    f"{b['id']}: status {s['status']}, but there is no hunter report — the status is not backed by work"
                )

    # 5. a session that died mid-block
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

    # 6. findings are well-formed and point at real code
    tracked = all_files()
    seen_ids: set[str] = set()
    for f in rows:
        finding_gates(gates, f, rows, idx, tracked, seen_ids)

    # 7. findings.md agrees with findings.jsonl. Compared by CONTENT, not by
    #    mtime: a clone or a `git checkout` stamps every file with the moment it
    #    was written, in whatever order, so mtimes say nothing about which of the
    #    two is the newer truth.
    if FINDINGS_MD.exists():
        if not findings_md_matches(FINDINGS_MD.read_text(encoding="utf-8"), rows):
            gates.refuse("findings-md/stale",
                         f"findings.md diverged from findings.jsonl — run `{CLI} findings`")

    # 8. a pattern that matches nothing silently shrinks a block's scope: the
    #    manifest promises to read code that was never handed to the agent.
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

    # 8a. the declared partial scope. Its reason is what tells a reader of the summary why
    #     the rest was not read; a scope pattern that matches nothing makes the coverage gate
    #     pass over files that are not there — the same silent shrinking as a block's.
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

    # 9. coverage
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

    # Hypotheses are the second denominator of coverage, next to the file map. A manifest
    # without hypotheses yields a review "by general impression", and a hypothesis without
    # a verdict gets lost in the report's prose: there will be nobody to ask "did you check this".
    for b in defn["blocks"]:
        stt = st["blocks"].get(b["id"], {}).get("status", "todo")
        if stt in ("todo", "blocked"):
            continue
        manifest = manifest_path(b)
        ids = hypotheses(b["id"], manifest)
        if not ids:
            gates.refuse(
                "manifest/no-hypotheses",
                f"{b['id']}: the manifest has no hypotheses — such a block yields a review "
                f"'by general impression'; a 'Hypotheses' section, one item per hypothesis"
            )
            continue
        if stt not in POST_VERIFY:
            continue
        for rp in verdict_reports(b):
            for h, vs in verdict_conflicts(rp.read_text(encoding="utf-8"), b["id"]).items():
                gates.refuse(
                    "report/verdicts-conflict",
                    f"{b['id']}: {rp.name} gives hypothesis {h} different verdicts "
                    f"({' / '.join(vs)}) — the outcome would depend on line order; leave one"
                )
        seen = verdicts_for(b)
        missing = [h for h in ids if h not in seen]
        if missing:
            gates.refuse(
                "report/hypothesis-without-verdict",
                f"{b['id']}: {len(missing)} of {len(ids)} hypotheses without a verdict "
                f"({', '.join(missing[:5])}{'…' if len(missing) > 5 else ''}) — "
                f"each is closed with the word 'checked', 'not checked' or 'not applicable'"
            )

    # A confirmed hypothesis that no finding carries is a defect the review saw and lost (see
    # CONFIRM_WORDS). From the hunt on: the hunter's draft is there, and the ids it will get
    # on import are known, so the refusal comes while the hunter's work is still fresh. Every
    # block, the closed ones of a review begun on an older kit included: on the kit's own
    # review (T1–T4, twelve hunter, fix and verifier reports) the rule refuses nothing, and a closed
    # block elsewhere that it does refuse holds exactly the defect the rule exists to recover.
    block_ids = [b["id"] for b in defn["blocks"]]
    for b in defn["blocks"]:
        if st["blocks"].get(b["id"], {}).get("status") not in READ_STATUSES:
            continue
        known = finding_ids_for(b, rows)
        draft = block_findings_path(b).relative_to(ROOT).as_posix()
        for rp in verdict_reports(b):
            for h, unknown in confirmed_without_finding(
                    rp.read_text(encoding="utf-8"), b["id"], known, block_ids):
                gates.refuse(
                    "report/confirmed-without-finding",
                    T("confirmed_unknown_finding" if unknown else "confirmed_no_finding",
                      block=b["id"], report=rp.name, h=h, ids=", ".join(unknown),
                      draft=draft))

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

    # "Read 25 of 25" is the agent's own word about its own work. The hunter of the first
    # block at the kit author's claimed all 25 files and named five; the top-up found 11
    # more defects. Therefore every file of a readable block must be named by FULL path in
    # at least one of the block's reports: the base name is not enough — 45 blocks out of
    # 59 had files with the same names, and "all page.tsx" would close six blocks at once.
    # The excluded is subtracted: it was not read on purpose, and demanding it in the
    # report would mean demanding imitation.
    if defn.get("named_files", True):
        excluded_all = git_files([e["pattern"] for e in defn.get("exclusions", [])])
        for b in defn["blocks"]:
            stt = st["blocks"].get(b["id"], {}).get("status", "todo")
            if stt not in ("hunted", *POST_VERIFY) or b.get("proof", "read") != "read":
                continue
            owned = sorted(git_files(b.get("paths", [])) - excluded_all)
            if not owned:
                continue
            text = "\n".join(
                rp.read_text(encoding="utf-8", errors="ignore")
                for rp in (REVIEW / "reports").glob(f"{b['id']}-*.md")
            )
            missing = [f for f in owned if not names_file(text, f)]
            if missing:
                gates.refuse(
                    "report/files-not-named",
                    f"{b['id']}: {len(missing)} of {len(owned)} block files are not named by full "
                    f"path in any report ({', '.join(missing[:4])}{'…' if len(missing) > 4 else ''}) "
                    f"— what was not read is named by path in 'Coverage limits', what was read — "
                    f"in the list of files read; or `named_files: false` in blocks.json, if the project "
                    f"deliberately opted out of this check"
                )

    # Fixes are the only code the review produces, and it is written by the same AI that
    # hunted the defects. Closing a block with fixes without a review of the fixes by those
    # who did not write them is closing on the fixer's own word.
    for b in defn["blocks"]:
        if st["blocks"].get(b["id"], {}).get("status") != "closed":
            continue
        if any(f.get("block") == b["id"] and f.get("status") == "fixed" for f in rows):
            if not list((REVIEW / "reports").glob(f"{b['id']}-{b['slug']}.fixreview-*.md")):
                gates.refuse(
                    "state/closed-without-fix-review",
                    f"{b['id']}: closed with fixed findings, but there is no fix reviewer report — "
                    f"`{CLI} prompt {b['id']} --role fixreview --diff <range>`"
                )

    # The manifest's acceptance criterion asks for artifacts — tables built by reading, a
    # mutation list — and the hunter delivers them under a heading of its own. In a field run
    # the hunter skipped them and nothing said so until the verifier did (#46). A warning,
    # not a refusal: the words of a criterion do not say which role must build its table,
    # and a review already past its hunts is not stopped retroactively. A closed block's
    # reports are history — asked of the blocks still in work.
    for b in defn["blocks"]:
        if st["blocks"].get(b["id"], {}).get("status", "todo") not in ("hunted", "verified",
                                                                       "triaged", "fixing"):
            continue
        manifest, hunter = manifest_path(b), REVIEW / "reports" / f"{b['id']}-{b['slug']}.hunter.md"
        if not (manifest.exists() and hunter.exists()):
            continue
        asked = section_body(manifest.read_text(encoding="utf-8"), ACCEPTANCE_HEADING)
        if not [ln for ln in unquoted(asked or [], "text") if ln.strip()]:
            continue
        given = section_body(hunter.read_text(encoding="utf-8"), ACCEPTANCE_HEADING, "quoted")
        if given is None or not [ln for ln in unquoted(given) if ln.strip()]:
            gates.warn(
                "report/no-acceptance-artifacts",
                f"{b['id']}: the manifest has an acceptance criterion, and the hunter report has "
                f"{'no' if given is None else 'an empty'} 'Acceptance criterion' section outside "
                f"a fence or a quotation — the tables or lists the criterion asks for go there; "
                f"what the hunter could not build is named there with the reason"
            )

    # The coverage-limits section is mandatory: completeness is proven by listing what was
    # NOT reviewed, and in audit reports that is a separate chapter. "No findings" without
    # it is indistinguishable from "skimmed".
    for b in defn["blocks"]:
        if st["blocks"].get(b["id"], {}).get("status", "todo") not in POST_VERIFY:
            continue
        hunter = REVIEW / "reports" / f"{b['id']}-{b['slug']}.hunter.md"
        if hunter.exists():
            body = section_body(hunter.read_text(encoding="utf-8"), LIMITS_HEADING, "quoted")
            if body is None:
                gates.refuse(
                    "report/no-coverage-limits",
                    f"{b['id']}: the hunter report has no 'Coverage limits' section outside a "
                    f"fence or a quotation — what was deliberately not read and why, as the "
                    f"report's own heading (a heading inside an example, or after a fence that "
                    f"never closes, is part of the example)"
                )
            elif not [ln for ln in unquoted(body)
                      if ln.strip() and not LIMITS_PLACEHOLDER.search(ln)]:
                # A heading without text is the same silence as no heading: neither what
                # was not reviewed is named, nor that there is nothing of the kind. A
                # section holding only the template's fenced example is that same silence.
                gates.refuse(
                    "report/empty-coverage-limits",
                    f"{b['id']}: the 'Coverage limits' section of the hunter report is empty — "
                    f"name what was not read or say outright that there is nothing, as an "
                    f"ordinary line and not inside a fence or a quotation"
                )

    # A defect class that repeated three times is closed by a guard, not by three fixes:
    # otherwise the next pass finds a fourth instance. A rule survives a refactoring, a
    # list of fixed places does not.
    for root, items in roots_of(rows).items():
        if len(items) < ROOT_RULE_AT:
            continue
        guards = root_guards(items)
        rules = set(guards) - {""}
        if rules:
            for r in sorted(rules):
                if why := rule_problem(r):
                    gates.refuse("root/guard-unusable", f"root '{root}': {why}")
            # A guard is recorded per finding (issue #28): one guarded instance no longer
            # stands for the rest. Instances without a guard are named, but not refused —
            # whether the recorded guard reaches them is a claim only a run on their own
            # defect can make, and the tool cannot make it for the fixer.
            if bare := guards.get(""):
                gates.warn(
                    "root/guard-partial",
                    f"root '{root}': {len(bare)} of {len(items)} instances carry no guard "
                    f"({', '.join(bare[:4])}) while others do — a guard holds only the findings "
                    f"it is recorded on; if it goes red on their defect too, record it on them "
                    f"(`{CLI} set-finding <ID>... <status> --rule <path>`), otherwise close "
                    f"them with a guard of their own; `{CLI} roots` shows who carries what")
            continue
        ids = ", ".join(f.get("id", "?") for f in items[:4])
        # The guard is recorded with `set-finding --rule` on a file that exists, i.e. by the
        # fixer; demanded before that, it made a block red for having been hunted and verified
        # well, and gate 3 of RELEASING.md ("hunter and verifier, and `check` green") could not
        # be passed on a block whose hunter found one class three times (the gate-3 run of
        # 0.8.0 on a live project). So the refusal waits for the fix phase: an instance
        # already fixed, or the block of one in `fixing`/`closed`. Before it the class is
        # named, so that whoever cuts the fix assignments plans a guard, not three edits.
        if not any(f.get("status") == "fixed"
                   or st["blocks"].get(f.get("block"), {}).get("status") in FIX_PHASE
                   for f in items):
            gates.warn(
                "root/guard-due",
                f"root '{root}': {len(items)} instances ({ids}) — a class that repeated "
                f"{ROOT_RULE_AT} times will be closed by a rule, not by a list of fixes; the "
                f"fix phase must record one: `{CLI} set-finding <ID>... <status> --rule "
                f"<path-to-guard>` (until an instance is fixed or its block reaches `fixing`, "
                f"this is a warning)")
            continue
        gates.refuse(
            "root/no-guard",
            f"root '{root}': {len(items)} instances ({ids}) and no guard — "
            f"a class that repeated {ROOT_RULE_AT} times is closed by a rule, not by a list of "
            f"fixes; record which: `{CLI} set-finding <ID> <status> --rule <path-to-guard>`"
        )

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

    # The loop signal, as `prompt --role fix` will refuse it: said here too, because the lead
    # reads `check` after every import, and the stop belongs before the next round is cut, not
    # at the moment its prompt is asked for. A warning: the state is not wrong, the next
    # move is a human's. A closed block has no next round.
    for bid in idx:
        if st["blocks"].get(bid, {}).get("status") == "closed":
            continue
        if why := loop_stop(bid, last_review_round(bid, rows) + 1, rows):
            gates.warn("loop/top-finding-in-own-diff", f"{bid}: {why}")

    refs = review_refs()
    if refs:
        sample = ", ".join(f"{p}:{n} ({fid})" for p, n, fid, _ in refs[:4])
        gates.warn("refs/findings-named-in-code",
                   f"{len(refs)} reference(s) to findings in the code: {sample} — the ids die "
                   f"with docs/review/; `{CLI} refs` lists them")
    old = open_findings_age(findings())
    if old:
        oldest = max(age for _, age in old)
        sample = ", ".join(f"{f.get('id')} ({age}d)" for f, age in sorted(old, key=lambda x: -x[1])[:5])
        gates.warn("findings/fix-debt-age",
                   f"{len(old)} open finding(s) older than {FIX_AGE_DAYS} days (oldest {oldest}d): "
                   f"{sample} — fix debt: fix, defer with a reason or reject; a register that "
                   f"outlives the code it describes stops being true")
    return gates.report()
