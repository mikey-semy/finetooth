"""Command: prompt — a role's prompt for one block."""

from __future__ import annotations

from ..base import SKILL_DIR, die
from ..git import ROOT, diff_text, git_files
from ..workspace import CLI, INVARIANTS_FILE, REVIEW
from ..model import CLAIM_MAX, PROOFS, SCENARIO_MAX
from ..i18n import T, review_lang
from ..text import demote
from ..blocks import block_index, blocks, manifest_path, report_path
from ..register import findings, next_finding_id
from ..coverage import sweep_lines
from ..seams import render_seams_for
from ..journal import loop_stop, pinned_range, render_decisions_for
from ..roles import (
    PLACEHOLDER, batch_note, commit_rules, diff_volume, files_heading, proof_rule,
    render_findings_for, render_recorded_for, render_refs, volume_note,
)


def cmd_prompt(args) -> int:
    defn = blocks()
    idx = block_index(defn)
    if args.block not in idx:
        die(f"unknown block {args.block}; known: {', '.join(idx)}")
    b = idx[args.block]
    manifest = manifest_path(b)
    if not manifest.exists():
        die(f"manifest missing: {manifest.relative_to(ROOT)}")
    proof = b.get("proof", "read")
    if proof not in PROOFS:
        die(f"{b['id']}: proof '{proof}' is not in the vocabulary: {', '.join(PROOFS)}")
    if args.role == "fixreview" and not args.diff:
        die("the fix reviewer needs a diff: --diff <range>, for example main...HEAD")
    if args.role == "fix" and (why := loop_stop(b["id"], args.round, findings())):
        die(why)
    # The project may keep its own version of a role template in `docs/review/prompts/` —
    # then that one is taken. If not — the skill's template: an own copy is not required
    # and does not fall behind it.
    template = REVIEW / "prompts" / f"{args.role}.md"
    if not template.exists():
        # The skill's template in the review language: `hunter.md` is English, `hunter.ru.md` Russian.
        lang = review_lang()
        template = SKILL_DIR / "references" / (f"{args.role}.md" if lang == "en" else f"{args.role}.{lang}.md")
    if not template.exists():
        die(f"no template for role {args.role}: neither docs/review/prompts/{args.role}.md nor {template}")

    # ⚠️ Exclusions are subtracted here too. The coverage map and the readability ceiling
    # subtract them, but the prompt did not, and the block got to work on what its size
    # did not count: a 19-thousand-line `package-lock.json`, codegen. The agent dutifully
    # started reading them, and the context went on files nobody intended to read.
    excluded = git_files([e["pattern"] for e in defn.get("exclusions", [])])
    files = sorted(git_files(b.get("paths", [])) - excluded)
    refs = sorted(git_files(b.get("ref_paths", [])) - excluded - set(files))
    report = report_path(b, args.role, args.round, args.scope)
    # Taken once: the volume line and the diff itself talk about the same text, and a
    # second `git diff` of a 193 KB range would only risk them disagreeing.
    diff = diff_text(args.diff) if args.role == "fixreview" else ""

    body = template.read_text(encoding="utf-8")
    subs = {
        "{{BLOCK_ID}}": b["id"],
        "{{BLOCK_TITLE}}": b["title"],
        "{{BLOCK_ROLE}}": b["role"],
        "{{BLOCK_GOAL}}": b["goal"],
        "{{REPORT_PATH}}": report,
        "{{HUNTER_REPORT}}": f"docs/review/reports/{b['id']}-{b['slug']}.hunter.md",
        "{{MANIFEST}}": demote(manifest.read_text(encoding="utf-8")),
        "{{INVARIANTS}}": demote(
            INVARIANTS_FILE.read_text(encoding="utf-8") if INVARIANTS_FILE.exists() else ""
        ),
        "{{FILES}}": "\n".join(files) if files else T("none"),
        "{{FILE_COUNT}}": str(len(files)),
        "{{PROOF_RULE}}": proof_rule(proof, args.role, len(files)),
        "{{FILES_HEADING}}": files_heading(proof, len(files)),
        "{{ROUND}}": str(args.round),
        "{{SCOPE_LINE}}": T("scope_line", scope=args.scope) if args.scope else "",
        "{{FIX_REPORT}}": report_path(b, "fix", args.round),
        "{{DIFF_RANGE}}": args.diff or "",
        # The range as two commit ids, for the import command the fix reviewer's template
        # names: `main...HEAD` means another diff once the next round commits, and the loop
        # signal reads the lines of THIS round's diff.
        "{{DIFF_PINNED}}": (pinned_range(args.diff) or args.diff) if args.diff else "",
        "{{DECISIONS}}": render_decisions_for(b["id"]),
        "{{DIFF_VOLUME}}": diff_volume(diff) if diff else "",
        "{{VOLUME}}": volume_note(files, args.role) + (
            T("vol_sweep", n=sweep_lines(b)[0], lines=sweep_lines(b)[1], id=b["id"])
            if sweep_lines(b)[0] else ""),
        "{{REF_FILES}}": render_refs(b.get("ref_paths", []), refs),
        "{{FINDINGS}}": render_findings_for(b["id"]),
        "{{BATCH}}": batch_note(b["id"]),
        "{{RECORDED}}": render_recorded_for(b["id"]),
        "{{NEXT_ID}}": next_finding_id(b["id"]),
        # The register's own limits, from the constants `import` and `check` hold: a template
        # that wrote them by hand fell behind the code the day a limit moved, and a field run
        # still had verifier drafts refused whole for fields past them (#46).
        "{{CLAIM_MAX}}": str(CLAIM_MAX),
        "{{SCENARIO_MAX}}": str(SCENARIO_MAX),
        # The project name and its gates are substitutions, not text in the template. A
        # template copied without proofreading greeted the agent on behalf of ANOTHER
        # project, and it was not noticed at once: the assignment looked meaningful as a whole.
        "{{PROJECT}}": defn.get("project", ROOT.name),
        # The command the project calls the tool by: a template that names a command for the
        # lead to run names it runnable, not as a bare subcommand.
        "{{CLI}}": CLI,
        "{{GATES}}": "\n".join(f"- `{g}`" for g in defn.get("gates", []))
        or T("gates_missing"),
        # Read from the project's files only when the template asks: a hunter has no
        # commits to make, and the lookup is a git run per file it reads.
        "{{COMMIT_RULES}}": commit_rules(args.role, args.diff or "")
        if "{{COMMIT_RULES}}" in body else "",
        # The same: the seams read the whole history, and only the hunter's template asks.
        "{{SEAMS}}": render_seams_for(b) if "{{SEAMS}}" in body else "",
    }
    if diff:
        # The diff is a substitution like any other and goes in the SAME pass. Applied
        # afterwards over the assembled body it also replaced the manifest's own mentions
        # of "{{DIFF}}" — a block whose manifest writes about the placeholder was handed
        # the diff three times while {{DIFF_VOLUME}}, measured on one copy, stated a third
        # of what arrived.
        subs["{{DIFF}}"] = diff
    # An unfilled substitution would reach the agent as the text "{{SOMETHING}}" — and it
    # would read it as an assignment. Checked on the TEMPLATE, not on the assembled text:
    # substituted content (a finding about a template, a manifest quoting one) legally
    # carries "{{FILES}}" as a quotation, and the assembled check refused the fix prompt
    # of the kit's own review for exactly that.
    left = sorted(set(PLACEHOLDER.findall(body)) - set(subs))
    # ONE pass over the template, not one pass per substitution: a manifest that writes
    # about the placeholders ("the template uses {{FILES}}") had its own prose rewritten
    # with the file list, because MANIFEST was substituted before FILES. What the template
    # asks for is substituted; what the substituted text contains is quotation.
    body = PLACEHOLDER.sub(lambda m: subs.get(m.group(0), m.group(0)), body)
    if left:
        die(f"template {template.name} has substitutions left without a value: {', '.join(left)}")
    print(body)
    return 0
