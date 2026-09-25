#!/usr/bin/env python3
"""Тесты инструмента ревью.

Каждый тест заводит свежий временный репозиторий и зовёт инструмент ИЗ СКИЛЛА, с рабочим
каталогом в этом репозитории, — так, как его зовёт агент: скилл лежит отдельно от проекта.
Поведение проверяется через командную строку. Внутренности не импортируются:
инструмент переживает переезд между проектами ровно настолько, насколько устойчив его
внешний договор.

Запуск: python3 -m unittest discover -s tests   (нужен только git и стандартная библиотека)
"""

from __future__ import annotations

import ast
import collections
import datetime as dt
import json
import re
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]
SKILL = KIT / "skills" / "finetooth"
TOOL = SKILL / "scripts" / "review.py"


class Stand:
    """Временный репозиторий с установленным набором."""

    block_id = "H1"

    def __init__(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="finetooth-test-"))
        # Инструмент НЕ копируется в проект: он лежит в скилле, а скилл сам — в чужом
        # git-репозитории (этом). Так каждый тест заодно проверяет, что корень берётся
        # по рабочему каталогу, а не по месту, где лежит файл.
        self.tool = TOOL
        for d in ("docs/review/blocks", "docs/review/reports", "src"):
            (self.root / d).mkdir(parents=True, exist_ok=True)
        self.git("init", "-q", ".")
        self.git("config", "user.email", "test@example.com")
        self.git("config", "user.name", "test")

    def git(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", "-C", str(self.root), *args],
                              capture_output=True, text=True, check=False)

    def write(self, rel: str, text: str) -> None:
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    def commit(self, message: str = "wip") -> None:
        self.git("add", "-A")
        self.git("commit", "-qm", message)

    def run(self, *args: str) -> subprocess.CompletedProcess:
        env = dict(os.environ, LC_ALL="C.UTF-8")
        return subprocess.run(["python3", str(self.tool), *args], cwd=self.root,
                              capture_output=True, text=True, check=False, env=env)

    def blocks(self, *, paths: list[str], exclusions: list[dict] | None = None,
               ref_paths: list[str] | None = None, readable_lines: int | None = None,
               named_files: bool = False, proof: str | None = None, lang: str = "ru",
               fix_gate: str | None = None, extra_blocks: list[dict] | None = None) -> None:
        # Гейт «каждый файл назван в отчёте» в стенде выключен: стендовые отчёты — заглушки.
        # Тесты самого гейта включают его явно.
        extra = {"readable_lines": readable_lines} if readable_lines else {}
        extra["named_files"] = named_files
        # Стенд ведёт ревью по-русски: шаблоны ролей и заглушки отчётов в тестах русские.
        extra["lang"] = lang
        if fix_gate is not None:
            extra["fix_gate"] = fix_gate
        self.write("docs/review/blocks.json", json.dumps({
            "review_id": "test", "project": "Тестовый проект", "gates": ["npm test"], **extra,
            "exclusions": (exclusions or []) + [
                {"pattern": "docs/review", "reason": "аппарат ревью"},
                {"pattern": "scripts/review", "reason": "аппарат ревью"},
            ],
            "blocks": [{"id": self.block_id, "slug": "demo", "phase": 1, "title": "Демоблок",
                        "role": "demo", "goal": "проверить оснастку",
                        **({"proof": proof} if proof else {}),
                        "paths": paths, "ref_paths": ref_paths or []}] + (extra_blocks or []),
        }, ensure_ascii=False, indent=2), )

    def manifest(self, hypotheses: int = 2) -> None:
        # Манифест намеренно не заглушка: проверка состояния ловит куцый файл, потому что
        # «манифест есть» и «манифест что-то требует» — разные вещи.
        items = "\n".join(
            f"{i}. Гипотеза номер {i}: предикат в этом месте расходится с каноном, "
            f"и расхождение меняет ответ на граничных значениях."
            for i in range(1, hypotheses + 1))
        self.write("docs/review/blocks/H1-demo.md",
                   f"# H1 — Демоблок\n\n## Зачем\n\nПроверить, что оснастка ведёт себя так, "
                   f"как обещает: гейты краснеют на сломанном состоянии и молчат на целом.\n\n"
                   f"## Что считается находкой\n\nРасхождение поведения с тем, что обещает "
                   f"документация модуля. Стилистика находкой не считается.\n\n"
                   f"## Гипотезы\n{items}\n\n## Критерий приёмки\n\n"
                   f"Таблица «вход → ожидание → факт» по каждой гипотезе.\n")

    def reports(self, hunter: str = "", verify: str = "") -> None:
        if hunter:
            self.write("docs/review/reports/H1-demo.hunter.md", hunter)
        if verify:
            self.write("docs/review/reports/H1-demo.verify.md", verify)

    def cleanup(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)


FULL_HUNTER = """# отчёт охотника

## Гипотезы
- H1.1 — проверена: вызвал функцию на матрице значений.
- H1.2 — не проверена: стенд не поднимается.

## Ограничения охвата
Живым запросом не проверял ничего.
"""

FULL_VERIFY = """# отчёт проверяющего

## Вердикты по находкам охотника
Находок нет.

## Состояние охвата блока
Охват полный: оба файла прочитаны, гипотезы прогнаны.
"""


class ReviewToolTest(unittest.TestCase):
    def setUp(self) -> None:
        self.s = Stand()
        self.addCleanup(self.s.cleanup)

    # ------------------------------------------------------------------ покрытие

    def test_пустой_список_путей_не_означает_весь_репозиторий(self):
        """Блок без файлов (стендовый) не может засчитать себе покрытие."""
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=[])
        self.s.manifest()
        self.s.commit()
        self.s.run("init")
        out = self.s.run("coverage")
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn("src/one.ts", out.stdout)

    def test_непокрытый_файл_роняет_карту(self):
        self.s.write("src/one.ts", "a\n")
        self.s.write("src/forgotten.ts", "b\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest()
        self.s.commit()
        self.s.run("init")
        out = self.s.run("coverage")
        self.assertEqual(out.returncode, 1)
        self.assertIn("forgotten", out.stdout)
        self.assertIn("What to do", out.stdout, "отказ обязан говорить, что делать")

    def test_устаревшая_карта_покрытия_роняет_проверку(self):
        """Карта сверяется содержимым, а не именем коммита в шапке: имя ничего не доказывает."""
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src"])
        self.s.manifest()
        self.s.commit()
        self.s.run("init")
        self.assertEqual(self.s.run("coverage").returncode, 0)
        self.assertNotIn("is stale", self.s.run("check").stdout)

        self.s.write("src/two.ts", "b\n")
        self.s.commit("новый файл после карты")
        self.assertIn("coverage.tsv is stale", self.s.run("check").stdout)
        self.s.run("coverage")
        self.assertNotIn("coverage.tsv is stale", self.s.run("check").stdout)

    def test_подмодуль_не_файл_а_симлинк_файл_без_двойного_счёта(self):
        """Подмодуль не открыть; симлинк — правка, которую надо видеть, но считать один раз."""
        self.s.write("src/real.ts", "одна\nдве\nтри\n")
        (self.s.root / "src" / "link.ts").symlink_to("real.ts")
        sub = self.s.root / "vendor"
        subprocess.run(["git", "init", "-q", str(sub)], check=True)
        for k, v in (("user.email", "t@e"), ("user.name", "t")):
            subprocess.run(["git", "-C", str(sub), "config", k, v], check=True)
        (sub / "f.txt").write_text("x\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(sub), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(sub), "commit", "-qm", "sub"], check=True)
        subprocess.run(["git", "-C", str(self.s.root), "-c", "protocol.file.allow=always",
                        "submodule", "add", "-q", "./vendor", "lib"],
                       check=False, capture_output=True)

        self.s.blocks(paths=["src"])
        self.s.manifest(hypotheses=1)
        self.s.commit()
        self.s.run("init")
        out = self.s.run("coverage")
        self.assertNotIn("lib", out.stdout.replace("библиотек", ""), "подмодуль — не файл")
        cov = (self.s.root / "docs/review/coverage.tsv").read_text(encoding="utf-8")
        self.assertIn("src/link.ts\tH1", cov, "симлинк принадлежит блоку: его можно перенаправить")

        # счётчик не падает и не считает содержимое цели дважды: у ссылки одна строка — её текст
        prompt = self.s.run("prompt", "H1", "--role", "hunter")
        self.assertEqual(prompt.returncode, 0, prompt.stderr)
        self.assertIn("Строк: 4", prompt.stdout, "три строки файла и одна строка ссылки, а не шесть")

    def test_перенаправленный_симлинк_меняет_отпечаток(self):
        """Цель с тем же содержимым: хеш по ссылке прошёл бы мимо."""
        self.s.write("src/a.ts", "одно и то же\n")
        self.s.write("src/b.ts", "одно и то же\n")
        (self.s.root / "src" / "link.ts").symlink_to("a.ts")
        self.s.blocks(paths=["src"])
        self.s.manifest(hypotheses=1)
        self.s.reports(hunter="# охотник\n## Гипотезы\n- H1.1 — проверена: да\n"
                              "## Ограничения охвата\nнет\n", verify=FULL_VERIFY)
        self.s.commit()
        self.s.run("init")
        self.s.run("coverage")
        self.s.run("set-status", "H1", "verified")
        self.assertEqual(self.s.run("check").returncode, 0, self.s.run("check").stdout)
        (self.s.root / "src" / "link.ts").unlink()
        (self.s.root / "src" / "link.ts").symlink_to("b.ts")
        self.s.commit("перенаправили ссылку")
        self.assertIn("changed after the review", self.s.run("check").stdout)

    def test_файл_удалённый_с_диска_но_живой_в_индексе_не_роняет_счёт(self):
        self.s.write("src/one.ts", "одна\nдве\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=1)
        self.s.commit()
        (self.s.root / "src" / "one.ts").unlink()
        self.s.run("init")
        out = self.s.run("prompt", "H1", "--role", "hunter")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("Строк: 2", out.stdout)

    # -------------------------------------------------------------------- промпт

    def test_исключённые_файлы_не_попадают_в_промпт(self):
        """Карта и порог вычитают исключения — промпт обязан вычитать их тоже."""
        self.s.write("src/one.ts", "a\n")
        self.s.write("src/generated.ts", "x\n" * 100)
        self.s.blocks(paths=["src/one.ts", "src/generated.ts"],
                      exclusions=[{"pattern": "src/generated.ts", "reason": "кодоген"}])
        self.s.manifest()
        self.s.commit()
        self.s.run("init")
        out = self.s.run("prompt", "H1", "--role", "hunter")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("src/one.ts", out.stdout)
        self.assertNotIn("src/generated.ts", out.stdout)

    def test_имя_проекта_и_ворота_подставляются(self):
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest()
        self.s.commit()
        self.s.run("init")
        out = self.s.run("prompt", "H1", "--role", "fix")
        self.assertIn("Тестовый проект", out.stdout)
        self.assertIn("npm test", out.stdout)
        self.assertNotIn("{{", out.stdout, "остались незакрытые подстановки")

    def test_промпт_называет_объём_работы(self):
        self.s.write("src/one.ts", "строка\n" * 100)
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=1)
        self.s.commit()
        self.s.run("init")
        out = self.s.run("prompt", "H1", "--role", "hunter")
        self.assertIn("Строк: 100", out.stdout)
        self.assertIn("токенов", out.stdout, "порядок величины должен стоять в задании")
        self.assertNotIn("больше, чем прочитывается", out.stdout)

    def test_слишком_большой_блок_показывает_границу_бюджета_в_промпте(self):
        """Невлезшее называется поимённо прямо в задании, а не остаётся догадкой агента."""
        self.s.write("src/huge.ts", "строка\n" * 7000)
        self.s.write("src/small.ts", "строка\n" * 10)
        self.s.blocks(paths=["src/huge.ts", "src/small.ts"])
        self.s.manifest(hypotheses=1)
        self.s.commit()
        self.s.run("init")
        out = self.s.run("prompt", "H1", "--role", "hunter")
        self.assertIn("больше, чем прочитывается за сеанс", out.stdout)
        self.assertIn("src/huge.ts", out.stdout)
        self.assertIn("▲", out.stdout, "граница бюджета должна быть видна поимённо")
        self.assertIn("ограничени", out.stdout.lower(),
                      "промпт обязан сказать, куда записать непрочитанное")

    # ------------------------------------------------------------------ гипотезы

    def test_гипотеза_без_вердикта_роняет_проверку(self):
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=2)
        self.s.reports(hunter="# отчёт\n\n## Ограничения охвата\nнет\n", verify=FULL_VERIFY)
        self.s.commit()
        self.s.run("init")
        self.s.run("coverage")
        self.s.run("set-status", "H1", "verified")
        out = self.s.run("check")
        self.assertEqual(out.returncode, 1)
        self.assertIn("without a verdict", out.stdout)

    def test_манифест_без_гипотез_роняет_проверку(self):
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.write("docs/review/blocks/H1-demo.md", "# H1\n\n## Критерий приёмки\nТаблица.\n")
        self.s.commit()
        self.s.run("init")
        self.s.run("coverage")
        self.s.run("set-status", "H1", "running")
        out = self.s.run("check")
        self.assertIn("has no hypotheses", out.stdout)

    def test_отчёт_без_раздела_про_непросмотренное_роняет_проверку(self):
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=1)
        self.s.reports(hunter="# отчёт\n\n## Гипотезы\n- H1.1 — проверена: да\n",
                       verify=FULL_VERIFY)
        self.s.commit()
        self.s.run("init")
        self.s.run("coverage")
        self.s.run("set-status", "H1", "verified")
        out = self.s.run("check")
        self.assertIn("coverage limits", out.stdout.lower())

    def test_пустой_раздел_ограничений_роняет_проверку(self):
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=1)
        self.s.commit()
        self.s.run("init")
        self.s.run("coverage")
        self.s.run("set-status", "H1", "verified")
        for limits in ("## Ограничения охвата\n\n",
                       "## Ограничения охвата\n**Обязательный раздел, даже если он короткий.**\n"):
            self.s.reports(hunter="# охотник\n## Гипотезы\n- H1.1 — проверена: да\n" + limits
                                  + "## Прочее\nтекст другого раздела\n", verify=FULL_VERIFY)
            self.assertIn("'Coverage limits' section of the hunter report is empty",
                          self.s.run("check").stdout, limits)
        self.s.reports(hunter="# охотник\n## Гипотезы\n- H1.1 — проверена: да\n"
                              "## Ограничения охвата\n### Не дошёл\nдо почтовых шаблонов\n",
                       verify=FULL_VERIFY)
        self.assertNotIn("Coverage limits", self.s.run("check").stdout)

    def test_отчёт_проверяющего_из_одних_цитат_не_проводит_блок(self):
        """Файл, полный цитат, — тот же пустой файл: образец из шаблона, перенесённый в
        ограду, ничего не проверяет и ни о чём не сообщает, а блок оставался проверенным."""
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=1)
        self.s.write("docs/review/reports/H1-findings.jsonl", json.dumps({
            "block": "H1", "severity": "low", "confidence": "confirmed", "status": "open",
            "file": "src/one.ts", "claim": "тут дефект",
            "scenario": "человек делает X — получает Y"}, ensure_ascii=False) + "\n")
        self.s.reports(hunter="# охотник\n## Гипотезы\n- H1.1 — проверена: да\n"
                              "## Ограничения охвата\nнет\n", verify="")
        quoted = ("# проверяющий\n\nШаблон просит написать так:\n\n"
                  "```markdown\n- H1-001 — подтверждена: воспроизвёл.\n"
                  "Охват полный, непрочитанного нет.\n```\n")
        self.s.write("docs/review/reports/H1-demo.verify.md", quoted)
        self.s.commit()
        self.s.run("init")
        self.s.run("coverage")
        self.s.run("import", "H1")
        self.s.run("findings")
        self.s.run("set-status", "H1", "verified")
        out = self.s.run("check")
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn("no verdict on any finding", out.stdout)

    def test_отчёт_проверяющего_с_образцом_рядом_со_словами_проходит(self):
        """Обратная сторона: ограда с образцом рядом с настоящими словами отчёта — это
        по-прежнему отчёт, и ворота его не трогают."""
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=1)
        self.s.reports(hunter="# охотник\n## Гипотезы\n- H1.1 — проверена: да\n"
                              "## Ограничения охвата\nнет\n",
                       verify="# проверяющий\n\nШаблон просит написать так:\n\n"
                              "```markdown\n- H1-001 — подтверждена: воспроизвёл.\n```\n\n"
                              "Находок нет, проверять нечего.\nОхват блока полный, "
                              "непрочитанного не осталось.\n")
        self.s.commit()
        self.s.run("init")
        self.s.run("coverage")
        self.s.run("set-status", "H1", "verified")
        out = self.s.run("check")
        self.assertEqual(out.returncode, 0, out.stdout)
        self.assertNotIn("verifier report", out.stdout)

    def test_раздел_ограничений_из_одной_цитаты_роняет_проверку(self):
        """Раздел, в котором только образец из шаблона внутри ограды, — то же молчание,
        что и раздел без текста. И обратная сторона: образец РЯДОМ со сказанным своими
        словами непросмотренным ничего не ломает."""
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=1)
        self.s.commit()
        self.s.run("init")
        self.s.run("coverage")
        self.s.run("set-status", "H1", "verified")
        for limits, red in (
                ("## Ограничения охвата\n\n```markdown\n- src/legacy.ts — не читал\n```\n", True),
                ("## Ограничения охвата\n\nдо почтовых шаблонов не дошёл\n\n"
                 "```markdown\n- src/legacy.ts — не читал\n```\n", False)):
            with self.subTest(красное=red):
                self.s.reports(hunter="# охотник\n## Гипотезы\n- H1.1 — проверена: да\n"
                                      + limits, verify=FULL_VERIFY)
                out = self.s.run("check").stdout
                said = "'Coverage limits' section of the hunter report is empty"
                self.assertEqual(said in out, red, out)

    def test_живой_язык_отчёта_понимается(self):
        """«Гипотеза 2 не подтвердилась» и таблица «| 1 | … | опровергнута |» — тоже вердикты."""
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=3)
        self.s.reports(hunter=(
            "# отчёт\n\n## Гипотезы\n\n| # | гипотеза | итог |\n|---|---|---|\n"
            "| 1 | первая | **Проверена — опровергнута.** Узда есть в другом месте |\n\n"
            "Гипотеза 2 не подтвердилась: разбор доверен конструктору URL.\n"
            "- H1.3 — неприменима: этого пути в коде нет.\n\n"
            "## Ограничения охвата\nстенда нет\n"), verify=FULL_VERIFY)
        self.s.commit()
        self.s.run("init")
        self.s.run("coverage")
        self.s.run("set-status", "H1", "verified")
        self.assertEqual(self.s.run("check").returncode, 0, self.s.run("check").stdout)
        self.assertIn("closed 3/3", self.s.run("hypotheses", "H1").stdout)

    def test_оговорка_в_строке_не_переворачивает_вердикт(self):
        """«Проверена по коду … живым запросом не проверял» — проверена, с оговоркой."""
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=2)
        # Таблица без шапки стоит под «Гипотезами» — там номер строки и есть номер
        # гипотезы. Вне этого раздела такая таблица вердиктом не считается.
        self.s.reports(hunter="# охотник\n## Гипотезы\n"
                              "| 1 | пути | **Проверена по коду**, живым запросом не проверял |\n"
                              "| 2 | ник | не проверена: стенда нет, хотя код проверена-подобен |\n"
                              "## Ограничения охвата\nнет\n", verify=FULL_VERIFY)
        self.s.commit()
        self.s.run("init")
        out = self.s.run("hypotheses", "H1").stdout
        self.assertRegex(out, r"H1\.1\s+checked")
        self.assertRegex(out, r"H1\.2\s+not checked")

    def test_идентификатор_блока_с_буквенным_суффиксом(self):
        """У больше чем половины блоков реального ревью имя вида V1d — их вердикты терялись."""
        self.s.block_id = "V1d"
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=2)
        self.s.write("docs/review/blocks/V1d-demo.md",
                     (self.s.root / "docs/review/blocks/H1-demo.md").read_text(encoding="utf-8"))
        (self.s.root / "docs/review/blocks/H1-demo.md").unlink()
        self.s.reports(hunter="# охотник\n## Гипотезы\n- V1d.1 — проверена: вызвал на матрице\n"
                              "- V1d.2 — неприменима: этого пути нет\n"
                              "## Ограничения охвата\nстенда нет\n", verify=FULL_VERIFY)
        for role in ("hunter", "verify"):
            src = self.s.root / f"docs/review/reports/H1-demo.{role}.md"
            if src.exists():
                src.rename(self.s.root / f"docs/review/reports/V1d-demo.{role}.md")
        self.s.commit()
        self.s.run("init")
        self.s.run("coverage")
        self.s.run("set-status", "V1d", "verified")
        out = self.s.run("hypotheses", "V1d")
        self.assertIn("closed 2/2", out.stdout)
        self.assertEqual(self.s.run("check").returncode, 0, self.s.run("check").stdout)

    def test_проверки_не_выключаются_переводом_в_следующий_статус(self):
        """`set-status triaged` не должен зеленить гейт, ничего не добавив."""
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=2)
        self.s.reports(hunter="# охотник\n## Ограничения охвата\nнет\n", verify=FULL_VERIFY)
        self.s.commit()
        self.s.run("init")
        self.s.run("coverage")
        self.s.run("set-status", "H1", "verified")
        self.assertIn("without a verdict", self.s.run("check").stdout)
        self.s.run("set-status", "H1", "triaged")
        self.assertIn("without a verdict", self.s.run("check").stdout,
                      "смена статуса не добавила вердиктов — гейт обязан остаться красным")

    def test_причина_отказа_принимается_там_где_её_велит_писать_шаблон(self):
        """Шаблон роли кладёт причину в заголовок — требовать иное поле значит ронять всё."""
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=1)
        self.s.write("docs/review/reports/H1-findings.jsonl", json.dumps({
            "block": "H1", "severity": "low", "confidence": "rejected", "status": "rejected",
            "file": "src/one.ts",
            "claim": "Отвергнуто: поведение корректно, проверено вызовом на матрице",
            "scenario": "проверено"}, ensure_ascii=False) + "\n")
        self.s.commit()
        self.s.run("init")
        self.s.run("import", "H1")
        self.s.run("findings")
        self.assertNotIn("reject reason is not recorded", self.s.run("check").stdout)

    def test_вердикт_проверяющего_перебивает_охотника(self):
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=1)
        self.s.reports(hunter="# охотник\n## Гипотезы\n- H1.1 — проверена: да\n"
                              "## Ограничения охвата\nнет\n",
                       verify="# проверяющий\n- H1.1 — не проверена: доказательства нет\n")
        self.s.commit()
        self.s.run("init")
        out = self.s.run("hypotheses", "H1")
        self.assertIn("not checked", out.stdout)

    def test_блок_просмотренный_на_другой_версии_файлов_роняет_проверку(self):
        """Статус «пройден» держится вечно, а файлы меняются — отпечаток это ловит."""
        self.s.write("src/one.ts", "было\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=1)
        self.s.reports(hunter="# охотник\n## Гипотезы\n- H1.1 — проверена: да\n"
                              "## Ограничения охвата\nнет\n", verify=FULL_VERIFY)
        self.s.commit()
        self.s.run("init")
        self.s.run("coverage")
        self.s.run("set-status", "H1", "verified")
        self.assertEqual(self.s.run("check").returncode, 0, self.s.run("check").stdout)

        self.s.write("src/one.ts", "переписали целиком\n")
        self.s.commit("правка после ревью")
        self.s.run("coverage")
        out = self.s.run("check")
        self.assertIn("changed after the review", out.stdout)
        self.assertIn("restamp", out.stdout, "отказ обязан говорить, что делать")

        self.assertEqual(self.s.run("restamp", "H1").returncode, 0)
        self.assertNotIn("changed after the review", self.s.run("check").stdout)

    def test_промежуточный_статус_не_перештамповывает_блок(self):
        """`set-status triaged` — не подтверждение просмотра; перештамповка только через restamp."""
        self.s.write("src/one.ts", "было\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=1)
        self.s.reports(hunter="# охотник\n## Гипотезы\n- H1.1 — проверена: да\n"
                              "## Ограничения охвата\nнет\n", verify=FULL_VERIFY)
        self.s.commit()
        self.s.run("init")
        self.s.run("coverage")
        self.s.run("set-status", "H1", "verified")
        self.s.write("src/one.ts", "переписали целиком\n")
        self.s.commit("правка после ревью")
        self.s.run("coverage")
        self.s.run("set-status", "H1", "triaged")
        self.assertIn("changed after the review", self.s.run("check").stdout,
                      "смена статуса не смотрела код — отпечаток обязан остаться старым")

    def test_ограничения_охвата_требуются_и_после_проверки(self):
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=1)
        self.s.reports(hunter="# охотник\n## Гипотезы\n- H1.1 — проверена: да\n",
                       verify=FULL_VERIFY)
        self.s.commit()
        self.s.run("init")
        self.s.run("coverage")
        for status in ("verified", "triaged", "fixing", "closed"):
            self.s.run("set-status", "H1", status)
            self.assertIn("has no 'Coverage limits' section", self.s.run("check").stdout, status)

    def test_старые_записи_без_отпечатков_ловятся_и_дописываются(self):
        """Блок и находка из времён до отпечатков не должны молча выпадать из проверки."""
        self.s.write("src/one.ts", "было\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=1)
        self.s.reports(hunter="# охотник\n## Гипотезы\n- H1.1 — проверена: да\n"
                              "## Ограничения охвата\nнет\n", verify=FULL_VERIFY)
        self.s.write("docs/review/reports/H1-findings.jsonl", json.dumps({
            "block": "H1", "severity": "high", "confidence": "confirmed", "status": "open",
            "file": "src/one.ts", "claim": "тут дефект",
            "scenario": "человек делает X — получает Y"}, ensure_ascii=False) + "\n")
        self.s.commit()
        self.s.run("init")
        self.s.run("coverage")
        self.s.run("import", "H1")
        self.s.run("findings")
        self.s.run("set-status", "H1", "verified")
        # Состояние, каким его оставила версия набора без отпечатков.
        st_path = self.s.root / "docs/review/state.json"
        st = json.loads(st_path.read_text(encoding="utf-8"))
        st["blocks"]["H1"].pop("reviewed_sha")
        st_path.write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")
        f_path = self.s.root / "docs/review/findings.jsonl"
        rows = [json.loads(x) for x in f_path.read_text(encoding="utf-8").splitlines() if x]
        for r in rows:
            r.pop("code_sha")
        f_path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                          encoding="utf-8")

        out = self.s.run("check").stdout
        self.assertIn("without a fingerprint of what was reviewed", out)
        self.assertIn("no code fingerprint", out)

        self.assertEqual(self.s.run("backfill").returncode, 0)
        out = self.s.run("check").stdout
        self.assertNotIn("without a fingerprint", out)
        self.assertNotIn("fingerprint", out)
        journal = (self.s.root / "docs/review/journal.md").read_text(encoding="utf-8")
        self.assertIn("задним числом", journal, "проставление обязано остаться в журнале")

        self.s.write("src/one.ts", "стало\n")
        self.s.commit("правка после проставления")
        self.s.run("coverage")
        out = self.s.run("check").stdout
        self.assertIn("changed after the review", out)
        self.assertIn("changed since import", out)

    def test_правка_гипотез_после_проверки_роняет_проверку(self):
        """Вердикт по номеру, данный старому вопросу, не должен засчитываться новому."""
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=2)
        self.s.reports(hunter=FULL_HUNTER.replace("не проверена: стенд не поднимается",
                                                  "проверена: да"),
                       verify=FULL_VERIFY)
        self.s.commit()
        self.s.run("init")
        self.s.run("coverage")
        self.s.run("set-status", "H1", "verified")
        self.assertEqual(self.s.run("check").returncode, 0, self.s.run("check").stdout)

        m = self.s.root / "docs/review/blocks/H1-demo.md"
        m.write_text(m.read_text(encoding="utf-8").replace(
            "2. Гипотеза номер 2:", "2. Совсем другой вопрос:"), encoding="utf-8")
        out = self.s.run("check").stdout
        self.assertIn("manifest hypotheses changed", out)
        self.assertEqual(self.s.run("restamp", "H1").returncode, 0)
        self.assertNotIn("manifest hypotheses changed", self.s.run("check").stdout)

    def test_блок_кода_в_гипотезах_не_обрывает_раздел(self):
        """`# комментарий` в примере кода — не заголовок, `- x` в нём — не гипотеза."""
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=2)
        m = self.s.root / "docs/review/blocks/H1-demo.md"
        m.write_text(m.read_text(encoding="utf-8").replace(
            "на граничных значениях.\n2.",
            "на граничных значениях.\n   ```sh\n# так воспроизводится\n- не пункт\n   ```\n2.", 1),
            encoding="utf-8")
        self.s.commit()
        self.s.run("init")
        self.assertIn("closed 0/2", self.s.run("hypotheses", "H1").stdout)

    def test_правка_продолжения_гипотезы_ловится(self):
        """Сценарий и ожидание пишутся под гипотезой с отступом — это тоже её текст."""
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=1)
        m = self.s.root / "docs/review/blocks/H1-demo.md"
        m.write_text(m.read_text(encoding="utf-8").replace(
            "на граничных значениях.\n",
            "на граничных значениях.\n   Ожидание: пустая строка отвергается.\n", 1),
            encoding="utf-8")
        self.s.reports(hunter="# охотник\n## Гипотезы\n- H1.1 — проверена: да\n"
                              "## Ограничения охвата\nнет\n", verify=FULL_VERIFY)
        self.s.commit()
        self.s.run("init")
        self.s.run("coverage")
        self.s.run("set-status", "H1", "verified")
        self.assertEqual(self.s.run("check").returncode, 0, self.s.run("check").stdout)
        m.write_text(m.read_text(encoding="utf-8").replace(
            "пустая строка отвергается", "пустая строка принимается"), encoding="utf-8")
        self.assertIn("manifest hypotheses changed", self.s.run("check").stdout)

    def test_подпункт_гипотезы_не_становится_гипотезой(self):
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=2)
        m = self.s.root / "docs/review/blocks/H1-demo.md"
        m.write_text(m.read_text(encoding="utf-8").replace(
            "на граничных значениях.\n2.",
            "на граничных значениях.\n   - подпункт: пустая строка\n   - [ ] ноль\n2.", 1),
            encoding="utf-8")
        self.s.commit()
        self.s.run("init")
        out = self.s.run("hypotheses", "H1")
        self.assertIn("closed 0/2", out.stdout, out.stdout)

    def test_пустой_отчёт_проверяющего_не_проводит_блок(self):
        """Файл есть — проверки нет: существование `*.verify.md` ничего не доказывало."""
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=1)
        self.s.write("docs/review/reports/H1-findings.jsonl", json.dumps({
            "block": "H1", "severity": "high", "confidence": "confirmed", "status": "open",
            "file": "src/one.ts", "claim": "тут дефект",
            "scenario": "человек делает X — получает Y"}, ensure_ascii=False) + "\n")
        self.s.reports(hunter="# охотник\n## Гипотезы\n- H1.1 — проверена: да\n"
                              "## Ограничения охвата\nнет\n", verify="")
        self.s.write("docs/review/reports/H1-demo.verify.md", "")
        self.s.commit()
        self.s.run("init")
        self.s.run("coverage")
        self.s.run("import", "H1")
        self.s.run("findings")
        self.s.run("set-status", "H1", "verified")
        self.assertIn("is empty — there is a file, there is no verification", self.s.run("check").stdout)

        self.s.write("docs/review/reports/H1-demo.verify.md",
                     "# проверяющий\n## Вердикты\n## Охват\n")
        self.assertIn("is empty — there is a file, there is no verification", self.s.run("check").stdout,
                      "одни заголовки — тоже пустой отчёт")

        self.s.write("docs/review/reports/H1-demo.verify.md",
                     "# проверяющий\nПосмотрел, всё хорошо, охват полный.\n")
        self.assertIn("no verdict on any finding", self.s.run("check").stdout)

        self.s.write("docs/review/reports/H1-demo.verify.md",
                     "# проверяющий\n| H1-001 | confirmed | прогнал тест, падает |\n")
        self.assertIn("no coverage verdict", self.s.run("check").stdout,
                      "вердикты по находкам не говорят, что осталось непросмотренным")

        self.s.write("docs/review/reports/H1-demo.verify.md",
                     "# проверяющий\n| H1-001 | confirmed | прогнал тест, падает |\n"
                     "## Состояние охвата\nПолный.\n")
        self.assertNotIn("verifier report", self.s.run("check").stdout)

    def test_без_находок_проверяющий_говорит_об_охвате(self):
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=1)
        self.s.reports(hunter="# охотник\n## Гипотезы\n- H1.1 — проверена: да\n"
                              "## Ограничения охвата\nнет\n",
                       verify="# проверяющий\nВсё посмотрел, претензий нет.\n")
        self.s.commit()
        self.s.run("init")
        self.s.run("coverage")
        self.s.run("set-status", "H1", "verified")
        self.assertIn("no coverage verdict", self.s.run("check").stdout)
        self.s.reports(verify=FULL_VERIFY)
        self.assertEqual(self.s.run("check").returncode, 0, self.s.run("check").stdout)

    def test_противоречивые_вердикты_в_одном_отчёте_роняют_проверку(self):
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=1)
        self.s.reports(hunter="# охотник\n## Гипотезы\n- H1.1 — проверена: да\n"
                              "## Итог\n| # | гипотеза | итог |\n|---|---|---|\n"
                              "| 1 | предикат | не проверена |\n"
                              "## Ограничения охвата\nнет\n", verify=FULL_VERIFY)
        self.s.commit()
        self.s.run("init")
        self.s.run("coverage")
        self.s.run("set-status", "H1", "verified")
        out = self.s.run("check").stdout
        self.assertIn("different verdicts", out)
        self.assertIn("H1.1", out)

    def test_нумерованная_таблица_приёмки_не_вердикт_гипотезы(self):
        """Живой отчёт: таблица «onConflict → ограничение» с номерами строк 4 и 5 считалась
        вердиктами гипотез 4 и 5, и check требовал «оставить один»."""
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=1)
        self.s.reports(hunter="# охотник\n## Гипотезы\n- H1.1 — проверена: да\n"
                              "## Таблица 1 — onConflict → ограничение\n"
                              "| # | место | ограничение | итог |\n|---|---|---|---|\n"
                              "| 1 | `a.ts:3` | `uq_a` | n/a |\n"
                              "## Ограничения охвата\nнет\n", verify=FULL_VERIFY)
        self.s.commit()
        self.s.run("init")
        self.s.run("coverage")
        self.s.run("set-status", "H1", "verified")
        out = self.s.run("check").stdout
        self.assertNotIn("different verdicts", out)
        hyp = self.s.run("hypotheses", "H1").stdout
        self.assertIn("checked", hyp)
        self.assertNotIn("not applicable", hyp)

    def test_n_a_внутри_пути_не_вердикт(self):
        """`curation/adapter.ts` содержит `n/a` — гипотеза, названная проверенной, становилась
        «неприменимой»."""
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=1)
        self.s.reports(hunter="# охотник\n## Гипотезы\n"
                              "- H1.1 (`features/curation/adapter.ts`) — проверена: да\n"
                              "## Ограничения охвата\nнет\n", verify=FULL_VERIFY)
        self.s.commit()
        self.s.run("init")
        self.s.run("coverage")
        self.s.run("set-status", "H1", "verified")
        hyp = self.s.run("hypotheses", "H1").stdout
        self.assertIn("checked", hyp)
        self.assertNotIn("not applicable", hyp)

    # ------------------------------------------------------------- гейт починки

    def _two_blocks_with_open_high(self, fix_gate: str | None = None) -> None:
        self.s.write("src/one.ts", "a\n")
        self.s.write("src/two.ts", "b\n")
        self.s.blocks(paths=["src/one.ts"], fix_gate=fix_gate, extra_blocks=[{
            "id": "H2", "slug": "two", "phase": 1, "title": "Второй блок", "role": "demo",
            "goal": "проверить гейт", "paths": ["src/two.ts"], "ref_paths": []}])
        self.s.manifest(hypotheses=1)
        self.s.write("docs/review/reports/H1-findings.jsonl", json.dumps({
            "block": "H1", "severity": "high", "confidence": "confirmed", "status": "open",
            "file": "src/one.ts", "claim": "серьёзный дефект",
            "scenario": "человек делает X — получает Y"}, ensure_ascii=False) + "\n")
        self.s.commit()
        self.s.run("init")
        self.s.run("import", "H1")

    def test_гейт_починки_не_пускает_следующий_блок_при_открытой_серьёзной_находке(self):
        """Метод находит быстрее, чем проект чинит: следующий блок не стартует поверх
        незакрытых high — иначе реестр через месяц описывает код, которого нет."""
        self._two_blocks_with_open_high()
        out = self.s.run("set-status", "H2", "running")
        self.assertNotEqual(out.returncode, 0)
        self.assertIn("fix gate", out.stdout + out.stderr)
        self.assertIn("H1-001", out.stdout + out.stderr)
        # тот же блок, где находка, гейтом не держится: в него возвращаются, чтобы чинить
        self.assertEqual(self.s.run("set-status", "H1", "running").returncode, 0)

    def test_гейт_починки_открывается_отложенной_с_причиной_и_выключается_none(self):
        self._two_blocks_with_open_high()
        self.assertEqual(
            self.s.run("set-finding", "H1-001", "deferred", "--reason", "чиним в следующем спринте").returncode, 0)
        self.assertEqual(self.s.run("set-status", "H2", "running").returncode, 0)

    def test_гейт_none_выключает_проверку(self):
        self._two_blocks_with_open_high(fix_gate="none")
        self.assertEqual(self.s.run("set-status", "H2", "running").returncode, 0)

    def test_статус_показывает_долг_починки(self):
        self._two_blocks_with_open_high()
        out = self.s.run("status").stdout
        self.assertRegex(out, r"fix debt \(gate: high and above\): 1 open in 1 block\(s\) — H1")

    def test_check_предупреждает_о_находке_старше_недели(self):
        self._two_blocks_with_open_high()
        reg = Path(self.s.root, "docs/review/findings.jsonl")
        rows = [json.loads(l) for l in reg.read_text(encoding="utf-8").splitlines() if l.strip()]
        rows[0]["imported_at"] = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=10)).isoformat()
        reg.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
        self.s.run("findings")
        out = self.s.run("check").stdout
        self.assertIn("older than 7 days", out)
        self.assertIn("H1-001 (10d)", out)

    # ------------------------------------------------------------- карта стыков

    def _coupled_history(self) -> None:
        """Два блока; a.ts (H1) и b.ts (H2) меняются вместе трижды; c.ts и d.ts — вместе
        только в трёх массовых коммитах; h.ts связан с шестью блоками (общий узел)."""
        names = ["a", "b", "c", "d", "h"] + [f"x{i}" for i in range(6)]
        for n in names:
            self.s.write(f"src/{n}.ts", "0\n")
        extra = [{"id": "H2", "slug": "two", "phase": 1, "title": "Второй", "role": "demo",
                  "goal": "г", "paths": ["src/b.ts", "src/d.ts"], "ref_paths": []}]
        for i in range(6):
            extra.append({"id": f"X{i}", "slug": f"x{i}", "phase": 1, "title": f"X{i}", "role": "demo",
                          "goal": "г", "paths": [f"src/x{i}.ts"], "ref_paths": []})
        self.s.blocks(paths=["src/a.ts", "src/c.ts", "src/h.ts"], extra_blocks=extra)
        self.s.manifest(hypotheses=1)
        self.s.commit()

        def touch(*files):
            for f in files:
                p = Path(self.s.root, "src", f + ".ts")
                p.write_text(p.read_text() + "1\n")
            self.s.git("add", "-A")
            self.s.git("commit", "-q", "-m", "t")
        for _ in range(3):
            touch("a", "b")                       # настоящая пара через блоки
        for _ in range(3):
            touch("a", "c")                       # оба в H1 — не стык, читает один блок
        for _ in range(3):
            touch("c", "d", *[f"x{i}" for i in range(6)])   # массовые: 8 файлов
        for i in range(6):
            for _ in range(3):
                touch("h", f"x{i}")               # h связан с шестью блоками
        for _ in range(60):
            touch("a")                            # мелких коммитов много — 95-й процентиль ниже массовых
        self.s.run("init")

    def test_coupling_находит_пару_через_блоки_и_отсекает_массовые_коммиты(self):
        self._coupled_history()
        out = self.s.run("coupling").stdout
        self.assertIn("H1 src/a.ts  ↔  H2 src/b.ts", out)
        self.assertNotIn("src/a.ts  ↔  H1 src/c.ts", out)
        self.assertNotIn("src/c.ts  ↔  H2 src/d.ts", out)
        self.assertIn("mass commits skipped (> ", out)
        # три массовых и стартовый коммит со всем деревом
        self.assertRegex(out, r"mass commits skipped \(> \d+ files, the 95th percentile of this repository\): 4")

    def test_coupling_выносит_общий_узел_отдельно(self):
        self._coupled_history()
        out = self.s.run("coupling").stdout
        self.assertIn("src/h.ts  ← 6 blocks", out)
        self.assertNotIn("↔  X0 src/x0.ts", out)

    def test_coupling_write_пишет_tsv(self):
        self._coupled_history()
        self.s.run("coupling", "--write")
        tsv = Path(self.s.root, "docs/review/coupling.tsv").read_text(encoding="utf-8")
        self.assertTrue(tsv.startswith("a\tblocks_a\tb\tblocks_b\ttogether"))
        self.assertIn("src/a.ts\tH1\tsrc/b.ts\tH2\t3", tsv)

    # ------------------------------------------------------------- порядок обхода

    def _churn_history(self, risk_first: str | None = None) -> None:
        """H1 объявлен первым, но почти не меняется; H2 меняется впятеро чаще."""
        self.s.write("src/a.ts", "0\n")
        self.s.write("src/b.ts", "0\n")
        self.s.blocks(paths=["src/a.ts"], extra_blocks=[{
            "id": "H2", "slug": "two", "phase": 1, "title": "Второй", "role": "demo",
            "goal": "г", "paths": ["src/b.ts"], "ref_paths": []}])
        if risk_first:
            bj = Path(self.s.root, "docs/review/blocks.json")
            d = json.loads(bj.read_text(encoding="utf-8"))
            d["blocks"][0]["risk"] = risk_first
            bj.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
        self.s.manifest(hypotheses=1)
        self.s.commit()

        def touch(f):
            p = Path(self.s.root, "src", f + ".ts")
            p.write_text(p.read_text() + "1\n")
            self.s.git("add", "-A")
            self.s.git("commit", "-q", "-m", "t")
        touch("a")
        for _ in range(5):
            touch("b")
        self.s.run("init")

    def test_order_ставит_часто_меняющийся_блок_выше_при_равном_риске(self):
        self._churn_history()
        out = self.s.run("order").stdout
        self.assertLess(out.index("H2 "), out.index("H1 "))
        self.assertRegex(out, r"H2\s+—\s+todo\s+6\s+1")  # 5 правок + стартовый коммит
        self.assertIn("block(s) would move against the declared order", out)

    def test_order_риск_важнее_частоты(self):
        """Хотспот ловит дефект, цена ошибки ловит необратимость — риск первый ключ."""
        self._churn_history(risk_first="high")
        out = self.s.run("order").stdout
        self.assertLess(out.index("H1 "), out.index("H2 "))
        self.assertIn("the declared order already matches", out)

    # ------------------------------------------------------------- итог ревью

    def _reviewed_with_findings(self) -> None:
        self.s.write("src/one.ts", "a\n")
        self.s.write("tests/guard.test.ts", "g\n")
        self.s.blocks(paths=["src/one.ts", "tests/guard.test.ts"])
        self.s.manifest(hypotheses=1)
        self.s.write("docs/review/reports/H1-findings.jsonl", "".join(json.dumps({
            "block": "H1", "severity": sev, "confidence": "confirmed", "status": "open",
            "file": "src/one.ts", "line": "1", "claim": f"дефект {i}",
            "scenario": "человек делает X — получает Y"}, ensure_ascii=False) + "\n"
            for i, sev in ((1, "high"), (2, "low"), (3, "medium"))))
        self.s.commit()
        self.s.run("init")
        self.s.run("import", "H1")
        self.s.run("set-finding", "H1-002", "rejected", "--reason", "так и задумано: поле необязательно")
        self.s.run("set-finding", "H1-003", "deferred", "--reason", "чиним после релиза")
        sha = self.s.git("rev-parse", "HEAD").stdout.strip()
        self.s.run("set-finding", "H1-001", "fixed", "--commit", sha, "--rule", "tests/guard.test.ts")

    def test_summary_пишет_итог_с_базой_отвергнутыми_и_уздами(self):
        self._reviewed_with_findings()
        out = self.s.run("summary", "--out", "docs/итог.md")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        text = Path(self.s.root, "docs/итог.md").read_text(encoding="utf-8")
        sha = self.s.git("rev-parse", "HEAD").stdout.strip()
        self.assertIn(f"`{sha[:12]}`", text)
        self.assertIn("H1-002", text)
        self.assertIn("так и задумано: поле необязательно", text)
        self.assertIn("чиним после релиза", text)
        self.assertIn("`tests/guard.test.ts` — H1-001", text)
        self.assertIn("<!-- finetooth-summary ", text)

    def test_критерий_приёмки_в_итоге_без_вставленного_образца(self):
        """Критерий приёмки попадает в итог одной ячейкой, и образец таблицы внутри него —
        не часть фразы: вклеенный в ячейку, он превращался в вереницу кавычек и палок."""
        self._reviewed_with_findings()
        m = Path(self.s.root, "docs/review/blocks/H1-demo.md")
        m.write_text(m.read_text(encoding="utf-8").replace(
            "Таблица «вход → ожидание → факт» по каждой гипотезе.",
            "Таблица «вход → ожидание → факт» по каждой гипотезе.\n\n"
            "```markdown\n| вход | ожидание | факт |\n```\n"), encoding="utf-8")
        self.s.run("summary", "--out", "docs/итог.md")
        text = Path(self.s.root, "docs/итог.md").read_text(encoding="utf-8")
        self.assertIn("Таблица «вход → ожидание → факт» по каждой гипотезе.", text)
        self.assertNotIn("```markdown", text)

    def test_summary_aged_считает_дрейф_от_коммита_базы(self):
        self._reviewed_with_findings()
        self.s.run("summary", "--out", "docs/итог.md")
        # правка в файле блока после итога — и одна вне блоков
        Path(self.s.root, "src/one.ts").write_text("a\nb\n")
        Path(self.s.root, "README.md").write_text("x\n")
        self.s.git("add", "-A")
        self.s.git("commit", "-q", "-m", "after")
        out = self.s.run("summary", "--aged", "docs/итог.md").stdout
        self.assertRegex(out, r"H1\s+\S+: 1\s+\S+: 1")

    def test_дрейф_не_считает_один_файл_дважды(self):
        """`git log -z` приклеивает перевод строки формата к ПЕРВОМУ пути каждого коммита,
        и файл, который в одном коммите первый, а в другом нет, попадал в счёт дважды:
        два коммита по двум файлам печатались как три файла."""
        self._reviewed_with_findings()
        self.s.run("summary", "--out", "docs/итог.md")
        Path(self.s.root, "src/one.ts").write_text("a\nb\n")
        Path(self.s.root, "tests/guard.test.ts").write_text("g\ng\n")
        self.s.git("add", "-A")
        self.s.git("commit", "-q", "-m", "оба файла")
        Path(self.s.root, "tests/guard.test.ts").write_text("g\ng\ng\n")
        self.s.git("add", "-A")
        self.s.git("commit", "-q", "-m", "второй файл ещё раз")
        out = self.s.run("summary", "--aged", "docs/итог.md").stdout
        self.assertRegex(out, r"H1\s+\S+: 2\s+\S+: 2", out)

    # ------------------------------------------------------------- экономия ходов

    def test_шаблоны_ролей_несут_правило_экономии_ходов(self):
        """Замер: цена = ходы × контекст. Правило живёт в шаблонах обоих языков, иначе
        промпт его не увидит."""
        refs = SKILL / "references"
        self.assertIn("whole in one call", (refs / "hunter.md").read_text(encoding="utf-8"))
        self.assertIn("целиком одним вызовом", (refs / "hunter.ru.md").read_text(encoding="utf-8"))
        self.assertIn("one script file", (refs / "verify.md").read_text(encoding="utf-8"))
        self.assertIn("одним файлом", (refs / "verify.ru.md").read_text(encoding="utf-8"))

    def test_шаблон_исполнителя_держит_правила_выпуска_и_расхода(self):
        """Оба правила выведены из первого прогона починки набора: он поднял версию сам
        (откатили — выпуск решает сопровождающий) и потратил бо́льшую часть 329 ходов на
        прогон всего набора в отдельных worktree на каждом коммите. Правило, которого нет
        ни в тесте, ни в журнале изменений, снимут при следующей правке шаблона."""
        refs = SKILL / "references"
        for name, said in ((
                "fix.md", ("the version, the release and the history are not yours",
                           "changelog entries go under \"Unreleased\"",
                           "spend turns on fixes, not on ceremony",
                           "the full gates once at the end of the series")),
                ("fix.ru.md", ("версия, выпуск и история — не твои",
                               "записи идут в «Не выпущено»",
                               "трать ходы на правки, а не на обряды",
                               "полные ворота — один раз в конце серии"))):
            # шаблон свёрстан по ширине: перенос строки внутри фразы — не пропуск
            text = re.sub(r"\s+", " ", (refs / name).read_text(encoding="utf-8")).lower()
            for rule in said:
                with self.subTest(шаблон=name, правило=rule):
                    self.assertIn(rule.lower(), text, f"{name}: правило снято из шаблона")

    def test_шаблоны_ролей_говорят_где_писать_вердикт(self):
        """Правка механизма — правка промпта: разборщик перестал читать вердикты внутри
        цитаты, и шаблоны обоих языков обязаны назвать все её формы. Иначе гейт краснеет
        на честном отчёте, а это дефект набора, а не агента."""
        refs = SKILL / "references"
        forms = {"": ("outside code blocks and quotations", "indented by four spaces",
                      "`>`", "html comment"),
                 ".ru": ("вне блоков кода и цитат", "отступом в четыре пробела",
                         "`>`", "html-комментарий")}
        for role in ("hunter", "verify"):
            for lang, said in forms.items():
                name = f"{role}{lang}.md"
                # шаблон свёрстан по ширине: перенос строки внутри фразы — не пропуск
                text = re.sub(r"\s+", " ", (refs / name).read_text(encoding="utf-8"))
                for form in said:
                    with self.subTest(шаблон=name, форма=form):
                        self.assertIn(form, text, f"{name}: форма цитаты не названа")

    def test_шаблоны_ролей_говорят_что_цитата_не_считается_нигде(self):
        """Правка механизма — правка промпта: цитату перестали считать не только в
        вердиктах гипотез, но и во всём, что ворота читают по существу — в разделе
        ограничений охвата и в словах проверяющего о находках и об охвате."""
        refs = SKILL / "references"
        said = {"": "everything the state check reads in the report",
                ".ru": "всего, что проверка состояния читает в отчёте"}
        for role in ("hunter", "verify"):
            for lang, rule in said.items():
                name = f"{role}{lang}.md"
                # шаблон свёрстан по ширине: перенос строки внутри фразы — не пропуск
                text = re.sub(r"\s+", " ", (refs / name).read_text(encoding="utf-8"))
                with self.subTest(шаблон=name):
                    self.assertIn(rule, text, f"{name}: правило о цитате сужено до вердиктов")

    def test_axes_считает_usage_раз_на_сообщение_и_перечитывания(self):
        """stream-json дробит одно сообщение на несколько событий с ОДНИМ usage: считать
        дважды — завысить вход вдвое."""
        usage = {"input_tokens": 1, "cache_creation_input_tokens": 100, "cache_read_input_tokens": 900, "output_tokens": 5}
        ev = lambda o: json.dumps(o, ensure_ascii=False)
        stream = "\n".join([
            ev({"type": "assistant", "message": {"id": "m1", "model": "test", "usage": usage,
                "content": [{"type": "tool_use", "id": "t1", "name": "Read", "input": {"file_path": "/x/a.ts"}}]}}),
            ev({"type": "assistant", "message": {"id": "m1", "model": "test", "usage": usage, "content": []}}),
            ev({"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t1", "content": "abcd"}]}}),
            ev({"type": "assistant", "message": {"id": "m2", "model": "test", "usage": usage,
                "content": [{"type": "tool_use", "id": "t2", "name": "Read", "input": {"file_path": "/x/a.ts"}}]}}),
            ev({"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t2", "content": "abcd"}]}}),
            ev({"type": "result", "num_turns": 2, "duration_ms": 60000, "total_cost_usd": 0.5,
                "usage": {"output_tokens": 42}}),
        ]) + "\n"
        path = Path(self.s.root, "stream.jsonl")
        path.write_text(stream, encoding="utf-8")
        out = subprocess.run([sys.executable, str(SKILL / "scripts" / "axes.py"), str(path), "--journal"],
                             capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        # два сообщения по 1001 на вход, не три
        self.assertIn("input 0.0M tokens (90% from cache", out.stdout)
        self.assertIn("re-reads 1", out.stdout)
        self.assertIn("output 0k", out.stdout)
        full = subprocess.run([sys.executable, str(SKILL / "scripts" / "axes.py"), str(path)],
                              capture_output=True, text=True).stdout
        self.assertIn("input total          2,002", full)

    def test_run_role_отказывает_на_неизвестной_роли(self):
        out = subprocess.run(["bash", str(SKILL / "assets" / "run-role.sh"), "H1", "nosuch"],
                             capture_output=True, text=True)
        self.assertEqual(out.returncode, 2)
        self.assertIn("unknown role", out.stderr)

    def test_строка_за_концом_файла_у_починенной_находки_не_ошибка(self):
        """После починки файл законно короче: процитированная строка была в старом тексте."""
        self.s.write("src/one.ts", "a\n" * 10)
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=1)
        self.s.write("docs/review/reports/H1-findings.jsonl", json.dumps({
            "block": "H1", "severity": "low", "confidence": "confirmed", "status": "open",
            "file": "src/one.ts", "line": 9, "claim": "дефект",
            "scenario": "человек делает X — получает Y"}, ensure_ascii=False) + "\n")
        self.s.commit()
        self.s.run("init")
        self.s.run("import", "H1")
        self.s.write("src/one.ts", "a\n" * 3)
        self.s.git("add", "-A")
        self.s.git("commit", "-q", "-m", "fix")
        sha = self.s.git("rev-parse", "HEAD").stdout.strip()
        self.assertIn("is cited, but", self.s.run("check").stdout)
        self.s.run("set-finding", "H1-001", "fixed", "--commit", sha)
        self.assertNotIn("is cited, but", self.s.run("check").stdout)

    def test_подстановка_в_тексте_находки_не_роняет_prompt(self):
        """Находка про шаблон цитирует `{{FILES}}` — это цитата, а не незаполненное место."""
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=1)
        self.s.write("docs/review/reports/H1-findings.jsonl", json.dumps({
            "block": "H1", "severity": "low", "confidence": "confirmed", "status": "open",
            "file": "src/one.ts", "claim": "шаблон оставляет {{FILES}} и {{HUNTER_NOTE}} без значения",
            "scenario": "агент видит {{FILES}} как задание"}, ensure_ascii=False) + "\n")
        self.s.commit()
        self.s.run("init")
        self.s.run("import", "H1")
        out = self.s.run("prompt", "H1", "--role", "fix")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertIn("{{HUNTER_NOTE}}", out.stdout)

    def test_ограда_при_любом_отступе_не_режет_манифест(self):
        """R3-001: открывающая ограда глубже трёх пробелов не открывалась, строка-пункт внутри
        примера сдвигала колонку, и ЗАКРЫВАЮЩАЯ ограда читалась как открывающая — манифест
        из четырёх гипотез становился манифестом из одной, и check зеленел. Правило одно:
        ограда — ограда при любом отступе."""
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=4)
        m = Path(self.s.root, "docs/review/blocks/H1-demo.md")
        text = m.read_text(encoding="utf-8")
        first = next(ln for ln in text.splitlines() if ln.startswith("1. "))
        text = text.replace(first, first + " Инструмент печатает вердикт так:\n"
                            "       ```\n       - H1.1 — проверена\n       ```", 1)
        m.write_text(text, encoding="utf-8")
        self.s.commit()
        self.s.run("init")
        out = self.s.run("hypotheses", "H1").stdout
        self.assertIn("H1.4", out)
        self.assertIn("0/4", out)

    def test_import_держит_те_же_пределы_что_check(self):
        """R5-005: черновик с длинным сценарием проходил import и ронял check навсегда."""
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=1)
        self.s.write("docs/review/reports/H1-findings.jsonl", json.dumps({
            "block": "H1", "severity": "low", "confidence": "confirmed", "status": "open",
            "file": "src/one.ts", "claim": "дефект", "scenario": "x" * 701}, ensure_ascii=False) + "\n")
        self.s.commit()
        self.s.run("init")
        out = self.s.run("import", "H1")
        self.assertEqual(out.returncode, 2, out.stdout + out.stderr)
        self.assertIn("scenario is 701 characters", out.stdout + out.stderr)

    def test_раздел_охвата_за_незакрытой_оградой_не_засчитан(self):
        """R6-004/R7-007: заголовок «Ограничения охвата» после ограды, которая не закрылась, —
        часть примера. Гейт обязан сказать, что раздела нет, и назвать причину."""
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=1)
        self.s.reports(hunter="# охотник\n## Гипотезы\n- H1.1 — проверена: да\n"
                              "Образец отчёта:\n````markdown\n## Ограничения охвата\nнет\n",
                       verify=FULL_VERIFY)
        self.s.commit()
        self.s.run("init")
        self.s.run("coverage")
        self.s.run("set-status", "H1", "verified")
        out = self.s.run("check").stdout
        self.assertIn("no 'Coverage limits' section outside a fence", out)

    def test_refs_находит_номер_находки_в_коде_и_только_его(self):
        """Номер находки в комментарии умирает вместе с каталогом ревью."""
        self.s.write("src/one.ts", "a\n")
        self.s.write("src/two.ts", "// see H1-001: the fix\n// H1-999 is not ours\n// H1-0012 neither\n")
        self.s.blocks(paths=["src/one.ts", "src/two.ts"])
        self.s.manifest(hypotheses=1)
        self.s.write("docs/review/reports/H1-findings.jsonl", json.dumps({
            "block": "H1", "severity": "low", "confidence": "confirmed", "status": "open",
            "file": "src/one.ts", "claim": "дефект", "scenario": "x делает y"}, ensure_ascii=False) + "\n")
        self.s.commit()
        self.s.run("init")
        self.s.run("import", "H1")
        self.s.git("add", "-A")
        self.s.git("commit", "-q", "-m", "reg")
        out = self.s.run("refs")
        self.assertEqual(out.returncode, 1, out.stdout + out.stderr)
        self.assertIn("src/two.ts:1: H1-001", out.stdout)
        self.assertNotIn("H1-999", out.stdout)
        self.assertNotIn("H1-0012", out.stdout)
        self.assertNotIn("docs/review/", out.stdout.split("\n\n")[0])   # the register itself is not a reference
        self.assertIn("reference(s) to findings in the code", self.s.run("check").stdout)

    def test_дубль_указывает_на_живую_находку(self):
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=1)
        self.s.write("docs/review/reports/H1-findings.jsonl", "".join(json.dumps({
            "block": "H1", "severity": "high", "confidence": "confirmed", "status": "open",
            "file": "src/one.ts", "claim": f"дефект {i}",
            "scenario": "человек делает X — получает Y"}, ensure_ascii=False) + "\n"
            for i in (1, 2, 3)))
        self.s.commit()
        self.s.run("init")
        self.s.run("import", "H1")
        for bogus in ("H1-999", "H1-002"):
            self.assertNotEqual(
                self.s.run("set-finding", "H1-002", "duplicate", "--dup-of", bogus).returncode,
                0, bogus)
        self.assertEqual(self.s.run("set-finding", "H1-002", "duplicate",
                                    "--dup-of", "H1-001").returncode, 0)
        self.assertNotEqual(self.s.run("set-finding", "H1-003", "duplicate",
                                       "--dup-of", "H1-002").returncode, 0,
                            "дубль дубля не несёт дефект ни в одной живой записи")

        f_path = self.s.root / "docs/review/findings.jsonl"
        rows = [json.loads(x) for x in f_path.read_text(encoding="utf-8").splitlines() if x]
        rows[1]["dup_of"] = "H1-777"  # вписано руками мимо set-finding
        f_path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                          encoding="utf-8")
        self.assertIn("duplicate of nonexistent H1-777", self.s.run("check").stdout)

    def test_живая_находка_на_изменённом_файле_перештамповывается(self):
        """Файл меняют и соседней починкой — подтвердить живой дефект должно быть чем."""
        self.s.write("src/one.ts", "было\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=1)
        self.s.write("docs/review/reports/H1-findings.jsonl", "".join(json.dumps({
            "block": "H1", "severity": "high", "confidence": "confirmed", "status": "open",
            "file": "src/one.ts", "claim": f"дефект {i}",
            "scenario": "человек делает X — получает Y"}, ensure_ascii=False) + "\n"
            for i in (1, 2)))
        self.s.commit()
        self.s.run("init")
        self.s.run("import", "H1")
        self.s.run("findings")
        self.s.write("src/one.ts", "первый починен, второй жив\n")
        self.s.commit("починка первого")
        self.s.run("set-finding", "H1-001", "fixed", "--commit",
                   self.s.git("rev-parse", "--short", "HEAD").stdout.strip())
        out = self.s.run("check").stdout
        self.assertIn("H1-002: code in src/one.ts changed", out)
        self.assertIn("restamp H1-002", out, "отказ обязан говорить, что делать")

        self.assertEqual(self.s.run("restamp", "H1-002").returncode, 0)
        self.assertNotIn("changed since import", self.s.run("check").stdout)
        self.assertNotEqual(self.s.run("restamp", "H1-001").returncode, 0,
                            "починенную находку штамповать нечего")
        self.assertNotEqual(self.s.run("restamp", "H1-999").returncode, 0)

    def test_правка_контекста_предупреждает_но_не_роняет(self):
        """Изменился не предмет блока, а то, на что он опирался, — «suspect link» doorstop."""
        self.s.write("src/one.ts", "a\n")
        self.s.write("lib/guard.ts", "было\n")
        self.s.blocks(paths=["src/one.ts", "lib/guard.ts"])
        bj = self.s.root / "docs/review/blocks.json"
        d = json.loads(bj.read_text(encoding="utf-8"))
        d["blocks"][0]["paths"] = ["src/one.ts"]
        d["blocks"][0]["ref_paths"] = ["lib"]
        d["blocks"].append({"id": "Z9", "slug": "lib", "phase": 2, "title": "Библиотека",
                            "role": "lib", "goal": "владелец lib", "paths": ["lib"],
                            "ref_paths": []})
        bj.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        self.s.manifest(hypotheses=1)
        self.s.reports(hunter="# охотник\n## Гипотезы\n- H1.1 — проверена: да\n"
                              "## Ограничения охвата\nнет\n", verify=FULL_VERIFY)
        self.s.commit()
        self.s.run("init")
        self.s.run("coverage")
        self.s.run("set-status", "H1", "verified")
        out = self.s.run("check")
        self.assertEqual(out.returncode, 0, out.stdout)
        self.assertNotIn("context", out.stdout)

        self.s.write("lib/guard.ts", "стало\n")
        self.s.commit("правка общего модуля")
        out = self.s.run("check")
        self.assertEqual(out.returncode, 0, "правка контекста не отказ: " + out.stdout)
        self.assertIn("context files (ref_paths) changed", out.stdout)
        self.s.run("restamp", "H1")
        self.assertNotIn("context", self.s.run("check").stdout)

    def test_нетронутая_строка_шаблона_не_оценка_охвата(self):
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=1)
        self.s.reports(hunter="# охотник\n## Гипотезы\n- H1.1 — проверена: да\n"
                              "## Ограничения охвата\nнет\n",
                       verify="# отчёт верификатора\n## Вердикты по находкам охотника\n"
                              "Находок нет.\n## Состояние охвата блока\n"
                              "Полный / неполный — и что именно осталось.\n")
        self.s.commit()
        self.s.run("init")
        self.s.run("coverage")
        self.s.run("set-status", "H1", "verified")
        self.assertIn("no coverage verdict", self.s.run("check").stdout)

    def test_штамповать_непройденный_блок_нельзя(self):
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=1)
        self.s.commit()
        self.s.run("init")
        self.assertEqual(self.s.run("restamp", "H1").returncode, 2)

    # -------------------------------------------------------------------- находки

    def test_находка_не_закрывается_без_коммита_причины_и_ссылки(self):
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=1)
        self.s.write("docs/review/reports/H1-findings.jsonl", json.dumps({
            "block": "H1", "severity": "low", "confidence": "confirmed", "status": "open",
            "file": "src/one.ts", "claim": "что-то не так",
            "scenario": "человек делает X — получает Y"}, ensure_ascii=False) + "\n")
        self.s.commit()
        self.s.run("init")
        self.s.run("import", "H1")

        self.assertEqual(self.s.run("set-finding", "H1-001", "fixed").returncode, 2)
        self.assertEqual(self.s.run("set-finding", "H1-001", "rejected").returncode, 2)
        self.assertEqual(self.s.run("set-finding", "H1-001", "duplicate").returncode, 2)
        self.assertEqual(
            self.s.run("set-finding", "H1-001", "fixed", "--commit", "abc1234").returncode, 0)

    def test_отказ_меняет_и_уверенность(self):
        """«Отвергнута» и «подтверждена» разом — противоречие в реестре."""
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=1)
        self.s.write("docs/review/reports/H1-findings.jsonl", json.dumps({
            "block": "H1", "severity": "high", "confidence": "confirmed", "status": "open",
            "file": "src/one.ts", "claim": "дефект", "scenario": "сценарий"},
            ensure_ascii=False) + "\n")
        self.s.commit()
        self.s.run("init")
        self.s.run("import", "H1")
        f_path = self.s.root / "docs/review/findings.jsonl"
        row = lambda: json.loads(f_path.read_text(encoding="utf-8").splitlines()[0])

        self.s.run("set-finding", "H1-001", "rejected", "--reason", "код так и задуман")
        self.assertEqual(row()["confidence"], "rejected")
        self.s.run("set-finding", "H1-001", "open")
        self.assertEqual(row()["confidence"], "plausible", "возвращённая ждёт новой проверки")

        r = row()
        r.update(status="rejected", reject_reason="вписано руками", confidence="confirmed")
        f_path.write_text(json.dumps(r, ensure_ascii=False) + "\n", encoding="utf-8")
        self.assertIn("status rejected but confidence confirmed", self.s.run("check").stdout)

    def test_отвергнутая_находка_без_причины_роняет_проверку(self):
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=1)
        self.s.write("docs/review/reports/H1-findings.jsonl", json.dumps({
            "block": "H1", "severity": "low", "confidence": "rejected", "status": "rejected",
            "file": "src/one.ts", "claim": "ложная тревога",
            "scenario": "проверено, поведение корректно"}, ensure_ascii=False) + "\n")
        self.s.commit()
        self.s.run("init")
        self.s.run("import", "H1")
        self.s.run("findings")
        out = self.s.run("check")
        self.assertIn("reject reason is not recorded", out.stdout)

    def test_идентификаторы_находок_не_разъезжаются_при_повторном_импорте(self):
        """Id раздаются по позиции — инструмент обязан писать их обратно в файл блока."""
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=1)
        rows = [{"block": "H1", "severity": "low", "confidence": "confirmed", "status": "open",
                 "file": "src/one.ts", "claim": f"находка {i}", "scenario": "сценарий"}
                for i in range(1, 3)]
        src = self.s.root / "docs/review/reports/H1-findings.jsonl"
        src.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                       encoding="utf-8")
        self.s.commit()
        self.s.run("init")
        self.s.run("import", "H1")
        first = [json.loads(l) for l in src.read_text(encoding="utf-8").splitlines() if l.strip()]
        self.assertEqual([f["id"] for f in first], ["H1-001", "H1-002"])

        # новая находка ДОПИСАНА в начало — старые id обязаны сохраниться
        rows2 = [{"block": "H1", "severity": "low", "confidence": "confirmed", "status": "open",
                  "file": "src/one.ts", "claim": "находка 0", "scenario": "сценарий"}] + first
        src.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows2) + "\n",
                       encoding="utf-8")
        self.s.run("import", "H1", "--force")
        second = [json.loads(l) for l in src.read_text(encoding="utf-8").splitlines() if l.strip()]
        by_claim = {f["claim"]: f["id"] for f in second}
        self.assertEqual(by_claim["находка 1"], "H1-001")
        self.assertEqual(by_claim["находка 2"], "H1-002")

    def test_изменившийся_код_под_открытой_находкой_роняет_проверку(self):
        """Реестр протухает: находку чинят, статус не переводят — гейт обязан это заметить."""
        self.s.write("src/one.ts", "было\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=1)
        self.s.write("docs/review/reports/H1-findings.jsonl", json.dumps({
            "block": "H1", "severity": "high", "confidence": "confirmed", "status": "open",
            "file": "src/one.ts", "claim": "тут дефект",
            "scenario": "человек делает X — получает Y"}, ensure_ascii=False) + "\n")
        self.s.commit()
        self.s.run("init")
        self.s.run("import", "H1")
        self.s.run("findings")
        self.assertNotIn("changed", self.s.run("check").stdout)

        self.s.write("src/one.ts", "стало, починено\n")
        self.s.commit("починка")
        out = self.s.run("check")
        self.assertIn("changed since import", out.stdout)
        self.assertIn("set-finding", out.stdout, "отказ обязан говорить, что делать")

    def test_повторный_импорт_не_переснимает_отпечаток_находки(self):
        """Иначе устаревшая находка пропадала из check без всякой перепроверки."""
        self.s.write("src/one.ts", "было\n")
        self.s.write("src/two.ts", "другое\n")
        self.s.blocks(paths=["src/one.ts", "src/two.ts"])
        self.s.manifest(hypotheses=1)
        self.s.write("docs/review/reports/H1-findings.jsonl", json.dumps({
            "block": "H1", "severity": "high", "confidence": "confirmed", "status": "open",
            "file": "src/one.ts", "claim": "тут дефект",
            "scenario": "человек делает X — получает Y"}, ensure_ascii=False) + "\n")
        self.s.commit()
        self.s.run("init")
        self.s.run("import", "H1")
        self.s.write("src/one.ts", "стало\n")
        self.s.commit("правка под находкой")
        self.assertIn("changed since import", self.s.run("check").stdout)

        self.assertEqual(self.s.run("import", "H1").returncode, 0)
        self.assertIn("changed since import", self.s.run("check").stdout,
                      "повторный импорт не перепроверка")

        src = self.s.root / "docs/review/reports/H1-findings.jsonl"
        row = json.loads(src.read_text(encoding="utf-8").splitlines()[0])
        row["file"] = "src/two.ts"
        src.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
        self.s.run("import", "H1")
        self.assertNotIn("changed since import", self.s.run("check").stdout,
                         "находка про другой файл — новое утверждение, отпечаток новый")

    def test_несуществующая_строка_в_находке_роняет_проверку(self):
        self.s.write("src/one.ts", "одна\nдве\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=1)
        self.s.write("docs/review/reports/H1-findings.jsonl", json.dumps({
            "block": "H1", "severity": "low", "confidence": "confirmed", "status": "open",
            "file": "src/one.ts", "line": 900, "claim": "дефект на строке, которой нет",
            "scenario": "сценарий"}, ensure_ascii=False) + "\n")
        self.s.commit()
        self.s.run("init")
        self.s.run("import", "H1")
        self.s.run("findings")
        out = self.s.run("check")
        self.assertIn("line 900 is cited", out.stdout)

    def test_коммит_починки_обязан_касаться_файла_находки(self):
        """Отметка «починено» проверяется коммитом, а не словом."""
        self.s.write("src/one.ts", "a\n")
        self.s.write("src/other.ts", "b\n")
        self.s.blocks(paths=["src/one.ts", "src/other.ts"])
        self.s.manifest(hypotheses=1)
        self.s.write("docs/review/reports/H1-findings.jsonl", json.dumps({
            "block": "H1", "severity": "low", "confidence": "confirmed", "status": "open",
            "file": "src/one.ts", "claim": "дефект", "scenario": "сценарий"},
            ensure_ascii=False) + "\n")
        self.s.commit()
        self.s.run("init")
        self.s.run("import", "H1")

        # правка сделана в СОСЕДНЕМ файле, а отметка ставится на находку про src/one.ts
        self.s.write("src/other.ts", "b\nправка не там\n")
        self.s.commit("правка соседнего модуля")
        wrong = self.s.git("rev-parse", "HEAD").stdout.strip()
        self.s.run("set-finding", "H1-001", "fixed", "--commit", wrong)
        self.s.run("findings")
        out = self.s.run("check")
        self.assertIn("does not touch src/one.ts", out.stdout)

        # а теперь коммит, которого в репозитории нет вовсе
        self.s.run("set-finding", "H1-001", "fixed", "--commit", "0123456789abcdef")
        self.s.run("findings")
        self.assertIn("is not in the repository", self.s.run("check").stdout)

    def test_путь_с_пробелом_не_ломает_проверку_коммита(self):
        self.s.write("src/my file.ts", "a\n")
        self.s.blocks(paths=["src"])
        self.s.manifest(hypotheses=1)
        self.s.write("docs/review/reports/H1-findings.jsonl", json.dumps({
            "block": "H1", "severity": "low", "confidence": "confirmed", "status": "open",
            "file": "src/my file.ts", "claim": "дефект", "scenario": "сценарий"},
            ensure_ascii=False) + "\n")
        self.s.commit()
        self.s.run("init")
        self.s.run("import", "H1")
        self.s.write("src/my file.ts", "a\nпочинено\n")
        self.s.commit("починка")
        sha = self.s.git("rev-parse", "HEAD").stdout.strip()
        self.s.run("set-finding", "H1-001", "fixed", "--commit", sha)
        self.assertNotIn("does not touch", self.s.run("check").stdout)

    def test_починка_в_общем_модуле_называется_явно(self):
        """Маршрут чинят в общем стороже — проверка не должна требовать правки не там."""
        self.s.write("src/route.ts", "a\n")
        self.s.write("src/guard.ts", "b\n")
        self.s.blocks(paths=["src/route.ts", "src/guard.ts"])
        self.s.manifest(hypotheses=1)
        self.s.write("docs/review/reports/H1-findings.jsonl", json.dumps({
            "block": "H1", "severity": "high", "confidence": "confirmed", "status": "open",
            "file": "src/route.ts", "claim": "маршрут без проверки прав", "scenario": "сценарий"},
            ensure_ascii=False) + "\n")
        self.s.commit()
        self.s.run("init")
        self.s.run("import", "H1")
        self.s.write("src/guard.ts", "b\nсторож проверяет права\n")
        self.s.commit("починка в стороже")
        sha = self.s.git("rev-parse", "HEAD").stdout.strip()

        self.assertNotEqual(self.s.run("set-finding", "H1-001", "fixed", "--commit", sha,
                                       "--fixed-in", "src/нет-такого.ts").returncode, 0)
        self.s.run("set-finding", "H1-001", "fixed", "--commit", sha)
        out = self.s.run("check").stdout
        self.assertIn("does not touch src/route.ts", out)
        self.assertIn("--fixed-in", out, "отказ обязан говорить, что делать")
        self.assertEqual(self.s.run("set-finding", "H1-001", "fixed", "--commit", sha,
                                    "--fixed-in", "src/guard.ts").returncode, 0)
        self.assertNotIn("does not touch", self.s.run("check").stdout)

    def test_починка_в_соседнем_репозитории_помечается_явно(self):
        """Коммит чужого репозитория здесь не найти — но пометка обязана быть явной."""
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=1)
        self.s.write("docs/review/reports/H1-findings.jsonl", json.dumps({
            "block": "H1", "severity": "high", "confidence": "confirmed", "status": "open",
            "file": "src/one.ts", "claim": "дефект в стыке с соседним сервисом",
            "scenario": "сценарий"}, ensure_ascii=False) + "\n")
        self.s.commit()
        self.s.run("init")
        self.s.run("import", "H1")

        # без пометки репозитория проверка честно говорит, что коммита нет
        self.s.run("set-finding", "H1-001", "fixed", "--commit", "0123456789abcdef")
        self.s.run("findings")
        self.assertIn("is not in the repository", self.s.run("check").stdout)

        # с пометкой — принимается
        self.s.run("set-finding", "H1-001", "fixed", "--commit", "ядро:0123456789abcdef")
        self.s.run("findings")
        out = self.s.run("check")
        self.assertNotIn("is not in the repository", out.stdout)
        self.assertNotIn("H1-001", out.stdout)

    def test_статус_блока_вписанный_руками_роняет_проверку(self):
        """set-status словарь проверял, а правку state.json руками — никто."""
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=1)
        self.s.commit()
        self.s.run("init")
        st = self.s.root / "docs" / "review" / "state.json"
        data = json.loads(st.read_text(encoding="utf-8"))
        data["blocks"]["H1"]["status"] = "почти готово"
        st.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        self.assertIn("is not in the vocabulary", self.s.run("check").stdout)

    def test_куцый_манифест_роняет_проверку(self):
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.write("docs/review/blocks/H1-demo.md", "# H1\n\n## Гипотезы\n1. Раз.\n")
        self.s.commit()
        self.s.run("init")
        self.s.run("set-status", "H1", "running")
        self.assertIn("is empty or nearly empty", self.s.run("check").stdout)

    def test_добор_не_затирает_починенное(self):
        """Штатный импорт заменяет находки блока целиком — у блока в работе это потеря."""
        self.s.write("src/one.ts", "a\n")
        self.s.write("src/two.ts", "b\n")
        self.s.blocks(paths=["src/one.ts", "src/two.ts"])
        self.s.manifest(hypotheses=1)
        src = self.s.root / "docs/review/reports/H1-findings.jsonl"
        src.write_text(json.dumps({
            "block": "H1", "severity": "high", "confidence": "confirmed", "status": "open",
            "file": "src/one.ts", "claim": "первая находка", "scenario": "сценарий"},
            ensure_ascii=False) + "\n", encoding="utf-8")
        self.s.commit()
        self.s.run("init")
        self.s.run("import", "H1")
        self.s.write("src/one.ts", "a\nпочинено\n")
        self.s.commit("починка")
        fix = self.s.git("rev-parse", "HEAD").stdout.strip()
        self.s.run("set-finding", "H1-001", "fixed", "--commit", fix)

        # добор: агент дописал новое в тот же файл блока, поверх уже импортированного
        with src.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "block": "H1", "severity": "low", "confidence": "confirmed", "status": "open",
                "file": "src/two.ts", "claim": "находка добора", "scenario": "сценарий"},
                ensure_ascii=False) + "\n")
        out = self.s.run("import", "H1", "--append")
        self.assertEqual(out.returncode, 0, out.stderr)

        rows = [json.loads(l) for l in
                (self.s.root / "docs/review/findings.jsonl").read_text(encoding="utf-8").splitlines()
                if l.strip()]
        by_id = {r["id"]: r for r in rows}
        self.assertEqual(len(rows), 2, "починенная находка должна остаться")
        self.assertEqual(by_id["H1-001"]["status"], "fixed", "отметка о починке затёрта")
        self.assertEqual(by_id["H1-002"]["claim"], "находка добора")
        self.assertEqual([json.loads(l)["id"] for l in src.read_text(encoding="utf-8").splitlines()],
                         ["H1-001", "H1-002"], "номера вписаны обратно в файл блока")
        again = self.s.run("import", "H1", "--append")
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertIn("appended 0", again.stdout, "повторный добор ничего не дописывает")

    def test_порог_читаемости_задаётся_проектом(self):
        """6000 строк выведены из TypeScript; в другом языке плотность смысла другая."""
        self.s.write("src/one.ts", "строка\n" * 500)
        self.s.blocks(paths=["src/one.ts"], readable_lines=100)
        self.s.manifest(hypotheses=1)
        self.s.commit()
        self.s.run("init")
        self.s.run("coverage")
        out = self.s.run("check")
        self.assertIn("ceiling 100", out.stdout, "проектный порог должен применяться")
        self.assertIn("cannot be read in one session", out.stdout)

    # ----------------------------------------------------------------- корни и узды

    def _three_of_one_root(self) -> None:
        self.s.write("src/one.ts", "a\n")
        self.s.write("src/two.ts", "b\n")
        self.s.write("src/three.ts", "c\n")
        self.s.blocks(paths=["src/one.ts", "src/two.ts", "src/three.ts"])
        self.s.manifest(hypotheses=1)
        rows = [{"block": "H1", "severity": "medium", "confidence": "confirmed", "status": "open",
                 "file": f, "root": "рукописная копия предиката",
                 "claim": f"копия предиката в {f}", "scenario": "поведение расходится с каноном"}
                for f in ("src/one.ts", "src/two.ts", "src/three.ts")]
        (self.s.root / "docs/review/reports/H1-findings.jsonl").write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
        self.s.commit()
        self.s.run("init")
        self.s.run("import", "H1")
        self.s.run("findings")

    def test_третий_повтор_корня_требует_узду(self):
        """Класс, повторившийся трижды, закрывается правилом, а не списком правок."""
        self._three_of_one_root()
        out = self.s.run("check")
        self.assertIn("and no guard", out.stdout)
        self.assertIn("рукописная копия предиката", out.stdout)
        self.assertIn("--rule", out.stdout, "отказ обязан говорить, что делать")

    def test_узда_записывается_на_весь_корень_сразу(self):
        """Класс закрыт целиком или не закрыт: узда проставляется всем экземплярам."""
        self._three_of_one_root()
        self.s.write("eslint.config.mjs", "export default [];\n")
        self.s.commit("узда")
        out = self.s.run("set-finding", "H1-001", "fixed", "--commit", "abc1234",
                         "--rule", "eslint.config.mjs")
        self.assertEqual(out.returncode, 0, out.stderr)
        rows = [json.loads(l) for l in
                (self.s.root / "docs/review/findings.jsonl").read_text(encoding="utf-8").splitlines()
                if l.strip()]
        self.assertTrue(all(r.get("rule") for r in rows), "узда должна стоять у всех трёх")
        self.s.run("findings")
        self.assertNotIn("and no guard", self.s.run("check").stdout)

    def test_узда_обязана_существовать(self):
        """Опечатка в пути делала класс «закрытым» без всякого правила."""
        self._three_of_one_root()
        for bogus in ("tests/нет-такого.test.ts", "eslint: no-handwritten-predicate",
                      "eslint:no-handwritten-predicate"):
            out = self.s.run("set-finding", "H1-001", "open", "--rule", bogus)
            self.assertNotEqual(out.returncode, 0, bogus)
        self.assertEqual(self.s.run("set-finding", "H1-001", "open", "--rule",
                                    "ядро:tests/predicate.rs").returncode, 0,
                         "узда в соседнем репозитории проверяется только на форму")

        self.s.write("tests/predicate.test.ts", "it('x', () => {});\n")
        self.s.commit("узда")
        out = self.s.run("set-finding", "H1-001", "open", "--rule",
                         "tests/predicate.test.ts::канон один")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.s.run("findings")
        self.assertNotIn("guard `", self.s.run("check").stdout)

        self.s.git("rm", "-q", "tests/predicate.test.ts")
        self.s.commit("узду удалили")
        self.assertIn("no such file", self.s.run("check").stdout,
                      "удалённая узда не должна держать класс закрытым")

    def test_два_экземпляра_узду_ещё_не_требуют(self):
        """Два повтора могут быть совпадением — гейт не должен шуметь раньше времени."""
        self.s.write("src/one.ts", "a\n")
        self.s.write("src/two.ts", "b\n")
        self.s.blocks(paths=["src/one.ts", "src/two.ts"])
        self.s.manifest(hypotheses=1)
        rows = [{"block": "H1", "severity": "low", "confidence": "confirmed", "status": "open",
                 "file": f, "root": "один корень", "claim": f"экземпляр в {f}",
                 "scenario": "сценарий"} for f in ("src/one.ts", "src/two.ts")]
        (self.s.root / "docs/review/reports/H1-findings.jsonl").write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
        self.s.commit()
        self.s.run("init")
        self.s.run("import", "H1")
        self.s.run("findings")
        self.assertNotIn("and no guard", self.s.run("check").stdout)

    def test_отвергнутые_и_дубли_не_считаются_экземплярами_класса(self):
        """Три записи — ещё не три экземпляра: отвергнутое и дубли класс не образуют."""
        self.s.write("src/one.ts", "a\n")
        self.s.write("src/two.ts", "b\n")
        self.s.write("src/three.ts", "c\n")
        self.s.blocks(paths=["src/one.ts", "src/two.ts", "src/three.ts"])
        self.s.manifest(hypotheses=1)
        rows = [
            {"file": "src/one.ts", "status": "open", "confidence": "confirmed"},
            {"file": "src/two.ts", "status": "rejected", "confidence": "rejected",
             "reject_reason": "поведение корректно, проверено вызовом"},
            {"file": "src/three.ts", "status": "duplicate", "dup_of": "H1-001",
             "confidence": "confirmed"},
        ]
        full = [{"block": "H1", "severity": "medium", "root": "один корень",
                 "claim": f"экземпляр в {r['file']}", "scenario": "сценарий", **r} for r in rows]
        (self.s.root / "docs/review/reports/H1-findings.jsonl").write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in full) + "\n", encoding="utf-8")
        self.s.commit()
        self.s.run("init")
        self.s.run("import", "H1")
        self.s.run("findings")
        out = self.s.run("check")
        self.assertNotIn("and no guard", out.stdout,
                         "живой экземпляр один — узда ещё не требуется")

    def test_команда_roots_показывает_состояние_классов(self):
        self._three_of_one_root()
        out = self.s.run("roots")
        self.assertIn("3 × рукописная копия предиката", out.stdout)
        self.assertIn("NO GUARD", out.stdout)

    # --------------------------------------------------------------------- размер

    def test_блок_который_за_сеанс_не_прочитать_роняет_проверку(self):
        self.s.write("src/huge.ts", "line\n" * 7000)
        self.s.blocks(paths=["src/huge.ts"])
        self.s.manifest(hypotheses=1)
        self.s.commit()
        self.s.run("init")
        self.s.run("coverage")
        out = self.s.run("check")
        self.assertIn("cannot be read in one session", out.stdout)

    def test_порог_размера_не_считает_исключённое(self):
        """Исключённый кодоген не должен требовать резать блок."""
        self.s.write("src/one.ts", "a\n")
        self.s.write("src/lock.json", "x\n" * 7000)
        self.s.blocks(paths=["src/one.ts", "src/lock.json"],
                      exclusions=[{"pattern": "src/lock.json", "reason": "сгенерировано"}])
        self.s.manifest(hypotheses=1)
        self.s.commit()
        self.s.run("init")
        self.s.run("coverage")
        out = self.s.run("check")
        self.assertNotIn("cannot be read in one session", out.stdout)

    def test_шаблон_который_ничего_не_нашёл_роняет_проверку(self):
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts", "src/nosuch.ts"])
        self.s.manifest(hypotheses=1)
        self.s.commit()
        self.s.run("init")
        out = self.s.run("check")
        self.assertIn("silently shrank", out.stdout)

    def test_шаблон_по_нетрекнутым_файлам_зовёт_git_add(self):
        """`npx skills add` кладёт файлы мимо индекса — без подсказки «не матчит» читается как
        «файлов нет», хотя они лежат на диске."""
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts", "vendor/**"])
        self.s.manifest(hypotheses=1)
        self.s.commit()
        self.s.write("vendor/tool.py", "x\n")
        self.s.run("init")
        out = self.s.run("check")
        self.assertIn("matches only untracked files (1)", out.stdout)
        self.assertIn("git add -- vendor/**", out.stdout)
        self.assertNotIn("silently shrank", out.stdout)

    # ------------------------------------------------------------- свежесть дерева

    def test_отставшее_от_сервера_дерево_роняет_проверку(self):
        """Устаревшее дерево показывает починенное как сломанное — гейт обязан это назвать."""
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=1)
        self.s.commit()

        bare = self.s.root.parent / (self.s.root.name + "-origin.git")
        subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)
        self.addCleanup(shutil.rmtree, bare, True)
        self.s.git("remote", "add", "origin", str(bare))
        self.s.git("push", "-q", "origin", "HEAD:refs/heads/master")
        self.s.git("symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/master")
        self.s.git("fetch", "-q", "origin")

        self.s.run("init")
        self.s.run("coverage")
        self.assertNotIn("behind", self.s.run("check").stdout,
                         "на свежем дереве жалоб быть не должно")

        # Сервер ушёл вперёд и починил то, про что мы собираемся написать находку.
        # Наша вершина при этом «двухнедельной давности»: устаревание меряется ВРЕМЕНЕМ,
        # а не числом коммитов — ветка, отведённая час назад, отстаёт на десяток коммитов
        # и не устарела ничуть.
        long_ago = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=14)).isoformat()
        env = dict(os.environ, GIT_COMMITTER_DATE=long_ago, GIT_AUTHOR_DATE=long_ago)
        subprocess.run(["git", "-C", str(self.s.root), "commit", "-q", "--amend",
                        "--no-edit", f"--date={long_ago}"], env=env, check=True,
                       capture_output=True)
        self.s.git("push", "-qf", "origin", "HEAD:refs/heads/master")
        self.s.git("fetch", "-q", "origin")
        self.s.write("src/one.ts", "a\nfixed\n")
        self.s.git("add", "src/one.ts")
        self.s.git("commit", "-qm", "починка на сервере")
        self.s.git("push", "-q", "origin", "HEAD:refs/heads/master")
        self.s.git("reset", "-q", "--hard", "HEAD~1")
        self.s.git("fetch", "-q", "origin")

        out = self.s.run("check")
        self.assertIn("behind", out.stdout)
        self.assertIn("days", out.stdout)
        self.assertIn("fetch", out.stdout, "отказ обязан говорить, что делать")

    def test_свежий_коммит_в_давней_ветке_не_прячет_устаревание(self):
        """Своя вершина новее чужой — а ветка всё равно без единого чужого исправления."""
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=1)
        self.s.commit()

        bare = self.s.root.parent / (self.s.root.name + "-origin2.git")
        subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)
        self.addCleanup(shutil.rmtree, bare, True)
        self.s.git("remote", "add", "origin", str(bare))

        # общий предок — двухнедельной давности
        long_ago = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=14)).isoformat()
        env = dict(os.environ, GIT_COMMITTER_DATE=long_ago, GIT_AUTHOR_DATE=long_ago)
        subprocess.run(["git", "-C", str(self.s.root), "commit", "-q", "--amend", "--no-edit",
                        f"--date={long_ago}"], env=env, check=True, capture_output=True)
        self.s.git("push", "-q", "origin", "HEAD:refs/heads/master")
        self.s.git("symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/master")

        # на сервере появилось чужое исправление, а у нас — свой свежий коммит рядом
        self.s.git("branch", "-q", "work")
        self.s.write("src/one.ts", "a\nчужое исправление\n")
        self.s.git("add", "src/one.ts")
        self.s.git("commit", "-qm", "чужое исправление")
        self.s.git("push", "-q", "origin", "HEAD:refs/heads/master")
        self.s.git("reset", "-q", "--hard", "work")
        self.s.write("src/one.ts", "a\nсвоя свежая правка\n")
        self.s.git("add", "src/one.ts")
        self.s.git("commit", "-qm", "своя свежая правка")
        self.s.git("fetch", "-q", "origin")

        self.s.run("init")
        self.s.run("coverage")
        out = self.s.run("check")
        self.assertIn("behind", out.stdout,
                      "ветка отведена две недели назад и не содержит чужих правок")

    # ---------------------------------------------------------------- размещение

    def test_корень_берётся_по_рабочему_каталогу(self):
        """Скилл лежит вне проекта — ревьюируется тот репозиторий, где запустили."""
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=1)
        self.s.commit()
        # У самого набора есть своё ревью (docs/review/ в репозитории скилла) — запуск в
        # чужом дереве не должен его ни создать, ни тронуть.
        kit_state = KIT / "docs" / "review" / "state.json"
        before = kit_state.read_bytes() if kit_state.exists() else None
        self.s.run("init")
        out = subprocess.run(["python3", str(TOOL), "status"], cwd=self.s.root / "src",
                             capture_output=True, text=True, check=False)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("H1", out.stdout, "из подкаталога — тот же корень")
        after = kit_state.read_bytes() if kit_state.exists() else None
        self.assertEqual(before, after, "состояние не должно уехать в репозиторий, где лежит скилл")

    def test_вне_репозитория_инструмент_отказывает(self):
        plain = Path(tempfile.mkdtemp(prefix="finetooth-plain-"))
        self.addCleanup(shutil.rmtree, plain, True)
        out = subprocess.run(["python3", str(TOOL), "status"], cwd=plain,
                             capture_output=True, text=True, check=False)
        self.assertEqual(out.returncode, 2)
        self.assertIn("git", out.stderr)
        self.assertEqual(subprocess.run(["python3", str(TOOL), "version"], cwd=plain,
                                        capture_output=True, text=True).returncode, 0,
                         "версию можно спросить откуда угодно")

    def test_шаблон_роли_из_скилла_и_проектная_замена(self):
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=1)
        self.s.commit()
        self.s.run("init")
        out = self.s.run("prompt", "H1", "--role", "hunter")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("ревьюер-охотник", out.stdout, "без своей копии — шаблон скилла")
        self.s.write("docs/review/prompts/hunter.md", "СВОЙ ШАБЛОН для {{BLOCK_ID}}\n")
        self.assertIn("СВОЙ ШАБЛОН для H1", self.s.run("prompt", "H1", "--role", "hunter").stdout)

    def test_подсказки_зовут_инструмент_как_его_зовёт_проект(self):
        self.s.write("src/one.ts", "a\n")
        self.s.write("src/lost.ts", "b\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=1)
        self.s.commit()
        self.s.run("init")
        out = self.s.run("coverage").stdout
        self.assertIn(f"python3 {TOOL}", out.replace("~/", str(Path.home()) + "/"),
                      "без поля cli подсказка называет настоящий путь к инструменту")
        bj = self.s.root / "docs/review/blocks.json"
        d = json.loads(bj.read_text(encoding="utf-8"))
        d["cli"] = "npm run review --"
        bj.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        self.assertIn("npm run review --", self.s.run("coverage").stdout)


class ParallelKitLessonsTest(unittest.TestCase):
    """Уроки второй версии набора у его автора (23.09.2026): пять дефектов нашей копии,
    род доказательства, названные файлы, ревьюер правок."""

    def setUp(self) -> None:
        self.s = Stand()
        self.addCleanup(self.s.cleanup)

    def _finding(self, file="src/one.ts", status="open", **extra) -> None:
        self.s.write("docs/review/reports/H1-findings.jsonl", json.dumps({
            "block": "H1", "severity": "high", "confidence": "confirmed", "status": status,
            "file": file, "claim": "дефект", "scenario": "сценарий", **extra},
            ensure_ascii=False) + "\n")

    def _rows(self) -> list[dict]:
        p = self.s.root / "docs/review/findings.jsonl"
        return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x]

    def _write_rows(self, rows: list[dict]) -> None:
        (self.s.root / "docs/review/findings.jsonl").write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")

    def test_починенная_находка_на_удалённом_файле_не_роняет_проверку(self):
        """Починенная находка — история; переименование файла после починки её не ломает."""
        self.s.write("src/one.ts", "a\n")
        self.s.write("src/keep.ts", "b\n")
        self.s.blocks(paths=["src"])
        self.s.manifest(hypotheses=1)
        self._finding()
        self.s.commit()
        self.s.run("init")
        self.s.run("import", "H1")
        self.s.write("src/one.ts", "починено\n")
        self.s.commit("починка")
        sha = self.s.git("rev-parse", "HEAD").stdout.strip()
        self.s.run("set-finding", "H1-001", "fixed", "--commit", sha)
        self.s.git("mv", "src/one.ts", "src/renamed.ts")
        self.s.commit("переименовали после починки")
        self.s.run("coverage")
        self.assertNotIn("is not in the repository", self.s.run("check").stdout)
        rows = self._rows(); rows[0]["status"] = "open"; rows[0].pop("code_sha", None)
        self._write_rows(rows)
        self.assertIn("is not in the repository", self.s.run("check").stdout,
                      "а открытая находка на пропавший файл — по-прежнему отказ")

    def test_отложенная_находка_требует_причину(self):
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=1)
        self._finding()
        self.s.commit()
        self.s.run("init")
        self.s.run("import", "H1")
        self.assertNotEqual(self.s.run("set-finding", "H1-001", "deferred").returncode, 0)
        out = self.s.run("set-finding", "H1-001", "deferred", "--reason", "ждёт блок H2")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(self._rows()[0]["defer_reason"], "ждёт блок H2")
        self.s.run("findings")
        self.assertNotIn("deferred without a reason", self.s.run("check").stdout)
        rows = self._rows(); rows[0].pop("defer_reason"); self._write_rows(rows)
        self.assertIn("deferred without a reason", self.s.run("check").stdout)

    def test_фазы_в_массиве_не_убывают(self):
        self.s.write("src/one.ts", "a\n")
        self.s.write("src/two.ts", "b\n")
        self.s.blocks(paths=["src/one.ts"])
        bj = self.s.root / "docs/review/blocks.json"
        d = json.loads(bj.read_text(encoding="utf-8"))
        d["blocks"].insert(0, {"id": "V2", "slug": "late", "phase": 2, "title": "Поздний",
                                "role": "r", "goal": "g", "paths": ["src/two.ts"], "ref_paths": []})
        bj.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        self.s.commit()
        self.s.run("init")
        self.assertIn("phase 1 comes after phase 2", self.s.run("check").stdout)

    def test_заблокированный_блок_не_значит_закончено(self):
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=1)
        self.s.commit()
        self.s.run("init")
        self.s.run("set-status", "H1", "blocked")
        self.assertIn("blocked without a note", self.s.run("check").stdout)
        self.s.run("set-status", "H1", "blocked", "--note", "ждёт стенда")
        self.assertNotIn("blocked without a note", self.s.run("check").stdout)
        out = self.s.run("status").stdout
        self.assertIn("review is NOT finished", out)
        self.assertNotIn("all blocks closed", out)
        self.assertIn("ждёт стенда", out)

    def test_время_running_считается_от_последнего_старта(self):
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=1)
        self.s.commit()
        self.s.run("init")
        self.s.run("set-status", "H1", "running")
        st_path = self.s.root / "docs/review/state.json"
        st = json.loads(st_path.read_text(encoding="utf-8"))
        st["blocks"]["H1"]["started"] = "2026-01-01T00:00:00Z"
        st_path.write_text(json.dumps(st), encoding="utf-8")
        self.s.write("docs/review/reports/H1-demo.hunter.md", "# охотник\n")
        self.s.run("set-status", "H1", "hunted")
        self.s.run("set-status", "H1", "running")
        self.assertNotIn("stuck in running", self.s.run("check").stdout,
                         "блок, возвращённый в работу, не завис")

    def test_измеряемый_блок_не_подчиняется_порогу_и_получает_своё_правило(self):
        self.s.write("src/big.ts", "x\n" * 150)
        self.s.blocks(paths=["src/big.ts"], readable_lines=100, proof="measured")
        self.s.manifest(hypotheses=1)
        self.s.commit()
        self.s.run("init")
        self.assertNotIn("cannot be read in one session", self.s.run("check").stdout)
        out = self.s.run("sizes")
        self.assertEqual(out.returncode, 0, out.stdout)
        self.assertIn("measured", out.stdout)
        self.assertIn("артефактами, а не чтением", self.s.run("prompt", "H1", "--role", "hunter").stdout)
        self.assertIn("пересобери", self.s.run("prompt", "H1", "--role", "verify").stdout)
        self.assertNotIn("прочитать все", self.s.run("prompt", "H1", "--role", "hunter").stdout)

    def test_читаемый_блок_выше_порога_виден_в_sizes(self):
        self.s.write("src/big.ts", "x\n" * 150)
        self.s.blocks(paths=["src/big.ts"], readable_lines=100)
        self.s.manifest(hypotheses=1)
        self.s.commit()
        self.s.run("init")
        out = self.s.run("sizes")
        self.assertEqual(out.returncode, 1)
        self.assertIn("above the ceiling", out.stdout)

    def test_блок_без_файлов_получает_правило_живого_стенда(self):
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=[])
        self.s.manifest(hypotheses=1)
        self.s.commit()
        self.s.run("init")
        out = self.s.run("prompt", "H1", "--role", "hunter").stdout
        self.assertIn("запущенной системе", out)
        self.assertNotIn("(0 шт.)", out)

    def test_каждый_файл_блока_назван_полным_путём(self):
        """«Прочитано 25 из 25» — слово агента; проверяется список полных путей."""
        self.s.write("src/a/page.tsx", "a\n")
        self.s.write("src/b/page.tsx", "b\n")
        self.s.write("src/vendor.min.js", "m\n")
        self.s.blocks(paths=["src"], named_files=True,
                      exclusions=[{"pattern": "src/vendor.min.js", "reason": "сборка"}])
        self.s.manifest(hypotheses=1)
        self.s.reports(hunter="# охотник\n## Гипотезы\n- H1.1 — проверена: да\n"
                              "## Прочитано\n- page.tsx\n## Ограничения охвата\nнет\n",
                       verify=FULL_VERIFY)
        self.s.commit()
        self.s.run("init")
        self.s.run("coverage")
        self.s.run("set-status", "H1", "verified")
        out = self.s.run("check").stdout
        self.assertIn("not named by full path", out)
        self.assertIn("src/a/page.tsx", out, "базового имени мало — одноимённых файлов много")
        self.assertNotIn("vendor.min.js", out, "исключённое называть не требуется")
        self.s.reports(hunter="# охотник\n## Гипотезы\n- H1.1 — проверена: да\n"
                              "## Прочитано\n- src/a/page.tsx\n## Ограничения охвата\n"
                              "не дочитал src/b/page.tsx\n")
        self.assertNotIn("not named by full path", self.s.run("check").stdout,
                         "названное в ограничениях охвата — тоже названное")

    def test_ревьюер_правок_получает_дифф_и_своё_имя_отчёта(self):
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=1)
        self.s.commit()
        self.s.run("init")
        out = self.s.run("prompt", "H1", "--role", "fixreview")
        self.assertEqual(out.returncode, 2, "без диффа — отказ, а не трассировка: " + out.stderr)
        self.assertIn("--diff", out.stderr, "отказ обязан говорить, что делать")
        base = self.s.git("rev-parse", "HEAD").stdout.strip()
        self.s.write("src/one.ts", "a\nпочинено\n")
        self.s.commit("починка")
        out = self.s.run("prompt", "H1", "--role", "fixreview", "--diff", f"{base}...HEAD",
                         "--round", "2", "--scope", "backend")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("+починено", out.stdout, "дифф вклеен целиком")
        self.assertIn("H1-demo.fixreview-2-backend.md", out.stdout)
        self.assertIn("H1-demo.fix-2.md", out.stdout, "отчёт исполнителя того же круга")
        self.assertIn("**backend**", out.stdout)
        self.assertNotIn("{{", out.stdout.split("````diff")[0], "все подстановки заполнены")

    def test_закрытие_с_починками_требует_ревью_правок(self):
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=1)
        self._finding()
        self.s.reports(hunter="# охотник\n## Гипотезы\n- H1.1 — проверена: да\n"
                              "## Ограничения охвата\nнет\n", verify=FULL_VERIFY)
        self.s.commit()
        self.s.run("init")
        self.s.run("coverage")
        self.s.run("import", "H1")
        self.s.write("src/one.ts", "починено\n")
        self.s.commit("починка")
        sha = self.s.git("rev-parse", "HEAD").stdout.strip()
        self.s.run("set-finding", "H1-001", "fixed", "--commit", sha)
        self.s.run("coverage")
        self.s.run("set-status", "H1", "closed")
        self.assertIn("no fix reviewer report", self.s.run("check").stdout)
        self.s.write("docs/review/reports/H1-demo.fixreview-1.md", "# ревью правок\nнаходок нет\n")
        self.assertNotIn("no fix reviewer report", self.s.run("check").stdout)

    def test_незаполненная_подстановка_в_шаблоне_роняет_prompt(self):
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=1)
        self.s.write("docs/review/prompts/hunter.md", "Блок {{BLOCK_ID}}, ещё {{NOPE}}\n")
        self.s.commit()
        self.s.run("init")
        out = self.s.run("prompt", "H1", "--role", "hunter")
        self.assertEqual(out.returncode, 2)
        self.assertIn("{{NOPE}}", out.stderr)

    def test_inventory_показывает_дерево_и_ничьих(self):
        self.s.write("src/a/one.ts", "1\n2\n")
        self.s.write("src/b/two.ts", "1\n")
        self.s.write("lib/x.ts", "1\n")
        (self.s.root / "src/a/pic.png").write_bytes(b"\x89PNG\0\0binary\n\n")
        self.s.blocks(paths=["src/a"])
        self.s.commit()
        self.s.run("init")
        out = self.s.run("inventory", "--depth", "2").stdout
        self.assertRegex(out, r"src/a\s+2\s+2\s+1\s+0\s+H1", "бинарник в счёт строк не идёт")
        self.assertRegex(out, r"lib\s+1\s+1\s+0\s+1\s+—")
        self.assertIn("unowned: 2", out)

    def test_coverage_без_записи_не_трогает_карту(self):
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src"])
        self.s.commit()
        self.s.run("init")
        self.s.run("coverage")
        cov = self.s.root / "docs/review/coverage.tsv"
        before = cov.read_text(encoding="utf-8")
        self.s.write("src/two.ts", "b\n")
        self.s.commit("новый файл блока")
        out = self.s.run("coverage", "--no-write")
        self.assertEqual(out.returncode, 0, out.stdout)
        self.assertEqual(cov.read_text(encoding="utf-8"), before,
                         "новый файл блока не должен попасть в карту без записи")
        self.s.write("lib/orphan.ts", "c\n")
        self.s.commit("ничей файл")
        self.assertEqual(self.s.run("coverage", "--no-write").returncode, 1,
                         "ворота обязаны краснеть на ничьем файле")

    def test_set_finding_переводит_несколько_находок(self):
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=1)
        self.s.write("docs/review/reports/H1-findings.jsonl", "".join(json.dumps({
            "block": "H1", "severity": "low", "confidence": "confirmed", "status": "open",
            "file": "src/one.ts", "claim": f"дефект {i}", "scenario": "сценарий"},
            ensure_ascii=False) + "\n" for i in (1, 2)))
        self.s.commit()
        self.s.run("init")
        self.s.run("import", "H1")
        out = self.s.run("set-finding", "H1-001", "H1-002", "deferred", "--reason", "ждёт H2")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual([r["status"] for r in self._rows()], ["deferred", "deferred"])


class LanguageTest(unittest.TestCase):
    """Язык ревью: английский по умолчанию, русский по полю `lang`; разбор отчётов
    понимает оба языка, сообщения инструмента — всегда английские."""

    def setUp(self) -> None:
        self.s = Stand()
        self.addCleanup(self.s.cleanup)

    def _block(self, lang: str) -> None:
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"], lang=lang)
        self.s.manifest(hypotheses=1)
        self.s.commit()
        self.s.run("init")
        self.s.run("coverage")

    def test_шаблон_роли_по_языку_проекта(self):
        self._block("en")
        out = self.s.run("prompt", "H1", "--role", "hunter").stdout
        self.assertIn("You are a hunter reviewer", out)
        self.assertIn("Read EVERY file", out, "правило 1 — на языке ревью")
        self.assertNotIn("Прочитай", out)
        self._block("ru")
        out = self.s.run("prompt", "H1", "--role", "hunter").stdout
        self.assertIn("ревьюер-охотник", out)
        self.assertIn("Прочитай КАЖДЫЙ файл", out)

    def test_без_поля_lang_язык_английский(self):
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"], lang="en")
        bj = self.s.root / "docs/review/blocks.json"
        d = json.loads(bj.read_text(encoding="utf-8")); d.pop("lang")
        bj.write_text(json.dumps(d), encoding="utf-8")
        self.s.manifest(hypotheses=1)
        self.s.commit()
        self.s.run("init")
        self.assertIn("You are a hunter reviewer", self.s.run("prompt", "H1").stdout)

    def test_setup_заводит_ревью_на_выбранном_языке(self):
        self.s.write("app.ts", "x\n")
        self.s.commit()
        out = self.s.run("setup", "--lang", "ru", "--project", "Демо")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("# Инварианты Демо", (self.s.root / "docs/review/invariants.md").read_text(encoding="utf-8"))
        self.assertIn("# Сплошное ревью Демо", (self.s.root / "docs/review/README.md").read_text(encoding="utf-8"))
        self.assertEqual(json.loads((self.s.root / "docs/review/blocks.json").read_text(encoding="utf-8"))["lang"], "ru")
        shutil.rmtree(self.s.root / "docs/review")
        out = self.s.run("setup", "--project", "Demo")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("# Demo invariants", (self.s.root / "docs/review/invariants.md").read_text(encoding="utf-8"))
        self.assertIn("# Whole-repository review of Demo", (self.s.root / "docs/review/README.md").read_text(encoding="utf-8"))
        self.assertNotEqual(self.s.run("setup", "--lang", "de").returncode, 0)

    def test_английский_отчёт_разбирается(self):
        self._block("en")
        self.s.reports(hunter="# H1 — hunter report\n## Hypotheses\n- H1.1 — checked: ran it\n"
                              "## Coverage limits\nnothing skipped\n",
                       verify="# verifier report\n## Verdicts on hunter findings\nno findings\n"
                              "## Block coverage status\nComplete: both files read.\n")
        self.s.run("set-status", "H1", "verified")
        out = self.s.run("check")
        self.assertEqual(out.returncode, 0, out.stdout)
        self.assertRegex(self.s.run("hypotheses", "H1").stdout, r"H1\.1\s+checked")

    def test_английские_заглушки_шаблона_ловятся(self):
        self._block("en")
        self.s.reports(hunter="# H1 — hunter report\n## Hypotheses\n- H1.1 — not checked: no stand\n"
                              "## Coverage limits\n**Mandatory section, even if it is short.**\n",
                       verify="# verifier report\n## Verdicts on hunter findings\nno findings\n"
                              "## Block coverage status\nComplete / incomplete — and what exactly remains.\n")
        self.s.run("set-status", "H1", "verified")
        out = self.s.run("check").stdout
        self.assertIn("section of the hunter report is empty", out, out)
        self.assertIn("has no coverage verdict", out, out)

    def test_findings_md_и_дневник_на_языке_ревью(self):
        self._block("en")
        self.s.write("docs/review/reports/H1-findings.jsonl", json.dumps({
            "block": "H1", "severity": "low", "confidence": "confirmed", "status": "open",
            "file": "src/one.ts", "claim": "defect", "scenario": "scenario"}) + "\n")
        self.s.run("import", "H1")
        self.s.run("findings")
        md = (self.s.root / "docs/review/findings.md").read_text(encoding="utf-8")
        self.assertIn("# Review findings", md)
        self.assertIn("| id | block | status |", md)
        self.s.run("log", "H1", "decided")
        self.assertIn("# Review journal", (self.s.root / "docs/review/journal.md").read_text(encoding="utf-8"))

    def test_сообщения_инструмента_английские_при_русском_ревью(self):
        self._block("ru")
        self.s.write("src/lost.ts", "b\n")
        self.s.commit("unowned")
        out = self.s.run("coverage").stdout
        self.assertIn("NOT COVERED", out)
        self.assertNotIn("НЕ ПОКРЫТО", out)


class SkillFormatTest(unittest.TestCase):
    """Скилл по спецификации agentskills.io — то, что проверяет `skills-ref validate`,
    плюс то, чего он не проверяет, но что ломает установку."""

    def frontmatter(self) -> dict[str, str]:
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\n"), "SKILL.md начинается с YAML-шапки")
        head = text.split("---\n", 2)[1]
        return {k.strip(): v.strip() for k, _, v in
                (ln.partition(":") for ln in head.splitlines() if ln and not ln.startswith(" "))}

    def test_имя_по_правилам_и_равно_каталогу(self):
        name = self.frontmatter()["name"]
        self.assertRegex(name, r"^[a-z0-9]+(-[a-z0-9]+)*$")
        self.assertLessEqual(len(name), 64)
        self.assertEqual(name, SKILL.name, "имя обязано совпадать с каталогом скилла")

    def test_описание_в_пределах(self):
        desc = self.frontmatter()["description"]
        self.assertTrue(0 < len(desc) <= 1024, len(desc))

    def test_тело_короче_пятисот_строк(self):
        self.assertLess(len((SKILL / "SKILL.md").read_text(encoding="utf-8").splitlines()), 500)

    def test_ссылки_из_skill_md_ведут_на_файлы_скилла(self):
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        for target in re.findall(r"\]\(([^)#]+)\)", text):
            if "://" in target:
                continue
            self.assertTrue((SKILL / target).exists(), target)

    def test_версия_в_шапке_равна_версии_инструмента(self):
        tool = TOOL.read_text(encoding="utf-8")
        ver = re.search(r'^VERSION = "([^"]+)"', tool, re.M).group(1)
        self.assertIn(f'version: "{ver}"', (SKILL / "SKILL.md").read_text(encoding="utf-8"))

    def test_лицензия_в_скилле_та_же_что_в_репозитории(self):
        """При установке уезжает только папка скилла — условия обязаны ехать с ней."""
        self.assertEqual((SKILL / "LICENSE").read_bytes(), (KIT / "LICENSE").read_bytes())

    def test_поле_лицензии_это_её_обозначение_и_ничего_сверх(self):
        """Шапку скилла читает тот, кто решает, можно ли его ставить. Пока в поле стояла
        проза («MIT на правки; основа передана без лицензии»), она пережила смену самой
        лицензии и утверждала обратное тому, что написано в LICENSE. Обозначение берётся
        из LICENSE, так что поле не разъедется с ним и в следующий раз."""
        first = (KIT / "LICENSE").read_text(encoding="utf-8").splitlines()[0].strip()
        spdx = re.fullmatch(r"([A-Za-z0-9.+-]+) License", first)
        self.assertTrue(spdx, f"первая строка LICENSE не называет лицензию: {first!r}")
        self.assertEqual(self.frontmatter()["license"], spdx.group(1))


class SetupTest(unittest.TestCase):
    """`setup` заводит ревью в проекте; инструмент при этом остаётся в скилле."""

    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="finetooth-install-"))
        self.addCleanup(shutil.rmtree, self.root, True)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        for k, v in (("user.email", "t@example.com"), ("user.name", "t")):
            subprocess.run(["git", "-C", str(self.root), "config", k, v], check=True)
        (self.root / "app.ts").write_text("x\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.root), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(self.root), "commit", "-qm", "init"], check=True)

    def install(self, *extra: str) -> subprocess.CompletedProcess:
        return subprocess.run(["python3", str(TOOL), "setup", *extra], cwd=self.root,
                              capture_output=True, text=True, check=False)

    def test_после_setup_инструмент_работает_и_советует_команду_проекта(self):
        out = self.install("--cli", "npm run review --", "--project", "Демо")
        self.assertEqual(out.returncode, 0, out.stderr)
        for rel in ("docs/review/README.md", "docs/review/blocks.json", "docs/review/invariants.md"):
            self.assertTrue((self.root / rel).exists(), rel)
        self.assertFalse((self.root / "scripts" / "review").exists(),
                         "инструмент живёт в скилле, в проект он не копируется")
        self.assertFalse((self.root / "docs" / "review" / "prompts").exists(),
                         "шаблоны ролей берутся из скилла, своя копия — только по желанию")
        readme = (self.root / "docs/review/README.md").read_text(encoding="utf-8")
        self.assertIn("npm run review -- status", readme)
        self.assertNotIn("{{", readme, "в точке входа не осталось подстановок")
        bj = json.loads((self.root / "docs/review/blocks.json").read_text(encoding="utf-8"))
        self.assertEqual(bj["cli"], "npm run review --")
        ver = re.search(r'^VERSION = "([^"]+)"', TOOL.read_text(encoding="utf-8"), re.M).group(1)
        self.assertEqual(bj["kit_version"], ver)

        run = lambda *a: subprocess.run(["python3", str(TOOL), *a], cwd=self.root,
                                        capture_output=True, text=True)
        self.assertEqual(run("init").returncode, 0)
        cov = run("coverage")
        self.assertEqual(cov.returncode, 1, "непокрытый файл обязан ронять карту")
        self.assertIn("npm run review --", cov.stdout, "советует команду проекта, а не свою")

    def test_скилл_внутри_проекта_не_роняет_покрытие(self):
        """Скилл коммитят в проект ради CI — его файлы не предмет ревью."""
        inside = self.root / ".claude" / "skills" / "finetooth"
        shutil.copytree(SKILL, inside, ignore=shutil.ignore_patterns("__pycache__"))
        subprocess.run(["git", "-C", str(self.root), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(self.root), "commit", "-qm", "скилл в проекте"], check=True)
        tool = inside / "scripts" / "review.py"
        run = lambda *a: subprocess.run(["python3", str(tool), *a], cwd=self.root,
                                        capture_output=True, text=True)
        self.assertEqual(run("setup").returncode, 0)
        run("init")
        out = run("coverage").stdout
        self.assertIn("NOT COVERED: 1 files", out,
                      "непокрыт только предмет ревью, а не два десятка файлов скилла: " + out)
        self.assertIn("\n  app.ts\n", out)
        self.assertIn("python3 .claude/skills/finetooth/scripts/review.py", out,
                      "подсказка — относительным путём внутри проекта")

    def test_setup_предупреждает_про_байткод(self):
        out = self.install()
        self.assertIn("__pycache__", out.stdout, "без правила байткод уезжает в коммит")
        (self.root / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
        out = self.install()
        self.assertNotIn(".gitignore has no", out.stdout)

    def test_повторный_setup_не_затирает_работу(self):
        self.install("--cli", "npm run review --")
        marker = "# правила именно этого проекта\n"
        inv = self.root / "docs" / "review" / "invariants.md"
        inv.write_text(marker, encoding="utf-8")
        out = self.install("--cli", "make review")
        self.assertEqual(inv.read_text(encoding="utf-8"), marker, "инварианты затёрты")
        self.assertIn("already exists", out.stdout)
        bj = json.loads((self.root / "docs/review/blocks.json").read_text(encoding="utf-8"))
        self.assertEqual(bj["cli"], "npm run review --",
                         "повторный запуск не должен менять уже настроенное определение")


class ReportShapeTest(unittest.TestCase):
    """Разбор отчёта: форма — не смысл.

    Вердикт гипотезы, оценка охвата и «файл назван в отчёте» читались по форме текста:
    слово в ограде кода, слово в обратных кавычках, номер строки таблицы, путь внутри
    другого пути. Каждый тест парный: запрещённое больше не проходит, разрешённое —
    по-прежнему проходит.
    """

    def setUp(self) -> None:
        self.s = Stand()
        self.addCleanup(self.s.cleanup)

    def _stand(self, hunter: str, hypotheses: int = 1, manifest: str | None = None) -> None:
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        if manifest is None:
            self.s.manifest(hypotheses=hypotheses)
        else:
            self.s.write("docs/review/blocks/H1-demo.md", manifest)
        self.s.reports(hunter=hunter, verify=FULL_VERIFY)
        self.s.commit()
        self.s.run("init")
        self.s.run("coverage")

    LIMITS = "\n## Ограничения охвата\nнет\n"

    def test_вердикт_внутри_ограды_кода_не_вердикт(self):
        """Шаблон роли отдаёт агенту образец строки вердикта внутри ```-ограды, с уже
        подставленным номером блока. Отчёт, который перенёс образец и не ответил ничего,
        закрывал все гипотезы блока, и `check` печатал «состояние согласовано»."""
        self._stand("# охотник\n\n## Гипотезы\n\nОтветов ниже нет.\n\n"
                    "```markdown\n- H1.1 — проверена: <чем именно доказано>\n```\n"
                    + self.LIMITS)
        out = self.s.run("hypotheses", "H1").stdout
        self.assertIn("NO VERDICT", out)
        self.assertIn("closed 0/1", out)

    def test_вердикт_вне_ограды_по_прежнему_вердикт(self):
        self._stand("# охотник\n\n## Гипотезы\n- H1.1 — проверена: прогнал на матрице.\n"
                    "```markdown\n- H1.1 — не проверена: образец\n```\n" + self.LIMITS)
        out = self.s.run("hypotheses", "H1").stdout
        self.assertRegex(out, r"H1\.1\s+checked")
        self.assertIn("closed 1/1", out)
        self.assertNotIn("different verdicts", self.s.run("check").stdout)

    def test_вердикт_внутри_отступа_или_цитаты_не_вердикт(self):
        """Ограда — одна из четырёх форм, которыми markdown цитирует образец. Отчёт,
        пересказавший своё задание блоком с отступом, цитатой `>` или html-комментарием,
        закрывал гипотезы, не ответив ни на одну."""
        for name, body in (
                ("отступ", "Ответов ниже нет.\n\n    - H1.1 — проверена: <чем доказано>\n"),
                ("цитата", "Ответов ниже нет.\n\n> - H1.1 — проверена: <чем доказано>\n"),
                ("комментарий", "Ответов ниже нет.\n\n<!-- - H1.1 — проверена: образец -->\n")):
            with self.subTest(форма=name):
                self._stand("# охотник\n\n## Гипотезы\n\n" + body + self.LIMITS)
                out = self.s.run("hypotheses", "H1").stdout
                self.assertIn("NO VERDICT", out)
                self.assertIn("closed 0/1", out)

    def test_вердикт_под_своей_гипотезой_с_отступом_по_прежнему_вердикт(self):
        """Обратная сторона: доказательство отчёт пишет вложенным списком под гипотезой, и
        такой отступ — продолжение пункта, а не образец. Считать его цитатой значит
        покраснеть на честном отчёте."""
        self._stand("# охотник\n\n## Гипотезы\n\n"
                    "- Разбор вердиктов\n"
                    "    - H1.1 — проверена: матрица из 21 входа, все совпали.\n"
                    + self.LIMITS)
        out = self.s.run("hypotheses", "H1").stdout
        self.assertRegex(out, r"H1\.1\s+checked")
        self.assertIn("closed 1/1", out)

    def test_ограда_внутри_пункта_списка_остаётся_оградой(self):
        """Ограду искали не дальше трёх пробелов от поля, а отчёт вкладывает её в пункт
        списка — там она начинается с четвёртого и дальше. Перенесённый в такой пункт
        образец из задания закрывал все гипотезы блока, и `check` печатал «состояние
        согласовано»."""
        self._stand("# охотник\n\n## Гипотезы\n\n"
                    "- Задание просило написать вердикт так:\n\n"
                    "    ```markdown\n"
                    "    - H1.1 — проверена: <чем доказано>\n"
                    "    - H1.2 — проверена: <чем доказано>\n"
                    "    ```\n\n"
                    "Ни на одну гипотезу я не ответил.\n" + self.LIMITS, hypotheses=2)
        out = self.s.run("hypotheses", "H1").stdout
        self.assertIn("NO VERDICT", out)
        self.assertIn("closed 0/2", out)

    def test_вердикт_после_вложенной_ограды_по_прежнему_вердикт(self):
        """Обратная сторона: вложенная ограда закрывается на своём месте, и написанное
        ниже остаётся словами отчёта, а не продолжением образца."""
        self._stand("# охотник\n\n## Гипотезы\n\n"
                    "- Образец из задания:\n\n"
                    "    ```markdown\n"
                    "    - H1.1 — проверена: <чем доказано>\n"
                    "    ```\n\n"
                    "- H1.1 — не проверена: не дошёл до матрицы входов.\n" + self.LIMITS)
        out = self.s.run("hypotheses", "H1").stdout
        self.assertRegex(out, r"H1\.1\s+not checked")
        self.assertIn("closed 1/1", out)

    def test_слово_вердикта_в_обратных_кавычках_цитата(self):
        """«в отчёте написано `не проверена`, а на деле я проверил» — цитата слова."""
        self._stand("# охотник\n## Гипотезы\n"
                    "- H1.1 — в отчёте написано `не проверена`, хотя всё осмотрено.\n"
                    + self.LIMITS)
        self.assertIn("NO VERDICT", self.s.run("hypotheses", "H1").stdout)

    def test_вся_строка_вердикта_в_кавычках_остаётся_вердиктом(self):
        """Живой отчёт пишет вердикт моноширинным целиком — это вердикт, а не цитата."""
        self._stand("# охотник\n## Гипотезы\n"
                    "- `H1.1 — проверена: посчитано, а не на глаз.`\n" + self.LIMITS)
        self.assertRegex(self.s.run("hypotheses", "H1").stdout, r"H1\.1\s+checked")

    def test_путь_с_n_a_в_кавычках_не_делает_гипотезу_неприменимой(self):
        self._stand("# охотник\n## Гипотезы\n"
                    "- H1.1 — маркер `n/a` внутри пути обработан; проверена тестом.\n"
                    + self.LIMITS)
        out = self.s.run("hypotheses", "H1").stdout
        self.assertRegex(out, r"H1\.1\s+checked")
        self.assertNotIn("not applicable", out)

    def test_нумерованная_таблица_вне_раздела_гипотез_не_вердикт(self):
        """Таблица «ворота → тест → мутация», которую требует сам критерий приёмки,
        закрывала гипотезы 1 и 2 вердиктами своих строк: вторая гипотеза, о которой в
        отчёте не сказано ни слова, считалась закрытой строкой про словарь статусов."""
        self._stand("# охотник\n## Гипотезы\n- H1.1 — проверена: да\n"
                    "## Ворота\n"
                    "| 1 | состояние против определения | нет | подтверждена |\n"
                    "| 2 | словарь статусов | test_x | не проверена |\n" + self.LIMITS,
                    hypotheses=2)
        hyp = self.s.run("hypotheses", "H1").stdout
        self.assertRegex(hyp, r"H1\.2\s+NO VERDICT", hyp)
        self.assertIn("closed 1/2", hyp)
        self.s.run("set-status", "H1", "verified")
        out = self.s.run("check").stdout
        self.assertIn("hypotheses without a verdict", out)
        self.assertNotIn("different verdicts", out)

    def test_таблица_названная_гипотезами_по_прежнему_читается(self):
        self._stand("# охотник\n## Итог\n| # | гипотеза | итог |\n|---|---|---|\n"
                    "| 1 | предикат | опровергнута |\n" + self.LIMITS)
        self.assertRegex(self.s.run("hypotheses", "H1").stdout, r"H1\.1\s+checked")

    def test_тильда_ограда_в_манифесте_не_обрывает_гипотезы(self):
        """`~~~`-ограда была невидима: заголовок внутри неё обрезал раздел, и гипотезы
        ниже исчезали из счёта и из отпечатка."""
        manifest = ("# H1 — Демоблок\n\n## Зачем\n\nПроверить, что оснастка ведёт себя так,"
                    " как обещает, и что раздел гипотез читается целиком.\n\n"
                    "## Гипотезы\n"
                    "1. Первая гипотеза о предикате и его граничных значениях.\n"
                    "2. Вторая гипотеза о том же коде, тоже достаточно длинная.\n\n"
                    "~~~markdown\n# заголовок внутри ограды\n~~~\n\n"
                    "3. Третья гипотеза, которая раньше пропадала.\n"
                    "4. Четвёртая гипотеза, которая пропадала вместе с ней.\n\n"
                    "## Критерий приёмки\n\nТаблица по каждой гипотезе.\n")
        self._stand("# охотник\n## Гипотезы\n- H1.1 — проверена: да\n" + self.LIMITS,
                    manifest=manifest)
        out = self.s.run("hypotheses", "H1").stdout
        for h in ("H1.1", "H1.2", "H1.3", "H1.4"):
            self.assertIn(h, out)
        self.assertIn("closed 1/4", out)

    def test_заголовок_внутри_тильда_ограды_не_понижается_в_промпте(self):
        manifest = ("# H1 — Демоблок\n\n## Зачем\n\nДостаточно длинный абзац, чтобы манифест"
                    " не считался куцым, и ограда ниже осталась оградой.\n\n"
                    "~~~\n# это комментарий примера, а не заголовок\n~~~\n\n"
                    "## Гипотезы\n1. Первая гипотеза о предикате и граничных значениях.\n\n"
                    "## Критерий приёмки\n\nТаблица.\n")
        self._stand("# охотник\n## Гипотезы\n- H1.1 — проверена: да\n" + self.LIMITS,
                    manifest=manifest)
        out = self.s.run("prompt", "H1", "--role", "hunter").stdout
        self.assertIn("\n# это комментарий примера, а не заголовок\n", out)
        self.assertNotIn("\n## это комментарий примера", out)

    def test_завершил_проверку_не_оценка_охвата(self):
        """Гейт требует сказать, что осталось непросмотренным; «я завершил проверку»
        отвечает на другой вопрос — и удовлетворял его словом внутри «завершил»."""
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"], lang="en")
        self.s.manifest(hypotheses=1)
        self.s.reports(hunter="# hunter\n## Hypotheses\n- H1.1 — checked: yes\n"
                              "## Coverage limits\nnothing\n",
                       verify="# verify\n\nI completed the check of every finding; "
                              "nothing was confirmed.\n")
        self.s.commit()
        self.s.run("init")
        self.s.run("coverage")
        self.s.run("set-status", "H1", "verified")
        out = self.s.run("check")
        self.assertEqual(out.returncode, 1)
        self.assertIn("no coverage verdict", out.stdout)

    def test_честная_оценка_охвата_принимается_на_обоих_языках(self):
        for lang, body in (("en", "# verify\n\nVerdicts: none.\n\nCoverage is complete: "
                                  "both files were read.\n"),
                           ("ru", "# проверяющий\n\nВердиктов нет.\n\n"
                                  "Проверка проведена полностью, непрочитанного не осталось.\n")):
            with self.subTest(lang=lang):
                s = Stand()
                self.addCleanup(s.cleanup)
                s.write("src/one.ts", "a\n")
                s.blocks(paths=["src/one.ts"], lang=lang)
                s.manifest(hypotheses=1)
                s.reports(hunter="# охотник\n## Гипотезы\n- H1.1 — проверена: да\n"
                                 "## Ограничения охвата\nнет\n", verify=body)
                s.commit()
                s.run("init")
                s.run("coverage")
                s.run("set-status", "H1", "verified")
                out = s.run("check")
                self.assertNotIn("no coverage verdict", out.stdout)

    def test_соседний_файл_с_тем_же_началом_не_закрывает_гейт_имён(self):
        """Отчёт назвал `src/api.ts.snap` — и `src/api.ts` считался названным."""
        self.s.write("src/api.ts", "a\n")
        self.s.write("src/api.ts.snap", "snap\n")
        self.s.blocks(paths=["src"], named_files=True)
        self.s.manifest(hypotheses=1)
        self.s.reports(hunter="# охотник\n## Прочитано\nsrc/api.ts.snap\n"
                              "## Гипотезы\n- H1.1 — проверена: да\n"
                              "## Ограничения охвата\nнет\n", verify=FULL_VERIFY)
        self.s.commit()
        self.s.run("init")
        self.s.run("coverage")
        self.s.run("set-status", "H1", "verified")
        out = self.s.run("check")
        self.assertEqual(out.returncode, 1)
        self.assertIn("src/api.ts", out.stdout)
        self.assertIn("not named by full", out.stdout)

    def test_названный_файл_в_конце_предложения_засчитывается(self):
        """Точка после пути — конец фразы, а не более длинный путь."""
        self.s.write("src/api.ts", "a\n")
        self.s.write("src/api.ts.snap", "snap\n")
        self.s.blocks(paths=["src"], named_files=True)
        self.s.manifest(hypotheses=1)
        self.s.reports(hunter="# охотник\n## Прочитано\nПрочитал `src/api.ts`, "
                              "а также src/api.ts.snap.\n"
                              "## Гипотезы\n- H1.1 — проверена: да\n"
                              "## Ограничения охвата\nнет\n", verify=FULL_VERIFY)
        self.s.commit()
        self.s.run("init")
        self.s.run("coverage")
        self.s.run("set-status", "H1", "verified")
        out = self.s.run("check")
        self.assertNotIn("not named by full", out.stdout)

    def test_путь_с_приставкой_точки_или_заголовка_диффа_засчитывается(self):
        """`./src/api.ts` и `a/src/api.ts` — тот же путь, написанный иначе: первое агент
        пишет по привычке, второе приходит из вставленного заголовка диффа. Отказ оставлял
        честный полный отчёт без починки, кроме переписывания путей."""
        self.s.write("src/api.ts", "a\n")
        self.s.write("src/util.ts", "u\n")
        self.s.blocks(paths=["src"], named_files=True)
        self.s.manifest(hypotheses=1)
        self.s.reports(hunter="# охотник\n## Прочитано\n- ./src/api.ts\n- --- a/src/util.ts\n"
                              "## Гипотезы\n- H1.1 — проверена: да\n"
                              "## Ограничения охвата\nнет\n", verify=FULL_VERIFY)
        self.s.commit()
        self.s.run("init")
        self.s.run("coverage")
        self.s.run("set-status", "H1", "verified")
        out = self.s.run("check")
        self.assertNotIn("not named by full", out.stdout)
        self.assertEqual(out.returncode, 0, out.stdout)

    def test_приставка_не_делает_названным_файл_из_другого_каталога(self):
        """Обратная сторона: приставка засчитывается только там, где она сама начинает
        путь. `docs/src/api.ts` и `lib/a/src/api.ts` — другие файлы, а не тот же."""
        self.s.write("src/api.ts", "a\n")
        self.s.write("docs/src/api.ts", "d\n")
        self.s.write("lib/a/src/api.ts", "l\n")
        self.s.blocks(paths=["src"], named_files=True)
        self.s.manifest(hypotheses=1)
        self.s.reports(hunter="# охотник\n## Прочитано\n- docs/src/api.ts\n- lib/a/src/api.ts\n"
                              "## Гипотезы\n- H1.1 — проверена: да\n"
                              "## Ограничения охвата\nнет\n", verify=FULL_VERIFY)
        self.s.commit()
        self.s.run("init")
        self.s.run("coverage")
        self.s.run("set-status", "H1", "verified")
        out = self.s.run("check")
        self.assertEqual(out.returncode, 1)
        self.assertIn("not named by full", out.stdout)

    def test_каталог_a_не_закрывает_ворота_за_файл_которого_никто_не_читал(self):
        """`a/` и `b/` — ещё и обычные имена каталогов. Засчитанные где угодно, они
        закрывали ворота за файл, которого никто не читал: блок владеет и `src/api.ts`,
        и `a/src/api.ts`, а отчёт назвал только второй."""
        self.s.write("src/api.ts", "a\n")
        self.s.write("a/src/api.ts", "b\n")
        self.s.blocks(paths=["src", "a"], named_files=True)
        self.s.manifest(hypotheses=1)
        self.s.reports(hunter="# охотник\n## Прочитано\n- a/src/api.ts\n"
                              "## Гипотезы\n- H1.1 — проверена: да\n"
                              "## Ограничения охвата\nнет\n", verify=FULL_VERIFY)
        self.s.commit()
        self.s.run("init")
        self.s.run("coverage")
        self.s.run("set-status", "H1", "verified")
        out = self.s.run("check")
        self.assertEqual(out.returncode, 1)
        self.assertIn("not named by full", out.stdout)
        self.assertIn("src/api.ts", out.stdout)

    def test_заголовок_диффа_в_том_же_дереве_по_прежнему_называет_файл(self):
        """Обратная сторона: там, где `a/` не может значить ничего другого — в заголовке
        диффа, — приставка засчитывается, и вставленный дифф остаётся доказательством
        чтения обоих файлов."""
        self.s.write("src/api.ts", "a\n")
        self.s.write("a/src/api.ts", "b\n")
        self.s.blocks(paths=["src", "a"], named_files=True)
        self.s.manifest(hypotheses=1)
        self.s.reports(hunter="# охотник\n## Прочитано\n- a/src/api.ts\n"
                              "```diff\ndiff --git a/src/api.ts b/src/api.ts\n```\n"
                              "## Гипотезы\n- H1.1 — проверена: да\n"
                              "## Ограничения охвата\nнет\n", verify=FULL_VERIFY)
        self.s.commit()
        self.s.run("init")
        self.s.run("coverage")
        self.s.run("set-status", "H1", "verified")
        out = self.s.run("check")
        self.assertNotIn("not named by full", out.stdout)
        self.assertEqual(out.returncode, 0, out.stdout)


class GitTruthTest(unittest.TestCase):
    """Правда о файлах берётся из индекса, а пути — NUL-разделёнными."""

    def setUp(self) -> None:
        self.s = Stand()
        self.addCleanup(self.s.cleanup)

    def test_файл_из_индекса_не_выложенный_на_диск_даёт_отпечаток_и_строки(self):
        """Разреженная выкладка (и файл, удалённый без коммита): `ls-files` его перечисляет,
        а отпечаток сводился к одному имени — содержимое можно было переписать, и «файлы
        блока изменились после просмотра» не срабатывало никогда."""
        self.s.write("src/one.ts", "одна\nдве\nтри\n")
        self.s.write("src/two.ts", "a\n")
        self.s.blocks(paths=["src"])
        self.s.manifest(hypotheses=1)
        self.s.reports(hunter="# охотник\n## Гипотезы\n- H1.1 — проверена: да\n"
                              "## Ограничения охвата\nнет\n", verify=FULL_VERIFY)
        self.s.commit()
        self.s.run("init")
        self.s.run("coverage")
        self.s.run("set-status", "H1", "verified")
        self.assertEqual(self.s.run("check").returncode, 0, self.s.run("check").stdout)
        before = self.s.run("sizes").stdout

        (self.s.root / "src" / "one.ts").unlink()          # индекс не тронут
        self.assertIn("src/one.ts", self.s.git("ls-files").stdout)
        self.assertEqual(self.s.run("sizes").stdout, before, "строки взяты из индекса")
        out = self.s.run("check")
        self.assertEqual(out.returncode, 0, out.stdout)

        # а правка содержимого в индексе отпечаток меняет
        self.s.write("src/one.ts", "переписали целиком\n")
        self.s.commit("правка после просмотра")
        self.s.run("coverage")
        self.assertIn("changed after the review", self.s.run("check").stdout)

    def test_двоичный_файл_не_считается_строками_в_пороге(self):
        """Порог читаемости мерил картинку как две тысячи строк."""
        self.s.write("src/one.ts", "a\n")
        (self.s.root / "src" / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00\xff" * 4000)
        self.s.blocks(paths=["src"])
        self.s.manifest(hypotheses=1)
        self.s.commit()
        self.s.run("init")
        out = self.s.run("sizes").stdout
        self.assertRegex(out, r"H1\s+read\s+2\s+1\b", out)

    def test_находка_на_пути_с_кириллицей_закрывается_коммитом(self):
        """`git show --name-only` экранирует не-ASCII путь, и находку на таком файле нельзя
        было пометить починенной никогда; путь с пробелом при этом проходил."""
        self.s.write("src/модуль.ts", "a\n")
        self.s.write("src/обычный файл.ts", "a\n")
        self.s.blocks(paths=["src"])
        self.s.manifest(hypotheses=1)
        self.s.write("docs/review/reports/H1-findings.jsonl", "\n".join(json.dumps(r, ensure_ascii=False) for r in [
            {"block": "H1", "severity": "low", "confidence": "confirmed", "status": "open",
             "file": "src/модуль.ts", "claim": "кириллица", "scenario": "с"},
            {"block": "H1", "severity": "low", "confidence": "confirmed", "status": "open",
             "file": "src/обычный файл.ts", "claim": "пробел", "scenario": "с"}]) + "\n")
        self.s.commit()
        self.s.run("init")
        self.s.run("import", "H1")
        self.s.write("src/модуль.ts", "починено\n")
        self.s.write("src/обычный файл.ts", "починено\n")
        self.s.commit("починка")
        sha = self.s.git("rev-parse", "HEAD").stdout.strip()
        for fid in ("H1-001", "H1-002"):
            self.assertEqual(self.s.run("set-finding", fid, "fixed", "--commit", sha).returncode, 0)
        self.s.run("findings")
        out = self.s.run("check").stdout
        self.assertNotIn("does not touch", out)

    def test_коммит_не_касающийся_кириллического_файла_по_прежнему_ловится(self):
        self.s.write("src/модуль.ts", "a\n")
        self.s.write("src/другой.ts", "a\n")
        self.s.blocks(paths=["src"])
        self.s.manifest(hypotheses=1)
        self.s.write("docs/review/reports/H1-findings.jsonl", json.dumps(
            {"block": "H1", "severity": "low", "confidence": "confirmed", "status": "open",
             "file": "src/модуль.ts", "claim": "кириллица", "scenario": "с"},
            ensure_ascii=False) + "\n")
        self.s.commit()
        self.s.run("init")
        self.s.run("import", "H1")
        self.s.write("src/другой.ts", "правка мимо находки\n")
        self.s.commit("не та починка")
        sha = self.s.git("rev-parse", "HEAD").stdout.strip()
        self.s.run("set-finding", "H1-001", "fixed", "--commit", sha)
        self.s.run("findings")
        out = self.s.run("check").stdout
        self.assertIn("does not touch src/модуль.ts", out)

    def test_переименование_не_обрывает_историю_изменений_блока(self):
        """`--name-only` печатает только новое имя: частота изменений блока обрывалась на
        каждом переезде файла, а `order` ранжировал блок по огрызку истории."""
        self.s.write("src/a.ts", "0\n")
        self.s.write("src/b.ts", "0\n")
        self.s.blocks(paths=["src/a.ts", "src/renamed.ts"], extra_blocks=[{
            "id": "H2", "slug": "two", "phase": 1, "title": "Второй", "role": "demo",
            "goal": "г", "paths": ["src/b.ts"], "ref_paths": []}])
        self.s.manifest(hypotheses=1)
        self.s.commit()

        def touch(name: str) -> None:
            p = self.s.root / "src" / name
            p.write_text(p.read_text(encoding="utf-8") + "1\n", encoding="utf-8")
            self.s.git("add", "-A")
            self.s.git("commit", "-q", "-m", "t")
        for _ in range(4):
            touch("a.ts")
        self.s.git("mv", "src/a.ts", "src/renamed.ts")
        self.s.git("commit", "-q", "-m", "переезд")
        self.s.run("init")
        out = self.s.run("order").stdout
        # стартовый + 4 правки под старым именем + переезд = 6 коммитов у H1
        self.assertRegex(out, r"H1\s+—\s+todo\s+6\b", out)

    def test_шаблон_который_git_отказывается_разобрать_объясняет_себя(self):
        """Опечатка в магии pathspec — это отказ с именем файла, а не трейсбек."""
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src"])
        self.s.manifest(hypotheses=1)
        self.s.commit()
        self.s.run("init")
        bj = self.s.root / "docs/review/blocks.json"
        d = json.loads(bj.read_text(encoding="utf-8"))
        d["blocks"][0]["paths"] = [":(нетмагии)src"]
        bj.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
        for cmd in ("check", "coverage"):
            out = self.s.run(cmd)
            with self.subTest(cmd=cmd):
                self.assertEqual(out.returncode, 2, out.stdout + out.stderr)
                self.assertNotIn("Traceback", out.stderr)
                self.assertIn("blocks.json", out.stderr)

    def test_законный_шаблон_с_исключением_по_прежнему_работает(self):
        self.s.write("src/one.ts", "a\n")
        self.s.write("src/generated/x.ts", "x\n")
        self.s.blocks(paths=["src", ":(exclude)src/generated/**"])
        self.s.manifest(hypotheses=1)
        self.s.commit()
        self.s.run("init")
        out = self.s.run("prompt", "H1", "--role", "hunter")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("src/one.ts", out.stdout)
        self.assertNotIn("src/generated/x.ts", out.stdout)


class HandWrittenInputTest(unittest.TestCase):
    """Всё, что человек правит руками, обязано получать отказ, а не трейсбек:
    определение блоков, итоговый файл, текст манифеста."""

    def setUp(self) -> None:
        self.s = Stand()
        self.addCleanup(self.s.cleanup)

    def _stand(self) -> None:
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=1)
        self.s.commit()
        self.s.run("init")

    def _add_block(self, **fields) -> None:
        bj = self.s.root / "docs/review/blocks.json"
        d = json.loads(bj.read_text(encoding="utf-8"))
        d["blocks"].append(fields)
        bj.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")

    def test_блок_без_обязательного_поля_называет_поле(self):
        """`setup` оставляет "blocks": [] человеку; блок без `phase` отвечал KeyError
        и кодом 1, который читается как «состояние красное»."""
        self._stand()
        self._add_block(id="H2", title="Платежи", paths=["src/one.ts"])
        for cmd in (("status",), ("check",), ("order",), ("summary", "--out", "s.md")):
            out = self.s.run(*cmd)
            with self.subTest(cmd=cmd[0]):
                self.assertEqual(out.returncode, 2, out.stdout + out.stderr)
                self.assertNotIn("Traceback", out.stderr)
                self.assertIn("phase", out.stderr)
                self.assertIn("blocks.json", out.stderr)

    def test_полностью_заполненный_блок_принимается(self):
        self._stand()
        self._add_block(id="H2", slug="two", phase=1, title="Платежи", role="demo",
                        goal="проверить", paths=["src/one.ts"], ref_paths=[])
        out = self.s.run("status")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertIn("Платежи", out.stdout)

    def test_два_блока_с_одним_идентификатором_отказ(self):
        self._stand()
        self._add_block(id="H1", slug="clone", phase=1, title="Клон", role="demo",
                        goal="г", paths=["src/one.ts"], ref_paths=[])
        out = self.s.run("status")
        self.assertEqual(out.returncode, 2)
        self.assertIn("share the id", out.stderr)

    def test_разделитель_пути_в_идентификаторе_отказ(self):
        """id и slug становятся именем файла под docs/review/."""
        self._stand()
        self._add_block(id="H2", slug="../../вне", phase=1, title="Побег", role="demo",
                        goal="г", paths=["src/one.ts"], ref_paths=[])
        out = self.s.run("status")
        self.assertEqual(out.returncode, 2)
        self.assertIn("file name", out.stderr)

    def test_итог_с_маркером_внутри_названия_блока_не_роняет_aged(self):
        """`Import --> export pipeline` резался на первом ` -->` внутри названия."""
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        bj = self.s.root / "docs/review/blocks.json"
        d = json.loads(bj.read_text(encoding="utf-8"))
        d["blocks"][0]["title"] = "Импорт --> экспорт"
        bj.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
        self.s.manifest(hypotheses=1)
        self.s.commit()
        self.s.run("init")
        self.s.run("summary", "--out", "sum.md")
        out = self.s.run("summary", "--aged", "sum.md")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertNotIn("Traceback", out.stderr)

    def test_испорченный_машинный_блок_итога_объясняет_себя(self):
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=1)
        self.s.commit()
        self.s.run("init")
        self.s.run("summary", "--out", "sum.md")
        p = self.s.root / "sum.md"
        text = p.read_text(encoding="utf-8")
        i = text.index("<!-- finetooth-summary ")
        p.write_text(text[:i] + "<!-- finetooth-summary {порвано -->\n", encoding="utf-8")
        out = self.s.run("summary", "--aged", "sum.md")
        self.assertEqual(out.returncode, 2)
        self.assertNotIn("Traceback", out.stderr)
        self.assertIn("summary", out.stderr)

    def test_подстановка_в_тексте_манифеста_остаётся_текстом(self):
        """Манифест, который пишет о подстановках, получал вместо них список файлов."""
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.write("docs/review/blocks/H1-demo.md",
                     "# H1 — Демоблок\n\n## Зачем\n\nШаблон использует {{FILES}} как "
                     "подстановку, и этот абзац достаточно длинный, чтобы манифест не "
                     "считался куцым.\n\n## Гипотезы\n1. Первая гипотеза о предикате.\n\n"
                     "## Критерий приёмки\n\nТаблица.\n")
        self.s.commit()
        self.s.run("init")
        out = self.s.run("prompt", "H1", "--role", "hunter")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("Шаблон использует {{FILES}} как подстановку", out.stdout)

    def test_подстановки_самого_шаблона_по_прежнему_заполняются(self):
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=1)
        self.s.commit()
        self.s.run("init")
        out = self.s.run("prompt", "H1", "--role", "hunter").stdout
        self.assertIn("src/one.ts", out)
        self.assertNotIn("{{FILES}}", out)
        self.assertNotIn("{{BLOCK_ID}}", out)

    # Порча определения — таблицей, а не одним случаем: стенд всегда писал верхнеуровневые
    # поля сам, поэтому `review_id`, `exclusions` и `paths` не проверял никто, и `init`
    # отвечал трейсбеком на определение, которое человек пишет руками.
    DAMAGE = {
        "блок без обязательных полей":
            lambda d: d["blocks"].append({"id": "H2", "title": "Платежи",
                                          "paths": ["src/one.ts"]}),
        "нет review_id": lambda d: d.pop("review_id"),
        "review_id пустой": lambda d: d.update(review_id="  "),
        "review_id не строка": lambda d: d.update(review_id=7),
        "исключение без pattern": lambda d: d["exclusions"].append({"reason": "сборка"}),
        "исключения не списком": lambda d: d.update(exclusions={"pattern": "dist/**"}),
        "pattern не строка": lambda d: d["exclusions"].append({"pattern": 7}),
        "paths строкой": lambda d: d["blocks"][0].update(paths="src/one.ts"),
        "paths с числом": lambda d: d["blocks"][0].update(paths=["src/one.ts", 7]),
        "ref_paths строкой": lambda d: d["blocks"][0].update(ref_paths="src/one.ts"),
        "blocks не списком": lambda d: d.update(blocks={"id": "H1"}),
    }

    def _damage(self, how) -> None:
        bj = self.s.root / "docs/review/blocks.json"
        d = json.loads(bj.read_text(encoding="utf-8"))
        how(d)
        bj.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")

    def _subcommands(self) -> list[str]:
        helped = self.s.run("--help").stdout
        names = re.search(r"\{([a-z0-9,\-]{20,})\}", helped.replace("\n", ""))
        self.assertTrue(names, helped)
        commands = names.group(1).split(",")
        self.assertIn("check", commands)
        return commands

    def test_ни_одна_команда_не_роняет_трейсбек_на_битом_определении(self):
        """Узда класса: список подкоманд берётся у самого инструмента, а порча определения —
        таблицей, так что и новая команда, и новое поле попадают под правило сами.

        Команда зовётся И с лишними доводами, И без них: пока звали только с `H1 s.md`,
        `init` до своего кода не доходил — argparse отвергал позиционные доводы раньше, —
        и трейсбек `KeyError: 'review_id'` проходил мимо узды.
        """
        self._stand()
        commands = self._subcommands()
        for name, how in self.DAMAGE.items():
            with self.subTest(порча=name):
                self._stand()
                self._damage(how)
                for cmd in commands:
                    for args in ((), ("H1", "s.md")):
                        out = self.s.run(cmd, *args)
                        with self.subTest(cmd=cmd, args=args):
                            self.assertNotIn("Traceback", out.stderr,
                                             f"{name} / {cmd} {args}: {out.stderr[-400:]}")

    def test_отказ_на_битом_определении_называет_поле_и_файл(self):
        """Отказ читает тот, кто видит инструмент впервые: он обязан назвать, что править."""
        for name, how, field in (
                ("нет review_id", self.DAMAGE["нет review_id"], "review_id"),
                ("исключение без pattern", self.DAMAGE["исключение без pattern"], "pattern"),
                ("paths строкой", self.DAMAGE["paths строкой"], "paths")):
            with self.subTest(порча=name):
                self._stand()
                self._damage(how)
                out = self.s.run("init")
                self.assertEqual(out.returncode, 2, out.stdout + out.stderr)
                self.assertNotIn("Traceback", out.stderr)
                self.assertIn(field, out.stderr)
                self.assertIn("blocks.json", out.stderr)

    def test_целое_определение_по_прежнему_принимается(self):
        """Обратная сторона: проверка не должна отнимать то, что было разрешено, —
        исключение с лишними ключами, блок без `paths`, определение без `exclusions`."""
        self._stand()
        self._damage(lambda d: d["exclusions"].append(
            {"pattern": "dist/**", "reason": "сборка", "кем": "человеком"}))
        self._damage(lambda d: d["blocks"].append(
            {"id": "H2", "slug": "two", "phase": 1, "title": "Платежи", "role": "demo",
             "goal": "проверить"}))
        out = self.s.run("init")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self._damage(lambda d: d.pop("exclusions"))
        out = self.s.run("status")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertIn("Платежи", out.stdout)


class IdempotenceTest(unittest.TestCase):
    """Повторный прогон на верном состоянии не трогает файл. Иначе ворота CI обычного
    вида — «перегенерируй и потребуй чистое дерево» — краснеют на верном состоянии, и
    честный обход один: перестать звать инструмент в CI."""

    def setUp(self) -> None:
        self.s = Stand()
        self.addCleanup(self.s.cleanup)
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=1)
        self.s.reports(hunter="# охотник\n## Гипотезы\n- H1.1 — проверена: да\n"
                              "## Ограничения охвата\nнет\n", verify=FULL_VERIFY)
        self.s.commit()
        self.s.run("init")
        self.s.run("coverage")

    def _state_text(self) -> str:
        return (self.s.root / "docs/review/state.json").read_text(encoding="utf-8")

    def test_повторный_init_не_меняет_состояние_ни_на_байт(self):
        before = self._state_text()
        time.sleep(1.1)                      # чтобы отличие было видно, если оно есть
        out = self.s.run("init")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(self._state_text(), before)
        self.assertIn("already matches", out.stdout)

    def test_init_на_изменившемся_определении_состояние_меняет(self):
        before = self._state_text()
        bj = self.s.root / "docs/review/blocks.json"
        d = json.loads(bj.read_text(encoding="utf-8"))
        d["blocks"].append({"id": "H2", "slug": "two", "phase": 1, "title": "Второй",
                            "role": "demo", "goal": "г", "paths": ["src/one.ts"], "ref_paths": []})
        bj.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
        self.assertEqual(self.s.run("init").returncode, 0)
        self.assertNotEqual(self._state_text(), before)
        self.assertIn("H2", self._state_text())

    def test_повторный_restamp_блока_ничего_не_пишет(self):
        self.s.run("set-status", "H1", "verified")
        before = self._state_text()
        time.sleep(1.1)
        out = self.s.run("restamp", "H1")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(self._state_text(), before)
        self.assertIn("nothing to stamp", out.stdout)

    def test_restamp_после_правки_файлов_отпечаток_переснимает(self):
        self.s.run("set-status", "H1", "verified")
        self.s.write("src/one.ts", "переписали\n")
        self.s.commit("правка")
        self.s.run("coverage")
        self.assertIn("changed after the review", self.s.run("check").stdout)
        out = self.s.run("restamp", "H1")
        self.assertIn("fingerprint re-taken", out.stdout)
        self.assertNotIn("changed after the review", self.s.run("check").stdout)

    def test_повторный_restamp_находки_ничего_не_пишет(self):
        self.s.write("docs/review/reports/H1-findings.jsonl", json.dumps(
            {"block": "H1", "severity": "low", "confidence": "confirmed", "status": "open",
             "file": "src/one.ts", "claim": "дефект", "scenario": "с"}, ensure_ascii=False) + "\n")
        self.s.commit()
        self.s.run("import", "H1")
        before = (self.s.root / "docs/review/findings.jsonl").read_text(encoding="utf-8")
        out = self.s.run("restamp", "H1-001")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual((self.s.root / "docs/review/findings.jsonl").read_text(encoding="utf-8"),
                         before)
        self.assertIn("nothing to stamp", out.stdout)

    def test_импорт_не_выдаёт_занятый_номер(self):
        """Находка, вставленная ВЫШЕ пронумерованных строк, получала уже занятый номер:
        в реестре оказывались две H1-001, и `set-finding` доставал только первую."""
        src = self.s.root / "docs/review/reports/H1-findings.jsonl"
        rows = [{"block": "H1", "severity": "low", "confidence": "confirmed", "status": "open",
                 "file": "src/one.ts", "claim": f"дефект {n}", "scenario": "с"} for n in (1, 2)]
        src.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                       encoding="utf-8")
        self.s.commit()
        self.s.run("import", "H1")
        ids = [json.loads(l)["id"] for l in src.read_text(encoding="utf-8").splitlines() if l.strip()]
        self.assertEqual(ids, ["H1-001", "H1-002"])

        new = json.dumps({"block": "H1", "severity": "low", "confidence": "confirmed",
                          "status": "open", "file": "src/one.ts", "claim": "вставлена сверху",
                          "scenario": "с"}, ensure_ascii=False)
        src.write_text(new + "\n" + src.read_text(encoding="utf-8"), encoding="utf-8")
        out = self.s.run("import", "H1")
        self.assertEqual(out.returncode, 0, out.stderr)
        rows = [json.loads(l) for l in
                (self.s.root / "docs/review/findings.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
        ids = [r["id"] for r in rows]
        self.assertEqual(len(ids), len(set(ids)), ids)
        self.assertEqual({r["claim"] for r in rows if r["id"] == "H1-001"}, {"дефект 1"},
                         "номер уже выданной находки не переехал на другую")
        self.s.run("findings")
        self.assertNotIn("duplicate id", self.s.run("check").stdout)

    def test_повторный_импорт_того_же_файла_ничего_не_добавляет(self):
        src = self.s.root / "docs/review/reports/H1-findings.jsonl"
        src.write_text(json.dumps({"block": "H1", "severity": "low", "confidence": "confirmed",
                                   "status": "open", "file": "src/one.ts", "claim": "дефект",
                                   "scenario": "с"}, ensure_ascii=False) + "\n", encoding="utf-8")
        self.s.commit()
        self.s.run("import", "H1")
        first = (self.s.root / "docs/review/findings.jsonl").read_text(encoding="utf-8")
        self.s.run("import", "H1")
        second = [json.loads(l) for l in
                  (self.s.root / "docs/review/findings.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
        self.assertEqual(len(second), 1)
        self.assertEqual(json.loads(first.splitlines()[0])["id"], second[0]["id"])

    def test_две_строки_с_одним_номером_в_черновике_отказ(self):
        src = self.s.root / "docs/review/reports/H1-findings.jsonl"
        row = {"id": "H1-001", "block": "H1", "severity": "low", "confidence": "confirmed",
               "status": "open", "file": "src/one.ts", "claim": "дефект", "scenario": "с"}
        src.write_text(json.dumps(row, ensure_ascii=False) + "\n"
                       + json.dumps({**row, "claim": "тот же номер"}, ensure_ascii=False) + "\n",
                       encoding="utf-8")
        self.s.commit()
        out = self.s.run("import", "H1")
        self.assertEqual(out.returncode, 2)
        self.assertIn("two rows carry the id H1-001", out.stderr)


class FreshnessGateTest(unittest.TestCase):
    """Ворота свежести дерева не имеют права молчать о том, что они не работают."""

    def setUp(self) -> None:
        self.s = Stand()
        self.addCleanup(self.s.cleanup)
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=1)
        self.s.commit()
        self.s.run("init")
        self.s.run("coverage")

    def test_без_удалённого_репозитория_ворота_объявляют_себя_неработающими(self):
        out = self.s.run("check")
        self.assertEqual(out.returncode, 0, out.stdout)
        self.assertIn("the freshness gate is not running", out.stdout)
        self.assertIn("git remote add origin", out.stdout)

    def _server(self, remote_name: str) -> None:
        """Соседний «сервер» с коммитом двухнедельной давности впереди нашего."""
        server = self.s.root.parent / (self.s.root.name + "-server")
        subprocess.run(["git", "init", "-q", "--bare", str(server)], check=True)
        self.addCleanup(shutil.rmtree, server, True)
        self.s.git("remote", "add", remote_name, str(server))
        self.s.git("push", "-q", remote_name, "HEAD:refs/heads/master")
        self.s.write("src/server.ts", "серверная правка\n")
        self.s.git("add", "src/server.ts")
        future = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=14)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
        env = dict(os.environ, GIT_AUTHOR_DATE=future, GIT_COMMITTER_DATE=future)
        subprocess.run(["git", "-C", str(self.s.root), "commit", "-qm", "серверная правка"],
                       env=env, check=False, capture_output=True)
        self.s.git("push", "-q", remote_name, "HEAD:refs/heads/master")
        self.s.git("reset", "-q", "--hard", "HEAD~1")
        self.s.git("fetch", "-q", remote_name)
        self.s.git("symbolic-ref", f"refs/remotes/{remote_name}/HEAD",
                   f"refs/remotes/{remote_name}/master")

    def test_удалённый_не_origin_ловит_отставание(self):
        """Копия соседнего сервиса, подключённая под именем upstream: ворота молчали."""
        self._server("upstream")
        out = self.s.run("check")
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn("the tree is behind", out.stdout)
        self.assertNotIn("the freshness gate is not running", out.stdout)

    def test_origin_по_прежнему_ловит_отставание(self):
        self._server("origin")
        out = self.s.run("check")
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn("the tree is behind", out.stdout)

    def test_удалённый_без_HEAD_называет_команду(self):
        server = self.s.root.parent / (self.s.root.name + "-bare")
        subprocess.run(["git", "init", "-q", "--bare", str(server)], check=True)
        self.addCleanup(shutil.rmtree, server, True)
        self.s.git("remote", "add", "origin", str(server))
        out = self.s.run("check")
        self.assertIn("the freshness gate is not running", out.stdout)
        self.assertIn("git remote set-head origin -a", out.stdout)


class ThresholdTest(unittest.TestCase):
    """Порог, который не держит на краю своего диапазона, — не порог."""

    def setUp(self) -> None:
        self.s = Stand()
        self.addCleanup(self.s.cleanup)

    def test_на_молодой_истории_стартовый_коммит_считается_массовым(self):
        """95-й процентиль на истории короче двадцати коммитов равен самому большому
        коммиту: не отсекалось ничего, и стартовый коммит со всем деревом связывал
        каждый файл с каждым."""
        names = [f"f{i}" for i in range(12)]
        for n in names:
            self.s.write(f"src/{n}.ts", "0\n")
        extra = [{"id": "H2", "slug": "two", "phase": 1, "title": "Второй", "role": "demo",
                  "goal": "г", "paths": [f"src/f{i}.ts" for i in range(6, 12)], "ref_paths": []}]
        self.s.blocks(paths=[f"src/f{i}.ts" for i in range(6)], extra_blocks=extra)
        self.s.manifest(hypotheses=1)
        self.s.commit()          # стартовый коммит: всё дерево разом

        def touch(*files):
            for f in files:
                p = self.s.root / "src" / (f + ".ts")
                p.write_text(p.read_text(encoding="utf-8") + "1\n", encoding="utf-8")
            self.s.git("add", "-A")
            self.s.git("commit", "-q", "-m", "t")
        for _ in range(3):       # настоящая пара через блоки
            touch("f0", "f6")
        for _ in range(3):       # и мелкие правки, чтобы выброс был виден как выброс
            touch("f1")
        self.s.run("init")
        out = self.s.run("coupling").stdout
        self.assertRegex(out, r"mass commits skipped \(> \d+ files, Tukey's fence over \d+ "
                              r"commits — fewer than 20, too few for a percentile\): 1")
        self.assertIn("H1 src/f0.ts  ↔  H2 src/f6.ts", out)
        self.assertNotIn("src/f2.ts", out, "пары из стартового коммита не должны выжить")

    def test_на_длинной_истории_порог_остаётся_процентилем(self):
        self.s.write("src/a.ts", "0\n")
        self.s.write("src/b.ts", "0\n")
        self.s.blocks(paths=["src/a.ts"], extra_blocks=[{
            "id": "H2", "slug": "two", "phase": 1, "title": "Второй", "role": "demo",
            "goal": "г", "paths": ["src/b.ts"], "ref_paths": []}])
        self.s.manifest(hypotheses=1)
        self.s.commit()
        for i in range(25):
            p = self.s.root / "src" / "a.ts"
            p.write_text(p.read_text(encoding="utf-8") + "1\n", encoding="utf-8")
            self.s.git("add", "-A")
            self.s.git("commit", "-q", "-m", "t")
        self.s.run("init")
        out = self.s.run("coupling").stdout
        self.assertIn("95th percentile of this repository", out)


class SpendTest(unittest.TestCase):
    """Замер расхода — то, из чего выведены потолки ходов. Обрезанный прогон не имеет
    права выглядеть в дневнике как обычный завершённый."""

    def setUp(self) -> None:
        self.s = Stand()
        self.addCleanup(self.s.cleanup)

    def _stream(self, with_result: bool = True, truncated: bool = False,
                subtype: str = "success") -> Path:
        ev = lambda o: json.dumps(o, ensure_ascii=False)
        usage = {"input_tokens": 1, "cache_creation_input_tokens": 100,
                 "cache_read_input_tokens": 900, "output_tokens": 5}
        lines = [ev({"type": "assistant", "message": {
            "id": "m1", "model": "test", "usage": usage,
            "content": [{"type": "tool_use", "id": "t1", "name": "Read",
                         "input": {"file_path": "/x/a.ts"}}]}})]
        if with_result:
            lines.append(ev({"type": "result", "subtype": subtype, "num_turns": 42,
                             "duration_ms": 600000, "total_cost_usd": 3.41,
                             "usage": {"output_tokens": 21000}, "result": "готово"}))
        text = "\n".join(lines) + "\n"
        if truncated:
            text = text[:-20]
        p = self.s.root / "stream.jsonl"
        p.write_text(text, encoding="utf-8")
        return p

    def _axes(self, path: Path, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(SKILL / "scripts" / "axes.py"),
                               str(path), *args], capture_output=True, text=True)

    def test_поток_без_события_result_не_выдаётся_за_измерение(self):
        """«0 min, None turns, $0.00» в формате настоящего замера записывало дорогой
        обрезанный прогон как бесплатный."""
        out = self._axes(self._stream(with_result=False), "--journal")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("NO RESULT EVENT", out.stdout)
        self.assertIn("? turns", out.stdout)
        self.assertIn("cost estimate unknown", out.stdout)
        self.assertNotIn("$0.00", out.stdout)

    def test_обрезанная_последняя_строка_не_роняет_замер(self):
        out = self._axes(self._stream(truncated=True), "--journal")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("unreadable line", out.stdout)

    def test_прогон_обрезанный_потолком_ходов_назван_обрезанным(self):
        out = self._axes(self._stream(subtype="error_max_turns"), "--journal")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("RUN CUT OFF", out.stdout)
        self.assertIn("error_max_turns", out.stdout)

    def test_целый_поток_по_прежнему_читается_как_замер(self):
        out = self._axes(self._stream(), "--journal")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertNotIn("RUN CUT OFF", out.stdout)
        self.assertNotIn("NO RESULT EVENT", out.stdout)
        self.assertIn("10 min, 42 turns", out.stdout)
        self.assertIn("cost estimate $3.41", out.stdout)

    def _two_results(self, cut_first: bool) -> Path:
        """Поток с двумя событиями `result`: фоновая задача, закончившаяся после главного
        ответа, печатает своё. Числа берутся у длинного, исход — у обоих."""
        ev = lambda o: json.dumps(o, ensure_ascii=False)
        done = {"type": "result", "subtype": "success", "num_turns": 40,
                "duration_ms": 600000, "total_cost_usd": 5.0, "usage": {"output_tokens": 1000}}
        cut = {"type": "result", "subtype": "error_max_turns", "is_error": True,
               "num_turns": 2, "duration_ms": 19000, "total_cost_usd": 0.1,
               "usage": {"output_tokens": 10}}
        lines = [ev({"type": "assistant", "message": {
            "id": "m1", "model": "test", "usage": {"input_tokens": 1, "output_tokens": 2},
            "content": []}})]
        lines += [ev(cut), ev(done)] if cut_first else [ev(done), ev(cut)]
        p = self.s.root / "two.jsonl"
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return p

    def test_обрезка_во_втором_событии_result_не_теряется(self):
        """Потолок ходов — предохранитель, и его срабатывание обязано быть видно в
        дневнике. Пока брали одно событие, слово об обрезке пропадало вместе с коротким."""
        for cut_first in (False, True):
            with self.subTest(обрезка_первой=cut_first):
                out = self._axes(self._two_results(cut_first), "--journal")
                self.assertEqual(out.returncode, 0, out.stderr)
                self.assertIn("RUN CUT OFF", out.stdout)
                self.assertIn("error_max_turns", out.stdout)
                # числа — у длинного события: потолок срабатывает на длинной ветке
                self.assertIn("10 min, 40 turns", out.stdout)
                self.assertIn("cost estimate $5.00", out.stdout)

    def test_два_успешных_события_result_не_объявляются_обрезкой(self):
        """Обратная сторона: два завершившихся события — обычный прогон, и слова об
        обрезке в строке быть не должно."""
        ev = lambda o: json.dumps(o, ensure_ascii=False)
        lines = [ev({"type": "assistant", "message": {
            "id": "m1", "model": "test", "usage": {"input_tokens": 1, "output_tokens": 2},
            "content": []}}),
            ev({"type": "result", "subtype": "success", "num_turns": 2, "duration_ms": 19000,
                "total_cost_usd": 0.1, "usage": {"output_tokens": 10}}),
            ev({"type": "result", "subtype": "success", "num_turns": 40, "duration_ms": 600000,
                "total_cost_usd": 5.0, "usage": {"output_tokens": 1000}})]
        p = self.s.root / "both-ok.jsonl"
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
        out = self._axes(p, "--journal")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertNotIn("RUN CUT OFF", out.stdout)
        self.assertNotIn("PARTIAL RESULT", out.stdout)
        self.assertIn("10 min, 40 turns", out.stdout)

    def test_результат_короче_потока_не_выдаётся_за_замер_прогона(self):
        """Ход несёт не больше одного сообщения ассистента, поэтому «2 turns» при
        одиннадцати сообщениях — результат о ЧАСТИ прогона. Так в дневнике самого набора
        появилась строка «0 min, 2 turns, 329 tool calls … $67.92»."""
        ev = lambda o: json.dumps(o, ensure_ascii=False)
        lines = [ev({"type": "assistant", "message": {
            "id": f"m{i}", "model": "test", "usage": {"input_tokens": 1, "output_tokens": 2},
            "content": []}}) for i in range(11)]
        lines.append(ev({"type": "result", "subtype": "success", "num_turns": 2,
                         "duration_ms": 0, "total_cost_usd": 67.92,
                         "usage": {"output_tokens": 100}}))
        p = self.s.root / "partial.jsonl"
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
        out = self._axes(p, "--journal")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("PARTIAL RESULT", out.stdout)
        self.assertIn("11 assistant messages", out.stdout)

    def _run_role(self, exit_code: int, truncated: bool = False,
                  log_fails: bool = False) -> tuple[subprocess.CompletedProcess, str]:
        """run-role.sh с заглушкой вместо `claude`: настоящий клиент здесь не нужен,
        нужен его код возврата и поток, который он оставляет. `truncated` — убитый прогон
        обрывает последнюю строку потока на середине; `log_fails` — отказывает шаг отчёта."""
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=1)
        self.s.commit()
        self.s.run("init")
        stub_dir = self.s.root / "stub"
        stub_dir.mkdir()
        stub = stub_dir / "claude"
        stub.write_text(
            "#!/usr/bin/env bash\n"
            'printf \'%s\\n\' \'{"type":"assistant","message":{"id":"m1","model":"test",'
            '"usage":{"input_tokens":1,"cache_creation_input_tokens":0,'
            '"cache_read_input_tokens":0,"output_tokens":1},"content":[]}}\'\n'
            + ('printf \'%s\' \'{"type":"assis\'\n' if truncated else "")
            + f"exit {exit_code}\n", encoding="utf-8")
        stub.chmod(0o755)
        review = f"{sys.executable} {TOOL}"
        if log_fails:
            # Отчётный шаг, который отказал: дневник не пишется, но код возврата обязан
            # остаться кодом ПРОГОНА — по нему читает всё, что запускает run-role.sh.
            wrap = stub_dir / "review-wrap.sh"
            wrap.write_text("#!/usr/bin/env bash\n"
                            'if [ "$1" = "log" ]; then echo "log failed" >&2; exit 3; fi\n'
                            f'exec {review} "$@"\n', encoding="utf-8")
            wrap.chmod(0o755)
            review = str(wrap)
        env = dict(os.environ, PATH=f"{stub_dir}:{os.environ['PATH']}",
                   REVIEW=review, TMPDIR=str(self.s.root / "runs"))
        (self.s.root / "runs").mkdir()
        out = subprocess.run(["bash", str(SKILL / "assets" / "run-role.sh"), "H1", "hunter"],
                             cwd=self.s.root, capture_output=True, text=True, env=env)
        journal = (self.s.root / "docs/review/journal.md")
        return out, journal.read_text(encoding="utf-8") if journal.exists() else ""

    def test_обрезанный_поток_не_роняет_запуск_роли(self):
        """Убитый прогон оставляет последнюю строку недописанной. Ответ агента читался
        вторым разборщиком, написанным прямо в скрипте; он умирал на такой строке, и под
        `set -e` вместе с ним пропадал `exit $RC` — оператор видел трейсбек и код 1."""
        out, journal = self._run_role(exit_code=143, truncated=True)
        self.assertEqual(out.returncode, 143, out.stdout + out.stderr)
        self.assertNotIn("Traceback", out.stderr)
        self.assertIn("unreadable line", journal)
        self.assertIn("RUN FAILED", journal)

    def test_отказ_шага_отчёта_не_подменяет_код_возврата_прогона(self):
        """Прогон упал — его код и остаётся, что бы ни случилось с отчётом."""
        out, _ = self._run_role(exit_code=7, log_fails=True)
        self.assertEqual(out.returncode, 7, out.stdout + out.stderr)

    def test_потерянная_запись_в_журнал_не_выдаёт_себя_за_чистый_прогон(self):
        """R3-004: ловушка `exit $RC` прятала несделанную запись в дневник за кодом 0.
        Прогон успешен, а отчёт потерян — код 3, и ответ агента всё равно напечатан."""
        out, journal = self._run_role(exit_code=0, log_fails=True)
        self.assertEqual(out.returncode, 3, out.stdout + out.stderr)
        self.assertIn("journal write failed", out.stderr)
        self.assertIn("no agent reply in the stream", out.stdout)

    def test_ответ_агента_печатается_из_целого_потока(self):
        """Прямая сторона: на целом потоке ответ агента по-прежнему виден оператору."""
        out, _ = self._run_role(exit_code=0)
        self.assertIn("no agent reply in the stream", out.stdout, out.stdout)
        p = self.s.root / "reply.jsonl"
        p.write_text(json.dumps({"type": "result", "subtype": "success", "num_turns": 1,
                                 "duration_ms": 1, "total_cost_usd": 0.1,
                                 "usage": {"output_tokens": 1}, "result": "блок пройден"},
                                ensure_ascii=False) + "\n", encoding="utf-8")
        got = self._axes(p, "--reply")
        self.assertEqual(got.returncode, 0, got.stderr)
        self.assertIn("--- agent reply ---", got.stdout)
        self.assertIn("блок пройден", got.stdout)

    def test_упавший_прогон_записан_в_дневник_как_упавший(self):
        """Дневник — единственная память следующей сессии; обрезанный прогон был записан
        в нём как обычная строка расхода, и блок читался как пройденный."""
        out, journal = self._run_role(exit_code=1)
        self.assertEqual(out.returncode, 1)
        self.assertIn("RUN FAILED", journal)
        self.assertIn("claude exit 1", journal)

    def test_несобравшийся_промпт_не_оставляет_пустого_файла(self):
        """`review prompt` отказал — в TMPDIR оставался нулевой файл промпта."""
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=1)
        self.s.commit()
        self.s.run("init")
        runs = self.s.root / "runs"
        runs.mkdir()
        env = dict(os.environ, REVIEW=f"{sys.executable} {TOOL}", TMPDIR=str(runs))
        out = subprocess.run(["bash", str(SKILL / "assets" / "run-role.sh"), "НЕТБЛОКА", "hunter"],
                             cwd=self.s.root, capture_output=True, text=True, env=env)
        self.assertEqual(out.returncode, 2, out.stdout + out.stderr)
        left = list((runs / "finetooth-runs").glob("*.prompt.md"))
        self.assertEqual(left, [], "нулевой файл промпта остался в TMPDIR")

    def test_успешный_прогон_записан_обычной_строкой(self):
        out, journal = self._run_role(exit_code=0)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("hunter — ", journal)
        self.assertNotIn("RUN FAILED", journal)


class GuardGrepTest(unittest.TestCase):
    """Узда проекта-пользователя: один маркер — одно послабление, а несуществующий путь
    — отказ, а не тишина."""

    def setUp(self) -> None:
        self.dir = Path(tempfile.mkdtemp(prefix="finetooth-guard-"))
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.pkg = self.dir / "internal" / "billing"
        self.pkg.mkdir(parents=True)

    def _run(self, *paths: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["bash", str(SKILL / "assets" / "guard-grep.sh"), "--pattern", r"\.Publish\(",
             "--marker", "outbox-allowed:", "--", *paths],
            capture_output=True, text=True)

    def test_один_маркер_освобождает_один_вызов(self):
        """Ровно тот дефект, ради замены которого скрипт и написан: `grep -B` склеивал
        соседние попадания, и маркер первого освобождал второе."""
        (self.pkg / "a.go").write_text(
            "package billing\n// outbox-allowed: причина\nbroker.Publish(1)\n"
            "broker.Publish(2)\nbroker.Publish(3)\nbroker.Publish(4)\n", encoding="utf-8")
        out = self._run(str(self.pkg))
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertNotIn("a.go:3", out.stdout, "вызов под маркером освобождён")
        for line in (4, 5, 6):
            self.assertIn(f"a.go:{line}", out.stdout, out.stdout)

    def test_каждому_вызову_свой_маркер_и_дерево_чистое(self):
        (self.pkg / "a.go").write_text(
            "package billing\n// outbox-allowed: раз\nbroker.Publish(1)\n"
            "// outbox-allowed: два\nbroker.Publish(2)\n"
            "broker.Publish(3) // outbox-allowed: три\n", encoding="utf-8")
        out = self._run(str(self.pkg))
        self.assertEqual(out.returncode, 0, out.stdout)
        self.assertEqual(out.stdout, "")

    def test_переименованный_пакет_роняет_ворота_а_не_молчит(self):
        (self.pkg / "a.go").write_text("package billing\nbroker.Publish(1)\n", encoding="utf-8")
        self.assertEqual(self._run(str(self.pkg)).returncode, 1)
        (self.pkg).rename(self.dir / "internal" / "payments")
        out = self._run(str(self.pkg))
        self.assertEqual(out.returncode, 2, out.stdout)
        self.assertIn("no such path", out.stderr)
        self.assertIn("not the same as a clean tree", out.stderr)


class GateCoverageTest(unittest.TestCase):
    """Ворота `check`, у которых не было ни одного теста.

    Измерено мутацией: каждое из этих ворот глушилось в отдельной копии набора, и весь
    прогон оставался зелёным — то есть механизм можно было снять и никто бы не заметил.
    По тесту на ворота; имена перечислены в GATES реестра ниже, и реестр сам себя сверяет
    с исходником.
    """

    def setUp(self) -> None:
        self.s = Stand()
        self.addCleanup(self.s.cleanup)

    def _green(self, status: str = "verified") -> None:
        """Стенд, на котором `check` зелёный: каждый тест ломает ровно одну вещь."""
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=1)
        self.s.reports(hunter="# охотник\n## Гипотезы\n- H1.1 — проверена: да\n"
                              "## Ограничения охвата\nнет\n", verify=FULL_VERIFY)
        self.s.commit()
        self.s.run("init")
        self.s.run("coverage")
        self.s.run("set-status", "H1", status)
        out = self.s.run("check")
        self.assertEqual(out.returncode, 0, out.stdout)

    def _state(self) -> dict:
        return json.loads((self.s.root / "docs/review/state.json").read_text(encoding="utf-8"))

    def _write_state(self, st: dict) -> None:
        (self.s.root / "docs/review/state.json").write_text(
            json.dumps(st, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def _register(self, **fields) -> None:
        """Реестр пишется руками: инструмент сам такую запись не создаст, а `check`
        обязан поймать её именно поэтому."""
        row = {"id": "H1-001", "block": "H1", "severity": "low", "confidence": "confirmed",
               "status": "open", "file": "src/one.ts", "claim": "дефект",
               "scenario": "сценарий", "code_sha": None}
        row.update(fields)
        if row.get("code_sha") is None and row.get("file") == "src/one.ts":
            row["code_sha"] = self.s.git("hash-object", "src/one.ts").stdout.strip()
        (self.s.root / "docs/review/findings.jsonl").write_text(
            json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
        self.s.run("findings")

    # --------------------------------------------------- состояние против определения

    def test_блок_из_определения_без_записи_в_состоянии(self):
        self._green()
        st = self._state()
        del st["blocks"]["H1"]
        self._write_state(st)
        out = self.s.run("check")
        self.assertEqual(out.returncode, 1)
        self.assertIn("no record in state.json", out.stdout)

    def test_блок_в_состоянии_которого_нет_в_определении(self):
        self._green()
        st = self._state()
        st["blocks"]["H9"] = {"status": "todo", "started": None, "finished": None,
                              "reports": [], "note": ""}
        self._write_state(st)
        out = self.s.run("check")
        self.assertEqual(out.returncode, 1)
        self.assertIn("missing from blocks.json", out.stdout)

    def test_манифест_пропал_а_блок_в_работе(self):
        self._green()
        (self.s.root / "docs/review/blocks/H1-demo.md").unlink()
        out = self.s.run("check")
        self.assertEqual(out.returncode, 1)
        self.assertIn("no manifest", out.stdout)

    def test_пройденный_блок_без_отчёта_проверяющего(self):
        self._green()
        (self.s.root / "docs/review/reports/H1-demo.verify.md").unlink()
        out = self.s.run("check")
        self.assertEqual(out.returncode, 1)
        self.assertIn("there is no verifier report", out.stdout)

    def test_объявленный_отчёт_которого_нет_на_диске(self):
        self._green()
        self.s.run("set-status", "H1", "verified", "--report", "docs/review/reports/none.md")
        out = self.s.run("check")
        self.assertEqual(out.returncode, 1)
        self.assertIn("which is not on disk", out.stdout)

    def test_статус_дальше_running_без_отчёта_охотника(self):
        self._green(status="hunted")
        (self.s.root / "docs/review/reports/H1-demo.hunter.md").unlink()
        out = self.s.run("check")
        self.assertEqual(out.returncode, 1)
        self.assertIn("there is no hunter report", out.stdout)

    def test_running_без_отметки_времени(self):
        self._green()
        st = self._state()
        st["blocks"]["H1"]["status"] = "running"
        st["blocks"]["H1"]["started"] = None
        self._write_state(st)
        out = self.s.run("check")
        self.assertEqual(out.returncode, 1)
        self.assertIn("without a timestamp", out.stdout)

    def test_неразбираемая_отметка_времени(self):
        self._green()
        st = self._state()
        st["blocks"]["H1"]["status"] = "running"
        st["blocks"]["H1"]["started"] = "вчера вечером"
        self._write_state(st)
        out = self.s.run("check")
        self.assertEqual(out.returncode, 1)
        self.assertIn("cannot be parsed", out.stdout)

    def test_running_дольше_суток(self):
        self._green()
        st = self._state()
        st["blocks"]["H1"]["status"] = "running"
        st["blocks"]["H1"]["started"] = (dt.datetime.now(dt.timezone.utc)
                                         - dt.timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
        self._write_state(st)
        out = self.s.run("check")
        self.assertEqual(out.returncode, 1)
        self.assertIn("stuck in running", out.stdout)

    # ------------------------------------------------------------- форма находок

    def test_две_записи_с_одним_идентификатором(self):
        self._green()
        sha = self.s.git("hash-object", "src/one.ts").stdout.strip()
        row = {"id": "H1-001", "block": "H1", "severity": "low", "confidence": "confirmed",
               "status": "open", "file": "src/one.ts", "claim": "дефект",
               "scenario": "сценарий", "code_sha": sha}
        (self.s.root / "docs/review/findings.jsonl").write_text(
            json.dumps(row, ensure_ascii=False) + "\n"
            + json.dumps({**row, "claim": "тот же номер"}, ensure_ascii=False) + "\n",
            encoding="utf-8")
        self.s.run("findings")
        out = self.s.run("check")
        self.assertEqual(out.returncode, 1)
        self.assertIn("duplicate id", out.stdout)

    def test_пустое_обязательное_поле_находки(self):
        self._green()
        self._register(claim="")
        out = self.s.run("check")
        self.assertEqual(out.returncode, 1)
        self.assertIn("field claim is empty", out.stdout)

    def test_находка_ссылается_на_несуществующий_блок(self):
        self._green()
        self._register(block="H9")
        out = self.s.run("check")
        self.assertEqual(out.returncode, 1)
        self.assertIn("nonexistent block H9", out.stdout)

    def test_severity_вне_словаря(self):
        self._green()
        self._register(severity="катастрофа")
        out = self.s.run("check")
        self.assertEqual(out.returncode, 1)
        self.assertIn("severity=катастрофа is not in the vocabulary", out.stdout)

    def test_confidence_вне_словаря(self):
        self._green()
        self._register(confidence="наверное")
        out = self.s.run("check")
        self.assertEqual(out.returncode, 1)
        self.assertIn("confidence=наверное is not in the vocabulary", out.stdout)

    def test_статус_находки_вне_словаря(self):
        self._green()
        self._register(status="почти")
        out = self.s.run("check")
        self.assertEqual(out.returncode, 1)
        self.assertIn("status=почти is not in the vocabulary", out.stdout)

    def test_внешний_коммит_починки_написан_не_по_форме(self):
        self._green()
        self._register(status="fixed", fix_commit="соседний-репозиторий:")
        out = self.s.run("check")
        self.assertEqual(out.returncode, 1)
        self.assertIn("an external fix is written as", out.stdout)

    def test_починено_без_коммита(self):
        self._green()
        self._register(status="fixed", fix_commit=None)
        out = self.s.run("check")
        self.assertEqual(out.returncode, 1)
        self.assertIn("marked fixed, but no fix commit", out.stdout)

    def test_дубль_без_указания_чего(self):
        self._green()
        self._register(status="duplicate", dup_of=None)
        out = self.s.run("check")
        self.assertEqual(out.returncode, 1)
        self.assertIn("marked duplicate, but not of what exactly", out.stdout)

    def test_отвергнутая_проверяющим_но_открытая(self):
        self._green()
        self._register(confidence="rejected", status="open")
        out = self.s.run("check")
        self.assertEqual(out.returncode, 1)
        self.assertIn("rejected by the verifier, but still open", out.stdout)

    def test_заголовок_находки_длиннее_потолка(self):
        self._green()
        self._register(claim="и" * 260)
        out = self.s.run("check")
        self.assertEqual(out.returncode, 1)
        self.assertIn("against a limit of 220", out.stdout)

    def test_сценарий_длиннее_потолка(self):
        self._green()
        self._register(scenario="и" * 800)
        out = self.s.run("check")
        self.assertEqual(out.returncode, 1)
        self.assertIn("against a limit of 700", out.stdout)

    def test_номер_строки_строкой_а_не_числом(self):
        """Черновик находок пишется руками, и `"line": "9999"` — обычная описка. Ворота
        о несуществующей строке молча пропускали её мимо, а findings.md рисовал её как
        настоящее место."""
        self._green()
        self._register(line="9999")
        out = self.s.run("check")
        self.assertEqual(out.returncode, 1)
        self.assertIn("is not a number", out.stdout)

    def test_число_в_пределах_файла_по_прежнему_проходит(self):
        self._green()
        self._register(line=1)
        # есть находка — у проверяющего обязан быть вердикт по ней
        self.s.write("docs/review/reports/H1-demo.verify.md",
                     "# проверяющий\n\n## Вердикты\nH1-001 — подтверждена.\n\n"
                     "## Охват\nОхват полный.\n")
        out = self.s.run("check")
        self.assertEqual(out.returncode, 0, out.stdout)

    def test_блок_без_отпечатка_контекста_предупреждает(self):
        self.s.write("src/one.ts", "a\n")
        self.s.write("src/ref.ts", "контекст\n")
        self.s.blocks(paths=["src/one.ts"], ref_paths=["src/ref.ts"], extra_blocks=[{
            "id": "H2", "slug": "two", "phase": 1, "title": "Второй", "role": "demo",
            "goal": "держит контекст", "paths": ["src/ref.ts"], "ref_paths": []}])
        self.s.manifest(hypotheses=1)
        self.s.reports(hunter="# охотник\n## Гипотезы\n- H1.1 — проверена: да\n"
                              "## Ограничения охвата\nнет\n", verify=FULL_VERIFY)
        self.s.commit()
        self.s.run("init")
        self.s.run("coverage")
        self.s.run("set-status", "H1", "verified")
        st = self._state()
        del st["blocks"]["H1"]["refs_sha"]
        self._write_state(st)
        out = self.s.run("check")
        self.assertEqual(out.returncode, 0, out.stdout)
        self.assertIn("no context fingerprint", out.stdout)

    def test_findings_md_разъехался_с_реестром(self):
        self._green()
        self._register()
        md = self.s.root / "docs/review/findings.md"
        md.write_text(md.read_text(encoding="utf-8") + "\n| дописано руками |\n", encoding="utf-8")
        out = self.s.run("check")
        self.assertEqual(out.returncode, 1)
        self.assertIn("findings.md diverged", out.stdout)

    def test_ничей_файл_роняет_не_только_карту_но_и_проверку(self):
        self._green()
        self.s.write("src/forgotten.ts", "b\n")
        self.s.commit("файл мимо блоков")
        out = self.s.run("check")
        self.assertEqual(out.returncode, 1)
        self.assertIn("belong to no block", out.stdout)

    def test_пройденный_блок_без_отпечатка_гипотез(self):
        self._green()
        st = self._state()
        del st["blocks"]["H1"]["hypotheses_sha"]
        self._write_state(st)
        out = self.s.run("check")
        self.assertEqual(out.returncode, 1)
        self.assertIn("no hypotheses fingerprint", out.stdout)

    def test_род_доказательства_вне_словаря(self):
        self._green()
        bj = self.s.root / "docs/review/blocks.json"
        d = json.loads(bj.read_text(encoding="utf-8"))
        d["blocks"][0]["proof"] = "на глаз"
        bj.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
        self.s.commit("род доказательства")
        self.s.run("coverage")
        out = self.s.run("check")
        self.assertEqual(out.returncode, 1)
        self.assertIn("is not in the vocabulary", out.stdout)


def _check_gates(source: str | None = None) -> list[tuple[int, str, str]]:
    """Все ворота `cmd_check`: (строка, problems|warnings, ключ ворот).

    Ключ — это литеральные куски f-строки, склеенные и ужатые по пробелам: он переживает
    правку подставляемых значений и меняется, когда меняется сама формулировка.

    У трёх ворот сообщение целиком приходит из вспомогательной функции или переменной
    (`problems.append(why)`), и литералов в нём нет вовсе. Такие ворота названы выражением,
    которое их сообщение порождает: иначе все они делят один пустой ключ, и следующие
    ворота, написанные той же формой, совпадут с уже записанными и пройдут незамеченными.
    """
    tree = ast.parse(source if source is not None else TOOL.read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "cmd_check")

    def literal(node) -> str:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.JoinedStr):
            return "".join(literal(v) for v in node.values)
        if isinstance(node, ast.BinOp):
            return literal(node.left) + literal(node.right)
        return ""

    out = []
    for node in ast.walk(fn):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "append"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id in ("problems", "warnings")):
            key = re.sub(r"\s+", " ", literal(node.args[0])).strip()[:46]
            if not re.search(r"[A-Za-zА-Яа-я]", key):
                # Quotes dropped: `ast.unparse` picks the quote style by Python version
                # (3.14 writes f"{b['id']}…", earlier versions f'{b['id']}…'), and the
                # registry went red in CI on a key nobody had changed.
                key = "= " + re.sub(r"\s+", " ", re.sub(r"[\"']", "", ast.unparse(node.args[0])))[:44]
            out.append((node.lineno, node.func.value.id, key))
    return sorted(out)


class GateRegistryTest(unittest.TestCase):
    """УЗДА КЛАССА «ворота, которые не могут покраснеть».

    Мутацией было измерено, что два десятка ворот `check` можно снять, и весь прогон
    останется зелёным. Список починенных мест такое не держит: следующие ворота напишут
    без теста так же. Здесь ворота перечислены поимённо вместе с тестом, который краснеет
    при их снятии, и правило сверяет список с исходником: новые ворота без записи роняют
    прогон, запись с несуществующим именем теста — тоже.
    """

    # ворота `cmd_check` → тест, который краснеет, если их заглушить
    GATES = [
        (': no record in state.json — run ` init`', "test_блок_из_определения_без_записи_в_состоянии"),
        (': present in state.json but missing from block', "test_блок_в_состоянии_которого_нет_в_определении"),
        (": status '' is not in the vocabulary — written", "test_статус_блока_вписанный_руками_роняет_проверку"),
        (': phase comes after phase — the blocks array i', "test_фазы_в_массиве_не_убывают"),
        (': blocked without a note — waiting for what? `', "test_заблокированный_блок_не_значит_закончено"),
        (': no manifest', "test_манифест_пропал_а_блок_в_работе"),
        (': manifest is empty or nearly empty', "test_куцый_манифест_роняет_проверку"),
        (': status , but there is no verifier report — t', "test_пройденный_блок_без_отчёта_проверяющего"),
        ("= f{b[id]}: {why}", "test_пустой_отчёт_проверяющего_не_проводит_блок"),   # verify_report_problem
        (': state.json declares report , which is not on', "test_объявленный_отчёт_которого_нет_на_диске"),
        (': status , but there is no hunter report — the', "test_статус_дальше_running_без_отчёта_охотника"),
        (': stuck in running without a timestamp — when ', "test_running_без_отметки_времени"),
        (": timestamp '' cannot be parsed", "test_неразбираемая_отметка_времени"),
        (': stuck in running for h — the session probabl', "test_running_дольше_суток"),
        ('finding : duplicate id', "test_две_записи_с_одним_идентификатором"),
        ('finding : field is empty', "test_пустое_обязательное_поле_находки"),
        ('finding : refers to nonexistent block', "test_находка_ссылается_на_несуществующий_блок"),
        ('finding : severity= is not in the vocabulary', "test_severity_вне_словаря"),
        ('finding : confidence= is not in the vocabulary', "test_confidence_вне_словаря"),
        ('finding : status= is not in the vocabulary', "test_статус_находки_вне_словаря"),
        ('finding : file is not in the repository', "test_починенная_находка_на_удалённом_файле_не_роняет_проверку"),
        ('finding : deferred without a reason — ` set-fi', "test_отложенная_находка_требует_причину"),
        ('finding : an external fix is written as `<repo', "test_внешний_коммит_починки_написан_не_по_форме"),
        ('finding : commit is not in the repository', "test_починка_в_соседнем_репозитории_помечается_явно"),
        ('finding : commit does not touch — either the m', "test_коммит_починки_обязан_касаться_файла_находки"),
        ('finding : marked fixed, but no fix commit is g', "test_починено_без_коммита"),
        ('finding : marked duplicate, but not of what ex', "test_дубль_без_указания_чего"),
        ('= why', "test_дубль_указывает_на_живую_находку"),                # dup_problem
        ('finding : rejected by the verifier, but still ', "test_отвергнутая_проверяющим_но_открытая"),
        ('finding : status rejected but confidence — the', "test_отказ_меняет_и_уверенность"),
        ('finding : no code fingerprint — changes in und', "test_старые_записи_без_отпечатков_ловятся_и_дописываются"),
        ('finding : code in changed since import — re-ch', "test_изменившийся_код_под_открытой_находкой_роняет_проверку"),
        ('finding : line= is not a number — write the li', "test_номер_строки_строкой_а_не_числом"),
        ('finding : line is cited, but has', "test_несуществующая_строка_в_находке_роняет_проверку"),
        ('finding : rejected, but the reject reason is n', "test_отвергнутая_находка_без_причины_роняет_проверку"),
        ('finding : claim is characters against a limit ', "test_заголовок_находки_длиннее_потолка"),
        ('finding : scenario is characters against a lim', "test_сценарий_длиннее_потолка"),
        ('findings.md diverged from findings.jsonl — run', "test_findings_md_разъехался_с_реестром"),
        (': pattern `` matches only untracked files () —', "test_шаблон_по_нетрекнутым_файлам_зовёт_git_add"),
        (': pattern `` matches no file — the block silen', "test_шаблон_который_ничего_не_нашёл_роняет_проверку"),
        ('files belong to no block — ` coverage`', "test_ничей_файл_роняет_не_только_карту_но_и_проверку"),
        ('coverage.tsv is stale: lines on disk, the reco', "test_устаревшая_карта_покрытия_роняет_проверку"),
        (': the manifest has no hypotheses — such a bloc', "test_манифест_без_гипотез_роняет_проверку"),
        (': gives hypothesis different verdicts () — the', "test_противоречивые_вердикты_в_одном_отчёте_роняют_проверку"),
        (': of hypotheses without a verdict () — each is', "test_гипотеза_без_вердикта_роняет_проверку"),
        (': block in status without a fingerprint of wha', "test_старые_записи_без_отпечатков_ловятся_и_дописываются"),
        (': block files changed after the review — the b', "test_блок_просмотренный_на_другой_версии_файлов_роняет_проверку"),
        (': no context fingerprint (ref_paths) — ` backf', "test_блок_без_отпечатка_контекста_предупреждает"),
        (': context files (ref_paths) changed after veri', "test_правка_контекста_предупреждает_но_не_роняет"),
        (': no hypotheses fingerprint — an edit of the m', "test_пройденный_блок_без_отпечатка_гипотез"),
        (': manifest hypotheses changed after verificati', "test_правка_гипотез_после_проверки_роняет_проверку"),
        (': of block files are not named by full path in', "test_каждый_файл_блока_назван_полным_путём"),
        (': closed with fixed findings, but there is no ', "test_закрытие_с_починками_требует_ревью_правок"),
        (": the hunter report has no 'Coverage limits' s", "test_отчёт_без_раздела_про_непросмотренное_роняет_проверку"),
        (": the 'Coverage limits' section of the hunter ", "test_пустой_раздел_ограничений_роняет_проверку"),
        ("root '':", "test_узда_обязана_существовать"),                    # rule_problem
        ("root '': instances () and no guard — a class t", "test_третий_повтор_корня_требует_узду"),
        ('the freshness gate is not running:', "test_без_удалённого_репозитория_ворота_объявляют_себя_неработающими"),
        ('the tree is behind by days — the findings of s', "test_отставшее_от_сервера_дерево_роняет_проверку"),
        (": proof '' is not in the vocabulary:", "test_род_доказательства_вне_словаря"),
        (': files, lines — cannot be read in one session', "test_блок_который_за_сеанс_не_прочитать_роняет_проверку"),
        ('open finding(s) older than days (oldest d): — ', "test_check_предупреждает_о_находке_старше_недели"),
        ('reference(s) to findings in the code: — the id', "test_refs_находит_номер_находки_в_коде_и_только_его"),
    ]

    def test_каждые_ворота_check_записаны_вместе_со_своим_тестом(self):
        # Сравниваются не множества, а СЧЁТЫ: два разных гейта могут дать один ключ
        # (сообщение целиком из переменной), и на множествах второй такой гейт совпадал
        # бы с первым и проходил без теста — измерено мутацией.
        in_source = collections.Counter(key for _, _, key in _check_gates())
        registered = collections.Counter(key for key, _ in self.GATES)
        missing = sorted((in_source - registered).elements())
        extra = sorted((registered - in_source).elements())
        self.assertEqual(
            missing, [],
            "ворота без записи в GATES: напишите тест, который краснеет при их снятии, "
            "и впишите его сюда — иначе механизм можно будет убрать, и прогон останется зелёным")
        self.assertEqual(
            extra, [],
            "запись в GATES, которой в cmd_check больше нет: ворота переписали — "
            "сверьте тест с новой формулировкой")

    def test_каждый_названный_тест_существует(self):
        known = {name for cls in globals().values()
                 if isinstance(cls, type) and issubclass(cls, unittest.TestCase)
                 for name in dir(cls) if name.startswith("test_")}
        for key, name in self.GATES:
            with self.subTest(gate=key):
                self.assertIn(name, known, f"ворота `{key}` ссылаются на несуществующий тест")

    # Сообщение ворот пишут двумя формами: f-строкой на месте и значением, собранным
    # раньше (`msg = …; problems.append(msg)`) или вспомогательной функцией. Реестр обязан
    # видеть обе: три ворот самого инструмента написаны второй формой, и следующие напишут
    # по соседству — копией.
    VARIABLE_MESSAGE_GATE = '''
def cmd_check(args):
    problems = []
    warnings = []
    if a != b:
        msg = f"review_id mismatch"
        problems.append(msg)
    if c != d:
        problems.append(dup_problem(f, dup))
    return 0
'''

    def test_ворота_с_сообщением_из_переменной_не_теряются(self):
        """Ворота, чьё сообщение не литерал, обязаны попасть в реестр отдельной записью.

        Пока ключом был только литеральный скелет, такие ворота получали пустой ключ,
        совпадали с уже записанными и проходили без единого теста — измерено мутацией:
        добавленные в `cmd_check` ворота с `problems.append(msg)` оставляли и этот класс,
        и весь прогон зелёными.
        """
        gates = _check_gates(self.VARIABLE_MESSAGE_GATE)
        keys = [key for _, _, key in gates]
        self.assertEqual(len(keys), 2, "оба гейта обязаны быть видны")
        self.assertEqual(len(set(keys)), 2, f"ворота слились в один ключ: {keys}")
        registered = collections.Counter(key for key, _ in self.GATES)
        for key in keys:
            self.assertNotIn(key, registered,
                             "новые ворота совпали с уже записанными — реестр их не заметит")

    def test_ворота_с_литеральным_сообщением_читаются_как_раньше(self):
        """Обратная сторона: обычная f-строка по-прежнему опознаётся своим текстом, а не
        выражением, — иначе правка подставляемого значения роняла бы реестр."""
        source = ('def cmd_check(args):\n'
                  '    problems = []\n'
                  '    problems.append(f"{bid}: no manifest {path}")\n')
        self.assertEqual([key for _, _, key in _check_gates(source)], [": no manifest"])


class SourceRuleTest(unittest.TestCase):
    """Узды классов, которые проще держать правилом по исходнику, чем списком мест."""

    SOURCE = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.SOURCE = TOOL.read_text(encoding="utf-8")

    def test_список_путей_у_git_всегда_запрашивается_NUL_разделённым(self):
        """УЗДА КЛАССА «вывод git разобран как обычный текст».

        Три места разбирали список путей построчно: не-ASCII путь приходит оттуда
        экранированным (`"src/\\320\\274…"`) и не совпадает ни с чем, а переименование
        печатается одним новым именем. Правило держит и те вызовы, которых ещё нет.
        """
        asks_for_names = ("ls-files", "--name-only", "--name-status", "--others")
        offenders = []
        for node in ast.walk(ast.parse(self.SOURCE)):
            if not isinstance(node, ast.List):
                continue
            items = [e.value for e in node.elts
                     if isinstance(e, ast.Constant) and isinstance(e.value, str)]
            if "git" not in items or not any(a in items for a in asks_for_names):
                continue
            if "-z" not in items:
                offenders.append((node.lineno, items))
        self.assertEqual(offenders, [], "вызов git со списком путей без -z")

    # Распознавание цитаты живёт здесь; всё остальное спрашивает у них.
    QUOTE_TRACKERS = ("quoted_lines", "_quoted_pass", "unquoted")
    # Детекторы цитаты: кто называет их у себя, тот завёл своё распознавание.
    QUOTE_DETECTORS = {"FENCE", "BLOCKQUOTE", "LIST_OPEN", "CODE_INDENT",
                       "COMMENT_OPEN", "COMMENT_CLOSE"}
    # Разборщик markdown узнаётся ПО ВИДУ, а не по имени из списка: список не видит того,
    # кого ещё не написали, — и не увидел ни одного из трёх, которыми это измерено.
    # Признаки: документ разметки в инструменте зовут `md`; структурные ограды разметки и
    # заголовочные образцы (`*_HEADING`) называет только тот, кто разбирает разметку;
    # строки раздела отдают только эти три функции; а `zip(строки, ...)` — это разбор
    # строки вместе с признаком, и признак обязан быть признаком цитаты.
    MARKDOWN_ARG = "md"
    MARKDOWN_SHAPES = {"FENCE", "BLOCKQUOTE", "LIST_OPEN", "LIST_ITEM", "LIST_MARK"}
    SECTION_READERS = {"section_body", "section_items", "section_items_full"}
    # `section_body` отдаёт строки раздела КАК ЕСТЬ: цитату оно распознаёт, чтобы найти
    # границы раздела, а не чтобы выкинуть её из ответа. Поэтому зов `section_body`
    # разборщика не оправдывает — читающий его строки обязан спросить трекер сам. Ровно
    # так и прошли мимо ворота про раздел ограничений охвата.
    RAW_LINES = {"section_body"}

    def _quote_offenders(self, source: str) -> tuple[list, list]:
        """Кто завёл своё распознавание цитаты и кто разбирает разметку, не спросив общее.

        Разборщик имеет право делегировать (`section_items` берёт строки у
        `section_items_full`), и требовать зова от каждого звена значило бы требовать
        лишнего вызова ради правила; отдающие сырые строки в делегаты не годятся.
        """
        tree = ast.parse(source)
        funcs = {fn.name: fn for fn in ast.walk(tree) if isinstance(fn, ast.FunctionDef)}
        names = {name: {n.id for n in ast.walk(fn) if isinstance(n, ast.Name)}
                 for name, fn in funcs.items()}
        calls = {name: {n.func.id for n in ast.walk(fn)
                        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
                 for name, fn in funcs.items()}
        asks, changed = set(self.QUOTE_TRACKERS), True
        while changed:
            changed = False
            for name, called in calls.items():
                if name not in asks and (called - self.RAW_LINES) & asks:
                    asks.add(name)
                    changed = True
        strangers, deaf = [], []
        for name, fn in funcs.items():
            if name not in self.QUOTE_TRACKERS and names[name] & self.QUOTE_DETECTORS:
                strangers.append((name, sorted(names[name] & self.QUOTE_DETECTORS)))
            shapes = {n for n in names[name]
                      if n in self.MARKDOWN_SHAPES or n.endswith("_HEADING")}
            paired = [n for n in ast.walk(fn)
                      if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                      and n.func.id == "zip" and len(n.args) > 1
                      and isinstance(n.args[1], ast.Call)]
            reads_markdown = (self.MARKDOWN_ARG in {a.arg for a in fn.args.args}
                              or shapes or calls[name] & self.SECTION_READERS or paired)
            if reads_markdown and name not in asks:
                deaf.append(name)
        return strangers, deaf

    def test_цитаты_распознаются_одним_местом(self):
        """УЗДА КЛАССА «цитата не распознана».

        Каждый разборщик имел своё представление об ограде, и `~~~` не знал никто: правка
        одного места не чинила остальные. Форм цитаты четыре — ограда, отступ, `>` и
        html-комментарий, — и каждая по очереди закрывала гипотезу, которую никто не
        отвечал. Распознавание живёт в одном месте, своих детекторов быть не должно, а
        разборщик разметки обязан спросить общий трекер — и узнаётся он по виду, потому
        что список имён не видит разборщика, которого ещё нет.
        """
        self.assertNotIn('startswith("```")', self.SOURCE,
                         "своё распознавание ограды — зовите quoted_lines()")
        strangers, deaf = self._quote_offenders(self.SOURCE)
        self.assertEqual(strangers, [], "своё распознавание цитаты — зовите quoted_lines()")
        self.assertEqual(deaf, [], "разборщик markdown не спрашивает общий трекер цитаты")

    # Разборщики, которых в инструменте ещё нет: правило обязано видеть их по виду. Все
    # три измерены — при узде, знавшей разборщиков поимённо, прогон на каждом оставался
    # зелёным.
    UNSEEN_PARSERS = {
        "документ разметки читается своими руками": '''
def report_sections(md):
    return [line for line in md.split("\\n") if line.startswith("#")]
''',
        "строка разбирается вместе с чужим признаком": '''
def report_sections(doc):
    lines = doc.split("\\n")
    return [line for line, flag in zip(lines, fenced_lines(lines)) if not flag]
''',
        "сырые строки раздела читаются как слова отчёта": '''
def limits_said(doc):
    return [ln for ln in section_body(doc, LIMITS_HEADING) or [] if ln.strip()]
''',
    }
    # А это не разборщики разметки, и требовать от них трекер значило бы требовать
    # бессмыслицы: реестр находок — JSONL, где `#` открывает комментарий строки.
    SEEN_INNOCENT = {
        "jsonl с комментариями": '''
def read_register(path):
    return [line for line in path.read_text().splitlines()
            if line.strip() and not line.startswith("#")]
''',
        "разборщик, который спрашивает трекер": '''
def report_sections(md):
    lines = md.split("\\n")
    return [line for line in unquoted(lines) if line.startswith("#")]
''',
    }

    def test_узда_видит_разборщика_которого_ещё_нет(self):
        """Обе стороны правила: новый разборщик разметки без трекера обязан ронять прогон,
        а читатель не-разметки и разборщик, который трекер спросил, — нет."""
        for why, src in self.UNSEEN_PARSERS.items():
            with self.subTest(разборщик=why):
                self.assertNotEqual(self._quote_offenders(src)[1], [],
                                    "узда не увидела разборщика по виду")
        for why, src in self.SEEN_INNOCENT.items():
            with self.subTest(невиновный=why):
                self.assertEqual(self._quote_offenders(src)[1], [],
                                 "узда требует трекер там, где разметки нет")

    def test_записи_коммитов_разбираются_одним_местом(self):
        """УЗДА КЛАССА «поток `git log -z` разобран своими руками».

        Ловушка не видна с места вызова: git завершает строку `--format` своим переводом
        строки, и `-z` оставляет его приклеенным к ПЕРВОМУ пути коммита. Два разборщика
        знали об этом порознь, и тот, что не знал, считал файл под двумя именами.
        Разбор живёт в `log_records`, и сверять токен с маркером больше негде.
        """
        tree = ast.parse(self.SOURCE)
        # маркер разрешено СТАВИТЬ в `--format=`, но не читать обратно
        placed = {n.lineno for n in ast.walk(tree)
                  if isinstance(n, ast.JoinedStr) and "--format=" in "".join(
                      v.value for v in n.values if isinstance(v, ast.Constant))}
        offenders = []
        for fn in ast.walk(tree):
            if not isinstance(fn, ast.FunctionDef) or fn.name == "log_records":
                continue
            offenders += [(fn.name, n.lineno) for n in ast.walk(fn)
                          if isinstance(n, ast.Name) and n.id == "LOG_MARK"
                          and n.lineno not in placed]
        self.assertEqual(offenders, [], "свой разбор записей git log — зовите log_records()")

    def test_каждое_число_в_коде_названо_и_объяснено(self):
        """УЗДА КЛАССА «порог без источника».

        Каждая константа-число обязана нести над собой комментарий о том, откуда она
        взялась: замер или ссылка. Правило ловит следующую добавленную так же, как эти.
        """
        lines = self.SOURCE.splitlines()
        bare = []
        for node in ast.parse(self.SOURCE).body:
            if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Constant):
                continue
            if not isinstance(node.value.value, (int, float)) or isinstance(node.value.value, bool):
                continue
            name = node.targets[0].id if isinstance(node.targets[0], ast.Name) else ""
            if not name.isupper():
                continue
            # комментарий может стоять над группой констант, а не над каждой
            i = node.lineno - 2
            while i >= 0 and re.match(r"^[A-Z_]+\s*=", lines[i]):
                i -= 1
            if i < 0 or not lines[i].lstrip().startswith("#"):
                bare.append(name)
        self.assertEqual(bare, [], "число без источника: припишите замер или ссылку")



class QuotationMapTest(unittest.TestCase):
    """The quotation class produced a defect in every fix round of the kit's own review
    (fences in lists, the closing fence that opened, the inner fence that closed, the fence
    that never closed), while a source-shape guard stayed green on all of them. This table
    holds the BEHAVIOUR both ways: every line of every document is marked Q (quoted — an
    example) or . (said — the report's own words), and a change that moves one mark in
    either direction is red."""

    CASES = {
        "fence at the margin": (
            "text\n```\n- H1.1 — checked\n```\nafter", ".QQQ."),
        "fence nested in a list item, four spaces in": (
            "1. item\n    ```\n    - H1.1 — checked\n    ```\n2. next", ".QQQ."),
        "opening fence deeper than the list column, inner list line (round 3)": (
            "1. hypothesis:\n       ```\n       - H1.1 — checked\n       ```\n2. next", ".QQQ."),
        "indented fence INSIDE a fence does not close it (round 4)": (
            "```\nexample:\n    ```\n    - H1.1 — checked\n    ```\n```\nafter", "QQQQQQ."),
        "a fence that never closes is text (round 4)": (
            "1. one\n   ```\n2. two\n3. three", "...."),
        "a tilde fence is not closed by backticks": (
            "~~~\n```\n- H1.1 — checked\n~~~\nafter", "QQQQ."),
        "blockquote": ("> - H1.1 — checked\nsaid", "Q."),
        "indented code after a blank line": ("para\n\n    - H1.1 — checked\nsaid", "..Q."),
        "sub-items of a list are said, not quoted": (
            "1. H1.1 — checked\n    - proof: ran it\n2. H1.2", "..."),
        "a line that is only a comment": ("<!-- H1.1 — checked -->\nsaid", "Q."),
    }

    def test_карта_цитат_в_обе_стороны(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("finetooth_review", TOOL)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        for name, (doc, want) in self.CASES.items():
            got = "".join("Q" if q else "." for q in mod.quoted_lines(doc.split("\n")))
            self.assertEqual(got, want, name)

    def test_незакрытая_ограда_в_отчёте_остаётся_цитатой(self):
        """R5-001: для отчёта сомнение трактуется в сторону «цитата» — иначе скелет шаблона в
        незакрытой ограде закрывает гипотезы; для манифеста — в сторону «текст»."""
        doc = "````\n- H1.1 — checked\n```\nafter".split("\n")
        mod = self._mod()
        self.assertEqual("".join("Q" if q else "." for q in mod.quoted_lines(doc, "quoted")), "QQQQ")
        self.assertEqual("".join("Q" if q else "." for q in mod.quoted_lines(doc, "text")), "....")

    def test_раздел_охвата_в_незакрытой_ограде_пуст(self):
        """R6-004: раздел «Границы охвата» отчёта, целиком внутри незакрытой ограды, — цитата,
        а не ответ: гейт обязан счесть раздел пустым."""
        mod = self._mod()
        md = "# report\n````\n## Coverage limits\n- nothing was skipped\n"
        self.assertIsNone(mod.section_body(md, mod.LIMITS_HEADING, "quoted"))
        # a manifest read the same way keeps its section: there doubt means "text"
        self.assertIsNotNone(mod.section_body(md, mod.LIMITS_HEADING, "text"))

    def _mod(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("finetooth_review", TOOL)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod




class RecordedFindingsImportTest(unittest.TestCase):
    """A finding can be recorded against a block before its pass — handed over by another
    block's fixer or fix reviewer, left by an earlier pass. The plain import replaced the
    block's set with the file's rows: the recorded finding vanished, its id went to the
    hunter's new finding, and `check` stayed green (the kit author's review, 24.09 — 26
    such rows in 15 unstarted blocks of a live register). Rules from that review, held both
    ways."""

    def setUp(self):
        self.s = Stand()
        self.addCleanup(self.s.cleanup)
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=1)
        self.s.commit()
        self.s.run("init")

    def row(self, claim, **kw):
        base = {"block": "H1", "severity": "low", "confidence": "confirmed", "status": "open",
                "file": "src/one.ts", "claim": claim, "scenario": "x does y"}
        base.update(kw)
        return base

    def register(self, *rows):
        self.s.write("docs/review/findings.jsonl",
                     "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))

    def draft(self, *rows):
        self.s.write("docs/review/reports/H1-findings.jsonl",
                     "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))

    def reg(self):
        p = Path(self.s.root, "docs/review/findings.jsonl")
        return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]

    # forbidden — refused, register and file untouched
    def test_записанная_открытая_находка_не_стирается_простым_импортом(self):
        self.register(self.row("handed over before the pass", id="H1-001", severity="high"))
        self.draft(self.row("the hunter found this"))
        before = self.reg()
        out = self.s.run("import", "H1")
        self.assertEqual(out.returncode, 2, out.stdout + out.stderr)
        self.assertIn("H1-001", out.stdout + out.stderr)
        self.assertIn("--append", out.stdout + out.stderr)
        self.assertEqual(self.reg(), before)

    def test_решение_записанное_командой_не_откатывается_повторным_импортом(self):
        self.draft(self.row("one"))
        self.s.run("import", "H1")
        self.assertEqual(self.s.run("set-finding", "H1-001", "rejected", "--reason", "так задумано").returncode, 0)
        self.draft(self.row("one", id="H1-001"))           # the file still says open
        before = self.reg()
        out = self.s.run("import", "H1")
        self.assertEqual(out.returncode, 2, out.stdout + out.stderr)
        self.assertEqual(self.reg(), before)

    # allowed
    def test_первый_импорт_блока_без_записанного(self):
        self.draft(self.row("one"))
        self.assertEqual(self.s.run("import", "H1").returncode, 0)

    def test_повторный_импорт_того_же_файла_и_с_новой_строкой(self):
        self.draft(self.row("one"))
        self.s.run("import", "H1")
        self.assertEqual(self.s.run("import", "H1").returncode, 0)
        p = Path(self.s.root, "docs/review/reports/H1-findings.jsonl")
        p.write_text(p.read_text(encoding="utf-8") + json.dumps(self.row("two"), ensure_ascii=False) + "\n",
                     encoding="utf-8")
        out = self.s.run("import", "H1")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertEqual(sorted(f["id"] for f in self.reg()), ["H1-001", "H1-002"])

    def test_append_нумерует_после_наибольшего_номера(self):
        self.register(self.row("a", id="H1-001"), self.row("d", id="H1-004"))
        self.draft(self.row("new"))
        out = self.s.run("import", "H1", "--append")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertIn("H1-005", [f["id"] for f in self.reg()])

    def test_файл_сам_меняет_нештампованное_решение(self):
        self.draft(self.row("one"))
        self.s.run("import", "H1")
        self.draft(self.row("Отвергнуто: так задумано", id="H1-001", status="rejected",
                            confidence="rejected"))
        self.assertEqual(self.s.run("import", "H1").returncode, 0)
        self.draft(self.row("one", id="H1-001"))
        self.assertEqual(self.s.run("import", "H1").returncode, 0)

    def test_force_заменяет_набор_осознанно(self):
        self.register(self.row("handed over", id="H1-001"))
        self.draft(self.row("the hunter found this"))
        out = self.s.run("import", "H1", "--force")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)

    # prompts
    def test_охотник_и_проверяющий_видят_записанные_находки(self):
        self.register(self.row("handed over before the pass", id="H1-001", severity="high"),
                      self.row("deferred into this block", id="H1-004", status="deferred",
                               defer_reason="after the release"))
        for role in ("hunter", "verify"):
            out = self.s.run("prompt", "H1", "--role", role).stdout
            self.assertIn("H1-001", out, role)
            self.assertIn("handed over before the pass", out, role)
            self.assertIn("H1-004", out, role)

    def test_номер_первой_новой_находки_тот_же_что_выдаст_append(self):
        self.register(self.row("a", id="H1-001"), self.row("d", id="H1-004"))
        out = self.s.run("prompt", "H1", "--role", "hunter").stdout
        self.assertIn("**H1-005**", out)
        self.draft(self.row("new"))
        self.s.run("import", "H1", "--append")
        self.assertIn("H1-005", [f["id"] for f in self.reg()])

    # --append and a foreign block's id
    def test_append_отказывает_на_номере_чужого_блока(self):
        self.register(self.row("mine", id="H1-001"))
        self.draft(self.row("from elsewhere", id="V2-001"))
        out = self.s.run("import", "H1", "--append")
        self.assertEqual(out.returncode, 2, out.stdout + out.stderr)
        self.assertIn("V2-001", out.stdout + out.stderr)

if __name__ == "__main__":
    unittest.main()
