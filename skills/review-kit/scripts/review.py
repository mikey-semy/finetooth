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

# Каталог скилла: инструмент лежит в `<скилл>/scripts/`, шаблоны ролей — в
# `<скилл>/references/`, заготовки — в `<скилл>/assets/`.
SKILL_DIR = Path(__file__).resolve().parent.parent


def repo_root() -> Path | None:
    """Корень репозитория, КОТОРЫЙ РЕВЬЮИРУЕМ, — от рабочего каталога, а не от файла.

    Пока инструмент копировался в проект, корень спрашивали у git от его собственного
    расположения. Скилл лежит где угодно — в `~/.claude/skills/`, в `.agents/skills/`
    чужого клона, — и корень «от файла» указывал бы на каталог скилла или вовсе на
    `~/.claude`, если тот под git: инструмент молча писал бы состояние туда. Ревьюируют
    репозиторий, в котором работают, — его и спрашиваем.
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

# Версия набора. Скилл ставится копией (в проект или в домашний каталог), и спросить
# «что у меня стоит» больше не у кого — только у него самого.
VERSION = "0.4.1"


def default_cli() -> str:
    """Как звать ЭТОТ экземпляр инструмента — из его настоящего пути.

    Строка идёт только в подсказки: отказ обязан говорить, что набрать. Раньше её
    вписывал установщик, и копия, поставленная руками, советовала несуществующую
    команду. Теперь путь известен сам: внутри проекта — относительный, в домашнем
    каталоге — через `~`, иначе абсолютный. Проект, который зовёт инструмент по-своему
    (`npm run review --`, `make review`), пишет это полем `cli` в `blocks.json`.
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
ROLES = ["hunter", "verify", "fix"]

# A block left `running` for longer than this almost certainly means a session
# died mid-flight rather than that an agent is still reading.
STALE_RUNNING_HOURS = 24

# Блок, прошедший проверку, не перестаёт быть проверенным при переходе дальше. Пока
# условие было «verified или closed», перевод в triaged зеленил гейт гипотез и гейт
# ограничений охвата, ничего не добавив: статус менялся, пробел оставался.
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


# Режимы в индексе git, которые выглядят как файлы, но файлами не являются.
# Проверено экспериментом: подмодуль (160000) в `ls-files` — одна запись, а на диске
# каталог, и счётчик строк падает на нём с IsADirectoryError. Его код живёт в другом
# репозитории и ревьюится там.
# Симлинк (120000) — НЕ исключается: ссылку можно перенаправить, и это правка, которую
# кто-то обязан увидеть. Исключение убирало его отовсюду — ни владельца, ни «непокрытого»,
# ни отпечатка. Двойного счёта при этом нет: строки берутся из индекса, где у симлинка
# лежит текст ссылки, а не содержимое цели; отпечаток — тоже от текста ссылки.
NOT_A_FILE_MODES = ("160000",)


def listed(pathspecs: list[str] | None) -> set[str]:
    """Отслеживаемые файлы — настоящие файлы, без подмодулей и симлинков."""
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
    """Отпечаток содержимого файла — тот же, что считает git, без лишних зависимостей."""
    if not rel or rel.startswith("("):
        return None
    p = ROOT / rel
    if p.is_symlink():
        # `hash-object` прошёл бы по ссылке и хешировал цель: перенаправление на файл с
        # тем же содержимым прошло бы незамеченным. Хешируется то, чем симлинк и является.
        return "link:" + hashlib.sha1(os.readlink(p).encode("utf-8")).hexdigest()
    if not p.is_file():
        return None
    out = subprocess.run(["git", "-C", str(ROOT), "hash-object", "--", rel],
                         capture_output=True, text=True)
    return out.stdout.strip() or None


def block_sha(b: dict) -> str:
    """Отпечаток того, что блок получает в работу: состав файлов плюс их содержимое.

    Считается по тем же правилам, по которым собирается промпт (исключения вычтены),
    иначе отпечаток стерёг бы не тот набор, который агент читал.
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
    """Отпечаток ТЕКСТА гипотез, а не их числа.

    Идентификатор гипотезы — её порядковый номер, и номер переживает правку: переставь
    пункты или замени вопрос другим того же количества — вердикт «H1.2 проверена», данный
    старому вопросу, молча засчитается новому. Отпечаток текста снимается там же, где
    отпечаток файлов, и правка манифеста после проверки ловится так же, как правка кода.
    """
    m = manifest_path(b)
    items = section_items_full(m.read_text(encoding="utf-8"), HYPOTHESIS_HEADING) if m.exists() else []
    norm = [re.sub(r"\s+", " ", LIST_MARK.sub("", t)).strip() for t in items]
    return hashlib.sha256("\n".join(norm).encode("utf-8")).hexdigest()[:16]


def refs_sha(b: dict) -> str:
    """Отпечаток КОНТЕКСТА: файлов `ref_paths`, которые промпт даёт блоку для справки."""
    defn = blocks()
    excluded = git_files([e["pattern"] for e in defn.get("exclusions", [])])
    own = git_files(b.get("paths", []))
    h = hashlib.sha256()
    for rel in sorted(git_files(b.get("ref_paths", [])) - excluded - own):
        h.update(rel.encode("utf-8"))
        h.update((file_sha(rel) or "").encode("utf-8"))
    return h.hexdigest()[:16]


def stamp(b: dict, s: dict) -> None:
    """Записать, ЧТО просмотрено: файлы блока, контекст и вопросы, на которые отвечали."""
    s["reviewed_sha"] = block_sha(b)
    s["refs_sha"] = refs_sha(b)
    s["hypotheses_sha"] = hypotheses_sha(b)


def changed_since_review(b: dict, seen: str) -> bool:
    return block_sha(b) != seen


def file_lines(rel: str) -> int | None:
    """Число строк — из ИНДЕКСА, а не с диска.

    На диске файла может не быть при живой записи в индексе (удалили, не закоммитив;
    sparse-checkout вообще не выкладывает часть дерева, а `ls-files` её печатает).
    Открывать такой путь — падать на ровном месте или молча терять его из знаменателя.
    """
    out = subprocess.run(["git", "-C", str(ROOT), "show", f":{rel}"],
                         capture_output=True, check=False)
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
        print(f"промпт:  {CLI} prompt {nxt['id']} --role {role}")
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


# Насколько дерево должно отстать по ВРЕМЕНИ, чтобы это значило «оно протухло».
#
# Мерить надо время, а не коммиты: в случае, ради которого проверка и заведена, копия
# соседнего сервиса отставала всего на ДВА коммита — и на двенадцать суток. Два коммита
# не насторожили бы никого, а за двенадцать дней дыру успели закрыть, и проверяющий
# «подтвердил исполнением» дефект, которого уже не было.
#
# Порог ниже того замера (12 суток) и выше обычной жизни рабочей ветки: ветка живёт дни,
# протухшая копия — недели. Счёт коммитов сознательно не используется: ветка, отведённая
# час назад, отстаёт от master на десяток коммитов и не устарела ничуть.
STALE_TREE_DAYS = 7


def stale_tree() -> tuple[float, str] | None:
    """Насколько вершина сервера свежее нашей — в сутках, если разрыв велик.

    Сеть не трогаем (`fetch` — дело человека), смотрим то, что git уже знает.
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

    # Считаем от ТОЧКИ РАСХОЖДЕНИЯ, а не от своей вершины: свежий коммит в давно
    # отведённой ветке делает её вершину новее удалённой и прячет то, что ветка не
    # содержит ни одного чужого исправления за всё это время.
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
        # ⚠️ Отказ обязан говорить, ЧТО делать. Плоские каталоги разрезаны поимённо
        # намеренно: пусть блок для нового файла выбирает человек, а не шаблон —
        # молча подошедший глоб означает «файл числится прочитанным», хотя его никто
        # не открывал. Но если отказ ограничится списком путей, человек допишет файл
        # в первый попавшийся блок, и цена решения не окупится.
        print(
            "\nЧто делать: добавьте путь в блок, который отвечает ЗА ЭТУ ОБЛАСТЬ "
            "(docs/review/blocks.json, поле paths).\n"
            f"Список блоков с их вопросами: {CLI} status.\n"
            "Выбор делает человек: файл, попавший в блок по совпадению шаблона, "
            "будет числиться прочитанным, не будучи прочитанным."
        )
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


def volume_note(files: list[str]) -> str:
    """Сколько кода блок просит прочитать — и что из этого заведомо не прочитается.

    Бюджет должен стоять в самом задании, а не в голове у ведущей сессии. Соседи по нише
    делают это двумя способами, и нужны оба: repomix роняет сборку ненулевым кодом, когда
    пакет перерос бюджет, а ai-digest оставляет невлезший файл в выводе заглушкой — путь
    виден, содержимого нет. Промолчать хуже всего: тогда агент отчитывается об охвате,
    которого не было, и никто не скажет, где проходила граница.
    """
    sizes = sorted(((file_lines(f) or 0, f) for f in files), reverse=True)
    total = sum(n for n, _ in sizes)
    # Грубая оценка, а не замер: около четырёх символов на токен — общее место, и здесь
    # оно честнее точного счёта, потому что токенайзер у каждой модели свой.
    chars = sum(len(f) for f in files) + total * 40
    out = [f"Файлов: {len(files)}. Строк: {total}. Порядок величины: ~{chars // 4000}k токенов "
           f"только на чтение, без рассуждений и вызовов инструментов."]
    limit = readable_lines()
    if total <= limit:
        out.append(f"Это укладывается в то, что читается за сеанс (порог {limit} строк).")
        return "\n".join(out)

    out.append(f"\n⚠️ **Блок больше, чем прочитывается за сеанс** — {total} строк при пороге "
               f"{limit}. Прочитать всё внимательно не выйдет, и честный выход один: "
               f"прочитать столько, сколько получится, и **поимённо назвать остальное** в "
               f"разделе об ограничениях охвата. Не делайте вид, что прочитали.")
    out.append("\nГде проходит граница бюджета (по убыванию размера, накопительно):")
    shown = 0
    for n, f in sizes:
        shown += 1
        acc = sum(x for x, _ in sizes[:shown])
        mark = "  " if acc <= limit else "▲ "
        out.append(f"  {mark}{acc:>6} · {f} ({n} строк)")
        if acc > limit * 2 and shown < len(sizes):
            out.append(f"  … и ещё {len(sizes) - shown} файл(ов)")
            break
    out.append("\n▲ — то, что за границей. Это не запрет их открывать: это то, что вы обязаны "
               "назвать непрочитанным, если не открыли.")
    return "\n".join(out)


def cmd_prompt(args) -> int:
    defn = blocks()
    idx = block_index(defn)
    if args.block not in idx:
        die(f"unknown block {args.block}; known: {', '.join(idx)}")
    b = idx[args.block]
    manifest = manifest_path(b)
    if not manifest.exists():
        die(f"manifest missing: {manifest.relative_to(ROOT)}")
    # Проект может держать свою версию шаблона роли в `docs/review/prompts/` — тогда
    # берётся она. Нет — шаблон скилла: своя копия не обязательна и не отстаёт от него.
    template = REVIEW / "prompts" / f"{args.role}.md"
    if not template.exists():
        template = SKILL_DIR / "references" / f"{args.role}.md"
    if not template.exists():
        die(f"нет шаблона роли {args.role}: ни docs/review/prompts/{args.role}.md, ни {template}")

    # ⚠️ Исключения вычитаются и здесь. Карта покрытия и порог читаемости их вычитают,
    # а промпт — нет, и блок получал в работу то, чего в его размере не числилось:
    # `package-lock.json` на 19 тысяч строк, кодоген. Агент послушно начинал их читать,
    # контекст уходил на файлы, которые никто читать не собирался.
    excluded = git_files([e["pattern"] for e in defn.get("exclusions", [])])
    files = sorted(git_files(b.get("paths", [])) - excluded)
    refs = sorted(git_files(b.get("ref_paths", [])) - excluded - set(files))
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
        "{{VOLUME}}": volume_note(files),
        "{{REF_FILES}}": render_refs(b.get("ref_paths", []), refs),
        "{{FINDINGS}}": render_findings_for(b["id"]),
        # Имя проекта и его ворота — подстановки, а не текст в шаблоне. Скопированный
        # без вычитки шаблон здоровался с агентом от имени ЧУЖОГО проекта, и это
        # заметили не сразу: задание выглядело осмысленным целиком.
        "{{PROJECT}}": defn.get("project", ROOT.name),
        "{{GATES}}": "\n".join(f"- `{g}`" for g in defn.get("gates", []))
        or '(в blocks.json не заполнено поле "gates" — впишите команды ворот проекта)',
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
    if args.append:
        # ДОБОР: находки, найденные поверх уже записанного. Штатный импорт заменяет
        # находки блока целиком, и у блока, где часть уже починена, это стёрло бы отметки
        # о починке — в соседнем проекте на этом обожглись и завели отдельный сводчик.
        # Здесь только дописываем, со следующими свободными номерами блока.
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
            # Файл блока после прошлого импорта хранит уже записанные находки с номерами —
            # добор дописывает к нему новые строки. Записанное пропускается: реестр о нём
            # знает больше (статус, починка), и файл блока его не перебивает.
            if f.get("id") in known:
                continue
            f.setdefault("block", args.block)
            if f["block"] != args.block:
                die(f"в файле добора находка чужого блока {f['block']} — сведение остановлено")
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
        # Номера вписываются обратно в файл блока — как при штатном импорте. Повторный
        # запуск их узнает и ничего не допишет; переименовывать файл «сведённым» не нужно,
        # а это переименование уносило файл блока целиком.
        src.write_text(
            "\n".join(json.dumps(f, ensure_ascii=False) for f in incoming) + "\n",
            encoding="utf-8",
        )
        print(f"{args.block}: дописано {len(added)} находок (добор)")
        print(f"не забудь: {CLI} findings && {CLI} check")
        return 0

    mine = [f for f in existing if f.get("block") == args.block]
    locked = [f for f in mine if f.get("status") not in ("open", "rejected")]
    if locked and not args.force:
        ids = ", ".join(f.get("id", "?") for f in locked)
        die(
            f"по блоку {args.block} уже есть находки в работе ({ids}) — "
            "повторный импорт затёр бы их состояние; используй --force, если это осознанно"
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
        # Отпечаток кода, о котором находка говорит. Реестр протухает быстрее, чем кажется:
        # находку чинят, статус не переводят, и следующий проход спорит с описанием кода,
        # которого уже нет. Так и вышло — два проверяющих независимо «опровергли» две
        # находки, закрытые накануне. Отпечаток превращает это из спора в вопрос.
        #
        # Повторный импорт отпечаток уже известной находки НЕ переснимает: иначе он молча
        # признавал бы текущий код совпадающим с описанием, и устаревшая находка пропадала
        # из `check` без перепроверки. Подтвердить её на новом коде — `restamp <ID>`.
        # Находка, переехавшая в другой файл, — новое утверждение, и отпечаток новый.
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
    print(f"{args.block}: импортировано {len(incoming)} записей, из них открытых {live}")
    print(f"не забудь: {CLI} findings && {CLI} check")
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
    # Отпечаток того, ЧТО именно было просмотрено. Статус «пройден» без него держится
    # вечно: файлы блока перепишут, а блок так и будет числиться закрытым — просмотренным
    # оказался другой текст. Форма взята у doorstop, где у требования стоит поле `reviewed`
    # с хешем содержимого, и правка текста сама переводит его в «непросмотренные изменения».
    # Только в точках, где просмотр ЗАВЕРШЁН: проверка (verified) и закрытие после ревью
    # диффа (closed). Переход в triaged или fixing — не просмотр; пересними отпечаток там,
    # и любая смена статуса молча признавала бы изменённый код просмотренным, обходя
    # `restamp`, который существует ровно для того, чтобы это говорилось под запись.
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
    """Перевести находку: починена, отвергнута, дубль, отложена.

    Правило «findings.jsonl правится только инструментом» держалось на честном
    слове: команды, которая проставляет `fixed` и коммит правки, в наборе не
    было — реестр правили руками, а руками ставят и `fixed` без коммита, и
    `rejected` без причины. Здесь перевод проходит те же проверки, что `check`,
    и файл перегенерируется вместе с записью.
    """
    rows = findings()
    hit = [f for f in rows if f.get("id") == args.finding]
    if not hit:
        die(f"находки {args.finding} нет в реестре")
    f = hit[0]
    if args.status not in FINDING_STATUS:
        die(f"неизвестный статус {args.status}; известные: {', '.join(FINDING_STATUS)}")
    if args.status == "fixed" and not args.commit:
        die("`fixed` без коммита правки — нечем подтвердить, что дефект закрыт (--commit)")
    if args.status == "rejected" and not (args.reason or f.get("reject_reason")):
        die("`rejected` без причины отказа — следующее ревью найдёт то же самое (--reason)")
    if args.status == "duplicate" and not (args.dup_of or f.get("dup_of")):
        die("`duplicate` без указания, чего именно это дубль (--dup-of)")
    if args.dup_of and (why := dup_problem(args.finding, args.dup_of, rows)):
        die(why)
    if args.rule and (why := rule_problem(args.rule)):
        die(why)
    # Починка не обязана трогать файл, где дефект виден: маршрут чинят в общем стороже.
    # Место правки называется явно, а не подразумевается, — иначе проверка «коммит
    # касается файла находки» перестаёт отличать правку в другом месте от чужой отметки.
    for path in args.fixed_in or []:
        if not git_files([path]):
            die(f"--fixed-in {path}: такого файла в репозитории нет")

    # Отказ — это вердикт, и он живёт в двух полях: статус говорит, что с находкой делают,
    # уверенность — что о ней решили. Меняя одно без другого, реестр утверждал бы разом
    # «отвергнута» и «подтверждена». Вернуть отвергнутую в работу — значит снять вердикт:
    # она снова ждёт проверки, а не наследует «rejected».
    if args.status == "rejected":
        f["confidence"] = "rejected"
    elif f.get("status") == "rejected" and f.get("confidence") == "rejected":
        f["confidence"] = "plausible"
    f["status"] = args.status
    if args.commit:
        f["fix_commit"] = args.commit
    if args.reason:
        f["reject_reason"] = args.reason
    if args.dup_of:
        f["dup_of"] = args.dup_of
    if args.fixed_in:
        f["fixed_in"] = sorted(set(f.get("fixed_in", [])) | set(args.fixed_in))
    if args.rule:
        # Узда записывается на ВСЕ находки этого корня: класс закрыт целиком или не закрыт.
        for row in rows:
            if (row.get("root") or "") == (f.get("root") or "") and f.get("root"):
                row["rule"] = args.rule
        f["rule"] = args.rule
    f["updated_at"] = now()

    with FINDINGS_FILE.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    FINDINGS_MD.write_text(render_findings_md(rows), encoding="utf-8")
    print(f"{args.finding}: {args.status}")
    return 0


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
        "# Находки ревью",
        "",
        f"> Файл СГЕНЕРИРОВАН из `findings.jsonl` командой `{CLI} findings`.",
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


# Сколько строк агент реально прочитывает за один сеанс. Число не выдумано: соседний
# проект прошёл блок в 1727 строк за шесть запусков и два часа, а блок в 87 тысяч строк
# отчитался по 4 файлам из 14 — то есть соврал про охват, не нарушив ни одной проверки.
# Порог с запасом втрое от прочитанного, чтобы ловить заведомо невыполнимое.
READABLE_LINES = 6000  # дефолт; переопределяется полем `readable_lines` в blocks.json


def readable_lines() -> int:
    """Сколько строк блок может честно отдать агенту за сеанс.

    ⚠️ Число из ОДНОГО языка. 6000 выведены из прогонов на TypeScript, а медианный
    размер изменения различается между языками в два-три раза (826 тыс. PR, MSR 2022:
    Shell 8 строк, Ruby 13, Python 21, TypeScript 35, Java 43), и по Go с Rust данных
    нет вовсе. Переносить это число молча нельзя — проект задаёт своё в `blocks.json`,
    полем `readable_lines`.
    """
    try:
        return int(blocks().get("readable_lines") or READABLE_LINES)
    except (ValueError, TypeError):
        return READABLE_LINES


def block_lines(pathspecs: list[str]) -> tuple[int, int]:
    """Сколько файлов и строк в блоке — чтобы отличить блок от обещания.

    ⚠️ ИСКЛЮЧЁННОЕ НЕ СЧИТАЕТСЯ. Порог мерил то, чего блок не владеет: `coverage_map`
    вычитает `exclusions`, а этот счёт — нет, и H13 показывал 30 388 строк, из которых
    19 181 приходились на `package-lock.json`, исключённый ещё при заведении блоков.
    Число выходило втрое больше настоящего и требовало резать то, что и так не читают.
    Считать надо ровно тот набор, который блок получит в работу.
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
    """Подтвердить, что изменения в файлах блока просмотрены, и переснять отпечаток.

    Ровно как `doorstop review`: не «выключить проверку», а сказать под запись, что новый
    текст видели. Поэтому команда требует блок поимённо и печатает, что именно штампует.
    """
    defn, st = blocks(), state()
    idx = block_index(defn)
    if args.block not in idx:
        return restamp_finding(args.block)
    s = st["blocks"].get(args.block, {})
    if s.get("status") not in POST_VERIFY:
        die(f"{args.block} в статусе {s.get('status', 'todo')} — штамповать нечего")
    stamp(idx[args.block], s)
    s["restamped_at"] = now()
    st["updated_at"] = now()
    save_json(STATE_FILE, st)
    print(f"{args.block}: отпечаток переснят — изменения в файлах блока считаются просмотренными")
    return 0


def restamp_finding(fid: str) -> int:
    """Подтвердить, что открытая находка жива на изменившемся файле.

    Файл под находкой меняется не только её починкой: в нём чинят соседнюю находку, правят
    строку рядом. Без этой команды выхода было два, и оба ложные — закрыть живой дефект или
    править реестр руками. Штамп ставится поимённо, как у блока: «перепроверил, дефект на
    месте» говорится под запись, а не выключает проверку.
    """
    rows = findings()
    hit = [f for f in rows if f.get("id") == fid]
    if not hit:
        die(f"нет ни блока, ни находки {fid}")
    f = hit[0]
    if f.get("status") not in ("open", "deferred"):
        die(f"находка {fid} в статусе {f.get('status')} — штампуют только открытые и отложенные")
    sha = file_sha(f.get("file", ""))
    if not sha:
        die(f"файла {f.get('file')} нет — находку переводят (`{CLI} set-finding`), а не штампуют")
    f["code_sha"] = sha
    f["restamped_at"] = now()
    with FINDINGS_FILE.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    FINDINGS_MD.write_text(render_findings_md(rows), encoding="utf-8")
    print(f"{fid}: отпечаток кода переснят — дефект подтверждён на текущей версии {f.get('file')}")
    return 0


# Сколько раз класс дефекта должен повториться, чтобы список правок перестал быть ответом.
#
# Число не выдумано: это правило карты корней ревью, выведенное из практики — «второй повтор
# пишем строкой, третий закрываем уздой». Причина простая: два экземпляра ещё могут оказаться
# совпадением, третий означает, что дефект порождается устройством кода, а не невнимательностью,
# и следующий появится сам. Аудиторские фирмы делают то же самое под именем variant analysis:
# из находки пишут правило статического анализа и гоняют по всей базе.
ROOT_RULE_AT = 3


def roots_of(rows: list[dict], block_id: str | None = None) -> dict[str, list[dict]]:
    """Находки, сгруппированные по корню. Без корня — не группируются."""
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
    """Корни: сколько экземпляров у каждого и чем класс закрыт."""
    rows = findings()
    groups = roots_of(rows, args.block)
    if not groups:
        print("корней не отмечено — поле `root` у находок не заполнено")
        return 0
    for root, items in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        rule = next((f.get("rule") for f in items if f.get("rule")), None)
        mark = f"узда: {rule}" if rule else (
            "УЗДЫ НЕТ" if len(items) >= ROOT_RULE_AT else "узды нет, но повторов мало")
        print(f"  {len(items):>2} × {root}  — {mark}")
        for f in items:
            where = f.get("file", "")
            if f.get("line"):
                where += f":{f['line']}"
            print(f"       {f.get('id','?'):<10} {f.get('status','?'):<9} {where}")
    return 0


def dup_problem(fid: str, target: str, rows: list[dict]) -> str | None:
    """Дубль обязан указывать на ДРУГУЮ СУЩЕСТВУЮЩУЮ находку, которая сама не выбыла.

    Иначе опечатка в `--dup-of` убирает живой дефект из остатка работ, не оставив в
    реестре ни одной записи, которая его несёт.
    """
    if target == fid:
        return f"находка {fid} указана дублем самой себя"
    hit = next((r for r in rows if r.get("id") == target), None)
    if hit is None:
        return f"находка {fid}: дубль несуществующей {target} — опечатка в номере?"
    if hit.get("status") in ("duplicate", "rejected"):
        return (f"находка {fid}: дубль {target}, а та сама {hit.get('status')} — "
                f"дефект не остаётся ни в одной живой записи; укажите основную")
    return None


def rule_problem(rule: str) -> str | None:
    """Узда обязана существовать: опечатка в пути делала класс «закрытым» без правила.

    Форма `репозиторий:путь/к/файлу` — узда в соседнем репозитории; проверяется только
    форма, как у внешнего коммита починки. Суффиксы `::тест`, `#якорь` и `:строка`
    отрезаются. Правило линтера указывается файлом, где оно включено.
    """
    rule = (rule or "").strip()
    head, sep, tail = rule.partition(":")
    # Внешняя форма узнаётся строго: путь сразу после двоеточия и похожий на файл. Иначе
    # «eslint: no-x» — имя правила без файла — проходило бы как репозиторий «eslint».
    if sep and re.fullmatch(r"[\w-]+", head) and re.fullmatch(r"[^\s:]*[./][^\s]*", tail):
        return None
    path = re.split(r"::|#", rule)[0]
    path = re.sub(r":\d+$", "", path).strip().rstrip("/")
    if not path:
        return "узда пустая"
    if not git_files([path]):
        return (f"узда «{rule}»: в репозитории нет такого файла — опечатка в пути или "
                f"узду удалили; укажите путь к тесту, правилу линтера или гейту CI")
    return None


def cmd_backfill(args) -> int:
    """Проставить отпечатки там, где их нет: блокам после проверки и открытым находкам.

    Отпечатки появились в наборе позже, чем часть ревью была пройдена, и у старых записей
    их нет. Без них проверка свежести молча пропускает ровно то, что старше всего. Снимок
    делается с ТЕКУЩЕГО кода, а не с того, на котором блок проходили, — поэтому каждое
    проставление пишется в журнал с коммитом: изменения до этого момента не отслежены, и
    это должно быть видно, а не подразумеваться.
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
        print("отпечатки на месте — проставлять нечего")
        return 0
    if stamped_blocks:
        st["updated_at"] = now()
        save_json(STATE_FILE, st)
    if stamped_findings:
        with FINDINGS_FILE.open("w", encoding="utf-8") as fh:
            for f in rows:
                fh.write(json.dumps(f, ensure_ascii=False) + "\n")
        FINDINGS_MD.write_text(render_findings_md(rows), encoding="utf-8")
    note = (f"Отпечатки проставлены задним числом на коммите {head}: блоки "
            f"{', '.join(stamped_blocks) or '—'}; находок {len(stamped_findings)}. "
            f"Изменения до этого коммита не отслежены.")
    if not JOURNAL_FILE.exists():
        JOURNAL_FILE.write_text("# Дневник ревью\n\n", encoding="utf-8")
    with JOURNAL_FILE.open("a", encoding="utf-8") as fh:
        fh.write(f"- **{now()}** · `backfill` — {note}\n")
    print(note)
    return 0


# --------------------------------------------------------------------- гипотезы

# Второй знаменатель покрытия. Карта файлов отвечает «файл открывали», и этого мало:
# файл можно открыть и ничего не понять. Профессиональный аудит считает покрытие не
# файлами, а вопросами к системе — у OWASP ASVS требование обязано закрыться решением
# «pass или fail», а неприменимое закрывается письменным обоснованием, не молчанием.
# Гипотезы манифеста — наши вопросы, и каждая обязана получить один из трёх вердиктов.
HYPOTHESIS_HEADING = re.compile(r"^#{1,6}\s*.*гипотез", re.IGNORECASE)
# Раздел про непросмотренное живёт под разными именами: «Ограничения охвата»,
# «Не прочитано из блока», «Чего НЕ сделал». Требовать одного заголовка значит
# заставлять переписывать готовый отчёт ради слова.
LIMITS_HEADING = re.compile(
    r"^#{1,6}\s*.*(ограничени|не проверено|не прочитано|не сделал|не смотрел|не дошёл)",
    re.IGNORECASE,
)
# Текст инструкции из шаблона охотника, скопированный в отчёт как есть, — не раскрытие.
LIMITS_PLACEHOLDER = re.compile(r"обязательный раздел, даже если он короткий", re.IGNORECASE)
LIST_ITEM = re.compile(r"^\s{0,3}(?:[-*+]\s+|\d+[.)]\s+)\S")
LIST_MARK = re.compile(r"^(?:[-*+]|\d+[.)])\s+")
# Порядок важен и словарь шире трёх слов: в живом отчёте пишут «гипотеза 2 опровергнута»
# и «не подтвердилась», и это тоже проверка — просто с отрицательным исходом, который в
# ревью ценен не меньше. Гейт обязан понимать язык, которым отчёты пишутся на самом деле,
# иначе он воюет с автором вместо того, чтобы ловить умолчание.
VERDICT_WORDS = (
    ("не проверена", "не проверена"),
    ("не проверял", "не проверена"),
    ("не удалось проверить", "не проверена"),
    ("неприменима", "неприменима"),
    ("не применима", "неприменима"),
    ("не подтвердилась", "проверена"),
    ("опровергнута", "проверена"),
    ("подтвердилась", "проверена"),
    ("подтверждена", "проверена"),
    ("проверена", "проверена"),
)


# Вердикт проверяющего по находке — словарём шаблона роли (confirmed / plausible /
# rejected / duplicate) или живым языком отчёта. Форму таблицы не требуем: отчёты пишутся
# по-разному, и гейт, воюющий с разметкой, перестают читать. Требуем содержание.
FINDING_VERDICT = re.compile(
    r"\b(confirmed|plausible|rejected|duplicate)\b|подтвержд|отверг|опроверг|дубл",
    re.IGNORECASE)
COVERAGE_VERDICT = re.compile(r"охват|полн(ый|ое|ая)\b|неполн", re.IGNORECASE)
# Строка шаблона «Полный / неполный — …», оставленная как есть, — не решение, а вопрос.
COVERAGE_PLACEHOLDER = re.compile(r"полн\w*\s*/\s*неполн", re.IGNORECASE)


def verify_report_problem(rep: Path, has_findings: bool) -> str | None:
    """Отчёт проверяющего, которого по сути нет: пустой, одни заголовки, ни одного вердикта.

    Вердикт по КАЖДОЙ находке здесь не сверяется, и это не упущение: номера в реестре
    (H1-003) выдаёт `import` уже после проверки, в отчёте их нет и быть не может.
    Вердикт по каждой находке — поле `confidence` её записи, которое проверяющий
    переписывает в итоговом файле находок, и `check` требует его у каждой.

    Существование файла доказывало только то, что файл создан: пустой `*.verify.md` при
    полном отчёте охотника проводил блок в `verified` без независимой проверки.
    """
    body = [ln for ln in rep.read_text(encoding="utf-8").splitlines()
            if ln.strip() and not ln.lstrip().startswith("#")]
    if not body:
        return (f"отчёт верификатора {rep.name} пуст — есть файл, нет проверки; "
                f"по каждой находке нужен вердикт, по блоку — состояние охвата")
    text = "\n".join(body)
    if has_findings and not FINDING_VERDICT.search(text):
        return (f"в отчёте верификатора {rep.name} нет ни одного вердикта по находкам — "
                f"confirmed / plausible / rejected / duplicate с обоснованием")
    # Охват — отдельный вопрос, не заменяемый вердиктами: найденное ничего не говорит о
    # том, что осталось непросмотренным.
    if not COVERAGE_VERDICT.search(
            "\n".join(ln for ln in body if not COVERAGE_PLACEHOLDER.search(ln))):
        return (f"в отчёте верификатора {rep.name} нет вердикта об охвате — полон ли он и "
                f"что осталось")
    return None


def line_verdict(line: str) -> str | None:
    """Вердикт строки — слово, стоящее в ней РАНЬШЕ, а не первое по словарю.

    «Проверена по коду все девять … Живым запросом не проверял» — это «проверена» с
    оговоркой. Поиск по порядку словаря находил «не проверял» где угодно в строке и
    объявлял гипотезу непроверенной. Отрицание при этом не теряется: «не проверена»
    начинается на три символа раньше вложенного в него «проверена».
    """
    low = line.lower()
    hits = [(i, v) for w, v in VERDICT_WORDS if (i := low.find(w)) >= 0]
    return min(hits)[1] if hits else None


def section_body(md: str, heading: re.Pattern) -> list[str] | None:
    """Строки раздела под первым совпавшим заголовком (подзаголовки — тоже содержание).

    None — раздела нет вовсе; пустой список — заголовок есть, под ним ничего.
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
    """Пункты верхнего уровня ЦЕЛИКОМ — со строками продолжения и вложенными подпунктами.

    Гипотеза редко умещается в строку: сценарий, граница, ожидание пишутся под ней с
    отступом. Отпечаток по одной первой строке не замечал правки ровно этой части.
    """
    lines = section_body(md, heading) or []
    marks = []
    fenced = False
    for i, ln in enumerate(lines):
        if ln.lstrip().startswith("```"):
            fenced = not fenced
        elif not fenced and LIST_ITEM.match(ln):
            # Считаются пункты ВЕРХНЕГО уровня: вложенный список под гипотезой — её
            # детали, а не новая гипотеза, и строка списка внутри блока кода — пример.
            marks.append((i, len(ln) - len(ln.lstrip())))
    if not marks:
        return []
    top = min(ind for _, ind in marks)
    starts = [i for i, ind in marks if ind == top]
    return ["\n".join(lines[a:b]).strip()
            for a, b in zip(starts, starts[1:] + [len(lines)])]


def section_items(md: str, heading: re.Pattern) -> list[str]:
    """Первые строки пунктов верхнего уровня — по тому же разбору, что и отпечаток.

    Два разбора одного раздела расходились: считавший не знал про блоки кода, и строка
    `# комментарий` внутри них обрывала раздел — гипотезы ниже терялись из счёта, хотя
    в отпечаток попадали.
    """
    return [item.split("\n", 1)[0].strip() for item in section_items_full(md, heading)]


def hypotheses(block_id: str, manifest: Path) -> list[str]:
    """Идентификаторы гипотез блока: H1.1, H1.2 … по порядку пунктов в манифесте."""
    if not manifest.exists():
        return []
    items = section_items(manifest.read_text(encoding="utf-8"), HYPOTHESIS_HEADING)
    return [f"{block_id}.{i}" for i in range(1, len(items) + 1)]


def verdicts_in(text: str, block_id: str = "") -> dict[str, str]:
    """Вердикты по гипотезам: «H1.3 — не проверена: …» или «гипотеза 3 опровергнута».

    Берётся ПЕРВОЕ упоминание — одно правило для всех форм записи. Противоречие внутри
    отчёта не разрешается порядком строк, а ловится `verdict_conflicts`.
    """
    return {h: vs[0] for h, vs in verdict_mentions(text, block_id).items()}


def verdict_conflicts(text: str, block_id: str) -> dict[str, list[str]]:
    """Гипотезы, которым один и тот же отчёт выносит разные вердикты."""
    return {h: sorted(set(vs)) for h, vs in verdict_mentions(text, block_id).items()
            if len(set(vs)) > 1}


def verdict_mentions(text: str, block_id: str = "") -> dict[str, list[str]]:
    """Все вердикты по каждой гипотезе в порядке появления."""
    out: dict[str, list[str]] = {}
    plain = re.compile(r"гипотез\w*\s*№?\s*(\d+)", re.IGNORECASE)
    # Идентификатор берётся из НАСТОЯЩЕГО имени блока, а не угадывается по форме: у больше
    # чем половины блоков реального ревью имя с буквенным суффиксом (`V1d`, `H13e`), и
    # регулярка «буквы, цифры, точка» их не ловила — вердикты таких блоков считались
    # отсутствующими, а проходили они только через запасные формы записи.
    tagged = re.compile(rf"\b({re.escape(block_id)}\.\d+)\b") if block_id else None
    for line in text.split("\n"):
        verdict = line_verdict(line)
        if not verdict:
            continue
        if tagged:
            for token in tagged.findall(line):
                out.setdefault(token, []).append(verdict)
        if not block_id:
            continue
        # Свободная форма привязывается к блоку, чей отчёт мы читаем: «гипотеза 2» в
        # отчёте H15 — это H15.2, и требовать от автора переписать её как ID незачем.
        for n in plain.findall(line):
            out.setdefault(f"{block_id}.{n}", []).append(verdict)
        # Сводная таблица «| # | гипотеза | итог |» — как отчёт по гипотезам пишется
        # чаще всего: номер стоит в первой ячейке, а вердикт в последней, и слова
        # «гипотеза» в строке нет вовсе. Без разбора таблицы гейт требовал бы
        # переписать готовый отчёт ради формы, ничего не добавив к его содержанию.
        if line.lstrip().startswith("|"):
            first = line.strip().strip("|").split("|")[0].strip()
            if first.isdigit():
                out.setdefault(f"{block_id}.{first}", []).append(verdict)
    return out


def verdicts_for(b: dict) -> dict[str, str]:
    """Вердикты по гипотезам блока, где слово проверяющего перебивает слово охотника.

    Промпт проверяющего прямо требует перебивать чужой вердикт своим, с объяснением.
    Пока отчёты склеивались в один текст, первым шёл охотник, и `setdefault` навсегда
    оставлял его вердикт: проверяющий мог написать «не проверена», а инструмент
    продолжал показывать «проверена». Читаем по ролям и накладываем в порядке
    старшинства.
    """
    out: dict[str, str] = {}
    for role in ("hunter", "fix", "verify"):  # verify последним — он и перебивает
        p = REVIEW / "reports" / f"{b['id']}-{b['slug']}.{role}.md"
        if p.exists():
            out.update(verdicts_in(p.read_text(encoding="utf-8"), b["id"]))
    return out


def cmd_hypotheses(args) -> int:
    """Показать гипотезы блока и их вердикты — что закрыто, что висит."""
    defn = blocks()
    idx = block_index(defn)
    if args.block not in idx:
        die(f"unknown block {args.block}")
    b = idx[args.block]
    manifest = manifest_path(b)
    ids = hypotheses(b["id"], manifest)
    if not ids:
        print(f"{b['id']}: в манифесте нет раздела «Гипотезы» или он пуст")
        return 1
    seen = verdicts_for(b)
    items = section_items(manifest.read_text(encoding="utf-8"), HYPOTHESIS_HEADING)
    for hid, text in zip(ids, items):
        mark = seen.get(hid, "БЕЗ ВЕРДИКТА")
        print(f"  {hid:<8} {mark:<14} {text[:90]}")
    print(f"\nзакрыто {sum(1 for h in ids if h in seen)}/{len(ids)}")
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
            problems.append(f"{bid}: нет записи в state.json — запусти `{CLI} init`")
    for bid in st["blocks"]:
        if bid not in idx:
            problems.append(f"{bid}: есть в state.json, но отсутствует в blocks.json")
        # `set-status` словарь проверял, а вписанное руками — никто.
        status = st["blocks"][bid].get("status")
        if status not in STATUSES:
            problems.append(f"{bid}: статус «{status}» вне словаря — вписан мимо set-status")

    # Манифест спрашиваем только у блока, который ДОШЁЛ до работы: манифест пишется
    # перед своим блоком, и требование его у всех сразу роняет проверку всегда —
    # тогда она перестаёт быть гейтом и её начинают игнорировать.
    for bid, b in idx.items():
        if st["blocks"].get(bid, {}).get("status", "todo") == "todo":
            continue
        manifest = manifest_path(b)
        if not manifest.exists():
            problems.append(f"{bid}: нет манифеста {manifest.relative_to(ROOT)}")
        elif len(manifest.read_text(encoding="utf-8").strip()) < 200:
            # Пустой файл проходил проверку «манифест есть».
            problems.append(f"{bid}: манифест {manifest.relative_to(ROOT)} пуст или почти пуст")

    # Блок, объявленный проверенным или закрытым, обязан предъявить отчёт
    # ВЕРИФИКАТОРА. Иначе `set-status closed` закрывает блок с одним отчётом
    # охотника, и непроверенные находки исчезают из остатка работ.
    for b in defn["blocks"]:
        stt = st["blocks"].get(b["id"], {}).get("status", "todo")
        if stt in POST_VERIFY:
            rep = REVIEW / "reports" / f"{b['id']}-{b['slug']}.verify.md"
            if not rep.exists():
                problems.append(
                    f"{b['id']}: статус {stt}, но отчёта верификатора нет — "
                    f"проверка держится на честном слове"
                )
            elif why := verify_report_problem(rep, any(f.get("block") == b["id"] for f in rows)):
                problems.append(f"{b['id']}: {why}")

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
        if s.get("status") == "running" and not s.get("started"):
            problems.append(f"{bid}: висит в running без отметки времени — когда начали, неизвестно")
        if s.get("status") == "running" and s.get("started"):
            try:
                started = dt.datetime.strptime(s["started"], "%Y-%m-%dT%H:%M:%SZ").replace(
                    tzinfo=dt.timezone.utc
                )
            except ValueError:
                problems.append(f"{bid}: отметка времени «{s['started']}» не читается")
                continue
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
        if f.get("status") == "fixed" and f.get("fix_commit") and ":" in str(f["fix_commit"]):
            # Починка в СОСЕДНЕМ репозитории: `<репозиторий>:<коммит>`. Здесь его нет и быть
            # не может, проверять нечего — но пометка обязана быть явной. Без неё такой
            # коммит выглядит как свой, и проверка честно сообщает, что его не существует;
            # так и случилось с находкой про чужое ядро.
            repo, _, sha = str(f["fix_commit"]).partition(":")
            if not repo or not sha:
                problems.append(
                    f"находка {fid}: внешняя починка пишется как `<репозиторий>:<коммит>`"
                )
        elif f.get("status") == "fixed" and f.get("fix_commit"):
            # Коммит правки обязан существовать и касаться файла находки. Две отметки
            # в соседнем проекте указывали на коммит, который названного файла не трогал
            # вовсе: правку сделали в другом модуле, а запись осталась прежней. Руками
            # такое не проверяют — и не проверяли полгода.
            touched = subprocess.run(
                ["git", "-C", str(ROOT), "show", "--name-only", "--format=", f["fix_commit"]],
                capture_output=True, text=True,
            )
            if touched.returncode != 0:
                problems.append(f"находка {fid}: коммита {f['fix_commit']} нет в репозитории")
            elif f.get("file") and not ({f["file"], *f.get("fixed_in", [])}
                                        & set(touched.stdout.splitlines())):
                problems.append(
                    f"находка {fid}: коммит {f['fix_commit']} не трогает {f['file']} — "
                    f"либо отметка не от той находки, либо чинили в другом месте: тогда "
                    f"назовите его (`{CLI} set-finding {fid} fixed --commit <sha> "
                    f"--fixed-in <путь>`)"
                )
        if f.get("status") == "fixed" and not f.get("fix_commit"):
            problems.append(f"находка {fid}: помечена fixed, но не указан коммит правки")
        if f.get("status") == "duplicate" and not f.get("dup_of"):
            problems.append(f"находка {fid}: помечена duplicate, но не указано, чего именно")
        elif f.get("status") == "duplicate" and (why := dup_problem(fid, f["dup_of"], rows)):
            problems.append(why)
        if f.get("confidence") == "rejected" and f.get("status") == "open":
            problems.append(f"находка {fid}: отвергнута верификатором, но всё ещё open")
        if f.get("status") == "rejected" and f.get("confidence") != "rejected":
            problems.append(
                f"находка {fid}: статус rejected, а уверенность {f.get('confidence')} — "
                f"реестр утверждает разом «отвергнута» и «не отвергнута»"
            )
        # Код под находкой уехал — значит либо её уже починили, либо описание устарело.
        # И то и другое требует действия, а не молчания: непереведённая находка заставляет
        # следующий проход спорить с несуществующим кодом.
        if (f.get("status") in ("open", "deferred") and not f.get("code_sha")
                and file_sha(f.get("file", ""))):
            problems.append(
                f"находка {fid}: нет отпечатка кода — изменения в {f.get('file')} под ней не "
                f"отслеживаются; `{CLI} backfill`"
            )
        if f.get("status") in ("open", "deferred") and f.get("code_sha"):
            fresh = file_sha(f.get("file", ""))
            if fresh and fresh != f["code_sha"]:
                problems.append(
                    f"находка {fid}: код в {f.get('file')} изменился с момента импорта — "
                    f"перепроверьте: либо она уже закрыта (`{CLI} set-finding {fid} fixed "
                    f"--commit <sha>`), либо описание устарело, либо дефект на месте "
                    f"(`{CLI} restamp {fid}`)"
                )
        # Номер строки, которого в файле нет, — самый дешёвый признак выдумки.
        if f.get("line") and isinstance(f["line"], int):
            n = file_lines(f.get("file", ""))
            if n is not None and f["line"] > n:
                problems.append(
                    f"находка {fid}: указана строка {f['line']}, а в {f.get('file')} их {n}"
                )
        # Отвергнутая находка остаётся в реестре ради причины отказа — без неё
        # запись бесполезна: следующее ревью найдёт то же самое и потратит время
        # заново. Условие завершения ревью требовало причину у каждой отвергнутой
        # с самого начала, а проверки на это не было, и поле оставалось пустым.
        if f.get("status") == "rejected":
            # Причина отказа пишется либо отдельным полем, либо — как велит шаблон роли —
            # прямо в заголовке находки («Отвергнуто: …»). Требовать только поле значило бы
            # ронять проверку на каждой находке, оформленной ровно по инструкции.
            claim = (f.get("claim") or "").strip()
            said = (f.get("reject_reason") or "").strip() or (
                claim if re.match(r"отвергнут|отклонен|отклонён|не подтверд", claim, re.I) else "")
            if not said:
                problems.append(
                    f"находка {fid}: отвергнута, но причина отказа не записана — "
                    f"`{CLI} set-finding {fid} rejected --reason '...'` либо строкой "
                    f"«Отвергнуто: …» в начале заголовка"
                )
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
            problems.append(f"findings.md разошёлся с findings.jsonl — запусти `{CLI} findings`")

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
        problems.append(f"{len(unassigned)} файлов не принадлежат ни одному блоку — `{CLI} coverage`")

    # Карта покрытия на диске обязана совпадать с пересчётом: иначе потребитель
    # читает вчерашнее владение и не узнаёт об этом. Ровно так она и разошлась —
    # файлы самого ревью появились после того, как карту записали.
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
                f"coverage.tsv устарел: на диске {len(on_disk)} строк, "
                f"пересчёт даёт {len(fresh)} — выполните `{CLI} coverage`"
            )

    # Гипотезы — второй знаменатель покрытия, рядом с картой файлов. Манифест без
    # гипотез даёт ревью «по общим соображениям», а гипотеза без вердикта теряется
    # в прозе отчёта: спросить «проверил ли ты вот это» потом будет некому.
    for b in defn["blocks"]:
        stt = st["blocks"].get(b["id"], {}).get("status", "todo")
        if stt in ("todo", "blocked"):
            continue
        manifest = manifest_path(b)
        ids = hypotheses(b["id"], manifest)
        if not ids:
            problems.append(
                f"{b['id']}: в манифесте нет гипотез — такой блок даёт ревью "
                f"«по общим соображениям»; раздел «Гипотезы», по пункту на гипотезу"
            )
            continue
        if stt not in POST_VERIFY:
            continue
        for role in ("hunter", "fix", "verify"):
            rp = REVIEW / "reports" / f"{b['id']}-{b['slug']}.{role}.md"
            if rp.exists():
                for h, vs in verdict_conflicts(rp.read_text(encoding="utf-8"), b["id"]).items():
                    problems.append(
                        f"{b['id']}: {rp.name} выносит гипотезе {h} разные вердикты "
                        f"({' / '.join(vs)}) — итог зависел бы от порядка строк; оставьте один"
                    )
        seen = verdicts_for(b)
        missing = [h for h in ids if h not in seen]
        if missing:
            problems.append(
                f"{b['id']}: без вердикта {len(missing)} из {len(ids)} гипотез "
                f"({', '.join(missing[:5])}{'…' if len(missing) > 5 else ''}) — "
                f"каждая закрывается словом «проверена», «не проверена» или «неприменима»"
            )

    # Блок, просмотренный на другой версии файлов, закрыт только на бумаге. Отпечаток
    # снимается при переводе в verified/closed; разойтись он может лишь одним способом —
    # файлы блока изменились после просмотра.
    for b in defn["blocks"]:
        s = st["blocks"].get(b["id"], {})
        if s.get("status") not in POST_VERIFY:
            continue
        if not s.get("reviewed_sha"):
            # Молча пропускать нельзя: тогда любая правка файлов такого блока проходит
            # незамеченной, а проверка зелёная. Так и было у всех блоков, прошедших
            # проверку до появления отпечатка.
            problems.append(
                f"{b['id']}: блок в статусе {s.get('status')} без отпечатка просмотренного — "
                f"правки его файлов не отслеживаются; `{CLI} backfill` или `{CLI} restamp {b['id']}`"
            )
            continue
        if changed_since_review(b, s["reviewed_sha"]):
            problems.append(
                f"{b['id']}: файлы блока изменились после просмотра — блок закрыт на другой "
                f"версии кода; перепройдите либо, если правки к предмету блока не относятся, "
                f"перештампуйте: `{CLI} restamp {b['id']}`"
            )
        # Контекст — предупреждение, а не отказ, как «suspect link» у doorstop: изменился не
        # предмет блока, а то, на что он опирался. Каталоги справки широкие (в первом же
        # проекте — 229 файлов и дюжина коммитов за две недели), и отказ на каждую их правку
        # краснел бы ежедневно, приучая жать `restamp` не глядя, — тогда не работает и
        # отпечаток собственных файлов.
        if b.get("ref_paths"):
            if not s.get("refs_sha"):
                warnings.append(f"{b['id']}: нет отпечатка контекста (ref_paths) — `{CLI} backfill`")
            elif s["refs_sha"] != refs_sha(b):
                warnings.append(
                    f"{b['id']}: файлы контекста (ref_paths) изменились после проверки — "
                    f"если выводы блока на них опирались, перепроверьте; иначе `{CLI} restamp {b['id']}`"
                )
        if not s.get("hypotheses_sha"):
            problems.append(
                f"{b['id']}: нет отпечатка гипотез — правка манифеста после проверки не "
                f"отслеживается; `{CLI} backfill`"
            )
        elif s["hypotheses_sha"] != hypotheses_sha(b):
            problems.append(
                f"{b['id']}: гипотезы манифеста изменились после проверки — вердикты по "
                f"номерам даны прежним вопросам; перепроверьте новые либо, если смысл не "
                f"менялся, перештампуйте: `{CLI} restamp {b['id']}`"
            )

    # Раздел про ограничения охвата обязателен: полноту доказывают перечислением
    # НЕпросмотренного, и в аудиторских отчётах это отдельная глава. «Находок нет»
    # без него неотличимо от «посмотрел по диагонали».
    for b in defn["blocks"]:
        if st["blocks"].get(b["id"], {}).get("status", "todo") not in POST_VERIFY:
            continue
        hunter = REVIEW / "reports" / f"{b['id']}-{b['slug']}.hunter.md"
        if hunter.exists():
            body = section_body(hunter.read_text(encoding="utf-8"), LIMITS_HEADING)
            if body is None:
                problems.append(
                    f"{b['id']}: в отчёте охотника нет раздела об ограничениях охвата — "
                    f"что осознанно не смотрел и почему"
                )
            elif not [ln for ln in body if ln.strip() and not LIMITS_PLACEHOLDER.search(ln)]:
                # Заголовок без текста — та же тишина, что и без заголовка: не названо ни
                # непросмотренное, ни то, что его нет.
                problems.append(
                    f"{b['id']}: раздел об ограничениях охвата в отчёте охотника пуст — "
                    f"назовите непросмотренное или прямо скажите, что его нет"
                )

    # Класс дефекта, повторившийся трижды, закрывается уздой, а не тремя правками: иначе
    # следующий проход найдёт четвёртый экземпляр. Правило переживает рефакторинг, список
    # починенных мест — нет.
    for root, items in roots_of(rows).items():
        if len(items) < ROOT_RULE_AT:
            continue
        rules = {(f.get("rule") or "").strip() for f in items} - {""}
        if rules:
            for r in sorted(rules):
                if why := rule_problem(r):
                    problems.append(f"корень «{root}»: {why}")
            continue
        ids = ", ".join(f.get("id", "?") for f in items[:4])
        problems.append(
            f"корень «{root}»: {len(items)} экземпляров ({ids}) и ни одной узды — "
            f"класс, повторившийся {ROOT_RULE_AT} раза, закрывается правилом, а не списком "
            f"правок; запишите чем: `{CLI} set-finding <ID> <статус> --rule <путь-к-узде>`"
        )

    # Дерево, отставшее от сервера, показывает починенное как сломанное. Находки такого
    # прохода описывают код, которого уже нет, а «проверено исполнением» звучит так же
    # убедительно, как на свежем дереве.
    stale = stale_tree()
    if stale:
        days, ref = stale
        problems.append(
            f"дерево старше {ref} на {days:.0f} суток — находки такого прохода могут "
            f"описывать уже починенное; `git fetch` и сверьтесь с {ref} перед тем, как их "
            f"оформлять"
        )

    # Блок, который за сеанс не прочитать, — обещание, а не блок.
    for bid, b in idx.items():
        if not b.get("paths"):
            continue
        n, lines = block_lines(b["paths"])
        limit = readable_lines()
        if lines > limit:
            problems.append(
                f"{bid}: {n} файлов, {lines} строк — за сеанс не прочитать "
                f"(порог {limit}). Разрежьте блок, иначе отчёт соврёт про охват"
            )

    if warnings:
        print("ПРЕДУПРЕЖДЕНИЯ (проверку не роняют):\n")
        for w in warnings:
            print(f"  · {w}")
        print()
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
    """Завести ревью в проекте: скелет определения, инварианты, точку входа.

    Раньше это делал отдельный установщик, копировавший в проект и сам инструмент.
    Скилл копировать некуда и незачем — он ставится стандартным способом, а в проекте
    остаётся только то, что принадлежит проекту: его блоки, его правила, его
    состояние. Существующие файлы не трогаются: команду запускают в живом проекте.
    """
    project = args.project or ROOT.name
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
        **({"cli": args.cli} if args.cli else {}),
        "gates": [],
        "note": "Статическое определение блоков. Прогресс живёт в state.json, находки — "
                "в findings.jsonl. Порядок массива = порядок исполнения.",
        "exclusions": [{"pattern": "docs/review/**", "reason": "аппарат ревью, а не его предмет"}],
        "blocks": [],
    }
    # Скилл, поставленный в проект (ради того, чтобы CI гонял ту же версию), — тоже
    # аппарат: без исключения его два десятка файлов с первого же коммита краснят карту
    # покрытия. Путь — фактический: `.claude/skills/`, `.agents/skills/`, какой поставили.
    try:
        own = SKILL_DIR.relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        own = None
    if own:
        skel["exclusions"].append({"pattern": f"{own}/**",
                                   "reason": "скилл ревью — оснастка, а не предмет ревью"})
    put(BLOCKS_FILE, json.dumps(skel, ensure_ascii=False, indent=2) + "\n")
    put(INVARIANTS_FILE, INVARIANTS_SKELETON.format(project=project))
    cli = args.cli or default_cli()
    entry = (SKILL_DIR / "assets" / "entry-point.md").read_text(encoding="utf-8")
    put(REVIEW / "README.md", entry.replace("{{PROJECT}}", project).replace("{{CLI}}", cli))
    for d in ("blocks", "reports"):
        (REVIEW / d).mkdir(parents=True, exist_ok=True)

    for rel in done:
        print(f"  + {rel}")
    for rel in skipped:
        print(f"  · {rel} — уже есть, не трогаю")
    # Байткод появляется, стоит кому-то импортировать инструмент как модуль, и уезжает
    # в коммит, если скилл лежит в проекте. В первом же проекте так и вышло. Чужой
    # .gitignore не правим — говорим.
    ignore = ROOT / ".gitignore"
    known = ignore.read_text(encoding="utf-8") if ignore.exists() else ""
    if not any(k in known for k in ("__pycache__", "*.pyc", "*.py[cod]")):
        print("\n⚠️ В .gitignore нет __pycache__/ — добавьте, иначе байткод инструмента "
              "попадёт в коммит")
    assets = SKILL_DIR / "assets"
    print(f"""
Дальше — руками, и это не формальность:

1. docs/review/invariants.md — правила ВАШЕГО проекта. Самый важный файл: он вклеивается
   каждому агенту и решает, что тот сочтёт дефектом. Образец: {assets / 'invariants.example.md'}
2. docs/review/blocks.json — `gates` (команды ворот проекта) и блоки: сквозные сначала,
   доменные потом, стендовые последними. Образец: {assets / 'blocks.example.json'}
3. Манифест первого блока — docs/review/blocks/<ID>-<слаг>.md: 10–15 гипотез про свой проект
   и критерий приёмки. Образец: {assets / 'manifest.example.md'}
4. `{cli} init`, затем `{cli} coverage` — и разбирайтесь с непокрытыми файлами, пока их не
   станет ноль. Здесь всплывает всё забытое.
5. Баннер в корневой файл инструкций ({assets / 'agent-banner.md'}), иначе новая сессия не
   узнает, что ревью идёт, и начнёт своё параллельное.""")
    return 0


def main() -> int:
    # `review.py prompt H1 --role hunter | head` is the obvious way to look
    # at a prompt before handing it to an agent; without this, python answers a
    # closed pipe with a traceback and exit code 120, which reads like the tool
    # is broken.
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)

    p = argparse.ArgumentParser(prog="review", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="создать/дополнить state.json по blocks.json").add_argument(
        "--force", action="store_true", help="перезаписать состояние с нуля"
    )
    sub.add_parser("version", help="версия набора, стоящего в этом проекте")
    c = sub.add_parser("setup", help="завести ревью в проекте: скелет blocks.json, инварианты, точка входа")
    c.add_argument("--project", default="", help="имя проекта для промптов и заготовок")
    c.add_argument("--cli", default="",
                   help="как проект зовёт инструмент, если не напрямую (например 'npm run review --'); "
                        "пишется в blocks.json и идёт во все подсказки")
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
    c.add_argument("--append", action="store_true",
                   help="добор: дописать новые находки, не трогая уже записанные и починенные")

    c = sub.add_parser("set-finding", help="перевести находку: fixed / rejected / duplicate / deferred")
    c.add_argument("finding")
    c.add_argument("status")
    c.add_argument("--commit", help="коммит правки; обязателен для fixed")
    c.add_argument("--reason", help="причина отказа; обязательна для rejected")
    c.add_argument("--dup-of", dest="dup_of", help="id находки, дублем которой она является")
    c.add_argument("--rule", help="чем закрыт класс: путь к узде, тесту или правилу линтера")
    c.add_argument("--fixed-in", dest="fixed_in", action="append",
                   help="где чинили, если не в файле находки (можно несколько раз)")

    c = sub.add_parser("hypotheses", help="гипотезы блока и их вердикты")
    c.add_argument("block")

    c = sub.add_parser("restamp", help="подтвердить просмотр правок: блока или файла под находкой")
    c.add_argument("block", help="блок (H1) или находка (H1-003)")

    sub.add_parser("backfill", help="проставить отпечатки старым блокам и находкам (с записью в журнал)")

    c = sub.add_parser("roots", help="корни находок: сколько экземпляров и чем закрыт класс")
    c.add_argument("block", nargs="?")

    sub.add_parser("findings", help="перегенерировать findings.md из findings.jsonl")
    sub.add_parser("check", help="проверить непротиворечивость состояния")

    c = sub.add_parser("log", help="дописать строку в дневник")
    c.add_argument("block")
    c.add_argument("text")

    args = p.parse_args()
    if IN_REPO is None and args.cmd != "version":
        die("не внутри git-репозитория — запускайте из каталога проекта, который ревьюируете: "
            "покрытие считается по `git ls-files`")
    return {
        "init": cmd_init, "version": cmd_version, "status": cmd_status, "next": cmd_next, "coverage": cmd_coverage,
        "prompt": cmd_prompt, "set-status": cmd_set_status, "findings": cmd_findings,
        "check": cmd_check, "log": cmd_log, "import": cmd_import,
        "set-finding": cmd_set_finding, "hypotheses": cmd_hypotheses,
        "restamp": cmd_restamp, "roots": cmd_roots, "backfill": cmd_backfill,
        "setup": cmd_setup,
    }[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
