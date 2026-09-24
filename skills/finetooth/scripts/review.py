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
import os
import re
import signal
import subprocess
import sys
from pathlib import Path

# The skill directory: the tool lives in `<skill>/scripts/`, the role templates in
# `<skill>/references/`, the scaffolds in `<skill>/assets/`.
SKILL_DIR = Path(__file__).resolve().parent.parent


def repo_root() -> Path | None:
    """Root of the repository UNDER REVIEW — taken from the working directory, not from the file.

    While the tool was copied into the project, the root was asked from git relative to
    the tool's own location. The skill lives anywhere — in `~/.claude/skills/`, in
    `.agents/skills/` of someone else's clone — and a root "from the file" would point at
    the skill directory or even at `~/.claude`, if that is under git: the tool would
    silently write its state there. The repository under review is the one you work in —
    that is the one we ask.
    """
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        return Path(out) if out else None
    except (OSError, subprocess.CalledProcessError):
        return None


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
    way (`npm run review --`, `make review`) writes that in the `cli` field of `blocks.json`.
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

# A block moves forward only through these, in this order. `blocked` is the one
# side exit: a block that cannot proceed until another one lands.
STATUSES = ["todo", "running", "hunted", "verified", "triaged", "fixing", "closed", "blocked"]
SEVERITIES = ["critical", "high", "medium", "low"]
CONFIDENCE = ["confirmed", "plausible", "rejected"]
FINDING_STATUS = ["open", "fixed", "rejected", "duplicate", "deferred"]

# `claim` is the headline of a finding: it is what the summary table prints, one
# row per finding, and a row has to be readable at a glance. Evidence, line
# numbers and the reasoning that establishes the defect belong in the block
# report, which is prose and has room for them. Without a cap the field drifts
# into a paragraph — the verifier of the first block pasted its whole
# verification into it — and the table it feeds stops being a table.
CLAIM_MAX = 220
SCENARIO_MAX = 700
ROLES = ["hunter", "verify", "fix", "fixreview"]
# The block's proof kind. `read` — every file is read in full and named in the report;
# `measured` — reading proves nothing (180 thousand lines of tests, performance,
# scanners), the proof is the artifacts from the manifest. A block without `paths` is a
# live system.
PROOFS = ("read", "measured")
# Review languages. The tool's own messages are always English; what is translated into
# the project's language is what the agent reads in the prompt and what a human reads in
# the docs/review/ artifacts: rule 1, headings, the reading budget, findings.md, the
# journal, the setup scaffolds.
LANGS = ("en", "ru")
MSG = {
 "en": {
  "none": "(none)",
  "refs_cut": "\n\n({n} files. The list is collapsed to patterns — expand the part you need yourself: `git ls-files -- <pattern>`.)",
  "vol_head": "Files: {n}. Lines: {lines}. Order of magnitude: ~{k}k tokens just to read, before any reasoning or tool calls.",
  "vol_fits": "This fits what can be read in one session (ceiling {limit} lines).",
  "vol_over": "\n⚠️ **The block is larger than one session can read** — {lines} lines against a ceiling of {limit}. Reading everything carefully will not work, and the only honest way out is to read as much as you can and **name the rest by path** in the coverage-limits section. Do not pretend you read it.",
  "vol_border": "\nWhere the budget line runs (largest first, cumulative):",
  "vol_more": "  … and {n} more file(s)",
  "vol_legend": "\n▲ — beyond the line. Not a ban on opening them: it is what you must name as unread if you did not.",
  "vol_lines": "lines",
  "gates_missing": "(the \"gates\" field in blocks.json is empty — list the project's gate commands)",
  "proof_live": "**The block owns no files: it works against the running system.** What to bring up, what to run and which artifact to hand in is in the manifest below; without that artifact the block is not closed. Read code only as much as is needed to set up the experiment and explain its outcome.",
  "proof_measured_verify": "**The block is proven by artifacts, not by reading** (`proof: measured`). Do not re-read files after the hunter: rebuild every artifact from the manifest with the same command and compare line by line with what was handed in. A discrepancy is a finding; an artifact that cannot be rebuilt means the block is not closed.",
  "proof_measured": "**The block is proven by artifacts, not by reading** (`proof: measured`). The file list below outlines the area, not a reading assignment: which artifacts to hand in and how to obtain them is in the manifest, and without them the block is not closed. Read what the artifact needs and do not report reading that did not happen.",
  "proof_read_verify": "**Every file in the list below had to be read in full by someone.** If the hunter admitted skipping part of it, read that part yourself; if the hunter is silent about a file, that does not mean it was read.",
  "proof_read": "**Read EVERY file in the list below in full.** Not selectively, not \"the key ones\". The list is generated mechanically and is the subject of your work. If a file is too large, read it in parts — but read all of it.",
  "files_live": "Block files: none — the block works against the running system",
  "files_measured": "Block files ({n}) — the block's area; proof is the manifest's artifacts",
  "files_read": "Block files ({n}) — read all",
  "scope_line": " Your half of the diff: **{scope}** — read the rest for context, file findings for your half.",
  "no_open_findings": "(no open findings for this block — ask the lead session why the fixer was started)",
  "f_where": "**Location:**", "f_claim": "**What is wrong:**", "f_scenario": "**Failure scenario:**", "f_invariant": "**Violated invariant:**", "f_conf": "confidence",
  "md_title": "# Review findings", "md_gen": "> This file is GENERATED from `findings.jsonl` by `{cli} findings`.", "md_noedit": "> Do not edit by hand — edit the jsonl and regenerate.",
  "md_open": "Open: **{live}** of {total} records.", "md_sev": "## {sev} ({open} open / {total})", "md_cols": "| id | block | status | location | what is wrong |",
  "journal_head": "# Review journal\n\n",
  "backfill_note": "Fingerprints stamped retroactively at commit {head}: blocks {blocks}; findings {n}. Changes before this commit are not tracked.",
  "setup_note": "Static definition of the blocks. Progress lives in state.json, findings in findings.jsonl. Array order = execution order.",
  "excl_apparatus": "review apparatus, not its subject", "excl_skill": "the review skill — tooling, not the subject of review",
 },
 "ru": {
  "none": "(нет)",
  "refs_cut": "\n\n({n} файлов. Список сокращён до шаблонов — разверни нужную часть сам: `git ls-files -- <шаблон>`.)",
  "vol_head": "Файлов: {n}. Строк: {lines}. Порядок величины: ~{k}k токенов только на чтение, без рассуждений и вызовов инструментов.",
  "vol_fits": "Это укладывается в то, что читается за сеанс (порог {limit} строк).",
  "vol_over": "\n⚠️ **Блок больше, чем прочитывается за сеанс** — {lines} строк при пороге {limit}. Прочитать всё внимательно не выйдет, и честный выход один: прочитать столько, сколько получится, и **поимённо назвать остальное** в разделе об ограничениях охвата. Не делайте вид, что прочитали.",
  "vol_border": "\nГде проходит граница бюджета (по убыванию размера, накопительно):",
  "vol_more": "  … и ещё {n} файл(ов)",
  "vol_legend": "\n▲ — то, что за границей. Это не запрет их открывать: это то, что вы обязаны назвать непрочитанным, если не открыли.",
  "vol_lines": "строк",
  "gates_missing": "(в blocks.json не заполнено поле \"gates\" — впишите команды ворот проекта)",
  "proof_live": "**У блока нет файлов: он работает на запущенной системе.** Что поднять, что прогнать и какой артефакт сдать — в манифесте ниже; без артефакта блок не закрыт. Код читай ровно настолько, чтобы поставить опыт и объяснить исход.",
  "proof_measured_verify": "**Блок доказывается артефактами, а не чтением** (`proof: measured`). Не перечитывай файлы за охотником: пересобери каждый артефакт манифеста той же командой и сверь построчно с тем, что он сдал. Расхождение — находка; артефакт, который не пересобирается, — блок не закрыт.",
  "proof_measured": "**Блок доказывается артефактами, а не чтением** (`proof: measured`). Список файлов ниже очерчивает область, а не задание на прочтение: какие артефакты сдать и как их получить — в манифесте, без них блок не закрыт. Читай то, что нужно для артефакта, и не отчитывайся о чтении, которого не было.",
  "proof_read_verify": "**Каждый файл из списка ниже кто-то обязан был прочитать целиком.** Если охотник признался, что часть не прочитал, — прочитай её сам; если он молчит о файле, это не значит, что файл прочитан.",
  "proof_read": "**Прочитай КАЖДЫЙ файл из списка ниже целиком.** Не выборочно, не «по ключевым». Список сгенерирован механически и является предметом твоей работы. Если файл слишком велик — читай его частями, но прочитай весь.",
  "files_live": "Файлы блока: нет — блок работает на запущенной системе",
  "files_measured": "Файлы блока ({n} шт.) — область блока; доказательство — артефакты манифеста",
  "files_read": "Файлы блока ({n} шт.) — прочитать все",
  "scope_line": " Твоя половина диффа: **{scope}** — остальное читай для контекста, находки оформляй по своей половине.",
  "no_open_findings": "(открытых находок по блоку нет — уточни у ведущей сессии, зачем запущен фиксер)",
  "f_where": "**Место:**", "f_claim": "**Что не так:**", "f_scenario": "**Сценарий отказа:**", "f_invariant": "**Нарушенный инвариант:**", "f_conf": "уверенность",
  "md_title": "# Находки ревью", "md_gen": "> Файл СГЕНЕРИРОВАН из `findings.jsonl` командой `{cli} findings`.", "md_noedit": "> Не редактируй его руками — правь jsonl и перегенерируй.",
  "md_open": "Открыто: **{live}** из {total} записей.", "md_sev": "## {sev} ({open} открыто / {total})", "md_cols": "| id | блок | статус | место | что не так |",
  "journal_head": "# Дневник ревью\n\n",
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


def die(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(2)


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


def listed(pathspecs: list[str] | None) -> set[str]:
    """Tracked files — real files, without submodules and symlinks."""
    cmd = ["git", "-C", str(ROOT), "ls-files", "--stage", "-z"]
    if pathspecs is not None:
        cmd += ["--"] + pathspecs
    out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    files = set()
    for row in out.split("\0"):
        if not row:
            continue
        head, _, path = row.partition("\t")
        if head.split(" ", 1)[0] not in NOT_A_FILE_MODES:
            files.add(path)
    return files


def untracked_files(specs: list[str]) -> list[str]:
    """Files on disk that match the specs but are not in the index (`npx skills add`,
    a fresh generator, an unpacked archive): `check` would otherwise call them absent."""
    cmd = ["git", "-C", str(ROOT), "ls-files", "--others", "--exclude-standard", "-z", "--", *specs]
    out = subprocess.run(cmd, capture_output=True, text=True, check=False).stdout
    return [f for f in out.split("\0") if f]


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


def file_sha(rel: str) -> str | None:
    """Fingerprint of a file's contents — the same one git computes, without extra dependencies."""
    if not rel or rel.startswith("("):
        return None
    p = ROOT / rel
    if p.is_symlink():
        # `hash-object` would follow the link and hash the target: re-pointing to a file
        # with the same contents would go unnoticed. What is hashed is what the symlink is.
        return "link:" + hashlib.sha1(os.readlink(p).encode("utf-8")).hexdigest()
    if not p.is_file():
        return None
    out = subprocess.run(["git", "-C", str(ROOT), "hash-object", "--", rel],
                         capture_output=True, text=True)
    return out.stdout.strip() or None


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
    out = subprocess.run(["git", "-C", str(ROOT), "show", f":{rel}"],
                         capture_output=True, check=False)
    # A binary file is not lines: a "two-thousand-line" picture inflated the block and
    # the readability ceiling. The sign is a NUL byte near the start, as git itself does it.
    if out.returncode == 0 and b"\0" in out.stdout[:8192]:
        return None
    if out.returncode != 0:
        p = ROOT / rel
        if not p.is_file():
            return None
        try:
            with open(p, encoding="utf-8", errors="ignore") as fh:
                return sum(1 for _ in fh)
        except OSError:
            return None
    return out.stdout.count(b"\n") + (0 if out.stdout.endswith(b"\n") or not out.stdout else 1)


def blocks() -> dict:
    return load_json(BLOCKS_FILE)


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
    st["updated_at"] = now()
    save_json(STATE_FILE, st)
    FINDINGS_FILE.touch()
    print(f"state initialised: {len(st['blocks'])} blocks")
    return 0


def cmd_version(args) -> int:
    print(VERSION)
    return 0


# ------------------------------------------------------------------------- status


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


def stale_tree() -> tuple[float, str] | None:
    """How much fresher the server's tip is than ours — in days, if the gap is large.

    The network is not touched (`fetch` is the human's business); we look at what git
    already knows.
    """
    ref = subprocess.run(
        ["git", "-C", str(ROOT), "symbolic-ref", "--short", "refs/remotes/origin/HEAD"],
        capture_output=True, text=True,
    ).stdout.strip()
    if not ref:
        return None

    def stamp(rev: str) -> int | None:
        out = subprocess.run(["git", "-C", str(ROOT), "log", "-1", "--format=%ct", rev],
                             capture_output=True, text=True)
        return int(out.stdout.strip()) if out.returncode == 0 and out.stdout.strip() else None

    # Counted from the POINT OF DIVERGENCE, not from our own tip: a fresh commit in a
    # long-ago branch makes its tip newer than the remote one and hides the fact that the
    # branch contains not a single fix made by others in all that time.
    base = subprocess.run(["git", "-C", str(ROOT), "merge-base", "HEAD", ref],
                          capture_output=True, text=True)
    anchor = base.stdout.strip() if base.returncode == 0 and base.stdout.strip() else "HEAD"
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
        print(f"{b['id']:<6} {proof:<9} {n:>6} {lines:>8}  {mark}")
    if over:
        print(f"\nblocks above the ceiling: {over}")
        return 1
    print("\nall readable blocks are within the ceiling")
    return 0


# ------------------------------------------------------------------------- prompt


def demote(md: str) -> str:
    """Push an embedded document one heading level down.

    The manifest and the invariants are pasted inside a prompt that has headings
    of its own; left alone, their `#` titles compete with it and the agent reads
    a document with two top levels. Fenced code is left untouched so a `#`
    comment inside an example stays a comment.
    """
    out, fenced = [], False
    for line in md.split("\n"):
        if line.lstrip().startswith("```"):
            fenced = not fenced
        elif not fenced and line.startswith("#"):
            line = "#" + line
        out.append(line)
    return "\n".join(out)


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


def volume_note(files: list[str]) -> str:
    """How much code the block asks to read — and what of it will certainly not be read.

    The budget must stand in the assignment itself, not in the lead session's head.
    Neighbours in the niche do it two ways, and both are needed: repomix fails the build
    with a non-zero code when the pack outgrew the budget, and ai-digest leaves a file that
    did not fit in the output as a stub — path visible, contents absent. Staying silent is
    the worst: then the agent reports coverage that did not happen, and nobody can say
    where the line ran.
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

    out.append(T("vol_over", lines=total, limit=limit))
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
    stat = subprocess.run(["git", "-C", str(ROOT), "diff", "--stat", rng],
                          capture_output=True, text=True)
    full = subprocess.run(["git", "-C", str(ROOT), "diff", rng], capture_output=True, text=True)
    if full.returncode != 0:
        die(f"git diff {rng}: {full.stderr.strip()}")
    if not full.stdout.strip():
        die(f"diff {rng} is empty — the fix reviewer has nothing to read")
    # A fence of four backticks: triple ones occur inside a diff.
    return f"{stat.stdout}\n````diff\n{full.stdout}\n````"


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
        "{{VOLUME}}": volume_note(files),
        "{{REF_FILES}}": render_refs(b.get("ref_paths", []), refs),
        "{{FINDINGS}}": render_findings_for(b["id"]),
        # The project name and its gates are substitutions, not text in the template. A
        # template copied without proofreading greeted the agent on behalf of ANOTHER
        # project, and it was not noticed at once: the assignment looked meaningful as a whole.
        "{{PROJECT}}": defn.get("project", ROOT.name),
        "{{GATES}}": "\n".join(f"- `{g}`" for g in defn.get("gates", []))
        or T("gates_missing"),
    }
    for k, v in subs.items():
        body = body.replace(k, v)
    # An unfilled substitution would reach the agent as the text "{{SOMETHING}}" — and it
    # would read it as an assignment. Checked BEFORE the diff is pasted: curly braces are
    # legal in someone else's code.
    left = sorted(set(PLACEHOLDER.findall(body)) - {"{{DIFF}}"})
    if left:
        die(f"template {template.name} has substitutions left without a value: {', '.join(left)}")
    if args.role == "fixreview":
        body = body.replace("{{DIFF}}", diff_text(args.diff))
    print(body)
    return 0


def block_findings_path(b: dict) -> Path:
    return REVIEW / "reports" / f"{b['id']}-findings.jsonl"


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

    incoming = []
    for n, line in enumerate(src.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            incoming.append(json.loads(line))
        except json.JSONDecodeError as exc:
            die(f"{src.name} line {n}: not JSON — {exc}")

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
            if f.get("id") in known:
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
            f["imported_at"] = now()
            f["code_sha"] = file_sha(f.get("file", ""))
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
    locked = [f for f in mine if f.get("status") not in ("open", "rejected")]
    if locked and not args.force:
        ids = ", ".join(f.get("id", "?") for f in locked)
        die(
            f"block {args.block} already has findings in progress ({ids}) — "
            "a repeated import would wipe their state; use --force if this is deliberate"
        )

    kept = [f for f in existing if f.get("block") != args.block]
    before = {f["id"]: f for f in mine if f.get("id")}
    width = 3
    for i, f in enumerate(incoming, 1):
        f.setdefault("block", args.block)
        f["id"] = f.get("id") or f"{args.block}-{i:0{width}d}"
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
        prev = before.get(f["id"])
        if prev and prev.get("code_sha") and prev.get("file") == f.get("file"):
            f["code_sha"] = prev["code_sha"]
        else:
            f["code_sha"] = file_sha(f.get("file", ""))
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
    if args.status not in FINDING_STATUS:
        die(f"unknown status {args.status}; known: {', '.join(FINDING_STATUS)}")
    if args.status == "fixed" and not args.commit:
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
        if not git_files([path]):
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
        # The guard is recorded on ALL findings of this root: the class is closed as a whole or not at all.
        for row in rows:
            if (row.get("root") or "") == (f.get("root") or "") and f.get("root"):
                row["rule"] = args.rule
        f["rule"] = args.rule
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
    """
    defn = blocks()
    excluded = git_files([e["pattern"] for e in defn.get("exclusions", [])])
    files = git_files(pathspecs) - excluded
    total = 0
    for f in files:
        try:
            with open(ROOT / f, encoding="utf-8", errors="ignore") as fh:
                total += sum(1 for _ in fh)
        except OSError:
            pass
    return len(files), total


def cmd_restamp(args) -> int:
    """Confirm that the changes in the block's files were reviewed, and re-take the fingerprint.

    Exactly like `doorstop review`: not "switch the check off", but say on record that the
    new text was seen. That is why the command demands the block by name and prints what
    exactly it stamps.
    """
    defn, st = blocks(), state()
    idx = block_index(defn)
    if args.block not in idx:
        return restamp_finding(args.block)
    s = st["blocks"].get(args.block, {})
    if s.get("status") not in POST_VERIFY:
        die(f"{args.block} is in status {s.get('status', 'todo')} — nothing to stamp")
    stamp(idx[args.block], s)
    s["restamped_at"] = now()
    st["updated_at"] = now()
    save_json(STATE_FILE, st)
    print(f"{args.block}: fingerprint re-taken — changes in the block's files count as reviewed")
    return 0


def restamp_finding(fid: str) -> int:
    """Confirm that an open finding is still alive on a changed file.

    The file under a finding changes not only by its fix: a neighbouring finding gets fixed
    in it, a line nearby gets edited. Without this command there were two ways out, both
    false — close a live defect or edit the register by hand. The stamp is set by name, as
    for a block: "re-checked, the defect is there" is said on record rather than switching
    the check off.
    """
    rows = findings()
    hit = [f for f in rows if f.get("id") == fid]
    if not hit:
        die(f"neither a block nor a finding {fid}")
    f = hit[0]
    if f.get("status") not in ("open", "deferred"):
        die(f"finding {fid} is in status {f.get('status')} — only open and deferred ones are stamped")
    sha = file_sha(f.get("file", ""))
    if not sha:
        die(f"file {f.get('file')} does not exist — a finding is moved (`{CLI} set-finding`), not stamped")
    f["code_sha"] = sha
    f["restamped_at"] = now()
    with FINDINGS_FILE.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    FINDINGS_MD.write_text(render_findings_md(rows), encoding="utf-8")
    print(f"{fid}: code fingerprint re-taken — the defect is confirmed on the current version of {f.get('file')}")
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


def cmd_roots(args) -> int:
    """Roots: how many instances each has and what closes the class."""
    rows = findings()
    groups = roots_of(rows, args.block)
    if not groups:
        print("no roots recorded — the `root` field of the findings is not filled in")
        return 0
    for root, items in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        rule = next((f.get("rule") for f in items if f.get("rule")), None)
        mark = f"guard: {rule}" if rule else (
            "NO GUARD" if len(items) >= ROOT_RULE_AT else "no guard, but few repeats")
        print(f"  {len(items):>2} × {root}  — {mark}")
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
    if not git_files([path]):
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
    head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"],
                          capture_output=True, text=True).stdout.strip() or "?"
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
        if f.get("status") in ("open", "deferred") and not f.get("code_sha"):
            sha = file_sha(f.get("file", ""))
            if sha:
                f["code_sha"] = sha
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
COVERAGE_VERDICT = re.compile(r"охват|полн(ый|ое|ая)\b|неполн|coverage|complete|incomplete", re.IGNORECASE)
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
    """
    body = [ln for ln in rep.read_text(encoding="utf-8").splitlines()
            if ln.strip() and not ln.lstrip().startswith("#")]
    if not body:
        return (f"verifier report {rep.name} is empty — there is a file, there is no verification; "
                f"each finding needs a verdict, the block needs a coverage state")
    text = "\n".join(body)
    if has_findings and not FINDING_VERDICT.search(text):
        return (f"verifier report {rep.name} has no verdict on any finding — "
                f"confirmed / plausible / rejected / duplicate with reasoning")
    # Coverage is a separate question, not replaced by verdicts: what was found says
    # nothing about what remained unreviewed.
    if not COVERAGE_VERDICT.search(
            "\n".join(ln for ln in body if not COVERAGE_PLACEHOLDER.search(ln))):
        return (f"verifier report {rep.name} has no coverage verdict — is it complete and "
                f"what is left")
    return None


def line_verdict(line: str) -> str | None:
    """A line's verdict is the word that stands EARLIER in it, not the first by the vocabulary.

    "Checked by code, all nine … Not checked with a live request" is "checked" with a
    reservation. Searching in vocabulary order found "not checked" anywhere in the line and
    declared the hypothesis unchecked. The negation is not lost either: the negated form
    ("not checked") starts earlier than the bare word ("checked") nested inside it.
    """
    low = line.lower()
    hits = [(i, v) for w, v in VERDICT_WORDS if (i := verdict_word_at(low, w)) >= 0]
    return min(hits)[1] if hits else None


def verdict_word_at(low: str, word: str) -> int:
    """Position of a verdict word, or -1. `n/a` is a sign, not letters: found inside a path
    (`curation/adapter.ts`), it declared a checked hypothesis "not applicable"."""
    if word == "n/a":
        m = re.search(r"(?<![\w/])n/a(?![\w/])", low)
        return m.start() if m else -1
    return low.find(word)


def section_body(md: str, heading: re.Pattern) -> list[str] | None:
    """The lines of the section under the first matching heading (subheadings are content too).

    None — there is no such section at all; an empty list — the heading is there, nothing under it.
    """
    body: list[str] | None = None
    depth = 0
    fenced = False
    for line in md.split("\n"):
        if line.lstrip().startswith("```"):
            fenced = not fenced
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
    fenced = False
    for i, ln in enumerate(lines):
        if ln.lstrip().startswith("```"):
            fenced = not fenced
        elif not fenced and LIST_ITEM.match(ln):
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
    for line in text.split("\n"):
        if line.startswith("#"):
            level = len(line) - len(line.lstrip("#"))
            if HYPOTHESIS_HEADING.match(line):
                in_hypotheses, hypotheses_depth = True, level
            elif in_hypotheses and level <= hypotheses_depth:
                in_hypotheses = False
        is_row = line.lstrip().startswith("|")
        if is_row and not prev_was_row:
            # The first row of a table says what the numbers in the first column are: a
            # header naming hypotheses, or no header at all (a bare "| 1 | … | verdict |"
            # summary). An acceptance table ("| # | place | constraint | ✓ |") is numbered
            # too, and its rows counted as verdicts on hypotheses 4 and 5.
            first = line.strip().strip("|").split("|")[0].strip()
            table_about_hypotheses = bool(HYPOTHESIS_WORD.search(line)) or first.isdigit()
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


def cmd_check(args) -> int:
    defn, st, rows = blocks(), state(), findings()
    idx = block_index(defn)
    problems: list[str] = []
    warnings: list[str] = []

    # 1. state and definition agree
    for bid in idx:
        if bid not in st["blocks"]:
            problems.append(f"{bid}: no record in state.json — run `{CLI} init`")
    for bid in st["blocks"]:
        if bid not in idx:
            problems.append(f"{bid}: present in state.json but missing from blocks.json")
        # `set-status` checked the vocabulary, but nobody checked what was written in by hand.
        status = st["blocks"][bid].get("status")
        if status not in STATUSES:
            problems.append(f"{bid}: status '{status}' is not in the vocabulary — written in past set-status")

    # Array order is execution order, and the phases must not decrease: a phase-3 block
    # written in between the first and the second, `next` hands out ahead of time, and
    # nobody notices.
    prev = None
    for b in defn["blocks"]:
        ph = b.get("phase")
        if prev is not None and ph is not None and ph < prev:
            problems.append(
                f"{b['id']}: phase {ph} comes after phase {prev} — the blocks array is ordered by "
                f"phase, because that is the execution order"
            )
        prev = ph if ph is not None else prev
    # A blocked block without a note is a block about which, a week later, nobody can say
    # what it is waiting for.
    for bid, s in st["blocks"].items():
        if s.get("status") == "blocked" and not (s.get("note") or "").strip():
            problems.append(f"{bid}: blocked without a note — waiting for what? `{CLI} set-status {bid} blocked --note '...'`")

    # The manifest is asked only of a block that GOT to work: the manifest is written
    # before its block, and demanding it of all at once fails the check always — then it
    # stops being a gate and starts being ignored.
    for bid, b in idx.items():
        if st["blocks"].get(bid, {}).get("status", "todo") == "todo":
            continue
        manifest = manifest_path(b)
        if not manifest.exists():
            problems.append(f"{bid}: no manifest {manifest.relative_to(ROOT)}")
        elif len(manifest.read_text(encoding="utf-8").strip()) < 200:
            # An empty file passed the "manifest exists" check.
            problems.append(f"{bid}: manifest {manifest.relative_to(ROOT)} is empty or nearly empty")

    # A block declared verified or closed must produce the VERIFIER's report.
    # Otherwise `set-status closed` closes a block with the hunter's report alone,
    # and unverified findings vanish from the remaining work.
    for b in defn["blocks"]:
        stt = st["blocks"].get(b["id"], {}).get("status", "todo")
        if stt in POST_VERIFY:
            rep = REVIEW / "reports" / f"{b['id']}-{b['slug']}.verify.md"
            if not rep.exists():
                problems.append(
                    f"{b['id']}: status {stt}, but there is no verifier report — "
                    f"the verification rests on the agent's own word"
                )
            elif why := verify_report_problem(rep, any(f.get("block") == b["id"] for f in rows)):
                problems.append(f"{b['id']}: {why}")

    # 3. declared reports exist
    for bid, s in st["blocks"].items():
        for r in s.get("reports", []):
            if not (ROOT / r).exists():
                problems.append(f"{bid}: state.json declares report {r}, which is not on disk")

    # 4. a block cannot be past `running` without a hunter report
    for b in defn["blocks"]:
        s = st["blocks"].get(b["id"], {})
        if s.get("status") in ("hunted", "verified", "triaged", "fixing", "closed"):
            hunter = REVIEW / "reports" / f"{b['id']}-{b['slug']}.hunter.md"
            if not hunter.exists():
                problems.append(
                    f"{b['id']}: status {s['status']}, but there is no hunter report — the status is not backed by work"
                )

    # 5. a session that died mid-block
    for bid, s in st["blocks"].items():
        if s.get("status") == "running" and not s.get("started"):
            problems.append(f"{bid}: stuck in running without a timestamp — when it started is unknown")
        if s.get("status") == "running" and s.get("started"):
            try:
                started = dt.datetime.strptime(s["started"], "%Y-%m-%dT%H:%M:%SZ").replace(
                    tzinfo=dt.timezone.utc
                )
            except ValueError:
                problems.append(f"{bid}: timestamp '{s['started']}' cannot be parsed")
                continue
            hours = (dt.datetime.now(dt.timezone.utc) - started).total_seconds() / 3600
            if hours > STALE_RUNNING_HOURS:
                problems.append(
                    f"{bid}: stuck in running for {hours:.0f} h — the session probably died; restart the block"
                )

    # 6. findings are well-formed and point at real code
    tracked = all_files()
    seen_ids: set[str] = set()
    for f in rows:
        fid = f.get("id", "<no id>")
        if fid in seen_ids:
            problems.append(f"finding {fid}: duplicate id")
        seen_ids.add(fid)
        for field in ("id", "block", "severity", "confidence", "status", "file", "claim", "scenario"):
            if not f.get(field):
                problems.append(f"finding {fid}: field {field} is empty")
        if f.get("block") not in idx:
            problems.append(f"finding {fid}: refers to nonexistent block {f.get('block')}")
        if f.get("severity") not in SEVERITIES:
            problems.append(f"finding {fid}: severity={f.get('severity')} is not in the vocabulary")
        if f.get("confidence") not in CONFIDENCE:
            problems.append(f"finding {fid}: confidence={f.get('confidence')} is not in the vocabulary")
        if f.get("status") not in FINDING_STATUS:
            problems.append(f"finding {fid}: status={f.get('status')} is not in the vocabulary")
        # Only open and deferred findings must point at a live file: a fixed finding is
        # history, and renaming the file after the fix does not make it false. The check
        # used to demand the file for any status and stayed red on history forever.
        if (f.get("status") in ("open", "deferred") and f.get("file")
                and f["file"] not in tracked and not f["file"].startswith("(")):
            problems.append(f"finding {fid}: file {f['file']} is not in the repository")
        # A deferred finding does not count as open and therefore survives the whole
        # review unnoticed. The reason is the only thing that will make anyone come back to it.
        if f.get("status") == "deferred" and not (f.get("defer_reason") or "").strip():
            problems.append(
                f"finding {fid}: deferred without a reason — `{CLI} set-finding {fid} deferred "
                f"--reason '...'`; by the end of the review every deferred finding is fixed or rejected with a reason"
            )
        if f.get("status") == "fixed" and f.get("fix_commit") and ":" in str(f["fix_commit"]):
            # A fix in a NEIGHBOURING repository: `<repository>:<commit>`. It is not here and
            # cannot be, there is nothing to check — but the mark must be explicit. Without
            # it such a commit looks like our own, and the check honestly reports that it
            # does not exist; that is what happened with the finding about the other core.
            repo, _, sha = str(f["fix_commit"]).partition(":")
            if not repo or not sha:
                problems.append(
                    f"finding {fid}: an external fix is written as `<repository>:<commit>`"
                )
        elif f.get("status") == "fixed" and f.get("fix_commit"):
            # The fix commit must exist and touch the finding's file. Two marks in a
            # neighbouring project pointed at a commit that did not touch the named file at
            # all: the fix was made in another module, and the record stayed as it was. By
            # hand nobody checks that — and nobody did for half a year.
            touched = subprocess.run(
                ["git", "-C", str(ROOT), "show", "--name-only", "--format=", f["fix_commit"]],
                capture_output=True, text=True,
            )
            if touched.returncode != 0:
                problems.append(f"finding {fid}: commit {f['fix_commit']} is not in the repository")
            elif f.get("file") and not ({f["file"], *f.get("fixed_in", [])}
                                        & set(touched.stdout.splitlines())):
                problems.append(
                    f"finding {fid}: commit {f['fix_commit']} does not touch {f['file']} — "
                    f"either the mark belongs to another finding, or the fix was made elsewhere: "
                    f"then name it (`{CLI} set-finding {fid} fixed --commit <sha> "
                    f"--fixed-in <path>`)"
                )
        if f.get("status") == "fixed" and not f.get("fix_commit"):
            problems.append(f"finding {fid}: marked fixed, but no fix commit is given")
        if f.get("status") == "duplicate" and not f.get("dup_of"):
            problems.append(f"finding {fid}: marked duplicate, but not of what exactly")
        elif f.get("status") == "duplicate" and (why := dup_problem(fid, f["dup_of"], rows)):
            problems.append(why)
        if f.get("confidence") == "rejected" and f.get("status") == "open":
            problems.append(f"finding {fid}: rejected by the verifier, but still open")
        if f.get("status") == "rejected" and f.get("confidence") != "rejected":
            problems.append(
                f"finding {fid}: status rejected but confidence {f.get('confidence')} — "
                f"the register claims 'rejected' and 'not rejected' at once"
            )
        # The code under the finding moved on — so either it was already fixed, or the
        # description is stale. Both demand action, not silence: a finding that is not
        # moved makes the next pass argue with nonexistent code.
        if (f.get("status") in ("open", "deferred") and not f.get("code_sha")
                and file_sha(f.get("file", ""))):
            problems.append(
                f"finding {fid}: no code fingerprint — changes in {f.get('file')} under it are not "
                f"tracked; `{CLI} backfill`"
            )
        if f.get("status") in ("open", "deferred") and f.get("code_sha"):
            fresh = file_sha(f.get("file", ""))
            if fresh and fresh != f["code_sha"]:
                problems.append(
                    f"finding {fid}: code in {f.get('file')} changed since import — "
                    f"re-check: either it is already closed (`{CLI} set-finding {fid} fixed "
                    f"--commit <sha>`), or the description is stale, or the defect is still there "
                    f"(`{CLI} restamp {fid}`)"
                )
        # A line number the file does not have is the cheapest sign of fabrication.
        if f.get("line") and isinstance(f["line"], int):
            n = file_lines(f.get("file", ""))
            if n is not None and f["line"] > n:
                problems.append(
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
                problems.append(
                    f"finding {fid}: rejected, but the reject reason is not recorded — "
                    f"`{CLI} set-finding {fid} rejected --reason '...'` or a claim that starts "
                    f"with 'Rejected: …' (in the review language)"
                )
        if len(f.get("claim") or "") > CLAIM_MAX:
            problems.append(
                f"finding {fid}: claim is {len(f['claim'])} characters against a limit of {CLAIM_MAX} — "
                "it is a headline for the summary table, the evidence goes into the block report"
            )
        if len(f.get("scenario") or "") > SCENARIO_MAX:
            problems.append(
                f"finding {fid}: scenario is {len(f['scenario'])} characters against a limit of {SCENARIO_MAX}"
            )

    # 7. findings.md agrees with findings.jsonl. Compared by CONTENT, not by
    #    mtime: a clone or a `git checkout` stamps every file with the moment it
    #    was written, in whatever order, so mtimes say nothing about which of the
    #    two is the newer truth.
    if FINDINGS_MD.exists():
        if FINDINGS_MD.read_text(encoding="utf-8") != render_findings_md(rows):
            problems.append(f"findings.md diverged from findings.jsonl — run `{CLI} findings`")

    # 8. a pattern that matches nothing silently shrinks a block's scope: the
    #    manifest promises to read code that was never handed to the agent.
    for b in defn["blocks"]:
        for key in ("paths", "ref_paths"):
            for spec in b.get(key, []):
                if not git_files([spec]):
                    untracked = untracked_files([spec])
                    if untracked:
                        problems.append(
                            f"{b['id']}: {key} pattern `{spec}` matches only untracked files "
                            f"({len(untracked)}) — the tool sees the index, not the disk: "
                            f"`git add -- {spec}`"
                        )
                    else:
                        problems.append(
                            f"{b['id']}: {key} pattern `{spec}` matches no file — "
                            "the block silently shrank"
                        )

    # 9. coverage
    _, _, unassigned = coverage_map()
    if unassigned:
        problems.append(f"{len(unassigned)} files belong to no block — `{CLI} coverage`")

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
            problems.append(
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
            problems.append(
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
                    problems.append(
                        f"{b['id']}: {rp.name} gives hypothesis {h} different verdicts "
                        f"({' / '.join(vs)}) — the outcome would depend on line order; leave one"
                    )
        seen = verdicts_for(b)
        missing = [h for h in ids if h not in seen]
        if missing:
            problems.append(
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
            problems.append(
                f"{b['id']}: block in status {s.get('status')} without a fingerprint of what was reviewed — "
                f"edits to its files are not tracked; `{CLI} backfill` or `{CLI} restamp {b['id']}`"
            )
            continue
        if changed_since_review(b, s["reviewed_sha"]):
            problems.append(
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
                warnings.append(f"{b['id']}: no context fingerprint (ref_paths) — `{CLI} backfill`")
            elif s["refs_sha"] != refs_sha(b):
                warnings.append(
                    f"{b['id']}: context files (ref_paths) changed after verification — "
                    f"if the block's conclusions leaned on them, re-check; otherwise `{CLI} restamp {b['id']}`"
                )
        if not s.get("hypotheses_sha"):
            problems.append(
                f"{b['id']}: no hypotheses fingerprint — an edit of the manifest after verification is not "
                f"tracked; `{CLI} backfill`"
            )
        elif s["hypotheses_sha"] != hypotheses_sha(b):
            problems.append(
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
            missing = [f for f in owned if f not in text]
            if missing:
                problems.append(
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
                problems.append(
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
            body = section_body(hunter.read_text(encoding="utf-8"), LIMITS_HEADING)
            if body is None:
                problems.append(
                    f"{b['id']}: the hunter report has no 'Coverage limits' section — "
                    f"what was deliberately not read and why"
                )
            elif not [ln for ln in body if ln.strip() and not LIMITS_PLACEHOLDER.search(ln)]:
                # A heading without text is the same silence as no heading: neither what
                # was not reviewed is named, nor that there is nothing of the kind.
                problems.append(
                    f"{b['id']}: the 'Coverage limits' section of the hunter report is empty — "
                    f"name what was not read or say outright that there is nothing"
                )

    # A defect class that repeated three times is closed by a guard, not by three fixes:
    # otherwise the next pass finds a fourth instance. A rule survives a refactoring, a
    # list of fixed places does not.
    for root, items in roots_of(rows).items():
        if len(items) < ROOT_RULE_AT:
            continue
        rules = {(f.get("rule") or "").strip() for f in items} - {""}
        if rules:
            for r in sorted(rules):
                if why := rule_problem(r):
                    problems.append(f"root '{root}': {why}")
            continue
        ids = ", ".join(f.get("id", "?") for f in items[:4])
        problems.append(
            f"root '{root}': {len(items)} instances ({ids}) and no guard — "
            f"a class that repeated {ROOT_RULE_AT} times is closed by a rule, not by a list of "
            f"fixes; record which: `{CLI} set-finding <ID> <status> --rule <path-to-guard>`"
        )

    # A tree that fell behind the server shows the fixed as broken. The findings of such a
    # pass describe code that no longer exists, and "confirmed by execution" sounds just as
    # convincing as on a fresh tree.
    stale = stale_tree()
    if stale:
        days, ref = stale
        problems.append(
            f"the tree is behind {ref} by {days:.0f} days — the findings of such a pass may "
            f"describe what is already fixed; `git fetch` and compare with {ref} before "
            f"filing them"
        )

    # A block that cannot be read in one session is a promise, not a block.
    for bid, b in idx.items():
        if not b.get("paths"):
            continue
        if b.get("proof", "read") not in PROOFS:
            problems.append(f"{bid}: proof '{b.get('proof')}' is not in the vocabulary: {', '.join(PROOFS)}")
            continue
        # The ceiling is a promise to read in full; a measured block makes no such promise.
        if b.get("proof", "read") == "measured":
            continue
        n, lines = block_lines(b["paths"])
        limit = readable_lines()
        if lines > limit:
            problems.append(
                f"{bid}: {n} files, {lines} lines — cannot be read in one session "
                f"(ceiling {limit}). Split the block, or the report will lie about coverage"
            )

    if warnings:
        print("WARNINGS (do not fail the check):\n")
        for w in warnings:
            print(f"  · {w}")
        print()
    if problems:
        print("CHECK FAILED:\n")
        for p in problems:
            print(f"  · {p}")
        return 1
    print("review state is consistent")
    return 0


# ---------------------------------------------------------------------------- log


def cmd_log(args) -> int:
    """Append a dated line to the journal. Decisions are what a re-run cannot recover."""
    if not JOURNAL_FILE.exists():
        JOURNAL_FILE.write_text(T("journal_head"), encoding="utf-8")
    entry = f"- **{now()}** · `{args.block}` — {args.text}\n"
    with JOURNAL_FILE.open("a", encoding="utf-8") as fh:
        fh.write(entry)
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
    entry_name = "entry-point.md" if lang == "en" else f"entry-point.{lang}.md"
    entry = (SKILL_DIR / "assets" / entry_name).read_text(encoding="utf-8")
    put(REVIEW / "README.md", entry.replace("{{PROJECT}}", project).replace("{{CLI}}", cli))
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
    assets = SKILL_DIR / "assets"
    print(f"""
Next — by hand, and this is not a formality:

1. docs/review/invariants.md — the rules of YOUR project. The most important file: it is
   pasted to every agent and decides what the agent will count as a defect. Example: {assets / 'invariants.example.md'}
2. docs/review/blocks.json — `gates` (the project's gate commands) and the blocks: cross-cutting
   first, domain ones next, live-system ones last. Example: {assets / 'blocks.example.json'}
3. The manifest of the first block — docs/review/blocks/<ID>-<slug>.md: 10–15 hypotheses about your
   project and the acceptance criterion. Example: {assets / 'manifest.example.md'}
4. `{cli} init`, then `{cli} coverage` — and deal with the unowned files until there are
   none left. This is where everything forgotten surfaces.
5. The banner in the root instructions file ({assets / 'agent-banner.md'}), otherwise a new session
   will not know a review is in progress and will start its own parallel one.""")
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
    c.add_argument("--scope", help="fixreview: the half of the diff for this reviewer (backend, ui…)")

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

    c = sub.add_parser("set-finding", help="move a finding (or several): fixed / rejected / duplicate / deferred")
    c.add_argument("finding", nargs="+")
    c.add_argument("status")
    c.add_argument("--commit", help="fix commit; required for fixed")
    c.add_argument("--reason", help="reject reason; required for rejected")
    c.add_argument("--dup-of", dest="dup_of", help="id of the finding this one duplicates")
    c.add_argument("--rule", help="what closes the class: path to the guard, test or linter rule")
    c.add_argument("--fixed-in", dest="fixed_in", action="append",
                   help="where the fix was made, if not in the finding's file (repeatable)")

    c = sub.add_parser("hypotheses", help="the block's hypotheses and their verdicts")
    c.add_argument("block")

    c = sub.add_parser("restamp", help="confirm the edits were reviewed: of a block or of the file under a finding")
    c.add_argument("block", help="block (H1) or finding (H1-003)")

    sub.add_parser("backfill", help="stamp fingerprints on old blocks and findings (with a journal entry)")

    c = sub.add_parser("inventory", help="repository tree: files, lines, binaries, whose — for cutting blocks")
    c.add_argument("--depth", type=int, default=2)
    c.add_argument("--under", help="only under this directory")
    c.add_argument("--unassigned", action="store_true", help="only unowned files")
    sub.add_parser("sizes", help="size of every block against the readability ceiling")

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
        "check": cmd_check, "log": cmd_log, "import": cmd_import,
        "set-finding": cmd_set_finding, "hypotheses": cmd_hypotheses,
        "restamp": cmd_restamp, "roots": cmd_roots, "backfill": cmd_backfill,
        "inventory": cmd_inventory, "sizes": cmd_sizes,
        "setup": cmd_setup,
    }[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
