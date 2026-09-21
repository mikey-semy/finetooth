#!/usr/bin/env python3
"""Тесты инструмента ревью.

Каждый тест ставит набор в свежий временный репозиторий и проверяет ПОВЕДЕНИЕ через
командную строку — так же, как его увидит проект. Внутренности не импортируются:
инструмент переживает переезд между проектами ровно настолько, насколько устойчив его
внешний договор.

Запуск: python3 -m unittest discover -s tests   (нужен только git и стандартная библиотека)
"""

from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]


class Stand:
    """Временный репозиторий с установленным набором."""

    def __init__(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="review-kit-test-"))
        self.tool = self.root / "scripts" / "review" / "review.py"
        for d in ("scripts/review", "docs/review/blocks", "docs/review/reports", "src"):
            (self.root / d).mkdir(parents=True, exist_ok=True)
        shutil.copy(KIT / "review.py", self.tool)
        shutil.copytree(KIT / "prompts", self.root / "docs" / "review" / "prompts")
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
        return subprocess.run(["python3", str(self.tool), *args],
                              capture_output=True, text=True, check=False, env=env)

    def blocks(self, *, paths: list[str], exclusions: list[dict] | None = None,
               ref_paths: list[str] | None = None) -> None:
        self.write("docs/review/blocks.json", json.dumps({
            "review_id": "test", "project": "Тестовый проект", "gates": ["npm test"],
            "exclusions": (exclusions or []) + [
                {"pattern": "docs/review", "reason": "аппарат ревью"},
                {"pattern": "scripts/review", "reason": "аппарат ревью"},
            ],
            "blocks": [{"id": "H1", "slug": "demo", "phase": 1, "title": "Демоблок",
                        "role": "demo", "goal": "проверить оснастку",
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
        self.assertIn("Что делать", out.stdout, "отказ обязан говорить, что делать")

    def test_карта_называет_коммит_и_ловит_чужую_ветку(self):
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest()
        self.s.commit()
        self.s.run("init")
        self.assertEqual(self.s.run("coverage").returncode, 0)
        head = self.s.git("rev-parse", "--short", "HEAD").stdout.strip()
        cov = (self.s.root / "docs/review/coverage.tsv").read_text(encoding="utf-8")
        self.assertIn(head, cov.splitlines()[0])

        cov_path = self.s.root / "docs/review/coverage.tsv"
        cov_path.write_text(cov.replace(head, "deadbee"), encoding="utf-8")
        out = self.s.run("check")
        self.assertIn("другой линии", out.stdout)

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
        self.s.reports(hunter="# отчёт\n\n## Ограничения охвата\nнет\n", verify="# проверяющий\n")
        self.s.commit()
        self.s.run("init")
        self.s.run("coverage")
        self.s.run("set-status", "H1", "verified")
        out = self.s.run("check")
        self.assertEqual(out.returncode, 1)
        self.assertIn("без вердикта", out.stdout)

    def test_манифест_без_гипотез_роняет_проверку(self):
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.write("docs/review/blocks/H1-demo.md", "# H1\n\n## Критерий приёмки\nТаблица.\n")
        self.s.commit()
        self.s.run("init")
        self.s.run("coverage")
        self.s.run("set-status", "H1", "running")
        out = self.s.run("check")
        self.assertIn("нет гипотез", out.stdout)

    def test_отчёт_без_раздела_про_непросмотренное_роняет_проверку(self):
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=1)
        self.s.reports(hunter="# отчёт\n\n## Гипотезы\n- H1.1 — проверена: да\n",
                       verify="# проверяющий\n")
        self.s.commit()
        self.s.run("init")
        self.s.run("coverage")
        self.s.run("set-status", "H1", "verified")
        out = self.s.run("check")
        self.assertIn("ограничени", out.stdout.lower())

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
            "## Ограничения охвата\nстенда нет\n"), verify="# проверяющий\n")
        self.s.commit()
        self.s.run("init")
        self.s.run("coverage")
        self.s.run("set-status", "H1", "verified")
        self.assertEqual(self.s.run("check").returncode, 0, self.s.run("check").stdout)
        self.assertIn("закрыто 3/3", self.s.run("hypotheses", "H1").stdout)

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
        self.assertIn("не проверена", out.stdout)

    def test_блок_просмотренный_на_другой_версии_файлов_роняет_проверку(self):
        """Статус «пройден» держится вечно, а файлы меняются — отпечаток это ловит."""
        self.s.write("src/one.ts", "было\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=1)
        self.s.reports(hunter="# охотник\n## Гипотезы\n- H1.1 — проверена: да\n"
                              "## Ограничения охвата\nнет\n", verify="# проверяющий\n")
        self.s.commit()
        self.s.run("init")
        self.s.run("coverage")
        self.s.run("set-status", "H1", "verified")
        self.assertEqual(self.s.run("check").returncode, 0, self.s.run("check").stdout)

        self.s.write("src/one.ts", "переписали целиком\n")
        self.s.commit("правка после ревью")
        self.s.run("coverage")
        out = self.s.run("check")
        self.assertIn("изменились после просмотра", out.stdout)
        self.assertIn("restamp", out.stdout, "отказ обязан говорить, что делать")

        self.assertEqual(self.s.run("restamp", "H1").returncode, 0)
        self.assertNotIn("изменились после просмотра", self.s.run("check").stdout)

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
        self.assertIn("причина отказа не записана", out.stdout)

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
        self.assertNotIn("изменился", self.s.run("check").stdout)

        self.s.write("src/one.ts", "стало, починено\n")
        self.s.commit("починка")
        out = self.s.run("check")
        self.assertIn("изменился с момента импорта", out.stdout)
        self.assertIn("set-finding", out.stdout, "отказ обязан говорить, что делать")

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
        self.assertIn("указана строка 900", out.stdout)

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
        self.assertIn("не трогает src/one.ts", out.stdout)

        # а теперь коммит, которого в репозитории нет вовсе
        self.s.run("set-finding", "H1-001", "fixed", "--commit", "0123456789abcdef")
        self.s.run("findings")
        self.assertIn("нет в репозитории", self.s.run("check").stdout)

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
        self.assertIn("вне словаря", self.s.run("check").stdout)

    def test_куцый_манифест_роняет_проверку(self):
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.write("docs/review/blocks/H1-demo.md", "# H1\n\n## Гипотезы\n1. Раз.\n")
        self.s.commit()
        self.s.run("init")
        self.s.run("set-status", "H1", "running")
        self.assertIn("пуст или почти пуст", self.s.run("check").stdout)

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
        self.assertIn("ни одной узды", out.stdout)
        self.assertIn("рукописная копия предиката", out.stdout)
        self.assertIn("--rule", out.stdout, "отказ обязан говорить, что делать")

    def test_узда_записывается_на_весь_корень_сразу(self):
        """Класс закрыт целиком или не закрыт: узда проставляется всем экземплярам."""
        self._three_of_one_root()
        out = self.s.run("set-finding", "H1-001", "fixed", "--commit", "abc1234",
                         "--rule", "eslint: no-handwritten-predicate")
        self.assertEqual(out.returncode, 0, out.stderr)
        rows = [json.loads(l) for l in
                (self.s.root / "docs/review/findings.jsonl").read_text(encoding="utf-8").splitlines()
                if l.strip()]
        self.assertTrue(all(r.get("rule") for r in rows), "узда должна стоять у всех трёх")
        self.s.run("findings")
        self.assertNotIn("ни одной узды", self.s.run("check").stdout)

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
        self.assertNotIn("ни одной узды", self.s.run("check").stdout)

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
        self.assertNotIn("ни одной узды", out.stdout,
                         "живой экземпляр один — узда ещё не требуется")

    def test_команда_roots_показывает_состояние_классов(self):
        self._three_of_one_root()
        out = self.s.run("roots")
        self.assertIn("3 × рукописная копия предиката", out.stdout)
        self.assertIn("УЗДЫ НЕТ", out.stdout)

    # --------------------------------------------------------------------- размер

    def test_блок_который_за_сеанс_не_прочитать_роняет_проверку(self):
        self.s.write("src/huge.ts", "line\n" * 7000)
        self.s.blocks(paths=["src/huge.ts"])
        self.s.manifest(hypotheses=1)
        self.s.commit()
        self.s.run("init")
        self.s.run("coverage")
        out = self.s.run("check")
        self.assertIn("за сеанс не прочитать", out.stdout)

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
        self.assertNotIn("за сеанс не прочитать", out.stdout)

    def test_шаблон_который_ничего_не_нашёл_роняет_проверку(self):
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts", "src/nosuch.ts"])
        self.s.manifest(hypotheses=1)
        self.s.commit()
        self.s.run("init")
        out = self.s.run("check")
        self.assertIn("молча сузился", out.stdout)

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
        self.assertNotIn("старше", self.s.run("check").stdout,
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
        self.assertIn("старше", out.stdout)
        self.assertIn("суток", out.stdout)
        self.assertIn("fetch", out.stdout, "отказ обязан говорить, что делать")

    # ---------------------------------------------------------------- размещение

    def test_инструмент_работает_из_любого_каталога(self):
        """Корень спрашивается у git, а не отсчитывается от файла."""
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=1)
        self.s.commit()
        self.s.run("init")
        moved = self.s.root / "tools" / "review.py"
        moved.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(self.s.tool, moved)
        out = subprocess.run(["python3", str(moved), "status"],
                             capture_output=True, text=True, check=False)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("H1", out.stdout)


class InstallTest(unittest.TestCase):
    """Установщик: набор должен работать сразу после него, без ручных правок."""

    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="review-kit-install-"))
        self.addCleanup(shutil.rmtree, self.root, True)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        for k, v in (("user.email", "t@example.com"), ("user.name", "t")):
            subprocess.run(["git", "-C", str(self.root), "config", k, v], check=True)
        (self.root / "app.ts").write_text("x\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.root), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(self.root), "commit", "-qm", "init"], check=True)

    def install(self, *extra: str) -> subprocess.CompletedProcess:
        return subprocess.run(["python3", str(KIT / "install.py"), str(self.root), *extra],
                              capture_output=True, text=True, check=False)

    def test_после_установки_инструмент_работает_и_советует_свои_команды(self):
        out = self.install("--cli", "npm run review --", "--project", "Демо")
        self.assertEqual(out.returncode, 0, out.stderr)
        tool = self.root / "scripts" / "review" / "review.py"
        self.assertTrue(tool.exists())
        self.assertIn('CLI = "npm run review --"', tool.read_text(encoding="utf-8"),
                      "подсказки собираются из CLI — установщик обязан её прописать")
        for rel in ("docs/review/prompts/hunter.md", "docs/review/README.md",
                    "docs/review/blocks.json", "docs/review/invariants.md"):
            self.assertTrue((self.root / rel).exists(), rel)

        init = subprocess.run(["python3", str(tool), "init"], capture_output=True, text=True)
        self.assertEqual(init.returncode, 0, init.stderr)
        cov = subprocess.run(["python3", str(tool), "coverage"], capture_output=True, text=True)
        self.assertEqual(cov.returncode, 1, "непокрытый файл обязан ронять карту")
        self.assertIn("npm run review --", cov.stdout, "советует команду проекта, а не свою")

    def test_повторная_установка_не_затирает_работу(self):
        self.install("--cli", "npm run review --")
        marker = "# правила именно этого проекта\n"
        inv = self.root / "docs" / "review" / "invariants.md"
        inv.write_text(marker, encoding="utf-8")
        # Промпт правят под проект чаще всего, и ставится он общей дорогой копирования —
        # проверять надо именно её, иначе тест сторожит одну ветку из двух.
        prompt = self.root / "docs" / "review" / "prompts" / "hunter.md"
        prompt.write_text(marker, encoding="utf-8")
        out = self.install("--cli", "make review")
        self.assertEqual(inv.read_text(encoding="utf-8"), marker, "инварианты затёрты")
        self.assertEqual(prompt.read_text(encoding="utf-8"), marker, "правленый промпт затёрт")
        self.assertIn("уже есть", out.stdout)
        self.assertIn('CLI = "npm run review --"',
                      (self.root / "scripts" / "review" / "review.py").read_text(encoding="utf-8"),
                      "повторный запуск не должен менять уже настроенный инструмент")

    def test_вне_репозитория_установка_отказывает(self):
        plain = Path(tempfile.mkdtemp(prefix="review-kit-plain-"))
        self.addCleanup(shutil.rmtree, plain, True)
        out = subprocess.run(["python3", str(KIT / "install.py"), str(plain)],
                             capture_output=True, text=True)
        self.assertEqual(out.returncode, 2)
        self.assertIn("git", out.stderr)


if __name__ == "__main__":
    unittest.main()
