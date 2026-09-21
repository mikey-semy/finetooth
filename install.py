#!/usr/bin/env python3
"""Установка набора в проект.

    python3 install.py /путь/к/проекту [--cli "npm run review --"]

Ставит инструмент, шаблоны промптов и точку входа, заводит скелет определения блоков и
инвариантов. Существующие файлы не трогает: повторный запуск дописывает недостающее и
говорит, что пропустил, — набор ставят в живой проект, а не в пустой каталог.

Зачем отдельный установщик, если это шесть операций копирования: при ручной установке
ошибаются на седьмой — строке `CLI` внутри инструмента, из которой собираются все его
подсказки. Поставленный без неё набор советует команды, которых в проекте нет.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parent


def kit_version() -> str:
    """Версия набора — читается из самого инструмента, чтобы не разъехаться с ним."""
    for line in (KIT / "review.py").read_text(encoding="utf-8").split("\n"):
        if line.startswith("VERSION = "):
            return line.split("=", 1)[1].strip().strip('"')
    return "неизвестна"

BLOCKS_SKELETON = {
    "review_id": "",
    "kit_version": "",
    "project": "",
    "gates": [],
    "note": "Статическое определение блоков. Прогресс живёт в state.json, находки — в findings.jsonl. Порядок массива = порядок исполнения.",
    "exclusions": [
        {"pattern": "docs/review/**", "reason": "аппарат ревью, а не его предмет"},
    ],
    "blocks": [],
}

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


def die(msg: str) -> int:
    print(f"error: {msg}", file=sys.stderr)
    return 2


def is_repo(path: Path) -> bool:
    out = subprocess.run(["git", "-C", str(path), "rev-parse", "--show-toplevel"],
                         capture_output=True, text=True)
    return out.returncode == 0


def put(src: Path, dst: Path, done: list[str], skipped: list[str]) -> None:
    if dst.exists():
        skipped.append(str(dst))
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(src, dst)
    done.append(str(dst))


def main() -> int:
    p = argparse.ArgumentParser(prog="install", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("target", help="корень проекта, в который ставим набор")
    p.add_argument("--cli", default="python3 scripts/review/review.py",
                   help="как проект зовёт инструмент; строка идёт во все подсказки "
                        "(например: 'npm run review --' или 'make review')")
    p.add_argument("--project", default="", help="имя проекта для промптов и заготовок")
    args = p.parse_args()

    root = Path(args.target).expanduser().resolve()
    if not root.is_dir():
        return die(f"{root} — не каталог")
    if not is_repo(root):
        return die(f"{root} не под git: покрытие считается по `git ls-files`, "
                   f"без репозитория набор работать не может")

    review = root / "docs" / "review"
    done: list[str] = []
    skipped: list[str] = []

    # Инструмент. CLI прописывается сразу: из неё собираются все подсказки, и поставленный
    # без неё набор советует команды, которых в проекте нет.
    tool = root / "scripts" / "review" / "review.py"
    if tool.exists():
        skipped.append(str(tool))
    else:
        tool.parent.mkdir(parents=True, exist_ok=True)
        text = (KIT / "review.py").read_text(encoding="utf-8").replace(
            'CLI = "python3 scripts/review/review.py"', f'CLI = "{args.cli}"', 1)
        tool.write_text(text, encoding="utf-8")
        tool.chmod(0o755)
        done.append(str(tool))

    for name in ("hunter", "verify", "fix"):
        put(KIT / "prompts" / f"{name}.md", review / "prompts" / f"{name}.md", done, skipped)

    put(KIT / "example" / "entry-point.md", review / "README.md", done, skipped)

    blocks = review / "blocks.json"
    if blocks.exists():
        skipped.append(str(blocks))
    else:
        skel = dict(BLOCKS_SKELETON)
        skel["review_id"] = f"{root.name}-review"
        skel["project"] = args.project or root.name
        # Версия набора едет в определение блоков: через полгода будет видно,
        # что именно стоит в проекте и стоит ли обновлять.
        skel["kit_version"] = kit_version()
        blocks.parent.mkdir(parents=True, exist_ok=True)
        blocks.write_text(json.dumps(skel, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        done.append(str(blocks))

    inv = review / "invariants.md"
    if inv.exists():
        skipped.append(str(inv))
    else:
        inv.write_text(INVARIANTS_SKELETON.format(project=args.project or root.name),
                       encoding="utf-8")
        done.append(str(inv))

    (review / "blocks").mkdir(parents=True, exist_ok=True)
    (review / "reports").mkdir(parents=True, exist_ok=True)

    for line in done:
        print(f"  + {Path(line).relative_to(root)}")
    for line in skipped:
        print(f"  · {Path(line).relative_to(root)} — уже есть, не трогаю")

    print(f"""
Дальше — руками, и это не формальность:

1. `docs/review/invariants.md` — правила ВАШЕГО проекта. Самый важный файл: он вклеивается
   каждому агенту и решает, что тот сочтёт дефектом. Образец структуры — example/invariants.example.md.
2. `docs/review/blocks.json` — заполните `gates` (команды ворот проекта) и распишите блоки:
   сквозные сначала, доменные потом, стендовые последними. Образец — example/blocks.example.json.
3. Манифест первого блока в `docs/review/blocks/<ID>-<слаг>.md`: 10–15 гипотез про свой
   проект и критерий приёмки, который нельзя выполнить, не прочитав код.
4. `{args.cli} init`, затем `{args.cli} coverage` — и разбирайтесь с непокрытыми файлами,
   пока их не станет ноль. Здесь всплывает всё забытое.
5. Баннер в корневой файл инструкций (example/agent-banner.md), иначе новая сессия не узнает,
   что ревью идёт, и начнёт своё параллельное.
""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
