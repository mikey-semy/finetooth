"""The pieces of a role prompt that are not the template itself."""

from __future__ import annotations

import re

from .git import git, git_files
from .workspace import named_file
from .model import FIX_BATCH
from .i18n import T
from .fingerprint import file_lines
from .blocks import readable_lines
from .register import finding_file, findings, open_findings_for, shown_lines


# Where a list of context files stops being a list and becomes a wall. Measured, not
# guessed: a path in a real tree is about 31 characters on average (this repository; the
# 90th percentile is 45), so 80 of them are ~2.5 thousand characters, about 600 tokens —
# the last size that still reads as an enumeration next to the manifest and the invariants
# on one screen. Above it the patterns say the same thing in four lines, and the agent
# expands the part it needs with `git ls-files`.
REF_LIST_LIMIT = 80


def render_refs(pathspecs: list[str], refs: list[str]) -> str:
    """Context files: listed by name while the list is short, by pattern once it is not.

    A sweep block's context is whole layers — every usecase, every repository —
    and spelling out a thousand paths would bury the manifest and the invariants
    under a wall of text the agent has to scroll past to reach its own task. The
    patterns say the same thing in four lines, and the agent expands whichever
    part it actually needs with `git ls-files`.
    """
    if not refs:
        return T("none")
    if len(refs) <= REF_LIST_LIMIT:
        return "\n".join(refs)
    return (
        "\n".join(pathspecs)
        + T("refs_cut", n=len(refs))
    )


def volume_note(files: list[str], role: str) -> str:
    """How much code the block asks to read — and what of it will certainly not be read.

    The budget must stand in the assignment itself, not in the lead session's head.
    Neighbours in the niche do it two ways, and both are needed: repomix fails the build
    with a non-zero code when the pack outgrew the budget, and ai-digest leaves a file that
    did not fit in the output as a stub — path visible, contents absent. Staying silent is
    the worst: then the agent reports coverage that did not happen, and nobody can say
    where the line ran.

    The way out is named by the section of the reader's OWN report that `check` reads for
    it: the hunter's coverage-limits section (`LIMITS_HEADING`), the verifier's block
    coverage status (`COVERAGE_VERDICT`). One wording for both roles sends one of them into
    a section its report does not have, or into one the gate does not read — and the gate
    then refuses a report written exactly as the warning said.
    """
    sizes = sorted(((file_lines(f) or 0, f) for f in files), reverse=True)
    total = sum(n for n, _ in sizes)
    # A rough estimate, not a measurement: about four characters per token is common
    # knowledge, and here it is more honest than an exact count, because every model has
    # its own tokenizer.
    chars = sum(len(f) for f in files) + total * 40
    out = [T("vol_head", n=len(files), lines=total, k=chars // 4000)]
    limit = readable_lines()
    if total <= limit:
        out.append(T("vol_fits", limit=limit))
        return "\n".join(out)

    out.append(T("vol_over_verify" if role == "verify" else "vol_over",
                 lines=total, limit=limit))
    out.append(T("vol_border"))
    shown = 0
    for n, f in sizes:
        shown += 1
        acc = sum(x for x, _ in sizes[:shown])
        mark = "  " if acc <= limit else "▲ "
        out.append(f"  {mark}{acc:>6} · {f} ({n} {T('vol_lines')})")
        if acc > limit * 2 and shown < len(sizes):
            out.append(T("vol_more", n=len(sizes) - shown))
            break
    out.append(T("vol_legend"))
    return "\n".join(out)


def proof_rule(proof: str, role: str, n_files: int) -> str:
    """The prompt's first rule: what it means to cover THIS block.

    One rule "read every file in full" for every block in a row forced the test-quality
    block to read hundreds of files while its manifest a page below explained why that is
    impossible, and gave live-system blocks "files 0 — read all". A prompt that contradicts
    its own manifest teaches the agent to pick the convenient half.
    """
    if n_files == 0:
        return T("proof_live")
    if proof == "measured":
        return T("proof_measured_verify" if role == "verify" else "proof_measured")
    return T("proof_read_verify" if role == "verify" else "proof_read")


def files_heading(proof: str, n_files: int) -> str:
    if n_files == 0:
        return T("files_live")
    if proof == "measured":
        return T("files_measured", n=n_files)
    return T("files_read", n=n_files)


def diff_volume(diff: str) -> str:
    """How much the fix reviewer is asked to read — the measure the hunter already gets.

    The budget belongs in the assignment, not in the lead session's head. The fix reviewer
    was handed a diff of any size with the rule "read it in full" and no condition: the
    first round of the kit's own tool block was 193 KB, and nothing in the prompt said so
    or named the way out. The way out is a narrower `--diff` range — the only thing that
    makes the diff smaller; `--scope` divides the reporting and leaves the size alone, and
    the message that once offered it for size sent the lead after what the mechanism does
    not do. Both stand where the volume does.
    The token estimate is the same rough one as for the file list: about four
    characters per token is common knowledge and more honest here than an exact count,
    because every model has its own tokenizer.
    """
    return T("diff_vol", kb=max(1, len(diff.encode("utf-8")) // 1024),
             lines=diff.count("\n"), k=max(1, len(diff) // 4000))


# Where a project writes down its commit rules. Tracked files only, read from the index:
# a rule that is not committed is not the project's rule yet. The places are the ones
# GitHub itself looks in for contribution guidelines (the root, `.github/`, `docs/`),
# plus `AGENTS.md`, which is written for exactly the agent that makes the commits.
COMMIT_RULE_DOCS = ("CONTRIBUTING*", ".github/CONTRIBUTING*", "docs/CONTRIBUTING*", "AGENTS.md")
# The CI side: a workflow that checks commits. A git pathspec `*` crosses `/`, so nested
# workflow files are reached too.
COMMIT_RULE_CI = (".github/workflows/*",)
# Files whose mere presence is the requirement: the project's own gate over a commit range
# (named to the fix reviewer by its path) and the DCO GitHub App's config, which may be as
# little as `require: members: false`.
DCO_SCRIPT = ".github/dco.sh"
DCO_APP = ".github/dco.yml"
# What reads as a sign-off requirement: the certificate's name, its abbreviation as a word
# (`tim-actions/dco`, `dco-check`, a job called `dco`) and the trailer itself.
DCO_SIGN = re.compile(r"\bdco\b|signed-off-by|developer certificate of origin", re.I)


def index_text(rel: str) -> str:
    """A tracked file's text as the index holds it — the same source `file_lines` counts."""
    out = git("show", f":{rel}", binary=True)
    return out.out.decode("utf-8", errors="replace") if out.code == 0 else ""


def commit_rules(role: str, diff_range: str) -> str:
    """`{{COMMIT_RULES}}`: the project's commit rules, as far as its files state them.

    The fix template told the fixer to commit every fix and never said the project's own
    commit rules apply: in the kit's own review the fixers made twelve commits without
    `Signed-off-by`, the project's `dco` job refused them, and the PR stood until the
    history was rewritten. So the requirement is looked up in the project's files and
    stated to the role that commits and to the role that checks the commits.

    Looked up at `prompt` time, not recorded by `setup`: a copy in `blocks.json` would be a
    second source of truth, stale from the day the project adds DCO to its CI.
    """
    docs = sorted(git_files(list(COMMIT_RULE_DOCS)))
    ci = sorted(git_files(list(COMMIT_RULE_CI)))
    signs = [rel for rel in (DCO_SCRIPT, DCO_APP) if named_file(rel)] + [
        rel for rel in docs + ci if DCO_SIGN.search(index_text(rel))]
    script = DCO_SCRIPT in signs
    if not signs:
        return T("commit_none_review" if role == "fixreview" else "commit_none",
                 docs=", ".join(f"`{d}`" for d in docs) or T("commit_no_docs"))
    where = ", ".join(f"`{s}`" for s in signs)
    if role != "fixreview":
        return T("commit_dco", where=where)
    gate = (T("commit_gate_script", script=DCO_SCRIPT, range=diff_range) if script
            else T("commit_gate_log", range=diff_range))
    return T("commit_dco_review", where=where, gate=gate)


PLACEHOLDER = re.compile(r"\{\{[A-Z_]+\}\}")


def render_recorded_for(block_id: str) -> str:
    """Findings recorded against the block before this pass — handed over by another block's
    fixer, left by an earlier pass, deferred into it. Without them in the prompt the hunter
    numbers from 001 and hunts again for what is already written down (the kit author's
    review, 24.09)."""
    rows = [f for f in findings() if f.get("block") == block_id
            and f.get("status") in ("open", "deferred")]
    if not rows:
        return T("rec_none")
    out = []
    line_of = shown_lines()
    for f in sorted(rows, key=lambda f: f.get("id", "")):
        at = line_of(f)
        where = finding_file(f) + (f":{at}" if at else "")
        out.append(T("rec_row", id=f.get("id", "?"), severity=f.get("severity", "?"),
                     status=f.get("status", "?"), where=where, claim=f.get("claim", ""),
                     date=(f.get("imported_at") or "")[:10]))
    return "\n".join(out)


def batch_note(block_id: str) -> str:
    """`{{BATCH}}`: the batch limit, named to the fixer when the block holds more than one
    run can close (`FIX_BATCH`). Without it the fixer took the whole list, ran out of turns
    halfway and left the half it had done uncommitted. Empty when everything fits: then the
    list below is the assignment as it stands."""
    rows = open_findings_for(block_id)
    if len(rows) <= FIX_BATCH:
        return ""
    return T("fix_batch", n=len(rows), cap=FIX_BATCH,
             ids=", ".join(f.get("id", "?") for f in rows[:FIX_BATCH]))


def render_findings_for(block_id: str) -> str:
    rows = open_findings_for(block_id)
    if not rows:
        return T("no_open_findings")
    out = []
    line_of = shown_lines()
    for f in rows:
        where = finding_file(f)
        if at := line_of(f):
            where += f":{at}"
        out.append(
            f"### {f['id']} · {f.get('severity')} · {T('f_conf')} {f.get('confidence')}\n"
            f"{T('f_where')} `{where}`\n\n"
            f"{T('f_claim')} {f.get('claim','')}\n\n"
            f"{T('f_scenario')} {f.get('scenario','')}\n"
            + (f"\n{T('f_invariant')} {f.get('invariant')}\n" if f.get("invariant") else "")
        )
    return "\n".join(out)
