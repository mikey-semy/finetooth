"""The findings register: rows, the draft, the fields every finding must carry, roots."""

from __future__ import annotations

import datetime as dt
import json
import os
import re
from collections.abc import Callable
from pathlib import Path

from .base import die, now
from .git import ROOT
from .workspace import CLI, FINDINGS_FILE, FINDINGS_MD, named_file
from .model import FIX_AGE_DAYS, FIX_GATE_DEFAULT, SEVERITIES
from .i18n import T
from .fingerprint import (
    CODE_FINGERPRINT_FIELDS, cited_line_now, code_fingerprint, file_lines, file_sha,
    line_follows_code, locate_region, put_fingerprint, text_lines,
)
from .blocks import block_findings_path


def shown_lines() -> Callable[[dict], object]:
    """The line every display of a finding uses: findings.md, the SARIF export, the summary,
    the prompts, `roots`.

    For a finding whose line follows its code, the window is looked for in the current file
    (`locate_region`) and, found, the line it sits on NOW is shown; not found, the recorded
    line, and `check` refuses the finding if it is live (`finding/region-changed`). The
    register is not rewritten: this is what is shown, not what is recorded, and `restamp`
    stays the one command that records a line. Before, the displays read the register's line
    and `check` warned on every shift (`finding/line-moved`) so a human would restamp — in an
    actively edited file that warning came on every PR, and it was there only to correct a
    display.

    Returns a function, so the lines of a file are read once however many findings sit in it.
    """
    cache: dict[str, list[bytes] | None] = {}

    def line_of(f: dict):
        line = f.get("line")
        if not line_follows_code(f):
            return line
        rel = finding_file(f)
        if rel not in cache:
            cache[rel] = text_lines(rel)
        lines = cache[rel]
        return (locate_region(f, lines) if lines is not None else None) or line
    return line_of


def findings() -> list[dict]:
    if not FINDINGS_FILE.exists():
        return []
    rows = []
    for n, line in enumerate(FINDINGS_FILE.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            die(f"findings.jsonl line {n} is not valid JSON: {exc}")
    return rows


def fix_gate(defn: dict) -> str | None:
    """The severity threshold of the fix gate, or None when the project switched it off."""
    gate = defn.get("fix_gate", FIX_GATE_DEFAULT)
    if gate in (None, "none", "off", False):
        return None
    if gate not in SEVERITIES:
        die(f"blocks.json: fix_gate must be one of {', '.join(SEVERITIES)} or \"none\", not `{gate}`")
    return gate


def fix_debt(defn: dict, rows: list[dict], except_block: str | None = None) -> list[dict]:
    """Open findings at the gate's severity or above, outside the given block."""
    gate = fix_gate(defn)
    if gate is None:
        return []
    rank = SEVERITIES.index(gate)
    return [f for f in rows
            if f.get("status") == "open"
            and f.get("block") != except_block
            and f.get("severity") in SEVERITIES
            and SEVERITIES.index(f["severity"]) <= rank]


def open_findings_age(rows: list[dict], days: int = FIX_AGE_DAYS) -> list[tuple[dict, int]]:
    """Open findings imported more than `days` ago, with their age in days."""
    out = []
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
    for f in rows:
        if f.get("status") != "open" or not f.get("imported_at"):
            continue
        try:
            when = dt.datetime.fromisoformat(f["imported_at"].replace("Z", "+00:00"))
        except ValueError:
            continue
        if when.tzinfo is None:
            when = when.replace(tzinfo=dt.timezone.utc)
        if when < cutoff:
            out.append((f, (dt.datetime.now(dt.timezone.utc) - when).days))
    return out


def reject_reason_of(f: dict) -> str:
    """The recorded reason a finding was rejected, or an empty string.

    The reason is written either as its own field or right in the claim ("Rejected: …") —
    a register written by an older template says it there, and demanding only the field
    would fail the check on every finding written exactly by those instructions. ONE place
    answers it: `check` refuses a rejected finding without it, and `import --dry-run` names
    the same row before the draft is handed in."""
    claim = (f.get("claim") or "").strip()
    return (f.get("reject_reason") or "").strip() or (
        claim if re.match(r"отвергнут|отклонен|отклонён|не подтверд|rejected|not confirmed", claim, re.I) else "")


def finding_file(f: dict) -> str:
    """A finding's `file` as every command reads it: the path when it is a string, "" when it
    is anything else.

    The register and the drafts are hand-written JSON, and `"file": null`, `12`, `true`, a
    list or an object are all one slip away. `f.get("file", "")` falls back only when the key
    is MISSING, so each of them reached the path code and the command died with a traceback:
    `findings` on `+=`, `sarif` on `removeprefix`, `check` on the set of a fixed finding's
    paths, the line lookup on a cache keyed by the path (the 0.8.0 release candidate, after
    `import --dry-run` and `check` were closed for two of the forms). What is not a string is
    no file here — the same as a finding about no file at all — and `file_problem` is what
    names it; a command that reads `file` directly is the next traceback."""
    path = f.get("file")
    return path if isinstance(path, str) else ""


def file_problem(f: dict) -> str | None:
    """Why a finding's `file` is not a path, or None: ONE message for `check`, for
    `import --dry-run` and for `import` itself. A missing or null file is the required-field
    refusal's to name, not this one's; every other value that is not a string is named with
    what was written."""
    path = f.get("file")
    if path is None or isinstance(path, str):
        return None
    return (f"file={path!r} is not a path — write the file as a string in quotes, relative "
            f"to the repository root")


def location_problems(f: dict, tracked: set[str]) -> dict[str, str]:
    """What is wrong with where a finding points — ONE rule for `check` over the register and
    for `import --dry-run` over a draft (a draft that the dry run passed was refused by
    `check` right after the import for a file that is not there or a line given as text).
    Keys: `file-not-a-string`, `file-missing`, `line-not-a-number`, `line-past-end`; the
    value is the message."""
    out: dict[str, str] = {}
    live = f.get("status") in ("open", "deferred")
    # `"file": 12` is as easy a slip as a quoted line, and it used to reach the path code
    # and kill the process before the message that would fix the row was printed.
    if why := file_problem(f):
        out["file-not-a-string"] = why
    path = finding_file(f)
    # Only open and deferred findings must point at a live file: a fixed finding is
    # history, and renaming the file after the fix does not make it false. The check
    # used to demand the file for any status and stayed red on history forever.
    if live and path and path not in tracked and not path.startswith("("):
        out["file-missing"] = f"file {path} is not in the repository"
    # A line number the file does not have is the cheapest sign of fabrication — for a
    # finding that is still open. A fixed one cites the file as it was before the fix;
    # after it the file legitimately shrinks (the first migrated registry: three fixed
    # findings, all flagged).
    # The type is part of the vocabulary, like severity and status: a hand-written draft
    # says `"line": "2137"` as easily as `2137`, `import` copies the field through
    # untouched, findings.md renders both the same — and the gate used to skip the
    # quoted one silently, which is worse than having no gate.
    if f.get("line") is not None and (isinstance(f["line"], bool) or not isinstance(f["line"], int)):
        out["line-not-a-number"] = (f"line={f['line']!r} is not a number — write the line as a "
                                    f"number without quotes, or leave the field out")
    elif live and f.get("line") and path:
        n = file_lines(path)
        if n is not None and f["line"] > n:
            out["line-past-end"] = f"line {f['line']} is cited, but {path} has {n}"
    return out


def draft_lines(src: Path):
    """The lines of a block's draft that are rows, with their numbers: blank lines and `#`
    comments are not rows."""
    for n, line in enumerate(src.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if line and not line.startswith("#"):
            yield n, line


def not_json(exc: json.JSONDecodeError) -> str:
    """What is wrong with a draft line JSON cannot read — and the way out, for someone
    seeing the draft format for the first time."""
    # `exc.msg` and the column, not `str(exc)`: that one says "line 1 column 34" of the one
    # line it was given, next to the draft's own line number.
    return (f"not JSON — {exc.msg} at column {exc.colno}; one finding per line, as `{{...}}`: "
            f"keys and strings in double quotes, no trailing comma")


NOT_AN_OBJECT = "not a JSON object — one finding per line, as `{...}`"


def read_draft(src: Path) -> list[tuple[int, object]]:
    """The rows of a block's draft as `check` reads them, with their line numbers. A line that
    is not JSON raises ValueError naming it — the gate below names it; `import` reads the
    draft with `draft_rows`, which names every such line."""
    rows = []
    for n, line in draft_lines(src):
        try:
            rows.append((n, json.loads(line)))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{src.name} line {n}: {not_json(exc)}") from None
    return rows


def draft_rows(src: Path) -> tuple[list[tuple[int, dict]], list[tuple[int, str]]]:
    """The draft as `import` reads it on every path: (the rows that are JSON objects, with
    their line numbers; a (line, message) for every line that is not). ONE rule for the
    plain import, `--append`, `--force` and `--dry-run`. A line that was JSON but not an
    object (`[1,2]`, `"text"`, `42`) reached the plan and the plain import died with a
    traceback on `.get`, while the dry run named it; a line that was not JSON stopped the
    dry run on itself, so a draft with three broken lines took three runs (fix review of the
    0.8.0 candidate, R13-003)."""
    rows, bad = [], []
    for n, line in draft_lines(src):
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            bad.append((n, not_json(exc)))
            continue
        if isinstance(row, dict):
            rows.append((n, row))
        else:
            bad.append((n, NOT_AN_OBJECT))
    return rows, bad


def unimported_rows(rows: list, register: list[dict]) -> list:
    """Draft rows the register does not hold — by the one rule `import` uses to call a row
    already taken in: its id is in the register. `import` writes the ids it hands out back
    into the draft, so after either import every row carries a recorded id; a row without
    one, or with an id nobody recorded, is a finding the review does not know about."""
    known = {e.get("id") for e in register if e.get("id")}
    return [r for r in rows if not isinstance(r, dict) or r.get("id") not in known]


def draft_not_imported(b: dict, register: list[dict]) -> str | None:
    """Why the block's draft is not all in the register, or None when it is.

    A field run: three blocks were set to `verified` with their verifiers' drafts never
    imported — a key leaking into a frontend bundle and 42 checkout and payment findings,
    four of them critical — and `check` called the review consistent while `summary` left
    the blocks out (#42). No draft, or a draft with no rows, is a block without findings,
    not a refusal."""
    src = block_findings_path(b)
    if not src.exists():
        return None
    draft = str(src.relative_to(ROOT))
    try:
        rows = [row for _, row in read_draft(src)]
    except ValueError as exc:
        return T("draft_unreadable", block=b["id"], draft=draft, why=exc, cli=CLI)
    missing = unimported_rows(rows, register)
    if not missing:
        return None
    return T("draft_unimported", block=b["id"], draft=draft, n=len(missing), cli=CLI)


def finding_id(block_id: str, n: int) -> str:
    """A finding's id: the block's id, a dash, the number in three digits. The ONE place the
    format is written — `import` hands ids out by it, `check` recognises them by it."""
    return f"{block_id}-{n:03d}"


def finding_number(block_id: str, fid: object) -> int | None:
    """The number of `fid` if it is an id of block `block_id`, else None."""
    m = re.fullmatch(rf"{re.escape(block_id)}-(\d+)", str(fid or ""))
    return int(m.group(1)) if m else None


def finding_ref(block_ids: list[str]) -> re.Pattern:
    """Finding ids of the given blocks as they stand in prose: built from the blocks' own ids,
    not guessed by shape — a block may be `api-core`, `T.1` or `Б1`, and `import` numbers its
    findings all the same. Longest id first, so `api-core-001` is not read as `core-001`."""
    alts = "|".join(re.escape(b) for b in sorted(set(block_ids), key=len, reverse=True))
    return re.compile(rf"(?<![\w.-])(?:{alts})-\d{{3,}}(?!\w)")


def next_finding_id(block_id: str) -> str:
    """The id `import --append` will give the block's first new finding: after the highest
    number the block has ever used — numbers have gaps, and a retired id stays retired."""
    taken = [n for f in findings() if (n := finding_number(block_id, f.get("id"))) is not None]
    return finding_id(block_id, max(taken, default=0) + 1)


def open_findings_for(block_id: str) -> list[dict]:
    """The block's open findings in the order a fixer takes them: by severity, then by id."""
    rows = [f for f in findings() if f.get("block") == block_id and f.get("status") == "open"]
    order = {s: i for i, s in enumerate(SEVERITIES)}
    return sorted(rows, key=lambda f: (order.get(f.get("severity"), 9), f.get("id", "")))


def render_findings_md(rows: list[dict], line_of: Callable[[dict], object] | None = None) -> str:
    """Render findings.md from the finding rows.

    Deliberately a function of `findings.jsonl` and nothing else but one thing: no wall
    clock, no counts of anything not in the rows. A generation stamp would make every run
    of `review.py findings` a diff, so the file would arrive in review commits as noise and
    `review-check` could not tell a stale render from a fresh one by comparing content.
    When the file changed is a question git already answers.

    The one thing is the line of a finding with a region fingerprint, which is where its code
    sits NOW (`shown_lines`), not the line the register recorded. `line_of` replaces that lookup —
    `check` passes one that leaves a mark, see `findings_md_matches`.
    """
    line_of = line_of or shown_lines()
    order = {s: i for i, s in enumerate(SEVERITIES)}
    rows = sorted(rows, key=lambda f: (order.get(f.get("severity"), 9), f.get("id", "")))

    out = [
        T("md_title"),
        "",
        T("md_gen", cli=CLI),
        T("md_noedit"),
        "",
    ]
    live = [f for f in rows if f.get("status") == "open"]
    out.append(T("md_open", live=len(live), total=len(rows)))
    out.append("")
    for sev in SEVERITIES:
        chunk = [f for f in rows if f.get("severity") == sev]
        if not chunk:
            continue
        out.append(T("md_sev", sev=sev, open=sum(1 for f in chunk if f.get('status') == 'open'), total=len(chunk)))
        out.append("")
        out.append(T("md_cols"))
        out.append("|---|---|---|---|---|")
        for f in chunk:
            where = finding_file(f)
            if at := line_of(f):
                where += f":{at}"
            claim = (f.get("claim", "") or "").replace("|", "\\|").replace("\n", " ")
            out.append(
                f"| {f.get('id','')} | {f.get('block','')} | {f.get('status','')} | "
                f"`{where}` | {claim} |"
            )
        out.append("")
    return "\n".join(out) + "\n"


def findings_md_matches(text: str, rows: list[dict]) -> bool:
    """Whether findings.md on disk is the render of this register.

    Everything is compared except the line of a finding whose line follows its code: that
    line was right when the file was rendered and moves with every edit above the finding.
    Comparing it would bring back, as a refusal, the very noise showing the current line
    removed — a PR adding a line above a finding would turn `check` red until someone ran
    `findings` again. What is compared there instead is that it IS a line number.
    """
    # The mark is random per call, so no text a finding carries can be taken for it.
    mark = f"\0{os.urandom(8).hex()}\0"
    expected = render_findings_md(rows, lambda f: mark if line_follows_code(f) else f.get("line"))
    pattern = r"[1-9][0-9]*".join(re.escape(part) for part in expected.split(mark))
    return re.fullmatch(pattern, text) is not None


def restamp_finding(fid: str, line: int | None = None) -> int:
    """Confirm that an open finding is still alive on a changed file.

    The file under a finding changes not only by its fix: a neighbouring finding gets fixed
    in it, a line nearby gets edited. Without this command there were two ways out, both
    false — close a live defect or edit the register by hand. The stamp is set by name, as
    for a block: "re-checked, the defect is there" is said on record rather than switching
    the check off.

    WHERE the defect is decides what is stamped. A finding with a line gets the region
    fingerprint (the lines around it, `REGION_K`); `--line` says where the defect sits now
    when the code moved away from the cited line. Without it the window is looked for by
    content, so a finding that only shifted keeps its code and gets its new line. A record
    of the whole-file form is moved to the region form here, and its window is taken from
    the version of the file its old fingerprint names, if git still has it: the line was
    cited on THAT version, and the current file may have moved it.
    """
    rows = findings()
    hit = [f for f in rows if f.get("id") == fid]
    if not hit:
        die(f"neither a block nor a finding {fid}")
    f = hit[0]
    if f.get("status") not in ("open", "deferred"):
        die(f"finding {fid} is in status {f.get('status')} — only open and deferred ones are stamped")
    rel = finding_file(f)
    if why := file_problem(f):
        die(f"finding {fid}: {why} — `{CLI} check` names every such record")
    if not file_sha(rel):
        die(f"file {rel} does not exist — a finding is moved (`{CLI} set-finding`), not stamped")
    lines = text_lines(rel)
    was = f.get("line")
    if line is not None:
        if lines is None or not 1 <= line <= len(lines):
            die(f"{rel} has no line {line} to anchor {fid} at"
                + ("" if lines is None else f" — it has {len(lines)}")
                + ("; the file is not text, so its finding keeps the whole-file fingerprint "
                   f"— drop --line" if lines is None else ""))
        at = line
    elif lines is not None and f.get("region_sha"):
        at = locate_region(f, lines) or was
    elif lines is not None and f.get("code_sha"):
        at = cited_line_now(f, lines)
    else:
        at = was
    fp = code_fingerprint(rel, at)
    if at == was and all(f.get(k) == fp.get(k) for k in CODE_FINGERPRINT_FIELDS):
        print(f"{fid}: the fingerprint already matches {rel} — nothing to stamp")
        return 0
    put_fingerprint(f, fp)
    if "region_sha" in fp:
        f["line"] = at
    f["restamped_at"] = now()
    with FINDINGS_FILE.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    FINDINGS_MD.write_text(render_findings_md(rows), encoding="utf-8")
    print(f"{fid}: code fingerprint re-taken — the defect is confirmed on the current version of {rel}")
    if "region_sha" in fp:
        above, below = fp["region_span"]
        text = lines[at - 1].decode("utf-8", "replace").strip()
        moved = f" (was line {was})" if was != at else ""
        # The line is printed so a wrong anchor is seen at once: a register restamped
        # whole-file for months may cite a line the code has long left.
        print(f"  anchored at line {at}{moved}, lines {at - above}-{at + below}: "
              f"{text[:100]}{'…' if len(text) > 100 else ''}\n"
              f"  not the defect's line? `{CLI} restamp {fid} --line <N>`")
    return 0


# How many times a defect class must repeat before a list of fixes stops being the answer.
#
# The number is not invented: it is the rule of the review's roots map, derived from
# practice — "the second repeat is written as a row, the third is closed by a guard". The
# reason is simple: two instances may still be a coincidence, the third means the defect is
# produced by the shape of the code, not by inattention, and the next one will appear by
# itself. Audit firms do the same under the name variant analysis: from a finding they write
# a static-analysis rule and run it over the whole codebase.
ROOT_RULE_AT = 3


def roots_of(rows: list[dict], block_id: str | None = None) -> dict[str, list[dict]]:
    """Findings grouped by root. Without a root they are not grouped."""
    out: dict[str, list[dict]] = {}
    for f in rows:
        if block_id and f.get("block") != block_id:
            continue
        if f.get("status") in ("rejected", "duplicate"):
            continue
        root = (f.get("root") or "").strip()
        if root:
            out.setdefault(root, []).append(f)
    return out


def root_guards(items: list[dict]) -> dict[str, list[str]]:
    """The guards a root's instances carry: guard → the ids it is recorded on, in the order
    of the instances; the key "" collects the instances with no guard at all.

    A guard is recorded per finding (issue #28), so a root has as many guards as its
    instances say, not one: reading the first one found and calling it the root's guard is
    how three fixers' guards came to stand for findings they stay green on.
    """
    out: dict[str, list[str]] = {}
    for f in items:
        out.setdefault((f.get("rule") or "").strip(), []).append(f.get("id", "?"))
    return out


def dup_problem(fid: str, target: str, rows: list[dict]) -> str | None:
    """A duplicate must point at ANOTHER EXISTING finding that has not itself dropped out.

    Otherwise a typo in `--dup-of` removes a live defect from the remaining work without
    leaving a single record in the register that carries it.
    """
    if target == fid:
        return f"finding {fid} is marked as a duplicate of itself"
    hit = next((r for r in rows if r.get("id") == target), None)
    if hit is None:
        return f"finding {fid}: duplicate of nonexistent {target} — a typo in the id?"
    if hit.get("status") in ("duplicate", "rejected"):
        return (f"finding {fid}: duplicate of {target}, which is itself {hit.get('status')} — "
                f"the defect stays in no live record; point at the primary one")
    return None


def rule_problem(rule: str) -> str | None:
    """A guard must exist: a typo in the path made the class "closed" without a rule.

    The form `repository:path/to/file` is a guard in a neighbouring repository; only the
    form is checked, as with an external fix commit. The suffixes `::test`, `#anchor` and
    `:line` are cut off. A linter rule is given by the file where it is enabled.
    """
    rule = (rule or "").strip()
    head, sep, tail = rule.partition(":")
    # The external form is recognised strictly: the path right after the colon and looking
    # like a file. Otherwise "eslint: no-x" — a rule name without a file — would pass as
    # the repository "eslint".
    if sep and re.fullmatch(r"[\w-]+", head) and re.fullmatch(r"[^\s:]*[./][^\s]*", tail):
        return None
    path = re.split(r"::|#", rule)[0]
    path = re.sub(r":\d+$", "", path).strip().rstrip("/")
    if not path:
        return "the guard is empty"
    if not named_file(path):
        return (f"guard `{rule}`: no such file in the repository — a typo in the path or "
                f"the guard was deleted; give the path to the test, the linter rule or the CI gate")
    return None
