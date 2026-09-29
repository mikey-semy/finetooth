"""Reading markdown the way a report is read: quoted versus said, sections, list items."""

from __future__ import annotations

import html
import re


def h(text) -> str:
    """Every piece of text from the register, the journal or git goes through here: a claim
    holding `<script>` or `&` is text on the page, not markup."""
    return html.escape(str(text), quote=True)


# A fence opens with three or more backticks OR three or more tildes and closes with at
# least as many marks of the SAME character and nothing after them. Both forms are ordinary
# markdown, and a report writes `~~~` exactly when its example itself contains backticks —
# which an example of this kit's own report always does.
# ONE tracker for the whole tool: while every parser had its own, `demote` pushed a heading
# inside a tilde fence down a level, and `section_body` cut the manifest's hypotheses short
# at a `# comment` inside one — two of four hypotheses silently vanished from the count and
# from the fingerprint.
FENCE = re.compile(r"^(\s*)(`{3,}|~{3,})(.*)$")
# A fence is one of FOUR ways markdown quotes an example, and a report uses all four: the
# fence was closed first, and a hypothesis verdict restated as an indented example or
# quoted from the template with `>` still closed a hypothesis nobody had answered.
# A blockquote at any indentation — inside a list item a quote is indented with it.
BLOCKQUOTE = re.compile(r"^\s*>")
# A list marker, so that a nested item is not read as indented code: inside a list item
# the code column moves to the item's own content column, four spaces further in
# (CommonMark 4.4 and 5.2). Without this, every sub-item of a hypothesis became an example.
LIST_OPEN = re.compile(r"^(\s*)([-*+]|\d+[.)])(\s+)")
# Four spaces past the enclosing content column — the CommonMark indented code block.
CODE_INDENT = 4
# A fence OPENS at any indentation and CLOSES only within three spaces of the column it
# opened at. Measured from the list's content column, an opening fence four spaces in was
# not seen and its closing fence opened a new one that swallowed a manifest (round 3);
# closing at any indentation let an indented example INSIDE a fence close it and leak its
# verdicts as the report's own (round 4). Anchoring the close to the opener closes both.
FENCE_SLACK = CODE_INDENT - 1
COMMENT_OPEN, COMMENT_CLOSE = "<!--", "-->"


def quoted_lines(lines: list[str], unclosed: str = "text") -> list[bool]:
    """For every line: is it QUOTED rather than said — an example, not the report's answer.

    Four forms, all of them ordinary markdown and all of them written by real reports: a
    fenced block, an indented code block, a blockquote, an HTML comment. ONE tracker for
    the whole tool: while every parser had its own idea of what a code block is, `demote`
    pushed a heading inside a tilde fence down a level and `section_body` cut the manifest's
    hypotheses short at a `# comment` inside one.

    `unclosed` says how to read a fence that never closes: "text" for what DEFINES the work
    (manifests — more hypotheses, more to answer), "quoted" for what REPORTS it (reports —
    fewer verdicts, more to answer). Both directions make the gate stricter, never looser.

    A fence opens at any indentation and closes near the column it opened at (see FENCE). An indented code block cannot
    interrupt a paragraph (a blank line must come first) and it measures its indent from the
    content column of the list item it sits in — otherwise a hypothesis's own
    sub-items, which is how a report writes its proof, would all be read as examples and
    the gate would refuse an honest report.
    """
    if unclosed not in ("text", "quoted"):
        raise ValueError(f"unclosed must be 'text' or 'quoted', not {unclosed!r}")
    return _quoted_pass(lines, frozenset(), unclosed)


def _quoted_pass(lines: list[str], not_fences: frozenset, unclosed: str) -> list[bool]:
    out: list[bool] = []
    in_comment = False
    content_col = 0      # where the innermost open list item's content begins
    prev_blank = True    # an indented code block may only start after a blank line
    char, width, open_col, open_at = "", 0, 0, -1   # the open fence
    for at, ln in enumerate(lines):
        m = FENCE.match(ln) if at not in not_fences else None
        indent = len(m.group(1)) if m else len(ln) - len(ln.lstrip())
        if char:
            out.append(True)
            prev_blank = False
            # The closing fence carries no info string; `~~~` does not close ``` and back.
            if (m and m.group(2)[0] == char and len(m.group(2)) >= width
                    and not m.group(3).strip() and indent <= open_col + FENCE_SLACK):
                char, width = "", 0
            continue
        if m:
            char, width, open_col, open_at = m.group(2)[0], len(m.group(2)), indent, at
            out.append(True)
            prev_blank = False
            if indent == 0:
                content_col = 0     # a fence at the margin closes every open list
            continue
        rest = ln
        if in_comment:
            _, sep, after = ln.partition(COMMENT_CLOSE)
            in_comment = not sep
            rest = after if sep else ""
        while not in_comment and COMMENT_OPEN in rest:
            before, _, tail = rest.partition(COMMENT_OPEN)
            _, sep, after = tail.partition(COMMENT_CLOSE)
            in_comment = not sep
            rest = before + after if sep else before
        # What is left of the line outside the comments decides: a line that is nothing but
        # a comment is a quotation, a sentence with a note after it is still a sentence.
        if rest != ln and not rest.strip():
            out.append(True)
            prev_blank = False
            continue
        if not ln.strip():
            out.append(False)
            prev_blank = True
            continue
        if BLOCKQUOTE.match(ln):
            out.append(True)
            prev_blank = False
            continue
        if prev_blank and indent >= content_col + CODE_INDENT:
            out.append(True)    # indented code: the list context it sits in is untouched
            continue
        out.append(False)
        prev_blank = False
        mark = LIST_OPEN.match(ln)
        if mark:
            content_col = len(mark.group(0))
        elif indent == 0:
            content_col = 0     # a paragraph at the margin closes every open list
    if char and unclosed == "text":
        # A fence that never closes: what it means depends on WHAT is read, and the rule
        # is the same for both — in doubt, the gate goes red. In a MANIFEST it is read as
        # text: swallowed, the remaining hypotheses vanished and `check` went green on one
        # of four (fix review round 4). In a REPORT it stays a quotation: read as text, the
        # template's skeleton inside it closed every hypothesis (fix review round 5).
        return _quoted_pass(lines, not_fences | {open_at}, unclosed)
    return out


def unquoted(lines: list[str], unclosed: str = "quoted") -> list[str]:
    """The lines a text SAYS — its quotations dropped.

    A gate that reads a report's SUBSTANCE must read the report's own words. A verifier
    report whose whole body was the template's example inside a ```markdown fence — nothing
    verified, nothing stated — satisfied every substance gate, and the block stayed
    `verified` with `check` printing "review state is consistent".
    """
    return [ln for ln, quote in zip(lines, quoted_lines(lines, unclosed)) if not quote]


def demote(md: str) -> str:
    """Push an embedded document one heading level down.

    The manifest and the invariants are pasted inside a prompt that has headings
    of its own; left alone, their `#` titles compete with it and the agent reads
    a document with two top levels. Fenced code is left untouched so a `#`
    comment inside an example stays a comment.
    """
    lines = md.split("\n")
    out = []
    for line, inside in zip(lines, quoted_lines(lines)):
        if not inside and line.startswith("#"):
            line = "#" + line
        out.append(line)
    return "\n".join(out)


# A hunk header of `git diff -U0`: the new side starts at `+c` and runs `d` lines, and a
# missing `,d` means one line (git's own convention). `d` = 0 is a pure deletion: no line of
# the new file was written by it.
DIFF_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", re.M)
LIST_ITEM = re.compile(r"^\s{0,3}(?:[-*+]\s+|\d+[.)]\s+)\S")
LIST_MARK = re.compile(r"^(?:[-*+]|\d+[.)])\s+")
CODE_SPAN = re.compile(r"`+([^`]*)`+")


def section_body(md: str, heading: re.Pattern, unclosed: str = "text") -> list[str] | None:
    """The lines of the section under the first matching heading (subheadings are content too).

    None — there is no such section at all; an empty list — the heading is there, nothing under it.
    """
    body: list[str] | None = None
    depth = 0
    lines = md.split("\n")
    for line, fenced in zip(lines, quoted_lines(lines, unclosed)):
        if not fenced and line.startswith("#"):
            level = len(line) - len(line.lstrip("#"))
            if body is None:
                if heading.match(line):
                    body, depth = [], level
                continue
            if level <= depth:
                break
        if body is not None:
            body.append(line)
    return body


def section_items_full(md: str, heading: re.Pattern) -> list[str]:
    """Top-level items IN FULL — with continuation lines and nested sub-items.

    A hypothesis rarely fits in one line: the scenario, the boundary, the expectation are
    written under it, indented. A fingerprint of the first line alone did not notice edits
    to exactly that part.
    """
    lines = section_body(md, heading) or []
    marks = []
    for i, (ln, fenced) in enumerate(zip(lines, quoted_lines(lines))):
        if not fenced and LIST_ITEM.match(ln):
            # TOP-level items are counted: a nested list under a hypothesis is its details,
            # not a new hypothesis, and a list line inside a code block is an example.
            marks.append((i, len(ln) - len(ln.lstrip())))
    if not marks:
        return []
    top = min(ind for _, ind in marks)
    starts = [i for i, ind in marks if ind == top]
    return ["\n".join(lines[a:b]).strip()
            for a, b in zip(starts, starts[1:] + [len(lines)])]


def section_items(md: str, heading: re.Pattern) -> list[str]:
    """First lines of the top-level items — by the same parse as the fingerprint.

    Two parses of one section diverged: the counting one did not know about code blocks,
    and a `# comment` line inside them cut the section short — the hypotheses below were
    lost from the count, although they got into the fingerprint.
    """
    return [item.split("\n", 1)[0].strip() for item in section_items_full(md, heading)]


# The header lines of a unified diff — the only place where `a/` and `b/` in front of a
# path mean "the same file before and after" rather than a directory called `a`. A report
# pastes such a header inside a list item ("- --- a/src/api.ts"), so the marker is looked
# for anywhere on the line and the prefix is read only after it.
DIFF_HEADER = re.compile(r"(?:^|\s)(?:diff --git|---|\+\+\+)\s")


def names_file(text: str, rel: str) -> bool:
    """Does the text name THIS path — not a longer one that merely contains it?

    A plain `in` closed the gate for `src/api.ts` as soon as the report mentioned
    `src/api.ts.snap`; the same held for a `.map`, a `.test.ts` next to a `.ts` and an
    `index.ts` under a longer directory. The occurrence must be a whole path: what follows
    may not continue the name, and what precedes may not be the rest of a longer one.
    A trailing period ("I read src/api.ts.") is a sentence, not a longer path.

    Two prefixes are the SAME path written another way and are accepted: `./`, which an
    agent writes out of habit, and the `a/`, `b/` of a pasted diff header. Refusing them
    left an honest, complete report with no repair but rewriting its paths — and a gate
    that stops accepting honest reports is discovered by the person whose work it refuses.
    They are accepted only where the prefix itself starts a path, so `docs/src/api.ts`
    and `lib/a/src/api.ts` still name files of their own.

    `a/` and `b/` are ALSO ordinary directory names, and they are read as a diff prefix
    only on a diff header line, where they cannot mean anything else. Accepted everywhere,
    they closed the gate for a file nobody had read: a block owning both `src/api.ts` and
    `a/src/api.ts` passed on a report that named only the second.
    """
    tail = r"(?![A-Za-z0-9_-]|[./][A-Za-z0-9_-])"
    said = re.compile(r"(?<![A-Za-z0-9_./-])(?:\./)?" + re.escape(rel) + tail)
    if said.search(text):
        return True
    diffed = re.compile(r"(?<![A-Za-z0-9_./-])[ab]/" + re.escape(rel) + tail)
    return any(diffed.search(line, m.end())
               for line in text.split("\n") if (m := DIFF_HEADER.search(line)))
