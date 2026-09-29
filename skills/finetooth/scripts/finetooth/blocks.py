"""Blocks: their definition, their state, their stamps and what a pass has read."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from .base import SKILL_DIR, die
from .git import git_files
from .workspace import BLOCKS_FILE, REVIEW, STATE_FILE, load_json
from .model import BLOCK_FIELDS, HYPOTHESIS_HEADING, READABLE_LINES, READ_LINES_KEY, READ_STATUSES
from .text import LIST_MARK, section_items_full
from .fingerprint import file_lines, file_sha


def ceiling_block(b: dict) -> bool:
    """Does the readability ceiling apply to the block: readable, with files."""
    return bool(b.get("paths")) and b.get("proof", "read") == "read"


def read_under_ceiling(s: dict, limit: int) -> bool:
    """Was the block read, and read at a size within the ceiling?"""
    n = s.get(READ_LINES_KEY)
    return s.get("status") in READ_STATUSES and isinstance(n, int) and n <= limit


def block_sha(b: dict) -> str:
    """Fingerprint of what the block gets to work on: the set of files plus their contents.

    Computed by the same rules the prompt is assembled with (exclusions subtracted),
    otherwise the fingerprint would guard a different set than the one the agent read.
    """
    defn = blocks()
    excluded = git_files([e["pattern"] for e in defn.get("exclusions", [])])
    files = sorted(git_files(b.get("paths", [])) - excluded)
    h = hashlib.sha256()
    for rel in files:
        h.update(rel.encode("utf-8"))
        h.update((file_sha(rel) or "").encode("utf-8"))
    return h.hexdigest()[:16]


def manifest_path(b: dict) -> Path:
    return REVIEW / "blocks" / f"{b['id']}-{b['slug']}.md"


def hypotheses_sha(b: dict) -> str:
    """Fingerprint of the hypotheses' TEXT, not their count.

    A hypothesis is identified by its ordinal number, and the number survives an edit:
    reorder the items or replace a question with another one of the same count — the
    verdict "H1.2 checked", given to the old question, is silently credited to the new one.
    The text fingerprint is taken in the same place as the file fingerprint, and an edit of
    the manifest after verification is caught the same way as an edit of the code.
    """
    m = manifest_path(b)
    items = section_items_full(m.read_text(encoding="utf-8"), HYPOTHESIS_HEADING) if m.exists() else []
    norm = [re.sub(r"\s+", " ", LIST_MARK.sub("", t)).strip() for t in items]
    return hashlib.sha256("\n".join(norm).encode("utf-8")).hexdigest()[:16]


def refs_sha(b: dict) -> str:
    """Fingerprint of the CONTEXT: the `ref_paths` files the prompt gives the block for reference."""
    defn = blocks()
    excluded = git_files([e["pattern"] for e in defn.get("exclusions", [])])
    own = git_files(b.get("paths", []))
    h = hashlib.sha256()
    for rel in sorted(git_files(b.get("ref_paths", [])) - excluded - own):
        h.update(rel.encode("utf-8"))
        h.update((file_sha(rel) or "").encode("utf-8"))
    return h.hexdigest()[:16]


def stamp(b: dict, s: dict) -> None:
    """Record WHAT was reviewed: the block's files, the context and the questions that were answered."""
    s["reviewed_sha"] = block_sha(b)
    s["refs_sha"] = refs_sha(b)
    s["hypotheses_sha"] = hypotheses_sha(b)


def changed_since_review(b: dict, seen: str) -> bool:
    return block_sha(b) != seen


def check_definition(defn: dict) -> None:
    example = SKILL_DIR / "assets" / "blocks.example.json"
    # `review_id` is read on the one path that WRITES the state, so a definition without it
    # passed every other command and answered `init` — the first command anyone runs — with
    # a traceback.
    if not isinstance(defn.get("review_id"), str) or not defn["review_id"].strip():
        die(f"docs/review/blocks.json: no `review_id` — it is the review's name in "
            f"docs/review/state.json, written there by `init`; give it any short string "
            f"(the example is {example})")
    if not isinstance(defn.get("blocks"), list):
        die(f"docs/review/blocks.json: the `blocks` field must be an array — "
            f"the example is {example}")
    # The exclusion list is walked as `e["pattern"]` by six commands: an entry written with
    # `reason` alone, or the whole list written as one object, reached git as a traceback.
    if "exclusions" in defn and not isinstance(defn["exclusions"], list):
        die(f"docs/review/blocks.json: the `exclusions` field must be an array of "
            f"`{{\"pattern\": …, \"reason\": …}}` objects — the example is {example}")
    for i, e in enumerate(defn.get("exclusions", []), 1):
        if not isinstance(e, dict) or not isinstance(e.get("pattern"), str) or not e["pattern"].strip():
            die(f"docs/review/blocks.json: exclusion #{i} has no `pattern` — an exclusion is "
                f"`{{\"pattern\": \"dist/**\", \"reason\": \"why\"}}`, and the pattern is what "
                f"is subtracted from the blocks' files; the example is {example}")
    # The declared partial scope (see `review_scope`). Its SHAPE is checked here, where every
    # command meets it: a scope written as a bare list or with an empty `paths` would reach
    # `git_files`, which reads an empty list as "no files", and the coverage gate would pass
    # over nothing at all. Whether the patterns match and the reason is given is `check`'s
    # business — those are states to refuse, not definitions to die on.
    if "scope" in defn:
        sc = defn["scope"]
        if not isinstance(sc, dict) or not isinstance(sc.get("paths"), list) or not sc["paths"] \
                or not all(isinstance(p, str) and p.strip() for p in sc["paths"]):
            die(f"docs/review/blocks.json: the `scope` field must be an object "
                f"`{{\"paths\": [\"src/api/**\"], \"reason\": \"why only this part\"}}` with at "
                f"least one pattern — it declares that the review covers only these files; "
                f"remove the field for a whole-repository review")
    seen: set[str] = set()
    for i, b in enumerate(defn["blocks"], 1):
        where = f"block {b['id']}" if isinstance(b, dict) and b.get("id") else f"block #{i}"
        if not isinstance(b, dict):
            die(f"docs/review/blocks.json: {where} is not an object")
        for field in BLOCK_FIELDS:
            value = b.get(field)
            if field == "phase":
                if not isinstance(value, int) or isinstance(value, bool):
                    die(f"docs/review/blocks.json: {where} has no whole-number `phase` — "
                        f"the phase orders the array (1 cross-cutting, 2 vertical slices, "
                        f"3 live-system); the example is {example}")
                continue
            if not isinstance(value, str) or not value.strip():
                die(f"docs/review/blocks.json: {where} has no `{field}` — every block needs "
                    f"{', '.join(BLOCK_FIELDS)}; the example is {example}")
        # Both lists go to git as pathspecs. Written as one string they were spliced into
        # the pathspec list a character at a time; an entry that is not a string reached
        # git as an argument it cannot pass.
        for field in ("paths", "ref_paths"):
            value = b.get(field)
            if value is None:
                continue
            if not isinstance(value, list) or not all(isinstance(p, str) and p.strip() for p in value):
                die(f"docs/review/blocks.json: {where} has `{field}` that is not a list of "
                    f"patterns — write it as [\"src/api/**\"] even for a single one; "
                    f"the example is {example}")
        # `id` and `slug` become file names (docs/review/blocks/<id>-<slug>.md and the
        # reports): a separator in them would write the manifest outside docs/review/.
        for field in ("id", "slug"):
            if "/" in b[field] or "\\" in b[field] or b[field] in (".", ".."):
                die(f"docs/review/blocks.json: {where} has `{field}` = `{b[field]}` — "
                    f"it becomes part of a file name under docs/review/, so it cannot "
                    f"contain a path separator")
        if "sweep" in b and not (isinstance(b["sweep"], list)
                                 and all(isinstance(x, str) and x for x in b["sweep"])):
            die(f"docs/review/blocks.json: {where} has `sweep` that is not a list of path "
                f"patterns — the files the acceptance criterion requires to enumerate over")
        if b["id"] in seen:
            die(f"docs/review/blocks.json: two blocks share the id `{b['id']}` — the id is "
                f"the block's name in the state, in the findings and in the reports")
        seen.add(b["id"])


def blocks() -> dict:
    defn = load_json(BLOCKS_FILE)
    check_definition(defn)
    return defn


def block_index(defn: dict) -> dict[str, dict]:
    return {b["id"]: b for b in defn["blocks"]}


def state() -> dict:
    return load_json(STATE_FILE)


def state_text(st: dict, keep: str) -> str:
    """The state as it would be written, with `updated_at` taken from `keep`.

    The stamp says when the state last CHANGED; comparing it against itself would mean
    nothing, so it is the one field excluded from the comparison.
    """
    same = dict(st)
    try:
        same["updated_at"] = json.loads(keep).get("updated_at")
    except (ValueError, AttributeError):
        return ""
    return json.dumps(same, ensure_ascii=False, indent=2) + "\n"


def phase_name(phase: int) -> str:
    return {
        0: "0 · preparation",
        1: "1 · cross-cutting invariants",
        2: "2 · vertical slices",
        3: "3 · live-system checks",
    }.get(phase, str(phase))


def next_block(defn: dict, st: dict) -> dict | None:
    """The first block, in definition order, that is neither closed nor blocked."""
    for b in defn["blocks"]:
        s = st["blocks"].get(b["id"], {}).get("status", "todo")
        if s not in ("closed", "blocked"):
            return b
    return None


def report_path(b: dict, role: str, rnd: int = 1, scope: str | None = None) -> str:
    """Where a role writes its report. Rounds and halves of the fix review get their own
    names — otherwise they are named by hand, and differently every time."""
    base = f"docs/review/reports/{b['id']}-{b['slug']}"
    if role == "fixreview":
        return f"{base}.fixreview-{rnd}{'-' + scope if scope else ''}.md"
    if role == "fix" and rnd > 1:
        return f"{base}.fix-{rnd}.md"
    return f"{base}.{role}.md"


def block_findings_path(b: dict) -> Path:
    return REVIEW / "reports" / f"{b['id']}-findings.jsonl"


def readable_lines() -> int:
    """How many lines a block can honestly hand an agent in one session.

    ⚠️ A number from ONE language. 6000 was derived from runs on TypeScript, and the
    median change size differs between languages two- to three-fold (826 thousand PRs,
    MSR 2022: Shell 8 lines, Ruby 13, Python 21, TypeScript 35, Java 43), and for Go and
    Rust there is no data at all. This number must not be carried over silently — the
    project sets its own in `blocks.json`, in the `readable_lines` field.
    """
    try:
        return int(blocks().get("readable_lines") or READABLE_LINES)
    except (ValueError, TypeError):
        return READABLE_LINES


def block_lines(pathspecs: list[str]) -> tuple[int, int]:
    """How many files and lines a block has — to tell a block from a promise.

    ⚠️ THE EXCLUDED IS NOT COUNTED. The ceiling measured what the block does not own:
    `coverage_map` subtracts `exclusions`, this count did not, and H13 showed 30 388
    lines, of which 19 181 belonged to `package-lock.json`, excluded back when the blocks
    were set up. The number came out three times the real one and demanded cutting what
    nobody reads anyway. What must be counted is exactly the set the block gets to work on.

    ⚠️ COUNTED BY `file_lines`, not by a second counter of its own. Its own `open()` read
    the disk — so a file living in the index but not laid out (sparse checkout, deleted
    without committing) dropped out of the count, and a binary file was counted as lines,
    which is exactly what `file_lines` was taught not to do.
    """
    defn = blocks()
    excluded = git_files([e["pattern"] for e in defn.get("exclusions", [])])
    files = git_files(pathspecs) - excluded
    return len(files), sum(file_lines(f) or 0 for f in files)
