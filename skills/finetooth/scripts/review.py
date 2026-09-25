#!/usr/bin/env python3
"""Bookkeeping for the full-project review.

The review spans dozens of blocks and many sessions; a context window does not.
Every piece of state therefore lives on disk and is read back through this tool,
so a session that knows nothing can resume exactly where the previous one stopped.

  definition  docs/review/blocks.json   what the blocks are (static, hand-edited)
  state       docs/review/state.json    how far each block got (mutable)
  findings    docs/review/findings.jsonl one line per finding, rewritten on import

Subcommands are described in main(). Standard library only, no dependencies.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import re
import signal
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

# The skill directory: the tool lives in `<skill>/scripts/`, the role templates in
# `<skill>/references/`, the scaffolds in `<skill>/assets/`.
SKILL_DIR = Path(__file__).resolve().parent.parent


def die(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(2)


# Subcommands and options whose output CARRIES PATHS. For them `-z` is not a nicety:
# without it git C-quotes a non-ASCII name (`"src/\320\272…"`) and separates fields with a
# tab, a colon or a newline — all three legal inside a path. The list is what the tool asks
# git for; `git()` below adds `-z` to such a run itself, so no call site can forget it.
GIT_PRINTS_PATHS = ("ls-files", "--name-only", "--name-status", "--others", "grep")


class GitRun:
    """What one git run produced: the exit code, the output, and the paths already split.

    The two traps of reading git are invisible from a call site — the `-z` that has to be
    asked for whenever the output carries paths, and the NUL split that has to read it
    back. They were therefore repeated at every call site and forgotten at some: three
    places parsed a path list line by line, and a review of a repository with a Cyrillic
    file name recorded paths that do not exist. `git()` is the only place in the tool that
    starts git, so the two belong here and nowhere else.
    """

    def __init__(self, argv: list[str], code: int, out, err: str) -> None:
        self.argv, self.code, self.out, self.err = argv, code, out, err

    @property
    def fields(self) -> list[str]:
        """A NUL-separated stream (`ls-files -z`, `show --name-only -z`, `log … -z`) as the
        raw fields git wrote: no unquoting, no line splitting, empty tails dropped."""
        return [f for f in self.out.split("\0") if f]

    @property
    def records(self) -> list[list[str]]:
        """`git grep -z` records: one per line, the fields inside separated by NUL — the
        separator git uses for grep, where a `:` would be ambiguous inside a path."""
        return [ln.split("\0") for ln in self.out.splitlines() if ln]


def git(*args: str, binary: bool = False, at_root: bool = True) -> GitRun:
    """Run git — THE ONE PLACE in the tool where a process is started.

    Everything the callers used to repeat lives here: the repository to work in, `-z` for
    every run whose output carries paths, and the reading of that output. A call site that
    wants a path list cannot get one that is not NUL-separated, because it does not build
    the command line — that is the whole point of a single entry.

    `at_root=False` is for the one run that asks git where the root IS: there is nothing to
    point `-C` at yet.
    """
    rest = list(args)
    # The decision reads the SUBCOMMAND and the options before `--`, never the data: a file
    # named `grep` turned `hash-object -- grep` into `hash-object -z`, git refused, and the
    # file silently dropped out of the block fingerprint.
    opts = rest[:rest.index("--")] if "--" in rest else rest
    asked = rest[:1] + [a for a in opts[1:] if a.startswith("-")]
    if any(a in GIT_PRINTS_PATHS for a in asked) and "-z" not in opts:
        # After the subcommand and before any `--`: that is where an option belongs.
        rest.insert(1, "-z")
    argv = ["git", *(["-C", str(ROOT)] if at_root else []), *rest]
    try:
        out = subprocess.run(argv, capture_output=True, text=not binary, check=False)
    except OSError as exc:
        # Without git the kit cannot answer a single question. Said once, plainly: the
        # alternative is a traceback out of whichever command the user typed first.
        die(f"git does not run ({exc}) — the kit reads the repository through git: "
            f"install it and repeat the command")
    err = out.stderr if isinstance(out.stderr, str) else out.stderr.decode("utf-8", "replace")
    return GitRun(argv, out.returncode, out.stdout, err)


def repo_root() -> Path | None:
    """Root of the repository UNDER REVIEW — taken from the working directory, not from the file.

    While the tool was copied into the project, the root was asked from git relative to
    the tool's own location. The skill lives anywhere — in `~/.claude/skills/`, in
    `.agents/skills/` of someone else's clone — and a root "from the file" would point at
    the skill directory or even at `~/.claude`, if that is under git: the tool would
    silently write its state there. The repository under review is the one you work in —
    that is the one we ask.
    """
    out = git("rev-parse", "--show-toplevel", at_root=False)
    top = out.out.strip()
    return Path(top) if out.code == 0 and top else None


IN_REPO = repo_root()
ROOT = IN_REPO or Path.cwd()
REVIEW = ROOT / "docs" / "review"

# Version of the kit. The skill is installed as a copy (into the project or the home
# directory), and there is nobody else to ask "what do I have installed" — only itself.
VERSION = "0.7.0"


def default_cli() -> str:
    """How to call THIS instance of the tool — from its real path.

    The string goes only into hints: a refusal must say what to type. It used to be
    written in by the installer, and a copy installed by hand advised a command that did
    not exist. Now the path is known on its own: inside the project — relative, in the
    home directory — via `~`, otherwise absolute. A project that calls the tool its own
    way writes that in the `cli` field of `blocks.json` — and it has to be a command that
    takes the subcommand and its flags after it (`npm run review --`, a shell wrapper).
    `make` is not one: it reads `--role` as its own option, so a project on `make` keeps
    the targets for the everyday commands and leaves `cli` unset.
    """
    here = Path(__file__).resolve()
    for base, prefix in ((ROOT, ""), (Path.home(), "~/")):
        try:
            return f"python3 {prefix}{here.relative_to(base).as_posix()}"
        except ValueError:
            continue
    return f"python3 {here}"


def project_cli() -> str:
    try:
        cli = json.loads((REVIEW / "blocks.json").read_text(encoding="utf-8")).get("cli")
    except (OSError, ValueError, AttributeError):
        cli = None
    return cli.strip() if isinstance(cli, str) and cli.strip() else default_cli()


CLI = project_cli()
BLOCKS_FILE = REVIEW / "blocks.json"
STATE_FILE = REVIEW / "state.json"
FINDINGS_FILE = REVIEW / "findings.jsonl"
FINDINGS_MD = REVIEW / "findings.md"
COVERAGE_FILE = REVIEW / "coverage.tsv"
JOURNAL_FILE = REVIEW / "journal.md"
INVARIANTS_FILE = REVIEW / "invariants.md"
# The human's decisions on a block, one JSON line each (`decide`). A file of its own, not a
# field in state.json: state is "where we are now" and `init --force` rewrites it from
# scratch, while a decision is history the next round's prompt must keep carrying — the
# same append-only shape as the register, next to it.
DECISIONS_FILE = REVIEW / "decisions.jsonl"

# A block moves forward only through these, in this order. `blocked` is the one
# side exit: a block that cannot proceed until another one lands.
STATUSES = ["todo", "running", "hunted", "verified", "triaged", "fixing", "closed", "blocked"]
SEVERITIES = ["critical", "high", "medium", "low"]
CONFIDENCE = ["confirmed", "plausible", "rejected"]
FINDING_STATUS = ["open", "fixed", "rejected", "duplicate", "deferred"]
# The fix gate: the next block does not start while findings of this severity or above
# are open in the blocks already passed. The method finds faster than a project fixes
# (first project: 77 findings on 5 blocks, 9 fixed), and a finding that never reaches a fix
# is debt — a month later the register describes code that no longer exists. "high" by
# default: at "medium" the review stalls on small things and the gate gets bypassed.
# "none" switches the gate off (a project decision, recorded in blocks.json).
FIX_GATE_DEFAULT = "high"
# An open finding older than this is a warning in `check`: the same week the stale-tree
# check uses — a review that lets findings sit longer than its own tree is allowed to lag
# is accumulating the debt the gate exists to stop.
FIX_AGE_DAYS = 7

# `claim` is the headline of a finding: it is what the summary table prints, one
# row per finding, and a row has to be readable at a glance. Evidence, line
# numbers and the reasoning that establishes the defect belong in the block
# report, which is prose and has room for them. Without a cap the field drifts
# into a paragraph — the verifier of the first block pasted its whole
# verification into it — and the table it feeds stops being a table.
#
# The two numbers are the measured ceiling of honest findings, not round figures: over the
# 24 findings of this kit's own first block the claim runs 82…202 characters (median 178,
# 90th percentile 194) and the scenario 452…690 (median 586, 90th percentile 665). Both
# caps sit just above the longest real one — they cut a field that has turned into a
# report, not a field that is thorough.
CLAIM_MAX = 220
SCENARIO_MAX = 700
ROLES = ["hunter", "verify", "fix", "fixreview"]
# The severity from which a fix-review finding earns another round — rule 11 of the fix
# reviewer's template, from the method author's own review: low ones are fixed by the lead
# without a round. The loop signal asks the same question of the previous round's top finding.
ROUND_SEVERITY = "medium"
# The block's proof kind. `read` — every file is read in full and named in the report;
# `measured` — reading proves nothing (180 thousand lines of tests, performance,
# scanners), the proof is the artifacts from the manifest. A block without `paths` is a
# live system.
PROOFS = ("read", "measured")
# A cross-cutting block's acceptance criterion is usually an enumeration — "every place that
# changes data", "every call and its constraint" — and that is a sweep over the whole program,
# not the block's files. The readability ceiling counted only `paths`, so a block "within the
# ceiling" demanded ten times more (a live review: 5.7k lines in the block, 47k in the sweep;
# setfork H3: 8 files by the counter, 89 by the criterion). The sweep is declared, sized apart
# and done by a script, not by attention.
SWEEP_DIR_NAME = "sweeps"
ENUMERATION = re.compile(
    r"\b(?:все|всех|всем|каждый|каждое|каждого|каждую)\s+(?:мест|вызов|точк|пут|маршрут|запис|обращен|использован|вхожден)"
    r"|\b(?:every|all)\s+(?:places?|calls?|sites?|routes?|writes?|paths?|quer(?:y|ies)|callers?|usages?|occurrences?)\b",
    re.IGNORECASE)
# Review languages. The tool's own messages are always English; what is translated into
# the project's language is what the agent reads in the prompt and what a human reads in
# the docs/review/ artifacts: rule 1, headings, the reading budget, findings.md, the
# journal, the setup scaffolds.
LANGS = ("en", "ru")
# Assets the setup hands to the project. The English name is the canonical one; a copy in
# another language sits next to it with the language before the extension
# (`entry-point.ru.md`). The names live here and not in the text of `cmd_setup`, because a
# checklist that hardcodes them names the English samples to a Russian review — and the
# translated copies were then reachable from nowhere in the kit.
ASSET_ENTRY = "entry-point.md"
ASSET_BANNER = "agent-banner.md"
ASSET_INVARIANTS = "invariants.example.md"
ASSET_MANIFEST = "manifest.example.md"
ASSET_JOURNAL = "journal.example.md"
ASSET_BLOCKS = "blocks.example.json"


def asset(name: str, lang: str) -> Path:
    """The asset in the review language, falling back to the English one.

    A definition sample is the same in any language, and a project may translate only
    part of the set: a missing copy is not a refusal, it is the English file.
    """
    assets = SKILL_DIR / "assets"
    stem, dot, ext = name.rpartition(".")
    localized = assets / f"{stem}.{lang}{dot}{ext}"
    return localized if lang != "en" and localized.exists() else assets / name


def fill(text: str, project: str, cli: str) -> str:
    """Substitutions of the scaffolds: the project's name and the command it calls the
    tool by. A scaffold that names `make review-status` to a project without a Makefile
    sends every future session to a command that does not exist."""
    return text.replace("{{PROJECT}}", project).replace("{{CLI}}", cli)


MSG = {
 "en": {
  "none": "(none)",
  "refs_cut": "\n\n({n} files. The list is collapsed to patterns — expand the part you need yourself: `git ls-files -- <pattern>`.)",
  "vol_head": "Files: {n}. Lines: {lines}. Order of magnitude: ~{k}k tokens just to read, before any reasoning or tool calls.",
  "vol_fits": "This fits what can be read in one session (ceiling {limit} lines).",
  "vol_sweep": "\n**The acceptance criterion sweeps beyond the block:** {n} more files, {lines} lines (`sweep` in blocks.json). Do not read them one by one — attention falls off at the end of a long list. Enumerate the places mechanically: a script at `docs/review/sweeps/{id}.<ext>` (grep, a parser) that prints every place with its path and line; commit it, then read the places it found. The script is the proof that the list is complete.",
  "vol_over": "\n⚠️ **The block is larger than one session can read** — {lines} lines against a ceiling of {limit}. Reading everything carefully will not work, and the only honest way out is to read as much as you can and **name the rest by path** in the coverage-limits section of your report. Do not pretend you read it.",
  "vol_over_verify": "\n⚠️ **The block is larger than one session can read** — {lines} lines against a ceiling of {limit}. Reading everything carefully will not work, and the only honest way out is to read as much as you can and **name the rest by path** in the block-coverage-status section of your report, opening it with the words \"Coverage is incomplete\". Do not pretend you read it.",
  "vol_border": "\nWhere the budget line runs (largest first, cumulative):",
  "vol_more": "  … and {n} more file(s)",
  "vol_legend": "\n▲ — beyond the line. Not a ban on opening them: it is what you must name as unread if you did not.",
  "vol_lines": "lines",
  "gates_missing": "(the \"gates\" field in blocks.json is empty — list the project's gate commands)",
  "commit_dco": "**The project requires a DCO sign-off** — stated in {where}. Commit every fix with `git commit -s`, under the name and email the project expects: the sign-off must name the commit's own author, and the global git identity of this machine is not that by default. The rest of the commit rules (message convention, language) are in the same files — read them before the first commit.",
  "commit_no_docs": "the contribution docs (the project has neither CONTRIBUTING nor AGENTS.md)",
  "commit_none": "(no commit rules of the project were found: no sign-off requirement in {docs} or in `.github/` — look at CONTRIBUTING and at the CI jobs about commits yourself before the first commit)",
  "commit_dco_review": "**The project requires a DCO sign-off** — stated in {where}. Check every commit of the diff range: {gate} A commit without `Signed-off-by`, or signed off by someone other than its own author, is a finding — the project's CI refuses it, and the change cannot land until the history is rewritten.",
  "commit_gate_script": "run the project's own check, `{script} {range}`, and put its output in the report.",
  "commit_gate_log": "the project has no script for it, so read the trailers: `git log --format='%h %an <%ae> %(trailers:key=Signed-off-by,valueonly,separator=%x2C )' {range}`.",
  "commit_none_review": "(no commit rules of the project were found: no sign-off requirement in {docs} or in `.github/` — if CONTRIBUTING or a CI job states one after all, check the commits of the range against it)",
  "proof_live": "**The block owns no files: it works against the running system.** What to bring up, what to run and which artifact to hand in is in the manifest below; without that artifact the block is not closed. Read code only as much as is needed to set up the experiment and explain its outcome.",
  "proof_measured_verify": "**The block is proven by artifacts, not by reading** (`proof: measured`). Do not re-read files after the hunter: rebuild every artifact from the manifest with the same command and compare line by line with what was handed in. A discrepancy is a finding; an artifact that cannot be rebuilt means the block is not closed.",
  "proof_measured": "**The block is proven by artifacts, not by reading** (`proof: measured`). The file list below outlines the area, not a reading assignment: which artifacts to hand in and how to obtain them is in the manifest, and without them the block is not closed. Read what the artifact needs and do not report reading that did not happen.",
  "proof_read_verify": "**Every file in the list below had to be read in full by someone.** If the hunter admitted skipping part of it, read that part yourself; if the hunter is silent about a file, that does not mean it was read.",
  "proof_read": "**Read EVERY file in the list below in full.** Not selectively, not \"the key ones\". The list is generated mechanically and is the subject of your work. If a file is too large, read it in parts — but read all of it.",
  "files_live": "Block files: none — the block works against the running system",
  "files_measured": "Block files ({n}) — the block's area; proof is the manifest's artifacts",
  "files_read": "Block files ({n}) — read all",
  "scope_line": " Your half of the fixes: **{scope}** — you file findings for this half; whatever else is in the diff below, read it for context.",
  "diff_vol": "The diff below: {kb} KB, {lines} lines. Order of magnitude: ~{k}k tokens just to read it, before any reasoning or tool calls. If that does not fit what you can hold at once, do not read half of it and report on the whole: say so in the report, and the lead splits the RANGE — `--diff <first part>` for you and `--diff <second>` for a second reviewer; that is what makes the diff smaller. `--scope <half>` does not: it names your half in the report and in its file name.",
  "no_open_findings": "(no open findings for this block — ask the lead session why the fixer was started)",
  "rec_none": "(nothing is recorded against this block yet)",
  "rec_row": "- **{id}** · {severity} · {status} · `{where}` — {claim} _(recorded {date})_",
  "dec_none": "(no human decision is recorded for this block — work by the rules above)",
  "loop_stop": "loop signal: the top finding lies in the code the previous round wrote — the human decides. {id} ({sev}, {file}:{line}) of fix review round {prev} sits on a line fix round {prev} changed ({diff}); another round would repeat that pattern. Record the decision — a different mechanism, a revert of the class, or closing the block — with `{cli} decide {block} \"<decision>\"`: it goes into the next fix and fix review prompts. If the decision is to close the block: `{cli} set-status {block} closed`.",
  "dec_row": "- **{date}**, after fix review round {round}: {text}",
  "f_where": "**Location:**", "f_claim": "**What is wrong:**", "f_scenario": "**Failure scenario:**", "f_invariant": "**Violated invariant:**", "f_conf": "confidence",
  "md_title": "# Review findings", "md_gen": "> This file is GENERATED from `findings.jsonl` by `{cli} findings`.", "md_noedit": "> Do not edit by hand — edit the jsonl and regenerate.",
  "md_open": "Open: **{live}** of {total} records.", "md_sev": "## {sev} ({open} open / {total})", "md_cols": "| id | block | status | location | what is wrong |",
  "journal_head": "# Review journal\n\n",
  "sum_title": "# {project} — review summary",
  "sum_intro": "This file outlives `docs/review/`: it describes the past and holds no status that can go stale. Base commit — the revision everything below was read against. To see how far each block has drifted since: `{cli} summary --aged <this file>`.",
  "sum_base": "**Date:** {date}  \n**Base commit:** `{sha}` ({branch})  \n**Blocks:** {closed} closed of {total}; **findings:** {total_f} — fixed {fixed}, rejected {rejected}, deferred {deferred}, duplicates {dups}, still open {open}",
  "sum_blocks": "## Blocks and what counted as checked",
  "sum_blocks_head": "| block | title | status | finished | files | reviewed at | acceptance criterion |",
  "sum_rejected": "## Rejected findings — do not find them again",
  "sum_rejected_none": "No rejected findings.",
  "sum_deferred": "## Accepted risks (deferred with a reason)",
  "sum_deferred_none": "Nothing deferred.",
  "sum_classes": "## What closed each class",
  "sum_classes_rules": "Guards (a test or a rule — and the findings it is recorded on):",
  "sum_classes_fixes": "Fixes by commit:",
  "sum_classes_none": "No guards recorded; fixes, if any, are listed above by commit.",
  "sum_open": "## Still open at the time of the summary",
  "sum_open_none": "Nothing open.",
  "sum_seams": "## Seams between blocks (from `coupling`)",
  "sum_machine": "## For the tool — do not edit",
  "sarif_deferred": "Accepted risk, deferred: ",
  "sarif_deferred_why": "Deferred because: {reason}",
  "sarif_report": "Block report: {path}",
  "sarif_rule_root": "Defect class of the review: {root}",
  "sarif_rule_block": "A finding of review block {block} ({title}) with no defect class named",
  "sarif_rule_guard": "What closes the class: {rules}",
  "sarif_rule_help": "Found by a whole-repository review with finetooth. Findings of this class: {ids}. The evidence and the failure scenario of each are in the block report named in the alert; the review state is in docs/review/.",
  "aged_head": "Drift since the base commit `{sha}` ({n} commits on the branch):",
  "aged_row": "  {block:<6} commits: {commits:<5} files: {files:<5} {title}",
  "aged_none": "nothing changed under the blocks' paths since the base — the summary still describes the tree",
  "backfill_note": "Fingerprints stamped retroactively at commit {head}: blocks {blocks}; findings {n}. Changes before this commit are not tracked.",
  "setup_note": "Static definition of the blocks. Progress lives in state.json, findings in findings.jsonl. Array order = execution order.",
  "excl_apparatus": "review apparatus, not its subject", "excl_skill": "the review skill — tooling, not the subject of review",
 },
 "ru": {
  "none": "(нет)",
  "refs_cut": "\n\n({n} файлов. Список сокращён до шаблонов — разверни нужную часть сам: `git ls-files -- <шаблон>`.)",
  "vol_head": "Файлов: {n}. Строк: {lines}. Порядок величины: ~{k}k токенов только на чтение, без рассуждений и вызовов инструментов.",
  "vol_fits": "Это укладывается в то, что читается за сеанс (порог {limit} строк).",
  "vol_sweep": "\n**Критерий приёмки обходит больше, чем блок:** ещё {n} файлов, {lines} строк (`sweep` в blocks.json). Не читай их по одному — к концу длинного списка внимание падает. Перечисли места механически: скрипт `docs/review/sweeps/{id}.<расширение>` (grep, разбор кода) печатает каждое место с путём и строкой; закоммить его и читай найденные места. Скрипт — доказательство, что список полон.",
  "vol_over": "\n⚠️ **Блок больше, чем прочитывается за сеанс** — {lines} строк при пороге {limit}. Прочитать всё внимательно не выйдет, и честный выход один: прочитать столько, сколько получится, и **поимённо назвать остальное** в разделе своего отчёта об ограничениях охвата. Не делайте вид, что прочитали.",
  "vol_over_verify": "\n⚠️ **Блок больше, чем прочитывается за сеанс** — {lines} строк при пороге {limit}. Прочитать всё внимательно не выйдет, и честный выход один: прочитать столько, сколько получится, и **поимённо назвать остальное** в разделе своего отчёта о состоянии охвата блока, открыв его словами «Охват неполный». Не делайте вид, что прочитали.",
  "vol_border": "\nГде проходит граница бюджета (по убыванию размера, накопительно):",
  "vol_more": "  … и ещё {n} файл(ов)",
  "vol_legend": "\n▲ — то, что за границей. Это не запрет их открывать: это то, что вы обязаны назвать непрочитанным, если не открыли.",
  "vol_lines": "строк",
  "gates_missing": "(в blocks.json не заполнено поле \"gates\" — впишите команды ворот проекта)",
  "commit_dco": "**Проект требует подпись DCO** — это сказано в {where}. Каждую правку коммить через `git commit -s` и под тем именем и почтой, которых ждёт проект: подпись обязана называть автора самого коммита, а глобальная идентичность git на этой машине — не она по умолчанию. Остальные правила коммитов (соглашение о сообщениях, язык) — в тех же файлах; прочитай их до первого коммита.",
  "commit_no_docs": "документах для участников (у проекта нет ни CONTRIBUTING, ни AGENTS.md)",
  "commit_none": "(правил коммитов проекта не найдено: требования подписи нет ни в {docs}, ни в `.github/` — до первого коммита сам посмотри CONTRIBUTING и джобы CI о коммитах)",
  "commit_dco_review": "**Проект требует подпись DCO** — это сказано в {where}. Проверь каждый коммит диапазона диффа: {gate} Коммит без `Signed-off-by` или подписанный не своим автором — находка: CI проекта его отвергает, и правка не войдёт, пока историю не перепишут.",
  "commit_gate_script": "прогони собственную проверку проекта, `{script} {range}`, и вклей её вывод в отчёт.",
  "commit_gate_log": "своего скрипта для этого у проекта нет, поэтому прочитай подписи: `git log --format='%h %an <%ae> %(trailers:key=Signed-off-by,valueonly,separator=%x2C )' {range}`.",
  "commit_none_review": "(правил коммитов проекта не найдено: требования подписи нет ни в {docs}, ни в `.github/` — если CONTRIBUTING или джоба CI всё же его ставит, сверь с ним коммиты диапазона)",
  "proof_live": "**У блока нет файлов: он работает на запущенной системе.** Что поднять, что прогнать и какой артефакт сдать — в манифесте ниже; без артефакта блок не закрыт. Код читай ровно настолько, чтобы поставить опыт и объяснить исход.",
  "proof_measured_verify": "**Блок доказывается артефактами, а не чтением** (`proof: measured`). Не перечитывай файлы за охотником: пересобери каждый артефакт манифеста той же командой и сверь построчно с тем, что он сдал. Расхождение — находка; артефакт, который не пересобирается, — блок не закрыт.",
  "proof_measured": "**Блок доказывается артефактами, а не чтением** (`proof: measured`). Список файлов ниже очерчивает область, а не задание на прочтение: какие артефакты сдать и как их получить — в манифесте, без них блок не закрыт. Читай то, что нужно для артефакта, и не отчитывайся о чтении, которого не было.",
  "proof_read_verify": "**Каждый файл из списка ниже кто-то обязан был прочитать целиком.** Если охотник признался, что часть не прочитал, — прочитай её сам; если он молчит о файле, это не значит, что файл прочитан.",
  "proof_read": "**Прочитай КАЖДЫЙ файл из списка ниже целиком.** Не выборочно, не «по ключевым». Список сгенерирован механически и является предметом твоей работы. Если файл слишком велик — читай его частями, но прочитай весь.",
  "files_live": "Файлы блока: нет — блок работает на запущенной системе",
  "files_measured": "Файлы блока ({n} шт.) — область блока; доказательство — артефакты манифеста",
  "files_read": "Файлы блока ({n} шт.) — прочитать все",
  "scope_line": " Твоя половина правок: **{scope}** — находки ты оформляешь по ней; то, что кроме неё есть в диффе ниже, читай для контекста.",
  "diff_vol": "Дифф ниже: {kb} КБ, {lines} строк. Порядок величины: ~{k}k токенов только на чтение, до рассуждений и вызовов инструментов. Если это не помещается в то, что ты держишь за раз, — не читай половину, отчитываясь за целое: скажи об этом в отчёте, и ведущая сессия разделит ДИАПАЗОН — `--diff <первая часть>` тебе и `--diff <вторая>` второму ревьюеру; уменьшает дифф именно это. `--scope <половина>` его не уменьшает: он называет твою половину в отчёте и в его имени.",
  "no_open_findings": "(открытых находок по блоку нет — уточни у ведущей сессии, зачем запущен фиксер)",
  "rec_none": "(за блоком пока ничего не записано)",
  "rec_row": "- **{id}** · {severity} · {status} · `{where}` — {claim} _(записана {date})_",
  "dec_none": "(решений человека по блоку не записано — работай по правилам выше)",
  "loop_stop": "сигнал петли: главная находка лежит в коде, который написал прошлый круг, — решает человек. {id} ({sev}, {file}:{line}) из ревью правок круга {prev} стоит на строке, которую изменил круг починки {prev} ({diff}); ещё один круг повторит тот же узор. Запишите решение — другой механизм, откат класса или закрытие блока — командой `{cli} decide {block} \"<decision>\"`: оно попадёт в задания следующего круга починки и ревью правок. Если решено закрыть блок: `{cli} set-status {block} closed`.",
  "dec_row": "- **{date}**, после ревью правок круга {round}: {text}",
  "f_where": "**Место:**", "f_claim": "**Что не так:**", "f_scenario": "**Сценарий отказа:**", "f_invariant": "**Нарушенный инвариант:**", "f_conf": "уверенность",
  "md_title": "# Находки ревью", "md_gen": "> Файл СГЕНЕРИРОВАН из `findings.jsonl` командой `{cli} findings`.", "md_noedit": "> Не редактируй его руками — правь jsonl и перегенерируй.",
  "md_open": "Открыто: **{live}** из {total} записей.", "md_sev": "## {sev} ({open} открыто / {total})", "md_cols": "| id | блок | статус | место | что не так |",
  "journal_head": "# Дневник ревью\n\n",
  "sum_title": "# {project} — итог ревью",
  "sum_intro": "Этот файл переживает снос `docs/review/`: он описывает прошлое и не держит статусов, которые могут протухнуть. Коммит-база — ревизия, относительно которой всё ниже читалось. Насколько каждый блок уехал с тех пор: `{cli} summary --aged <этот файл>`.",
  "sum_base": "**Дата:** {date}  \n**Коммит-база:** `{sha}` ({branch})  \n**Блоки:** закрыто {closed} из {total}; **находки:** {total_f} — починено {fixed}, отвергнуто {rejected}, отложено {deferred}, дублей {dups}, ещё открыто {open}",
  "sum_blocks": "## Блоки и что считалось проверенным",
  "sum_blocks_head": "| блок | название | статус | закрыт | файлов | отпечаток | критерий приёмки |",
  "sum_rejected": "## Отвергнутые находки — не искать заново",
  "sum_rejected_none": "Отвергнутых находок нет.",
  "sum_deferred": "## Принятые риски (отложено с причиной)",
  "sum_deferred_none": "Отложенного нет.",
  "sum_classes": "## Чем закрыт каждый класс",
  "sum_classes_rules": "Узды (тест или правило — и находки, на которые она записана):",
  "sum_classes_fixes": "Починки по коммитам:",
  "sum_classes_none": "Узды не записаны; починки, если есть, перечислены выше по коммитам.",
  "sum_open": "## Ещё открыто на момент итога",
  "sum_open_none": "Открытого нет.",
  "sum_seams": "## Стыки между блоками (из `coupling`)",
  "sum_machine": "## Для инструмента — не править",
  "sarif_deferred": "Принятый риск, отложено: ",
  "sarif_deferred_why": "Отложено, потому что: {reason}",
  "sarif_report": "Отчёт блока: {path}",
  "sarif_rule_root": "Класс дефекта ревью: {root}",
  "sarif_rule_block": "Находка блока ревью {block} ({title}) без названного класса дефекта",
  "sarif_rule_guard": "Что закрывает класс: {rules}",
  "sarif_rule_help": "Найдено сплошным ревью репозитория с finetooth. Находки этого класса: {ids}. Доказательство и сценарий отказа каждой — в отчёте блока, названном в предупреждении; состояние ревью — в docs/review/.",
  "aged_head": "Дрейф от коммита-базы `{sha}` ({n} коммитов на ветке):",
  "aged_row": "  {block:<6} коммитов: {commits:<5} файлов: {files:<5} {title}",
  "aged_none": "под путями блоков ничего не менялось с базы — итог по-прежнему описывает дерево",
  "backfill_note": "Отпечатки проставлены задним числом на коммите {head}: блоки {blocks}; находок {n}. Изменения до этого коммита не отслежены.",
  "setup_note": "Статическое определение блоков. Прогресс живёт в state.json, находки — в findings.jsonl. Порядок массива = порядок исполнения.",
  "excl_apparatus": "аппарат ревью, а не его предмет", "excl_skill": "скилл ревью — оснастка, а не предмет ревью",
 },
}


def review_lang() -> str:
    """The project's review language — the `lang` field in blocks.json; English by default."""
    try:
        lang = json.loads(BLOCKS_FILE.read_text(encoding="utf-8")).get("lang", "en")
    except (OSError, ValueError, AttributeError):
        lang = "en"
    return lang if lang in LANGS else "en"


def T(key: str, **kw) -> str:
    return MSG[review_lang()][key].format(**kw)
# Which role comes next given the block status — the hint in `status`.
NEXT_ROLE = {"todo": "hunter", "running": "hunter", "hunted": "verify", "verified": "fix",
             "triaged": "fix", "fixing": "fixreview"}

# A block left `running` for longer than this almost certainly means a session
# died mid-flight rather than that an agent is still reading.
STALE_RUNNING_HOURS = 24

# A block that passed verification does not stop being verified when it moves on. While
# the condition was "verified or closed", moving to triaged turned the hypotheses gate and
# the coverage-limits gate green without adding anything: the status changed, the gap stayed.
POST_VERIFY = ("verified", "triaged", "fixing", "closed")


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        die(f"{path.relative_to(ROOT)} is missing — run `{CLI} init`")
    except json.JSONDecodeError as exc:
        die(f"{path.relative_to(ROOT)} is not valid JSON: {exc}")


def save_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# Modes in the git index that look like files but are not files.
# Verified by experiment: a submodule (160000) is one entry in `ls-files`, but a directory
# on disk, and the line counter dies on it with IsADirectoryError. Its code lives in
# another repository and is reviewed there.
# A symlink (120000) is NOT excluded: a link can be re-pointed, and that is a change
# someone must see. Excluding it removed it from everywhere — no owner, no "unowned",
# no fingerprint. There is no double counting either: lines are taken from the index,
# where a symlink holds the link text, not the target's contents; the fingerprint is
# also taken from the link text.
NOT_A_FILE_MODES = ("160000",)


def index_rows(pathspecs: list[str] | None) -> list[tuple[str, str, str]]:
    """Index entries matching the pathspecs: (mode, blob sha, path).

    The patterns come from `blocks.json`, which is edited by hand, and git refuses to
    parse some of them (a typo in the pathspec magic the kit itself invites projects to
    use for exclusions). A refusal from git used to reach the user as a traceback with
    exit 1 — which reads as "the state is red", not as "your pattern is malformed".
    """
    out = git("ls-files", "--stage", *(["--", *pathspecs] if pathspecs is not None else []))
    if out.code != 0:
        where = ", ".join(f"`{p}`" for p in pathspecs or []) or "(no patterns)"
        die(f"git refuses the pattern(s) {where}: {out.err.strip() or 'unknown error'}\n"
            f"The patterns are the `paths`, `ref_paths` and `exclusions` fields of "
            f"docs/review/blocks.json — fix the one git names and re-run. "
            f"They are git pathspecs: `src/**/*.ts`, `:(exclude)src/generated/**`.")
    rows = []
    for row in out.fields:
        head, _, path = row.partition("\t")
        mode, _, rest = head.partition(" ")
        rows.append((mode, rest.split(" ", 1)[0], path))
    return rows


def listed(pathspecs: list[str] | None) -> set[str]:
    """Tracked files — real files, without submodules (a symlink is a file here, see above)."""
    return {path for mode, _, path in index_rows(pathspecs) if mode not in NOT_A_FILE_MODES}


def untracked_files(specs: list[str]) -> list[str]:
    """Files on disk that match the specs but are not in the index (`npx skills add`,
    a fresh generator, an unpacked archive): `check` would otherwise call them absent."""
    return git("ls-files", "--others", "--exclude-standard", "--", *specs).fields


def git_files(pathspecs: list[str]) -> set[str]:
    """Tracked files matching git pathspecs.

    An empty pathspec list means an empty set, NOT everything: a block that
    declares no paths (the ones that work on the running stand) owns no files,
    and must not be able to claim coverage it never earned. Use all_files() to
    ask for the whole repository on purpose.
    """
    if not pathspecs:
        return set()
    return listed(pathspecs)


def all_files() -> set[str]:
    return listed(None)


def named_file(rel: str) -> bool:
    """Is this NAME a tracked file?

    A name is not a pattern: `:(literal)` keeps a `[handle]` in the path a directory and
    not a character class. Next.js routes — `app/[id]/page.tsx` — are the kit's stated
    target, and without this a guard or a `--fixed-in` path that really exists is refused.
    """
    return bool(git_files([f":(literal){rel}"]))


def file_sha(rel: str) -> str | None:
    """Fingerprint of a file's contents — the same one git computes, without extra dependencies.

    Taken from the working tree while the file is laid out there (that is the text a human
    and an agent actually read), and FROM THE INDEX when it is not. The index branch is not
    an exotic case: a sparse checkout does not lay out part of the tree at all, and a file
    deleted without committing is still listed by `ls-files`. Without it such a file
    contributed only its NAME to the block fingerprint — its contents could be rewritten
    and `check` would never say "block files changed after the review".
    """
    if not rel or rel.startswith("("):
        return None
    p = ROOT / rel
    if p.is_symlink():
        # `hash-object` would follow the link and hash the target: re-pointing to a file
        # with the same contents would go unnoticed. What is hashed is what the symlink is.
        return "link:" + hashlib.sha1(os.readlink(p).encode("utf-8")).hexdigest()
    if p.is_file():
        return git("hash-object", "--", rel).out.strip() or None
    # `:(literal)` — the path is a name, not a pattern: a `[handle]` in it is a directory,
    # not a character class.
    rows = index_rows([f":(literal){rel}"])
    entry = next((r for r in rows if r[2] == rel), None)
    if entry is None or entry[0] in NOT_A_FILE_MODES:
        return None
    if entry[0] == "120000":
        # A symlink not laid out on disk: the index holds its target as the blob. Hashed
        # the same way as the laid-out branch, so the fingerprint does not jump when a
        # sparse checkout lays the link out.
        blob = git("show", f":{rel}", binary=True).out
        return "link:" + hashlib.sha1(blob).hexdigest()
    return entry[1]


# How far the fingerprint of a finding reaches: its line and REGION_K lines above and below.
#
# A hash of the whole file re-flagged every deferred finding on every commit to its file —
# in the kit's own review five pull requests in a row turned `check` red on the same 15
# findings whose code nobody had touched (#37). A window around the line is what GitHub
# code scanning matches on too (`primaryLocationLineHash`, the context of the line). The
# size is measured on the kit's own history, not guessed:
#
#   * fixes seen — of the 148 fixed findings of the review that have a fix commit, the
#     window at the cited line (in the version the finding was imported on) is gone after
#     the fix commit for 67 at K=0, 95 at K=2, 98 at K=3, 103 at K=5, 111 at K=10; the
#     whole-file hash sees 141 (the other seven fix commits did not touch the file);
#   * edits elsewhere — over 61 commits to `review.py` and `tests/test_review.py`, the
#     window around a line the commit left untouched breaks in 0.9% of cases at K=1, 2.4%
#     at K=3, 3.5% at K=5, 5.7% at K=10; the whole-file hash breaks on every commit;
#   * uniqueness — at K=0 16 of 164 cited lines occur more than once in their file (`)`,
#     a blank line), at K=1 3, from K=2 on none.
#
# K=3 sits past the knee: up to 3 each step adds a handful of fixes seen, after it about
# two per step while the collateral rate keeps rising by half a point. The price is named:
# a fix made more than three lines from the cited line (the line is a function's head, the
# fix is in its body) goes unseen by this gate — it is a backstop for a status nobody moved,
# not the way fixes are recorded (`set-finding fixed --commit` is).
REGION_K = 3


def text_lines(rel: str) -> list[bytes] | None:
    """The file's lines as the region fingerprint reads them, or None where there are none.

    Read from the same place as `file_sha` (the working tree while the file is laid out,
    the index when it is not), so the two fingerprints never describe different versions.
    Trailing whitespace is dropped and every line ending counts the same: an editor that
    trims spaces or rewrites CRLF has not changed the code. Leading whitespace is kept —
    GitHub drops all of it, but in Python indentation IS code, and a line moved out of a
    `with` is a different program. A symlink, a binary file (a NUL near the start, as git
    itself decides) and a missing file have no lines: such a finding keeps the whole-file
    fingerprint.
    """
    if not rel or rel.startswith("("):
        return None
    p = ROOT / rel
    if p.is_symlink():
        return None
    if p.is_file():
        try:
            data = p.read_bytes()
        except OSError:
            return None
    else:
        rows = index_rows([f":(literal){rel}"])
        entry = next((r for r in rows if r[2] == rel), None)
        if entry is None or entry[0] in NOT_A_FILE_MODES or entry[0] == "120000":
            return None
        data = git("show", f":{rel}", binary=True).out
    if b"\0" in data[:8192]:
        return None
    return [ln.rstrip() for ln in data.splitlines()]


def region_hash(lines: list[bytes], start: int, count: int) -> str:
    return hashlib.sha256(b"\n".join(lines[start:start + count])).hexdigest()[:16]


def take_region(lines: list[bytes] | None, line) -> dict | None:
    """The region fingerprint of `line` (1-based) in these lines: the hash and how many lines
    above and below it the window took. The window is clipped at the file's edges, so the
    span is recorded, not derived from K — which also lets K change without invalidating
    the records stamped before."""
    if (lines is None or isinstance(line, bool) or not isinstance(line, int)
            or not 1 <= line <= len(lines)):
        return None
    above, below = min(REGION_K, line - 1), min(REGION_K, len(lines) - line)
    return {"region_sha": region_hash(lines, line - 1 - above, above + below + 1),
            "region_span": [above, below]}


def locate_region(f: dict, lines: list[bytes]) -> int | None:
    """Where the finding's window is in these lines — the line it now sits on, or None.

    Searched by CONTENT across the whole file: an edit above the finding moves it without
    touching it. When the same window occurs more than once, the one nearest the recorded
    line wins — that is the one the finding was about, give or take the shift.
    """
    span = f.get("region_span")
    if (not isinstance(span, list) or len(span) != 2
            or not all(isinstance(x, int) and not isinstance(x, bool) and x >= 0 for x in span)):
        return None
    above, below = span
    count = above + below + 1
    was = f["line"] if isinstance(f.get("line"), int) else above + 1
    hits = [s + above + 1 for s in range(0, len(lines) - count + 1)
            if region_hash(lines, s, count) == f.get("region_sha")]
    return min(hits, key=lambda at: (abs(at - was), at)) if hits else None


def code_fingerprint(rel: str, line) -> dict:
    """The fingerprint a finding gets: its region when it cites a line the file has, the
    whole file when it does not (a finding about a file as a whole, a binary, a symlink)."""
    region = take_region(text_lines(rel), line)
    if region:
        return region
    sha = file_sha(rel)
    return {"code_sha": sha} if sha else {}


# Every field a finding's code fingerprint is written in: `code_sha` (the whole file — the
# only form before #37, and still the form of a finding without a line) or the region pair.
CODE_FINGERPRINT_FIELDS = ("code_sha", "region_sha", "region_span")


def put_fingerprint(f: dict, fp: dict) -> None:
    """Replace the finding's fingerprint: the old form goes, so a record never carries two."""
    for k in CODE_FINGERPRINT_FIELDS:
        f.pop(k, None)
    f.update(fp)


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


def file_lines(rel: str) -> int | None:
    """Line count — from the INDEX, not from disk.

    The file may be absent from disk while its index entry is alive (deleted without
    committing; sparse-checkout does not lay out part of the tree at all, yet `ls-files`
    prints it). Opening such a path means crashing for no reason or silently losing it
    from the denominator.
    """
    out = git("show", f":{rel}", binary=True)
    # A binary file is not lines: a "two-thousand-line" picture inflated the block and
    # the readability ceiling. The sign is a NUL byte near the start, as git itself does it.
    if out.code == 0 and b"\0" in out.out[:8192]:
        return None
    if out.code != 0:
        p = ROOT / rel
        if not p.is_file():
            return None
        try:
            with open(p, encoding="utf-8", errors="ignore") as fh:
                return sum(1 for _ in fh)
        except OSError:
            return None
    return out.out.count(b"\n") + (0 if out.out.endswith(b"\n") or not out.out else 1)


# What a block definition must carry for the tool to be able to do anything with it. The
# file is written BY HAND — `setup` leaves `"blocks": []` for a human to fill in — and a
# missing field used to surface as `KeyError: 'phase'` with exit 1, which reads as "the
# state is red" rather than "your definition is malformed". Each field is used somewhere
# with no default: `slug` names the manifest and the reports, `phase` orders the array,
# `role` and `goal` are pasted into every prompt.
BLOCK_FIELDS = ("id", "slug", "phase", "title", "role", "goal")


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


# --------------------------------------------------------------------------- init


def cmd_init(args) -> int:
    defn = blocks()
    before = STATE_FILE.read_text(encoding="utf-8") if STATE_FILE.exists() else None
    st = {"review_id": defn["review_id"], "updated_at": now(), "blocks": {}}
    if STATE_FILE.exists() and not args.force:
        st = state()
    for b in defn["blocks"]:
        st["blocks"].setdefault(
            b["id"],
            {"status": "todo", "started": None, "finished": None, "reports": [], "note": ""},
        )
    # A block deleted from the definition must not linger in the state.
    known = {b["id"] for b in defn["blocks"]}
    for stale in [k for k in st["blocks"] if k not in known]:
        del st["blocks"][stale]
    FINDINGS_FILE.touch()
    # A re-run on an unchanged definition must leave the file alone, to the byte. While
    # `updated_at` was rewritten unconditionally, a CI gate of the usual shape — regenerate,
    # then require a clean working tree — went red on a correct state, and the only way to
    # keep it green was to stop running `init` in CI, which is what the gate existed for.
    if before is not None and state_text(st, keep=before) == before:
        print(f"state already matches the definition: {len(st['blocks'])} blocks")
        return 0
    st["updated_at"] = now()
    save_json(STATE_FILE, st)
    print(f"state initialised: {len(st['blocks'])} blocks")
    return 0


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


def cmd_version(args) -> int:
    print(VERSION)
    return 0


# ------------------------------------------------------------------------- status


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


def cmd_status(args) -> int:
    defn, st = blocks(), state()
    rows = findings()
    open_by_block: dict[str, int] = {}
    for f in rows:
        if f.get("status") == "open":
            open_by_block[f.get("block", "?")] = open_by_block.get(f.get("block", "?"), 0) + 1

    mark = {
        "todo": "·", "running": "»", "hunted": "h", "verified": "v",
        "triaged": "t", "fixing": "f", "closed": "✓", "blocked": "!",
    }
    phase = None
    for b in defn["blocks"]:
        if b["phase"] != phase:
            phase = b["phase"]
            print(f"\n── Phase {phase_name(phase)} " + "─" * 40)
        s = st["blocks"].get(b["id"], {})
        status = s.get("status", "todo")
        opened = open_by_block.get(b["id"], 0)
        tail = f"  open findings: {opened}" if opened else ""
        print(f"  {mark.get(status,'?')} {b['id']:<4} {status:<9} {b['title']}{tail}")

    total = len(defn["blocks"])
    closed = sum(1 for b in defn["blocks"] if st["blocks"].get(b["id"], {}).get("status") == "closed")
    print(f"\nblocks: {closed}/{total} closed")

    by_sev = {s: 0 for s in SEVERITIES}
    for f in rows:
        if f.get("status") == "open":
            by_sev[f.get("severity", "low")] = by_sev.get(f.get("severity", "low"), 0) + 1
    print("findings open: " + ", ".join(f"{s}={by_sev.get(s,0)}" for s in SEVERITIES)
          + f"  (total records: {len(rows)})")
    gate = fix_gate(defn)
    if gate:
        debt = fix_debt(defn, rows)
        if debt:
            in_blocks = sorted({f.get("block", "?") for f in debt})
            print(f"fix debt (gate: {gate} and above): {len(debt)} open in {len(in_blocks)} block(s) — "
                  f"{', '.join(in_blocks)}; the next block will not start until they are fixed, "
                  f"deferred with a reason or rejected")
        else:
            print(f"fix debt (gate: {gate} and above): none")

    blocked = [b for b in defn["blocks"] if st["blocks"].get(b["id"], {}).get("status") == "blocked"]
    if blocked:
        print("\nwaiting:")
        for b in blocked:
            print(f"  ! {b['id']:<4} {b['title']} — {st['blocks'][b['id']].get('note') or 'no note'}")

    nxt = next_block(defn, st)
    if nxt:
        cur = st["blocks"][nxt["id"]]["status"]
        role = NEXT_ROLE.get(cur, "hunter")
        print(f"\nnext block: {nxt['id']} ({nxt['title']}) — status {cur}")
        print(f"prompt:   {CLI} prompt {nxt['id']} --role {role}")
        print(f"manifest: docs/review/blocks/{nxt['id']}-{nxt['slug']}.md")
    elif blocked:
        # A blocked block is not a read one. It used to not prevent declaring the review
        # finished, and the directory was offered for deletion with an unread block inside.
        print(f"\nreview is NOT finished: waiting {', '.join(b['id'] for b in blocked)}")
    elif not defn["blocks"]:
        print("\nreview not started: blocks.json has no blocks")
    else:
        print("\nall blocks closed — time to consolidate the findings and delete docs/review/")
    return 0


def cmd_next(args) -> int:
    nxt = next_block(blocks(), state())
    print(nxt["id"] if nxt else "")
    return 0


# ----------------------------------------------------------------------- coverage


def coverage_map() -> tuple[dict[str, list[str]], set[str], set[str]]:
    """file -> owning block ids, plus the excluded and the unassigned sets."""
    defn = blocks()
    excluded = git_files([e["pattern"] for e in defn.get("exclusions", [])])
    everything = all_files() - excluded
    owned: dict[str, list[str]] = {}
    for b in defn["blocks"]:
        for f in git_files(b.get("paths", [])) - excluded:
            owned.setdefault(f, []).append(b["id"])
    # Owners are sorted: reordering blocks in the array must not change the map.
    for f in owned:
        owned[f].sort()
    unassigned = everything - set(owned)
    return owned, excluded, unassigned


# How far behind in TIME the tree must be for that to mean "it has gone stale".
#
# Time is what must be measured, not commits: in the case this check was created for, the
# copy of the neighbouring service was only TWO commits behind — and twelve days. Two
# commits would alarm nobody, while in twelve days the hole had been closed, and the
# verifier "confirmed by execution" a defect that no longer existed.
#
# The threshold is below that measurement (12 days) and above the usual life of a working
# branch: a branch lives days, a stale copy — weeks. Counting commits is deliberately not
# used: a branch cut an hour ago is a dozen commits behind master and not stale at all.
STALE_TREE_DAYS = 7


def mainline_ref() -> str | None:
    """The remote's main line to measure freshness against, or None if git knows of none.

    `refs/remotes/origin/HEAD` is written by `clone` and by `fetch`, but a repository whose
    remote is not called `origin` has no such ref at all — and neither has a copy with no
    remote, which is exactly the vendored copy of a neighbouring service the freshness
    threshold was written for. Every remote is asked, not just `origin`.
    """
    remotes = git("remote").out.split()
    for name in (["origin"] if "origin" in remotes else []) + [r for r in remotes if r != "origin"]:
        ref = git("symbolic-ref", "--short", f"refs/remotes/{name}/HEAD").out.strip()
        if ref:
            return ref
    return None


def freshness_inert() -> str | None:
    """Why the freshness gate cannot run here — or None when it can.

    A gate whose mechanism is silently inert is not a gate: with no `origin/HEAD` the check
    used to return None and say nothing, so a tree twelve days behind passed in silence,
    indistinguishable from a fresh one.
    """
    if mainline_ref():
        return None
    remotes = git("remote").out.split()
    if not remotes:
        return ("no remote in this repository, so the freshness of the tree cannot be "
                "checked at all — findings from a stale copy describe what is already "
                "fixed; if this is a copy of somebody else's repository, add it "
                "(`git remote add origin <url> && git fetch`) before filing findings")
    return (f"remote(s) {', '.join(remotes)} have no HEAD ref, so the freshness of the tree "
            f"is not checked — `git remote set-head {remotes[0]} -a` writes it once and the "
            f"gate starts working")


def stale_tree() -> tuple[float, str] | None:
    """How much fresher the server's tip is than ours — in days, if the gap is large.

    The network is not touched (`fetch` is the human's business); we look at what git
    already knows.
    """
    ref = mainline_ref()
    if not ref:
        return None

    def stamp(rev: str) -> int | None:
        # `show -s`, not `log`: reading a commit's date is not reading the history, and the
        # marked `git log` stream has exactly one reader (`log_records`).
        out = git("show", "-s", "--format=%ct", rev)
        return int(out.out.strip()) if out.code == 0 and out.out.strip() else None

    # Counted from the POINT OF DIVERGENCE, not from our own tip: a fresh commit in a
    # long-ago branch makes its tip newer than the remote one and hides the fact that the
    # branch contains not a single fix made by others in all that time.
    base = git("merge-base", "HEAD", ref)
    anchor = base.out.strip() if base.code == 0 and base.out.strip() else "HEAD"
    mine, theirs = stamp(anchor), stamp(ref)
    if mine is None or theirs is None:
        return None
    days = (theirs - mine) / 86400
    return (days, ref) if days > STALE_TREE_DAYS else None


def cmd_coverage(args) -> int:
    owned, excluded, unassigned = coverage_map()
    lines = ["file\tblocks"]
    for f in sorted(owned):
        lines.append(f"{f}\t{','.join(owned[f])}")
    # `--no-write` — gate mode: CI checks that there are no unowned files without touching the tree.
    if not args.no_write:
        COVERAGE_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")

    total = len(owned) + len(unassigned)
    print(f"covered:     {len(owned)}/{total} files")
    print(f"excluded:    {len(excluded)} (with a reason in blocks.json)")
    print(f"map:         docs/review/coverage.tsv{' (not rewritten: --no-write)' if args.no_write else ''}")
    if unassigned:
        print(f"\nNOT COVERED: {len(unassigned)} files — the review is incomplete:")
        for f in sorted(unassigned)[: args.limit]:
            print(f"  {f}")
        if len(unassigned) > args.limit:
            print(f"  … and {len(unassigned) - args.limit} more")
        # ⚠️ A refusal must say WHAT to do. Flat directories are cut up by name on
        # purpose: let a human, not a pattern, choose the block for a new file — a glob
        # that silently matched means "the file counts as read" although nobody opened
        # it. But if the refusal stops at a list of paths, the human will append the file
        # to the first block that comes to hand, and the price of the decision is not repaid.
        print(
            "\nWhat to do: add the path to the block that is responsible FOR THIS AREA "
            "(docs/review/blocks.json, the paths field).\n"
            f"The list of blocks with their questions: {CLI} status.\n"
            "The choice is made by a human: a file that landed in a block by pattern match "
            "will count as read without having been read."
        )
        return 1
    print("\nno unowned files")
    return 0


def cmd_inventory(args) -> int:
    """The repository tree by directory: files, lines, binaries, whose — for cutting blocks.

    Blocks are cut by subject, not by directory, but it all starts with the tree anyway:
    without it neither the volume nor what remains unowned is visible.
    """
    owned, excluded, unassigned = coverage_map()
    files = sorted(set(owned) | unassigned)
    if args.under:
        prefix = args.under.rstrip("/") + "/"
        files = [f for f in files if f.startswith(prefix)]
    if args.unassigned:
        files = [f for f in files if f in unassigned]
    rows: dict[str, dict] = {}
    for f in files:
        parts = f.split("/")
        key = "/".join(parts[: args.depth]) if len(parts) > args.depth else "/".join(parts[:-1]) or "."
        r = rows.setdefault(key, {"files": 0, "lines": 0, "binary": 0, "unassigned": 0, "blocks": set()})
        r["files"] += 1
        n = file_lines(f)
        if n is None:
            r["binary"] += 1
        else:
            r["lines"] += n
        if f in unassigned:
            r["unassigned"] += 1
        else:
            r["blocks"].update(owned.get(f, []))
    print(f"{'directory':<48} {'files':>6} {'lines':>8} {'binary':>7} {'unowned':>6}  blocks")
    for key in sorted(rows):
        r = rows[key]
        print(f"{key:<48} {r['files']:>6} {r['lines']:>8} {r['binary']:>7} {r['unassigned']:>6}  "
              f"{','.join(sorted(r['blocks'])) or '—'}")
    print(f"\nexcluded files: {len(excluded)}; unowned: {len(unassigned)}")
    return 0


def sweep_lines(b: dict) -> tuple[int, int]:
    """Files and lines the block's `sweep` covers beyond its own `paths`."""
    if not b.get("sweep"):
        return 0, 0
    own = git_files(b.get("paths", [])) if b.get("paths") else set()
    extra = sorted(git_files(b["sweep"]) - own)
    return len(extra), sum(file_lines(f) or 0 for f in extra)


def sweep_script(b: dict) -> Path | None:
    d = REVIEW / SWEEP_DIR_NAME
    if not d.is_dir():
        return None
    hits = sorted(p for p in d.iterdir() if p.is_file() and p.stem == b["id"])
    return hits[0] if hits else None


def enumerates_beyond(b: dict) -> bool:
    """Does the manifest's acceptance criterion ask to enumerate places program-wide?"""
    m = manifest_path(b)
    if not m.exists():
        return False
    body = section_body(m.read_text(encoding="utf-8"), ACCEPTANCE_HEADING) or []
    # what the criterion SAYS, not an example quoted in it
    return bool(ENUMERATION.search("\n".join(unquoted(body, "text"))))


def cmd_sizes(args) -> int:
    """Size of every block against the readability ceiling: what to split before it is too late."""
    defn = blocks()
    limit = readable_lines()
    over = 0
    print(f"{'block':<6} {'proof':<9} {'files':>6} {'lines':>8}  {'ceiling ' + str(limit)}")
    for b in defn["blocks"]:
        if not b.get("paths"):
            print(f"{b['id']:<6} {'stand':<9} {0:>6} {0:>8}  live system")
            continue
        n, lines = block_lines(b["paths"])
        proof = b.get("proof", "read")
        mark = ""
        if proof == "read" and lines > limit:
            mark = f"⚠ above the ceiling by {lines - limit} — split by subject"
            over += 1
        elif proof == "measured":
            mark = "measured, the ceiling does not apply"
        sn, sl = sweep_lines(b)
        if sn:
            mark = (mark + "; " if mark else "") + f"+ sweep {sn} files / {sl} lines (mechanical, not read)"
        print(f"{b['id']:<6} {proof:<9} {n:>6} {lines:>8}  {mark}")
    if over:
        print(f"\nblocks above the ceiling: {over}")
        return 1
    print("\nall readable blocks are within the ceiling")
    return 0


# ------------------------------------------------------------------------ coupling

# Files that change together but sit in different blocks: the seam nobody reads. The
# thresholds come from the first project's measurement (553 pairs co-changed ≥ 3 times,
# 76% across blocks, 38 strong pairs) and from change-coupling research (Zimmermann et al.,
# ROSE, TSE 2005: support and confidence over the commit history):
#   COUPLING_MIN_TOGETHER — a pair counts from this many joint commits (support);
#   COUPLING_MIN_SHARE    — and when the joint commits are at least this share of the
#                           commits of one of the two files (confidence, the stronger side);
#   hub_blocks()          — a file coupled with that many blocks is a shared node (schema,
#                           dictionary), printed apart: it explains most cross-block pairs
#                           and says nothing about a specific seam.
# The mass-commit cutoff is not a constant: it is the 95th percentile of files per commit
# IN THIS repository, so a codemod or a formatting sweep does not manufacture pairs.
COUPLING_MIN_TOGETHER = 3
COUPLING_MIN_SHARE = 0.5
COUPLING_MASS_PERCENTILE = 95
# Fewer commits than this and the percentile cannot separate anything at all: its rank,
# ceil(0.95·n), equals n for every n up to 20. See `mass_cutoff`.
COUPLING_MIN_SAMPLE = 20
# The hub threshold is a SHARE of the review, not a fixed count, and both halves are
# derived rather than chosen. A seam runs between two blocks; a file that reaches a third
# is no longer describing one seam, which is the floor. The share reproduces the number the
# kit has run with since the command appeared — 6 on the 59-block review it was measured on
# (59 × 10% = 5.9) — so a big review keeps the behaviour it was tuned to, while on a review
# of four blocks a "hub coupled with six of four blocks" cannot exist and the filter would
# be dead code.
COUPLING_HUB_SHARE = 0.10
COUPLING_HUB_FLOOR = 3


def hub_blocks(n_blocks: int) -> int:
    """How many blocks a file must be coupled with to count as a shared node."""
    return max(COUPLING_HUB_FLOOR, math.ceil(n_blocks * COUPLING_HUB_SHARE))
COUPLING_FILE = REVIEW / "coupling.tsv"


# `\x01` marks the start of a commit record: with `-z` every field is NUL-terminated, so
# the commit line cannot be told from a path by the separator alone.
LOG_MARK = "\x01"


def log_records(*args: str) -> list[tuple[str, list[str]]]:
    """Commit records of a `git log` run: (sha, the tokens after it). The caller passes the
    rest of the arguments — the record marker and the format are set HERE.

    ONE reader AND the only caller of `git log` in the tool, because the trap is not visible
    from a call site: git terminates the `--format` line with a newline of its own, and `-z`
    leaves that newline GLUED to the first token of the commit — the stream is `…<sha>\\0` +
    `\\nsrc/a.ts\\0`. Read without stripping it, a file that comes first in one commit and
    not in another is counted under two names, and `summary --aged` over-reported the drift
    of every real history for exactly that reason. Two parsers of one stream is how that
    happened: whoever wants records asks here, and nobody else has a marked stream to parse.
    """
    records: list[tuple[str, list[str]]] = []
    for token in git("log", f"--format={LOG_MARK}%H", *args).fields:
        if token.startswith(LOG_MARK):
            records.append((token[1:], []))
        elif records:
            body = records[-1][1]
            body.append(token[1:] if not body and token.startswith("\n") else token)
    return records


def commit_file_sets(since: str | None = None) -> list[set[str]]:
    """The set of files touched by every commit on the current history, UNDER TODAY'S NAMES
    (first parent only: a merge lists everything the branch brought, and that is not a joint
    change).

    Two things `--name-only` alone gets wrong, both measured on this repository's own
    history. A rename is printed as the new path only, so a file's churn is cut at every
    move — `review.py` has 42 first-parent commits and 10 under its current path, and the
    block that owns it was ranked on a quarter of its real change frequency. And a non-ASCII
    path comes out C-quoted (`"src/\\320\\274…"`), so it never matches what `ls-files -z`
    reports and is invisible to `coupling` altogether.

    `--name-status -z -M` answers both: `-z` gives raw NUL-separated paths, and the rename
    records let the old name be translated into the current one. The log is walked
    newest-first, so a rename `old → new` seen at a commit renames everything OLDER than it.
    """
    args = ["--first-parent", "--no-merges", "--name-status", "-M"]
    if since:
        args.append(f"--since={since}")
    sets: list[set[str]] = []
    # old path -> the name that path bears today
    alias: dict[str, str] = {}
    for _sha, tokens in log_records(*args):
        current: set[str] = set()
        renames: list[tuple[str, str]] = []   # (old, new) of the commit being read
        i = 0
        while i < len(tokens):
            status, paths = tokens[i], []
            take = 2 if status[:1] in ("R", "C") else 1
            for j in range(1, take + 1):
                if i + j < len(tokens):
                    paths.append(tokens[i + j])
            i += 1 + len(paths)
            if not paths:
                continue
            if take == 2 and len(paths) == 2:
                old, new = paths
                renames.append((old, new))
                current.add(alias.get(new, new))
            else:
                p = paths[-1]
                current.add(alias.get(p, p))
        if current:
            sets.append(current)
        for old, new in renames:
            alias[old] = alias.get(new, new)
    return sets


def quantile(sorted_sizes: list[int], q: float) -> int:
    """Nearest-rank quantile: the smallest value at or below which at least `q` of the
    sample lies. Rank ceil(q·n), 1-based — the textbook definition, and the one that
    actually leaves the top of the distribution outside the cutoff."""
    return sorted_sizes[max(0, math.ceil(q * len(sorted_sizes)) - 1)]


def mass_cutoff(sets: list[set[str]], percentile: int = COUPLING_MASS_PERCENTILE) -> int:
    """How many files a commit may touch before it stops being a joint change.

    A 95th percentile needs a sample: its rank is ceil(0.95·n), which for n ≤ 20 equals n
    itself — the cutoff came out EQUAL to the largest commit and not a single one was ever
    skipped. A young repository is exactly where `coupling` is run first, and its initial
    commit holds the whole tree: it paired every file with every other, and three formatting
    sweeps were enough to push those pairs over the threshold.

    Below the sample floor the outlier is found instead by Tukey's fence — Q3 + 1.5·IQR
    (Tukey, Exploratory Data Analysis, 1977), the standard outlier rule, which asks for no
    large sample and leaves a history without outliers untouched.
    """
    sizes = sorted(len(s) for s in sets)
    if not sizes:
        return 0
    if len(sizes) >= COUPLING_MIN_SAMPLE:
        return max(quantile(sizes, percentile / 100), 2)
    q1, q3 = quantile(sizes, 0.25), quantile(sizes, 0.75)
    return max(int(q3 + 1.5 * (q3 - q1)), 2)


def mass_basis(sets: list[set[str]]) -> str:
    """What the cutoff rests on — printed, because a threshold nobody can trace is a guess."""
    if len(sets) >= COUPLING_MIN_SAMPLE:
        return f"the {COUPLING_MASS_PERCENTILE}th percentile of this repository"
    return (f"Tukey's fence over {len(sets)} commits — fewer than {COUPLING_MIN_SAMPLE}, "
            f"too few for a percentile")


def coupling_pairs(owned: dict[str, list[str]], sets: list[set[str]], cutoff: int,
                   min_together: int, min_share: float,
                   hub_at: int) -> tuple[list[dict], list[tuple[str, set[str]]], int]:
    """Cross-block pairs above the thresholds, the hub files, and the number of mass commits skipped."""
    changes: dict[str, int] = {}
    together: dict[tuple[str, str], int] = {}
    skipped = 0
    for files in sets:
        files = {f for f in files if f in owned}
        if not files:
            continue
        if len(files) > cutoff:
            skipped += 1
            continue
        for f in files:
            changes[f] = changes.get(f, 0) + 1
        ordered = sorted(files)
        for i, a in enumerate(ordered):
            for b in ordered[i + 1:]:
                if set(owned[a]) & set(owned[b]):
                    continue  # the same block reads both: not a seam
                together[(a, b)] = together.get((a, b), 0) + 1
    partners: dict[str, set[str]] = {}
    for (a, b), n in together.items():
        if n >= min_together:
            partners.setdefault(a, set()).update(owned[b])
            partners.setdefault(b, set()).update(owned[a])
    hubs = {f for f, bl in partners.items() if len(bl) >= hub_at}
    pairs = []
    for (a, b), n in together.items():
        if n < min_together or a in hubs or b in hubs:
            continue
        share_a, share_b = n / changes[a], n / changes[b]
        if max(share_a, share_b) < min_share:
            continue
        pairs.append({"a": a, "b": b, "blocks_a": owned[a], "blocks_b": owned[b],
                      "together": n, "share_a": share_a, "share_b": share_b})
    pairs.sort(key=lambda p: (-p["together"], -max(p["share_a"], p["share_b"]), p["a"], p["b"]))
    hub_rows = sorted((f, partners[f]) for f in hubs)
    return pairs, hub_rows, skipped


def cmd_coupling(args) -> int:
    """Pairs of files that change together but belong to different blocks — the seams."""
    owned, _, _ = coverage_map()
    sets = commit_file_sets(args.since)
    if not sets:
        print("no commits in the history — nothing to couple")
        return 0
    cutoff = mass_cutoff(sets)
    hub_at = hub_blocks(len(blocks()["blocks"]))
    pairs, hubs, skipped = coupling_pairs(owned, sets, cutoff, args.min_together,
                                          args.min_share, hub_at)
    print(f"commits: {len(sets)}; mass commits skipped (> {cutoff} files, "
          f"{mass_basis(sets)}): {skipped}")
    print(f"thresholds: together ≥ {args.min_together}, share ≥ {args.min_share:.0%}, "
          f"hub = coupled with ≥ {hub_at} blocks\n")
    if hubs:
        print(f"shared nodes ({len(hubs)}) — coupled with many blocks, excluded from the pairs; "
              f"they belong in ref_paths of everyone who touches them:")
        for f, bl in hubs:
            print(f"  {f}  ← {len(bl)} blocks: {', '.join(sorted(bl))}")
        print()
    if not pairs:
        print("no cross-block pairs above the thresholds")
    else:
        print(f"cross-block pairs ({len(pairs)}):")
        for p in pairs:
            ba, bb = "+".join(p["blocks_a"]), "+".join(p["blocks_b"])
            lead, other, lead_block = ((p["a"], p["b"], bb) if p["share_a"] >= p["share_b"]
                                       else (p["b"], p["a"], ba))
            print(f"  {p['together']:>3}×  {ba} {p['a']}  ↔  {bb} {p['b']}  "
                  f"({p['share_a']:.0%} / {p['share_b']:.0%})")
            print(f"        → add `{other}` to ref_paths of the block that reads `{lead}`; "
                  f"hypothesis: a value leaving `{lead}` reaches `{other}` unchanged")
        # a cluster of pairs between the same two blocks is a seam worth its own block
        clusters: dict[tuple[str, str], int] = {}
        for p in pairs:
            key = (p["blocks_a"][0], p["blocks_b"][0])
            clusters[key] = clusters.get(key, 0) + 1
        strong = sorted(((n, k) for k, n in clusters.items() if n >= args.min_together), reverse=True)
        if strong:
            print("\nclusters — several pairs between the same two blocks; a seam block "
                  "(one chain from input to storage, one named instance of the data) is due:")
            for n, (x, y) in strong:
                print(f"  {x} ↔ {y}: {n} pairs")
    if args.write:
        lines = ["a\tblocks_a\tb\tblocks_b\ttogether\tshare_a\tshare_b"]
        for p in pairs:
            lines.append(f"{p['a']}\t{'+'.join(p['blocks_a'])}\t{p['b']}\t{'+'.join(p['blocks_b'])}"
                         f"\t{p['together']}\t{p['share_a']:.2f}\t{p['share_b']:.2f}")
        COUPLING_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"\nwritten: {COUPLING_FILE.relative_to(ROOT)}")
    return 0


# --------------------------------------------------------------------------- order

# Which block next: the cost of failure first, the change frequency second. Measured on
# the first project as a prediction (history split in half, ranking on the first half,
# fixes counted on the second): the top 10% of files by change frequency collected 34% of
# the later fixes, by size 29%, at random 6% — the same as the literature (Nagappan & Ball
# 2005; Moser et al. 2008; Graves et al. 2000). Frequency catches defects; the cost of
# failure catches IRREVERSIBILITY (access, money, the write path), so it stays the first
# key: `risk` on the block (the severity vocabulary), and without it the declared order
# of the blocks is the risk statement.
def block_risk(b: dict) -> int:
    r = b.get("risk")
    if r is None:
        return len(SEVERITIES)  # not stated: after every stated one, in declared order
    if r not in SEVERITIES:
        die(f"blocks.json: block {b['id']}: risk must be one of {', '.join(SEVERITIES)}, not `{r}`")
    return SEVERITIES.index(r)


def block_churn(owned: dict[str, list[str]], sets: list[set[str]], cutoff: int) -> dict[str, tuple[int, int]]:
    """Per block: how many commits touched at least one of its files, and how many of its
    files were touched at all. Mass commits are skipped as in `coupling`."""
    commits: dict[str, int] = {}
    files: dict[str, set[str]] = {}
    for fs in sets:
        fs = {f for f in fs if f in owned}
        if not fs or len(fs) > cutoff:
            continue
        touched: set[str] = set()
        for f in fs:
            for bid in owned[f]:
                touched.add(bid)
                files.setdefault(bid, set()).add(f)
        for bid in touched:
            commits[bid] = commits.get(bid, 0) + 1
    return {bid: (commits.get(bid, 0), len(files.get(bid, ()))) for bid in set(commits) | set(files)}


def cmd_order(args) -> int:
    """Blocks in the order worth walking them: risk first, change frequency second."""
    defn, st = blocks(), state()
    owned, _, _ = coverage_map()
    sets = commit_file_sets(args.since)
    cutoff = mass_cutoff(sets) if sets else 0
    churn = block_churn(owned, sets, cutoff)
    window = f"since {args.since}" if args.since else "whole history"
    print(f"commits: {len(sets)} ({window}); mass commits skipped (> {cutoff} files): "
          f"{sum(1 for fs in sets if len({f for f in fs if f in owned}) > cutoff)}")
    stated = sum(1 for b in defn["blocks"] if b.get("risk"))
    print(f"risk stated on {stated} of {len(defn['blocks'])} blocks"
          + ("" if stated else " — below, change frequency alone speaks; state `risk` on the blocks "
             "to put the cost of failure first, as the method wants"))
    print(f"\n{'':2}{'block':<6}{'risk':<10}{'status':<10}{'commits':>8}{'files':>7}  title")
    moved = 0
    phase = None
    for ph in sorted({b["phase"] for b in defn["blocks"]}):
        print(f"\n── Phase {phase_name(ph)} " + "─" * 40)
        group = [b for b in defn["blocks"] if b["phase"] == ph]
        declared = {b["id"]: i for i, b in enumerate(group)}
        ranked = sorted(group, key=lambda b: (block_risk(b), -churn.get(b["id"], (0, 0))[0], declared[b["id"]]))
        for pos, b in enumerate(ranked):
            status = st["blocks"].get(b["id"], {}).get("status", "todo")
            c, nf = churn.get(b["id"], (0, 0))
            mark = " "
            if status not in ("closed",) and declared[b["id"]] != pos:
                mark = "↑" if declared[b["id"]] > pos else "↓"
                moved += 1
            print(f"{mark:2}{b['id']:<6}{(b.get('risk') or '—'):<10}{status:<10}{c:>8}{nf:>7}  {b['title']}")
    if moved:
        print(f"\n{moved} block(s) would move against the declared order; the order is the human's — "
              f"reorder blocks.json if you agree, or state `risk` where the frequency is misleading")
    else:
        print("\nthe declared order already matches risk and change frequency")
    return 0


# ------------------------------------------------------------------------- summary

ACCEPTANCE_HEADING = re.compile(r"^#{1,6}\s*.*(критери\w* приёмки|acceptance criteri)", re.I)
SUMMARY_MARK = "<!-- finetooth-summary "
SUMMARY_DEFAULT = "docs/review-summary.md"


def acceptance_of(b: dict) -> str:
    """The manifest's acceptance criterion, collapsed to one line for the table."""
    m = REVIEW / "blocks" / f"{b['id']}-{b['slug']}.md"
    if not m.exists():
        return "—"
    body = section_body(m.read_text(encoding="utf-8"), ACCEPTANCE_HEADING)
    if not body:
        return "—"
    # What the criterion SAYS: a fenced example of a table inside it is not part of the
    # sentence, and pasted into a one-line cell it is a run of backticks and column bars.
    text = " ".join(ln.strip() for ln in unquoted(body, "text") if ln.strip())
    text = text.replace("|", "\\|")
    return text if len(text) <= 300 else text[:297] + "…"


def git_head() -> tuple[str, str]:
    return (git("rev-parse", "HEAD").out.strip(),
            git("rev-parse", "--abbrev-ref", "HEAD").out.strip())


def render_summary(defn: dict, st: dict, rows: list[dict]) -> str:
    sha, branch = git_head()
    by_status = {k: 0 for k in FINDING_STATUS}
    for f in rows:
        by_status[f.get("status", "open")] = by_status.get(f.get("status", "open"), 0) + 1
    closed = sum(1 for b in defn["blocks"] if st["blocks"].get(b["id"], {}).get("status") == "closed")
    out = [T("sum_title", project=defn.get("project", "?")), "",
           T("sum_intro", cli=CLI), "",
           T("sum_base", date=now()[:10], sha=sha[:12], branch=branch, closed=closed,
             total=len(defn["blocks"]), total_f=len(rows), fixed=by_status["fixed"],
             rejected=by_status["rejected"], deferred=by_status["deferred"],
             dups=by_status["duplicate"], open=by_status["open"]), ""]
    out += [T("sum_blocks"), "", T("sum_blocks_head"), "|---|---|---|---|---|---|---|"]
    for b in defn["blocks"]:
        s = st["blocks"].get(b["id"], {})
        n_files = len(git_files(b.get("paths", []))) if b.get("paths") else 0
        out.append(f"| {b['id']} | {b['title']} | {s.get('status', 'todo')} | "
                   f"{(s.get('finished') or '')[:10]} | {n_files} | `{s.get('reviewed_sha') or '—'}` | "
                   f"{acceptance_of(b)} |")
    out.append("")
    def finding_line(f: dict, reason_key: str | None) -> str:
        where = f"`{f.get('file')}:{f.get('line')}`" if f.get("line") else f"`{f.get('file')}`"
        line = f"- **{f.get('id')}** ({f.get('severity')}) {where} — {f.get('claim', '').strip()}"
        if reason_key and f.get(reason_key):
            line += f"  \n  *{f[reason_key].strip()}*"
        return line
    rejected = [f for f in rows if f.get("status") == "rejected"]
    out += [T("sum_rejected"), ""]
    out += [finding_line(f, "reject_reason") for f in rejected] or [T("sum_rejected_none")]
    out.append("")
    deferred = [f for f in rows if f.get("status") == "deferred"]
    out += [T("sum_deferred"), ""]
    out += [finding_line(f, "defer_reason") for f in deferred] or [T("sum_deferred_none")]
    out.append("")
    out += [T("sum_classes"), ""]
    rules: dict[str, list[str]] = {}
    for f in rows:
        if f.get("rule"):
            rules.setdefault(f["rule"], []).append(f.get("id", "?"))
    fixed = [f for f in rows if f.get("status") == "fixed"]
    if rules:
        out.append(T("sum_classes_rules"))
        out += [f"- `{rule}` — {', '.join(ids)}" for rule, ids in sorted(rules.items())]
        out.append("")
    if fixed:
        out.append(T("sum_classes_fixes"))
        out += [f"- {f.get('id')} → `{f.get('fix_commit') or ', '.join(f.get('fixed_in', []))}`"
                for f in fixed]
        out.append("")
    if not rules and not fixed:
        out += [T("sum_classes_none"), ""]
    open_rows = [f for f in rows if f.get("status") == "open"]
    out += [T("sum_open"), ""]
    out += [finding_line(f, None) for f in open_rows] or [T("sum_open_none")]
    out.append("")
    if COUPLING_FILE.exists():
        lines = COUPLING_FILE.read_text(encoding="utf-8").splitlines()[1:]
        if lines:
            out += [T("sum_seams"), ""]
            out += ["- " + " ↔ ".join(f"{c[1]} `{c[0]}`" for c in
                    [(x.split("\t")[0], x.split("\t")[1]), (x.split("\t")[2], x.split("\t")[3])])
                    + f" ({x.split(chr(9))[4]}×)" for x in lines[:50]]
            out.append("")
    machine = {"base": sha, "blocks": {b["id"]: {"title": b["title"], "paths": b.get("paths", [])}
                                        for b in defn["blocks"]}}
    out += [T("sum_machine"), "", SUMMARY_MARK + json.dumps(machine, ensure_ascii=False) + " -->", ""]
    return "\n".join(out)


def cmd_summary(args) -> int:
    """The one file that outlives docs/review/: what was checked, against which revision,
    what was rejected and why, what closes each class. With --aged: how far each block has
    drifted from the summary's base commit — the only thing a re-run needs to start from."""
    if args.aged:
        path = Path(args.aged)
        if not path.is_absolute():
            path = ROOT / path
        if not path.exists():
            die(f"no such summary: {path}")
        text = path.read_text(encoding="utf-8")
        i = text.find(SUMMARY_MARK)
        if i < 0:
            die(f"{path.name} carries no machine block — was it written by `summary`?")
        # The machine block is one line: `<!-- finetooth-summary {…} -->`. Cut at the LAST
        # `-->` of that line, not at the first ` -->` in the file: a block whose title holds
        # the marker (`Import --> export pipeline`) is written into the block verbatim, and
        # cutting at the first one left half a JSON object and a traceback in the user's
        # face — on the one file that is meant to outlive docs/review/.
        raw = text[i + len(SUMMARY_MARK):].split("\n", 1)[0].rstrip()
        if not raw.endswith("-->"):
            die(f"{path.name}: the machine block is not closed with `-->` — "
                f"it is generated, not written by hand; regenerate it with `{CLI} summary`")
        try:
            machine = json.loads(raw[:-3].strip())
        except json.JSONDecodeError as exc:
            die(f"{path.name}: the machine block is not valid JSON ({exc}) — "
                f"it is generated, not written by hand; regenerate it with `{CLI} summary`")
        base = machine["base"]
        n = git("rev-list", "--count", f"{base}..HEAD").out.strip() or "0"
        print(T("aged_head", sha=base[:12], n=n))
        drift = []
        for bid, info in machine["blocks"].items():
            if not info.get("paths"):
                continue
            records = log_records("--name-only", f"{base}..HEAD", "--", *info["paths"])
            files = {p for _sha, paths in records for p in paths}
            if records:
                drift.append((len(records), len(files), bid, info.get("title", "")))
        if not drift:
            print(T("aged_none"))
            return 0
        for commits, files, bid, title in sorted(drift, reverse=True):
            print(T("aged_row", block=bid, commits=commits, files=files, title=title))
        return 0
    defn, st, rows = blocks(), state(), findings()
    text = render_summary(defn, st, rows)
    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text + "\n", encoding="utf-8")
    print(f"written: {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}")
    return 0


# ------------------------------------------------------------------------- sarif
#
# The findings of the register as SARIF 2.1.0, for GitHub code scanning (the Security tab and
# the lines of a pull request). Every decision below is taken from one of two sources, and
# each names which:
#   OASIS SARIF 2.1.0 (errata 01) —
#     https://docs.oasis-open.org/sarif/sarif/v2.1.0/errata01/os/sarif-v2.1.0-errata01-os-complete.html
#   GitHub, "SARIF support for code scanning" —
#     https://docs.github.com/en/code-security/code-scanning/integrating-with-code-scanning/sarif-support-for-code-scanning
#
# What is exported: `open` and `deferred`. `fixed`, `rejected` and `duplicate` are closed —
# an alert for them would be a defect GitHub shows as present when the register says it is
# not. A deferred finding is still in the code: the kit calls it an accepted risk (it is
# published in the summary with its reason), and SARIF has the exact word for that — a
# `suppression` with `status: "accepted"` and a `justification` (§3.27.23, §3.35). `kind`
# is `external` because the decision lives in the register, not in a comment in the source
# (§3.35.2). GitHub does not read `suppressions` (they are not in its list of supported
# properties, and suppressed results are still shown as open alerts — acknowledged by GitHub
# in community discussion #156737), so the message also SAYS "accepted risk" in its first
# sentence, the one GitHub displays when space is short.
#
# `security-severity` is NOT written. GitHub reads it on the RULE ("if you include a value for
# this field, results for the rule are treated as security results"), a rule here is a defect
# class holding findings of different severities, and the register has no field that says a
# finding is a vulnerability — deciding it from the wording of the claim is guessing, and a
# guess would move code-quality findings into the security severity scale. Without it the
# alerts are shown with their `level` (error / warning / note), which the register does know.

# Severity → SARIF `level` (§3.27.10: none | note | warning | error). The fix gate treats
# high and above as what blocks the next block (FIX_GATE_DEFAULT), so both are `error`;
# `note` is the level for a finding that is worth knowing and not worth failing a build.
SARIF_LEVEL = {"critical": "error", "high": "error", "medium": "warning", "low": "note"}
# Statuses that leave the review with the defect still in the code. The others are closed.
SARIF_STATUSES = ("open", "deferred")
# GitHub: `shortDescription.text` and `fullDescription.text` are "limited to 1024 characters".
SARIF_TEXT_MAX = 1024
SARIF_SCHEMA = "https://json.schemastore.org/sarif-2.1.0.json"
KIT_URI = "https://github.com/mikey-semy/finetooth"


def sarif_text(text: str) -> str:
    return text if len(text) <= SARIF_TEXT_MAX else text[:SARIF_TEXT_MAX - 1] + "…"


def sarif_rule_id(f: dict) -> str:
    """The rule is the finding's defect class: the `root`, written the same way in every
    instance of the class, is exactly what a rule is — one id many results point at. A finding
    with no class gets its block's id: the finding still has to be filterable by something."""
    return (f.get("root") or "").strip() or f.get("block", "?")


def sarif_report(b: dict | None) -> str | None:
    """The block report the finding is argued in: the verifier's, whose verdict put it into
    the register, or the hunter's when there is no verifier's yet. A path from the root, like
    every path in the register; no link is built from a remote — the kit does not know the
    platform, and a relative `helpUri` would resolve against GitHub, not the repository."""
    if not b:
        return None
    for role in ("verify", "hunter"):
        rel = report_path(b, role)
        if (ROOT / rel).is_file():
            return rel
    return None


def render_sarif(defn: dict, rows: list[dict]) -> dict:
    idx = block_index(defn)
    live = [f for f in rows if f.get("status", "open") in SARIF_STATUSES]
    classes: dict[str, list[dict]] = {}
    for f in live:
        classes.setdefault(sarif_rule_id(f), []).append(f)
    rule_ids = sorted(classes)
    rules = []
    for rid in rule_ids:
        items = classes[rid]
        first = items[0]
        if (first.get("root") or "").strip():
            short = T("sarif_rule_root", root=rid)
        else:
            b = idx.get(first.get("block", ""), {})
            short = T("sarif_rule_block", block=rid, title=b.get("title", "?"))
        guards = sorted({f["rule"] for f in items if f.get("rule")})
        full = short + (". " + T("sarif_rule_guard", rules=", ".join(guards)) if guards else "")
        # The rule's default is its most severe instance: a result overrides it anyway
        # ("this level overrides the default severity defined by the rule" — GitHub).
        worst = min((SEVERITIES.index(f["severity"]) for f in items
                     if f.get("severity") in SEVERITIES), default=SEVERITIES.index("medium"))
        rules.append({
            "id": rid,
            "shortDescription": {"text": sarif_text(short)},
            "fullDescription": {"text": sarif_text(full)},
            "help": {"text": T("sarif_rule_help", ids=", ".join(f.get("id", "?") for f in items))},
            "helpUri": KIT_URI,
            "defaultConfiguration": {"level": SARIF_LEVEL[SEVERITIES[worst]]},
            "properties": {"tags": ["finetooth", "review"]},
        })
    results = []
    review_id = defn.get("review_id", "")
    for f in live:
        fid = f.get("id", "?")
        report = sarif_report(idx.get(f.get("block", "")))
        deferred = f.get("status") == "deferred"
        parts = [(T("sarif_deferred") if deferred else "") + (f.get("claim") or "").strip()]
        if (f.get("scenario") or "").strip():
            parts.append(f["scenario"].strip())
        if deferred and (f.get("defer_reason") or "").strip():
            parts.append(T("sarif_deferred_why", reason=f["defer_reason"].strip()))
        if report:
            parts.append(T("sarif_report", path=report))
        rid = sarif_rule_id(f)
        result = {
            "ruleId": rid,
            "ruleIndex": rule_ids.index(rid),
            "level": SARIF_LEVEL.get(f.get("severity"), "warning"),
            "message": {"text": "\n\n".join(parts)},
            # GitHub: "code scanning only uses the `primaryLocationLineHash`" to match a
            # result across runs. Left out, `upload-sarif` fills it with a hash of the line's
            # text, and every edit of that line opens a new alert beside the old one. The
            # finding's identity is its id — prefixed with the review, because the next
            # review numbers from H1-001 again. The action logs a warning that the value is
            # not the hash it computed, and keeps ours (codeql-action src/fingerprints.ts).
            "partialFingerprints": {"primaryLocationLineHash": f"{review_id}/{fid}",
                                    "finetoothFinding/v1": f"{review_id}/{fid}"},
            "properties": {"finding": fid, "block": f.get("block"),
                           "severity": f.get("severity"), "confidence": f.get("confidence"),
                           "status": f.get("status", "open"),
                           **({"report": report} if report else {})},
        }
        if f.get("file"):
            # A relative reference from the repository root (GitHub: "interprets results
            # that are reported with relative paths as relative to the root of the GitHub
            # repository analyzed"), percent-encoded because `uri` is an RFC 3986 string
            # (§3.10.1): a space or a Cyrillic letter is not allowed in one raw, and
            # `upload-sarif` decodes it back with decodeURIComponent.
            uri = quote(f["file"].removeprefix("./"), safe="/")
            # GitHub lists `region.startLine` as required. A finding without a line is about
            # the whole file, and line 1 is what the action itself hashes for such a result.
            line = f.get("line") if isinstance(f.get("line"), int) and f["line"] >= 1 else 1
            result["locations"] = [{"physicalLocation": {
                "artifactLocation": {"uri": uri},
                "region": {"startLine": line}}}]
        if deferred:
            why = (f.get("defer_reason") or "").strip()
            result["suppressions"] = [{"kind": "external", "status": "accepted",
                                       **({"justification": why} if why else {})}]
        results.append(result)
    return {
        "$schema": SARIF_SCHEMA,
        "version": "2.1.0",
        "runs": [{
            "tool": {"driver": {"name": "finetooth", "version": VERSION,
                                "semanticVersion": VERSION, "informationUri": KIT_URI,
                                "rules": rules}},
            "results": results,
        }],
    }


def cmd_sarif(args) -> int:
    """The open and deferred findings of the register as SARIF 2.1.0 — for GitHub code
    scanning, uploaded by `github/codeql-action/upload-sarif`. Printed to stdout; `--out`
    writes a file instead, wherever it says (the one other place the tool writes outside
    docs/review/, beside `summary` — SECURITY.md names both)."""
    defn, rows = blocks(), findings()
    text = json.dumps(render_sarif(defn, rows), ensure_ascii=False, indent=2) + "\n"
    if not args.out:
        sys.stdout.write(text)
        return 0
    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"written: {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}")
    return 0


# -------------------------------------------------------------------------- refs

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
    args += ["--", ".", ":(exclude)docs/review/**"]
    hits = []
    for record in git(*args).records:
        # A record git prints short (no line number for some reason) is not worth a
        # traceback: the fields that are there are read, the rest come out empty.
        path, num, text = (record + ["", ""])[:3]
        for fid in ids:
            if re.search(rf"(?<![\w-]){re.escape(fid)}(?![\w-])", text):
                hits.append((path, int(num) if num.isdigit() else 0, fid, text.strip()))
    return hits


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


# ------------------------------------------------------------------------- prompt

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


def report_path(b: dict, role: str, rnd: int = 1, scope: str | None = None) -> str:
    """Where a role writes its report. Rounds and halves of the fix review get their own
    names — otherwise they are named by hand, and differently every time."""
    base = f"docs/review/reports/{b['id']}-{b['slug']}"
    if role == "fixreview":
        return f"{base}.fixreview-{rnd}{'-' + scope if scope else ''}.md"
    if role == "fix" and rnd > 1:
        return f"{base}.fix-{rnd}.md"
    return f"{base}.{role}.md"


def diff_text(rng: str) -> str:
    """The whole diff of a range, for the fix reviewer: it reads the diff, not a report about it."""
    stat = git("diff", "--stat", rng)
    full = git("diff", rng)
    if full.code != 0:
        die(f"git diff {rng}: {full.err.strip()}")
    if not full.out.strip():
        die(f"diff {rng} is empty — the fix reviewer has nothing to read")
    # A fence of four backticks: triple ones occur inside a diff.
    return f"{stat.out}\n````diff\n{full.out}\n````"


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
        "{{RECORDED}}": render_recorded_for(b["id"]),
        "{{NEXT_ID}}": next_finding_id(b["id"]),
        # The project name and its gates are substitutions, not text in the template. A
        # template copied without proofreading greeted the agent on behalf of ANOTHER
        # project, and it was not noticed at once: the assignment looked meaningful as a whole.
        "{{PROJECT}}": defn.get("project", ROOT.name),
        "{{GATES}}": "\n".join(f"- `{g}`" for g in defn.get("gates", []))
        or T("gates_missing"),
        # Read from the project's files only when the template asks: a hunter has no
        # commits to make, and the lookup is a git run per file it reads.
        "{{COMMIT_RULES}}": commit_rules(args.role, args.diff or "")
        if "{{COMMIT_RULES}}" in body else "",
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


def block_findings_path(b: dict) -> Path:
    return REVIEW / "reports" / f"{b['id']}-findings.jsonl"


def next_finding_id(block_id: str) -> str:
    """The id `import --append` will give the block's first new finding: after the highest
    number the block has ever used — numbers have gaps, and a retired id stays retired."""
    taken = [int(m.group(1)) for f in findings()
             if (m := re.fullmatch(rf"{re.escape(block_id)}-(\d+)", f.get("id", "")))]
    return f"{block_id}-{max(taken, default=0) + 1:03d}"


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
    for f in sorted(rows, key=lambda f: f.get("id", "")):
        where = f.get("file", "") + (f":{f['line']}" if f.get("line") else "")
        out.append(T("rec_row", id=f.get("id", "?"), severity=f.get("severity", "?"),
                     status=f.get("status", "?"), where=where, claim=f.get("claim", ""),
                     date=(f.get("imported_at") or "")[:10]))
    return "\n".join(out)


def render_findings_for(block_id: str) -> str:
    rows = [f for f in findings() if f.get("block") == block_id and f.get("status") == "open"]
    if not rows:
        return T("no_open_findings")
    order = {s: i for i, s in enumerate(SEVERITIES)}
    rows.sort(key=lambda f: (order.get(f.get("severity"), 9), f.get("id", "")))
    out = []
    for f in rows:
        where = f.get("file", "")
        if f.get("line"):
            where += f":{f['line']}"
        out.append(
            f"### {f['id']} · {f.get('severity')} · {T('f_conf')} {f.get('confidence')}\n"
            f"{T('f_where')} `{where}`\n\n"
            f"{T('f_claim')} {f.get('claim','')}\n\n"
            f"{T('f_scenario')} {f.get('scenario','')}\n"
            + (f"\n{T('f_invariant')} {f.get('invariant')}\n" if f.get("invariant") else "")
        )
    return "\n".join(out)


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

    incoming = []
    for n, line in enumerate(src.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            die(f"{src.name} line {n}: not JSON — {exc}")
        # The limits `check` holds are held here too: a draft that `import` accepted and
        # `check` then refused made every later gate red on a row nobody could fix through
        # the tool (the kit's own review hit it three times).
        for field, limit in (("claim", CLAIM_MAX), ("scenario", SCENARIO_MAX)):
            if isinstance(row, dict) and len(str(row.get(field) or "")) > limit:
                die(f"{src.name} line {n}: {field} is {len(str(row[field]))} characters against a "
                    f"limit of {limit} — shorten it in the draft; the evidence belongs in the report")
        incoming.append(row)

    # A row numbered for ANOTHER block (`V2-001` in the file of H1) is refused on every
    # path: the top-up skipped it silently as "already known", and the plain import would
    # file it under this block with a foreign number (the kit author's review, 24.09).
    other = [f.get("id") for f in incoming
             if isinstance(f.get("id"), str) and (m := re.fullmatch(r"(.+)-(\d+)", f["id"]))
             and m.group(1) != args.block]
    if other:
        die(f"{src.name}: rows numbered for another block — {', '.join(other)}; a block's file "
            f"holds that block's findings only: remove the rows or import them with their own block")

    existing = findings()
    if args.append:
        # TOP-UP IMPORT: findings found on top of what is already recorded. The regular
        # import replaces the block's findings wholesale, and for a block where part is
        # already fixed that would erase the fix marks — a neighbouring project got burnt
        # by this and started a separate consolidator. Here we only append, with the
        # block's next free numbers.
        taken = [
            int(m.group(1))
            for f in existing
            if f.get("block") == args.block
            and (m := re.fullmatch(rf"{re.escape(args.block)}-(\d+)", f.get("id", "")))
        ]
        next_n = max(taken, default=0) + 1
        known = {e.get("id") for e in existing}
        added = []
        for f in incoming:
            # After the previous import the block's file holds the already recorded findings
            # with their numbers — the top-up appends new lines to it. What is recorded is
            # skipped: the register knows more about it (status, fix), and the block's file
            # does not override it.
            fid = f.get("id")
            if fid in known:
                continue
            f.setdefault("block", args.block)
            if f["block"] != args.block:
                die(f"the top-up file holds a finding of another block {f['block']} — the import is stopped")
            f["id"] = f"{args.block}-{next_n:03d}"
            next_n += 1
            f.setdefault("status", "open")
            f.setdefault("confidence", "plausible")
            f.setdefault("fix_commit", None)
            f.setdefault("dup_of", None)
            if found_in:
                f["found_in"] = dict(found_in)
            f["imported_at"] = now()
            put_fingerprint(f, code_fingerprint(f.get("file", ""), f.get("line"))
                            or {"code_sha": None})
            added.append(f)
        with FINDINGS_FILE.open("a", encoding="utf-8") as fh:
            for f in added:
                fh.write(json.dumps(f, ensure_ascii=False) + "\n")
        # The numbers are written back into the block's file — as with the regular import.
        # A repeated run recognises them and appends nothing; renaming the file as
        # "consolidated" is unnecessary, and that rename used to carry the whole block's
        # file away.
        src.write_text(
            "\n".join(json.dumps(f, ensure_ascii=False) for f in incoming) + "\n",
            encoding="utf-8",
        )
        print(f"{args.block}: appended {len(added)} findings (top-up import)")
        print(f"do not forget: {CLI} findings && {CLI} check")
        return 0

    mine = [f for f in existing if f.get("block") == args.block]
    if mine and not args.force:
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
            die(f"block {args.block}: the plain import would replace what is recorded — "
                f"{'; '.join(parts)}. Add the new findings with `{CLI} import {args.block} --append` "
                f"(what is recorded stays, new rows get the next free numbers), or replace the "
                f"whole set deliberately with --force")

    kept = [f for f in existing if f.get("block") != args.block]
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
            die(f"{src.name}: two rows carry the id {fid} — an id is unique within a block; "
                f"delete the id field of the row that is new and the import will hand out a "
                f"free number")
        if fid:
            seen_here.add(fid)
    numbered = [int(m.group(1)) for fid in taken
                if (m := re.fullmatch(rf"{re.escape(args.block)}-(\d+)", fid))]
    next_n = max(numbered, default=0) + 1
    width = 3
    for f in incoming:
        f.setdefault("block", args.block)
        if not f.get("id"):
            f["id"] = f"{args.block}-{next_n:0{width}d}"
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
        if (prev and prev.get("file") == f.get("file")
                and (prev.get("code_sha") or prev.get("region_sha"))):
            put_fingerprint(f, {k: prev[k] for k in CODE_FINGERPRINT_FIELDS if k in prev})
            if prev.get("region_sha") and "line" in prev:
                f["line"] = prev["line"]
        else:
            put_fingerprint(f, code_fingerprint(f.get("file", ""), f.get("line"))
                            or {"code_sha": None})
        if f.get("confidence") == "rejected":
            f["status"] = "rejected"
    merged = kept + incoming
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


# ------------------------------------------------------------------ loop signal
#
# The kit's own review ran three blocks through two and three fix rounds each (T2–T4, issue
# #9). From round 2 on, almost every fix-review finding sat in the code the previous round
# had written — mostly inside the guard that round added to close a class — and each round's
# guard got its own hole found by the next. The round counter is not the signal; the place
# is: when the top finding of fix review N−1 lies on a line fix round N−1 changed, round N
# repeats the pattern, and what stopped it every time was a human's decision. So the tool
# asks for that decision before another round, and carries it into the next prompts.


def pinned_range(rng: str) -> str | None:
    """`A...B` or `A..B` as `<base>..<tip>` commit ids, or None when it is not a range of commits.

    `git diff A...B` is the diff from their merge base to B, so that is the base pinned. A
    symbolic range moves with the branch: `main...HEAD` read after the next round commits is
    another diff, and a finding would be judged against lines its round never wrote.
    """
    sym = "..." in rng
    a, sep, b = rng.partition("..." if sym else "..")
    if not sep or a.startswith("-") or b.startswith("-"):
        return None
    a, b = a or "HEAD", b or "HEAD"
    tip = git("rev-parse", "--verify", "--quiet", f"{b}^{{commit}}")
    base = (git("merge-base", a, b) if sym
            else git("rev-parse", "--verify", "--quiet", f"{a}^{{commit}}"))
    if tip.code != 0 or base.code != 0 or not base.out.split():
        return None
    return f"{base.out.split()[0]}..{tip.out.strip()}"


# A hunk header of `git diff -U0`: the new side starts at `+c` and runs `d` lines, and a
# missing `,d` means one line (git's own convention). `d` = 0 is a pure deletion: no line of
# the new file was written by it.
DIFF_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", re.M)


def diff_spans(rng: str, rel: str) -> list[tuple[int, int]] | None:
    """The lines of `rel` the range wrote, as `(first, last)` spans of the new side; None when
    git cannot read the range. Asked per file, so no path is parsed out of a patch."""
    out = git("diff", "--no-ext-diff", "--no-color", "-U0", rng, "--", f":(literal){rel}")
    if out.code != 0:
        return None
    spans = []
    for m in DIFF_HUNK.finditer(out.out):
        first, count = int(m.group(1)), int(m.group(2) or "1")
        if count:
            spans.append((first, first + count - 1))
    return spans


def found_round(f: dict) -> int | None:
    """The fix review round that found the finding, when `import --round` recorded one.
    Records from before the field — and anything hand-written in its place — have none."""
    fi = f.get("found_in")
    if not isinstance(fi, dict) or fi.get("role") != "fixreview":
        return None
    rnd = fi.get("round")
    return rnd if isinstance(rnd, int) and not isinstance(rnd, bool) else None


def last_review_round(block_id: str, rows: list[dict]) -> int:
    """The latest fix review round that put findings into the block's register; 0 if none."""
    return max((r for f in rows if f.get("block") == block_id
                and (r := found_round(f)) is not None), default=0)


def in_own_diff(f: dict) -> bool:
    """Does the finding's file:line lie on a line its round's diff wrote? By LINE, not by
    file: a finding elsewhere in a file the round touched is not the round's own code."""
    line, rng = f.get("line"), (f.get("found_in") or {}).get("diff")
    if not isinstance(line, int) or isinstance(line, bool) or not rng or not f.get("file"):
        return False
    return any(a <= line <= b for a, b in diff_spans(str(rng), f["file"]) or [])


def decisions() -> list[dict]:
    """The human's decisions, in the order they were taken."""
    if not DECISIONS_FILE.exists():
        return []
    out = []
    for n, line in enumerate(DECISIONS_FILE.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            die(f"{DECISIONS_FILE.relative_to(ROOT)} line {n}: not JSON — {exc}; it is written "
                f"by `{CLI} decide`, fix the line by hand")
        if isinstance(row, dict):
            out.append(row)
    return out


def loop_stop(block_id: str, rnd: int, rows: list[dict]) -> str | None:
    """Why fix round `rnd` is a human's move, not the next agent's — or None.

    The top finding of fix review `rnd − 1` (by severity, among its open ones) is medium or
    higher and lies inside the diff of fix round `rnd − 1`, and no decision was recorded
    after that review. Findings without `found_in` take no part: nothing says which round
    found them.
    """
    prev = rnd - 1
    if prev < 1:
        return None
    theirs = [f for f in rows if f.get("block") == block_id and f.get("status") == "open"
              and found_round(f) == prev]
    order = {s: i for i, s in enumerate(SEVERITIES)}
    top = min((order.get(f.get("severity"), len(order)) for f in theirs), default=len(order))
    if top > order[ROUND_SEVERITY]:
        return None
    inside = [f for f in sorted(theirs, key=lambda f: f.get("id", ""))
              if order.get(f.get("severity")) == top and in_own_diff(f)]
    if not inside:
        return None
    if any(d.get("block") == block_id and isinstance(d.get("round"), int)
           and d["round"] >= prev for d in decisions()):
        return None
    f = inside[0]
    return T("loop_stop", id=f.get("id"), sev=f.get("severity"), file=f.get("file"),
             line=f.get("line"), prev=prev, diff=f["found_in"]["diff"], cli=CLI, block=block_id)


def render_decisions_for(block_id: str) -> str:
    rows = [d for d in decisions() if d.get("block") == block_id]
    if not rows:
        return T("dec_none")
    return "\n".join(T("dec_row", date=str(d.get("at") or "")[:10], round=d.get("round", "?"),
                       text=d.get("text", "")) for d in rows)


def journal(block: str, text: str) -> None:
    """Append a dated line to the journal — the log a human reads."""
    if not JOURNAL_FILE.exists():
        JOURNAL_FILE.write_text(T("journal_head"), encoding="utf-8")
    with JOURNAL_FILE.open("a", encoding="utf-8") as fh:
        fh.write(f"- **{now()}** · `{block}` — {text}\n")


def cmd_decide(args) -> int:
    """Record a human's decision on a block: the answer to the loop signal."""
    if args.block not in block_index(blocks()):
        die(f"unknown block {args.block}")
    text = " ".join(args.text.split())
    if not text:
        die("the decision is empty — write what was decided: the next fixer gets it as it is")
    rnd = last_review_round(args.block, findings()) if args.round is None else args.round
    if rnd < 0:
        die(f"--round {rnd}: rounds are counted from 1 (0 — before any fix review)")
    row = {"block": args.block, "round": rnd, "at": now(), "text": text}
    with DECISIONS_FILE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    # The journal is where a human looks for what was decided; the file is what the tool reads.
    journal(args.block, f"decision after fix review round {rnd}: {text}")
    print(f"{args.block}: decision recorded after fix review round {rnd} — "
          f"`{CLI} prompt {args.block} --role fix --round {rnd + 1}` carries it")
    return 0


# --------------------------------------------------------------------- set-status


def cmd_set_status(args) -> int:
    defn, st = blocks(), state()
    if args.block not in block_index(defn):
        die(f"unknown block {args.block}")
    if args.status not in STATUSES:
        die(f"unknown status {args.status}; known: {', '.join(STATUSES)}")
    s = st["blocks"].setdefault(
        args.block, {"status": "todo", "started": None, "finished": None, "reports": [], "note": ""}
    )
    if args.status == "running":
        debt = fix_debt(defn, findings(), except_block=args.block)
        if debt:
            ids = ", ".join(f"{f.get('id')} ({f.get('severity')})" for f in debt[:8])
            more = f" and {len(debt) - 8} more" if len(debt) > 8 else ""
            die(f"fix gate: {len(debt)} open finding(s) at `{fix_gate(defn)}` or above in the blocks "
                f"already passed — {ids}{more}. The next block does not start on top of unfixed "
                f"serious findings: fix them (`{CLI} set-finding <id> fixed --commit <sha>`), defer "
                f"with a reason (`deferred --reason \"…\"`) or reject (`rejected --reason \"…\"`). "
                f"To switch the gate off for this project: `\"fix_gate\": \"none\"` in blocks.json")
    s["status"] = args.status
    # The timestamp is set on EVERY entry into running, not only the first: a block
    # returned to work three weeks later would otherwise count as stuck at once, and the
    # check advised restarting exactly what was being worked on.
    if args.status == "running":
        s["started"] = now()
    if args.status == "closed":
        s["finished"] = now()
    # Fingerprint of WHAT exactly was reviewed. A "passed" status without it holds forever:
    # the block's files get rewritten, and the block still counts as closed — what was
    # reviewed turns out to be a different text. The form is taken from doorstop, where a
    # requirement has a `reviewed` field with a content hash, and an edit of the text by
    # itself moves it to "unreviewed changes".
    # Only at the points where the review is COMPLETE: verification (verified) and closing
    # after the diff review (closed). Moving to triaged or fixing is not a review; re-take
    # the fingerprint there, and any status change would silently declare the changed code
    # reviewed, bypassing `restamp`, which exists precisely so that this is said on record.
    if args.status in ("verified", "closed"):
        stamp(block_index(defn)[args.block], s)
    if args.report:
        for r in args.report:
            if r not in s["reports"]:
                s["reports"].append(r)
    if args.note:
        s["note"] = args.note
    st["updated_at"] = now()
    save_json(STATE_FILE, st)
    print(f"{args.block}: {args.status}")
    return 0


# -------------------------------------------------------------------- set-finding


def cmd_set_finding(args) -> int:
    """Move a finding: fixed, rejected, duplicate, deferred.

    The rule "findings.jsonl is edited only by the tool" rested on the agent's own word:
    the kit had no command that sets `fixed` and the fix commit — the register was edited
    by hand, and by hand one sets both `fixed` without a commit and `rejected` without a
    reason. Here the move passes the same checks as `check`, and the file is regenerated
    together with the record.
    """
    if len(args.finding) > 1 and args.dup_of:
        die("--dup-of takes one finding: several cannot meaningfully share the same duplicate target")
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


# ------------------------------------------------------------------------ findings


def render_findings_md(rows: list[dict]) -> str:
    """Render findings.md from the finding rows.

    Deliberately a PURE function of `findings.jsonl`: no wall clock, no counts
    of anything not in the rows. A generation stamp would make every run of
    `review.py findings` a diff, so the file would arrive in review commits as
    noise and `review-check` could not tell a stale render from a fresh one by
    comparing content. When the file changed is a question git already answers.
    """
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
            where = f.get("file", "")
            if f.get("line"):
                where += f":{f['line']}"
            claim = (f.get("claim", "") or "").replace("|", "\\|").replace("\n", " ")
            out.append(
                f"| {f.get('id','')} | {f.get('block','')} | {f.get('status','')} | "
                f"`{where}` | {claim} |"
            )
        out.append("")
    return "\n".join(out) + "\n"


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


# --------------------------------------------------------------------------- check


# How many lines an agent really reads in one session. The number is not invented: a
# neighbouring project went through a 1727-line block in six runs and two hours, while an
# 87-thousand-line block reported on 4 files out of 14 — that is, it lied about coverage
# without breaking a single check. The ceiling is three times what was read, with margin,
# to catch what is plainly impossible.
READABLE_LINES = 6000  # default; overridden by the `readable_lines` field in blocks.json

# Below this a manifest holds nothing but its own headings. Measured on the scaffold the
# kit itself hands out: the six headings of `assets/manifest.example.md`, with the title,
# come to 171 characters, and a manifest copied and not filled in is exactly that file with
# the text deleted. 200 is the first round number above it, so the gate catches the empty
# copy and not a terse real one — the shortest real manifest measured here is 4 743
# characters, more than twenty times the bound.
MANIFEST_MIN_CHARS = 200


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


def cmd_restamp(args) -> int:
    """Confirm that the changes in the block's files were reviewed, and re-take the fingerprint.

    Exactly like `doorstop review`: not "switch the check off", but say on record that the
    new text was seen. That is why the command demands the block by name and prints what
    exactly it stamps.
    """
    defn, st = blocks(), state()
    idx = block_index(defn)
    if args.block not in idx:
        return restamp_finding(args.block, args.line)
    if args.line is not None:
        die(f"--line belongs to a finding, not to a block: {args.block} is a block — its "
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
    rel = f.get("file", "")
    if not file_sha(rel):
        die(f"file {f.get('file')} does not exist — a finding is moved (`{CLI} set-finding`), not stamped")
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
        print(f"{fid}: the fingerprint already matches {f.get('file')} — nothing to stamp")
        return 0
    put_fingerprint(f, fp)
    if "region_sha" in fp:
        f["line"] = at
    f["restamped_at"] = now()
    with FINDINGS_FILE.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    FINDINGS_MD.write_text(render_findings_md(rows), encoding="utf-8")
    print(f"{fid}: code fingerprint re-taken — the defect is confirmed on the current version of {f.get('file')}")
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


def cited_line_now(f: dict, lines: list[bytes]) -> int:
    """Where the line a whole-file record cites is in the current file.

    The old fingerprint is the blob the finding was last stamped on, and its line was cited
    on that version. When git still has the blob, the window around the line is taken there
    and looked for here; not found (the code under it changed, or the blob is gone) — the
    recorded line stands, and `restamp` prints what it reads so a human sees the anchor.
    """
    sha = f.get("code_sha")
    if isinstance(sha, str) and re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", sha):
        old = git("cat-file", "blob", sha, binary=True)
        if old.code == 0 and b"\0" not in old.out[:8192]:
            region = take_region([ln.rstrip() for ln in old.out.splitlines()], f.get("line"))
            if region:
                found = locate_region({**region, "line": f.get("line")}, lines)
                if found:
                    return found
    return f.get("line")


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


def cmd_roots(args) -> int:
    """Roots: how many instances each has and which guard each instance is recorded under."""
    rows = findings()
    groups = roots_of(rows, args.block)
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
            where = f.get("file", "")
            if f.get("line"):
                where += f":{f['line']}"
            print(f"       {f.get('id','?'):<10} {f.get('status','?'):<9} {where}")
    return 0


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
            fp = code_fingerprint(f.get("file", ""), f.get("line"))
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
    if not JOURNAL_FILE.exists():
        JOURNAL_FILE.write_text(T("journal_head"), encoding="utf-8")
    with JOURNAL_FILE.open("a", encoding="utf-8") as fh:
        fh.write(f"- **{now()}** · `backfill` — {note}\n")
    print(note)
    return 0


# ------------------------------------------------------------------- hypotheses

# The second denominator of coverage. The file map answers "the file was opened", and
# that is not enough: a file can be opened and nothing understood. A professional audit
# counts coverage not in files but in questions to the system — in OWASP ASVS a
# requirement must be closed by a "pass or fail" decision, and an inapplicable one is
# closed by a written justification, not by silence. The manifest's hypotheses are our
# questions, and each must receive one of three verdicts.
HYPOTHESIS_HEADING = re.compile(r"^#{1,6}\s*.*(гипотез|hypothes)", re.IGNORECASE)
HYPOTHESIS_WORD = re.compile(r"гипотез|hypothes", re.I)
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
LIST_ITEM = re.compile(r"^\s{0,3}(?:[-*+]\s+|\d+[.)]\s+)\S")
LIST_MARK = re.compile(r"^(?:[-*+]|\d+[.)])\s+")
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


CODE_SPAN = re.compile(r"`+([^`]*)`+")

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
    for line, fenced in zip(lines, quoted_lines(lines, "quoted")):
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
                out.setdefault(token, []).append(verdict)
        if not block_id:
            continue
        # The free form is bound to the block whose report we are reading: "hypothesis 2"
        # in the H15 report is H15.2, and there is no point demanding the author rewrite it as an ID.
        for n in plain.findall(line):
            out.setdefault(f"{block_id}.{n}", []).append(verdict)
        # The summary table "| # | hypothesis | outcome |" — the way a hypotheses report is
        # written most often: the number stands in the first cell, the verdict in the last,
        # and the word "hypothesis" is not in the line at all. Without parsing the table the
        # gate would demand a finished report be rewritten for the sake of form, adding
        # nothing to its content.
        if is_row and (in_hypotheses or table_about_hypotheses):
            first = line.strip().strip("|").split("|")[0].strip()
            if first.isdigit():
                out.setdefault(f"{block_id}.{first}", []).append(verdict)
    return out


def verdicts_for(b: dict) -> dict[str, str]:
    """Verdicts on the block's hypotheses, where the verifier's word overrides the hunter's.

    The verifier's prompt explicitly demands overriding someone else's verdict with its
    own, with an explanation. While the reports were glued into one text, the hunter came
    first, and `setdefault` kept its verdict forever: the verifier could write "not
    checked", and the tool kept showing "checked". We read by role and overlay in order
    of seniority.
    """
    out: dict[str, str] = {}
    for role in ("hunter", "fix", "verify"):  # verify last — it is the one that overrides
        p = REVIEW / "reports" / f"{b['id']}-{b['slug']}.{role}.md"
        if p.exists():
            out.update(verdicts_in(p.read_text(encoding="utf-8"), b["id"]))
    return out


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


# --------------------------------------------------------------------------- check


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


class Refusals:
    """Everything `check` has to say, and the one way for a gate to say it.

    A gate is a mechanism that must not be removable in silence: CONTRIBUTING promises that
    each one comes with a test, and the suite holds a table pairing every gate with the test
    that reddens when it is disabled. For that table to be complete, the gates have to be
    countable — and while a gate was "a line that appends to a list called `problems`", they
    were not: a gate written in a helper whose parameter is called something else, or
    accumulated with `extend`, or assigned, gave no name to pair, no test, and could be
    deleted later with the whole suite green. Three rounds of review found that same shape
    three times, in a new spelling each time.

    So a refusal is a pair — the gate's KEY, which the call site writes itself, and the text
    a human reads. The key is never printed: the user reads the message, and the key is what
    the gate is called by the suite's table and by the mutation run that proves the table.
    There is one container and two verbs, `refuse` (the state is wrong: exit 1) and `warn`
    (worth a look, exit unchanged), so adding a gate anywhere in the tool means naming it.
    """

    def __init__(self) -> None:
        self.said: list[tuple[bool, str, str]] = []      # (fatal, key, message)

    def refuse(self, key: str, message: str) -> None:
        """The state is wrong: `check` prints the message and exits 1."""
        self.said.append((True, key, message))

    def warn(self, key: str, message: str) -> None:
        """Worth a human's eye, but not a red state: printed, exit code unchanged."""
        self.said.append((False, key, message))

    @property
    def problems(self) -> list[str]:
        return [m for fatal, _, m in self.said if fatal]

    @property
    def warnings(self) -> list[str]:
        return [m for fatal, _, m in self.said if not fatal]

    def report(self) -> int:
        """Print what the gates said and give `check` its exit code.

        The code is computed here and nowhere else: a gate that printed its own refusal and
        returned by itself would be outside every table that counts them.
        """
        if self.warnings:
            print("WARNINGS (do not fail the check):\n")
            for w in self.warnings:
                print(f"  · {w}")
            print()
        if self.problems:
            print("CHECK FAILED:\n")
            for p in self.problems:
                print(f"  · {p}")
            return 1
        print("review state is consistent")
        return 0


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
        fid = f.get("id", "<no id>")
        if fid in seen_ids:
            gates.refuse("finding/duplicate-id", f"finding {fid}: duplicate id")
        seen_ids.add(fid)
        for field in ("id", "block", "severity", "confidence", "status", "file", "claim", "scenario"):
            if not f.get(field):
                gates.refuse("finding/empty-field", f"finding {fid}: field {field} is empty")
        if f.get("block") not in idx:
            gates.refuse("finding/unknown-block",
                         f"finding {fid}: refers to nonexistent block {f.get('block')}")
        if f.get("severity") not in SEVERITIES:
            gates.refuse("finding/severity-unknown",
                         f"finding {fid}: severity={f.get('severity')} is not in the vocabulary")
        if f.get("confidence") not in CONFIDENCE:
            gates.refuse("finding/confidence-unknown",
                         f"finding {fid}: confidence={f.get('confidence')} is not in the vocabulary")
        if f.get("status") not in FINDING_STATUS:
            gates.refuse("finding/status-unknown",
                         f"finding {fid}: status={f.get('status')} is not in the vocabulary")
        # Only open and deferred findings must point at a live file: a fixed finding is
        # history, and renaming the file after the fix does not make it false. The check
        # used to demand the file for any status and stayed red on history forever.
        if (f.get("status") in ("open", "deferred") and f.get("file")
                and f["file"] not in tracked and not f["file"].startswith("(")):
            gates.refuse("finding/file-missing",
                         f"finding {fid}: file {f['file']} is not in the repository")
        # A deferred finding does not count as open and therefore survives the whole
        # review unnoticed. The reason is what turns it from silence into a decision: the
        # summary publishes deferred findings as accepted risks, by that reason and no
        # other text. The message used to demand that every deferral be resolved before
        # the end, which is not what the tool holds and not what the summary does with it.
        if f.get("status") == "deferred" and not (f.get("defer_reason") or "").strip():
            gates.refuse(
                "finding/deferred-without-reason",
                f"finding {fid}: deferred without a reason — `{CLI} set-finding {fid} deferred "
                f"--reason '...'`; a deferral is an accepted risk, and the summary publishes it by that reason"
            )
        if f.get("status") == "fixed" and f.get("fix_commit") and ":" in str(f["fix_commit"]):
            # A fix in a NEIGHBOURING repository: `<repository>:<commit>`. It is not here and
            # cannot be, there is nothing to check — but the mark must be explicit. Without
            # it such a commit looks like our own, and the check honestly reports that it
            # does not exist; that is what happened with the finding about the other core.
            repo, _, sha = str(f["fix_commit"]).partition(":")
            if not repo or not sha:
                gates.refuse(
                    "finding/external-fix-malformed",
                    f"finding {fid}: an external fix is written as `<repository>:<commit>`"
                )
        elif f.get("status") == "fixed" and f.get("fix_commit"):
            # The fix commit must exist and touch the finding's file. Two marks in a
            # neighbouring project pointed at a commit that did not touch the named file at
            # all: the fix was made in another module, and the record stayed as it was. By
            # hand nobody checks that — and nobody did for half a year.
            # The paths are compared as git prints them for `ls-files`: raw and
            # NUL-separated. C-quoted, a Cyrillic name matched nothing, and no finding on
            # such a file could ever be marked fixed — the gate stayed red on a truthful
            # state for ever.
            touched = git("show", "--name-only", "--format=", f["fix_commit"])
            if touched.code != 0:
                gates.refuse("finding/commit-missing",
                             f"finding {fid}: commit {f['fix_commit']} is not in the repository")
            elif f.get("file") and not ({f["file"], *f.get("fixed_in", [])} & set(touched.fields)):
                gates.refuse(
                    "finding/commit-does-not-touch",
                    f"finding {fid}: commit {f['fix_commit']} does not touch {f['file']} — "
                    f"either the mark belongs to another finding, or the fix was made elsewhere: "
                    f"then name it (`{CLI} set-finding {fid} fixed --commit <sha> "
                    f"--fixed-in <path>`)"
                )
        if f.get("status") == "fixed" and not f.get("fix_commit"):
            gates.refuse("finding/fixed-without-commit",
                         f"finding {fid}: marked fixed, but no fix commit is given")
        if f.get("status") == "duplicate" and not f.get("dup_of"):
            gates.refuse("finding/duplicate-without-target",
                         f"finding {fid}: marked duplicate, but not of what exactly")
        elif f.get("status") == "duplicate" and (why := dup_problem(fid, f["dup_of"], rows)):
            gates.refuse("finding/duplicate-target-unusable", why)
        if f.get("confidence") == "rejected" and f.get("status") == "open":
            gates.refuse("finding/rejected-but-open",
                         f"finding {fid}: rejected by the verifier, but still open")
        if f.get("status") == "rejected" and f.get("confidence") != "rejected":
            gates.refuse(
                "finding/rejected-without-confidence",
                f"finding {fid}: status rejected but confidence {f.get('confidence')} — "
                f"the register claims 'rejected' and 'not rejected' at once"
            )
        # The code under the finding moved on — so either it was already fixed, or the
        # description is stale. Both demand action, not silence: a finding that is not
        # moved makes the next pass argue with nonexistent code.
        if (f.get("status") in ("open", "deferred") and not f.get("code_sha")
                and not f.get("region_sha") and file_sha(f.get("file", ""))):
            gates.refuse(
                "finding/no-code-fingerprint",
                f"finding {fid}: no code fingerprint — changes in {f.get('file')} under it are not "
                f"tracked; `{CLI} backfill`"
            )
        # The region form (#37): only the lines around the finding count, wherever they have
        # moved. The whole-file form is read as before, so a register written by an older
        # kit keeps its meaning until `restamp` moves each record over.
        if (f.get("status") in ("open", "deferred") and f.get("region_sha")
                and file_sha(f.get("file", ""))):
            lines = text_lines(f.get("file", ""))
            at = locate_region(f, lines) if lines is not None else None
            if at is None:
                gates.refuse(
                    "finding/region-changed",
                    f"finding {fid}: the code around {f.get('file')}:{f.get('line')} changed since "
                    f"it was stamped — re-check: either it is already closed (`{CLI} set-finding "
                    f"{fid} fixed --commit <sha>`), or the description is stale, or the defect is "
                    f"still there (`{CLI} restamp {fid}`, with `--line <N>` if it now sits elsewhere)"
                )
            elif at != f.get("line"):
                # A warning, not a refusal: the code under the finding is exactly what was
                # stamped, only lines above it came or went. `check` writes nothing, and the
                # register's line is what findings.md and the SARIF export point at — so the
                # shift is said, and one command records it.
                gates.warn(
                    "finding/line-moved",
                    f"finding {fid}: its code is unchanged but now sits at {f.get('file')}:{at}, "
                    f"not {f.get('line')} — `{CLI} restamp {fid}` records the new line"
                )
        elif f.get("status") in ("open", "deferred") and f.get("code_sha"):
            fresh = file_sha(f.get("file", ""))
            if fresh and fresh != f["code_sha"]:
                gates.refuse(
                    "finding/code-changed",
                    f"finding {fid}: code in {f.get('file')} changed since import — "
                    f"re-check: either it is already closed (`{CLI} set-finding {fid} fixed "
                    f"--commit <sha>`), or the description is stale, or the defect is still there "
                    f"(`{CLI} restamp {fid}`"
                    + (" — for a finding with a line it also moves the record to a fingerprint "
                       "of the lines around it, which edits elsewhere in the file leave alone)"
                       if f.get("line") is not None else ")")
                )
        # A line number the file does not have is the cheapest sign of fabrication — for a
        # finding that is still open. A fixed one cites the file as it was before the fix;
        # after it the file legitimately shrinks (the first migrated registry: three fixed
        # findings, all flagged).
        # The type is part of the vocabulary, like severity and status: a hand-written draft
        # says `"line": "2137"` as easily as `2137`, `import` copies the field through
        # untouched, findings.md renders both the same — and the gate below used to skip the
        # quoted one silently, which is worse than having no gate.
        if f.get("line") is not None and (isinstance(f["line"], bool)
                                          or not isinstance(f["line"], int)):
            gates.refuse(
                "finding/line-not-a-number",
                f"finding {fid}: line={f['line']!r} is not a number — write the line as a "
                f"number without quotes, or leave the field out"
            )
        elif f.get("status") in ("open", "deferred") and f.get("line"):
            n = file_lines(f.get("file", ""))
            if n is not None and f["line"] > n:
                gates.refuse(
                    "finding/line-past-end",
                    f"finding {fid}: line {f['line']} is cited, but {f.get('file')} has {n}"
                )
        # A rejected finding stays in the register for the sake of the reject reason —
        # without it the record is useless: the next review finds the same thing and
        # spends the time again. The review's completion condition demanded a reason for
        # every rejected finding from the start, but there was no check, and the field stayed empty.
        if f.get("status") == "rejected":
            # The reject reason is written either as a separate field or — as the role
            # template instructs — right in the finding's claim ("Rejected: …"). Demanding
            # only the field would fail the check on every finding written exactly by the instructions.
            claim = (f.get("claim") or "").strip()
            said = (f.get("reject_reason") or "").strip() or (
                claim if re.match(r"отвергнут|отклонен|отклонён|не подтверд|rejected|not confirmed", claim, re.I) else "")
            if not said:
                gates.refuse(
                    "finding/rejected-without-reason",
                    f"finding {fid}: rejected, but the reject reason is not recorded — "
                    f"`{CLI} set-finding {fid} rejected --reason '...'` or a claim that starts "
                    f"with 'Rejected: …' (in the review language)"
                )
        if len(f.get("claim") or "") > CLAIM_MAX:
            gates.refuse(
                "finding/claim-too-long",
                f"finding {fid}: claim is {len(f['claim'])} characters against a limit of {CLAIM_MAX} — "
                "it is a headline for the summary table, the evidence goes into the block report"
            )
        if len(f.get("scenario") or "") > SCENARIO_MAX:
            gates.refuse(
                "finding/scenario-too-long",
                f"finding {fid}: scenario is {len(f['scenario'])} characters against a limit of {SCENARIO_MAX}"
            )

    # 7. findings.md agrees with findings.jsonl. Compared by CONTENT, not by
    #    mtime: a clone or a `git checkout` stamps every file with the moment it
    #    was written, in whatever order, so mtimes say nothing about which of the
    #    two is the newer truth.
    if FINDINGS_MD.exists():
        if FINDINGS_MD.read_text(encoding="utf-8") != render_findings_md(rows):
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

    # 9. coverage
    _, _, unassigned = coverage_map()
    if unassigned:
        gates.refuse("coverage/unowned-files",
                     f"{len(unassigned)} files belong to no block — `{CLI} coverage`")

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
        for role in ("hunter", "fix", "verify"):
            rp = REVIEW / "reports" / f"{b['id']}-{b['slug']}.{role}.md"
            if rp.exists():
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
        if lines > limit:
            gates.refuse(
                "blocks/too-big-to-read",
                f"{bid}: {n} files, {lines} lines — cannot be read in one session "
                f"(ceiling {limit}). Split the block, or the report will lie about coverage"
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


# ---------------------------------------------------------------------------- log


def cmd_log(args) -> int:
    """Append a dated line to the journal. Decisions are what a re-run cannot recover."""
    journal(args.block, args.text)
    print("written to journal.md")
    return 0


INVARIANTS_SKELETON_EN = """# {project} invariants

This file is pasted into the prompt of EVERY agent, and it decides what the agent will
count as a defect. Generic words are useless here — write what the project has already
paid for.

## Context that changes how findings are judged

<Is there a production? Legacy data? Target scale? What may be broken and what must never
be, under any circumstances?>

## Rules that must not be broken

<One item per rule, each from your own history. "Limits count successes; the user does not
pay for our failures" beats "the code must be correct".>

## What is NOT a finding

<Style? Limit numbers that live in env? Known and accepted trade-offs? List them, or the
agent will bring nitpicks.>
"""

INVARIANTS_SKELETON = """# Инварианты {project}

Этот файл вклеивается в промпт КАЖДОМУ агенту, и от него зависит, что агент сочтёт
дефектом. Общие слова здесь бесполезны — пишите то, за что уже заплатили.

## Контекст, меняющий оценку находок

<Есть ли продакшен? Есть ли legacy-данные? Какой целевой масштаб? Что можно ломать, а что
нельзя ни при каких условиях?>

## Правила, которые нарушать нельзя

<По пункту на правило, каждое — из своей истории. «Лимиты считают успехи, за наши сбои
пользователь не платит» лучше, чем «код должен быть корректным».>

## Что НЕ является находкой

<Стилистика? Числа лимитов, живущие в env? Известные и осознанные компромиссы? Перечислите,
иначе агент принесёт придирки.>
"""


def cmd_setup(args) -> int:
    """Set up the review in a project: the definition skeleton, the invariants, the entry point.

    This used to be done by a separate installer that also copied the tool itself into the
    project. There is nowhere and no reason to copy the skill — it is installed the
    standard way, and what stays in the project is only what belongs to the project: its
    blocks, its rules, its state. Existing files are not touched: the command is run in a
    live project.
    """
    project = args.project or ROOT.name
    lang = args.lang
    if lang not in LANGS:
        die(f"unknown language {lang}; known: {', '.join(LANGS)}")
    done: list[str] = []
    skipped: list[str] = []

    def put(path: Path, text: str) -> None:
        rel = path.relative_to(ROOT).as_posix()
        if path.exists():
            skipped.append(rel)
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        done.append(rel)

    skel = {
        "review_id": f"{ROOT.name}-review",
        "kit_version": VERSION,
        "project": project,
        "lang": lang,
        **({"cli": args.cli} if args.cli else {}),
        "gates": [],
        "note": MSG[lang]["setup_note"],
        "exclusions": [{"pattern": "docs/review/**", "reason": MSG[lang]["excl_apparatus"]}],
        "blocks": [],
    }
    # A skill installed into the project (so that CI runs the same version) is apparatus
    # too: without the exclusion its two dozen files turn the coverage map red from the
    # first commit. The path is the actual one: `.claude/skills/`, `.agents/skills/`,
    # wherever it was installed.
    try:
        own = SKILL_DIR.relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        own = None
    if own:
        skel["exclusions"].append({"pattern": f"{own}/**", "reason": MSG[lang]["excl_skill"]})
    put(BLOCKS_FILE, json.dumps(skel, ensure_ascii=False, indent=2) + "\n")
    put(INVARIANTS_FILE, (INVARIANTS_SKELETON if lang == "ru" else INVARIANTS_SKELETON_EN).format(project=project))
    cli = args.cli or default_cli()
    entry = asset(ASSET_ENTRY, lang).read_text(encoding="utf-8")
    put(REVIEW / "README.md", fill(entry, project, cli))
    for d in ("blocks", "reports"):
        (REVIEW / d).mkdir(parents=True, exist_ok=True)

    for rel in done:
        print(f"  + {rel}")
    for rel in skipped:
        print(f"  · {rel} — already exists, left untouched")
    # Bytecode appears as soon as someone imports the tool as a module, and rides into a
    # commit if the skill lives in the project. In the first project that is exactly what
    # happened. We do not edit someone else's .gitignore — we say so.
    ignore = ROOT / ".gitignore"
    known = ignore.read_text(encoding="utf-8") if ignore.exists() else ""
    if not any(k in known for k in ("__pycache__", "*.pyc", "*.py[cod]")):
        print("\n⚠️ .gitignore has no __pycache__/ — add it, otherwise the tool's bytecode "
              "ends up in a commit")
    # The banner is not written anywhere by the tool — it goes into the project's own root
    # instructions file, which is not ours to edit. So it is printed ready to paste: its
    # whole point is to name the command a future session must run, and a sample that says
    # `make review-status` to a project without a Makefile sends every session to a
    # command that does not exist.
    banner = asset(ASSET_BANNER, lang).read_text(encoding="utf-8")
    banner = fill(banner.split("\n---\n", 1)[-1].strip(), project, cli)
    print(f"""
Next — by hand, and this is not a formality:

1. docs/review/invariants.md — the rules of YOUR project. The most important file: it is
   pasted to every agent and decides what the agent will count as a defect. Example: {asset(ASSET_INVARIANTS, lang)}
2. docs/review/blocks.json — `gates` (the project's gate commands) and the blocks: cross-cutting
   first, domain ones next, live-system ones last. Example: {asset(ASSET_BLOCKS, lang)}
3. The manifest of the first block — docs/review/blocks/<ID>-<slug>.md: 10–15 hypotheses about your
   project and the acceptance criterion. Example: {asset(ASSET_MANIFEST, lang)}
4. `{cli} init`, then `{cli} coverage` — and deal with the unowned files until there are
   none left. This is where everything forgotten surfaces.
5. `{cli} log <ID> "what was decided and why"` — from the first decision on: findings a
   re-run recovers, decisions it does not. What a useful line looks like: {asset(ASSET_JOURNAL, lang)}
6. The banner in the root instructions file ({asset(ASSET_BANNER, lang)}), otherwise a new session
   will not know a review is in progress and will start its own parallel one. Ready to paste:

{banner}""")
    return 0


def main() -> int:
    # `review.py prompt H1 --role hunter | head` is the obvious way to look
    # at a prompt before handing it to an agent; without this, python answers a
    # closed pipe with a traceback and exit code 120, which reads like the tool
    # is broken.
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)

    p = argparse.ArgumentParser(prog="review", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="create/extend state.json from blocks.json").add_argument(
        "--force", action="store_true", help="rewrite the state from scratch"
    )
    sub.add_parser("version", help="version of the kit installed in this project")
    c = sub.add_parser("setup", help="set up the review in the project: blocks.json skeleton, invariants, entry point")
    c.add_argument("--project", default="", help="project name for the prompts and scaffolds")
    c.add_argument("--lang", default="en", choices=list(LANGS),
                   help="review language: role templates, scaffolds and docs/review artifacts (en by default)")
    c.add_argument("--cli", default="",
                   help="how the project calls the tool, if not directly (for example 'npm run review --'); "
                        "written to blocks.json and used in every hint")
    sub.add_parser("status", help="where we are now")
    sub.add_parser("next", help="id of the next unclosed block")

    c = sub.add_parser("coverage", help="file→block map; fails if there are unowned files")
    c.add_argument("--limit", type=int, default=40)
    c.add_argument("--no-write", action="store_true",
                   help="only check, do not rewrite coverage.tsv — gate mode in CI")

    c = sub.add_parser("prompt", help="assemble the prompt for an agent")
    c.add_argument("block")
    c.add_argument("--role", choices=ROLES, default="hunter")
    c.add_argument("--diff", help="fixreview: diff range of the fixes (main...HEAD)")
    c.add_argument("--round", type=int, default=1, help="round of fixing/fix review (from 1)")
    c.add_argument("--scope", help="fixreview: the half of the fixes this reviewer reports on "
                                   "(backend, ui…) — it names the half, it does not shrink the "
                                   "diff; narrow --diff for that")

    c = sub.add_parser("set-status", help="move a block to a new status")
    c.add_argument("block")
    c.add_argument("status")
    c.add_argument("--report", action="append")
    c.add_argument("--note")

    c = sub.add_parser("import", help="take a block's findings into the shared register")
    c.add_argument("block")
    c.add_argument("--force", action="store_true", help="overwrite the block's findings already taken into work")
    c.add_argument("--append", action="store_true",
                   help="top-up import: append new findings without touching the recorded and fixed ones")
    c.add_argument("--round", type=int,
                   help="with --append: the fix review round that found the new findings (recorded as found_in)")
    c.add_argument("--diff", help="with --round: the diff range that fix review read (pinned to commit ids)")

    c = sub.add_parser("decide", help="record a human's decision on a block — the answer to the loop signal")
    c.add_argument("block")
    c.add_argument("text")
    c.add_argument("--round", type=int,
                   help="the fix review round the decision follows (default: the latest one in the register)")

    c = sub.add_parser("set-finding", help="move a finding (or several): fixed / rejected / duplicate / deferred")
    c.add_argument("finding", nargs="+")
    c.add_argument("status")
    c.add_argument("--commit", help="fix commit; required for fixed")
    c.add_argument("--reason", help="reject reason; required for rejected")
    c.add_argument("--dup-of", dest="dup_of", help="id of the finding this one duplicates")
    c.add_argument("--rule", help="what closes the class: path to the guard, test or linter rule")
    c.add_argument("--clear-rule", dest="clear_rule", action="store_true",
                   help="remove the recorded guard (it does not go red on this finding's defect)")
    c.add_argument("--fixed-in", dest="fixed_in", action="append",
                   help="where the fix was made, if not in the finding's file (repeatable)")

    c = sub.add_parser("hypotheses", help="the block's hypotheses and their verdicts")
    c.add_argument("block")

    c = sub.add_parser("restamp", help="confirm the edits were reviewed: of a block or of the code under a finding")
    c.add_argument("block", help="block (H1) or finding (H1-003)")
    c.add_argument("--line", type=int,
                   help="a finding only: the line the defect sits on now, when the code moved away from the cited one")

    sub.add_parser("backfill", help="stamp fingerprints on old blocks and findings (with a journal entry)")

    c = sub.add_parser("inventory", help="repository tree: files, lines, binaries, whose — for cutting blocks")
    c.add_argument("--depth", type=int, default=2)
    c.add_argument("--under", help="only under this directory")
    c.add_argument("--unassigned", action="store_true", help="only unowned files")
    sub.add_parser("sizes", help="size of every block against the readability ceiling")
    c = sub.add_parser("coupling", help="files that change together but sit in different blocks — the seams")
    c.add_argument("--since", help="only commits since this date (git --since)")
    c.add_argument("--min-together", type=int, default=COUPLING_MIN_TOGETHER, help="joint commits a pair needs")
    c.add_argument("--min-share", type=float, default=COUPLING_MIN_SHARE, help="share of one file's commits the pair must cover")
    c.add_argument("--write", action="store_true", help="also write docs/review/coupling.tsv")
    c = sub.add_parser("order", help="blocks in the order worth walking them: risk first, change frequency second")
    c.add_argument("--since", help="only commits since this date (git --since)")
    sub.add_parser("refs", help="finding ids of the register named in the code outside docs/review/")
    c = sub.add_parser("summary", help="the one file that outlives docs/review/; --aged <file>: drift since its base commit")
    c.add_argument("--out", default=SUMMARY_DEFAULT, help=f"where to write (default {SUMMARY_DEFAULT}, outside docs/review/)")
    c.add_argument("--aged", metavar="FILE", help="read a summary and print how much each block changed since its base commit")

    c = sub.add_parser("sarif", help="open and deferred findings as SARIF 2.1.0 for GitHub code scanning")
    c.add_argument("--out", help="write to this file instead of stdout (for upload-sarif in CI)")

    c = sub.add_parser("roots", help="finding roots: how many instances and what closes the class")
    c.add_argument("block", nargs="?")

    sub.add_parser("findings", help="regenerate findings.md from findings.jsonl")
    sub.add_parser("check", help="check the state for consistency")

    c = sub.add_parser("log", help="append a line to the journal")
    c.add_argument("block")
    c.add_argument("text")

    args = p.parse_args()
    if IN_REPO is None and args.cmd != "version":
        die("not inside a git repository — run from the directory of the project under review: "
            "coverage is computed from `git ls-files`")
    return {
        "init": cmd_init, "version": cmd_version, "status": cmd_status, "next": cmd_next, "coverage": cmd_coverage,
        "prompt": cmd_prompt, "set-status": cmd_set_status, "findings": cmd_findings,
        "check": cmd_check, "log": cmd_log, "import": cmd_import, "decide": cmd_decide,
        "set-finding": cmd_set_finding, "hypotheses": cmd_hypotheses,
        "restamp": cmd_restamp, "roots": cmd_roots, "backfill": cmd_backfill,
        "inventory": cmd_inventory, "sizes": cmd_sizes, "coupling": cmd_coupling, "order": cmd_order, "refs": cmd_refs, "summary": cmd_summary, "sarif": cmd_sarif,
        "setup": cmd_setup,
    }[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
