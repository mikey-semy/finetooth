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

import datetime as dt
import json
import re
import os
import shutil
import subprocess
import tempfile
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
               named_files: bool = False, proof: str | None = None, lang: str = "ru") -> None:
        # Гейт «каждый файл назван в отчёте» в стенде выключен: стендовые отчёты — заглушки.
        # Тесты самого гейта включают его явно.
        extra = {"readable_lines": readable_lines} if readable_lines else {}
        extra["named_files"] = named_files
        # Стенд ведёт ревью по-русски: шаблоны ролей и заглушки отчётов в тестах русские.
        extra["lang"] = lang
        self.write("docs/review/blocks.json", json.dumps({
            "review_id": "test", "project": "Тестовый проект", "gates": ["npm test"], **extra,
            "exclusions": (exclusions or []) + [
                {"pattern": "docs/review", "reason": "аппарат ревью"},
                {"pattern": "scripts/review", "reason": "аппарат ревью"},
            ],
            "blocks": [{"id": self.block_id, "slug": "demo", "phase": 1, "title": "Демоблок",
                        "role": "demo", "goal": "проверить оснастку",
                        **({"proof": proof} if proof else {}),
                        "paths": paths, "ref_paths": ref_paths or []}],
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
        self.s.reports(hunter="# охотник\n## Итог\n"
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
        self.s.run("init")
        out = subprocess.run(["python3", str(TOOL), "status"], cwd=self.s.root / "src",
                             capture_output=True, text=True, check=False)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("H1", out.stdout, "из подкаталога — тот же корень")
        self.assertFalse((KIT / "docs" / "review" / "state.json").exists(),
                         "состояние не должно уехать в репозиторий, где лежит скилл")

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


if __name__ == "__main__":
    unittest.main()
