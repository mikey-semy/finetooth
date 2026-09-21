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
import json
import signal
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REVIEW = ROOT / "docs" / "review"
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
ROLES = ["hunter", "verify", "fix"]

# A block left `running` for longer than this almost certainly means a session
# died mid-flight rather than that an agent is still reading.
STALE_RUNNING_HOURS = 24


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def die(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(2)


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        die(f"{path.relative_to(ROOT)} is missing — run `make review-init`")
    except json.JSONDecodeError as exc:
        die(f"{path.relative_to(ROOT)} is not valid JSON: {exc}")


def save_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def git_files(pathspecs: list[str]) -> set[str]:
    """Tracked files matching git pathspecs.

    An empty pathspec list means an empty set, NOT everything: a block that
    declares no paths (the ones that work on the running stand) owns no files,
    and must not be able to claim coverage it never earned. Use all_files() to
    ask for the whole repository on purpose.
    """
    if not pathspecs:
        return set()
    out = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "-z", "--"] + pathspecs,
        capture_output=True, text=True, check=True,
    ).stdout
    return {p for p in out.split("\0") if p}


def all_files() -> set[str]:
    out = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "-z"], capture_output=True, text=True, check=True
    ).stdout
    return {p for p in out.split("\0") if p}


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


# ------------------------------------------------------------------------- status


def phase_name(phase: int) -> str:
    return {
        0: "0 · подготовка",
        1: "1 · сквозные инварианты",
        2: "2 · вертикальные срезы",
        3: "3 · проверки на живом стенде",
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
            print(f"\n── Фаза {phase_name(phase)} " + "─" * 40)
        s = st["blocks"].get(b["id"], {})
        status = s.get("status", "todo")
        opened = open_by_block.get(b["id"], 0)
        tail = f"  открытых находок: {opened}" if opened else ""
        print(f"  {mark.get(status,'?')} {b['id']:<4} {status:<9} {b['title']}{tail}")

    total = len(defn["blocks"])
    closed = sum(1 for b in defn["blocks"] if st["blocks"].get(b["id"], {}).get("status") == "closed")
    print(f"\nблоков: {closed}/{total} закрыто")

    by_sev = {s: 0 for s in SEVERITIES}
    for f in rows:
        if f.get("status") == "open":
            by_sev[f.get("severity", "low")] = by_sev.get(f.get("severity", "low"), 0) + 1
    print("находок открыто: " + ", ".join(f"{s}={by_sev.get(s,0)}" for s in SEVERITIES)
          + f"  (всего записей: {len(rows)})")

    nxt = next_block(defn, st)
    if nxt:
        cur = st["blocks"][nxt["id"]]["status"]
        role = "verify" if cur == "hunted" else "hunter"
        print(f"\nследующий блок: {nxt['id']} ({nxt['title']}) — статус {cur}")
        print(f"промпт:  make review-prompt BLOCK={nxt['id']} ROLE={role}")
        print(f"манифест: docs/review/blocks/{nxt['id']}-{nxt['slug']}.md")
    else:
        print("\nвсе блоки закрыты — пора сводить находки и удалять docs/review/")
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
    unassigned = everything - set(owned)
    return owned, excluded, unassigned


def cmd_coverage(args) -> int:
    owned, excluded, unassigned = coverage_map()
    lines = ["file\tblocks"]
    for f in sorted(owned):
        lines.append(f"{f}\t{','.join(owned[f])}")
    COVERAGE_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")

    total = len(owned) + len(unassigned)
    print(f"покрыто:     {len(owned)}/{total} файлов")
    print(f"исключено:   {len(excluded)} (с обоснованием в blocks.json)")
    print(f"карта:       docs/review/coverage.tsv")
    if unassigned:
        print(f"\nНЕ ПОКРЫТО: {len(unassigned)} файлов — ревью неполное:")
        for f in sorted(unassigned)[: args.limit]:
            print(f"  {f}")
        if len(unassigned) > args.limit:
            print(f"  … ещё {len(unassigned) - args.limit}")
        return 1
    print("\nнепокрытых файлов нет")
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
        return "(нет)"
    if len(refs) <= REF_LIST_LIMIT:
        return "\n".join(refs)
    return (
        "\n".join(pathspecs)
        + f"\n\n({len(refs)} файлов. Список сокращён до шаблонов — разверни нужную "
        "часть сам: `git ls-files -- <шаблон>`.)"
    )


def cmd_prompt(args) -> int:
    defn = blocks()
    idx = block_index(defn)
    if args.block not in idx:
        die(f"unknown block {args.block}; known: {', '.join(idx)}")
    b = idx[args.block]
    manifest = REVIEW / "blocks" / f"{b['id']}-{b['slug']}.md"
    if not manifest.exists():
        die(f"manifest missing: {manifest.relative_to(ROOT)}")
    template = REVIEW / "prompts" / f"{args.role}.md"
    if not template.exists():
        die(f"prompt template missing: {template.relative_to(ROOT)}")

    files = sorted(git_files(b.get("paths", [])))
    refs = sorted(git_files(b.get("ref_paths", [])) - set(files))
    report = f"docs/review/reports/{b['id']}-{b['slug']}.{args.role}.md"

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
        "{{FILES}}": "\n".join(files) if files else "(нет)",
        "{{FILE_COUNT}}": str(len(files)),
        "{{REF_FILES}}": render_refs(b.get("ref_paths", []), refs),
        "{{FINDINGS}}": render_findings_for(b["id"]),
    }
    for k, v in subs.items():
        body = body.replace(k, v)
    print(body)
    return 0


def block_findings_path(b: dict) -> Path:
    return REVIEW / "reports" / f"{b['id']}-findings.jsonl"


def render_findings_for(block_id: str) -> str:
    rows = [f for f in findings() if f.get("block") == block_id and f.get("status") == "open"]
    if not rows:
        return "(открытых находок по блоку нет — уточни у ведущей сессии, зачем запущен фиксер)"
    order = {s: i for i, s in enumerate(SEVERITIES)}
    rows.sort(key=lambda f: (order.get(f.get("severity"), 9), f.get("id", "")))
    out = []
    for f in rows:
        where = f.get("file", "")
        if f.get("line"):
            where += f":{f['line']}"
        out.append(
            f"### {f['id']} · {f.get('severity')} · уверенность {f.get('confidence')}\n"
            f"**Место:** `{where}`\n\n"
            f"**Что не так:** {f.get('claim','')}\n\n"
            f"**Сценарий отказа:** {f.get('scenario','')}\n"
            + (f"\n**Нарушенный инвариант:** {f.get('invariant')}\n" if f.get("invariant") else "")
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
        die(f"нет файла находок блока: {src.relative_to(ROOT)}")

    incoming = []
    for n, line in enumerate(src.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            incoming.append(json.loads(line))
        except json.JSONDecodeError as exc:
            die(f"{src.name} строка {n}: не JSON — {exc}")

    existing = findings()
    mine = [f for f in existing if f.get("block") == args.block]
    locked = [f for f in mine if f.get("status") not in ("open", "rejected")]
    if locked and not args.force:
        ids = ", ".join(f.get("id", "?") for f in locked)
        die(
            f"по блоку {args.block} уже есть находки в работе ({ids}) — "
            "повторный импорт затёр бы их состояние; используй --force, если это осознанно"
        )

    kept = [f for f in existing if f.get("block") != args.block]
    width = 3
    for i, f in enumerate(incoming, 1):
        f.setdefault("block", args.block)
        f["id"] = f.get("id") or f"{args.block}-{i:0{width}d}"
        f.setdefault("status", "open")
        f.setdefault("confidence", "plausible")
        f.setdefault("fix_commit", None)
        f.setdefault("dup_of", None)
        f["imported_at"] = now()
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
    print(f"{args.block}: импортировано {len(incoming)} записей, из них открытых {live}")
    print("не забудь: make review-findings && make review-check")
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
    if args.status == "running" and not s.get("started"):
        s["started"] = now()
    if args.status == "closed":
        s["finished"] = now()
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


# ------------------------------------------------------------------------ findings


def render_findings_md(rows: list[dict]) -> str:
    """Render findings.md from the finding rows.

    Deliberately a PURE function of `findings.jsonl`: no wall clock, no counts
    of anything not in the rows. A generation stamp would make every run of
    `make review-findings` a diff, so the file would arrive in review commits as
    noise and `review-check` could not tell a stale render from a fresh one by
    comparing content. When the file changed is a question git already answers.
    """
    order = {s: i for i, s in enumerate(SEVERITIES)}
    rows = sorted(rows, key=lambda f: (order.get(f.get("severity"), 9), f.get("id", "")))

    out = [
        "# Находки ревью",
        "",
        "> Файл СГЕНЕРИРОВАН из `findings.jsonl` командой `make review-findings`.",
        "> Не редактируй его руками — правь jsonl и перегенерируй.",
        "",
    ]
    live = [f for f in rows if f.get("status") == "open"]
    out.append(f"Открыто: **{len(live)}** из {len(rows)} записей.")
    out.append("")
    for sev in SEVERITIES:
        chunk = [f for f in rows if f.get("severity") == sev]
        if not chunk:
            continue
        out.append(f"## {sev} ({sum(1 for f in chunk if f.get('status') == 'open')} открыто / {len(chunk)})")
        out.append("")
        out.append("| id | блок | статус | место | что не так |")
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
    print(f"findings.md перегенерирован: {len(live)} открыто, {len(rows)} всего")
    for b in defn["blocks"]:
        n = sum(1 for f in rows if f.get("block") == b["id"] and f.get("status") == "open")
        if n:
            print(f"  {b['id']:<4} {n}")
    return 0


# --------------------------------------------------------------------------- check


def cmd_check(args) -> int:
    defn, st, rows = blocks(), state(), findings()
    idx = block_index(defn)
    problems: list[str] = []

    # 1. state and definition agree
    for bid in idx:
        if bid not in st["blocks"]:
            problems.append(f"{bid}: нет записи в state.json — запусти `make review-init`")
    for bid in st["blocks"]:
        if bid not in idx:
            problems.append(f"{bid}: есть в state.json, но отсутствует в blocks.json")

    # 2. every block has a manifest
    for b in defn["blocks"]:
        m = REVIEW / "blocks" / f"{b['id']}-{b['slug']}.md"
        if not m.exists():
            problems.append(f"{b['id']}: нет манифеста {m.relative_to(ROOT)}")

    # 3. declared reports exist
    for bid, s in st["blocks"].items():
        for r in s.get("reports", []):
            if not (ROOT / r).exists():
                problems.append(f"{bid}: в state.json заявлен отчёт {r}, которого нет на диске")

    # 4. a block cannot be past `running` without a hunter report
    for b in defn["blocks"]:
        s = st["blocks"].get(b["id"], {})
        if s.get("status") in ("hunted", "verified", "triaged", "fixing", "closed"):
            hunter = REVIEW / "reports" / f"{b['id']}-{b['slug']}.hunter.md"
            if not hunter.exists():
                problems.append(
                    f"{b['id']}: статус {s['status']}, но отчёта охотника нет — статус не подтверждён работой"
                )

    # 5. a session that died mid-block
    for bid, s in st["blocks"].items():
        if s.get("status") == "running" and s.get("started"):
            started = dt.datetime.strptime(s["started"], "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=dt.timezone.utc
            )
            hours = (dt.datetime.now(dt.timezone.utc) - started).total_seconds() / 3600
            if hours > STALE_RUNNING_HOURS:
                problems.append(
                    f"{bid}: висит в running {hours:.0f} ч — сессия, вероятно, оборвалась; перезапусти блок"
                )

    # 6. findings are well-formed and point at real code
    tracked = all_files()
    seen_ids: set[str] = set()
    for f in rows:
        fid = f.get("id", "<без id>")
        if fid in seen_ids:
            problems.append(f"находка {fid}: дублирующийся id")
        seen_ids.add(fid)
        for field in ("id", "block", "severity", "confidence", "status", "file", "claim", "scenario"):
            if not f.get(field):
                problems.append(f"находка {fid}: не заполнено поле {field}")
        if f.get("block") not in idx:
            problems.append(f"находка {fid}: ссылается на несуществующий блок {f.get('block')}")
        if f.get("severity") not in SEVERITIES:
            problems.append(f"находка {fid}: severity={f.get('severity')} вне словаря")
        if f.get("confidence") not in CONFIDENCE:
            problems.append(f"находка {fid}: confidence={f.get('confidence')} вне словаря")
        if f.get("status") not in FINDING_STATUS:
            problems.append(f"находка {fid}: status={f.get('status')} вне словаря")
        if f.get("file") and f["file"] not in tracked and not f["file"].startswith("("):
            problems.append(f"находка {fid}: файла {f['file']} нет в репозитории")
        if f.get("status") == "fixed" and not f.get("fix_commit"):
            problems.append(f"находка {fid}: помечена fixed, но не указан коммит правки")
        if f.get("status") == "duplicate" and not f.get("dup_of"):
            problems.append(f"находка {fid}: помечена duplicate, но не указано, чего именно")
        if f.get("confidence") == "rejected" and f.get("status") == "open":
            problems.append(f"находка {fid}: отвергнута верификатором, но всё ещё open")
        if len(f.get("claim") or "") > CLAIM_MAX:
            problems.append(
                f"находка {fid}: claim длиной {len(f['claim'])} символов при пределе {CLAIM_MAX} — "
                "это заголовок для сводной таблицы, а доказательства идут в отчёт блока"
            )
        if len(f.get("scenario") or "") > SCENARIO_MAX:
            problems.append(
                f"находка {fid}: scenario длиной {len(f['scenario'])} символов при пределе {SCENARIO_MAX}"
            )

    # 7. findings.md agrees with findings.jsonl. Compared by CONTENT, not by
    #    mtime: a clone or a `git checkout` stamps every file with the moment it
    #    was written, in whatever order, so mtimes say nothing about which of the
    #    two is the newer truth.
    if FINDINGS_MD.exists():
        if FINDINGS_MD.read_text(encoding="utf-8") != render_findings_md(rows):
            problems.append("findings.md разошёлся с findings.jsonl — запусти `make review-findings`")

    # 8. a pattern that matches nothing silently shrinks a block's scope: the
    #    manifest promises to read code that was never handed to the agent.
    for b in defn["blocks"]:
        for key in ("paths", "ref_paths"):
            for spec in b.get(key, []):
                if not git_files([spec]):
                    problems.append(
                        f"{b['id']}: шаблон {key} `{spec}` не совпадает ни с одним файлом — "
                        "блок молча сузился"
                    )

    # 9. coverage
    _, _, unassigned = coverage_map()
    if unassigned:
        problems.append(f"{len(unassigned)} файлов не принадлежат ни одному блоку — `make review-coverage`")

    if problems:
        print("ПРОВЕРКА НЕ ПРОЙДЕНА:\n")
        for p in problems:
            print(f"  · {p}")
        return 1
    print("состояние ревью непротиворечиво")
    return 0


# ---------------------------------------------------------------------------- log


def cmd_log(args) -> int:
    """Append a dated line to the journal. Decisions are what a re-run cannot recover."""
    if not JOURNAL_FILE.exists():
        JOURNAL_FILE.write_text("# Дневник ревью\n\n", encoding="utf-8")
    entry = f"- **{now()}** · `{args.block}` — {args.text}\n"
    with JOURNAL_FILE.open("a", encoding="utf-8") as fh:
        fh.write(entry)
    print("записано в journal.md")
    return 0


def main() -> int:
    # `make review-prompt BLOCK=H1 ROLE=hunter | head` is the obvious way to look
    # at a prompt before handing it to an agent; without this, python answers a
    # closed pipe with a traceback and exit code 120, which reads like the tool
    # is broken.
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)

    p = argparse.ArgumentParser(prog="review", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="создать/дополнить state.json по blocks.json").add_argument(
        "--force", action="store_true", help="перезаписать состояние с нуля"
    )
    sub.add_parser("status", help="где мы сейчас")
    sub.add_parser("next", help="id следующего незакрытого блока")

    c = sub.add_parser("coverage", help="карта файл→блок; падает, если есть непокрытые")
    c.add_argument("--limit", type=int, default=40)

    c = sub.add_parser("prompt", help="собрать промпт для агента")
    c.add_argument("block")
    c.add_argument("--role", choices=ROLES, default="hunter")

    c = sub.add_parser("set-status", help="перевести блок в новый статус")
    c.add_argument("block")
    c.add_argument("status")
    c.add_argument("--report", action="append")
    c.add_argument("--note")

    c = sub.add_parser("import", help="втянуть находки блока в общий реестр")
    c.add_argument("block")
    c.add_argument("--force", action="store_true", help="перезаписать находки блока, уже взятые в работу")

    sub.add_parser("findings", help="перегенерировать findings.md из findings.jsonl")
    sub.add_parser("check", help="проверить непротиворечивость состояния")

    c = sub.add_parser("log", help="дописать строку в дневник")
    c.add_argument("block")
    c.add_argument("text")

    args = p.parse_args()
    return {
        "init": cmd_init, "status": cmd_status, "next": cmd_next, "coverage": cmd_coverage,
        "prompt": cmd_prompt, "set-status": cmd_set_status, "findings": cmd_findings,
        "check": cmd_check, "log": cmd_log, "import": cmd_import,
    }[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
