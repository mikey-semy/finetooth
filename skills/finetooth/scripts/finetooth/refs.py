"""References to finding ids left in the code, docs and summaries."""

from __future__ import annotations

import re

from .git import git
from .workspace import SUMMARY_DEFAULT, SUMMARY_HTML_DEFAULT
from .register import findings
from .report.summary import SUMMARY_MARK
from .report.html import SUMMARY_HTML_MARK


def summary_files() -> list[str]:
    """Tracked files `summary` wrote: the two default paths, and a file written with `--out`
    anywhere else — recognised by its machine line at the start of a line (Markdown) or its
    generator tag in the head (HTML), as it is written and nowhere else. The tool's own source
    names both marks too, but never at the start of a line."""
    found = git("grep", "-l", "-I", "--full-name", "-E",
                # POSIX ERE, not Python's: `re.escape` writes `\-` and `\ `, which ERE leaves
                # undefined. Neither mark holds an ERE metacharacter, so they go in as they are.
                "-e", "^" + SUMMARY_MARK + r"\{",
                "-e", "^<!doctype html>.*" + SUMMARY_HTML_MARK).fields
    return sorted({SUMMARY_DEFAULT, SUMMARY_HTML_DEFAULT, *found})


def review_refs() -> list[tuple[str, int, str, str]]:
    """Places in the tracked tree, outside `docs/review/`, that name a finding of this
    register by its id: (path, line, id, text). The ids die with the review directory; a
    comment "see H1-012" then points nowhere. The kit author's review found about forty such
    references by hand; the register knows the ids exactly, so here there is no guessing."""
    ids = sorted({f.get("id") for f in findings() if f.get("id")})
    if not ids:
        return []
    # A grep record is `path NUL line NUL text` — raw and unambiguous, which is why the
    # fields are read with `records` and not split on `:`, a character a path may hold.
    args = ["grep", "-n", "-I", "-w", "-F", "--full-name"]
    for fid in ids:
        args += ["-e", fid]
    # The summary is excluded by the same rule as the review directory: it is the register
    # rendered for a reader, and naming the ids is its whole point. `summary` wrote it and
    # `check` then called every row a reference in the code (#46).
    args += ["--", ".", ":(exclude)docs/review/**",
             *(f":(exclude,literal){p}" for p in summary_files())]
    hits = []
    for record in git(*args).records:
        # A record git prints short (no line number for some reason) is not worth a
        # traceback: the fields that are there are read, the rest come out empty.
        path, num, text = (record + ["", ""])[:3]
        for fid in ids:
            if re.search(rf"(?<![\w-]){re.escape(fid)}(?![\w-])", text):
                hits.append((path, int(num) if num.isdigit() else 0, fid, text.strip()))
    return hits
