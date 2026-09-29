"""Hypotheses from the manifest and the verdicts reports give them."""

from __future__ import annotations

import re
from pathlib import Path

from .workspace import REVIEW
from .model import HYPOTHESIS_HEADING, HYPOTHESIS_WORD, VERDICT_ROLES
from .text import CODE_SPAN, LIST_ITEM, quoted_lines, section_items, unquoted
from .blocks import block_findings_path
from .register import finding_id, finding_number, finding_ref, read_draft, unimported_rows


# The section about what was not reviewed lives under different names: "Coverage limits",
# "Not read from the block", "What I did NOT do". Demanding a single heading means forcing
# a finished report to be rewritten for the sake of a word.
LIMITS_HEADING = re.compile(
    r"^#{1,6}\s*.*(ограничени|не проверено|не прочитано|не сделал|не смотрел|не дошёл"
    r"|coverage limit|not read|not checked|not covered|did not|skipped|limitations)",
    re.IGNORECASE,
)
# The instruction text from the hunter template, copied into the report as is, is not a disclosure.
LIMITS_PLACEHOLDER = re.compile(r"обязательный раздел, даже если он короткий|mandatory section, even if (it is )?short", re.IGNORECASE)
# Order matters and the vocabulary is wider than three words: a live report says
# "hypothesis 2 refuted" and "not confirmed", and that is a check too — just with a
# negative outcome, which is worth no less in a review. The gate must understand the
# language reports are actually written in, otherwise it fights the author instead of
# catching silence.
# The verdict labels inside the tool are English (they go into the messages of `check` and
# `hypotheses`); the words in reports are in either of the two languages. A line's verdict
# is the word that stands earlier in it: "not confirmed" starts earlier than the nested "confirmed".
CHECKED, NOT_CHECKED, NOT_APPLICABLE = "checked", "not checked", "not applicable"
VERDICT_WORDS = (
    ("не проверена", NOT_CHECKED), ("не проверял", NOT_CHECKED), ("не удалось проверить", NOT_CHECKED),
    ("not checked", NOT_CHECKED), ("could not check", NOT_CHECKED), ("unchecked", NOT_CHECKED),
    ("not verified", NOT_CHECKED), ("unverified", NOT_CHECKED),
    ("неприменима", NOT_APPLICABLE), ("не применима", NOT_APPLICABLE),
    ("not applicable", NOT_APPLICABLE), ("n/a", NOT_APPLICABLE),
    ("не подтвердилась", CHECKED), ("опровергнута", CHECKED), ("подтвердилась", CHECKED),
    ("подтверждена", CHECKED), ("проверена", CHECKED),
    ("not confirmed", CHECKED), ("refuted", CHECKED), ("disproved", CHECKED),
    ("confirmed", CHECKED), ("checked", CHECKED), ("verified", CHECKED),
)
# The verifier's verdict on a finding — in the role template's vocabulary (confirmed /
# plausible / rejected / duplicate) or in the live language of the report. A table form is
# not demanded: reports are written differently, and a gate that fights the markup stops
# being read. The content is what is demanded.
FINDING_VERDICT = re.compile(
    r"\b(confirmed|plausible|rejected|duplicate)\b|подтвержд|отверг|опроверг|дубл",
    re.IGNORECASE)
# A verdict on COVERAGE, not on the work: "complete" and "полный" say how much of the block
# was reviewed, while "I completed the check" and "проверка завершена" say only that the
# agent stopped. The `\b` after `complete` is the whole difference between the two — without
# it a report whose entire body was "I completed the check of every finding; nothing was
# confirmed" satisfied the gate that exists to demand a statement about what was left
# unreviewed. The Russian side takes every form of `полн-` (полный, полностью, полнота) for
# the same reason the English side takes `completely`: the adjective and the adverb are the
# same statement, and matching only the adjective refused an honest report.
COVERAGE_VERDICT = re.compile(
    r"охват|\bполн\w*|\bнеполн\w*|coverage|complete(ly)?\b|incomplete", re.IGNORECASE)
# The template line "Complete / incomplete — …", left as is, is a question, not a decision.
COVERAGE_PLACEHOLDER = re.compile(r"полн\w*\s*/\s*неполн|complete\s*/\s*incomplete", re.IGNORECASE)


def verify_report_problem(rep: Path, has_findings: bool) -> str | None:
    """A verifier report that in substance is not there: empty, headings only, not a single verdict.

    The verdict on EACH finding is not checked here, and that is not an omission: the
    register numbers (H1-003) are handed out by `import` after verification, the report
    does not and cannot have them. The verdict on each finding is the `confidence` field of
    its record, which the verifier rewrites in the final findings file, and `check`
    demands it of every one.

    The file's existence proved only that the file was created: an empty `*.verify.md`
    alongside a full hunter report moved the block to `verified` without an independent check.
    A file full of quotations is that same empty file: the template's example restated
    inside a fence verifies nothing and states nothing, so what the gate weighs is what the
    report SAYS — headings and quotations are not it.
    """
    body = [ln for ln in unquoted(rep.read_text(encoding="utf-8").splitlines())
            if ln.strip() and not ln.lstrip().startswith("#")]
    if not body:
        return (f"verifier report {rep.name} is empty — there is a file, there is no verification; "
                f"each finding needs a verdict, the block needs a coverage state, and both as "
                f"ordinary lines: a fenced, indented, `>`-quoted or commented-out block is an example")
    text = "\n".join(body)
    if has_findings and not FINDING_VERDICT.search(text):
        return (f"verifier report {rep.name} has no verdict on any finding — "
                f"confirmed / plausible / rejected / duplicate with reasoning, as an "
                f"ordinary line and not inside a fence or a quotation")
    # Coverage is a separate question, not replaced by verdicts: what was found says
    # nothing about what remained unreviewed.
    if not COVERAGE_VERDICT.search(
            "\n".join(ln for ln in body if not COVERAGE_PLACEHOLDER.search(ln))):
        return (f"verifier report {rep.name} has no coverage verdict — is it complete and "
                f"what is left, as an ordinary line and not inside a fence or a quotation")
    return None


VERDICT_VOCABULARY = {w for w, _ in VERDICT_WORDS}


def unquote_verdicts(line: str) -> str:
    """Blank out code spans that QUOTE a verdict word instead of giving one.

    A report writes about its own vocabulary: "the report says `not checked` but I did check
    it", "`checked` is only a code span here", "the `n/a` token in a path is handled". Every
    one of those scored the quoted word as the line's verdict, and the wrong answer reached
    `hypotheses`, `check` and the summary with no gate going red.

    Only a span whose WHOLE content is a vocabulary word is blanked. A span that carries a
    whole clause is prose in monospace — `` `H1.1 — checked: proven by running it` `` is how
    a real report writes its verdicts, and it must keep working.
    """
    def one(m: re.Match) -> str:
        inner = m.group(1).strip().strip(".,:;!?").strip().lower()
        return " " if inner in VERDICT_VOCABULARY else m.group(0)
    return CODE_SPAN.sub(one, line)


def line_verdict(line: str) -> str | None:
    """A line's verdict is the word that stands EARLIER in it, not the first by the vocabulary.

    "Checked by code, all nine … Not checked with a live request" is "checked" with a
    reservation. Searching in vocabulary order found "not checked" anywhere in the line and
    declared the hypothesis unchecked. The negation is not lost either: the negated form
    ("not checked") starts earlier than the bare word ("checked") nested inside it.
    """
    low = unquote_verdicts(line).lower()
    hits = [(i, v) for w, v in VERDICT_WORDS if (i := verdict_word_at(low, w)) >= 0]
    return min(hits)[1] if hits else None


def verdict_word_at(low: str, word: str) -> int:
    """Position of a verdict word, or -1. `n/a` is a sign, not letters: found inside a path
    (`curation/adapter.ts`), it declared a checked hypothesis "not applicable"."""
    if word == "n/a":
        m = re.search(r"(?<![\w/])n/a(?![\w/])", low)
        return m.start() if m else -1
    return low.find(word)


def hypotheses(block_id: str, manifest: Path) -> list[str]:
    """The block's hypothesis identifiers: H1.1, H1.2 … in the order of the items in the manifest."""
    if not manifest.exists():
        return []
    items = section_items(manifest.read_text(encoding="utf-8"), HYPOTHESIS_HEADING)
    return [f"{block_id}.{i}" for i in range(1, len(items) + 1)]


def verdicts_in(text: str, block_id: str = "") -> dict[str, str]:
    """Verdicts on hypotheses: "H1.3 — not checked: …" or "hypothesis 3 refuted".

    The FIRST mention is taken — one rule for all forms of writing. A contradiction inside
    a report is not resolved by line order but caught by `verdict_conflicts`.
    """
    return {h: vs[0] for h, vs in verdict_mentions(text, block_id).items()}


def verdict_conflicts(text: str, block_id: str) -> dict[str, list[str]]:
    """Hypotheses to which one and the same report gives different verdicts."""
    return {h: sorted(set(vs)) for h, vs in verdict_mentions(text, block_id).items()
            if len(set(vs)) > 1}


def verdict_mentions(text: str, block_id: str = "") -> dict[str, list[str]]:
    """All verdicts on each hypothesis in order of appearance."""
    out: dict[str, list[str]] = {}
    for h, verdict, _ in verdict_records(text, block_id):
        out.setdefault(h, []).append(verdict)
    return out


def verdict_records(text: str, block_id: str = "") -> list[tuple[str, str, int]]:
    """Every verdict the parser reads, as (hypothesis, verdict, index of its line in the
    text), in order of appearance. `verdict_mentions` is this list folded by
    hypothesis; the line index is what a gate needs to read what the verdict SAYS beyond
    its word (see `confirmed_without_finding`). The rules are the parser's, unchanged
    (issue #17): nothing here decides differently what a verdict is."""
    out: list[tuple[str, str, int]] = []
    plain = re.compile(r"(?:гипотез\w*|hypothesis)\s*[№#]?\s*(\d+)", re.IGNORECASE)
    # The identifier is taken from the block's REAL name, not guessed by shape: more than
    # half of the blocks of the real review have a name with a letter suffix (`V1d`,
    # `H13e`), and the regex "letters, digits, dot" did not catch them — the verdicts of
    # such blocks counted as missing, and they passed only through the fallback forms.
    tagged = re.compile(rf"\b({re.escape(block_id)}\.\d+)\b") if block_id else None
    in_hypotheses = False
    hypotheses_depth = 0
    table_about_hypotheses = False
    prev_was_row = False
    lines = text.split("\n")
    for at, (line, fenced) in enumerate(zip(lines, quoted_lines(lines, "quoted"))):
        # A fenced block is an EXAMPLE, not an answer. The role template hands the agent the
        # shape of a verdict line inside a ```markdown fence, with the block id already
        # substituted; a report that quotes that skeleton and answers nothing closed every
        # hypothesis of the block and `check` printed "review state is consistent".
        if fenced:
            prev_was_row = False
            continue
        if line.startswith("#"):
            level = len(line) - len(line.lstrip("#"))
            if HYPOTHESIS_HEADING.match(line):
                in_hypotheses, hypotheses_depth = True, level
            elif in_hypotheses and level <= hypotheses_depth:
                in_hypotheses = False
        is_row = line.lstrip().startswith("|")
        if is_row and not prev_was_row:
            # A table counts as a table of hypothesis verdicts only when it SAYS SO — its
            # first row names hypotheses. Reading a bare first data row ("| 1 | … |") as a
            # header too made every numbered table in the report a verdict table: the
            # gate→test→mutation table the acceptance criterion itself asks for closed
            # hypotheses 1 and 2 with the verdicts of rows 1 and 2. A header-less summary of
            # hypotheses is still read — under the "Hypotheses" heading, where it belongs.
            table_about_hypotheses = bool(HYPOTHESIS_WORD.search(line))
        prev_was_row = is_row
        verdict = line_verdict(line)
        if not verdict:
            continue
        if tagged:
            for token in tagged.findall(line):
                out.append((token, verdict, at))
        if not block_id:
            continue
        # The free form is bound to the block whose report we are reading: "hypothesis 2"
        # in the H15 report is H15.2, and there is no point demanding the author rewrite it as an ID.
        for n in plain.findall(line):
            out.append((f"{block_id}.{n}", verdict, at))
        # The summary table "| # | hypothesis | outcome |" — the way a hypotheses report is
        # written most often: the number stands in the first cell, the verdict in the last,
        # and the word "hypothesis" is not in the line at all. Without parsing the table the
        # gate would demand a finished report be rewritten for the sake of form, adding
        # nothing to its content.
        if is_row and (in_hypotheses or table_about_hypotheses):
            first = line.strip().strip("|").split("|")[0].strip()
            if first.isdigit():
                out.append((f"{block_id}.{first}", verdict, at))
    return out


# A confirmed hypothesis is a defect, and a defect the review knows of is a finding. The recall
# measurement (finetooth-hq, experiments/2026-09-recall: P2 of the pilot and half the partial
# hits of phases 2 and 3) lost found defects in one way above all: the hunter confirmed the
# hypothesis — in the hypotheses section, in the acceptance table, in a live check — and never
# wrote it up, so the register, the fix gate and the summary never saw it. The words are the
# parser's own affirmative confirmations, taken from VERDICT_WORDS, not a second vocabulary.
CONFIRM_WORDS = tuple(w for w, v in VERDICT_WORDS
                      if v == CHECKED and ("подтвер" in w or "confirm" in w)
                      and not w.startswith(("не ", "not ")))
# A confirmation word is negated only when the negation is ITS OWN: the negator stands right
# before the word, or right before the auxiliaries of the word's own verb phrase — "не
# подтвердилась бы", "не была подтверждена", "не до конца подтверждена", "was not confirmed",
# "could not be confirmed", "has not yet been confirmed", "wasn't confirmed". A list of whole
# phrases missed most of those (Codex on #60). A window of the few words before the word
# caught them, and caught as well the negator of a neighbouring clause: "there is no guard,
# confirmed by running it", "узды нет, подтверждена потеря флага", "no doubt confirmed by the
# run" — the commonest shape of a hunter's proof states an absence first — and those
# confirmations went unrefused (fix review of the 0.8.0 candidate). So the walk back from the
# word skips only the auxiliaries and degree words of its own phrase and stops at anything
# else: a punctuation mark ends the phrase ("нет, подтверждена"), a word of another phrase
# ("doubt", "guard") means the negator negates that word, not the confirmation. It looks only
# backwards: "подтверждена, не только X, но и Y" is still a confirmation. A confirmation word
# inside a longer word ("unconfirmed") is not the word; emphasis and code marks are
# transparent ("**not** confirmed").
CONFIRM_NEGATORS = frozenset({"не", "ни", "нельзя", "нет", "not", "no", "never", "cannot",
                              "failed"})
# The words a negation may stand behind and still be the confirmation's own: the auxiliaries,
# modals and degree words of the negated forms above, in both languages. A word missing here
# errs towards refusing (the gate asks for a finding, the hunter rewords), never towards
# silence.
CONFIRM_PHRASE_WORDS = frozenset({
    "be", "been", "being", "is", "are", "was", "were", "am", "has", "have", "had", "do", "does",
    "did", "can", "could", "will", "would", "shall", "should", "may", "might", "must", "to",
    "get", "got", "yet", "ever", "even", "fully", "entirely", "completely", "really",
    "actually", "quite",
    "был", "была", "было", "были", "быть", "будет", "будут", "бы", "б", "ещё", "еще", "пока",
    "даже", "до", "конца", "полностью", "вполне", "окончательно", "вообще"})
CONFIRM_AT = re.compile(rf"(?<!\w)(?:{'|'.join(re.escape(w) for w in CONFIRM_WORDS)})(?!\w)")
PHRASE_TOKEN = re.compile(r"[\w'’]+|[^\w\s*`]")


def negated_before(low: str, at: int) -> bool:
    """The confirmation word at `at` is negated by its own phrase: a negator right before it,
    or right before the auxiliaries and degree words that lead up to it (see
    CONFIRM_PHRASE_WORDS). A punctuation mark or any other word in between ends the search."""
    for tok in reversed(PHRASE_TOKEN.findall(low[:at])):
        if tok in CONFIRM_NEGATORS or tok.endswith(("n't", "n’t")):
            return True
        if tok not in CONFIRM_PHRASE_WORDS:
            return False
    return False


def says_confirmed(passage: str) -> bool:
    """The verdict CONFIRMS the hypothesis: its passage (`verdict_passage` — the same lines
    its finding id is read from) carries an affirmative confirmation word that no negation of
    its own phrase turns round (`negated_before`). "проверена и подтверждена как дефект"
    confirms, and so does "there is no guard, confirmed by running it"; "refuted: the guard
    is there", "was not confirmed" and "не подтвердилась бы" do not. A word quoted alone in
    backticks is a quotation, as for the parser."""
    low = unquote_verdicts(passage).lower()
    return any(not negated_before(low, m.start()) for m in CONFIRM_AT.finditer(low))


def verdict_passage(lines: list[str], at: int, starts: set[int]) -> str:
    """The verdict line and what continues it: the rest of its paragraph (a hard-wrapped
    verdict — a phase-3 hunter wrote "P1.1 — проверена: подтверждена …" over nine lines and
    named P1-001…P1-006 on the last) and the sub-items under it (the templates say proof
    written indented under the verdict belongs to it). It ends at a blank line, a quotation,
    a heading, a table row, another verdict line (`starts`) or a list item no deeper than the
    verdict's own line. What is quoted is asked of the one tracker, `quoted_lines`."""
    fenced = quoted_lines(lines, "quoted")
    own = len(lines[at]) - len(lines[at].lstrip())
    out = [lines[at]]
    for j in range(at + 1, len(lines)):
        ln = lines[j]
        if (fenced[j] or not ln.strip() or j in starts or ln.lstrip().startswith(("#", "|"))
                or (LIST_ITEM.match(ln) and len(ln) - len(ln.lstrip()) <= own)):
            break
        out.append(ln)
    return "\n".join(out)


def confirmed_without_finding(text: str, block_id: str, known: set[str],
                              block_ids: list[str] | None = None) -> list[tuple[str, list[str]]]:
    """Confirmed hypotheses whose verdict names no finding in `known`: (hypothesis, the ids
    the verdict does name that `known` does not hold). Read on the parser's records — the
    same verdicts `check` and `hypotheses` see — and only on "checked" ones: "not checked:
    it would be confirmed only on a live system" confirms nothing."""
    lines = text.split("\n")
    ref = finding_ref(block_ids or [block_id])
    out: list[tuple[str, list[str]]] = []
    seen: set[tuple[str, int]] = set()
    records = verdict_records(text, block_id)
    starts = {at for _, _, at in records}
    for h, verdict, at in records:
        if verdict != CHECKED or (h, at) in seen:
            continue
        seen.add((h, at))
        # One passage for both questions: the word that confirms and the id that names the
        # finding are looked for over the same lines. Asked of the verdict line alone, a
        # confirmation hard-wrapped onto the next line, or written in the proof indented under
        # it (as the templates allow), was no confirmation at all, while its id was read there.
        passage = verdict_passage(lines, at, starts)
        if not says_confirmed(passage):
            continue
        named = ref.findall(passage)
        if any(n in known for n in named):
            continue
        out.append((h, list(dict.fromkeys(n for n in named if n not in known))))
    return out


def finding_ids_for(b: dict, register: list[dict]) -> set[str]:
    """The finding ids a verdict of block `b` may name: every id of the register, every id
    its draft holds, and the ids the draft's unrecorded rows will get on `import` — numbered
    as `import --append` numbers them, from the block's highest recorded number on, which is
    the id the hunter's prompt told it to start from (`{{NEXT_ID}}`). An unreadable draft
    adds nothing: `findings/draft-not-imported` names that one."""
    known = {f["id"] for f in register if isinstance(f.get("id"), str)}
    src = block_findings_path(b)
    try:
        rows = [r for _, r in read_draft(src)] if src.exists() else []
    except ValueError:
        return known
    known |= {r["id"] for r in rows if isinstance(r, dict) and isinstance(r.get("id"), str)}
    taken = [n for f in register if (n := finding_number(b["id"], f.get("id"))) is not None]
    start = max(taken, default=0) + 1
    known |= {finding_id(b["id"], start + k) for k in range(len(unimported_rows(rows, register)))}
    return known


def verdicts_for(b: dict) -> dict[str, str]:
    """Verdicts on the block's hypotheses, where the verifier's word overrides the hunter's.

    The verifier's prompt explicitly demands overriding someone else's verdict with its
    own, with an explanation. While the reports were glued into one text, the hunter came
    first, and `setdefault` kept its verdict forever: the verifier could write "not
    checked", and the tool kept showing "checked". We read by role and overlay in order
    of seniority.
    """
    out: dict[str, str] = {}
    for p in verdict_reports(b):
        out.update(verdicts_in(p.read_text(encoding="utf-8"), b["id"]))
    return out


def verdict_reports(b: dict) -> list[Path]:
    """The block's reports that carry hypothesis verdicts, in VERDICT_ROLES order — the files
    every reader of a verdict opens, so no gate reads fewer of them than the parser does."""
    stem = REVIEW / "reports" / f"{b['id']}-{b['slug']}"
    paths = []
    for role in VERDICT_ROLES:
        paths.append(Path(f"{stem}.{role}.md"))
        if role == "fix":
            # later fixer passes (prompt --role fix --round N) write .fix-N.md — same verdicts
            later = stem.parent.glob(f"{stem.name}.fix-*.md")
            rounds = [(int(q.name[len(stem.name) + 5:-3]), q) for q in later
                      if q.name[len(stem.name) + 5:-3].isdigit()]
            paths += [q for _, q in sorted(rounds)]
    return [p for p in paths if p.exists()]
