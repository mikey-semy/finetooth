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
import concurrent.futures
import datetime as dt
import hashlib
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
# Обычно — инструмент из скилла. Переменной окружения его подменяет мутационная узда
# (GateMutationTest): она глушит одни ворота в копии инструмента и требует, чтобы
# названный рядом с ними тест на этой копии покраснел.
TOOL = Path(os.environ.get("FINETOOTH_TOOL", SKILL / "scripts" / "review.py"))


def tracked(*args: str) -> list[str]:
    """Файлы набора — у git, по пути от корня. Список, разделённый NUL: имя файла может
    содержать что угодно, кроме NUL, и разбор по строкам на первом же таком имени лжёт."""
    out = subprocess.run(["git", "-C", str(KIT), "ls-files", "-z", *args],
                         capture_output=True, text=True, check=True, env=child_env()).stdout
    return [p for p in out.split("\0") if p]


def shell_gate(rel: str) -> Path:
    """Ворота, написанные на оболочке (`dco.sh`, `guard-grep.sh`) — по пути от корня.

    Обычно — те, что лежат в репозитории. Переменной окружения один из них подменяет
    мутационная узда (`ShellGateMutationTest`): она обращает в успех один отказ скрипта и
    требует, чтобы названный рядом прогон на этой копии покраснел. Формат подмены —
    `путь-от-корня=путь-к-копии`: подменяется ровно один скрипт, остальные остаются своими.
    """
    name, _, path = os.environ.get("FINETOOTH_SHELL_GATE", "").partition("=")
    return Path(path) if name == rel and path else KIT / rel


if "utf-8" not in (sys.getfilesystemencoding() or "").lower().replace("utf8", "utf-8"):
    # Потомкам локаль задаёт child_env, но argv кодирует РОДИТЕЛЬ: имена тестов, пути
    # стенда и сообщения коммитов здесь не-ASCII, и в локали C без режима UTF-8 прогон
    # рассыпается двумя сотнями UnicodeEncodeError, ни один из которых не называет
    # причину. Лучше один отказ, который её называет.
    #
    # Отказ написан по-английски и только из ASCII — единственный такой текст в наборе.
    # Он печатается ровно там, где кириллица печататься не может: stderr в этой локали
    # переходит на backslashreplace, и объяснение приходит вереницей `\xd0\xba`. Причина,
    # которую нельзя прочесть, — это отсутствие причины.
    raise RuntimeError(
        f"filesystem encoding is {sys.getfilesystemencoding()}, and this suite speaks "
        f"Russian: test names, stand paths and commit messages are non-ASCII, and argv "
        f"is encoded by the PARENT process. Run it in a UTF-8 locale or with "
        f"PYTHONUTF8=1: `PYTHONUTF8=1 python3 -m unittest discover -s tests`")


def child_env(**extra: str) -> dict:
    """Окружение ЛЮБОГО потомка теста: инструмента, git, оболочки.

    Приговор набора не должен зависеть от машины, на которой он идёт.

    Локаль. Только `Stand.run` задавал UTF-8, остальные запуски брали её у среды — и
    держалось всё на том, что CPython сам включает режим UTF-8 в локали C. Со снятой
    подстраховкой (`PYTHONUTF8=0 PYTHONCOERCECLOCALE=0`, локаль C) набор краснел
    пятнадцатью падениями и 195 ошибками из 248, начиная с UnicodeEncodeError в `print`
    промпта.

    git. Глобальный конфиг разработчика решал, пройдёт ли прогон: `core.excludesFile`
    с `vendor/` роняет тест про нетрекнутые файлы, `commit.gpgsign=true` без ключа —
    шесть тестов. Конфиг потомка — только локальный, заведённый самим стендом; ветка по
    умолчанию тоже перестаёт зависеть от `init.defaultBranch` разработчика.
    """
    return dict(os.environ,
                LC_ALL="C.UTF-8", LANG="C.UTF-8", PYTHONUTF8="1", PYTHONIOENCODING="utf-8",
                GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull,
                GIT_CONFIG_NOSYSTEM="1", **extra)


class Stand:
    """Временный репозиторий с установленным набором."""

    block_id = "H1"

    def __init__(self, branch: str = "master") -> None:
        self.root = Path(tempfile.mkdtemp(prefix="finetooth-test-"))
        # Инструмент НЕ копируется в проект: он лежит в скилле, а скилл сам — в чужом
        # git-репозитории (этом). Так каждый тест заодно проверяет, что корень берётся
        # по рабочему каталогу, а не по месту, где лежит файл.
        self.tool = TOOL
        for d in ("docs/review/blocks", "docs/review/reports", "src"):
            (self.root / d).mkdir(parents=True, exist_ok=True)
        # Имя ветки названо явно: глобального конфига у потомка нет, а полагаться на
        # встроенное умолчание git значит снова зависеть от версии git на машине.
        self.git("init", "-q", "-b", branch, ".", check=True)
        self.git("config", "user.email", "test@example.com", check=True)
        self.git("config", "user.name", "test", check=True)

    def git(self, *args: str, check: bool = False) -> subprocess.CompletedProcess:
        out = subprocess.run(["git", "-C", str(self.root), *args],
                             capture_output=True, text=True, check=False, env=child_env())
        if check and out.returncode != 0:
            raise AssertionError(f"git {' '.join(args)} → {out.returncode}: "
                                 f"{(out.stderr or out.stdout).strip()}")
        return out

    def write(self, rel: str, text: str) -> None:
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    def commit(self, message: str = "wip") -> None:
        """Коммит стенда обязан состояться.

        Пока он молчал о своём коде возврата, стенд, не дошедший до нужного состояния,
        читался как исправный: тест, который потом ищет в выводе ОТСУТСТВИЕ жалобы,
        зелен и тогда, когда до этого состояния дело не дошло. Глобальный
        `commit.gpgsign=true` роняет так шесть тестов, и ни один не называет причину.
        """
        self.git("add", "-A", check=True)
        self.git("commit", "-qm", message, check=True)

    def run(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(self.tool), *args], cwd=self.root,
                              capture_output=True, text=True, check=False, env=child_env())

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


def refused(out: subprocess.CompletedProcess) -> str:
    """Что `check` записал в ОТКАЗЫ: раздел CHECK FAILED — и только если прогон упал.

    Отказ и предупреждение печатаются одним и тем же предложением, а различает их код
    возврата. Тест, который ищет сообщение во всём выводе, этой разницы не видит:
    измерено мутацией — ворота, перенесённые из `problems` в `warnings`, оставляли
    сорок семь тестов зелёными, а `check` выходил с нулём на состоянии, которое сам же
    отказался принять.
    """
    if out.returncode != 1:
        return ""
    _, _, failed = out.stdout.partition("CHECK FAILED:")
    return failed


def warned(out: subprocess.CompletedProcess) -> str:
    """Что `check` сказал вслух, НЕ уронив прогон: раздел предупреждений при коде 0.

    Обратная сторона `refused`: предупреждение, ставшее отказом, — это остановленная
    работа на состоянии, которое договор принимает.
    """
    if out.returncode != 0:
        return ""
    _, _, rest = out.stdout.partition("WARNINGS (do not fail the check):")
    return rest


class _Values:
    """Где модуль СОБИРАЕТ значения: имя → всё, что в него клали, по областям видимости.

    Общее основание для всех правил по исходнику. Правило, написанное на форму записи,
    слепнет от первого же безобидного переноса: приставка `["git", "-C", str(ROOT)]`,
    вынесенная в модульную переменную, звёздочка вместо склейки, псевдоним модуля,
    переименованная переменная записи. Измерено трижды подряд — и каждый раз ответом было
    «допишем ещё одну ветку `isinstance`», после чего находилась следующая форма.
    Значение собирают в одном месте, а читают в другом; смотреть надо туда, где собрали.

    Здесь нет исполнения: имена разрешаются по ВСЕМУ, что в них когда-либо клали в этой
    области видимости и в объемлющих. Объединение — намеренно щедрое: правило,
    основанное на нём, ошибается в сторону лишней жалобы, а не пропущенного дефекта.
    """

    def __init__(self, source: str) -> None:
        self.tree = ast.parse(source)
        self.parent: dict = {}
        self.scope: dict = {}
        self._map(self.tree, self.tree)
        self.assigned: dict = {}      # (область, имя) → всё, что в него клали
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Assign):
                targets = node.targets
            elif isinstance(node, (ast.AugAssign, ast.AnnAssign)):
                targets = [node.target]
            else:
                continue
            if node.value is None:
                continue
            for t in targets:
                if isinstance(t, ast.Name):
                    self.assigned.setdefault((self.scope_of(node), t.id), []).append(node.value)

    def _map(self, node, scope) -> None:
        for child in ast.iter_child_nodes(node):
            self.parent[child] = node
            self.scope[child] = scope
            inner = child if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef,
                                                ast.Lambda)) else scope
            self._map(child, inner)

    def scope_of(self, node):
        return self.scope.get(node, self.tree)

    def lookup(self, name: str, scope) -> list:
        """Всё, что клали в имя: сначала своя область, потом объемлющие."""
        while True:
            if (scope, name) in self.assigned:
                return self.assigned[(scope, name)]
            if scope is self.tree:
                return []
            scope = self.scope_of(scope)

    def elements(self, node, seen: tuple = ()) -> list:
        """Элементы списка, собранного как угодно: литералом, склейкой, звёздочкой, по имени."""
        if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            out = []
            for e in node.elts:
                out += self.elements(e.value, seen) if isinstance(e, ast.Starred) else [e]
            return out
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            return self.elements(node.left, seen) + self.elements(node.right, seen)
        if isinstance(node, ast.Name) and node.id not in seen:
            return self.name_elements(node.id, self.scope_of(node), seen)
        return []

    def name_elements(self, name: str, scope, seen: tuple = ()) -> list:
        return [e for v in self.lookup(name, scope)
                for e in self.elements(v, seen + (name,))]

    def literal(self, node, seen: tuple = ()):
        """Значение выражения с подставленными именами: таблицу собирают из кусков."""
        if isinstance(node, ast.Name) and node.id not in seen:
            values = self.lookup(node.id, self.scope_of(node))
            if values:
                return self.literal(values[-1], seen + (node.id,))
        if isinstance(node, ast.Dict):
            out = {}
            for key, value in zip(node.keys, node.values):
                if key is None:
                    out.update(self.literal(value, seen))
                else:
                    out[self.literal(key, seen)] = self.literal(value, seen)
            return out
        if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            items = [self.literal(e, seen) for e in node.elts]
            return items if isinstance(node, ast.List) else tuple(items)
        return ast.literal_eval(node)

    def text(self, node) -> str:
        """Текст выражения ВМЕСТЕ с тем, что стоит за его именами."""
        parts = [ast.unparse(node)]
        for inner in ast.walk(node):
            if isinstance(inner, ast.Name):
                parts += [ast.unparse(v) for v in self.lookup(inner.id, self.scope_of(inner))]
        return " ".join(parts)


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
        self.assertIn("coverage.tsv is stale", refused(self.s.run("check")))
        self.s.run("coverage")
        self.assertNotIn("coverage.tsv is stale", self.s.run("check").stdout)

    def test_подмодуль_не_файл_а_симлинк_файл_без_двойного_счёта(self):
        """Подмодуль не открыть; симлинк — правка, которую надо видеть, но считать один раз."""
        self.s.write("src/real.ts", "одна\nдве\nтри\n")
        (self.s.root / "src" / "link.ts").symlink_to("real.ts")
        sub = self.s.root / "vendor"
        subprocess.run(["git", "init", "-q", str(sub)], check=True, env=child_env())
        for k, v in (("user.email", "t@e"), ("user.name", "t")):
            subprocess.run(["git", "-C", str(sub), "config", k, v], check=True, env=child_env())
        (sub / "f.txt").write_text("x\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(sub), "add", "-A"], check=True, env=child_env())
        subprocess.run(["git", "-C", str(sub), "commit", "-qm", "sub"], check=True, env=child_env())
        subprocess.run(["git", "-C", str(self.s.root), "-c", "protocol.file.allow=always",
                        "submodule", "add", "-q", "./vendor", "lib"],
                       check=False, capture_output=True, env=child_env())

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
        self.assertIn("has no hypotheses", refused(out), out.stdout)

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
        self.assertIn("coverage limits", refused(out).lower(), out.stdout)

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
                          refused(self.s.run("check")), limits)
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
        self.assertIn("changed after the review", refused(out), out.stdout)
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

        out = self.s.run("check")
        self.assertIn("without a fingerprint of what was reviewed", refused(out), out.stdout)
        self.assertIn("no code fingerprint", refused(out), out.stdout)

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
        out = self.s.run("check")
        self.assertIn("manifest hypotheses changed", refused(out), out.stdout)
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
        self.assertIn("is empty — there is a file, there is no verification",
                      refused(self.s.run("check")))

        self.s.write("docs/review/reports/H1-demo.verify.md",
                     "# проверяющий\n## Вердикты\n## Охват\n")
        self.assertIn("is empty — there is a file, there is no verification",
                      refused(self.s.run("check")), "одни заголовки — тоже пустой отчёт")

        self.s.write("docs/review/reports/H1-demo.verify.md",
                     "# проверяющий\nПосмотрел, всё хорошо, охват полный.\n")
        self.assertIn("no verdict on any finding", refused(self.s.run("check")))

        self.s.write("docs/review/reports/H1-demo.verify.md",
                     "# проверяющий\n| H1-001 | confirmed | прогнал тест, падает |\n")
        self.assertIn("no coverage verdict", refused(self.s.run("check")),
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
        out = self.s.run("check")
        self.assertIn("different verdicts", refused(out), out.stdout)
        self.assertIn("H1.1", out.stdout)

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
        out = self.s.run("check")
        self.assertIn("older than 7 days", warned(out), out.stdout)
        self.assertIn("H1-001 (10d)", warned(out), out.stdout)

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

    def test_риск_вне_словаря_это_отказ_а_не_трейсбек(self):
        """`risk` пишут руками в blocks.json. Слово мимо словаря доходило до
        `SEVERITIES.index` и выходило к человеку как ValueError."""
        self._churn_history(risk_first="катастрофа")
        out = self.s.run("order")
        self.assertEqual(out.returncode, 2, out.stdout + out.stderr)
        self.assertNotIn("Traceback", out.stderr)
        self.assertIn("risk", out.stderr)
        self.assertIn("blocks.json", out.stderr)
        self.assertIn("critical", out.stderr, "отказ обязан назвать словарь")

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
                             capture_output=True, text=True, env=child_env())
        self.assertEqual(out.returncode, 0, out.stderr)
        # два сообщения по 1001 на вход, не три
        self.assertIn("input 0.0M tokens (90% from cache", out.stdout)
        self.assertIn("re-reads 1", out.stdout)
        self.assertIn("output 0k", out.stdout)
        full = subprocess.run([sys.executable, str(SKILL / "scripts" / "axes.py"), str(path)],
                              capture_output=True, text=True, env=child_env()).stdout
        self.assertIn("input total          2,002", full)

    def test_run_role_отказывает_на_неизвестной_роли(self):
        """Скрипт берётся через `shell_gate`: этот отказ — предмет мутационной узды ворот
        на оболочке, а она подменяет скрипт копией через окружение."""
        out = subprocess.run(
            ["bash", str(shell_gate("skills/finetooth/assets/run-role.sh")), "H1", "nosuch"],
            capture_output=True, text=True, env=child_env())
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
        self.assertIn("reference(s) to findings in the code", warned(self.s.run("check")))

    def test_refs_называет_не_ASCII_путь_как_он_есть(self):
        """`git grep` экранирует такой путь по-C и разделяет поля двоеточием, которое в
        пути законно: оператор получал `"src/\\320\\274…"` и путь, обрезанный по первому
        двоеточию, — то есть адрес, по которому ничего не найти."""
        self.s.write("src/модуль:раз.ts", "// см. H1-001 — причина\n")
        self.s.blocks(paths=["src"])
        self.s.manifest(hypotheses=1)
        self.s.write("docs/review/reports/H1-findings.jsonl", json.dumps({
            "block": "H1", "severity": "low", "confidence": "confirmed", "status": "open",
            "file": "src/модуль:раз.ts", "claim": "дефект", "scenario": "x делает y"},
            ensure_ascii=False) + "\n")
        self.s.commit()
        self.s.run("init")
        self.s.run("import", "H1")
        out = self.s.run("refs")
        self.assertEqual(out.returncode, 1, out.stdout + out.stderr)
        self.assertIn("src/модуль:раз.ts:1: H1-001", out.stdout, out.stdout)
        self.assertNotIn("\\320", out.stdout, "путь пришёл экранированным")

    def test_охотник_может_исполнять(self):
        """Три блока подряд (T1–T3) охотнику отказывали в python3, и блок `proof: measured`
        доказывался чтением. Список разрешений охотника обязан включать исполнение."""
        text = (SKILL / "assets" / "run-role.sh").read_text(encoding="utf-8")
        hunter = next(ln for ln in text.splitlines() if ln.strip().startswith("hunter)"))
        for tool in ("Bash(python3 *)", "Bash(npm test *)", "Bash(node *)"):
            self.assertIn(tool, hunter)

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
        self.assertIn("duplicate of nonexistent H1-777", refused(self.s.run("check")))

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
        self.assertIn("status rejected but confidence confirmed", refused(self.s.run("check")))

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
        self.assertIn("reject reason is not recorded", refused(out), out.stdout)

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
        self.assertIn("changed since import", refused(out), out.stdout)
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
        self.assertIn("line 900 is cited", refused(out), out.stdout)

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
        self.assertIn("does not touch src/one.ts", refused(out), out.stdout)

        # а теперь коммит, которого в репозитории нет вовсе
        self.s.run("set-finding", "H1-001", "fixed", "--commit", "0123456789abcdef")
        self.s.run("findings")
        self.assertIn("is not in the repository", self.s.run("check").stdout)

    def test_путь_с_пробелом_не_ломает_проверку_коммита(self):
        """Обе стороны: на пути с пробелом ворота ПРОПУСКАЮТ верный коммит и ЛОВЯТ чужой.

        Пока тест проверял только отсутствие жалобы, он был зелен и тогда, когда ворота
        для таких путей выключены вовсе, — измерено мутацией.
        """
        self.s.write("src/my file.ts", "a\n")
        self.s.write("src/other.ts", "b\n")
        self.s.blocks(paths=["src"])
        self.s.manifest(hypotheses=1)
        self.s.write("docs/review/reports/H1-findings.jsonl", json.dumps({
            "block": "H1", "severity": "low", "confidence": "confirmed", "status": "open",
            "file": "src/my file.ts", "claim": "дефект", "scenario": "сценарий"},
            ensure_ascii=False) + "\n")
        self.s.commit()
        self.s.run("init")
        self.s.run("coverage")
        self.s.run("import", "H1")

        # правка сделана в соседнем файле — ворота обязаны сработать и здесь
        self.s.write("src/other.ts", "b\nправка не там\n")
        self.s.commit("правка соседнего модуля")
        wrong = self.s.git("rev-parse", "HEAD").stdout.strip()
        self.assertEqual(
            self.s.run("set-finding", "H1-001", "fixed", "--commit", wrong).returncode, 0)
        self.s.run("findings")
        self.assertIn("does not touch src/my file.ts", refused(self.s.run("check")))

        # а правка самого файла принимается
        self.s.write("src/my file.ts", "a\nпочинено\n")
        self.s.commit("починка")
        sha = self.s.git("rev-parse", "HEAD").stdout.strip()
        self.assertEqual(
            self.s.run("set-finding", "H1-001", "fixed", "--commit", sha).returncode, 0)
        self.s.run("coverage")
        self.s.run("findings")
        out = self.s.run("check")
        self.assertEqual(out.returncode, 0, out.stdout)
        self.assertNotIn("does not touch", out.stdout)

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
        self.assertIn("is not in the repository", refused(self.s.run("check")))

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
        self.assertIn("is not in the vocabulary", refused(self.s.run("check")))

    def test_куцый_манифест_роняет_проверку(self):
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.write("docs/review/blocks/H1-demo.md", "# H1\n\n## Гипотезы\n1. Раз.\n")
        self.s.commit()
        self.s.run("init")
        self.s.run("set-status", "H1", "running")
        self.assertIn("is empty or nearly empty", refused(self.s.run("check")))

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
        self.assertIn("cannot be read in one session", refused(out), out.stdout)

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
        self.assertIn("and no guard", refused(out), out.stdout)
        self.assertIn("рукописная копия предиката", out.stdout)
        self.assertIn("--rule", out.stdout, "отказ обязан говорить, что делать")

    def test_узда_на_все_названные_экземпляры_закрывает_корень(self):
        """Класс закрыт, когда узда записана на каждый его экземпляр — названный в команде."""
        self._three_of_one_root()
        self.s.write("eslint.config.mjs", "export default [];\n")
        self.s.commit("узда")
        out = self.s.run("set-finding", "H1-001", "H1-002", "H1-003", "fixed",
                         "--commit", "abc1234", "--rule", "eslint.config.mjs")
        self.assertEqual(out.returncode, 0, out.stderr)
        rows = self._register()
        self.assertTrue(all(r.get("rule") for r in rows), "узда должна стоять у всех трёх")
        self.s.run("findings")
        out = self.s.run("check")
        self.assertNotIn("and no guard", out.stdout)
        self.assertNotIn("carry no guard", out.stdout)

    def _register(self) -> list[dict]:
        return [json.loads(l) for l in
                (self.s.root / "docs/review/findings.jsonl").read_text(encoding="utf-8").splitlines()
                if l.strip()]

    # Отметка «давно», которую запись обязана сменить, если её тронули, — и сохранить, если нет.
    OLD_STAMP = "2026-01-01T00:00:00Z"

    def _root_across_blocks(self) -> None:
        """Один корень на двух блоках, часть экземпляров уже починена под своей уздой, и
        второй корень, у всех экземпляров которого узда одна. Реестр пишется напрямую:
        проверяется `set-finding` и `roots`, а не путь импорта."""
        for f in ("src/one.ts", "src/two.ts", "src/three.ts", "src/four.ts", "src/five.ts",
                  "tests/old.test.ts", "tests/new.test.ts"):
            self.s.write(f, "x\n")
        self.s.blocks(paths=["src/one.ts", "src/two.ts", "src/three.ts"], extra_blocks=[{
            "id": "H2", "slug": "other", "phase": 1, "title": "Другой блок", "role": "demo",
            "goal": "соседний блок", "paths": ["src/four.ts", "src/five.ts"], "ref_paths": []}])
        self.s.commit()

        def row(fid, block, file, status="open", root="общий корень", **extra):
            return {"id": fid, "block": block, "severity": "medium", "confidence": "confirmed",
                    "status": status, "file": file, "root": root, "claim": f"экземпляр {fid}",
                    "scenario": "сценарий", "updated_at": self.OLD_STAMP, **extra}
        rows = [
            row("H1-001", "H1", "src/one.ts"),
            row("H1-002", "H1", "src/two.ts"),
            row("H1-003", "H1", "src/three.ts", "fixed", fix_commit="abc1234",
                rule="tests/old.test.ts"),
            row("H2-001", "H2", "src/four.ts"),
            row("H2-002", "H2", "src/five.ts", "fixed", fix_commit="def5678",
                rule="tests/old.test.ts"),
            row("H2-003", "H2", "src/four.ts", root="согласный корень", rule="tests/new.test.ts"),
            row("H2-004", "H2", "src/five.ts", root="согласный корень", rule="tests/new.test.ts"),
            row("H1-004", "H1", "src/one.ts", root="согласный корень", rule="tests/new.test.ts"),
        ]
        (self.s.root / "docs/review/findings.jsonl").write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")

    def test_узда_записывается_только_на_названные_находки(self):
        """`--rule` пишет узду названным находкам и больше никому (#28).

        Прежде узда уходила на все находки с тем же корнем: исполнители чужих блоков
        переписывали узды починенных находок тестом, зелёным на их дефекте, и ни у одной
        переписанной записи не менялся `updated_at`. Обе стороны: названная находка
        получает узду и новую отметку; соседи по корню — в своём блоке, в чужом, уже
        починенные — остаются как были, вместе с отметкой.
        """
        self._root_across_blocks()
        out = self.s.run("set-finding", "H1-001", "H1-002", "open", "--rule", "tests/new.test.ts")
        self.assertEqual(out.returncode, 0, out.stderr)
        rows = {r["id"]: r for r in self._register()}
        for fid in ("H1-001", "H1-002"):
            with self.subTest(названа=fid):
                self.assertEqual(rows[fid].get("rule"), "tests/new.test.ts")
                self.assertNotEqual(rows[fid].get("updated_at"), self.OLD_STAMP,
                                    "смена узды — это правка записи: отметка обязана смениться")
        for fid, rule in (("H1-003", "tests/old.test.ts"), ("H2-001", None),
                          ("H2-002", "tests/old.test.ts")):
            with self.subTest(сосед=fid):
                self.assertEqual(rows[fid].get("rule"), rule,
                                 f"{fid} не назван в команде, а его узду переписали")
                self.assertEqual(rows[fid].get("updated_at"), self.OLD_STAMP)
                self.assertEqual(rows[fid].get("status"), "open" if rule is None else "fixed")

    def test_узда_снимается_только_с_названной_находки(self):
        """Узду, которая не краснеет на дефекте находки, можно снять (`--clear-rule`): иначе
        реестр продолжает утверждать, что класс держится. Обе стороны: у названной узды нет
        и отметка сменилась; соседи по корню остались при своих; `--rule` вместе с
        `--clear-rule` — отказ, а не молчаливый выбор одного из двух."""
        self._root_across_blocks()
        out = self.s.run("set-finding", "H1-003", "fixed", "--clear-rule")
        self.assertEqual(out.returncode, 0, out.stderr)
        rows = {r["id"]: r for r in self._register()}
        self.assertNotIn("rule", rows["H1-003"])
        self.assertNotEqual(rows["H1-003"].get("updated_at"), self.OLD_STAMP)
        self.assertEqual(rows["H1-003"].get("fix_commit"), "abc1234")
        self.assertEqual(rows["H2-002"].get("rule"), "tests/old.test.ts")
        self.assertEqual(rows["H2-002"].get("updated_at"), self.OLD_STAMP)
        out = self.s.run("set-finding", "H2-002", "fixed", "--rule", "x", "--clear-rule")
        self.assertNotEqual(out.returncode, 0)
        self.assertIn("--clear-rule together", out.stderr)
        self.assertEqual({r["id"]: r for r in self._register()}["H2-002"].get("rule"),
                         "tests/old.test.ts")

    def test_узда_на_починенную_находку_без_повторного_коммита(self):
        """Записать узду на уже починенную находку — значит назвать её со статусом `fixed`;
        требовать `--commit` заново значило бы одной командой затереть разные коммиты
        починки у нескольких находок. Обратная сторона: открытая находка без коммита
        в `fixed` по-прежнему не переходит."""
        self._root_across_blocks()
        out = self.s.run("set-finding", "H1-003", "H2-002", "fixed", "--rule", "tests/new.test.ts")
        self.assertEqual(out.returncode, 0, out.stderr)
        rows = {r["id"]: r for r in self._register()}
        self.assertEqual((rows["H1-003"]["fix_commit"], rows["H2-002"]["fix_commit"]),
                         ("abc1234", "def5678"), "коммиты починки обязаны сохраниться свои")
        self.assertEqual({rows[f]["rule"] for f in ("H1-003", "H2-002")}, {"tests/new.test.ts"})
        out = self.s.run("set-finding", "H1-001", "fixed", "--rule", "tests/new.test.ts")
        self.assertNotEqual(out.returncode, 0)
        self.assertIn("without a fix commit", out.stderr)
        self.assertNotEqual({r["id"]: r for r in self._register()}["H1-001"].get("status"), "fixed")

    def test_roots_показывает_узды_каждого_экземпляра(self):
        """`roots` больше не выдаёт первую найденную узду за узду корня (#28): корень, чьи
        экземпляры несут разные узды или часть — никакой, помечен и расписан, кто под чем.
        Обратная сторона: корень с одной уздой на всех читается одной строкой, как прежде."""
        self._root_across_blocks()
        self.assertEqual(self.s.run("set-finding", "H1-001", "open", "--rule",
                                    "tests/new.test.ts").returncode, 0)
        out = self.s.run("roots")
        self.assertEqual(out.returncode, 0, out.stderr)
        text = out.stdout
        head = next(l for l in text.splitlines() if "× общий корень" in l)
        self.assertIn("GUARDS DIFFER", head)
        self.assertIn("2 of 5 instances without one", head)
        self.assertIn("tests/new.test.ts — H1-001\n", text)
        self.assertIn("tests/old.test.ts — H1-003, H2-002\n", text)
        self.assertIn("no guard — H1-002, H2-001\n", text)
        agreed = next(l for l in text.splitlines() if "× согласный корень" in l)
        self.assertIn("guard: tests/new.test.ts", agreed)
        self.assertNotIn("GUARDS DIFFER", agreed)
        # Разные узды без единого экземпляра без узды — тоже расхождение, но без счёта.
        self.assertEqual(self.s.run("set-finding", "H1-002", "H2-001", "open", "--rule",
                                    "tests/old.test.ts").returncode, 0)
        head = next(l for l in self.s.run("roots").stdout.splitlines() if "× общий корень" in l)
        self.assertIn("GUARDS DIFFER", head)
        self.assertNotIn("without one", head)

    def test_корень_с_уздой_не_на_всех_экземплярах_предупреждает(self):
        """Узда одного экземпляра больше не держит остальные (#28): третий повтор, у части
        которого узды нет, `check` называет — предупреждением, не отказом: дойдёт ли
        записанная узда до них, решает прогон на их дефекте, а не инструмент."""
        self._three_of_one_root()
        self.s.write("eslint.config.mjs", "export default [];\n")
        # узда — не код под ревью: без исключения файл ничей, и `check` падает не о том
        self.s.blocks(paths=["src/one.ts", "src/two.ts", "src/three.ts"],
                      exclusions=[{"pattern": "eslint.config.mjs", "reason": "узда"}])
        self.s.commit("узда")
        self.assertEqual(self.s.run("set-finding", "H1-001", "open", "--rule",
                                    "eslint.config.mjs").returncode, 0)
        self.s.run("findings")
        out = self.s.run("check")
        said = warned(out)
        self.assertIn("2 of 3 instances carry no guard (H1-002, H1-003)", said, out.stdout)
        self.assertIn("--rule", said, "предупреждение обязано говорить, что делать")
        self.assertNotIn("and no guard", out.stdout, "класс с уздой — не класс без узды")

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
        self.assertIn("no such file", refused(self.s.run("check")),
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
        self.assertIn("cannot be read in one session", refused(out), out.stdout)

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
        self.assertIn("silently shrank", refused(out), out.stdout)

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
        self.assertIn("matches only untracked files (1)", refused(out), out.stdout)
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
        subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True, env=child_env())
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
        env = child_env(GIT_COMMITTER_DATE=long_ago, GIT_AUTHOR_DATE=long_ago)
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
        self.assertIn("behind", refused(out), out.stdout)
        self.assertIn("days", out.stdout)
        self.assertIn("fetch", out.stdout, "отказ обязан говорить, что делать")

    def test_свежий_коммит_в_давней_ветке_не_прячет_устаревание(self):
        """Своя вершина новее чужой — а ветка всё равно без единого чужого исправления."""
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=1)
        self.s.commit()

        bare = self.s.root.parent / (self.s.root.name + "-origin2.git")
        subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True, env=child_env())
        self.addCleanup(shutil.rmtree, bare, True)
        self.s.git("remote", "add", "origin", str(bare))

        # общий предок — двухнедельной давности
        long_ago = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=14)).isoformat()
        env = child_env(GIT_COMMITTER_DATE=long_ago, GIT_AUTHOR_DATE=long_ago)
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
        out = subprocess.run([sys.executable, str(TOOL), "status"], cwd=self.s.root / "src",
                             capture_output=True, text=True, check=False, env=child_env())
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("H1", out.stdout, "из подкаталога — тот же корень")
        after = kit_state.read_bytes() if kit_state.exists() else None
        self.assertEqual(before, after, "состояние не должно уехать в репозиторий, где лежит скилл")

    def test_вне_репозитория_инструмент_отказывает(self):
        plain = Path(tempfile.mkdtemp(prefix="finetooth-plain-"))
        self.addCleanup(shutil.rmtree, plain, True)
        out = subprocess.run([sys.executable, str(TOOL), "status"], cwd=plain,
                             capture_output=True, text=True, check=False, env=child_env())
        self.assertEqual(out.returncode, 2)
        self.assertIn("git", out.stderr)
        self.assertEqual(subprocess.run([sys.executable, str(TOOL), "version"], cwd=plain,
                                        capture_output=True, text=True, env=child_env()).returncode, 0,
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
        self.assertIn("is not in the repository", refused(self.s.run("check")),
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
        self.assertIn("deferred without a reason", refused(self.s.run("check")))

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
        self.assertIn("phase 1 comes after phase 2", refused(self.s.run("check")))

    def test_заблокированный_блок_не_значит_закончено(self):
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=1)
        self.s.commit()
        self.s.run("init")
        self.s.run("set-status", "H1", "blocked")
        self.assertIn("blocked without a note", refused(self.s.run("check")))
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
        out = self.s.run("check")
        self.assertIn("not named by full path", refused(out), out.stdout)
        self.assertIn("src/a/page.tsx", out.stdout, "базового имени мало — одноимённых файлов много")
        self.assertNotIn("vendor.min.js", out.stdout, "исключённое называть не требуется")
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

    def test_ревьюер_правок_знает_объём_диффа_и_про_scope(self):
        """Бюджет стоит в самом задании, а не в голове ведущей сессии.

        Дифф первого круга блока об инструменте был 193 КБ; правило говорило «читай
        целиком» без условия, объём не назывался нигде, а `--scope` не упоминался ни в
        одном из двух шаблонов. Агент читает сколько влезло и отчитывается за целое.
        """
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=1)
        self.s.commit()
        base = self.s.git("rev-parse", "HEAD").stdout.strip()
        self.s.write("src/one.ts", "a\n" + "изменено\n" * 300)
        self.s.commit("правка")
        self.s.run("init")
        out = self.s.run("prompt", "H1", "--role", "fixreview", "--diff", f"{base}...HEAD")
        self.assertEqual(out.returncode, 0, out.stderr)
        head = out.stdout.split("````diff")[0]
        self.assertRegex(head, r"Дифф ниже: \d+ КБ, \d+ строк")
        self.assertIn("--scope", head, "выход из положения назван там же, где объём")
        hunter = self.s.run("prompt", "H1", "--role", "hunter").stdout
        self.assertNotIn("Дифф ниже", hunter, "замер диффа не протекает в другие роли")
        self.assertNotIn("{{", hunter, "и не оставляет незаполненной подстановки")

    def test_названный_рядом_с_объёмом_выход_действительно_уменьшает_дифф(self):
        """Выход, названный там же, где объём, обязан работать.

        Сообщение звало разделить дифф через `--scope`, а `--scope` его не уменьшает:
        замерено — промпт с ним на 120 байт БОЛЬШЕ. Уменьшает дифф только более узкий
        диапазон `--diff`, и названо в сообщении обязано быть именно это.
        """
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=1)
        self.s.commit()
        base = self.s.git("rev-parse", "HEAD").stdout.strip()
        self.s.write("src/one.ts", "a\n" + "первая часть\n" * 300)
        self.s.commit("первая часть правок")
        middle = self.s.git("rev-parse", "HEAD").stdout.strip()
        self.s.write("src/one.ts", "a\n" + "первая часть\n" * 300 + "вторая часть\n" * 300)
        self.s.commit("вторая часть правок")
        self.s.run("init")
        whole = self.s.run("prompt", "H1", "--role", "fixreview", "--diff", f"{base}...HEAD")
        self.assertEqual(whole.returncode, 0, whole.stderr)
        measure = next(l for l in whole.stdout.splitlines() if l.startswith("Дифф ниже:"))
        self.assertIn("--diff", measure,
                      "выход из положения — тот флаг, который дифф действительно уменьшает")
        part = self.s.run("prompt", "H1", "--role", "fixreview", "--diff", f"{base}...{middle}")
        self.assertEqual(part.returncode, 0, part.stderr)
        self.assertLess(len(part.stdout), len(whole.stdout) * 3 // 4,
                        "названный выход обязан уменьшать промпт, а не переименовывать отчёт")
        # Вторая сторона: `--scope` остаётся тем, чем был, — делит ответственность за
        # отчёт, и сообщение больше не выдаёт его за способ уменьшить чтение.
        scoped = self.s.run("prompt", "H1", "--role", "fixreview", "--diff", f"{base}...HEAD",
                            "--scope", "первая")
        self.assertEqual(scoped.returncode, 0, scoped.stderr)
        self.assertIn("**первая**", scoped.stdout)
        self.assertIn("H1-demo.fixreview-1-первая.md", scoped.stdout)
        self.assertGreaterEqual(len(scoped.stdout), len(whole.stdout),
                                "`--scope` дифф не уменьшает — и сообщение этого не обещает")

    def test_каждая_роль_с_полным_списком_файлов_получает_и_его_объём(self):
        """Бюджет чтения — не привилегия одной роли, а часть задания каждой, кому вручают
        блок целиком. Замер получал только охотник; проверяющему доставался тот же список
        «прочитать все» и ни слова о его цене — а это самая дорогая роль (165 → 330 ходов),
        и без меры ей нечем сказать, что блок не помещается."""
        for path in sorted((SKILL / "references").glob("*.md")):
            text = path.read_text(encoding="utf-8")
            if "{{FILES}}" not in text:
                continue
            with self.subTest(файл=path.name):
                self.assertIn("{{VOLUME}}", text,
                              f"{path.name} вручает список файлов блока и молчит о его "
                              f"объёме: роль узнаёт, что читать, и не узнаёт, сколько это")
        self.s.write("src/one.ts", "a\n" * 200)
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=1)
        self.s.commit()
        self.s.run("init")
        for role in ("hunter", "verify"):
            out = self.s.run("prompt", "H1", "--role", role)
            with self.subTest(роль=role):
                self.assertEqual(out.returncode, 0, out.stderr)
                self.assertRegex(out.stdout, r"Файлов: \d+\. Строк: \d+",
                                 f"роль {role} получает список файлов без замера")
                self.assertNotIn("{{", out.stdout, "и без незаполненных подстановок")

    # Два раздела отчёта охотника про охват: что прочитано и что НЕ прочитано. Ворота
    # читают второй, а предупреждение об объёме посылает непрочитанное в тот, который
    # назовёт само, — и это обязан быть тот же раздел.
    COVERAGE_SECTIONS = {"Охват": "- прочитано файлов: 0 из 1",
                         "Ограничения охвата": "**Обязательный раздел, даже если он короткий.**"}
    UNREAD = "- не прочитано, поимённо: src/one.ts"
    LIMITS_REFUSAL = "'Coverage limits' section of the hunter report is empty"

    def _hunter_naming_unread_in(self, section: str) -> str:
        body = dict(self.COVERAGE_SECTIONS)
        body[section] += "\n" + self.UNREAD
        return ("# H1 — отчёт охотника\n\n## Гипотезы\n"
                "- H1.1 — проверена: прочитано то, что влезло\n\n"
                + "".join(f"## {h}\n{t}\n\n" for h, t in body.items()))

    def test_отчёт_написанный_по_предупреждению_об_объёме_проходит_ворота(self):
        """Предупреждение о непомерном блоке называет раздел, куда писать непрочитанное, и
        ворота обязаны читать ИМЕННО его: сообщение звало в раздел про охват, а ворота
        читают раздел ограничений охвата — отчёт, написанный ровно по предупреждению,
        проверка отказывала. Раздел здесь не вписан в тест, а вычитан из самого
        предупреждения: поменяется сообщение — поменяется и то, что пишет охотник."""
        self.s.write("src/one.ts", "a\n" * 100)
        self.s.blocks(paths=["src/one.ts"], readable_lines=50)
        self.s.manifest(hypotheses=1)
        self.s.commit()
        self.s.run("init")
        prompt = self.s.run("prompt", "H1", "--role", "hunter")
        self.assertEqual(prompt.returncode, 0, prompt.stderr)
        warning = next((l for l in prompt.stdout.splitlines() if "⚠️" in l), "").lower()
        self.assertIn("поимённо", warning, "предупреждения об объёме в промпте нет")
        named = max((h for h in self.COVERAGE_SECTIONS
                     if all(w[:5].lower() in warning for w in h.split())),
                    key=len, default="")
        self.assertIn(named, self.COVERAGE_SECTIONS,
                      f"предупреждение не называет ни одного раздела отчёта: {warning}")
        self.s.reports(hunter=self._hunter_naming_unread_in(named), verify=FULL_VERIFY)
        self.s.run("set-status", "H1", "hunted")
        self.s.run("set-status", "H1", "verified")
        self.s.commit("отчёты")
        out = self.s.run("check")
        self.assertNotIn(self.LIMITS_REFUSAL, refused(out),
                         "охотник написал непрочитанное туда, куда послало предупреждение, "
                         "и ворота отказали: сообщение называет не тот раздел, который они "
                         "читают")
        # Вторая сторона: ворота не ослабли. Тот же отчёт с непрочитанным в СОСЕДНЕМ
        # разделе по-прежнему отказывают — изменилось только то, куда посылает сообщение.
        other = next(h for h in self.COVERAGE_SECTIONS if h != named)
        self.s.reports(hunter=self._hunter_naming_unread_in(other))
        self.s.commit("отчёт мимо раздела")
        self.assertIn(self.LIMITS_REFUSAL, refused(self.s.run("check")),
                      "непрочитанное названо мимо раздела ограничений охвата, а ворота молчат")

    # Раздел отчёта проверяющего про охват: его заголовок ворота не читают (заголовки
    # отброшены), а читают строки под ним — и там обязан стоять вердикт.
    VERIFY_COVERAGE = {"en": "Block coverage status", "ru": "Состояние охвата блока"}
    QUOTED_VERDICT = re.compile(r"[\"“«]([^\"”»\n]+)[\"”»]")

    def test_отчёт_проверяющего_по_предупреждению_об_объёме_проходит_ворота(self):
        """Предупреждение проверяющему — два указания: КУДА писать непрочитанное и ЧТО там
        сказать. Раздел держит `NamedExitTest`, а слова — только этот тест: пути под
        заголовком раздела вердиктом охвата не являются, и ворота отказывают отчёт
        «no coverage verdict». Удалённая из сообщения оговорка оставляла весь набор
        зелёным (T2 fix review round 3, R3-002) — тот же дефект, что T2-023, у второй роли.
        Слова не вписаны в тест, а вычитаны из предупреждения на каждом языке: отчёт пишет
        то, что велено, и ворота обязаны его принять."""
        hunter = ("# h\n## Гипотезы\n- H1.1 — проверена: да\n"
                  "## Ограничения охвата\n- не прочитано: src/one.ts\n")
        for lang, section in self.VERIFY_COVERAGE.items():
            with self.subTest(lang=lang):
                s = Stand()
                self.addCleanup(s.cleanup)
                s.write("src/one.ts", "a\n" * 100)
                s.blocks(paths=["src/one.ts"], readable_lines=50, lang=lang)
                s.manifest(hypotheses=1)
                s.commit()
                s.run("init")
                prompt = s.run("prompt", "H1", "--role", "verify")
                self.assertEqual(prompt.returncode, 0, prompt.stderr)
                warning = next((l for l in prompt.stdout.splitlines() if "⚠️" in l), "")
                self.assertTrue(warning, "предупреждения об объёме в промпте проверяющего нет")
                said = self.QUOTED_VERDICT.findall(warning)
                self.assertTrue(said, f"предупреждение не даёт проверяющему слов, которыми "
                                      f"сказать, что охват неполный: {warning}")
                paths_only = (f"# v\n\n## Verdicts\nНаходок нет.\n\n## {section}\n"
                              f"- src/one.ts\n")
                s.reports(hunter=hunter, verify=paths_only.replace(
                    f"## {section}\n", f"## {section}\n{said[-1]}.\n"))
                s.run("set-status", "H1", "hunted")
                s.run("set-status", "H1", "verified")
                s.commit("отчёт по предупреждению")
                self.assertNotIn("no coverage verdict", refused(s.run("check")),
                                 f"проверяющий написал ровно то, что велело предупреждение "
                                 f"({said[-1]!r}), и ворота отказали")
                # Вторая сторона: одни пути под заголовком раздела вердиктом не являются —
                # иначе тест выше зеленел бы и без слов, которые он проверяет.
                s.reports(verify=paths_only)
                s.commit("только пути")
                self.assertIn("no coverage verdict", refused(s.run("check")),
                              "пути без вердикта приняты: слова предупреждения не нагружены")

    def test_правило_шаблона_называет_тот_же_выход_что_и_замер(self):
        """Ведущая сессия читает сообщение об объёме, агент — правило 1 своего шаблона, и
        разойтись им нельзя: правило звало просить половину через `--scope`, который диффа
        не уменьшает, — тот же дефект вторым адресом, на обоих языках."""
        for name, token in (("fixreview.md", "does not fit"),
                            ("fixreview.ru.md", "не помещается")):
            text = (SKILL / "references" / name).read_text(encoding="utf-8")
            item = next(b for b in re.split(r"\n(?=\d+\. )", text) if token in b)
            with self.subTest(файл=name):
                self.assertIn("--diff", item,
                              f"{name}: правило о неподъёмном диффе обязано называть флаг, "
                              f"который дифф действительно уменьшает")

    def test_дифф_вклеивается_один_раз_даже_если_манифест_о_нём_пишет(self):
        """Названный объём обязан совпасть с тем, что приехало.

        Дифф подставлялся отдельным проходом по СОБРАННОМУ тексту, и упоминания
        `{{DIFF}}` внутри вклеенного манифеста получали дифф тоже. Замерено на этом
        наборе: заявлено 464 КБ, приехало 1410 КБ — дифф вклеен трижды, а измерен один.
        """
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=1)
        # Манифест пишет о самой подстановке — это законная цитата, а не место для диффа.
        manifest = self.s.root / "docs/review/blocks/H1-demo.md"
        manifest.write_text(manifest.read_text(encoding="utf-8")
                            + "\n## Подстановки\n\nШаблон ревьюера правок берёт `{{DIFF}}`.\n",
                            encoding="utf-8")
        self.s.commit()
        base = self.s.git("rev-parse", "HEAD").stdout.strip()
        self.s.write("src/one.ts", "a\nпочинено\n")
        self.s.commit("починка")
        self.s.run("init")
        out = self.s.run("prompt", "H1", "--role", "fixreview", "--diff", f"{base}...HEAD")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(out.stdout.count("````diff"), 1,
                         "дифф вклеен ровно один раз — столько же, сколько измерено")
        self.assertIn("+починено", out.stdout, "и вклеен он всё-таки целиком")
        self.assertIn("берёт `{{DIFF}}`", out.stdout,
                      "цитата в манифесте остаётся цитатой, а не превращается в дифф")

    def test_подстановка_диффа_в_чужой_роли_это_отказ_а_не_текст(self):
        """Вторая сторона той же правки: `{{DIFF}}` больше не исключение из проверки
        незаполненных подстановок. Роль без диффа, назвавшая его в своём шаблоне, получает
        отказ с именем подстановки, а не строку `{{DIFF}}` в задании.
        """
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=1)
        self.s.write("docs/review/prompts/hunter.md",
                     "Ты охотник блока {{BLOCK_ID}}.\n\n{{DIFF}}\n")
        self.s.write("docs/review/prompts/fixreview.md",
                     "Ты ревьюер правок блока {{BLOCK_ID}}.\n\n{{DIFF}}\n")
        self.s.commit()
        base = self.s.git("rev-parse", "HEAD").stdout.strip()
        self.s.write("src/one.ts", "a\nпочинено\n")
        self.s.commit("починка")
        self.s.run("init")
        out = self.s.run("prompt", "H1", "--role", "hunter")
        self.assertEqual(out.returncode, 2, out.stdout)
        self.assertIn("{{DIFF}}", out.stderr, "отказ называет подстановку, оставшуюся пустой")
        # И та же подстановка в роли, у которой дифф есть, по-прежнему заполняется.
        ok = self.s.run("prompt", "H1", "--role", "fixreview", "--diff", f"{base}...HEAD")
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertIn("+починено", ok.stdout)
        self.assertNotIn("{{DIFF}}", ok.stdout.split("````diff")[0])

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
        self.assertIn("no fix reviewer report", refused(self.s.run("check")))
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

    def test_set_finding_на_нескольких_номерах_всё_или_ничего(self):
        """Инвариант: перевод нескольких находок — целиком или никак.

        Отказ на втором номере — обычное дело: опечатка в номере, `fixed` без коммита. Если
        первую к этому моменту уже записали, команда сказала «нет», а реестр говорит «да»,
        и расхождение видно только при чтении файла руками.
        """
        self._two_open()
        for why, argv in (
                ("номера нет в реестре", ("H1-001", "H1-999", "deferred", "--reason", "x")),
                ("отказ на проверке поля", ("H1-001", "H1-002", "fixed"))):
            with self.subTest(отказ=why):
                before = self._rows()
                out = self.s.run("set-finding", *argv)
                self.assertNotEqual(out.returncode, 0, out.stdout + out.stderr)
                self.assertEqual(self._rows(), before,
                                 "часть находок уже переведена, а команда отказала")
        # а та же команда без чужого номера переводит обе
        out = self.s.run("set-finding", "H1-001", "H1-002", "deferred", "--reason", "ждёт H2")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertEqual([r["status"] for r in self._rows()], ["deferred", "deferred"])

    def _two_open(self) -> None:
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

    def test_обе_языковые_таблицы_держат_одни_ключи_и_подстановки(self):
        """УЗДА КЛАССА «строка есть на одном языке и нет на другом».

        `T()` берёт ключ из таблицы ВЫБРАННОГО языка и падает `KeyError` в работе, а не
        при импорте. Удаление русского `refs_cut` оставляло весь прогон зелёным —
        измерено: ни один тест не даёт блоку больше REF_LIST_LIMIT файлов контекста, и
        ветка не исполняется никогда; так же не исполняются `vol_more`, `sum_seams`,
        `f_invariant`. Проект с русским ревью и 81 файлом контекста получал бы трейсбек
        из `prompt` — команды, которая выдаёт агенту задание.

        Подстановки сверяются заодно: перевод с другим именем поля падает тем же
        образом, только уже в `format`.
        """
        table = self._msg_tables(TOOL.read_text(encoding="utf-8"))
        self.assertEqual(sorted(table), ["en", "ru"], "языков стало больше — правило сверяет все")
        self.assertEqual(self._msg_mismatch(table), [])

    @staticmethod
    def _msg_tables(source: str) -> dict:
        """Таблицы сообщений инструмента, прочитанные из его исходника.

        Таблица читается там, где её СОБРАЛИ: объявление с типом, языки отдельными
        константами, склейка из кусков — всё это одна и та же таблица, а правило,
        знавшее одно `MSG = {...}` в теле модуля, на любой из этих форм переставало
        сверять языки и молчало об этом.
        """
        vals = _Values(source)
        for node in ast.walk(vals.tree):
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                target = node.targets[0]
            elif isinstance(node, ast.AnnAssign):
                target = node.target
            else:
                continue
            if isinstance(target, ast.Name) and target.id == "MSG":
                return vals.literal(node.value)
        raise AssertionError("в исходнике нет таблицы MSG — правило смотрит не туда")

    @staticmethod
    def _msg_mismatch(table: dict) -> list[str]:
        """Ключи, которые есть не на всех языках, и ключи с разными подстановками."""
        langs = sorted(table)
        first, *rest = langs
        out = []
        for lang in rest:
            out += [f"`{k}`: есть в {first}, нет в {lang}"
                    for k in sorted(set(table[first]) - set(table[lang]))]
            out += [f"`{k}`: есть в {lang}, нет в {first}"
                    for k in sorted(set(table[lang]) - set(table[first]))]
        for key in table[first]:
            fields = {lang: frozenset(re.findall(r"\{(\w+)", table[lang].get(key, "")))
                      for lang in langs if key in table[lang]}
            if len(set(fields.values())) > 1:
                out.append(f"`{key}`: подстановки расходятся по языкам: {dict(fields)}")
        return out

    def test_узда_видит_расхождение_таблиц_на_выдуманном_исходнике(self):
        """Обе стороны правила на таблицах, которых в инструменте нет: сверенные проходят,
        потерянный перевод и переименованная подстановка — нет."""
        same = 'MSG = {"en": {"a": "{n} files"}, "ru": {"a": "{n} файлов"}}\n'
        self.assertEqual(self._msg_mismatch(self._msg_tables(same)), [])
        gone = 'MSG = {"en": {"a": "{n} files"}, "ru": {}}\n'
        self.assertNotEqual(self._msg_mismatch(self._msg_tables(gone)), [])
        renamed = 'MSG = {"en": {"a": "{n} files"}, "ru": {"a": "{count} файлов"}}\n'
        self.assertNotEqual(self._msg_mismatch(self._msg_tables(renamed)), [])

    def test_у_каждого_шаблона_и_образца_есть_второй_язык(self):
        """Та же узда для файлов: шаблон роли или образец, переведённый наполовину,
        оставляет проект одного из языков без того, что обещает `SKILL.md`."""
        for folder in ("references", "assets"):
            names = {p.name for p in (SKILL / folder).glob("*.md")}
            for name in sorted(names):
                twin = name.replace(".ru.md", ".md") if name.endswith(".ru.md") \
                    else name[:-3] + ".ru.md"
                with self.subTest(файл=f"{folder}/{name}"):
                    self.assertIn(twin, names, f"{folder}/{name} без пары {twin}")

    def test_язык_которого_нет_не_роняет_инструмент(self):
        """`lang` пишут руками, и `ru-RU` — обычная описка. Ни один гейт `check` поле не
        проверяет, так что запасной английский — единственное, что стоит между опиской и
        трейсбеком из `prompt`."""
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"], lang="ru-RU")
        self.s.manifest(hypotheses=1)
        self.s.commit()
        self.assertEqual(self.s.run("init").returncode, 0)
        out = self.s.run("prompt", "H1", "--role", "hunter")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertNotIn("Traceback", out.stderr)
        self.assertIn("You are a hunter reviewer", out.stdout, "запасной язык — английский")

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
        subprocess.run(["git", "init", "-q", str(self.root)], check=True, env=child_env())
        for k, v in (("user.email", "t@example.com"), ("user.name", "t")):
            subprocess.run(["git", "-C", str(self.root), "config", k, v], check=True, env=child_env())
        (self.root / "app.ts").write_text("x\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.root), "add", "-A"], check=True, env=child_env())
        subprocess.run(["git", "-C", str(self.root), "commit", "-qm", "init"], check=True, env=child_env())

    def install(self, *extra: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(TOOL), "setup", *extra], cwd=self.root,
                              capture_output=True, text=True, check=False, env=child_env())

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

        run = lambda *a: subprocess.run([sys.executable, str(TOOL), *a], cwd=self.root,
                                        capture_output=True, text=True, env=child_env())
        self.assertEqual(run("init").returncode, 0)
        cov = run("coverage")
        self.assertEqual(cov.returncode, 1, "непокрытый файл обязан ронять карту")
        self.assertIn("npm run review --", cov.stdout, "советует команду проекта, а не свою")

    def test_скилл_внутри_проекта_не_роняет_покрытие(self):
        """Скилл коммитят в проект ради CI — его файлы не предмет ревью."""
        inside = self.root / ".claude" / "skills" / "finetooth"
        shutil.copytree(SKILL, inside, ignore=shutil.ignore_patterns("__pycache__"))
        subprocess.run(["git", "-C", str(self.root), "add", "-A"], check=True, env=child_env())
        subprocess.run(["git", "-C", str(self.root), "commit", "-qm", "скилл в проекте"], check=True, env=child_env())
        tool = inside / "scripts" / "review.py"
        run = lambda *a: subprocess.run([sys.executable, str(tool), *a], cwd=self.root,
                                        capture_output=True, text=True, env=child_env())
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

    def test_без_git_инструмент_отказывает_а_не_роняет_трейсбек(self):
        """Читать репозиторий инструмент умеет только через git, и сказать об этом обязан
        один раз и внятно: прежде отсутствие git приходило трейсбеком `FileNotFoundError`
        из той команды, которую пользователь набрал первой.

        Обратная сторона — весь остальной прогон: с обычным PATH инструмент работает."""
        empty = Path(tempfile.mkdtemp(prefix="finetooth-nopath-"))
        self.addCleanup(shutil.rmtree, empty, True)
        out = subprocess.run([sys.executable, str(TOOL), "status"], cwd=self.s.root,
                             capture_output=True, text=True, env=child_env(PATH=str(empty)))
        self.assertEqual(out.returncode, 2, out.stdout + out.stderr)
        self.assertIn("git does not run", out.stderr)
        self.assertIn("install it", out.stderr)
        self.assertNotIn("Traceback", out.stderr)

    def test_главная_ветка_проекта_ничего_не_решает(self):
        """Обратная сторона пришпиленного конфига git: стенд больше не берёт имя ветки у
        разработчика — и обязан работать на любом. `main` — умолчание большинства живых
        проектов, а набор целиком ходил по `master`."""
        s = Stand(branch="main")
        self.addCleanup(s.cleanup)
        s.write("src/one.ts", "a\n")
        s.blocks(paths=["src/one.ts"])
        s.manifest(hypotheses=1)
        s.reports(hunter="# охотник\n## Гипотезы\n- H1.1 — проверена: да\n"
                         "## Ограничения охвата\nнет\n", verify=FULL_VERIFY)
        s.commit()
        self.assertEqual(s.git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip(), "main")
        self.assertEqual(s.run("init").returncode, 0)
        self.assertEqual(s.run("coverage").returncode, 0)
        s.run("set-status", "H1", "verified")
        out = s.run("check")
        self.assertEqual(out.returncode, 0, out.stdout)

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

    def test_имя_файла_со_скобкой_это_имя_а_не_образец(self):
        """`app/[id]/page.tsx` — обычный маршрут Next.js, а для git-pathspec `[id]` —
        класс символов. Имя, отданное как образец, совпадает и с СОСЕДОМ: несуществующий
        `app/[i]/page.tsx` матчится на живой `app/i/page.tsx`, и «узда есть» становится
        правдой без всякой узды — ровно тот дефект, ради которого проверка и написана.

        Обе стороны: имя, которое есть, принимается; имя, которого нет, отвергается, как
        бы удачно его скобки ни совпадали с соседним файлом.
        """
        route = "app/[id]/page.tsx"
        self.s.write(route, "было\n")
        self.s.write("app/i/page.tsx", "сосед\n")
        self.s.blocks(paths=["app"])
        self.s.manifest(hypotheses=1)
        self.s.write("docs/review/reports/H1-findings.jsonl", json.dumps({
            "block": "H1", "severity": "low", "confidence": "confirmed", "status": "open",
            "file": route, "claim": "дефект на маршруте", "scenario": "x делает y"},
            ensure_ascii=False) + "\n")
        self.s.commit()
        self.s.run("init")
        self.s.run("coverage")
        self.s.run("import", "H1")

        # имя, которое есть, — принимается и там, и там
        for flag in ("--rule", "--fixed-in"):
            with self.subTest(поле=flag, имя="живое"):
                got = self.s.run("set-finding", "H1-001", "open", flag, route)
                self.assertEqual(got.returncode, 0, got.stdout + got.stderr)

        # а имени, которого нет, не помогает совпадение по классу символов
        for flag in ("--rule", "--fixed-in"):
            with self.subTest(поле=flag, имя="которого нет"):
                got = self.s.run("set-finding", "H1-001", "open", flag, "app/[i]/page.tsx")
                self.assertNotEqual(got.returncode, 0, got.stdout + got.stderr)
                self.assertIn("app/[i]/page.tsx", got.stdout + got.stderr)

        # и файл под скобками живёт в отпечатке блока: его правка роняет проверку
        self.s.reports(hunter="# охотник\n## Гипотезы\n- H1.1 — проверена: да\n"
                              "## Ограничения охвата\nнет\n", verify=FULL_VERIFY)
        self.s.commit("отчёты")
        self.s.run("coverage")
        self.s.run("set-status", "H1", "verified")
        self.s.write(route, "переписали целиком\n")
        self.s.commit("правка после просмотра")
        self.s.run("coverage")
        self.assertIn("changed after the review", refused(self.s.run("check")))

    def test_файл_с_именем_подкоманды_git_живёт_в_отпечатке_блока(self):
        """`git()` решал про `-z` по ЛЮБОМУ аргументу, данные включая: файл `grep` в корне
        (обычная обёртка-скрипт) превращал `hash-object -- grep` в `hash-object -z -- grep`,
        git отвечал 129, отпечаток файла пропадал — и правка этого файла после просмотра
        проходила мимо `check`. Решают подкоманда и опции до `--`, а не имена файлов.

        Обе стороны: правка файла `grep` роняет проверку, как и правка соседа."""
        for name in ("grep", "ls-files"):
            with self.subTest(файл=name):
                s = Stand()
                self.addCleanup(s.cleanup)
                s.write(name, "#!/bin/sh\nexec grep \"$@\"\n")
                s.write("plain.txt", "a\n")
                s.blocks(paths=[name, "plain.txt"])
                s.manifest(hypotheses=1)
                s.reports(hunter="# охотник\n## Гипотезы\n- H1.1 — проверена: да\n"
                                 "## Ограничения охвата\nнет\n", verify=FULL_VERIFY)
                s.commit()
                s.run("init")
                s.run("coverage")
                s.run("set-status", "H1", "verified")
                self.assertEqual(s.run("check").returncode, 0, s.run("check").stdout)

                s.write(name, "#!/bin/sh\nexec rg \"$@\"\n")
                s.commit("правка после просмотра")
                s.run("coverage")
                self.assertIn("changed after the review", refused(s.run("check")))

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
        self.s.run("coverage")
        self.s.run("import", "H1")
        self.s.write("src/модуль.ts", "починено\n")
        self.s.write("src/обычный файл.ts", "починено\n")
        self.s.commit("починка")
        sha = self.s.git("rev-parse", "HEAD").stdout.strip()
        for fid in ("H1-001", "H1-002"):
            self.assertEqual(self.s.run("set-finding", fid, "fixed", "--commit", sha).returncode, 0)
        self.s.run("coverage")
        self.s.run("findings")
        out = self.s.run("check")
        self.assertEqual(out.returncode, 0, out.stdout)
        self.assertNotIn("does not touch", out.stdout)

    def test_кириллический_путь_записан_в_карту_покрытия_как_есть(self):
        """Карта покрытия — договор на диске: её читают обратно и `check`, и человек.

        `ls-files` без `-z` печатает не-ASCII путь экранированным по C
        (`"src/\\320\\272\\321\\200…"`, вместе с кавычками внутри значения), и в карту
        попадал путь, которого на диске нет, — при нулевом коде возврата и без единого
        слова. Обе стороны: и кириллическое имя, и соседнее ASCII записаны так, как их
        держит индекс.
        """
        self.s.write("src/крыша.txt", "а\n")
        self.s.write("src/plain.txt", "a\n")
        self.s.blocks(paths=["src/**"])
        self.s.manifest(hypotheses=1)
        self.s.commit()
        self.s.run("init")
        self.assertEqual(self.s.run("coverage").returncode, 0)
        table = (self.s.root / "docs/review/coverage.tsv").read_text(encoding="utf-8")
        rows = dict(ln.split("\t", 1) for ln in table.strip().split("\n")[1:])
        self.assertEqual(rows.get("src/крыша.txt"), "H1", table)
        self.assertEqual(rows.get("src/plain.txt"), "H1", table)
        self.assertNotIn("\\3", table, "путь попал в карту экранированным по C")
        self.assertNotIn('"', table, "путь попал в карту в кавычках git")

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
        self.assertIn("does not touch src/модуль.ts", refused(self.s.run("check")))

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


# Аргументы, при которых команда ДОХОДИТ ДО СВОЕЙ РАБОТЫ. Одного набора на всех не бывает:
# `review set-status H1 s.md` — это `argparse`, отказавший до начала команды, и правило,
# звавшее всех одинаково, проверяло бы его отказ, а не поведение команды. Измерено дважды:
# при общем наборе `H1 s.md` до тела доходили три команды из двадцати трёх, а при наборах
# `()` и `("H1",)` — двадцать из двадцати трёх, и мимо правила проходили ровно `set-status`,
# `set-finding` и `log`, то есть три из тех, что ПИШУТ. Таблица одна на все обходы команд.
#
# Доводов, однако, мало: команда начинается и отказывается ДО своей записи, если стенду
# нечего ей дать. Измерено на стенде обхода границы записи: `set-finding H1-001 open`
# отвечал «finding H1-001 is not in the register» (код 2), `import H1` — «no findings file
# for the block», `restamp H1` — «H1 is in status todo»; argparse при этом молчал, и обход
# оставался зелёным. Стенд доводит `body_stand`, и вместе они — один договор: довод и то
# состояние, при котором этот довод доводит команду до записи.
BODY_ARGV = {
    "init": (), "version": (), "setup": (), "status": (), "next": (),
    "coverage": (), "prompt": ("H1",), "set-status": ("H1", "running"),
    "import": ("H1",), "set-finding": ("H1-001", "open"), "hypotheses": ("H1",),
    # Именно находка, а не блок: `set-status` в обходе идёт раньше `restamp`, и после него
    # блок не в том статусе, который штампуется, — блочный `restamp` отказывался бы всегда.
    "restamp": ("H1-001",), "backfill": (), "inventory": (), "sizes": (),
    "coupling": (), "order": (), "refs": (), "summary": ("--out", "s.md"),
    "roots": (), "findings": (), "check": (), "log": ("H1", "строка"),
}
# Отказ argparse — это не поведение команды: он печатается до её начала.
ARGPARSE_REFUSED = ("unrecognized arguments", "the following arguments are required",
                    "invalid choice")


def argparse_refused(stderr: str) -> str:
    """Жалоба argparse в выводе: команда до своего тела не дошла, и обход её не проверил."""
    return next((said for said in ARGPARSE_REFUSED if said in stderr), "")


def body_stand(s: Stand) -> None:
    """Доводит УЖЕ заведённый стенд (`init` сделан) до состояния, в котором `BODY_ARGV`
    доводит каждую команду до её РАБОТЫ, а не до отказа перед ней.

    Реестр с находкой `H1-001`: её вносит `import`, двигает `set-finding`, переснимает
    `restamp`. Каждой из трёх оставлена работа, которую видно в самом реестре, а не по
    времени записи: в черновике ждёт непронумерованная вторая находка (её внесёт `import`),
    у `H1-001` нет отметки о переводе (её поставит `set-finding`), а файл находки уехал
    вперёд отпечатка (его переснимет `restamp`). Иначе команда доходит до записи и пишет
    те же байты — и «реестр не изменился» означало бы то же, что отказ до записи.
    """
    draft = json.dumps({
        "block": "H1", "severity": "low", "confidence": "confirmed", "status": "open",
        "file": "src/one.ts", "claim": "тут дефект",
        "scenario": "человек делает X — получает Y"}, ensure_ascii=False) + "\n"
    s.write("docs/review/reports/H1-findings.jsonl", draft)
    s.commit("черновик находок")
    imported = s.run("import", "H1")
    assert imported.returncode == 0, imported.stderr
    # Вторая находка дописывается ПОСЛЕ ввоза: номер ей выдаст тот `import`, который
    # зовёт обход, и выданный номер — это его запись в реестр.
    numbered = (s.root / "docs/review/reports/H1-findings.jsonl").read_text(encoding="utf-8")
    s.write("docs/review/reports/H1-findings.jsonl", numbered + draft.replace(
        "тут дефект", "тут второй дефект"))
    s.write("src/one.ts", "a\nб\n")
    s.commit("вторая находка в черновике; файл находки уехал вперёд отпечатка")


class WriteBoundaryTest(unittest.TestCase):
    """УЗДА КЛАССА «инструмент пишет не там, где обещано».

    SECURITY.md называет запись вне разрешённых мест уязвимостью, и это обещание дано
    вслух — значит, его держит прогон, а не вычитка. Снимок дерева до и после: всё, что
    появилось или изменилось вне `docs/review/`, обязано быть в списке ниже, а список
    равен тому, что написано в SECURITY.md. Новая команда попадает под правило сама —
    список подкоманд берётся у самого инструмента.
    """

    # Единственное разрешённое исключение: итог задуман пережить снос каталога ревью,
    # поэтому пишется вне него — по умолчанию сюда, а по `--out` туда, куда скажут.
    ALLOWED_OUTSIDE = {"docs/review-summary.md"}

    def setUp(self) -> None:
        self.s = Stand()
        self.addCleanup(self.s.cleanup)
        self.s.write("src/one.ts", "a\n")
        self.s.write(".gitignore", "__pycache__/\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=1)
        self.s.commit()
        self.s.run("init")
        body_stand(self.s)

    def _snapshot(self) -> dict[str, str]:
        """Всё дерево проекта, кроме `.git` и самого каталога ревью."""
        out = {}
        for p in sorted(self.s.root.rglob("*")):
            rel = p.relative_to(self.s.root).as_posix()
            if rel.startswith((".git/", "docs/review/")) or rel in (".git", "docs/review"):
                continue
            if p.is_file():
                out[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
        return out

    # `summary` зовётся без `--out`: путь по умолчанию — то самое разрешённое исключение,
    # которое проверяет это правило, а `--out` — просьба человека, и её держит отдельный
    # тест ниже.
    ARGV = dict(BODY_ARGV, summary=())

    def test_ни_одна_команда_не_пишет_вне_каталога_ревью(self):
        """Каждая команда зовётся так, что ДЕЛАЕТ СВОЮ РАБОТУ.

        Пока обход звал всех через `()` и `("H1",)`, три команды — `set-status`,
        `set-finding` и `log` — отвергал argparse раньше их кода, и под правилом о границе
        записи они не были вовсе: ровно три из тех, что пишут. Отказ argparse поэтому не
        засчитывается как проход — иначе обход перечисляет команды, не запуская их.

        Одних доводов мало. С ними, но на пустом стенде, `import`, `set-finding` и
        `restamp` отказывались раньше своей записи (код 2, argparse молчит) — снова три
        пишущие команды мимо правила: направь запись реестра в корень репозитория, и обход
        оставался зелёным. Отказ команды поэтому тоже не засчитывается как проход: код 2 —
        это «до записи не дошло», и стенд надо дописать (`body_stand`), а не смириться.
        Код 1 — законный приговор ворот (`check`, `coverage` на красном состоянии), он
        работу сделал.
        """
        helped = self.s.run("--help").stdout
        names = re.search(r"\{([a-z0-9,\-]{20,})\}", helped.replace("\n", ""))
        self.assertTrue(names, helped)
        commands = names.group(1).split(",")
        self.assertIn("summary", commands)
        self.assertEqual(sorted(set(self.ARGV) - set(commands)), [],
                         "в таблице есть команда, которой у инструмента больше нет")
        before = self._snapshot()
        for cmd in commands:
            with self.subTest(cmd=cmd):
                self.assertIn(cmd, self.ARGV,
                              "новая команда: впишите в BODY_ARGV аргументы, при которых "
                              "она доходит до своего тела, — иначе правило проверяет "
                              "отказ argparse, а не запись команды")
            out = self.s.run(cmd, *self.ARGV.get(cmd, ()))
            with self.subTest(cmd=cmd, args=self.ARGV.get(cmd, ())):
                self.assertFalse(argparse_refused(out.stderr),
                                 f"{cmd}: команда не начиналась — поправьте BODY_ARGV: "
                                 f"{out.stderr[-300:]}")
                self.assertNotEqual(
                    out.returncode, 2,
                    f"{cmd}: отказ раньше работы команды — до своей записи она не дошла, и "
                    f"обход её не проверил. Допишите стенд (`body_stand`) или довод в "
                    f"BODY_ARGV: {out.stderr[-300:]}")
        after = self._snapshot()
        appeared = {rel for rel in after if rel not in before}
        changed = {rel for rel in before if after.get(rel, before[rel]) != before[rel]}
        self.assertEqual(appeared - self.ALLOWED_OUTSIDE, set(),
                         "файлы появились вне docs/review/ — SECURITY.md этого не обещает")
        self.assertEqual(changed, set(),
                         "файлы изменены вне docs/review/ — SECURITY.md этого не обещает")

    # Команды, которые ПИШУТ В РЕЕСТР: ровно те три, что обход перечислял, не запуская.
    REGISTER_WRITERS = ("import", "set-finding", "restamp")

    def test_обход_доводит_до_записи_каждую_пишущую_в_реестр_команду(self):
        """Что именно проверяет обход границы записи: не «команда началась», а «команда
        записала». Со стендом без реестра `import`, `set-finding` и `restamp` отказывались
        раньше своей записи, и направленная в корень репозитория запись реестра оставляла
        обход зелёным — три пишущие команды из двадцати трёх мимо обещания SECURITY.md."""
        register = self.s.root / "docs/review/findings.jsonl"
        for cmd in self.REGISTER_WRITERS:
            before = register.read_text(encoding="utf-8")
            out = self.s.run(cmd, *self.ARGV[cmd])
            with self.subTest(cmd=cmd):
                self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
                self.assertNotEqual(
                    register.read_text(encoding="utf-8"), before,
                    f"{cmd} {self.ARGV[cmd]}: реестр не изменился — до своей записи команда "
                    f"не дошла, и обход границы записи её не проверил")

    def test_красный_приговор_ворот_за_несделанную_работу_не_считается(self):
        """Обратная сторона сужения: обход требует не нуля, а того, что команда дошла до
        работы. `check` и `coverage` на красном состоянии выходят с единицей — это их
        приговор, а не отказ до работы; потребуй обход нуля, он краснел бы на собственном
        стенде, и держать границу записи стало бы нечем."""
        self.s.write("docs/review/reports/H1-demo.hunter.md", "")
        for cmd in ("check", "coverage"):
            out = self.s.run(cmd)
            with self.subTest(cmd=cmd):
                self.assertEqual(out.returncode, 1, out.stdout + out.stderr)
                self.assertNotEqual(out.returncode, 2)
                self.assertFalse(argparse_refused(out.stderr))

    def test_итог_пишется_туда_куда_сказали_и_только_туда(self):
        """Обратная сторона: разрешённое исключение обязано работать — и по умолчанию,
        и по `--out`, в том числе за пределы репозитория."""
        before = self._snapshot()
        self.assertEqual(self.s.run("summary").returncode, 0)
        self.assertTrue((self.s.root / "docs/review-summary.md").exists())
        outside = Path(tempfile.mkdtemp(prefix="finetooth-out-"))
        self.addCleanup(shutil.rmtree, outside, True)
        target = outside / "итог.md"
        out = self.s.run("summary", "--out", str(target))
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertTrue(target.exists())
        appeared = {rel for rel in self._snapshot() if rel not in before}
        self.assertEqual(appeared, {"docs/review-summary.md"})

    def test_обещание_безопасности_называет_то_же_исключение(self):
        """Правило и текст обещания не должны разъезжаться: то, что тест разрешает
        инструменту, обязано быть названо в SECURITY.md."""
        promise = (KIT / "SECURITY.md").read_text(encoding="utf-8")
        self.assertIn("docs/review/", promise)
        for rel in self.ALLOWED_OUTSIDE:
            self.assertIn(rel, promise, f"SECURITY.md не называет {rel}")
        # Скрипт-запускатель пишет во временный каталог и отправляет промпт по сети —
        # обещание обязано говорить и об этом, иначе оно лжёт о наборе целиком.
        runner = (SKILL / "assets" / "run-role.sh").read_text(encoding="utf-8")
        self.assertIn("finetooth-runs", runner)
        self.assertIn("finetooth-runs", promise)
        self.assertIn("claude -p", promise)


class HandWrittenInputTest(unittest.TestCase):
    """Всё, что человек правит руками, обязано получать отказ, а не трейсбек:
    определение блоков, итоговый файл, текст манифеста."""

    def setUp(self) -> None:
        self.s = Stand()
        self.addCleanup(self.s.cleanup)

    def _stand(self) -> None:
        # Каждый вызов — свежий стенд: порча прошлой итерации не должна доставаться
        # следующей, а пустой коммит стенд (честно) считает ошибкой.
        self.s = Stand()
        self.addCleanup(self.s.cleanup)
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=1)
        self.s.commit()
        self.s.run("init")
        # Стенд тот же, что у обхода границы записи: таблица доводов и состояние, при
        # котором эти доводы доводят команду до работы, — один договор на оба обхода.
        body_stand(self.s)

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

    # Аргументы, при которых команда доходит до своего тела, — общая таблица `BODY_ARGV`:
    # обходы команд обязаны звать их одинаково, иначе один из них снова проверит отказ
    # argparse вместо самой команды.
    ARGV = BODY_ARGV

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

        Каждая команда зовётся со СВОИМИ аргументами из `ARGV`, при которых она доходит до
        тела: пока звали всех с общим `H1 s.md`, `init` до своего кода не доходил —
        argparse отвергал позиционные доводы раньше, — и трейсбек `KeyError: 'review_id'`
        проходил мимо узды. Отказ argparse поэтому не засчитывается как проход.
        """
        self._stand()
        commands = self._subcommands()
        self.assertEqual(sorted(set(self.ARGV) - set(commands)), [],
                         "в таблице есть команда, которой у инструмента больше нет")
        for cmd in commands:
            with self.subTest(cmd=cmd):
                self.assertIn(cmd, self.ARGV,
                              "новая команда: впишите сюда аргументы, при которых она "
                              "доходит до своего тела, — иначе правило проверяет отказ "
                              "argparse, а не её саму")
        for name, how in self.DAMAGE.items():
            with self.subTest(порча=name):
                self._stand()
                self._damage(how)
                for cmd in commands:
                    args = self.ARGV.get(cmd, ())
                    out = self.s.run(cmd, *args)
                    with self.subTest(cmd=cmd, args=args):
                        self.assertNotIn("Traceback", out.stderr,
                                         f"{name} / {cmd} {args}: {out.stderr[-400:]}")
                        self.assertFalse(argparse_refused(out.stderr),
                                         f"{name} / {cmd}: команда не начиналась — "
                                         f"поправьте BODY_ARGV")

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

    def test_restamp_на_пропавшем_файле_отказ_а_не_отпечаток_пустоты(self):
        """Файл под находкой исчез — «пересняли отпечаток» было бы неправдой: находку в
        таком случае двигают (`set-finding`), и отказ обязан это сказать."""
        self.s.write("docs/review/reports/H1-findings.jsonl", json.dumps(
            {"block": "H1", "severity": "low", "confidence": "confirmed", "status": "open",
             "file": "src/one.ts", "claim": "дефект", "scenario": "с"}, ensure_ascii=False) + "\n")
        self.s.commit()
        self.s.run("import", "H1")
        self.s.git("rm", "-q", "src/one.ts", check=True)
        self.s.commit("файл унесли")
        before = (self.s.root / "docs/review/findings.jsonl").read_text(encoding="utf-8")
        out = self.s.run("restamp", "H1-001")
        self.assertEqual(out.returncode, 2, out.stdout + out.stderr)
        self.assertNotIn("Traceback", out.stderr)
        self.assertIn("set-finding", out.stderr, "отказ обязан говорить, что делать")
        self.assertEqual((self.s.root / "docs/review/findings.jsonl").read_text(encoding="utf-8"),
                         before, "реестр остался прежним")

    def test_next_называет_следующий_незакрытый_блок(self):
        """`next` — то, чем следующая сессия узнаёт, с чего начать; своего теста у него
        не было вовсе."""
        out = self.s.run("next")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(out.stdout.strip(), "H1")
        self.s.run("set-status", "H1", "closed")
        out = self.s.run("next")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(out.stdout.strip(), "", "закрытых блоков `next` не называет")

    def test_повторный_backfill_на_проставленном_состоянии_ничего_не_пишет(self):
        """`backfill` перечислен в инвариантe об идемпотентности рядом с `init` и
        `restamp`, а теста у него не было: каждый повторный прогон переписывал бы
        state.json и дописывал строку в дневник, и ворота CI обычного вида —
        «перегенерируй и потребуй чистое дерево» — краснели бы на верном состоянии."""
        self.s.write("docs/review/reports/H1-findings.jsonl", json.dumps(
            {"block": "H1", "severity": "low", "confidence": "confirmed", "status": "open",
             "file": "src/one.ts", "claim": "дефект", "scenario": "с"}, ensure_ascii=False) + "\n")
        self.s.commit()
        self.s.run("import", "H1")
        self.s.run("set-status", "H1", "verified")
        # состояние, оставленное версией набора без отпечатков
        st_path = self.s.root / "docs/review/state.json"
        st = json.loads(st_path.read_text(encoding="utf-8"))
        st["blocks"]["H1"].pop("reviewed_sha")
        st_path.write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")

        first = self.s.run("backfill")
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertIn("H1", first.stdout, "проставить было что")
        before = self._state_text()
        journal = (self.s.root / "docs/review/journal.md").read_text(encoding="utf-8")
        time.sleep(1.1)                      # чтобы отличие было видно, если оно есть
        again = self.s.run("backfill")
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertIn("nothing to stamp", again.stdout)
        self.assertEqual(self._state_text(), before, "повторный прогон переписал состояние")
        self.assertEqual((self.s.root / "docs/review/journal.md").read_text(encoding="utf-8"),
                         journal, "повторный прогон дописал строку в дневник")

    def test_импорт_держит_те_же_потолки_что_и_проверка(self):
        """`import` пропускал заголовок длиннее потолка, а `check` его потом отвергал: строка
        оказывалась в реестре, и каждые следующие ворота краснели на записи, которую
        инструментом уже не поправить. Обе стороны: длинный отвергается, обычный проходит."""
        src = self.s.root / "docs/review/reports/H1-findings.jsonl"
        row = {"block": "H1", "severity": "low", "confidence": "confirmed", "status": "open",
               "file": "src/one.ts", "claim": "и" * 300, "scenario": "с"}
        src.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
        self.s.commit()
        out = self.s.run("import", "H1")
        self.assertEqual(out.returncode, 2, out.stdout + out.stderr)
        self.assertIn("claim is 300 characters", out.stdout + out.stderr)
        reg = self.s.root / "docs/review/findings.jsonl"
        self.assertNotIn("и" * 300, reg.read_text(encoding="utf-8") if reg.exists() else "",
                         "отвергнутая строка не должна попасть в реестр")

        row["claim"] = "и" * 200
        src.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
        out = self.s.run("import", "H1")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertEqual(self.s.run("check").returncode, 0, "и проверка его принимает")

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
        subprocess.run(["git", "init", "-q", "--bare", str(server)], check=True, env=child_env())
        self.addCleanup(shutil.rmtree, server, True)
        self.s.git("remote", "add", remote_name, str(server))
        self.s.git("push", "-q", remote_name, "HEAD:refs/heads/master")
        self.s.write("src/server.ts", "серверная правка\n")
        self.s.git("add", "src/server.ts")
        future = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=14)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
        env = child_env(GIT_AUTHOR_DATE=future, GIT_COMMITTER_DATE=future)
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
        subprocess.run(["git", "init", "-q", "--bare", str(server)], check=True, env=child_env())
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


STREAM_REPLY = "блок пройден"
STREAM_TURNS = 42
STREAM_COST = 3.41


def stream_text(with_result: bool = True, subtype: str = "success") -> str:
    """Поток `claude -p --output-format stream-json --verbose` целого прогона.

    ОДНО место на весь набор: и заглушки `axes.py`, и заглушка самого `claude` для
    `run-role.sh` собираются отсюда. Пока заглушка клиента не отдавала события `result`,
    все шесть тестов `run-role.sh` шли по ветке «события нет», и тест, названный
    «успешный прогон записан обычной строкой», принимал за неё строку
    `NO RESULT EVENT … spend: ? min, ? turns … cost estimate unknown`: вида, который
    оператор читает как «блок пройден», не производил ни один тест.
    """
    ev = lambda o: json.dumps(o, ensure_ascii=False)
    usage = {"input_tokens": 1, "cache_creation_input_tokens": 100,
             "cache_read_input_tokens": 900, "output_tokens": 5}
    lines = [ev({"type": "assistant", "message": {
        "id": "m1", "model": "test", "usage": usage,
        "content": [{"type": "tool_use", "id": "t1", "name": "Read",
                     "input": {"file_path": "/x/a.ts"}}]}})]
    if with_result:
        lines.append(ev({"type": "result", "subtype": subtype, "num_turns": STREAM_TURNS,
                         "duration_ms": 600000, "total_cost_usd": STREAM_COST,
                         "usage": {"output_tokens": 21000}, "result": STREAM_REPLY}))
    return "\n".join(lines) + "\n"


class SpendTest(unittest.TestCase):
    """Замер расхода — то, из чего выведены потолки ходов. Обрезанный прогон не имеет
    права выглядеть в дневнике как обычный завершённый."""

    def setUp(self) -> None:
        self.s = Stand()
        self.addCleanup(self.s.cleanup)

    def _stream(self, with_result: bool = True, truncated: bool = False,
                subtype: str = "success") -> Path:
        text = stream_text(with_result=with_result, subtype=subtype)
        if truncated:
            text = text[:-20]
        p = self.s.root / "stream.jsonl"
        p.write_text(text, encoding="utf-8")
        return p

    def _axes(self, path: Path, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(SKILL / "scripts" / "axes.py"),
                               str(path), *args], capture_output=True, text=True, env=child_env())

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

    def _run_role(self, exit_code: int, truncated: bool = False, log_fails: bool = False,
                  with_result: bool = True) -> tuple[subprocess.CompletedProcess, str]:
        """run-role.sh с заглушкой вместо `claude`: настоящий клиент здесь не нужен,
        нужен его код возврата и поток, который он оставляет.

        Поток — тот же, что у целого прогона (`stream_text`): заглушка, которая мягче
        настоящего клиента, красит зелёным то, что в жизни красное. `truncated` — убитый
        прогон обрывает последнюю строку на середине; `with_result=False` — поток без
        события `result` вовсе; `log_fails` — отказывает шаг отчёта.
        """
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=1)
        self.s.commit()
        self.s.run("init")
        stub_dir = self.s.root / "stub"
        stub_dir.mkdir()
        # Поток лежит рядом с заглушкой файлом: так в нём переживают без потерь и
        # кавычки, и кириллица ответа агента.
        text = stream_text(with_result=with_result)
        if truncated:
            text = text[:-20]
        (stub_dir / "stream.jsonl").write_text(text, encoding="utf-8")
        stub = stub_dir / "claude"
        stub.write_text("#!/usr/bin/env bash\n"
                        f'cat "{stub_dir}/stream.jsonl"\n'
                        f"exit {exit_code}\n", encoding="utf-8")
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
        env = child_env(PATH=f"{stub_dir}:{os.environ['PATH']}",
                        REVIEW=review, TMPDIR=str(self.s.root / "runs"))
        (self.s.root / "runs").mkdir()
        # Через `shell_gate`: отказы этого скрипта — предмет мутационной узды ворот на
        # оболочке, а она подменяет скрипт копией через окружение.
        out = subprocess.run(
            ["bash", str(shell_gate("skills/finetooth/assets/run-role.sh")), "H1", "hunter"],
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
        self.assertIn(STREAM_REPLY, out.stdout, "ответ агента печатается и при потерянной записи")

    def test_ответ_агента_печатается_из_целого_потока(self):
        """Прямая сторона: на целом потоке ответ агента доходит до оператора — через сам
        `run-role.sh`, а не через `axes.py` на файле, написанном руками."""
        out, _ = self._run_role(exit_code=0)
        self.assertIn("--- agent reply ---", out.stdout, out.stdout)
        self.assertIn(STREAM_REPLY, out.stdout, out.stdout)
        self.assertNotIn("no agent reply in the stream", out.stdout)

    def test_поток_без_события_result_виден_в_дневнике_как_несостоявшийся_замер(self):
        """Обратная сторона: клиент, ушедший без события `result`, обязан оставить в
        дневнике слова о том, что замера нет, — даже когда код возврата нулевой."""
        out, journal = self._run_role(exit_code=0, with_result=False)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("NO RESULT EVENT", journal)
        self.assertIn("? turns", journal)
        self.assertIn("no agent reply in the stream", out.stdout)

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
        env = child_env(REVIEW=f"{sys.executable} {TOOL}", TMPDIR=str(runs))
        out = subprocess.run(["bash", str(SKILL / "assets" / "run-role.sh"), "НЕТБЛОКА", "hunter"],
                             cwd=self.s.root, capture_output=True, text=True, env=env)
        self.assertEqual(out.returncode, 2, out.stdout + out.stderr)
        left = list((runs / "finetooth-runs").glob("*.prompt.md"))
        self.assertEqual(left, [], "нулевой файл промпта остался в TMPDIR")

    def test_успешный_прогон_записан_обычной_строкой(self):
        """Строка целого прогона — та, которую оператор читает как «блок пройден»: с
        ходами, временем и ценой. Пока заглушка клиента не отдавала события `result`, под
        этим именем проверялась строка `NO RESULT EVENT … ? turns … cost unknown`."""
        out, journal = self._run_role(exit_code=0)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("hunter — ", journal)
        self.assertNotIn("RUN FAILED", journal)
        self.assertNotIn("NO RESULT EVENT", journal)
        self.assertNotIn("RUN CUT OFF", journal)
        self.assertIn(f"{STREAM_TURNS} turns", journal)
        self.assertIn(f"cost estimate ${STREAM_COST:.2f}", journal)
        self.assertNotIn("? turns", journal)


class GuardGrepTest(unittest.TestCase):
    """Узда проекта-пользователя: один маркер — одно послабление, а несуществующий путь
    — отказ, а не тишина."""

    SCRIPT = shell_gate("skills/finetooth/assets/guard-grep.sh")

    def setUp(self) -> None:
        self.dir = Path(tempfile.mkdtemp(prefix="finetooth-guard-"))
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.pkg = self.dir / "internal" / "billing"
        self.pkg.mkdir(parents=True)

    def _bare(self, *args: str) -> subprocess.CompletedProcess:
        """Скрипт без ключей от себя: отказы про сами ключи иначе не проверить."""
        return subprocess.run(["bash", str(self.SCRIPT), *args],
                              capture_output=True, text=True, env=child_env())

    def _run(self, *paths: str, extra: tuple[str, ...] = ()) -> subprocess.CompletedProcess:
        return self._bare("--pattern", r"\.Publish\(", "--marker", "outbox-allowed:",
                          *extra, "--", *paths)

    def test_исключение_снимает_попадание_а_остальные_оставляет(self):
        """`--exclude` — второй способ не быть нарушением: вызов, который И ТАК идёт
        через разрешённую обёртку, нарушением не считается. Обе стороны: исключённый
        вызов не назван, все прочие названы — иначе ключ, потерявший своё значение, тихо
        делает ворота зелёными на всём подряд."""
        (self.pkg / "a.go").write_text(
            "package billing\noutbox.Publish(1)\nbroker.Publish(2)\n", encoding="utf-8")
        strict = self._run(str(self.pkg))
        self.assertEqual(strict.returncode, 1, strict.stdout)
        self.assertIn("a.go:2", strict.stdout, "без исключения назван и обёрнутый вызов")
        self.assertIn("a.go:3", strict.stdout)

        out = self._run(str(self.pkg), extra=("--exclude", r"outbox\.Publish\("))
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertNotIn("a.go:2", out.stdout, "исключённый вызов назван нарушением")
        self.assertIn("a.go:3", out.stdout, "исключение освободило чужой вызов")

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

    # Ворота зовут из Makefile, и всякая опечатка в вызове — это скрипт, который ничего
    # не просмотрел. Каждый его отказ обязан отличаться от чистого дерева кодом возврата;
    # держит это `ShellGateMutationTest`, а без своего теста отказ не держало ничто.
    def test_неизвестный_ключ_это_отказ_а_не_тишина(self):
        (self.pkg / "a.go").write_text("package billing\nbroker.Publish(1)\n", encoding="utf-8")
        out = self._run(str(self.pkg), extra=("--windwo", "3"))
        self.assertEqual(out.returncode, 2, out.stdout + out.stderr)
        self.assertIn("unknown argument", out.stderr)

    def test_без_образца_и_маркера_это_отказ_а_не_тишина(self):
        out = self._bare("--", str(self.pkg))
        self.assertEqual(out.returncode, 2, out.stdout + out.stderr)
        self.assertIn("--pattern", out.stderr)
        self.assertIn("--marker", out.stderr)

    def test_без_путей_это_отказ_а_не_тишина(self):
        out = self._bare("--pattern", r"\.Publish\(", "--marker", "outbox-allowed:", "--")
        self.assertEqual(out.returncode, 2, out.stdout + out.stderr)
        self.assertIn("no paths", out.stderr)


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
        self.assertIn("no manifest", refused(out), out.stdout)

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
        self.assertIn("duplicate id", refused(out), out.stdout)

    def test_пустое_обязательное_поле_находки(self):
        self._green()
        self._register(claim="")
        out = self.s.run("check")
        self.assertEqual(out.returncode, 1)
        self.assertIn("field claim is empty", refused(out), out.stdout)

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
        self.assertIn("severity=катастрофа is not in the vocabulary", refused(out), out.stdout)

    def test_confidence_вне_словаря(self):
        self._green()
        self._register(confidence="наверное")
        out = self.s.run("check")
        self.assertEqual(out.returncode, 1)
        self.assertIn("confidence=наверное is not in the vocabulary", refused(out), out.stdout)

    def test_статус_находки_вне_словаря(self):
        self._green()
        self._register(status="почти")
        out = self.s.run("check")
        self.assertEqual(out.returncode, 1)
        self.assertIn("status=почти is not in the vocabulary", refused(out), out.stdout)

    def test_внешний_коммит_починки_написан_не_по_форме(self):
        self._green()
        self._register(status="fixed", fix_commit="соседний-репозиторий:")
        out = self.s.run("check")
        self.assertEqual(out.returncode, 1)
        self.assertIn("an external fix is written as", refused(out), out.stdout)

    def test_починено_без_коммита(self):
        self._green()
        self._register(status="fixed", fix_commit=None)
        out = self.s.run("check")
        self.assertEqual(out.returncode, 1)
        self.assertIn("marked fixed, but no fix commit", refused(out), out.stdout)

    def test_дубль_без_указания_чего(self):
        self._green()
        self._register(status="duplicate", dup_of=None)
        out = self.s.run("check")
        self.assertEqual(out.returncode, 1)
        self.assertIn("marked duplicate, but not of what exactly", refused(out), out.stdout)

    def test_отвергнутая_проверяющим_но_открытая(self):
        self._green()
        self._register(confidence="rejected", status="open")
        out = self.s.run("check")
        self.assertEqual(out.returncode, 1)
        self.assertIn("rejected by the verifier, but still open", refused(out), out.stdout)

    def test_заголовок_находки_длиннее_потолка(self):
        self._green()
        self._register(claim="и" * 260)
        out = self.s.run("check")
        self.assertEqual(out.returncode, 1)
        self.assertIn("against a limit of 220", refused(out), out.stdout)

    def test_сценарий_длиннее_потолка(self):
        self._green()
        self._register(scenario="и" * 800)
        out = self.s.run("check")
        self.assertEqual(out.returncode, 1)
        self.assertIn("against a limit of 700", refused(out), out.stdout)

    def test_номер_строки_строкой_а_не_числом(self):
        """Черновик находок пишется руками, и `"line": "9999"` — обычная описка. Ворота
        о несуществующей строке молча пропускали её мимо, а findings.md рисовал её как
        настоящее место."""
        self._green()
        self._register(line="9999")
        out = self.s.run("check")
        self.assertEqual(out.returncode, 1)
        self.assertIn("is not a number", refused(out), out.stdout)

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
        self.assertIn("findings.md diverged", refused(out), out.stdout)

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


# Контейнер отказов инструмента и два его глагола: другого способа завести ворота в `check`
# нет, а у отказа есть ключ, и пишет его то место, где ворота стоят.
GATE_VERBS = ("refuse", "warn")


class GateWithoutKey(Exception):
    """Отказ, добавленный без ключа-литерала: такие ворота реестру нечем назвать."""


# Ворота: где они написаны (первая и последняя строка ЦЕЛОГО оператора — мутация вырезает
# его целиком), каким глаголом отказ добавлен и под каким ключом.
Gate = collections.namedtuple("Gate", "lineno end_lineno verb key")


def _check_gates(source: str | None = None) -> list[Gate]:
    """Все ворота инструмента — по вызовам контейнера отказов, ГДЕ БЫ ОНИ НИ СТОЯЛИ.

    Три круга подряд реестр узнавал ворота по ВИДУ строки: сначала `problems.append(...)`,
    потом ещё `+=`, `extend` и присваивание, — и каждый круг находилась следующая форма.
    Ворота в вынесенном помощнике, у которого список отказов зовут `refusals`, не давали
    ключа, не требовали ни записи, ни теста и снимались потом при зелёном прогоне.
    Перечислять формы записи бесполезно: их всегда на одну больше, чем вообразил автор.

    Поэтому у инструмента один контейнер отказов, а у отказа — ключ, который пишут на
    месте: реестр читает то, как ворота ЗОВУТ САМИ СЕБЯ. Имя переменной, вынесенный
    помощник, глубина вложенности не значат больше ничего — вопрос только в том, добавлен
    отказ или нет. Ключ обязан быть литералом: собранный по дороге ключ реестру нечем
    назвать, и это отказ, а не молчание — см. GateWithoutKey.
    """
    if source is None:
        source = TOOL.read_text(encoding="utf-8")
    vals = _Values(source)
    out = []
    for node in ast.walk(vals.tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr in GATE_VERBS):
            continue
        key = node.args[0] if node.args else None
        if not (isinstance(key, ast.Constant) and isinstance(key.value, str)
                and key.value.strip()):
            where = getattr(vals.scope_of(node), "name", "модуль")
            raise GateWithoutKey(
                f"{where}, строка {node.lineno}: отказ добавлен без ключа-литерала "
                f"(`{ast.unparse(node)[:60]}`) — реестру нечем назвать эти ворота, и они "
                f"прошли бы без теста. Первым аргументом `refuse`/`warn` пишут ключ "
                f"строкой, и он же стоит в GATES.")
        stmt = node
        while not isinstance(stmt, ast.stmt) and stmt in vals.parent:
            stmt = vals.parent[stmt]
        out.append(Gate(stmt.lineno, stmt.end_lineno, node.func.attr, key.value))
    return sorted(out)


def _own_verdict(source: str | None = None) -> list[str]:
    """Места, где `check` выносит приговор мимо контейнера отказов.

    Ворота, которые печатают отказ сами и сами возвращают код, не видны ни одному реестру:
    ни записи, ни теста, ни мутации — и снять их можно при зелёном прогоне. Поэтому у
    команды ровно один выход, и он приговор контейнера; `die` тоже не годится — это код 2,
    «ошибка вызова», а красное состояние это код 1.
    """
    if source is None:
        source = TOOL.read_text(encoding="utf-8")
    vals = _Values(source)
    fn = next((n for n in ast.walk(vals.tree)
               if isinstance(n, ast.FunctionDef) and n.name == "cmd_check"), None)
    if fn is None:
        return ["в исходнике нет cmd_check — правило смотрит не туда"]
    out = []
    for node in ast.walk(fn):
        if vals.scope_of(node) is not fn:
            continue                       # вложенная функция отвечает за свой выход сама
        if isinstance(node, ast.Return):
            text = ast.unparse(node.value) if node.value is not None else ""
            if not re.fullmatch(r"\w+\.report\(\)", text):
                out.append(f"выход `return {text}` мимо контейнера")
        if isinstance(node, ast.Call):
            called = (node.func.attr if isinstance(node.func, ast.Attribute)
                      else getattr(node.func, "id", ""))
            if called in ("exit", "die"):
                out.append(f"выход `{ast.unparse(node)[:40]}` мимо контейнера")
    return sorted(out)


class GateRegistryTest(unittest.TestCase):
    """УЗДА КЛАССА «ворота, которые не могут покраснеть».

    Мутацией было измерено, что два десятка ворот `check` можно снять, и весь прогон
    останется зелёным. Список починенных мест такое не держит: следующие ворота напишут
    без теста так же. Здесь ворота перечислены поимённо вместе с тестом, который краснеет
    при их снятии, и правило сверяет список с исходником: новые ворота без записи роняют
    прогон, запись с несуществующим именем теста — тоже. Исходник берётся весь: ворота
    ищутся там, где наполняют список отказов, а не в одной названной команде.
    """

    # ворота инструмента → тест, который краснеет, если их заглушить
    GATES = [
        ("state/no-record",                     "test_блок_из_определения_без_записи_в_состоянии"),
        ("state/block-not-in-definition",       "test_блок_в_состоянии_которого_нет_в_определении"),
        ("state/status-unknown",                "test_статус_блока_вписанный_руками_роняет_проверку"),
        ("blocks/phase-order",                  "test_фазы_в_массиве_не_убывают"),
        ("state/blocked-without-note",          "test_заблокированный_блок_не_значит_закончено"),
        ("manifest/missing",                    "test_манифест_пропал_а_блок_в_работе"),
        ("manifest/too-short",                  "test_куцый_манифест_роняет_проверку"),
        ("report/verify-missing",               "test_пройденный_блок_без_отчёта_проверяющего"),
        ("report/verify-weak",                  "test_пустой_отчёт_проверяющего_не_проводит_блок"),
        ("report/declared-missing",             "test_объявленный_отчёт_которого_нет_на_диске"),
        ("report/hunter-missing",               "test_статус_дальше_running_без_отчёта_охотника"),
        ("state/running-without-timestamp",     "test_running_без_отметки_времени"),
        ("state/timestamp-unparsable",          "test_неразбираемая_отметка_времени"),
        ("state/running-too-long",              "test_running_дольше_суток"),
        ("finding/duplicate-id",                "test_две_записи_с_одним_идентификатором"),
        ("finding/empty-field",                 "test_пустое_обязательное_поле_находки"),
        ("finding/unknown-block",               "test_находка_ссылается_на_несуществующий_блок"),
        ("finding/severity-unknown",            "test_severity_вне_словаря"),
        ("finding/confidence-unknown",          "test_confidence_вне_словаря"),
        ("finding/status-unknown",              "test_статус_находки_вне_словаря"),
        ("finding/file-missing",                "test_починенная_находка_на_удалённом_файле_не_роняет_проверку"),
        ("finding/deferred-without-reason",     "test_отложенная_находка_требует_причину"),
        ("finding/external-fix-malformed",      "test_внешний_коммит_починки_написан_не_по_форме"),
        ("finding/commit-missing",              "test_починка_в_соседнем_репозитории_помечается_явно"),
        ("finding/commit-does-not-touch",       "test_коммит_починки_обязан_касаться_файла_находки"),
        ("finding/fixed-without-commit",        "test_починено_без_коммита"),
        ("finding/duplicate-without-target",    "test_дубль_без_указания_чего"),
        ("finding/duplicate-target-unusable",   "test_дубль_указывает_на_живую_находку"),
        ("finding/rejected-but-open",           "test_отвергнутая_проверяющим_но_открытая"),
        ("finding/rejected-without-confidence", "test_отказ_меняет_и_уверенность"),
        ("finding/no-code-fingerprint",         "test_старые_записи_без_отпечатков_ловятся_и_дописываются"),
        ("finding/code-changed",                "test_изменившийся_код_под_открытой_находкой_роняет_проверку"),
        ("finding/line-not-a-number",           "test_номер_строки_строкой_а_не_числом"),
        ("finding/line-past-end",               "test_несуществующая_строка_в_находке_роняет_проверку"),
        ("finding/rejected-without-reason",     "test_отвергнутая_находка_без_причины_роняет_проверку"),
        ("finding/claim-too-long",              "test_заголовок_находки_длиннее_потолка"),
        ("finding/scenario-too-long",           "test_сценарий_длиннее_потолка"),
        ("findings-md/stale",                   "test_findings_md_разъехался_с_реестром"),
        ("paths/only-untracked",                "test_шаблон_по_нетрекнутым_файлам_зовёт_git_add"),
        ("paths/matches-nothing",               "test_шаблон_который_ничего_не_нашёл_роняет_проверку"),
        ("coverage/unowned-files",              "test_ничей_файл_роняет_не_только_карту_но_и_проверку"),
        ("coverage/stale",                      "test_устаревшая_карта_покрытия_роняет_проверку"),
        ("manifest/no-hypotheses",              "test_манифест_без_гипотез_роняет_проверку"),
        ("report/verdicts-conflict",            "test_противоречивые_вердикты_в_одном_отчёте_роняют_проверку"),
        ("report/hypothesis-without-verdict",   "test_гипотеза_без_вердикта_роняет_проверку"),
        ("state/no-reviewed-fingerprint",       "test_старые_записи_без_отпечатков_ловятся_и_дописываются"),
        ("state/files-changed",                 "test_блок_просмотренный_на_другой_версии_файлов_роняет_проверку"),
        ("state/no-refs-fingerprint",           "test_блок_без_отпечатка_контекста_предупреждает"),
        ("state/refs-changed",                  "test_правка_контекста_предупреждает_но_не_роняет"),
        ("state/no-hypotheses-fingerprint",     "test_пройденный_блок_без_отпечатка_гипотез"),
        ("state/hypotheses-changed",            "test_правка_гипотез_после_проверки_роняет_проверку"),
        ("report/files-not-named",              "test_каждый_файл_блока_назван_полным_путём"),
        ("state/closed-without-fix-review",     "test_закрытие_с_починками_требует_ревью_правок"),
        ("report/no-coverage-limits",           "test_отчёт_без_раздела_про_непросмотренное_роняет_проверку"),
        ("report/empty-coverage-limits",        "test_пустой_раздел_ограничений_роняет_проверку"),
        ("root/guard-unusable",                 "test_узда_обязана_существовать"),
        ("root/no-guard",                       "test_третий_повтор_корня_требует_узду"),
        ("root/guard-partial",                  "test_корень_с_уздой_не_на_всех_экземплярах_предупреждает"),
        ("freshness/inert",                     "test_без_удалённого_репозитория_ворота_объявляют_себя_неработающими"),
        ("freshness/tree-behind",               "test_отставшее_от_сервера_дерево_роняет_проверку"),
        ("blocks/proof-unknown",                "test_род_доказательства_вне_словаря"),
        ("blocks/too-big-to-read",              "test_блок_который_за_сеанс_не_прочитать_роняет_проверку"),
        ("refs/findings-named-in-code",         "test_refs_находит_номер_находки_в_коде_и_только_его"),
        ("findings/fix-debt-age",               "test_check_предупреждает_о_находке_старше_недели"),
        ("sweep/undeclared",                    "test_перечисление_без_sweep_краснеет"),
        ("sweep/no-script",                     "test_sweep_без_скрипта_после_охоты_краснеет"),
    ]

    def test_каждые_ворота_check_записаны_вместе_со_своим_тестом(self):
        # Сравниваются не множества, а СЧЁТЫ: два разных гейта могут дать один ключ
        # (сообщение целиком из переменной), и на множествах второй такой гейт совпадал
        # бы с первым и проходил без теста — измерено мутацией.
        in_source = collections.Counter(g.key for g in _check_gates())
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

    # Ворота, которых в инструменте нет: реестр обязан видеть их по ФАКТУ отказа, как бы
    # ни было написано всё вокруг. Первые две формы — те самые, на которых реестр,
    # узнававший ворота по виду строки, молчал три круга подряд: ворота, вынесенные в
    # помощник, и контейнер, который в этом помощнике зовут иначе.
    UNSEEN_GATES = {
        "ворота в помощнике, контейнер зовут иначе":
            'def _reserved_role(defn, refusals):\n'
            '    if defn.get("role") == "__never__":\n'
            '        refusals.refuse("blocks/reserved-role", f"{bid}: role is reserved")\n\n'
            'def cmd_check(args):\n'
            '    gates = Refusals()\n'
            '    _reserved_role(defn, gates)\n'
            '    return gates.report()\n',
        "ворота в цикле внутри вложенной функции":
            'def cmd_check(args):\n'
            '    gates = Refusals()\n'
            '    def one(b):\n'
            '        for x in b:\n'
            '            if bad(x):\n'
            '                gates.refuse("blocks/reserved-role", f"{x}: role is reserved")\n'
            '    return gates.report()\n',
        "предупреждение, а не отказ":
            'def cmd_check(args):\n'
            '    gates = Refusals()\n'
            '    if soft:\n'
            '        gates.warn("blocks/reserved-role", f"{bid}: role is reserved")\n'
            '    return gates.report()\n',
    }

    def test_ворота_где_бы_они_ни_стояли_видны_реестру(self):
        """Ворота узнаются по ключу, который они пишут сами, а не по имени переменной, не
        по форме строки и не по тому, в какой функции стоят."""
        for how, source in self.UNSEEN_GATES.items():
            with self.subTest(форма=how):
                self.assertEqual([g.key for g in _check_gates(source)],
                                 ["blocks/reserved-role"],
                                 f"ворота, написанные как «{how}», реестр не увидел")

    def test_ворота_с_несобранным_сообщением_не_сливаются(self):
        """Обратная сторона: ключ не зависит от сообщения. Пока ключом был литеральный
        скелет f-строки, ворота, чьё сообщение приходит из переменной или из функции,
        получали ПУСТОЙ ключ, совпадали с уже записанными и проходили без единого теста —
        измерено мутацией. Ключ пишут на месте, и такие ворота различимы."""
        source = ('def cmd_check(args):\n'
                  '    gates = Refusals()\n'
                  '    msg = f"review_id mismatch"\n'
                  '    gates.refuse("state/review-id", msg)\n'
                  '    gates.refuse("finding/duplicate-target-unusable", dup_problem(f, dup))\n'
                  '    return gates.report()\n')
        keys = [g.key for g in _check_gates(source)]
        self.assertEqual(keys, ["state/review-id", "finding/duplicate-target-unusable"])

    def test_чтение_отказов_воротами_не_считается(self):
        """Обратная сторона: контейнер читают и печатают — это не ворота, и требовать от
        такого места записи в реестре значило бы требовать записи о печати."""
        reading = ('def cmd_check(args):\n'
                   '    gates = Refusals()\n'
                   '    if gates.problems:\n'
                   '        for p in gates.problems:\n'
                   '            print(f"  · {p}")\n'
                   '    return gates.report()\n')
        self.assertEqual(_check_gates(reading), [])

    def test_отказ_без_ключа_роняет_прогон_а_не_молчит(self):
        """Ключ, собранный по дороге, реестру нечем назвать: тогда ворота прошли бы без
        теста, а это ровно то, ради чего реестр и написан. Молчать нельзя."""
        source = ('def cmd_check(args):\n'
                  '    gates = Refusals()\n'
                  '    for key, msg in extra_gates():\n'
                  '        gates.refuse(key, msg)\n'
                  '    return gates.report()\n')
        with self.assertRaises(GateWithoutKey) as e:
            _check_gates(source)
        self.assertIn("gates.refuse(key, msg)", str(e.exception))
        self.assertIn("GATES", str(e.exception))

    def test_приговор_check_выносит_только_контейнер(self):
        """УЗДА КЛАССА «ворота мимо реестра»: ворота, которые печатают отказ сами и сами
        возвращают код, не видны ни записи, ни мутации — и снимаются при зелёном прогоне."""
        self.assertEqual(_own_verdict(), [], "у `check` появился выход мимо контейнера")

    # Обе стороны правила на исходниках, которых в инструменте нет.
    OWN_VERDICTS = {
        "печатает и возвращает сам":
            'def cmd_check(args):\n'
            '    gates = Refusals()\n'
            '    if bad:\n'
            '        print("CHECK FAILED: role is reserved")\n'
            '        return 1\n'
            '    return gates.report()\n',
        "выходит через sys.exit":
            'def cmd_check(args):\n'
            '    gates = Refusals()\n'
            '    if bad:\n'
            '        sys.exit(1)\n'
            '    return gates.report()\n',
        "красное состояние через die":
            'def cmd_check(args):\n'
            '    gates = Refusals()\n'
            '    if bad:\n'
            '        die("role is reserved")\n'
            '    return gates.report()\n',
    }

    def test_узда_видит_приговор_мимо_контейнера(self):
        for how, source in self.OWN_VERDICTS.items():
            with self.subTest(форма=how):
                self.assertNotEqual(_own_verdict(source), [],
                                    f"узда не увидела приговор «{how}»")
        good = ('def cmd_check(args):\n'
                '    gates = Refusals()\n'
                '    def local(b):\n'
                '        if not b:\n'
                '            return None\n'          # вложенная функция отвечает за себя сама
                '        return b\n'
                '    for b in blocks():\n'
                '        if local(b) is None:\n'
                '            gates.refuse("blocks/empty", f"{b}: empty")\n'
                '    return gates.report()\n')
        self.assertEqual(_own_verdict(good), [], "узда придирается к верной команде")


@unittest.skipIf(os.environ.get("FINETOOTH_TOOL"),
                 "прогон уже идёт на мутанте: мутировать мутанта незачем")
class GateMutationTest(unittest.TestCase):
    """УЗДА КЛАССА «ворота, которые нечем уронить» — измерением, а не списком.

    Реестр выше называет рядом с каждыми воротами тест, но что тест держит ИМЕННО ЭТИ
    ворота, не проверял никто: запись, переставленная на любой существующий тест, проходила
    обе проверки реестра. Здесь каждые ворота по очереди глушатся в копии инструмента, и
    названный тест обязан на этой копии покраснеть. Второй мутацией отказ становится
    предупреждением и наоборот: сообщение остаётся тем же, а код возврата меняется,
    и тест, который смотрит только на текст, этого не замечает — `check` печатает ту же
    фразу и выходит с нулём на состоянии, которое сам же отказался принять.

    Мутации независимы и каждая живёт в своём процессе, поэтому идут пачкой.
    """

    # Мутации ждут не процессора, а своих подпроцессов (git, инструмент): восьми хватает,
    # чтобы все ворота уложились в те же секунды, что один тест набора.
    WORKERS = 8

    @classmethod
    def setUpClass(cls) -> None:
        cls.lines = TOOL.read_text(encoding="utf-8").split("\n")
        cls.gates = _check_gates()
        cls.registered = dict(GateRegistryTest.GATES)

    def _silenced(self, gate: Gate) -> str:
        """Ворота сняты: оператор целиком заменён на `pass` — мутант обязан собираться,
        иначе «ни одного упавшего теста» читается как «тест не зависит от ворот»."""
        head = self.lines[gate.lineno - 1]
        indent = head[:len(head) - len(head.lstrip())]
        return "\n".join(self.lines[:gate.lineno - 1] + [indent + "pass"]
                         + self.lines[gate.end_lineno:])

    def _flipped(self, gate: Gate) -> str:
        """Ворота сменили строгость: отказ стал предупреждением или наоборот."""
        other = "warn" if gate.verb == "refuse" else "refuse"
        lines = list(self.lines)
        for i in range(gate.lineno - 1, gate.end_lineno):
            if f".{gate.verb}(" in lines[i]:
                lines[i] = lines[i].replace(f".{gate.verb}(", f".{other}(", 1)
                break
        return "\n".join(lines)

    @staticmethod
    def _run_on_copy(source: str | None, *names: str) -> subprocess.CompletedProcess:
        """Прогоняет названные тесты на КОПИИ СКИЛЛА, где инструмент заменён на `source`.

        Копируется скилл целиком, а не один файл: инструмент берёт у себя под боком
        `references/` и `assets/`, и на копии одного файла краснели бы тесты, которым
        нужны шаблоны, — «тест покраснел» значило бы тогда «копия неполная», а не
        «ворота держит тест». Узда, зелёная по неверной причине, — ровно тот дефект,
        который этот блок и ищет.
        """
        with tempfile.TemporaryDirectory(prefix="finetooth-mutant-") as d:
            skill = Path(d, SKILL.name)
            shutil.copytree(SKILL, skill, ignore=shutil.ignore_patterns("__pycache__"))
            tool = skill / "scripts" / "review.py"
            if source is not None:
                tool.write_text(source, encoding="utf-8")
            argv = [sys.executable, "-m", "unittest", "discover", "-s", str(KIT / "tests")]
            for name in names:
                argv += ["-k", name]
            return subprocess.run(argv, cwd=KIT, capture_output=True, text=True,
                                  env=child_env(FINETOOTH_TOOL=str(tool)))

    def _goes_red(self, gate: Gate, mutant: str) -> str:
        """Прогоняет названный рядом с воротами тест на мутанте. Возвращает пустую строку,
        если тест покраснел (так и надо), и жалобу, если прогон остался зелёным."""
        name = self.registered.get(gate.key)
        if name is None:
            return f"ворота не записаны в реестр: {gate.key}"
        out = self._run_on_copy(mutant, name)
        if "Ran 1 test" not in out.stderr:
            return (f"по имени `{name}` запустился не один тест, а "
                    f"{out.stderr.strip().splitlines()[-3:]}")
        if out.returncode != 0:
            return ""
        return (f"тест `{name}` зелёный на снятых воротах — он их не держит; "
                f"напишите тест, который краснеет, или укажите в реестре тот, который "
                f"краснеет")

    def test_на_целой_копии_все_названные_тесты_зелены(self):
        """Обратная сторона мутационной узды: сама копия ничего не ломает.

        Без этого «тест покраснел» доказывает не то, что он держит ворота, а только то,
        что он покраснел: копия, где инструмент лежит без своих `references/`, роняет
        каждый тест, которому нужен шаблон, — и узда считает это убийством мутанта.
        """
        names = sorted({name for _, name in GateRegistryTest.GATES})
        out = self._run_on_copy(None, *names)
        self.assertEqual(out.returncode, 0,
                         "на копии без мутаций названные тесты обязаны быть зелёными:\n"
                         + out.stderr[-2000:])
        self.assertIn(f"Ran {len(names)} test", out.stderr, out.stderr[-500:])

    def _all(self, mutate) -> None:
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.WORKERS) as pool:
            verdicts = list(pool.map(lambda g: self._goes_red(g, mutate(g)), self.gates))
        for gate, complaint in zip(self.gates, verdicts):
            with self.subTest(gate=gate.key):
                self.assertEqual(complaint, "", f"{TOOL.name}:{gate.lineno}: {complaint}")

    def test_названный_тест_краснеет_когда_ворота_сняты(self):
        self._all(self._silenced)

    def test_названный_тест_краснеет_когда_ворота_сменили_строгость(self):
        """Отказ, ставший предупреждением, — самый дешёвый способ провести состояние,
        которое инструмент отказался принять: сообщение печатается прежнее, а код
        возврата нулевой. Тест ворот обязан смотреть и на код возврата тоже."""
        self._all(self._flipped)


# Отказ ворот, написанных на оболочке: `exit` с ненулевым кодом ТАМ, ГДЕ ОБОЛОЧКА НАЧИНАЕТ
# КОМАНДУ, — начало строки, `;`, `&&`, `||`, ветка `case` или ключевое слово `then`, `else`,
# `do`. Ищется ПО ВИДУ, а не списком строк: отказ, дописанный завтра, попадает под правило
# сам. Пока предшественником считались только начало строки и `;`, `if … ; then exit 3; fi`
# — обычнейшая форма отказа, и ею написан отказ `run-role.sh` о потерянной записи в
# дневник — правилом не считался вовсе. Отказ вида `${1:?…}` сюда не входит: его печатает
# сама оболочка, и заглушить его нечем.
SHELL_REFUSAL = re.compile(
    r"(?:^|[;)]|\|\||&&|\b(?:then|else|do))(\s*exit\s+)[1-9][0-9]*\b")


def _shell_gates(source: str) -> list[int]:
    """Номера строк, на которых скрипт-ворота отказывает.

    Строка-комментарий отказом не считается: оба скрипта объясняют свои коды возврата
    прозой рядом с ними («a path that does not exist is a REFUSAL (exit 2)»), и мутанту
    из комментария нечего заглушать.
    """
    return [i for i, line in enumerate(source.splitlines(), 1)
            if not line.lstrip().startswith("#") and SHELL_REFUSAL.search(line)]


def _silence_refusal(line: str) -> str:
    """Отказ обращён в успех: `exit 2` → `exit 0`.

    Мутант обязан оставаться исполнимым скриптом — иначе «прогон покраснел» значило бы
    «копия не запускается», а не «отказ держит тест».
    """
    return SHELL_REFUSAL.sub(
        lambda m: m.group(0)[:m.end(1) - m.start(0)] + "0", line, count=1)


class ShellGateMutationTest(unittest.TestCase):
    """УЗДА КЛАССА «ворота, которые нечем уронить» — для ворот, написанных на оболочке.

    `GateMutationTest` глушит ворота внутри `cmd_check` и ворот на оболочке не видит
    вовсе. А они есть, и красноречиво: `dco.sh` печатал «all commits are signed off» и
    выходил с нулём, когда git не смог разобрать диапазон, а три отказа `guard-grep.sh`
    (неизвестный ключ, нет образца, нет путей) не держал ни один тест — каждый из них
    можно было обратить в успех, и прогон оставался зелёным. Здесь каждый отказ по очереди
    становится `exit 0`, и названный рядом прогон обязан на такой копии покраснеть.
    """

    # Скрипт-ворота → прогоны, которые обязаны его держать (образцы `-k`, годится и имя
    # класса, и имя теста). Список не «те скрипты, о которых вспомнили»: он сверяется с
    # `git ls-files` тестом ниже, и скрипт с отказом, которого здесь нет, роняет прогон,
    # называя себя. Пока список был написан от руки, `run-role.sh` лежал вне правила, а
    # четвёртые ворота попали бы туда же молча.
    GATES = {".github/dco.sh": ("DcoGateTest",),
             "skills/finetooth/assets/guard-grep.sh": ("GuardGrepTest",),
             "skills/finetooth/assets/run-role.sh": (
                 "test_run_role_отказывает_на_неизвестной_роли",
                 "test_потерянная_запись_в_журнал_не_выдаёт_себя_за_чистый_прогон")}
    # Мутанты ждут не процессора, а своих подпроцессов (git, bash, awk).
    WORKERS = 8

    def test_каждые_ворота_на_оболочке_под_правилом(self):
        """Предмет правила берётся у git, а не из памяти автора. Скрипт без отказов уздой
        не проверяется — глушить в нём нечего; скрипт с отказом обязан назвать прогон,
        который эти отказы держит."""
        with_refusals = [rel for rel in tracked("*.sh")
                         if _shell_gates((KIT / rel).read_text(encoding="utf-8"))]
        self.assertTrue(with_refusals, "в наборе не нашлось ни одного скрипта с отказом")
        self.assertEqual(
            sorted(set(with_refusals) - set(self.GATES)), [],
            "скрипт с отказом вне правила: впишите его в GATES вместе с прогоном, который "
            "его отказы держит, — иначе ворота можно обратить в успех, и прогон зелёный")
        self.assertEqual(
            sorted(set(self.GATES) - set(with_refusals)), [],
            "в GATES назван скрипт, у которого отказов нет: глушить в нём нечего, и "
            "правило о нём молчит — уберите строку или напишите отказ")

    # Соседи, без которых копия скрипта не работает: `run-role.sh` зовёт `axes.py` путём от
    # самого себя, и копия в голом временном каталоге падала бы не от мутации, а оттого, что
    # соседа рядом нет — «прогон покраснел» перестало бы что-либо доказывать. Названо
    # явно: угадывать, что именно скрипту нужно рядом, значит угадывать молча.
    NEIGHBOURHOOD = {"skills/finetooth/assets/run-role.sh": "skills/finetooth"}

    @classmethod
    def _run_suite(cls, rel: str, source: str | None,
                   suites: tuple[str, ...]) -> subprocess.CompletedProcess:
        """Прогоняет названные наборы на КОПИИ скрипта, подменённой через окружение."""
        with tempfile.TemporaryDirectory(prefix="finetooth-shell-") as d:
            if rel in cls.NEIGHBOURHOOD:
                near = cls.NEIGHBOURHOOD[rel]
                shutil.copytree(KIT / near, Path(d, near))
                copy = Path(d, rel)
            else:
                copy = Path(d, Path(rel).name)
            copy.write_text((KIT / rel).read_text(encoding="utf-8")
                            if source is None else source, encoding="utf-8")
            copy.chmod(0o755)  # бит исполнения смотрит тест «скрипт без вызова — не ворота»
            keys = [a for s in suites for a in ("-k", s)]
            return subprocess.run(
                [sys.executable, "-m", "unittest", "discover", "-s", str(KIT / "tests"),
                 *keys], cwd=KIT, capture_output=True, text=True,
                env=child_env(FINETOOTH_SHELL_GATE=f"{rel}={copy}"))

    def test_на_целой_копии_прогон_ворот_зелёный(self):
        """Обратная сторона: сама подмена ничего не ломает. Без этого «прогон покраснел»
        доказывало бы не то, что отказ держит тест, а только то, что копия не работает."""
        for rel, suites in self.GATES.items():
            with self.subTest(ворота=rel):
                out = self._run_suite(rel, None, suites)
                self.assertEqual(out.returncode, 0,
                                 f"{rel}: на копии без мутаций `{', '.join(suites)}` обязан "
                                 f"быть зелёным:\n{out.stderr[-2000:]}")

    def test_каждый_отказ_скрипта_держит_тест(self):
        jobs = []
        for rel, suites in self.GATES.items():
            source = (KIT / rel).read_text(encoding="utf-8")
            lines = source.splitlines(keepends=True)
            refusals = _shell_gates(source)
            with self.subTest(ворота=rel):
                self.assertTrue(refusals, f"{rel}: не нашлось ни одного отказа")
            for lineno in refusals:
                jobs.append((rel, lineno, suites,
                             "".join(lines[:lineno - 1]
                                     + [_silence_refusal(lines[lineno - 1])]
                                     + lines[lineno:])))
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.WORKERS) as pool:
            codes = list(pool.map(
                lambda j: self._run_suite(j[0], j[3], j[2]).returncode, jobs))
        for (rel, lineno, suites, _), code in zip(jobs, codes):
            with self.subTest(ворота=f"{rel}:{lineno}"):
                self.assertNotEqual(
                    code, 0,
                    f"{rel}:{lineno}: отказ обращён в успех, а `{', '.join(suites)}` "
                    f"зелёный — этот отказ не держит ни один тест. Напишите тест, который "
                    f"на нём краснеет: ворота, которые нечем уронить, — не ворота")

    # Обе стороны самого правила, на скриптах, которых в наборе нет: отказ узнаётся по
    # виду, а успех и чужой `exit` в тексте — не отказ.
    REFUSAL_SHAPES = {
        "отказ в отдельной строке": ("if [ -z \"$x\" ]; then\n  exit 1\nfi\n", 2),
        "отказ после точки с запятой": ("case $1 in\n*) echo no >&2; exit 2 ;;\nesac\n", 2),
        # Формы, которых правило не видело: отказ в одну строку с `then`, отказ после
        # `||` и ветка `case` без echo. Каждой написан не один скрипт ворот.
        "отказ в одну строку с then": ("if [ -z \"$x\" ]; then exit 3; fi\n", 1),
        "отказ после else": ("if ok; then :\nelse exit 4\nfi\n", 2),
        "отказ после ||": ("check || exit 5\n", 1),
        "отказ веткой case": ("case $1 in\n*) exit 2 ;;\nesac\n", 2),
    }
    INNOCENT_SHAPES = ("[ -n \"$x\" ] || exit 0\n",
                       "# a gate exits 1 when the tree is dirty\n",
                       "# a path that does not exist is a REFUSAL (exit 2), not a miss\n",
                       "# if the range is empty; then exit 1 — that is the old wording\n",
                       "awk 'END { exit(found ? 1 : 0) }' f\n",
                       "if [ \"$RC\" -ne 0 ]; then exit \"$RC\"; fi\n")

    def test_узда_видит_отказ_которого_ещё_нет(self):
        for why, (src, lineno) in self.REFUSAL_SHAPES.items():
            with self.subTest(отказ=why):
                self.assertEqual(_shell_gates(src), [lineno],
                                 "узда не увидела отказ по виду")
                line = src.splitlines(keepends=True)[lineno - 1]
                self.assertIn("exit 0", _silence_refusal(line),
                              "отказ не обращён в успех — мутант ничего не проверяет")
        for src in self.INNOCENT_SHAPES:
            with self.subTest(невиновный=src.strip()):
                self.assertEqual(_shell_gates(src), [],
                                 "узда приняла за отказ то, что отказом не является")


def _spawns(source: str) -> list[tuple[int, str]]:
    """Запуски потомков в наборе и то, чем они грешат: (строка, жалоба).

    Потомок запускается здесь три десятка раз, и каждый раз — это вопрос «зависит ли
    приговор от машины». Два ответа обязаны быть одинаковыми везде: окружение задаёт
    `child_env`, а интерпретатор — тот же, на котором идёт прогон.

    Запуск узнаётся по тому, ЧТО зовут, а не по тому, как это написали: `subprocess.run`,
    модуль под псевдонимом, имя, втянутое `from subprocess import run`, — один и тот же
    потомок. Имя интерпретатора и окружение читаются там, где их собрали.
    """
    vals = _Values(source)
    tree = vals.tree
    spawners = ("run", "Popen", "call", "check_output", "check_call")

    # За чем стоит сам модуль и за чем — его порождающие функции.
    modules, imported = {"subprocess"}, set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules |= {a.asname or a.name for a in node.names if a.name == "subprocess"}
        elif isinstance(node, ast.ImportFrom) and node.module == "subprocess":
            imported |= {a.asname or a.name for a in node.names if a.name in spawners}

    def is_child_env(node) -> bool:
        return (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "child_env")

    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        by_module = (isinstance(node.func, ast.Attribute) and node.func.attr in spawners
                     and isinstance(node.func.value, ast.Name)
                     and node.func.value.id in modules)
        # Втянутое имя может быть перекрыто своим: `run = lambda ...` в тесте — это не
        # `subprocess.run`, и требовать от него окружения значило бы требовать пустого.
        by_name = (isinstance(node.func, ast.Name) and node.func.id in imported
                   and not vals.lookup(node.func.id, vals.scope_of(node)))
        if not (by_module or by_name):
            continue
        why = []
        passed = next((k.value for k in node.keywords if k.arg == "env"), None)
        if passed is None:
            why.append("без env=child_env(): локаль и конфиг git достаются от машины")
        elif isinstance(passed, ast.Name):
            # `env=env` — обычная форма, когда одно окружение нужно двум запускам:
            # переменная годится ровно настолько, насколько годится всё, что в неё клали.
            values = vals.lookup(passed.id, vals.scope_of(passed))
            if not values or not all(is_child_env(v) for v in values):
                why.append(f"env={passed.id}, а он собран не из child_env()")
        elif not is_child_env(passed):
            why.append("env= собран не из child_env()")
        head = next(iter(vals.elements(node.args[0]) if node.args else []), None)
        try:
            first = vals.literal(head) if head is not None else ""
        except (ValueError, TypeError, SyntaxError):
            first = ""
        if isinstance(first, str) and re.fullmatch(r"python[\d.]*", first):
            why.append(f"`{first}` из PATH вместо sys.executable: прогон на другом "
                       f"интерпретаторе измерил бы не его")
        if why:
            offenders.append((node.lineno, "; ".join(why)))
    return offenders


class TestSuiteRuleTest(unittest.TestCase):
    """УЗДА КЛАССА «приговор набора зависит от машины».

    Прогон запускает потомков три десятка раз. Локаль задавал один `Stand.run`, а
    остальные брали её у среды; интерпретатор брался из PATH там, где прогон идёт на
    другом. Правило по исходнику держит и те запуски, которых ещё нет, — список мест не
    держал бы: следующий запуск напишут копией соседнего.
    """

    def test_каждый_потомок_запускается_с_общим_окружением(self):
        offenders = _spawns(Path(__file__).read_text(encoding="utf-8"))
        self.assertEqual(
            offenders, [],
            "запуск потомка мимо общего окружения: env=child_env(...) и sys.executable")

    # Обе стороны правила на исходниках, которых в наборе нет: узда обязана видеть
    # нарушение по виду и не придираться к тому, что написано верно.
    OFFENDERS = {
        "без окружения": 'subprocess.run(["git", "status"], capture_output=True)',
        "чужое окружение": 'subprocess.run(["git", "status"], env=dict(os.environ, X="1"))',
        "окружение из переменной мимо child_env":
            'e = dict(os.environ)\nsubprocess.run(["git", "status"], env=e)',
        "интерпретатор из PATH":
            'subprocess.run(["python3", str(TOOL)], env=child_env())',
    }
    INNOCENT = {
        "прямой вызов": 'subprocess.run([sys.executable, str(TOOL)], env=child_env())',
        "окружение с добавкой": 'subprocess.run(["bash", "x.sh"], env=child_env(TMPDIR="/t"))',
        "окружение из переменной": 'e = child_env(X="1")\nsubprocess.run(["git"], env=e)',
    }

    def test_узда_видит_запуск_которого_ещё_нет(self):
        for why, src in self.OFFENDERS.items():
            with self.subTest(нарушение=why):
                self.assertNotEqual(_spawns(src), [], "узда не увидела запуск по виду")
        for why, src in self.INNOCENT.items():
            with self.subTest(невиновный=why):
                self.assertEqual(_spawns(src), [], "узда придирается к верной записи")

    # Локаль, в которой набор отказывается идти: та самая, ради которой отказ и написан.
    HOSTILE = dict(LC_ALL="C", LANG="C", PYTHONUTF8="0", PYTHONCOERCECLOCALE="0")

    def _import_suite(self, hostile: bool = False) -> subprocess.CompletedProcess:
        env = child_env()
        if hostile:
            # Единственное место, где общее окружение снимают НАМЕРЕННО: проверяется
            # то самое, от чего оно защищает.
            env.update(self.HOSTILE)
            env.pop("PYTHONIOENCODING", None)   # иначе поток кодируется мимо локали
        return subprocess.run([sys.executable, "-c", "import test_review"],
                              cwd=str(KIT / "tests"), capture_output=True, text=True, env=env)

    def test_отказ_набора_читается_в_той_локали_ради_которой_написан(self):
        """Отказ печатается там, где не-ASCII печататься не может.

        В локали C stderr переходит на backslashreplace: русский текст приходит
        вереницей `\\xd0\\xba`, и причина, которую нельзя прочесть, — это отсутствие
        причины. Проверяется не форма строки в исходнике, а то, что доехало до потока.
        """
        out = self._import_suite(hostile=True)
        if out.returncode == 0:
            self.skipTest("интерпретатор включает режим UTF-8 сам: отказу не на чем сработать")
        self.assertIn("filesystem encoding is", out.stderr,
                      "отказ не назвал причину:\n" + out.stderr[-800:])
        self.assertIn("PYTHONUTF8=1 python3 -m unittest discover -s tests", out.stderr,
                      "отказ не назвал команду, которая его снимает")
        self.assertEqual(
            re.findall(r"\\x[0-9a-f]{2}|\\u[0-9a-f]{4}", out.stderr), [],
            "в отказе есть символы, которые эта локаль печатать не умеет — "
            "он обязан быть из одного ASCII:\n" + out.stderr[-800:])

    def test_в_UTF_8_локали_набор_импортируется_молча(self):
        """Обратная сторона: отказ не срабатывает там, где всё в порядке, — иначе
        «набор не идёт» стало бы нормой прогона."""
        out = self._import_suite()
        self.assertEqual(out.returncode, 0, out.stderr[-800:])
        self.assertEqual(out.stderr.strip(), "", "молчаливый импорт обязан быть молчаливым")


def _asks_the_tool_for_commands(fn: ast.FunctionDef) -> bool:
    """Обход спросил список подкоманд у самого инструмента: `--help` или `_subcommands()`.

    Вопрос ищется в КОДЕ, а не в тексте функции: докстрока, называющая `--help`, — это
    рассказ об обходе, а не обход.
    """
    for n in ast.walk(fn):
        if not isinstance(n, ast.Call):
            continue
        if isinstance(n.func, ast.Name) and n.func.id == "_subcommands":
            return True
        if isinstance(n.func, ast.Attribute) and n.func.attr == "_subcommands":
            return True
        if any(isinstance(a, ast.Constant) and a.value == "--help" for a in n.args):
            return True
    return False


def _runs_a_command_it_was_given(fn: ast.FunctionDef) -> bool:
    """Обход зовёт команду, имя которой он получил, а не написал: довод не строка-литерал.

    `self.s.run(*[cmd])` — тот же обход: имя приходит из развёрнутого списка, и правило,
    смотревшее только на голое имя первым доводом, такой обход не видело вовсе.
    """
    for n in ast.walk(fn):
        if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == "run" and n.args):
            continue
        first = n.args[0]
        if isinstance(first, ast.Starred):
            return True
        if not (isinstance(first, ast.Constant) and isinstance(first.value, str)):
            return True
    return False


def _asserts_the_command_started(fn: ast.FunctionDef) -> bool:
    """Обход СПРАШИВАЕТ про отказ argparse и ВЕШАЕТ НА ОТВЕТ проверку.

    Оба условия измерены на выдуманных обходах: имя `argparse_refused` в докстроке,
    мёртвое `argparse_refused = None` и вызов без проверки оставляют обход ровно таким,
    каким он был до правила. Годится и общий помощник, и свой перебор `ARGPARSE_REFUSED`
    — важно, что вопрос задан в коде, а ответ доведён до утверждения.
    """
    # `for said in ARGPARSE_REFUSED: ... assertNotIn(said, ...)` — проверка утверждает про
    # имя, взятое ИЗ словаря; без этого свой перебор выглядел бы обходом без вопроса.
    borrowed: set[str] = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.For) and any(
                isinstance(n, ast.Name) and n.id == "ARGPARSE_REFUSED"
                and isinstance(n.ctx, ast.Load) for n in ast.walk(node.iter)):
            borrowed |= {t.id for t in ast.walk(node.target) if isinstance(t, ast.Name)}
    for node in ast.walk(fn):
        if not (isinstance(node, ast.Assert)
                or (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr.startswith("assert"))):
            continue
        for n in ast.walk(node):
            if (isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)
                    and (n.id in ("argparse_refused", "ARGPARSE_REFUSED") or n.id in borrowed)):
                return True
    return False


def _sweeps_without_body_check(source: str) -> list[str]:
    """Обходы команд, которые не смотрят, дошла ли команда до своего тела.

    Обход узнаётся ПО ВИДУ, а не по имени: он спросил список у самого инструмента
    (`--help` или общий `_subcommands`) и зовёт команду, имя которой получил. Такой обход
    обязан спросить общий словарь отказов argparse и повесить на ответ проверку — иначе
    он перечисляет команды, а проверяет отказ argparse, и мимо него проходит ровно то,
    что он заведён держать.
    """
    return [fn.name for fn in ast.walk(ast.parse(source))
            if isinstance(fn, ast.FunctionDef) and fn.name.startswith("test_")
            and _asks_the_tool_for_commands(fn) and _runs_a_command_it_was_given(fn)
            and not _asserts_the_command_started(fn)]


class CommandSweepRuleTest(unittest.TestCase):
    """УЗДА КЛАССА «узда перечисляет свой предмет, не запуская его».

    Два обхода подряд брали список подкоманд у самого инструмента — и звали их так, что
    argparse отвергал часть до их кода: до `init` не доходил обход порченых определений, до
    `set-status`, `set-finding` и `log` — обход границы записи, то есть до трёх из тех
    команд, что пишут. Оба обхода были зелёные, и оба записаны как правила, под которые
    новая команда попадает сама. Правило по исходнику набора держит и тот обход, которого
    ещё нет: следующий напишут копией соседнего.
    """

    def test_каждый_обход_команд_проверяет_что_команда_началась(self):
        self.assertEqual(
            _sweeps_without_body_check(Path(__file__).read_text(encoding="utf-8")), [],
            "обход берёт список команд у инструмента и не проверяет, что команда дошла до "
            "тела: спросите argparse_refused(out.stderr) и зовите команды через BODY_ARGV")

    # Обе стороны правила, на обходах, которых в наборе нет.
    SWEEP_SHAPES = {
        "обход через --help": (
            "class S:\n    def test_x(self):\n"
            "        cmds = re.findall(r'x', self.s.run('--help').stdout)\n"
            "        for cmd in cmds:\n            self.s.run(cmd)\n"),
        "обход через общий список": (
            "class S:\n    def test_x(self):\n"
            "        for cmd in self._subcommands():\n            self.s.run(cmd)\n"),
        # Три способа выглядеть спросившим, не спросив: измерены на правиле, которое
        # искало имя `argparse_refused` в тексте функции и команду — голым именем.
        "вопрос только в докстроке": (
            "class S:\n    def test_x(self):\n"
            "        '''Каждая команда зовётся так, что argparse_refused пуст.'''\n"
            "        for cmd in self._subcommands():\n            self.s.run(cmd)\n"),
        "мёртвое присваивание вместо вопроса": (
            "class S:\n    def test_x(self):\n"
            "        argparse_refused = None\n"
            "        for cmd in self._subcommands():\n            self.s.run(cmd)\n"),
        "вопрос без проверки": (
            "class S:\n    def test_x(self):\n"
            "        for cmd in self._subcommands():\n"
            "            out = self.s.run(cmd)\n"
            "            argparse_refused(out.stderr)\n"),
        "имя команды через развёртывание списка": (
            "class S:\n    def test_x(self):\n"
            "        for cmd in self._subcommands():\n            self.s.run(*[cmd])\n"),
    }
    INNOCENT_SWEEPS = {
        "обход, который спросил про argparse": (
            "class S:\n    def test_x(self):\n"
            "        for cmd in self._subcommands():\n"
            "            out = self.s.run(cmd, *BODY_ARGV[cmd])\n"
            "            self.assertFalse(argparse_refused(out.stderr))\n"),
        "обход со своей копией словаря отказов": (
            "class S:\n    def test_x(self):\n"
            "        for cmd in self._subcommands():\n"
            "            out = self.s.run(cmd)\n"
            "            for said in ARGPARSE_REFUSED:\n"
            "                self.assertNotIn(said, out.stderr)\n"),
        "перебор двух названных команд": (
            "class S:\n    def test_x(self):\n"
            "        for cmd in ('check', 'coverage'):\n            self.s.run(cmd)\n"),
        "развёртывание списка, но со спросом": (
            "class S:\n    def test_x(self):\n"
            "        for cmd in self._subcommands():\n"
            "            out = self.s.run(*[cmd, *BODY_ARGV[cmd]])\n"
            "            self.assertFalse(argparse_refused(out.stderr))\n"),
        "рассказ об обходе, а не обход": (
            "class S:\n    def test_x(self):\n"
            "        '''Список берётся у --help, как в обходе через _subcommands().'''\n"
            "        self.assertIn('check', self.s.run('--help').stdout)\n"),
    }

    def test_узда_видит_обход_которого_ещё_нет(self):
        for why, src in self.SWEEP_SHAPES.items():
            with self.subTest(обход=why):
                self.assertEqual(_sweeps_without_body_check(src), ["test_x"],
                                 "узда не увидела обход по виду")
        for why, src in self.INNOCENT_SWEEPS.items():
            with self.subTest(невиновный=why):
                self.assertEqual(_sweeps_without_body_check(src), [],
                                 "узда придирается к верному обходу")


class DcoGateTest(unittest.TestCase):
    """CONTRIBUTING обещает, что каждый коммит подписан, — и до этих ворот обещание не
    держало ничто, кроме галочки в шаблоне предложения, которую автор ставит сам."""

    SCRIPT = shell_gate(".github/dco.sh")

    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="finetooth-dco-"))
        self.addCleanup(shutil.rmtree, self.root, True)
        self.git("init", "-q", "-b", "main", ".")
        self.git("config", "user.name", "Анна Автор")
        self.git("config", "user.email", "anna@example.com")
        self.commit("first", signoff="Анна Автор <anna@example.com>")

    def git(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", *args], cwd=self.root, check=True,
                              capture_output=True, text=True, env=child_env())

    def commit(self, subject: str, *, signoff: str | None = None, author: str | None = None) -> None:
        (self.root / f"{subject}.txt").write_text(subject + "\n", encoding="utf-8")
        self.git("add", "-A")
        message = subject if signoff is None else f"{subject}\n\nSigned-off-by: {signoff}"
        extra = ["--author", author] if author else []
        self.git("commit", "-qm", message, *extra)

    def check(self, rng: str) -> subprocess.CompletedProcess:
        return subprocess.run(["bash", str(self.SCRIPT), rng], cwd=self.root,
                              capture_output=True, text=True, env=child_env())

    def test_коммит_без_подписи_роняет_ворота_и_называет_починку(self):
        self.commit("second")
        out = self.check("HEAD~1..HEAD")
        self.assertEqual(out.returncode, 1, out.stdout + out.stderr)
        self.assertIn("second", out.stderr)
        self.assertIn("git rebase --signoff", out.stderr)
        self.assertIn("CONTRIBUTING.md", out.stderr)

    def test_подпись_с_чужой_почтой_не_засчитывается(self):
        """Подпись, перенесённая из соседнего коммита, не удостоверяет ничего: DCO
        подписывает тот, кто передаёт код."""
        self.commit("borrowed", signoff="Борис Другой <boris@example.com>")
        self.assertEqual(self.check("HEAD~1..HEAD").returncode, 1)

    def test_подписанные_коммиты_проходят(self):
        """Обратная сторона, и она важнее: ворота не должны заворачивать честную работу.
        Проверяются и разные авторы в одной ветке, и подпись, набранная в другом регистре."""
        self.commit("second", signoff="Анна Автор <anna@example.com>")
        self.commit("third", signoff="Пётр Второй <PETR@example.com>",
                    author="Пётр Второй <petr@example.com>")
        self.commit("fourth", signoff="Анна Автор <anna@example.com>")
        out = self.check("HEAD~3..HEAD")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertIn("signed off", out.stdout)

    # Адреса, в которых есть метасимволы регулярного выражения. Это не редкий случай:
    # `12345678+login@users.noreply.github.com` GitHub выдаёт каждому, кто закрыл свою
    # почту, и коммитит под ним из веб-интерфейса; точка в локальной части — обычная
    # форма корпоративного адреса.
    METACHARACTER_ADDRESSES = ("12345678+octocat@users.noreply.github.com",
                               "first.last@company.com", "dev+finetooth@example.com")

    def test_подпись_с_адреса_с_метасимволами_проходит(self):
        """Сторона, которая важнее: честную работу ворота не заворачивают.

        Адрес автора уходил в образец `grep -E` как есть, и `+` становился квантором:
        подписанный коммит получал отказ, а названная в отказе починка
        (`git rebase --signoff`) заново писала ту же самую строку — выхода из отказа не
        было вовсе.
        """
        for i, addr in enumerate(self.METACHARACTER_ADDRESSES):
            who = f"Кто-То {i} <{addr}>"
            self.commit(f"meta{i}", signoff=who, author=who)
        out = self.check(f"HEAD~{len(self.METACHARACTER_ADDRESSES)}..HEAD")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertIn("signed off", out.stdout)

    def test_подпись_на_похожий_адрес_не_засчитывается(self):
        """Та же поломка в другую сторону: точка в образце — это любой знак, и подпись
        `aXb@example.com` удостоверяла коммит автора `a.b@example.com`. Адрес сверяется
        строкой, а не образцом."""
        self.commit("lookalike", signoff="Борис Другой <aXb@example.com>",
                    author="Анна Автор <a.b@example.com>")
        out = self.check("HEAD~1..HEAD")
        self.assertEqual(out.returncode, 1, out.stdout + out.stderr)

    def test_нерешаемый_диапазон_роняет_ворота_и_называет_починку(self):
        """`git rev-list` читался через подстановку процесса и свой код возврата не
        сообщал никому: на диапазоне, которого git не понимает — клон без `origin/dev`,
        удалённый под другим именем, — список коммитов выходил пустым, и ворота печатали
        «all commits are signed off» с нулём, не посмотрев ни одного коммита. Ровно тот
        диапазон, который CONTRIBUTING велит гонять у себя."""
        self.commit("unsigned")
        out = self.check("origin/dev..HEAD")
        self.assertEqual(out.returncode, 1, out.stdout + out.stderr)
        self.assertNotIn("signed off", out.stdout)
        self.assertIn("git fetch", out.stderr, "отказ обязан называть, что делать")

    def test_диапазон_без_коммитов_ворота_не_роняет(self):
        """Обратная сторона: диапазон, который git понимает, но в котором коммитов нет,
        — не нарушение. Проверка списка не должна превратить пустую ветку в отказ."""
        out = self.check("HEAD..HEAD")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertIn("signed off", out.stdout)

    def test_коммит_слияния_подписи_не_требует(self):
        """Слияние не несёт ничьего авторства кода, и `git merge` не подписывает его."""
        self.git("checkout", "-q", "-b", "side")
        self.commit("side-work", signoff="Анна Автор <anna@example.com>")
        self.git("checkout", "-q", "main")
        self.commit("main-work", signoff="Анна Автор <anna@example.com>")
        self.git("merge", "--no-ff", "-q", "-m", "merge side", "side")
        out = self.check("HEAD~2..HEAD")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)

    def test_рабочий_процесс_зовёт_эти_ворота(self):
        """Скрипт без вызова — не ворота."""
        wf = (KIT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
        self.assertIn(".github/dco.sh", wf)
        self.assertIn("fetch-depth: 0", wf)
        self.assertTrue(os.access(self.SCRIPT, os.X_OK), "dco.sh не исполняемый")


def _workflow_steps(text: str) -> list[str]:
    """Командные строки рабочего процесса: тело каждого `run:`, по строке за раз.

    Искать по всему тексту процесса нельзя, и это измерено: `python3` встречается в шаге,
    который ставит валидатор скилла, а `tests` — в имени самого процесса (`name: tests`),
    так что узда, требовавшая двух таких слов где угодно, оставалась зелёной и когда из CI
    удаляли шаг с прогоном тестов, и когда удаляли весь его job. Запускает команды только
    `run:`, и сверять надо с ним.
    """
    lines, steps, i = text.splitlines(), [], 0
    while i < len(lines):
        m = re.match(r"^(\s*)(?:-\s+)?run:[ \t]*([|>][-+]?)?[ \t]*(.*)$", lines[i])
        i += 1
        if not m:
            continue
        indent, folded, inline = m.group(1), m.group(2), m.group(3).strip()
        if not folded:
            steps.append(inline)
            continue
        # Тело блочного значения — всё, что отбито глубже ключа.
        while i < len(lines) and (not lines[i].strip()
                                  or lines[i].startswith(indent + " ")):
            if lines[i].strip():
                steps.append(lines[i].strip())
            i += 1
    return steps


# Доводы, которые шаг ВПРАВЕ добавить к объявленной команде: они делают прогон громче, а
# не уже. Всё остальное — отказ по имени: `-k НетТакого` гоняет ноль тестов, `|| true`
# уносит код возврата мимо CI, и оба измерены зелёными на правиле, которое считало любой
# лишний довод безобидным. Новый довод вписывается сюда вместе с причиной, почему он не
# сужает ворота, — молчаливое «наверное, ничего» и есть то, чем ворота отключают.
WIDENING_ARGS = ("-v", "--verbose")
# Выражение GitHub Actions, свёрнутое в одно слово: `${{ github.sha }}` содержит пробелы,
# и по пробелам диапазон рассыпается на пять слов, из которых на диапазон похоже `}}..${{`.
SUBSTITUTION = "${{}}"


def _step_tokens(step: str) -> list[str]:
    """Слова командной строки шага, с выражениями `${{ … }}`, свёрнутыми в одно слово."""
    return re.sub(r"\$\{\{[^{}]*\}\}", SUBSTITUTION, step).split()


def _runs_command(cmd: str, step: str) -> bool:
    """Шаг гоняет ИМЕННО эту команду: та же программа, все её доводы в том же порядке, и
    ничего сверх того, что названо расширением.

    Программа сверяется по имени, а не по пути: в CI валидатор лежит в venv под
    `$RUNNER_TEMP`, а зовётся тем же именем. Диапазон коммитов CI подставляет из события,
    поэтому на месте объявленного диапазона принимается подстановка — но не собственный
    диапазон шага: `.github/dco.sh HEAD~1..HEAD` проверяет один коммит вместо всех
    коммитов предложения, и это те же отключённые ворота, только тише.
    """
    want, got = cmd.split(), _step_tokens(step)
    if not want or not got:
        return False
    if Path(want[0].strip("\"'")).name != Path(got[0].strip("\"'")).name:
        return False
    rest, extra = got[1:], []
    for arg in want[1:]:
        if ".." in arg:
            hit = next((i for i, g in enumerate(rest)
                        if ".." in g and (SUBSTITUTION in g or g == arg)), None)
        else:
            hit = rest.index(arg) if arg in rest else None
        if hit is None:
            return False
        extra += rest[:hit]
        rest = rest[hit + 1:]
    return all(a in WIDENING_ARGS for a in extra + rest)


def _gates_not_run(commands: list[str], steps: list[str]) -> list[str]:
    """Команды, которые документ велит гонять, а ни один шаг процесса не гоняет."""
    return [cmd for cmd in commands
            if not any(_runs_command(cmd, step) for step in steps)]


# Начало пункта списка любого вида: маркер `-`, `*`, `+` или номер с точкой либо скобкой.
# Нумерованный пункт правило раньше не знало вовсе, а `RELEASING.md` — нумерованная
# процедура целиком: абзац, написанный вплотную под шагом 4, уезжал внутрь шага 4.
LIST_OPENER = re.compile(r"^(\s*)([-*+]|\d{1,9}[.)])( +)(?=\S)")
# Строки, которые пунктом НЕ проглатываются. Ленивое продолжение бывает только у АБЗАЦА:
# строка, которая сама открывает блок, список обрывает и печатается там, где написана.
# Таких четыре (ограда — пятая, её функция считает отдельно): ATX-заголовок, цитата,
# тематический разрыв и html-блок типов 1–6. Строка таблицы и определение ссылки сюда НЕ
# входят: ни то ни другое абзац не прерывает (CommonMark 4.7; шапку таблицы GFM собирает
# из последней строки абзаца), и `| a | b |` или `[x]: url` сразу за пунктом остаются
# внутри пункта — послабление здесь ослепило бы правило на настоящем склеивании.
OWN_BLOCK = re.compile(r"^ {0,3}(?:>|#{1,6}(?:\s|$)|(?:\*\s*){3,}$|(?:-\s*){3,}$"
                       r"|(?:_\s*){3,}$|<[A-Za-z/!?])")


def _glued_to_list_item(text: str) -> list[str]:
    """Абзацы, приклеенные к пункту списка: строка текста под пунктом, без пустой строки.

    По правилам markdown такой абзац — ЧАСТЬ пункта (ленивое продолжение), а не свой
    абзац. Вводный абзац блока попал внутрь записи про `NOTICE.md`, и пятнадцать пунктов
    блока оказались под заголовком, которого в разметке нет, — а заметки о выпуске берут
    этот раздел как есть.

    Разделяет продолжение и абзац КОЛОНКА, с которой начинается текст пункта, а не факт
    отступа: под `- пункт` текст пункта идёт с колонки 2, и строка, отбитая одним
    пробелом, проглатывается ровно так же, как отбитая нулём. Правило, смотревшее на
    «есть ли отступ», такую строку не видело, как не видело и абзац после законного
    продолжения пункта.
    """
    glued, fence, column = [], "", None
    for i, line in enumerate(text.splitlines(), 1):
        edge = re.match(r"^\s*(```+|~~~+)", line)
        if fence:
            if edge and edge.group(1)[0] == fence[0] and len(edge.group(1)) >= len(fence):
                fence = ""
            continue
        if edge or not line.strip():
            fence, column = (edge.group(1) if edge else ""), None
            continue
        opener = LIST_OPENER.match(line)
        if opener:
            # Колонка текста пункта. Больше четырёх пробелов после маркера — это уже
            # отступленный блок внутри пункта, и текст считается с первого пробела.
            spaces = len(opener.group(3))
            column = (len(opener.group(1)) + len(opener.group(2))
                      + (1 if spaces > 4 else spaces))
            continue
        if column is None:
            continue
        if OWN_BLOCK.match(line):
            column = None
            continue
        if len(line) - len(line.lstrip()) < column:
            glued.append(f"{i}: {line.strip()[:70]}")
    return glued


def _glued_lines(text: str) -> list[int]:
    """Номера строк, которые `_glued_to_list_item` называет приклеенными."""
    return [int(g.split(":", 1)[0]) for g in _glued_to_list_item(text)]


def scenario_count() -> int:
    """Сколько в наборе сценариев — тем числом, которое называют документы.

    Загрузчик СВОЙ, а не `defaultTestLoader`: тот несёт в себе образцы из `-k`, и под
    фильтром замер давал единицу. Число, которое зависит от способа запуска, — не замер, и
    сверять с ним публичное число нельзя.
    """
    return unittest.TestLoader().discover(str(KIT / "tests")).countTestCases()


def _ordinal_share(value: float) -> str:
    """0.10 → "tenth": доля, как её называют словом в английском тексте."""
    return {2: "half", 3: "third", 4: "quarter", 5: "fifth", 10: "tenth"}[round(1 / value)]


def _ordinal_share_ru(value: float) -> str:
    return {2: "половине", 3: "трети", 4: "четверти", 5: "пятой", 10: "десятой"}[round(1 / value)]


def _conflict_markers(text: str) -> list[int]:
    """Строки, с которых начинается незавершённое слияние: `<<<<<<< `, затем `=======`
    отдельной строкой (у diff3 перед ним ещё `||||||| `), затем `>>>>>>> `.

    Ищется ТРОЙКА в этом порядке, а не любая из строк: `=======` — законное подчёркивание
    заголовка в markdown (setext), и правило, звавшее конфликтом одну её, запретило бы
    обычную разметку. Возвращается строка открывающего маркера — с неё и читают.
    """
    found, opened, middle = [], None, False
    for i, line in enumerate(text.splitlines(), 1):
        line = line.rstrip("\r")
        if line.startswith("<<<<<<< ") or line == "<<<<<<<":
            opened, middle = i, False
        elif opened is None:
            continue
        elif line == "=======":
            middle = True
        elif middle and (line.startswith(">>>>>>> ") or line == ">>>>>>>"):
            found.append(opened)
            opened, middle = None, False
    return found


class ConflictMarkerTest(unittest.TestCase):
    """УЗДА КЛАССА «слияние, которое не доделали, прошло как сделанное».

    Прошлое слияние веток ревью занесло маркеры конфликта в README и AGENTS.md: git
    записывает их в файл как обычный текст, коммит их принимает, и ни одна проверка набора
    их не увидела — документ просто показывал обе версии числа сценариев сразу. Предмет
    правила берётся у git целиком, а не списком «файлов, где конфликтуют чаще»: конфликт
    случается там, где его не ждали.
    """

    def test_ни_в_одном_файле_нет_маркеров_конфликта(self):
        offenders, read, binary = [], set(), set()
        # Во время слияния индекс держит файл в трёх стадиях — и `ls-files` назовёт его трижды.
        every = set(tracked())
        for rel in sorted(every):
            data = (KIT / rel).read_bytes() if (KIT / rel).is_file() else b""
            if b"\0" in data:
                binary.add(rel)            # двоичный файл: маркеры git пишет только в текст
                continue
            read.add(rel)
            offenders += [f"{rel}:{n}" for n in
                          _conflict_markers(data.decode("utf-8", errors="replace"))]
        # Обход, оборвавшийся на первом двоичном файле, оставил бы непрочитанным всё, что
        # за ним, — и молчал бы о маркерах там. Измерено мутацией `continue` → `break`.
        self.assertEqual(sorted(every - read - binary), [],
                         "узда прочла не все файлы, которые отслеживает git")
        self.assertTrue(read, "узда не прочла ни одного файла")
        self.assertEqual(
            offenders, [],
            "в файле остались маркеры конфликта слияния: разрешите конфликт — оставьте одну "
            "из версий или соберите обе в одну — и уберите строки `<<<<<<<`, `=======`, "
            "`>>>>>>>`; git принимает их как обычный текст и не остановит")

    # Обе стороны правила, на текстах, которых в репозитории нет.
    CONFLICTS = {
        "обычный конфликт": ("a\n<<<<<<< HEAD\nours\n=======\ntheirs\n>>>>>>> side\nb\n", [2]),
        "конфликт diff3": ("<<<<<<< HEAD\no\n||||||| base\nb\n=======\nt\n>>>>>>> side\n", [1]),
        "два конфликта": ("<<<<<<< a\n=======\n>>>>>>> b\nx\n<<<<<<< a\n=======\n>>>>>>> b\n",
                          [1, 5]),
        "перевод строки Windows": ("<<<<<<< HEAD\r\no\r\n=======\r\nt\r\n>>>>>>> s\r\n", [1]),
    }
    INNOCENT = {
        "подчёркивание заголовка": "Title\n=======\n\ntext\n",
        "маркеры в прозе, не с начала строки": "git writes `<<<<<<< HEAD` and `>>>>>>> side`\n",
        "маркеры в строке кода": '    sample = "<<<<<<< HEAD\\n=======\\n>>>>>>> x"\n',
        "маркеры не в том порядке": ">>>>>>> side\n=======\n<<<<<<< HEAD\n",
        "открыт и не разделён": "<<<<<<< HEAD\nours\n>>>>>>> side\n",
    }

    def test_узда_видит_конфликт_и_не_видит_разметку(self):
        for why, (text, lines) in self.CONFLICTS.items():
            with self.subTest(конфликт=why):
                self.assertEqual(_conflict_markers(text), lines, "узда не увидела конфликт")
        for why, text in self.INNOCENT.items():
            with self.subTest(невиновный=why):
                self.assertEqual(_conflict_markers(text), [],
                                 "узда приняла за конфликт то, что им не является")


class RepositoryContractTest(unittest.TestCase):
    """УЗДЫ КЛАССА «документ обещает то, чего в репозитории нет».

    Документы — публичное лицо набора, и их никто не прогоняет: число сценариев
    отставало от настоящего втрое, `RELEASING.md` вёл к путям, которых нет с 0.4.0,
    шаблон обращения — в каталог, уехавший в закрытую базу знаний. Каждое такое
    утверждение либо держится прогоном, либо разъезжается с кодом молча.
    """

    def test_число_сценариев_в_документах_равно_настоящему(self):
        """README (обоих языков) и AGENTS.md называют число сценариев как доказательство
        того, что набор проверен. Число брали из головы: 98 против настоящих 248.

        Равенство, а не полоса. Полоса «не больше настоящего и не меньше девяти десятых»
        заводилась, чтобы не краснел каждый PR с новым тестом, — и вместе с этим разрешала
        публичному числу отставать навсегда: раунд закрылся с 270 в документах против 296 в
        прогоне, и это ровно то состояние, из-за которого читатель не может понять, что
        именно у него не так. Замер стоит одной правки в трёх файлах, и отказ её называет.
        """
        real = scenario_count()
        self.assertGreater(real, 0)
        # Русское число склоняет за собой существительное: 336 сценариЕВ, но 343
        # сценариЯ. Образец, знающий одну форму, требовал бы от документа неграмотности
        # или замолкал бы на числе, кончающемся на 2, 3, 4.
        for rel, pattern in (("README.md", r"(\d+) scenarios"),
                             ("README.ru.md", r"(\d+) сценари(?:ев|я|й)"),
                             ("AGENTS.md", r"(\d+) scenarios")):
            text = (KIT / rel).read_text(encoding="utf-8")
            found = re.findall(pattern, text)
            with self.subTest(файл=rel):
                self.assertTrue(found, f"{rel}: число сценариев не названо")
                for n in found:
                    self.assertEqual(
                        int(n), real,
                        f"{rel} называет {n} сценариев, а их {real}. Число сценариев — "
                        f"замер: прогоните `python3 -m unittest discover -s tests` и "
                        f"впишите {real} в README.md, README.ru.md и AGENTS.md")

    def test_замер_числа_сценариев_не_зависит_от_способа_запуска(self):
        """Обратная сторона точного равенства: замер обязан быть одним и тем же, как бы ни
        звали прогон. `defaultTestLoader` несёт образцы `-k` в себе, и под фильтром счёт
        давал единицу — с ним точное равенство было бы невыполнимо ни при каком числе в
        документах, а полоса молча сравнивала документ с отфильтрованным прогоном."""
        whole = scenario_count()
        self.assertGreater(whole, 1)
        saved = unittest.defaultTestLoader.testNamePatterns
        unittest.defaultTestLoader.testNamePatterns = ["*такого_теста_в_наборе_нет*"]
        try:
            self.assertEqual(scenario_count(), whole,
                             "замер числа сценариев зависит от образцов `-k`: считайте "
                             "своим загрузчиком, а не defaultTestLoader")
        finally:
            unittest.defaultTestLoader.testNamePatterns = saved

    # Порог, названный в публичном документе, обязан читаться из того же места, откуда его
    # берёт инструмент. Пары «константа → как она обязана звучать в тексте»: README описывал
    # порог общего узла твёрдой шестёркой, когда в коде давно доля с полом.
    CHANGELOGS = ("CHANGELOG.md", "CHANGELOG.ru.md")
    QUOTED_CONSTANTS = (
        ("COUPLING_MIN_TOGETHER", CHANGELOGS, lambda v: [f"≥ {int(v)}"]),
        ("COUPLING_MIN_SHARE", CHANGELOGS, lambda v: [f"{int(v * 100)}%", f"{int(v * 100)} %"]),
        ("COUPLING_MASS_PERCENTILE", ("README.md", "README.ru.md") + CHANGELOGS,
         lambda v: [f"{int(v)}th percentile", f"{int(v)}-го процентиля"]),
        ("COUPLING_HUB_FLOOR", ("README.md", "README.ru.md") + CHANGELOGS,
         lambda v: ["three", "трёх", "тремя"]),
        ("COUPLING_HUB_SHARE", ("README.md", "README.ru.md") + CHANGELOGS,
         lambda v: [f"a {_ordinal_share(v)}", f"{_ordinal_share_ru(v)} част"]),
    )

    def test_пороги_из_документов_читаются_из_кода(self):
        """УЗДА КОРНЯ «число в публичном документе не сверено с источником». Документы
        описывают отсечки `coupling` словами; если константа в коде изменится, а текст —
        нет, прогон краснеет. Каждый порог спрашивается у тех файлов, которые его
        называют: README говорит про отбор, CHANGELOG — про все пороги команды."""
        source = TOOL.read_text(encoding="utf-8")
        for name, files, wording in self.QUOTED_CONSTANTS:
            m = re.search(rf"^{name} = ([0-9.]+)$", source, re.M)
            self.assertTrue(m, f"{name} не найдена в инструменте")
            forms = wording(float(m.group(1)))
            for rel in files:
                text = (KIT / rel).read_text(encoding="utf-8")
                with self.subTest(константа=name, файл=rel):
                    self.assertTrue(any(f in text for f in forms),
                                    f"{rel} не описывает {name} = {m.group(1)} "
                                    f"(ожидалось одно из {forms})")

    # Команда, которую документ велит гонять, обязана гоняться в CI: иначе правило
    # объявлено обязательным, а держит его честное слово автора предложения.
    GATE_BLOCKS = ("CONTRIBUTING.md",)

    @classmethod
    def _declared_gates(cls) -> list[str]:
        """Команды из `sh`-блоков документов, которые велят их гонять."""
        commands = []
        for rel in cls.GATE_BLOCKS:
            text = (KIT / rel).read_text(encoding="utf-8")
            for block in re.findall(r"```sh\n(.*?)```", text, re.S):
                for line in block.splitlines():
                    line = re.sub(r"\s+#.*$", "", line).strip()
                    if line:
                        commands.append(line)
        return commands

    @staticmethod
    def _workflow_steps_of_repository() -> list[str]:
        return _workflow_steps("\n".join(
            p.read_text(encoding="utf-8")
            for p in sorted((KIT / ".github" / "workflows").glob("*.yml"))))

    def test_каждые_объявленные_ворота_гоняет_ci(self):
        """УЗДА КОРНЯ «правило объявлено обязательным, и не держит его ничто». Прогон
        тестов, валидатор скилла и подпись DCO названы в CONTRIBUTING как обязательные;
        до этой узды подпись не проверял никто.

        Сверяется ШАГ процесса, а не текст файла: пока узда искала два слова команды где
        угодно в процессах, `python3` находился в шаге установки валидатора, а `tests` — в
        имени процесса, и удалить из CI и шаг с прогоном тестов, и весь его job можно было,
        не покраснев (измерено оба раза).
        """
        commands = self._declared_gates()
        self.assertTrue(commands, "в CONTRIBUTING не нашлось ни одной команды ворот")
        steps = self._workflow_steps_of_repository()
        self.assertTrue(steps, "в рабочих процессах не нашлось ни одного шага `run:`")
        self.assertEqual(
            _gates_not_run(commands, steps), [],
            "CONTRIBUTING велит гонять эти команды, а ни один шаг рабочего процесса их не "
            "гоняет: правило объявлено обязательным, и держит его честное слово автора")

    # Обе стороны правила — на процессе, которого в репозитории нет. Соответствие по двум
    # словам где угодно ловило ровно то, чего не бывает: пока правило было таким, оба
    # нарушения ниже проходили зелёными.
    INVENTED_WORKFLOW = """name: tests
jobs:
  unittest:
    steps:
      - uses: actions/checkout@abc
      - name: Run the tests
        run: python3 -m unittest discover -s tests -v
  skill:
    steps:
      - name: Validate the skill format
        run: |
          python3 -m venv "$RUNNER_TEMP/skills-ref"
          "$RUNNER_TEMP/skills-ref/bin/skills-ref" validate skills/finetooth
  dco:
    steps:
      - run: .github/dco.sh ${{ github.event.pull_request.base.sha }}..${{ github.sha }}
"""
    INVENTED_GATES = ("python3 -m unittest discover -s tests",
                      "skills-ref validate skills/finetooth",
                      ".github/dco.sh origin/dev..HEAD")

    def test_узда_видит_ворота_которых_ci_не_гоняет(self):
        """Нарушение обязано ронять прогон, а честный процесс — проходить: команда
        названа шагом по-своему (валидатор из venv, диапазон из события, лишний `-v`) и
        всё равно засчитывается."""
        whole = _workflow_steps(self.INVENTED_WORKFLOW)
        self.assertEqual(_gates_not_run(list(self.INVENTED_GATES), whole), [],
                         "узда придирается к процессу, который команды гоняет")
        without_step = self.INVENTED_WORKFLOW.replace(
            "        run: python3 -m unittest discover -s tests -v\n", "")
        self.assertEqual(
            _gates_not_run(list(self.INVENTED_GATES), _workflow_steps(without_step)),
            [self.INVENTED_GATES[0]], "узда не увидела удалённый шаг с прогоном тестов")
        stubbed = self.INVENTED_WORKFLOW.replace(
            '"$RUNNER_TEMP/skills-ref/bin/skills-ref" validate skills/finetooth', "true")
        self.assertEqual(
            _gates_not_run(list(self.INVENTED_GATES), _workflow_steps(stubbed)),
            [self.INVENTED_GATES[1]], "узда не увидела подменённый валидатор")

    # Ворота, оставшиеся на месте и обезвреженные: шаг зовёт ту же программу с теми же
    # доводами, а красным стать уже не может. Каждая форма измерена зелёной на правиле,
    # которое разрешало шагу быть любым, лишь бы доводы документа в нём нашлись.
    NEUTRALISED_STEPS = {
        "код возврата не доходит до CI":
            ("python3 -m unittest discover -s tests", "python3 -m unittest discover -s tests || true"),
        "прогон сужен образцом":
            ("python3 -m unittest discover -s tests",
             "python3 -m unittest discover -s tests -k НетТакогоТеста"),
        "свой диапазон вместо подставленного":
            (".github/dco.sh origin/dev..HEAD", ".github/dco.sh HEAD~1..HEAD"),
    }
    # Обратная сторона: шаг вправе называть команду по-своему, и это не обезвреживание.
    HONEST_STEPS = {
        "громче, но не уже":
            ("python3 -m unittest discover -s tests", "python3 -m unittest discover -s tests -v"),
        "программа из venv":
            ("skills-ref validate skills/finetooth",
             '"$RUNNER_TEMP/skills-ref/bin/skills-ref" validate skills/finetooth'),
        "диапазон из события":
            (".github/dco.sh origin/dev..HEAD",
             ".github/dco.sh ${{ github.event.pull_request.base.sha }}..${{ github.sha }}"),
        "диапазон слово в слово":
            (".github/dco.sh origin/dev..HEAD", ".github/dco.sh origin/dev..HEAD"),
    }

    def test_узда_видит_обезвреженные_ворота(self):
        """Ворота, которые нельзя уронить, — не ворота, даже если шаг с ними на месте.
        `|| true` уносит код возврата мимо CI, `-k НетТакогоТеста` гоняет ноль тестов,
        `HEAD~1..HEAD` проверяет один коммит вместо всех коммитов предложения."""
        for why, (cmd, step) in self.NEUTRALISED_STEPS.items():
            with self.subTest(обезврежено=why):
                self.assertFalse(_runs_command(cmd, step),
                                 f"{step!r} засчитан как прогон `{cmd}`")
        for why, (cmd, step) in self.HONEST_STEPS.items():
            with self.subTest(честный=why):
                self.assertTrue(_runs_command(cmd, step),
                                f"{step!r} не засчитан как прогон `{cmd}`")

    READMES = ("README.md", "README.ru.md")
    _tracked = staticmethod(tracked)
    # Отчёты ревью, которые репозиторий хранит, но не пишет сам: реестр `docs/review/`
    # (сносится вместе с ревью) и корпус вердиктов — те же отчёты T1 ДОСЛОВНО, на которых
    # заморожен разборщик (`expected.json`); поправить в них разметку значит сдвинуть его
    # вход. Правила о публикуемых документах обходят оба места одним списком.
    VERBATIM_REPORTS = (":(exclude)docs/review/", ":(exclude)tests/corpus/verdicts/finetooth/")

    def test_опись_набора_называет_все_команды(self):
        """Раздел «Что внутри» — единственное место, где репозиторий перечисляет сам себя;
        по нему пишут цели make и решают, что именно ставится. Он перечислял 19 команд из
        23, и `refs` не упоминался в README ни разу — значит, его никто не запускал."""
        helped = subprocess.run([sys.executable, str(TOOL), "--help"],
                                capture_output=True, text=True, env=child_env()).stdout
        names = re.search(r"\{([a-z0-9,\-]{20,})\}", helped.replace("\n", ""))
        self.assertTrue(names, helped)
        commands = names.group(1).split(",")
        for rel in self.READMES:
            text = (KIT / rel).read_text(encoding="utf-8")
            missing = [c for c in commands if not re.search(rf"(?<![\w-]){re.escape(c)}(?![\w-])", text)]
            with self.subTest(файл=rel):
                self.assertEqual(missing, [], f"{rel} не называет команды: {missing}")

    def test_у_каждой_версии_в_истории_есть_ссылка_на_сравнение(self):
        """RELEASING, ворота 4: ссылка на сравнение ставится до тега. У 0.5.1, 0.5.0 и
        0.4.1 её не было, и заголовки этих версий печатались как текст в квадратных
        скобках — как раз у тех выпусков, чей дифф читать и хотелось бы."""
        for rel in ("CHANGELOG.md", "CHANGELOG.ru.md"):
            text = (KIT / rel).read_text(encoding="utf-8")
            headings = re.findall(r"^## \[([^\]]+)\]", text, re.M)
            defined = set(re.findall(r"^\[([^\]]+)\]:\s*\S+", text, re.M))
            self.assertTrue(headings, rel)
            with self.subTest(файл=rel):
                self.assertEqual([h for h in headings if h not in defined], [],
                                 f"{rel}: версии без ссылки на сравнение")

    # Строка, идущая сразу за пунктом списка без пустой строки, в CommonMark — ленивое
    # продолжение этого пункта, а не новый абзац. Правило одно на весь файл —
    # `_glued_to_list_item`; оба прохода ниже (T2 и T4 нашли один и тот же дефект с двух
    # сторон) и обе пары образцов держат ОДНУ функцию, чтобы их знание не разъехалось.
    def test_ни_один_абзац_не_приклеен_к_предыдущему_пункту_списка(self):
        # Отчёты самого ревью сюда не входят (`VERBATIM_REPORTS`): их пишут агенты, а
        # правило — о документах, которые репозиторий публикует.
        swallowed = []
        for rel in self._tracked("*.md", *self.VERBATIM_REPORTS):
            lines = (KIT / rel).read_text(encoding="utf-8").split("\n")
            swallowed += [f"{rel}:{n}: {lines[n - 1][:60]}"
                          for n in _glued_lines("\n".join(lines))]
        self.assertEqual(swallowed, [],
                         "абзац идёт сразу за пунктом списка, без пустой строки между ними, "
                         "и разметка делает его продолжением этого пункта — вставьте пустую "
                         "строку: " + "; ".join(swallowed))

    # Обе стороны правила на документах, которых в репозитории нет: склеенным считается
    # только то, что разметка действительно вносит в пункт.
    GLUED = {
        "абзац за пунктом": "- пункт списка\nВводный абзац раздела\n",
        "абзац за нумерованным пунктом": "1. пункт списка\nВводный абзац раздела\n",
    }
    NOT_GLUED = {
        "заголовок обрывает список": "- пункт списка\n## Заголовок раздела\n",
        "тематический разрыв": "- пункт списка\n---\n",
        "html-блок": "- пункт списка\n<div>врезка</div>\n",
        "ограда кода": "- пункт списка\n```sh\nmake test\n```\n",
        "продолжение с отступом": "- пункт списка\n  продолжение пункта\n",
        "цитата": "- пункт списка\n> цитата\n",
        "следующий пункт": "- пункт списка\n- следующий пункт\n",
        "пустая строка между ними": "- пункт списка\n\nОтдельный абзац\n",
        "пример внутри ограды": "```md\n- пункт списка\nабзац примера\n```\n",
    }

    def test_правило_про_склеенный_абзац_читается_на_выдуманном_документе(self):
        """Правило запрещает — значит, проверено и то, что оно ПРОПУСКАЕТ: заголовок,
        разрыв и html-блок сразу за пунктом список обрывают и рисуются как написаны, а
        запрет на них выгонял бы автора править верную разметку."""
        for why, text in self.GLUED.items():
            with self.subTest(склеено=why):
                self.assertEqual(_glued_lines(text), [2],
                                 "правило не увидело абзаца, приклеенного к пункту")
        for why, text in self.NOT_GLUED.items():
            with self.subTest(невиновный=why):
                self.assertEqual(_glued_lines(text), [],
                                 "правило придирается к верной разметке")

    def test_в_документах_нет_абзаца_приклеенного_к_пункту_списка(self):
        """Заметки о выпуске берут раздел «Unreleased» как есть (RELEASING, ворота 4), а
        абзац, стоящий вплотную под пунктом списка, по правилам markdown становится частью
        пункта. Так вводный абзац блока T2 оказался внутри записи про `NOTICE.md`, и
        пятнадцать пунктов блока пришли под заголовком, которого в разметке нет —
        одинаково в обоих языках. Список документов берётся у git: новый документ
        попадает под правило сам.

        Не корнем единым: шаблоны ролей — нумерованные списки правил, по которым работает
        агент, и абзац, уехавший внутрь правила 4, меняет смысл ровно так же. Вне правила
        остаются только отчёты ревью (`VERBATIM_REPORTS`): `docs/review/` — аппарат,
        который сносится вместе с ревью, и дословные отчёты корпуса вердиктов, — их не
        переписывают."""
        for rel in self._tracked("*.md", *self.VERBATIM_REPORTS):
            with self.subTest(файл=rel):
                self.assertEqual(
                    _glued_to_list_item((KIT / rel).read_text(encoding="utf-8")), [],
                    f"{rel}: абзац приклеен к пункту списка — отбейте его пустой строкой, "
                    f"иначе разметка считает его продолжением пункта")

    # Обе стороны правила, на разметке, которой в документах нет.
    GLUED_SHAPES = {
        "абзац вплотную под пунктом": "- пункт\nАбзац.\n",
        "абзац под вложенным пунктом": "- пункт\n  - вложенный\nАбзац.\n",
        # Нумерованный пункт правило не знало вовсе, а `RELEASING.md` — нумерованная
        # процедура целиком; отступ меньше колонки текста пункт проглатывает так же, как
        # его отсутствие, и абзац после законного продолжения — тоже часть пункта.
        "абзац под нумерованным пунктом": "1. пункт\nАбзац.\n",
        "абзац под пунктом со скобкой": "1) пункт\nАбзац.\n",
        "отступ меньше колонки текста пункта": "- пункт\n Абзац.\n",
        "абзац после продолжения пункта": "- пункт\n  продолжение.\nАбзац.\n",
        # Ни определение ссылки, ни строка таблицы абзац не прерывают: под пунктом они —
        # его продолжение, и ссылка сравнения версий перестаёт быть ссылкой.
        "определение ссылки под пунктом": "- пункт\n[0.6.0]: https://example.com\n",
        "строка таблицы под пунктом": "- пункт\n| а | б |\n",
    }
    NOT_GLUED_SHAPES = {
        "абзац отбит пустой строкой": "- пункт\n\nАбзац.\n",
        "продолжение с отступом": "- пункт\n  продолжение.\n",
        "продолжение нумерованного пункта": "1. пункт\n   продолжение.\n",
        "следующий пункт": "- пункт\n- другой пункт\n",
        "следующий нумерованный пункт": "1. пункт\n2. другой пункт\n",
        "заголовок": "- пункт\n## Раздел\n",
        "горизонтальная черта": "- пункт\n---\n",
        "пункт внутри ограды": "```\n- пункт\nтекст\n```\n",
        "абзац после пустой строки за продолжением": "- пункт\n  продолжение.\n\nАбзац.\n",
    }

    def test_узда_видит_абзац_приклеенный_к_пункту(self):
        for why, src in self.GLUED_SHAPES.items():
            with self.subTest(разметка=why):
                self.assertNotEqual(_glued_to_list_item(src), [],
                                    "узда не увидела приклеенный абзац")
        for why, src in self.NOT_GLUED_SHAPES.items():
            with self.subTest(невиновный=why):
                self.assertEqual(_glued_to_list_item(src), [],
                                 "узда придирается к верной разметке")

    # Пары «оригинал — перевод»: обе половины обязаны вести друг на друга с первой строки.
    BILINGUAL = ("README", "CHANGELOG", "CODE_OF_CONDUCT")

    def test_у_двуязычных_файлов_ссылка_друг_на_друга_в_первой_строке(self):
        """0.7.0 обещал, что русские копии «связаны ссылкой в шапке каждого файла». У обоих
        кодексов поведения ссылки не было ни в одну сторону, а CODE_OF_CONDUCT.md — тот
        файл, который GitHub показывает в профиле сообщества: перевод существовал и был
        никому не виден."""
        for stem in self.BILINGUAL:
            en, ru = KIT / f"{stem}.md", KIT / f"{stem}.ru.md"
            self.assertTrue(ru.exists(), ru)
            for src, target in ((en, ru.name), (ru, en.name)):
                head = "\n".join(src.read_text(encoding="utf-8").splitlines()[:3])
                with self.subTest(файл=src.name):
                    self.assertIn(f"]({target})", head,
                                  f"{src.name}: в шапке нет ссылки на {target}")

    # Документы, которые говорят «сделай вот это сейчас»: процедура выпуска и шаблоны, по
    # которым пишет человек со стороны. CHANGELOG сюда не входит — он про то, что было.
    LIVE_GUIDANCE = ("RELEASING.md", ".github/PULL_REQUEST_TEMPLATE.md",
                     ".github/ISSUE_TEMPLATE/bug.yml", ".github/ISSUE_TEMPLATE/proposal.yml",
                     ".github/ISSUE_TEMPLATE/trophy.yml", ".github/ISSUE_TEMPLATE/config.yml")
    # Путь — то, в чём есть косая черта: голое имя (`blocks.json`, `SKILL.md`) документы
    # называют по-свойски, и оно не обязано лежать в корне.
    PATH_IN_TEXT = re.compile(
        r"(?<![\w/.-])((?:[\w.-]+/)+[\w.-]+\.(?:md|py|sh|json|yml|tsv|jsonl|mk))(?![\w/-])")

    def test_живое_руководство_ведёт_на_существующие_пути(self):
        """Шаг 2 выпуска вёл на `scripts/review.py`, которого нет с 0.4.0, а шаблон
        предложения — на `docs/prior-art.md`, уехавший в закрытую базу знаний: человек со
        стороны либо застревает, либо заводит файл заново рядом с настоящим."""
        missing = []
        for rel in self.LIVE_GUIDANCE:
            f = KIT / rel
            self.assertTrue(f.exists(), rel)
            for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
                for tok in self.PATH_IN_TEXT.findall(line):
                    if not (KIT / tok).exists():
                        missing.append(f"{rel}:{n} {tok}")
        self.assertEqual(missing, [], "руководство ведёт на путь, которого в репозитории нет")

    def test_действия_ci_закреплены_коммитом(self):
        """Подвижный тег — чужой код в шаге, который распоряжается рабочим деревом, а
        зелёный CI — то, что защита ветки требует перед слиянием в `master`. `stale.yml`
        и установка `skills-ref` закреплены давно; `actions/checkout` ехал по `v5`."""
        loose = []
        for wf in sorted((KIT / ".github" / "workflows").glob("*.yml")):
            for n, line in enumerate(wf.read_text(encoding="utf-8").splitlines(), 1):
                m = re.search(r"uses:\s*(\S+)", line)
                if m and not re.search(r"@[0-9a-f]{40}\b", m.group(1)):
                    loose.append(f"{wf.name}:{n} {m.group(1)}")
        self.assertEqual(loose, [], "действие CI не закреплено коммитом")

    def test_версии_python_из_шапки_скилла_прогоняются_в_ci(self):
        """`compatibility` в SKILL.md — то, на что смотрит команда, решая, ставить ли набор.
        Пока в рабочем процессе не было `setup-python`, обе названные версии держались на
        слове: суите доставался тот python3, который принёс образ раннера."""
        head = (SKILL / "SKILL.md").read_text(encoding="utf-8").split("---\n", 2)[1]
        claimed = set(re.findall(r"\b(\d+\.\d+)\b",
                                 re.search(r"^compatibility:.*$", head, re.M).group(0)))
        wf = (KIT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
        matrix = re.search(r"python-version:\s*\[([^\]]+)\]", wf)
        self.assertTrue(matrix, "в рабочем процессе нет набора версий python")
        run = set(re.findall(r"\d+\.\d+", matrix.group(1)))
        self.assertEqual(claimed, run,
                         f"SKILL.md обещает {sorted(claimed)}, CI гоняет {sorted(run)}")

    def test_в_github_нет_кириллицы(self):
        """AGENTS.md, правило 7: содержимое по-английски, русское — только в копиях
        `.ru.md`. Имена шагов и комментарии рабочего процесса были по-русски, а это то,
        что видит в панели проверок автор предложения со стороны."""
        offenders = []
        for p in sorted((KIT / ".github").rglob("*")):
            if not p.is_file() or p.suffix in (".png", ".jpg", ".ico"):
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
            if re.search(r"[А-Яа-яЁё]", text):
                offenders.append(p.relative_to(KIT).as_posix())
        self.assertEqual(offenders, [], "кириллица в .github/ — там нет двуязычных копий")

    def test_опись_набора_называет_все_файлы_скилла_и_корня(self):
        """Ставится папка скилла целиком — значит, названа она целиком; корневые файлы
        читает тот, кто пришёл со стороны. Десять русских шаблонов, `axes.py` и
        `run-role.sh` (два файла, пишущие вне репозитория) в описи не значились."""
        files = [Path(p).name for p in self._tracked("skills/finetooth")]
        files += [p for p in self._tracked() if "/" not in p]
        for rel in self.READMES:
            text = (KIT / rel).read_text(encoding="utf-8")
            missing = sorted({f for f in files if f not in text})
            with self.subTest(файл=rel):
                self.assertEqual(missing, [], f"{rel} не называет файлы: {missing}")


class SourceRuleTest(unittest.TestCase):
    """Узды классов, которые проще держать правилом по исходнику, чем списком мест."""

    SOURCE = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.SOURCE = TOOL.read_text(encoding="utf-8")

    # Единственная функция инструмента, которой позволено запускать процесс. Всё, что
    # нужно знать о чтении git — репозиторий, `-z` там, где в выводе пути, разбор этого
    # вывода, — живёт внутри неё; поэтому вопрос «попросили ли `-z`» задаётся одному месту,
    # а не каждой сборке argv по отдельности.
    GIT_HELPER = "git"
    # Как запускают процесс: способ узнаётся по тому, ЧТО зовут, а не по тому, как написали.
    SPAWNERS = ("run", "Popen", "call", "check_output", "check_call")
    OS_SPAWNERS = ("system", "popen", "execv", "execve", "execvp", "execl", "execlp",
                   "spawnv", "spawnve", "spawnl", "spawnlp", "posix_spawn")

    @classmethod
    def _spawns_outside_git(cls, source: str) -> list[str]:
        """Функции инструмента, которые запускают процесс сами, мимо помощника.

        Три круга подряд правило спрашивало у СБОРКИ argv, попросили ли у git `-z`, и
        каждый круг находилась форма записи, которой оно не видело: приставка, вынесенная
        в константу; argv, накопленный `extend`; argv, собранный обёрткой `_git(*rest)`.
        Форм записи всегда на одну больше, чем вообразил автор правила.

        Поэтому спрашивается не форма, а факт: процесс запускают в одном месте, и `-z`
        добавляет оно же. Argv можно собирать как угодно — хоть обёрткой, хоть по частям, —
        потому что дойти до git он может только через помощника.
        """
        vals = _Values(source)
        tree = vals.tree
        # За чем стоит сам модуль запуска и за чем — втянутые из него имена.
        modules, imported = {"subprocess"}, set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules |= {a.asname or a.name for a in node.names if a.name == "subprocess"}
            elif isinstance(node, ast.ImportFrom) and node.module == "subprocess":
                imported |= {a.asname or a.name for a in node.names if a.name in cls.SPAWNERS}
        offenders = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            by_module = (isinstance(node.func, ast.Attribute)
                         and isinstance(node.func.value, ast.Name)
                         and ((node.func.value.id in modules and node.func.attr in cls.SPAWNERS)
                              or (node.func.value.id == "os"
                                  and node.func.attr in cls.OS_SPAWNERS)))
            by_name = (isinstance(node.func, ast.Name) and node.func.id in imported
                       and not vals.lookup(node.func.id, vals.scope_of(node)))
            if not (by_module or by_name):
                continue
            where = getattr(vals.scope_of(node), "name", "модуль")
            if where != cls.GIT_HELPER:
                offenders.add(where)
        return sorted(offenders)

    def test_процесс_запускают_в_одном_месте(self):
        """УЗДА КЛАССА «вывод git разобран как обычный текст».

        Три места разбирали список путей построчно: не-ASCII путь приходит оттуда
        экранированным (`"src/\\320\\272…"`) и не совпадает ни с чем, а переименование
        печатается одним новым именем. `-z` просит один помощник за всех, и держится это
        не перечислением форм записи argv, а тем, что запуск процесса в инструменте
        ровно один.
        """
        self.assertEqual(
            self._spawns_outside_git(self.SOURCE), [],
            f"процесс запускают мимо `{self.GIT_HELPER}()`: тогда argv собирают на месте, "
            f"а вместе с ним и `-z` — зовите помощника")

    # Обе стороны правила на исходниках, которых в инструменте нет. Первые две — те самые
    # формы, на которых слепло правило по сборке argv.
    OUTSIDE_SPAWNS = {
        "argv накоплен методом":
            'def untracked_files(specs):\n'
            '    cmd = ["git", "-C", str(ROOT)]\n'
            '    cmd.extend(["ls-files", "--others", "--", *specs])\n'
            '    return subprocess.run(cmd, capture_output=True, text=True).stdout.splitlines()\n',
        "argv собран обёрткой":
            'def _git(*rest):\n'
            '    return ["git", "-C", str(ROOT), *rest]\n\n'
            'def index_rows(specs):\n'
            '    out = subprocess.run(_git("ls-files", "--stage"), capture_output=True,\n'
            '                         text=True)\n'
            '    return out.stdout.splitlines()\n',
        "модуль под псевдонимом":
            'import subprocess as sp\n\n'
            'def churn():\n'
            '    return sp.check_output(["git", "log", "--name-only"])\n',
        "имя втянуто из модуля":
            'from subprocess import run\n\n'
            'def churn():\n'
            '    return run(["git", "log", "--name-only"], capture_output=True)\n',
        "мимо subprocess вообще":
            'def churn():\n'
            '    return os.popen("git log --name-only").read()\n',
    }
    INSIDE_HELPER = {
        "помощник запускает":
            'def git(*args, binary=False):\n'
            '    argv = ["git", "-C", str(ROOT), *args]\n'
            '    return subprocess.run(argv, capture_output=True, text=not binary)\n',
        "argv по частям, но запуск в помощнике":
            'def _git(*rest):\n'
            '    return ["git", "-C", str(ROOT), *rest]\n\n'
            'def git(*args):\n'
            '    argv = _git(*args)\n'
            '    argv.extend(["--"])\n'
            '    return subprocess.run(argv, capture_output=True, text=True)\n\n'
            'def index_rows(specs):\n'
            '    return git("ls-files", "--stage").fields\n',
        "своё имя run в другой роли":
            'def run(cmd):\n'
            '    return cmd\n\n'
            'def index_rows(specs):\n'
            '    return run(["git", "ls-files"])\n',
    }

    def test_узда_видит_запуск_мимо_помощника(self):
        """Обе стороны: запуск мимо помощника роняет прогон в любой форме записи, а сборка
        argv по частям и сам помощник — нет."""
        for how, src in self.OUTSIDE_SPAWNS.items():
            with self.subTest(запуск=how):
                self.assertNotEqual(self._spawns_outside_git(src), [],
                                    "узда не увидела запуск мимо помощника")
        for how, src in self.INSIDE_HELPER.items():
            with self.subTest(невиновный=how):
                self.assertEqual(self._spawns_outside_git(src), [],
                                 "узда придирается к верной записи")

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

    # Единственный читатель потока `git log` в инструменте: он же и единственный, кто этот
    # поток заказывает, — маркер записи ставит он сам.
    LOG_READER = "log_records"

    @classmethod
    def _log_stream_outside_reader(cls, source: str) -> list[str]:
        """Функции, которые сами заказывают или сами разбирают поток `git log`.

        Ловушка не видна с места вызова: git завершает строку `--format` своим переводом
        строки, и `-z` оставляет его приклеенным к ПЕРВОМУ пути коммита. Два разборщика
        знали об этом порознь, и тот, что не знал, считал файл под двумя именами.

        Прежнее правило разрешало ПОСТАНОВКУ маркера в `--format=` где угодно и запрещало
        чтение — и на том различении теряло разбор, написанный в одном выражении с форматом.
        Различать больше нечего: формат ставит сам читатель, поток заказывает он же, и
        маркера за его пределами быть не может — ни в постановке, ни в чтении.
        """
        vals = _Values(source)
        offenders = set()
        for n in ast.walk(vals.tree):
            where = getattr(vals.scope_of(n), "name", "модуль")
            if where == cls.LOG_READER:
                continue
            # Само объявление маркера — не чтение: смотрим туда, где его БЕРУТ.
            if (isinstance(n, ast.Name) and n.id == "LOG_MARK"
                    and isinstance(n.ctx, ast.Load)):
                offenders.add(f"{where}: маркер записи мимо {cls.LOG_READER}()")
            if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                    and n.func.id == cls.GIT_HELPER and n.args
                    and isinstance(n.args[0], ast.Constant) and n.args[0].value == "log"):
                offenders.add(f"{where}: свой запуск `git log`")
        return sorted(offenders)

    def test_поток_истории_заказывает_и_разбирает_одно_место(self):
        """УЗДА КЛАССА «поток `git log` разобран своими руками».

        Второй разбор потока — это второе представление о том, где заканчивается запись
        коммита, и в прошлый раз оно разошлось с первым молча. Заказ потока и его разбор
        живут в одной функции, и взять помеченный поток больше негде.
        """
        self.assertEqual(self._log_stream_outside_reader(self.SOURCE), [],
                         f"свой поток или свой разбор истории — зовите {self.LOG_READER}()")

    # Обе стороны правила на исходниках, которых в инструменте нет. Первый — та самая
    # сжатая форма, которую прежнее правило пропускало: разбор в одном выражении с форматом.
    OWN_LOG_PARSERS = {
        "разбор в одном выражении с форматом":
            'def churn(root):\n'
            '    return git("log", f"--format={LOG_MARK}%H", "--name-only").out.split(LOG_MARK)\n',
        "разбор отдельным оператором":
            'def churn(out):\n'
            '    for rec in out.split(LOG_MARK):\n'
            '        yield rec\n',
        "свой заказ потока без маркера":
            'def churn(root):\n'
            '    return git("log", "--name-only", "--first-parent").fields\n',
    }
    LOG_READER_ONLY = {
        "читатель заказывает и разбирает сам":
            'def log_records(*args):\n'
            '    out = git("log", f"--format={LOG_MARK}%H", *args)\n'
            '    return [t for t in out.fields if t.startswith(LOG_MARK)]\n\n'
            'def churn(paths):\n'
            '    return log_records("--name-only", "--", *paths)\n',
        "соседняя команда git не история":
            'def touched(commit):\n'
            '    return git("show", "--name-only", "--format=", commit).fields\n',
    }

    def test_узда_видит_свой_разбор_истории_которого_ещё_нет(self):
        for how, src in self.OWN_LOG_PARSERS.items():
            with self.subTest(разбор=how):
                self.assertNotEqual(self._log_stream_outside_reader(src), [],
                                    "узда не увидела своего разбора истории")
        for how, src in self.LOG_READER_ONLY.items():
            with self.subTest(невиновный=how):
                self.assertEqual(self._log_stream_outside_reader(src), [],
                                 "узда придирается к верной записи")

    @staticmethod
    def _bare_numbers(source: str) -> list[str]:
        """Пороги без источника: имена присваиваний, в которых есть число, а над ними нет
        ни слова о том, откуда оно взялось.

        Число ищется В ЛЮБОМ выражении, а не только в готовой константе: `6 * 1000` —
        естественная запись выведенного предела, а `A_MAX, B_MAX = 12, 34` — обычная
        запись пары, заведённой разом. Пока правило смотрело только на
        `ИМЯ = <константа>`, обе формы проходили мимо него — измерено.

        Порог ищется во ВСЁМ модуле, а не в его верхнем уровне: константа, переехавшая
        внутрь единственной функции, которая ей пользуется, объяснения требует ровно
        того же.
        """
        lines = source.splitlines()
        bare = []
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Assign):
                targets = node.targets
            elif isinstance(node, ast.AnnAssign):
                targets = [node.target]
            else:
                continue
            names = [e.id for t in targets
                     for e in (t.elts if isinstance(t, ast.Tuple) else [t])
                     if isinstance(e, ast.Name)]
            if not names or not all(n.isupper() for n in names):
                continue
            if node.value is None or not any(
                    isinstance(n, ast.Constant) and isinstance(n.value, (int, float))
                    and not isinstance(n.value, bool) for n in ast.walk(node.value)):
                continue
            # комментарий может стоять над группой констант, а не над каждой
            i = node.lineno - 2
            while i >= 0 and re.match(r"^[A-Z_][A-Z_0-9, ]*\s*[:=]", lines[i].lstrip()):
                i -= 1
            if i < 0 or not lines[i].lstrip().startswith("#"):
                bare += names
        return bare

    # УЗДА КЛАССА «узда, написанная под одну форму записи».
    #
    # Правило по исходнику видит ровно то, что уже написано, и три узды подряд пропустили
    # правдоподобную форму, которой в инструменте нет. Доказывается такое правило только
    # мутацией настоящего исходника (SOURCE_MUTATIONS ниже), поэтому каждое обязано в той
    # таблице быть. Прежде правило-по-исходнику узнавалось по тому, чем его КОРМЯТ — по трём
    # строкам-маркерам в аргументе, — и правило, которому инструмент подали путём
    # (`(SKILL / "scripts" / "review.py").read_text()`), в таблицу не просилось вовсе.
    # Кормить можно как угодно; узнаётся правило по тому, что оно ДЕЛАЕТ: превращает текст
    # в дерево. Ищется это вызовом, а не поиском строки в тексте функции: иначе выдуманный
    # образец, лежащий в тесте строкой, сам сходил бы за правило.
    PARSE_CALLS = ("ast.parse", "_Values")
    # Откуда начинается поиск: приговор набора выносят тесты и то, что для них готовят.
    RULE_ENTRIES = ("test_", "setUp", "setUpClass", "setUpModule")
    # Второй предмет таких правил — ФАЙЛ РЕПОЗИТОРИЯ (процесс CI, документ, скрипт). Правило
    # про рабочий процесс CI сверяло команду по двум словам где угодно в его тексте и
    # оставалось зелёным, когда из CI удаляли весь прогон тестов: та же болезнь, только
    # предмет — документ, а не код. В дерево такое правило текст не превращает, и по
    # PARSE_CALLS его не узнать; узнаётся оно по тому, что ему отдают ПРОЧИТАННЫЙ ФАЙЛ, и
    # обязано хоть где-то получить выдуманный образец — обе стороны, нарушение и невиновный.
    FILE_READS = ("read_text", "read_bytes")

    @classmethod
    def _rules_without_tables(cls, source: str) -> tuple[list[str], list[str]]:
        """(правила прямо в тесте; правила по исходнику — те, чей приговор доходит до теста).

        Правило — это первая разбирающая исходник функция на пути от теста: глубже искать
        нечего, потому что помощники правила доказываются вместе с ним. Написанное прямо в
        тесте правилом не считается — его нечем покормить, кроме уже написанного кода, и это
        отдельная жалоба.
        """
        tree = ast.parse(source)
        funcs: dict[str, list] = {}
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                funcs.setdefault(node.name, []).append(node)

        def called_in(name: str) -> list:
            return [node.func for fn in funcs.get(name, [])
                    for node in ast.walk(fn) if isinstance(node, ast.Call)]

        def parses(name: str) -> bool:
            return any(f"{f.value.id}.{f.attr}" in cls.PARSE_CALLS
                       if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name)
                       else getattr(f, "id", "") in cls.PARSE_CALLS
                       for f in called_in(name))

        def calls(name: str) -> set[str]:
            out = {f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
                   for f in called_in(name)}
            return out & set(funcs)

        entries = [name for name in funcs if name.startswith(cls.RULE_ENTRIES)]
        inline = sorted({name for name in entries
                         if name.startswith("test_") and parses(name)})
        rules, seen, queue = set(), set(entries), list(entries)
        while queue:
            for called in calls(queue.pop()) - seen:
                seen.add(called)
                if parses(called):
                    rules.add(called)          # правило: дальше по этому пути не идём
                else:
                    queue.append(called)
        return inline, sorted(rules)

    def test_каждое_правило_по_исходнику_доказано_таблицей(self):
        """УЗДА КЛАССА «узда, написанная под одну форму записи»."""
        inline, rules = self._rules_without_tables(
            Path(__file__).read_text(encoding="utf-8"))
        self.assertEqual(
            inline, [],
            "правило по исходнику написано прямо в тесте: вынесите его в функцию, иначе "
            "его нечем покормить, кроме уже написанного кода, и мутацией оно не доказано")
        missing = sorted(set(rules) - set(SOURCE_MUTATIONS))
        self.assertEqual(
            missing, [],
            "правило по исходнику без таблицы мутаций: впишите его в SOURCE_MUTATIONS — "
            "приговор, дефект и правдоподобные переписывания, — иначе оно доказано только "
            "тем, что сумел вообразить его автор")
        stale = sorted(set(SOURCE_MUTATIONS) - set(rules))
        self.assertEqual(stale, [],
                         "в таблице мутаций правило, чей приговор до теста больше не "
                         "доходит: сверьте таблицу с тем, что осталось")

    @classmethod
    def _file_rules_without_samples(cls, source: str) -> list[str]:
        """Правила по файлу репозитория, которые кормили только самим файлом.

        Такое правило видит ровно то, что в файле уже написано, и молчит о форме, которой там
        ещё нет, — ровно как правило по исходнику без мутаций. Узнаётся оно по тому, ЧТО ему
        отдают: прочитанный файл (`FILE_READS`) в доводе вызова — прямо или через имя, в
        которое его положили. Доказательство — вызов того же правила хоть где-то с доводом,
        который файлом не является: выдуманным образцом.
        """
        vals = _Values(source)

        def reads_file(node, seen: tuple = ()) -> bool:
            for inner in ast.walk(node):
                if (isinstance(inner, ast.Call) and isinstance(inner.func, ast.Attribute)
                        and inner.func.attr in cls.FILE_READS):
                    return True
                if isinstance(inner, ast.Name) and inner.id not in seen and any(
                        reads_file(v, seen + (inner.id,))
                        for v in vals.lookup(inner.id, vals.scope_of(inner))):
                    return True
            return False

        over_file, over_invented = set(), set()
        for node in ast.walk(vals.tree):
            if not (isinstance(node, ast.Call) and node.args):
                continue
            name = (node.func.attr if isinstance(node.func, ast.Attribute)
                    else getattr(node.func, "id", ""))
            if not name.startswith("_"):
                continue
            if any(reads_file(a) for a in node.args):
                over_file.add(name)
            else:
                over_invented.add(name)
        return sorted(over_file - over_invented)

    def test_у_каждого_правила_по_файлу_есть_выдуманный_образец(self):
        """УЗДА КЛАССА «узда, написанная под одну форму записи» — для файлов репозитория."""
        self.assertEqual(
            self._file_rules_without_samples(Path(__file__).read_text(encoding="utf-8")), [],
            "правило по файлу репозитория прогнано только на самом файле: добавьте тест, "
            "который кормит его ВЫДУМАННЫМ образцом — обе стороны, нарушение и невиновный")

    # Обе стороны этой узды. Второй случай — файл, сначала положенный в имя: узда, читавшая
    # только текст довода, такого правила не видела бы.
    FILE_RULE_SHAPES = {
        "файл прямо в доводе":
            "class R:\n    def test_x(self):\n"
            "        self.assertEqual(_new_rule((KIT / 'CHANGELOG.md').read_text()), [])\n",
        "файл сначала в имени":
            "class R:\n    def test_x(self):\n"
            "        text = (KIT / '.github' / 'workflows' / 'tests.yml').read_text()\n"
            "        self.assertEqual(_new_rule(text), [])\n",
    }

    def test_узда_видит_правило_по_файлу_без_образца(self):
        for why, src in self.FILE_RULE_SHAPES.items():
            with self.subTest(правило=why):
                self.assertEqual(self._file_rules_without_samples(src), ["_new_rule"],
                                 "узда не увидела правило, которое кормили только файлом")
                fed = src + ("    def test_y(self):\n"
                             "        self.assertNotEqual(_new_rule('- a\\ntext'), [])\n")
                self.assertEqual(self._file_rules_without_samples(fed), [],
                                 "узда придирается к правилу, у которого образец есть")

    # Обе стороны самой узды, на модулях, которых в наборе нет. Третий случай — тот самый,
    # на котором слепла узда по строкам-маркерам: исходник взят путём, а не через SOURCE.
    RULE_SHAPES = {
        "правило прямо в тесте": (
            "class R:\n    def test_x(self):\n"
            "        for n in ast.walk(ast.parse(self.SOURCE)):\n            pass\n", 0),
        "правило, до которого зовут через посредника": (
            "def _new_rule(src):\n    return [n for n in ast.walk(ast.parse(src))]\n\n"
            "def _offenders_of(src):\n    return _new_rule(src)\n\n"
            "class R:\n    def test_x(self):\n"
            "        self.assertEqual(_offenders_of(self.SOURCE), [])\n", 1),
        "исходник взят путём": (
            "def _new_rule(src):\n    return _Values(src).tree\n\n"
            "class R:\n    def test_x(self):\n"
            "        src = (SKILL / 'scripts' / 'review.py').read_text()\n"
            "        self.assertEqual(_new_rule(src), [])\n", 1),
    }

    def test_узда_видит_правило_которое_никто_не_доказал(self):
        for why, (src, half) in self.RULE_SHAPES.items():
            with self.subTest(правило=why):
                self.assertIn("_new_rule" if half else "test_x",
                              self._rules_without_tables(src)[half],
                              "узда не увидела правило по тому, что оно делает")
        # Обратная сторона: помощник правила отдельной записи в таблице не требует — он
        # доказан вместе с правилом, которое его зовёт.
        helper = ("def _gate_shape(node):\n    return isinstance(node, ast.Call)\n\n"
                  "def _new_rule(src):\n"
                  "    return [n for n in ast.walk(ast.parse(src)) if _gate_shape(n)]\n\n"
                  "class R:\n    def test_x(self):\n"
                  "        self.assertEqual(_new_rule(self.SOURCE), [])\n")
        self.assertEqual(self._rules_without_tables(helper), ([], ["_new_rule"]),
                         "узда требует таблицу от помощника правила")

    # Спрашивающие git по pathspec. Образец приходит из blocks.json и зовётся `spec` или
    # `pattern`; всё прочее — ИМЯ файла, и имя обязано идти под `:(literal)`.
    PATHSPEC_CALLS = ("git_files", "index_rows", "listed", "untracked_files")
    PATTERN_NAMES = ("spec", "specs", "pattern", "patterns", "pathspec", "pathspecs")

    @classmethod
    def _name_as_pattern(cls, source: str) -> list[tuple[int, str]]:
        """Где ИМЯ файла отдают git как образец.

        `[id]` — класс символов: несуществующий `app/[i]/page.tsx` совпадает с живым
        соседом `app/i/page.tsx`, и «файл есть» становится правдой без файла. Три места
        спрашивали так (`file_sha`, узда, `--fixed-in`) — класс закрывается правилом.

        Аргумент читается там, где его собрали: имя в переменной, кортеж, склейка —
        всё это тот же вопрос к git, и правило, знавшее только литеральный список,
        не видело ни одной из этих форм.
        """
        vals = _Values(source)
        offenders = []
        for node in ast.walk(vals.tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id in cls.PATHSPEC_CALLS and node.args):
                continue
            for el in vals.elements(node.args[0]):
                text = ast.unparse(el)
                if ":(literal)" in text or any(p in text for p in cls.PATTERN_NAMES):
                    continue
                offenders.append((node.lineno, text))
        return offenders

    def test_имя_файла_не_уходит_к_git_образцом(self):
        """УЗДА КЛАССА «имя отдано как pathspec»."""
        self.assertEqual(self._name_as_pattern(self.SOURCE), [],
                         "имя файла отдано git образцом: зовите named_file() "
                         "или ставьте префикс `:(literal)`")

    def test_узда_видит_имя_отданное_образцом(self):
        """Обе стороны: имя без `:(literal)` роняет прогон, образец из blocks.json — нет."""
        self.assertNotEqual(self._name_as_pattern("git_files([path])\n"), [])
        self.assertNotEqual(self._name_as_pattern('index_rows([f"{rel}"])\n'), [])
        self.assertEqual(self._name_as_pattern('git_files([f":(literal){rel}"])\n'), [])
        self.assertEqual(self._name_as_pattern("git_files([spec])\n"), [])
        self.assertEqual(
            self._name_as_pattern('git_files([e["pattern"] for e in exclusions])\n'), [])

    def test_каждое_число_в_коде_названо_и_объяснено(self):
        """УЗДА КЛАССА «порог без источника».

        Каждая константа-число обязана нести над собой комментарий о том, откуда она
        взялась: замер или ссылка. Правило ловит следующую добавленную так же, как эти.
        """
        self.assertEqual(self._bare_numbers(self.SOURCE), [],
                         "число без источника: припишите замер или ссылку")

    def test_узда_видит_порог_записанный_не_константой(self):
        """Обе стороны правила на исходниках, которых в инструменте нет: выражение и пара
        обязаны требовать источник так же, как готовое число, а объяснённое — проходить."""
        for why, src in (("выражение", "FOO_LIMIT = 6 * 7\n"),
                         ("пара", "BAR_MAX, BAZ_MAX = 12, 34\n"),
                         ("объявление с типом", "QUX: int = 5\n")):
            with self.subTest(форма=why):
                self.assertNotEqual(self._bare_numbers(src), [],
                                    "порог без источника прошёл мимо узды")
                self.assertEqual(self._bare_numbers("# замер: столько-то\n" + src), [],
                                 "узда не признаёт объяснённый порог")
        self.assertEqual(self._bare_numbers('NAMES = ("critical", "high")\n'), [],
                         "источник спрашивают у чисел, а не у словарей")


# ── Мутации узд по исходнику ────────────────────────────────────────────────────────
#
# Выдуманный образец доказывает ровно то, что сумел вообразить автор правила, — и три
# круга подряд воображения не хватало: каждый раз находилась форма записи, которой правило
# не видело, и ответом было «допишем ещё одну ветку». Поэтому каждое правило прогоняется
# ещё и на НАСТОЯЩЕМ исходнике, переписанном правдоподобно и испорченном нарочно, — так
# же, как `GateMutationTest` прогоняет ворота: приговор правила обязан зависеть от того,
# ЧТО код делает, и не зависеть от того, КАК он написан.


class _Rewrite(ast.NodeTransformer):
    """Подмена узлов по тождеству: мутатор находит узлы, оснастка их заменяет."""

    def __init__(self, table: dict) -> None:
        self.table = table

    def visit(self, node):
        swapped = self.table.get(id(node))
        return swapped if swapped is not None else super().visit(node)


def _rewritten(vals: _Values, table: dict | None = None,
               hoisted: list | None = None, local: dict | None = None) -> str:
    """Дерево обратно в текст: замены, вставки в функции и новые определения модуля."""
    tree = _Rewrite(table or {}).visit(vals.tree)
    top = list(hoisted or [])
    for holder, stmts in (local or {}).items():
        if isinstance(holder, (ast.FunctionDef, ast.AsyncFunctionDef)):
            holder.body[:0] = stmts
        else:
            top += stmts
    if top:
        # `from __future__ import annotations` обязан остаться первым оператором модуля
        after = 0
        while after < len(tree.body) and (
                isinstance(tree.body[after], (ast.Import, ast.ImportFrom))
                or (isinstance(tree.body[after], ast.Expr)
                    and isinstance(tree.body[after].value, ast.Constant))):
            after += 1
        tree.body[after:after] = top
    ast.fix_missing_locations(tree)
    return ast.unparse(tree)


def _reparsed(source: str) -> str:
    """Тот же модуль, пропущенный через дерево, — контроль самой оснастки."""
    return ast.unparse(ast.parse(source))


def _put(vals: _Values, near, stmt, hoisted: list, local: dict) -> None:
    """Новый оператор — в функцию, где живёт `near`, или в модуль, если её нет."""
    scope = vals.scope_of(near)
    if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef)):
        local.setdefault(scope, []).append(stmt)
    else:
        hoisted.append(stmt)


# ── запуск git ──


def _git_spawn_outside(source: str) -> str:
    """ДЕФЕКТ: git запускают мимо помощника — и argv, и `-z` собирают на месте."""
    return source.rstrip("\n") + (
        "\n\n\ndef churn_records():\n"
        '    cmd = ["git", "log", "--first-parent", "--name-only"]\n'
        "    out = subprocess.run(cmd, capture_output=True, text=True, check=False)\n"
        "    return out.stdout.splitlines()\n")


def _git_argv_by_method(source: str) -> str:
    """Argv копят методом списка: `cmd = [...]` → `cmd = [...]; cmd.extend([...])`.

    Одна из двух форм, на которых слепло правило по СБОРКЕ argv: приговор нового правила не
    имеет права от неё зависеть — argv можно собирать как угодно, дойти до git он может
    только через помощника.
    """
    vals = _Values(source)
    table, local, hoisted = {}, {}, []
    for node in ast.walk(vals.tree):
        if not (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and isinstance(node.value, ast.List) and len(node.value.elts) > 1):
            continue
        items = [e.value for e in node.value.elts
                 if isinstance(e, ast.Constant) and isinstance(e.value, str)]
        if "git" not in items:
            continue
        name = node.targets[0].id
        head, tail = node.value.elts[:1], node.value.elts[1:]
        node.value.elts = head
        grow = ast.parse(f"{name}.extend([])").body[0]
        grow.value.args[0].elts = tail
        table[id(node)] = [node, grow]
    # оператор заменяется ДВУМЯ: подмена по тождеству отдаёт список, `_Rewrite` его развернёт
    return _rewritten(vals, table, hoisted, local)


def _git_argv_via_wrapper(source: str) -> str:
    """Argv приходит на запуск из обёртки: на месте запуска списка не видно вовсе.

    Вторая форма, на которой слепло прежнее правило (`_git(*rest)`): argv у запуска —
    результат чужого вызова, и прочесть его по виду нельзя. Приговор нового правила от этого
    не зависит: запуск виден по тому, ЧТО зовут.
    """
    vals = _Values(source)
    table, hoisted = {}, []
    for node in ast.walk(vals.tree):
        if not (isinstance(node, ast.Call) and node.args):
            continue
        called = (node.func.attr if isinstance(node.func, ast.Attribute)
                  else getattr(node.func, "id", ""))
        if called not in SourceRuleTest.SPAWNERS:
            continue
        wrapped = ast.parse("_argv_of(None)").body[0].value
        wrapped.args = [node.args[0]]
        table[id(node.args[0])] = wrapped
    if table:
        hoisted.append(ast.parse("def _argv_of(argv):\n    return list(argv)\n").body[0])
    return _rewritten(vals, table, hoisted)


# ── имя файла как pathspec ──


def _pathspec_calls(tree) -> list:
    return [n for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
            and n.func.id in SourceRuleTest.PATHSPEC_CALLS and n.args
            and isinstance(n.args[0], ast.List) and n.args[0].elts]


def _pathspec_without_literal(source: str) -> str:
    """ДЕФЕКТ: имя файла уходит к git образцом, и `[handle]` в нём — класс символов."""
    vals = _Values(source)
    for call in _pathspec_calls(vals.tree):
        for part in ast.walk(call.args[0]):
            if isinstance(part, ast.Constant) and isinstance(part.value, str):
                part.value = part.value.replace(":(literal)", "")
    return _rewritten(vals)


def _pathspec_respelled(source: str, how: str) -> str:
    vals = _Values(source)
    table, hoisted, local = {}, [], {}
    for n, call in enumerate(_pathspec_calls(vals.tree)):
        arg = call.args[0]
        if how == "кортежем":
            table[id(arg)] = ast.Tuple(elts=list(arg.elts), ctx=ast.Load())
        elif how == "склейкой":
            new = ast.parse("[] + []").body[0].value
            new.right.elts = list(arg.elts)
            table[id(arg)] = new
        else:
            name = f"_WANT_{n}"
            holder = ast.parse(f"{name} = []").body[0]
            holder.value.elts = list(arg.elts)
            _put(vals, call, holder, hoisted, local)
            table[id(arg)] = ast.Name(id=name, ctx=ast.Load())
    return _rewritten(vals, table, hoisted, local)


# ── реестр ворот ──


def _gate_statements(tree) -> list:
    """Операторы, которые добавляют отказ: ворота целиком, как их вырезает мутация."""
    out = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr in GATE_VERBS):
            continue
        parents = {id(c): n for n in ast.walk(tree) for c in ast.iter_child_nodes(n)}
        stmt = node
        while not isinstance(stmt, ast.stmt) and id(stmt) in parents:
            stmt = parents[id(stmt)]
        out.append(stmt)
    return out


def _gate_removed(source: str) -> str:
    """ДЕФЕКТ: одних ворот больше нет — их ключ обязан пропасть из реестра."""
    vals = _Values(source)
    return _rewritten(vals, {id(_gate_statements(vals.tree)[0]): ast.Pass()})


def _gates_split_out(source: str, how: str) -> str:
    """`cmd_check` в пятьсот строк разобран на части — очевидный следующий шаг.

    Контейнер отказов при этом передают в помощника, и зовут его там как придётся: `refusals`
    — ровно то имя, на котором прежний реестр, узнававший список отказов по имени
    переменной, не видел ворот вовсе.
    """
    vals = _Values(source)
    table, hoisted, local = {}, [], {}
    for n, stmt in enumerate(_gate_statements(vals.tree)):
        name = f"_gate_{n}"
        holder = "refusals" if how == "контейнер зовут иначе" else "gates"
        helper = ast.parse(f"def {name}({holder}):\n    pass\n").body[0]
        for node in ast.walk(stmt):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr in GATE_VERBS
                    and isinstance(node.func.value, ast.Name)):
                node.func.value.id = holder
        helper.body = [stmt]
        table[id(stmt)] = ast.parse(f"{name}(gates)").body[0]
        if how == "часть внутри команды":
            _put(vals, stmt, helper, hoisted, local)
        else:
            hoisted.append(helper)
    return _rewritten(vals, table, hoisted, local)


def _check_verdict_of_its_own(source: str) -> str:
    """ДЕФЕКТ: ворота печатают отказ сами и сами выходят — мимо контейнера и реестра."""
    vals = _Values(source)
    fn = next(n for n in ast.walk(vals.tree)
              if isinstance(n, ast.FunctionDef) and n.name == "cmd_check")
    own = ast.parse('if not idx:\n'
                    '    print("CHECK FAILED: no blocks at all")\n'
                    '    return 1\n').body[0]
    fn.body.insert(1, own)
    return _rewritten(vals)


# ── пороги ──


def _simple_const(line: str) -> bool:
    """Константа модуля, записанная целиком в одну строку."""
    if not re.match(r"^[A-Z_][A-Z_0-9]*\s*(:[^=]+)?=", line):
        return False
    return all(line.count(a) == line.count(b) for a, b in ("()", "[]", "{}")) \
        and not line.rstrip().endswith("\\")


def _threshold_unexplained(source: str) -> str:
    """ДЕФЕКТ: у порога нет ни замера, ни ссылки."""
    return source.rstrip("\n") + "\n\n\nSPOILED_LIMIT = 42\n"


def _thresholds_respelled(source: str, how: str) -> str:
    out = []
    for line in source.split("\n"):
        m = re.match(r"^([A-Z_][A-Z_0-9]*)( *: *[\w\[\], .]+)? = (.+)$", line)
        value, sep, tail = (m.group(3), "", "") if m else ("", "", "")
        if m and "  #" in value:
            value, sep, tail = value.partition("  #")
        if not m or not re.fullmatch(r"-?\d+", value.strip()):
            out.append(line)
        elif how == "число выражением":
            out.append(f"{m.group(1)}{m.group(2) or ''} = ({value.strip()}) + 0{sep}{tail}")
        else:
            out.append(f"{m.group(1)}: int = {value.strip()}{sep}{tail}")
    return "\n".join(out)


def _thresholds_in_a_function(source: str) -> str:
    """Порог переехал внутрь функции, которая им одна и пользуется."""
    lines, out, n = source.split("\n"), [], 0
    i = 0
    while i < len(lines):
        if not _simple_const(lines[i]):
            out.append(lines[i])
            i += 1
            continue
        start = i
        while i < len(lines) and _simple_const(lines[i]):
            i += 1
        block = lines[start:i]
        while out and out[-1].lstrip().startswith("#"):
            block.insert(0, out.pop())
        n += 1
        out.append(f"def _thresholds_{n}():")
        out += ["    " + ln if ln.strip() else ln for ln in block]
    return "\n".join(out)


# ── поток `git log` ──


def _second_log_parser(source: str) -> str:
    """ДЕФЕКТ: поток истории заказывают и разбирают ещё раз, своими руками.

    Написано так, как такой разборщик и пишут, — одним выражением вместе с форматом. На
    прежнем правиле, которое разрешало постановку маркера «куда бы значение ни шло», ровно
    эта сжатая форма проходила молча, а раздельная — нет.
    """
    return source.rstrip("\n") + (
        "\n\n\ndef churn_records(paths):\n"
        '    return git("log", f"--format={LOG_MARK}%H", "--name-only", "--", *paths)'
        ".out.split(LOG_MARK)\n")


def _format_respelled(source: str, how: str) -> str:
    """Строку `--format=` пишут не только f-строкой."""
    vals = _Values(source)
    table, hoisted, local = {}, [], {}
    marks = [n for n in ast.walk(vals.tree)
             if isinstance(n, ast.JoinedStr)
             and any(isinstance(v, ast.Constant) and "--format=" in v.value
                     for v in n.values)]
    for n, node in enumerate(marks):
        parts = [v if isinstance(v, ast.Constant) else v.value for v in node.values]
        if how == "склейкой":
            new = parts[0]
            for part in parts[1:]:
                new = ast.BinOp(left=new, op=ast.Add(), right=part)
            table[id(node)] = new
            continue
        name = f"_fmt_{n}"
        tail = parts[1]
        for part in parts[2:]:
            tail = ast.BinOp(left=tail, op=ast.Add(), right=part)
        holder = ast.parse(f"{name} = None").body[0]
        holder.value = tail
        _put(vals, node, holder, hoisted, local)
        table[id(node)] = ast.parse(f'f"--format={{{name}}}"').body[0].value
    return _rewritten(vals, table, hoisted, local)


# ── распознавание цитаты ──


def _deaf_report_parser(source: str) -> str:
    """ДЕФЕКТ: разметку отчёта разбирают, не спросив общий трекер цитаты."""
    return source.rstrip("\n") + (
        "\n\n\ndef limits_lines(md):\n"
        "    return [line for line in md.split(chr(10)) if line.startswith('#')]\n")


def _tracker_via_relay(source: str) -> str:
    """Трекер цитаты зовут через посредника — разбор всё равно его спросил."""
    vals = _Values(source)
    table, hoisted = {}, []
    used = set()
    for node in ast.walk(vals.tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id in SourceRuleTest.QUOTE_TRACKERS):
            relay = f"_relay_{node.func.id}"
            table[id(node.func)] = ast.Name(id=relay, ctx=ast.Load())
            used.add((relay, node.func.id))
    for relay, tracker in sorted(used):
        hoisted.append(ast.parse(f"def {relay}(*args):\n"
                                 f"    return {tracker}(*args)\n").body[0])
    return _rewritten(vals, table, hoisted)


# ── таблицы сообщений ──


def _msg_assign(tree):
    for node in ast.walk(tree):
        target = (node.targets[0] if isinstance(node, ast.Assign) and len(node.targets) == 1
                  else node.target if isinstance(node, ast.AnnAssign) else None)
        if isinstance(target, ast.Name) and target.id == "MSG":
            return node
    return None


def _msg_key_dropped(source: str) -> str:
    """ДЕФЕКТ: перевод потерян — ключ есть на одном языке и нет на другом."""
    vals = _Values(source)
    table = _msg_assign(vals.tree).value
    for key, value in zip(table.keys, table.values):
        if isinstance(key, ast.Constant) and key.value == "ru":
            value.keys, value.values = value.keys[1:], value.values[1:]
    return _rewritten(vals)


def _msg_respelled(source: str, how: str) -> str:
    vals = _Values(source)
    hoisted, table = [], {}
    node = _msg_assign(vals.tree)
    if how == "объявление с типом":
        new = ast.parse("MSG: dict = {}").body[0]
        new.value = node.value
        table[id(node)] = new
        return _rewritten(vals, table)
    for key, value in zip(node.value.keys, node.value.values):
        name = f"_MSG_{key.value.upper()}"
        holder = ast.parse(f"{name} = None").body[0]
        holder.value = value
        hoisted.append(holder)
        table[id(value)] = ast.Name(id=name, ctx=ast.Load())
    return _rewritten(vals, table, hoisted)


# ── поля записи реестра ──


def _unknown_field_read(source: str) -> str:
    """ДЕФЕКТ: у находки появилось поле, о котором не знает ни один шаблон роли."""
    return source.rstrip("\n") + ('\n\n\ndef finding_note(f) -> str:\n'
                                  '    return f.get("verdict_note") or ""\n')


def _record_renamed(source: str) -> str:
    """Запись реестра зовут не `f`, а по-человечески."""
    vals = _Values(source)
    for node in ast.walk(vals.tree):
        if isinstance(node, ast.Name) and node.id == "f":
            node.id = "record"
        elif isinstance(node, ast.arg) and node.arg == "f":
            node.arg = "record"
    return _rewritten(vals)


# ── запуск потомков в наборе ──


def _spawn_without_env(source: str) -> str:
    """ДЕФЕКТ: потомок берёт локаль и конфиг git у машины, а python — из PATH."""
    return source.rstrip("\n") + ('\n\n\ndef _probe_version():\n'
                                  '    return subprocess.run(["python3", "-V"], text=True)\n')


def _subprocess_respelled(source: str, how: str) -> str:
    vals = _Values(source)
    table, hoisted = {}, []
    if how == "модуль под псевдонимом":
        for node in ast.walk(vals.tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "subprocess":
                        alias.asname = "sp"
            elif isinstance(node, ast.Name) and node.id == "subprocess":
                node.id = "sp"
        return _rewritten(vals)
    if how == "имя втянуто из модуля":
        for node in ast.walk(vals.tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "subprocess"):
                table[id(node.func)] = ast.Name(id=node.func.attr, ctx=ast.Load())
        hoisted.append(ast.parse("from subprocess import CalledProcessError, PIPE, Popen, "
                                 "TimeoutExpired, call, check_call, check_output, run"
                                 ).body[0])
        return _rewritten(vals, table, hoisted)
    for node in ast.walk(vals.tree):
        if isinstance(node, ast.Constant) and node.value == "python3":
            table[id(node)] = ast.Name(id="_PY", ctx=ast.Load())
    hoisted.append(ast.parse('_PY = "python3"').body[0])
    return _rewritten(vals, table, hoisted)


# ── правила без таблицы мутаций ──


def _rule_inline_in_a_test(source: str) -> str:
    """ДЕФЕКТ: правило по исходнику написано прямо в тесте — покормить его нечем."""
    return source.rstrip("\n") + (
        "\n\n\nclass _InlineRuleTest(unittest.TestCase):\n"
        "    def test_правило_написано_прямо_в_тесте(self):\n"
        "        for node in ast.walk(ast.parse(self.SOURCE)):\n"
        "            self.assertIsNotNone(node)\n")


def _rule_via_relay(source: str) -> str:
    """До правила зовут не из теста прямо, а через посредника.

    Узда обязана дойти до правила по вызовам: прежняя смотрела, ЧЕМ правило кормят, и
    посредник выводил правило из-под таблицы мутаций молча.
    """
    vals = _Values(source)
    table, hoisted, relays = {}, [], set()
    for node in ast.walk(vals.tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id in SOURCE_MUTATIONS):
            continue
        relay = f"_relay{node.func.id}"
        table[id(node.func)] = ast.Name(id=relay, ctx=ast.Load())
        relays.add((relay, node.func.id))
    for relay, rule in sorted(relays):
        hoisted.append(ast.parse(f"def {relay}(*args, **kw):\n"
                                 f"    return {rule}(*args, **kw)\n").body[0])
    return _rewritten(vals, table, hoisted)


# ── команды инструмента ──


def _undocumented_subcommand(source: str) -> str:
    """ДЕФЕКТ: у инструмента появилась команда, о которой SKILL.md не знает."""
    vals = _Values(source)
    call = next(n for n in ast.walk(vals.tree)
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == "add_parser" and n.args)
    sub = ast.unparse(call.func.value)
    added = ast.parse(f'{sub}.add_parser("wibble", help="undocumented")').body[0]
    hoisted, local = [], {}
    _put(vals, call, added, hoisted, local)
    return _rewritten(vals, {}, hoisted, local)


def _subcommand_via_variable(source: str) -> str:
    """Имя команды вынесено в переменную — обычный перенос, и правило не имеет права от
    него слепнуть."""
    vals = _Values(source)
    table, hoisted, local = {}, [], {}
    for n, call in enumerate(list(ast.walk(vals.tree))):
        if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                and call.func.attr == "add_parser" and call.args
                and isinstance(call.args[0], ast.Constant)):
            continue
        name = f"_CMD_{n}"
        holder = ast.parse(f"{name} = None").body[0]
        holder.value = call.args[0]
        _put(vals, call, holder, hoisted, local)
        table[id(call.args[0])] = ast.Name(id=name, ctx=ast.Load())
    return _rewritten(vals, table, hoisted, local)


# ── вынос значения в имя перед оператором ──


class _Hoist(ast.NodeTransformer):
    """Вставка операторов ПЕРЕД названными: значение сначала кладут в имя, потом зовут.

    В отличие от `_Rewrite`, дети заменённого оператора тоже обходятся — вынос из цикла не
    должен терять вынос из его тела.
    """

    def __init__(self, before: dict) -> None:
        self.before = before

    def visit(self, node):
        key = id(node)
        out = super().visit(node)
        pre = self.before.get(key)
        return [*pre, out] if pre else out


def _hoisted_args(source: str, wanted) -> str:
    """Доводы, которые `wanted(call, arg)` называет, выносятся в имя перед оператором."""
    vals = _Values(source)
    before: dict = {}
    n = 0
    for node in list(ast.walk(vals.tree)):
        if not isinstance(node, ast.Call):
            continue
        for i, arg in enumerate(node.args):
            if not wanted(node, arg):
                continue
            stmt = node
            while not isinstance(stmt, ast.stmt):
                stmt = vals.parent[stmt]
            n += 1
            holder = ast.parse(f"_hoisted_{n} = None").body[0]
            holder.value = arg
            node.args[i] = ast.Name(id=f"_hoisted_{n}", ctx=ast.Load())
            before.setdefault(id(stmt), []).append(holder)
    tree = _Hoist(before).visit(vals.tree)
    ast.fix_missing_locations(tree)
    return ast.unparse(tree)


def _called(node) -> str:
    return (node.func.attr if isinstance(node.func, ast.Attribute)
            else getattr(node.func, "id", ""))


# ── названные агенту выходы ──


def _exit_misnamed(source: str) -> str:
    """ДЕФЕКТ: предупреждение об объёме зовёт в раздел, которого ворота не читают."""
    was, now = "in the coverage-limits section of your report", "in the coverage section of your report"
    assert was in source, "порча ставится мимо исходника"
    return source.replace(was, now)


def _diff_unnamed(source: str) -> str:
    """ДЕФЕКТ: текст зовёт `--scope` как выход из объёма, а флаг, который дифф уменьшает,
    из него пропал."""
    assert "--scope" in source and "--diff" in source, "порча ставится мимо исходника"
    return source.replace("--diff", "--range")


# ── обходы команд ──


def _sweep_without_body_check(source: str) -> str:
    """ДЕФЕКТ: обход берёт команды у инструмента и не спрашивает, дошла ли команда до тела."""
    return source.rstrip("\n") + (
        "\n\n\nclass _SweepSpoilTest(unittest.TestCase):\n"
        "    def test_обход_без_вопроса_о_теле(self):\n"
        "        for cmd in self._subcommands():\n"
        "            self.s.run(cmd)\n")


def _hoist_iters(source: str) -> str:
    """Список команд сначала кладут в имя, потом обходят — обычный перенос."""
    vals = _Values(source)
    before: dict = {}
    for n, node in enumerate(list(ast.walk(vals.tree))):
        if not (isinstance(node, ast.For) and any(
                isinstance(c, ast.Call) and _called(c) == "_subcommands"
                for c in ast.walk(node.iter))):
            continue
        holder = ast.parse(f"_commands_{n} = None").body[0]
        holder.value = node.iter
        node.iter = ast.Name(id=f"_commands_{n}", ctx=ast.Load())
        before.setdefault(id(node), []).append(holder)
    tree = _Hoist(before).visit(vals.tree)
    ast.fix_missing_locations(tree)
    return ast.unparse(tree)


# ── правила по файлу репозитория ──


def _file_rule_without_sample(source: str) -> str:
    """ДЕФЕКТ: правило по файлу репозитория кормят только самим файлом."""
    return source.rstrip("\n") + (
        "\n\n\ndef _new_file_rule(text):\n"
        "    return [ln for ln in text.splitlines() if ln.startswith('<<<')]\n\n\n"
        "class _FileRuleSpoilTest(unittest.TestCase):\n"
        "    def test_правило_по_файлу_без_образца(self):\n"
        "        self.assertEqual(\n"
        "            _new_file_rule((KIT / 'README.md').read_text(encoding='utf-8')), [])\n")


def _file_read_into_a_name(source: str) -> str:
    """Прочитанный файл сначала кладут в имя, а правилу отдают имя."""
    return _hoisted_args(source, lambda call, arg: _called(call).startswith("_") and any(
        isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)
        and c.func.attr in SourceRuleTest.FILE_READS for c in ast.walk(arg)))


# ── приговоры правил: один список строк, пустой на честном исходнике ──


def _v_spawn_host(source: str) -> list[str]:
    return SourceRuleTest._spawns_outside_git(source)


def _v_pathspec(source: str) -> list[str]:
    return sorted({text for _, text in SourceRuleTest._name_as_pattern(source)})


def _v_gates(source: str) -> list[str]:
    """Ключи ворот, которые ПРОПАЛИ по сравнению с честным инструментом."""
    was = collections.Counter(g.key for g in _check_gates())
    now = collections.Counter(g.key for g in _check_gates(source))
    return sorted((was - now).elements())


def _v_own_verdict(source: str) -> list[str]:
    return _own_verdict(source)


def _v_numbers(source: str) -> list[str]:
    return sorted(set(SourceRuleTest._bare_numbers(source)))


def _v_log_stream(source: str) -> list[str]:
    return SourceRuleTest._log_stream_outside_reader(source)


def _v_quotes(source: str) -> list[str]:
    strangers, deaf = SourceRuleTest._quote_offenders(SourceRuleTest, source)
    return sorted([f"свой детектор: {name}" for name, _ in strangers]
                  + [f"без трекера: {name}" for name in deaf])


def _v_msg(source: str) -> list[str]:
    return sorted(LanguageTest._msg_mismatch(LanguageTest._msg_tables(source)))


def _v_fields(source: str) -> list[str]:
    known = TemplateContractTest.TOOL_FIELDS | TemplateContractTest.AGENT_FIELDS
    return sorted(TemplateContractTest._register_fields(source) - known)


def _v_spawns(source: str) -> list[str]:
    return sorted({why for _, why in _spawns(source)})


def _v_subcommands(source: str) -> list[str]:
    """Команды инструмента, которых нет в SKILL.md, — то, о чём и есть тот тест."""
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    return [c for c in DocumentedSurfaceTest.subcommands(source)
            if not re.search(rf"review(?:\.py)?\s+{re.escape(c)}\b", text)]


def _v_rules(source: str) -> list[str]:
    """Заодно и потеря правила из виду: узда, переставшая замечать правило, молча выводит
    его из-под собственной таблицы мутаций."""
    inline, rules = SourceRuleTest._rules_without_tables(source)
    return sorted([f"в тесте: {name}" for name in inline]
                  + [f"без таблицы: {name}" for name in set(rules) - set(SOURCE_MUTATIONS)]
                  + [f"потеряно из виду: {name}"
                     for name in set(SOURCE_MUTATIONS) - set(rules)])


def _v_named_exits(source: str) -> list[str]:
    sources = dict(NamedExitTest._sources())
    sources["scripts/review.py"] = source
    return NamedExitTest._named_exits(sources, NamedExitTest._documents())


def _v_scope(source: str) -> list[str]:
    """Тексты, а не номера строк: перенос сдвигает строки, а дефект остаётся тем же."""
    return sorted({text for _, text in NamedExitTest._scope_without_diff(source)})


def _v_sweeps(source: str) -> list[str]:
    return _sweeps_without_body_check(source)


def _v_file_rules(source: str) -> list[str]:
    return SourceRuleTest._file_rules_without_samples(source)


# Что доказывается мутациями: приговор правила, дефект и правдоподобные переписывания,
# от которых приговор меняться НЕ имеет права. `suite` — правило читает не инструмент,
# а сам набор.
Mutated = collections.namedtuple("Mutated", "verdict spoil respellings suite")

SOURCE_MUTATIONS = {
    "_spawns_outside_git": Mutated(_v_spawn_host, _git_spawn_outside, {
        "как написано": _reparsed,
        "argv накоплен методом": _git_argv_by_method,
        "argv из обёртки": _git_argv_via_wrapper,
        "модуль под псевдонимом": lambda s: _subprocess_respelled(s, "модуль под псевдонимом"),
        "имя втянуто из модуля": lambda s: _subprocess_respelled(s, "имя втянуто из модуля"),
    }, False),
    "_name_as_pattern": Mutated(_v_pathspec, _pathspec_without_literal, {
        "как написано": _reparsed,
        "имя в переменной": lambda s: _pathspec_respelled(s, "имя в переменной"),
        "кортежем": lambda s: _pathspec_respelled(s, "кортежем"),
        "склейкой": lambda s: _pathspec_respelled(s, "склейкой"),
    }, False),
    "_check_gates": Mutated(_v_gates, _gate_removed, {
        "как написано": _reparsed,
        "ворота в помощнике": lambda s: _gates_split_out(s, "ворота в помощнике"),
        "контейнер зовут иначе": lambda s: _gates_split_out(s, "контейнер зовут иначе"),
        "часть внутри команды": lambda s: _gates_split_out(s, "часть внутри команды"),
    }, False),
    "_own_verdict": Mutated(_v_own_verdict, _check_verdict_of_its_own, {
        "как написано": _reparsed,
        "ворота в помощнике": lambda s: _gates_split_out(s, "ворота в помощнике"),
        "контейнер зовут иначе": lambda s: _gates_split_out(s, "контейнер зовут иначе"),
    }, False),
    "_bare_numbers": Mutated(_v_numbers, _threshold_unexplained, {
        "как написано": lambda s: s,
        "число выражением": lambda s: _thresholds_respelled(s, "число выражением"),
        "объявление с типом": lambda s: _thresholds_respelled(s, "объявление с типом"),
        "порог внутри функции": _thresholds_in_a_function,
    }, False),
    "_log_stream_outside_reader": Mutated(_v_log_stream, _second_log_parser, {
        "как написано": _reparsed,
        "формат склейкой": lambda s: _format_respelled(s, "склейкой"),
        "формат собран заранее": lambda s: _format_respelled(s, "заранее"),
    }, False),
    "_quote_offenders": Mutated(_v_quotes, _deaf_report_parser, {
        "как написано": _reparsed,
        "трекер через посредника": _tracker_via_relay,
    }, False),
    "_msg_tables": Mutated(_v_msg, _msg_key_dropped, {
        "как написано": _reparsed,
        "объявление с типом": lambda s: _msg_respelled(s, "объявление с типом"),
        "языки отдельными константами": lambda s: _msg_respelled(s, "отдельными"),
    }, False),
    "_register_fields": Mutated(_v_fields, _unknown_field_read, {
        "как написано": _reparsed,
        "запись зовут иначе": _record_renamed,
    }, False),
    "_spawns": Mutated(_v_spawns, _spawn_without_env, {
        "как написано": _reparsed,
        "модуль под псевдонимом": lambda s: _subprocess_respelled(s, "модуль под псевдонимом"),
        "имя втянуто из модуля": lambda s: _subprocess_respelled(s, "имя втянуто из модуля"),
        "интерпретатор в переменной": lambda s: _subprocess_respelled(s, "в переменной"),
    }, True),
    "subcommands": Mutated(_v_subcommands, _undocumented_subcommand, {
        "как написано": _reparsed,
        "имя команды в переменной": _subcommand_via_variable,
    }, False),
    "_rules_without_tables": Mutated(_v_rules, _rule_inline_in_a_test, {
        "как написано": _reparsed,
        "правило через посредника": _rule_via_relay,
    }, True),
    "_named_exits": Mutated(_v_named_exits, _exit_misnamed, {
        "как написано": _reparsed,
        "объявление с типом": lambda s: _msg_respelled(s, "объявление с типом"),
    }, False),
    "_scope_without_diff": Mutated(_v_scope, _diff_unnamed, {
        "как написано": _reparsed,
        "объявление с типом": lambda s: _msg_respelled(s, "объявление с типом"),
    }, False),
    "_sweeps_without_body_check": Mutated(_v_sweeps, _sweep_without_body_check, {
        "как написано": _reparsed,
        "список команд в имени": _hoist_iters,
    }, True),
    "_file_rules_without_samples": Mutated(_v_file_rules, _file_rule_without_sample, {
        "как написано": _reparsed,
        "файл сначала в имени": _file_read_into_a_name,
    }, True),
}


class SourceMutationTest(unittest.TestCase):
    """УЗДА КЛАССА «узда, написанная под одну форму записи» — мутациями, а не списком.

    Корень блока пережил два круга починок: правило по исходнику расширяли ещё на одну
    форму записи, находилась следующая, и «починено» держалось ровно до неё. Список форм
    здесь не поможет — их всегда на одну больше, чем вообразил автор. Поэтому доказывать
    правило надо тем же способом, каким `GateMutationTest` доказывает ворота: на нарочно
    испорченном НАСТОЯЩЕМ исходнике.

    Каждое правило прогоняется четырежды в каждой форме записи:

    * на честном исходнике — обязано молчать (иначе «покраснело» ничего не значит);
    * на честном ПЕРЕПИСАННОМ — обязано молчать (иначе правило запрещает переносы);
    * на испорченном — обязано говорить;
    * на испорченном И переписанном — обязано говорить ТО ЖЕ САМОЕ.

    Последнее и есть проверяемое свойство: приговор зависит от того, что код делает, и
    не зависит от того, как он написан.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.TOOL_SOURCE = TOOL.read_text(encoding="utf-8")
        cls.SUITE_SOURCE = Path(__file__).read_text(encoding="utf-8")

    def _clean(self, rule) -> str:
        return self.SUITE_SOURCE if rule.suite else self.TOOL_SOURCE

    def test_каждое_правило_по_исходнику_доказано_мутацией(self):
        for name, rule in SOURCE_MUTATIONS.items():
            clean = self._clean(rule)
            with self.subTest(узда=name):
                self.assertEqual(rule.verdict(clean), [],
                                 "контроль: на честном исходнике правило обязано молчать")
                wounded = rule.verdict(rule.spoil(clean))
                self.assertNotEqual(
                    wounded, [],
                    "правило не увидело дефекта даже там, где он написан прямо: "
                    "мутация не воспроизводит то, ради чего правило написано")
                for how, respell in rule.respellings.items():
                    with self.subTest(форма=how):
                        self.assertEqual(
                            rule.verdict(respell(clean)), [],
                            "правило придирается к переписанному, но ЧЕСТНОМУ исходнику: "
                            "оно запрещает перенос, а не дефект")
                        self.assertEqual(
                            rule.verdict(respell(rule.spoil(clean))), wounded,
                            "правило не увидело тот же дефект, записанный иначе: "
                            "смотрите туда, где значение собирают, а не туда, где его "
                            "написали — ещё одна ветка `isinstance` кончится так же")

    def test_приговор_каждого_правила_проверен_на_обеих_сторонах(self):
        """Контроль самой таблицы: у правила обязан быть и дефект, и хотя бы один честный
        перенос. Запись без переписываний доказывает только то, что правило видит дефект
        там, где он написан прямо, — а разъезжались правила именно на переносах.

        Кому таблица нужна — решает `_rules_without_tables`: правило, чей приговор доходит
        до теста, обязано быть здесь.
        """
        for name, rule in SOURCE_MUTATIONS.items():
            with self.subTest(узда=name):
                self.assertTrue(callable(rule.verdict) and callable(rule.spoil))
                self.assertGreaterEqual(
                    len(rule.respellings), 2,
                    "у правила нет ни одного переписывания кроме контрольного: "
                    "перечислите правдоподобные переносы, иначе правило доказано только "
                    "на той форме записи, в которой оно и написано")


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

class TemplateContractTest(unittest.TestCase):
    """УЗДА КЛАССА «ворота спрашивают то, о чём шаблон роли молчит».

    Если `check` читает у находки поле, которого нет ни в одном шаблоне, честно написанный
    отчёт краснеет, а выхода агенту никто не назвал. Измерено дважды: причину отказа
    шаблон проверяющего велел писать в `claim`, а ворота ждали `reject_reason`; поля `root`
    в образце черновика не было вовсе, и ворота про третий экземпляр класса не могли
    покраснеть ни на одном прогоне, написанном по образцу. Список полей берётся из
    ИСХОДНИКА: поле, которого ещё не написали, тоже обязано быть классифицировано.

    Спрашивается не «слово встречается в шаблоне», а «шаблон даёт образец, который агент
    копирует». Прежняя проверка искала подстроку по всему тексту, а каждое имя поля —
    обычное слово прозы: `root` «числился названным» фразой «the whole root at once» и
    строкой пути `"file":"path/from/repository/root"`. Измерено: из всех восьми шаблонов
    удалены ВСЕ огороженные схемы черновика — узда осталась зелёной на всех тринадцати
    полях по-английски, то есть ровно то, ради чего её писали, ею не держалось.
    """

    # Поля, которые проставляет сам инструмент: шаблону о них говорить нечего.
    TOOL_FIELDS = {"id", "code_sha", "imported_at", "updated_at", "restamped_at",
                   "fix_commit", "fixed_in", "rule"}
    # Поля черновика: агент пишет их строкой JSON. Шаблон обязан назвать каждое КЛЮЧОМ
    # схемы (`"поле":`) и внутри кода — в огороженном блоке или в обратных кавычках.
    DRAFT_FIELDS = {"block", "severity", "confidence", "status", "file", "line", "claim",
                    "scenario", "invariant", "root", "dup_of", "reject_reason"}
    # Поля, которые инструмент проставляет по флагу: их пишет не черновик, а команда, и
    # шаблон обязан назвать поле и команду в одном абзаце — иначе агент узнаёт имя поля и
    # не узнаёт, чем его заполнить.
    COMMAND_FIELDS = {"defer_reason": "set-finding"}
    # Поля, которые пишет АГЕНТ, — каждое обязано быть названо в шаблоне хоть одной роли,
    # и на каждом языке ревью отдельно.
    AGENT_FIELDS = DRAFT_FIELDS | set(COMMAND_FIELDS)
    ROLES = ("hunter", "verify", "fix", "fixreview")
    LANGS = ("", "ru")

    # Поля, которые бывают только у записи реестра: по ним запись и УЗНАЁТСЯ. Имя
    # переменной для этого не годится — `f` в инструменте это и находка, и путь к файлу,
    # а переименование `f` → `finding` снимало бы правило целиком и молча.
    RECORD_MARKS = {"claim", "scenario", "severity", "confidence", "reject_reason",
                    "defer_reason", "dup_of", "fix_commit", "code_sha", "root"}

    @classmethod
    def _register_fields(cls, source: str) -> set[str]:
        """Словарь полей записи реестра — из обращений к находке в исходнике инструмента.

        Запись узнаётся по своим полям: переменная, у которой спрашивают `claim` или
        `severity`, — это находка, как бы её ни звали, и все прочие поля, которые
        спрашивают у неё же, тоже поля записи.
        """
        accesses = []
        for n in ast.walk(ast.parse(source)):
            key = base = None
            if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                    and n.func.attr in ("get", "setdefault")
                    and isinstance(n.func.value, ast.Name) and n.args
                    and isinstance(n.args[0], ast.Constant)):
                base, key = n.func.value.id, n.args[0].value
            elif (isinstance(n, ast.Subscript) and isinstance(n.value, ast.Name)
                  and isinstance(n.slice, ast.Constant)):
                base, key = n.value.id, n.slice.value
            if base is not None and isinstance(key, str):
                accesses.append((base, key))
        holders = {base for base, key in accesses if key in cls.RECORD_MARKS}
        return {key for base, key in accesses if base in holders}

    def _templates(self, lang: str) -> dict[str, str]:
        suffix = ".md" if not lang else f".{lang}.md"
        return {role: (SKILL / "references" / f"{role}{suffix}").read_text(encoding="utf-8")
                for role in self.ROLES}

    @staticmethod
    def _code(text: str) -> str:
        """Только машинная часть шаблона: огороженные блоки и вставки в обратных кавычках.
        Прозу агент не копирует, и объявлением поля она не является."""
        fenced = re.findall(r"^ {0,3}`{3,4}.*?^ {0,3}`{3,4}", text, re.S | re.M)
        spans = re.findall(r"`[^`\n]+`", text)
        return "\n".join(fenced + spans)

    @classmethod
    def _named_in_schema(cls, bodies: dict[str, str], field: str) -> bool:
        return any(re.search(rf'"{re.escape(field)}"\s*:', cls._code(b))
                   for b in bodies.values())

    @classmethod
    def _named_beside_command(cls, bodies: dict[str, str], field: str, command: str) -> bool:
        return any(f"`{command}" in para and f"`{field}`" in para
                   for b in bodies.values() for para in re.split(r"\n\s*\n", b))

    def test_каждое_поле_реестра_названо_в_шаблоне_или_проставлено_инструментом(self):
        unknown = (self._register_fields(TOOL.read_text(encoding="utf-8"))
                   - self.TOOL_FIELDS - self.AGENT_FIELDS)
        self.assertEqual(
            sorted(unknown), [],
            "у находки появилось поле, о котором правило не знает: решите, пишет его агент "
            "(тогда назовите его в шаблонах обеих языковых версий и впишите в AGENT_FIELDS) "
            "или инструмент (TOOL_FIELDS) — иначе ворота будут спрашивать то, чего никто не "
            "объявлял")
        for lang in self.LANGS:
            bodies = self._templates(lang)
            for field in sorted(self.DRAFT_FIELDS):
                with self.subTest(lang=lang or "en", field=field):
                    self.assertTrue(
                        self._named_in_schema(bodies, field),
                        f"поле `{field}` не названо ключом схемы (`\"{field}\":`) ни в одном "
                        f"шаблоне роли ({lang or 'en'}): агент копирует образец, а не прозу — "
                        f"впишите поле в схему черновика того шаблона, чья роль его пишет")
            for field, command in sorted(self.COMMAND_FIELDS.items()):
                with self.subTest(lang=lang or "en", field=field):
                    self.assertTrue(
                        self._named_beside_command(bodies, field, command),
                        f"поле `{field}` инструмент проставляет по флагу `{command}`, и ни "
                        f"один шаблон роли ({lang or 'en'}) не называет их рядом: агент узнает "
                        f"имя поля и не узнает, чем его заполнить")

    def test_проза_поле_не_объявляет_а_ключ_схемы_объявляет(self):
        """Обе стороны правила на выдуманных шаблонах: слово в тексте и то же слово внутри
        пути — не объявление; ключ схемы — объявление, и в огороженном блоке, и в кавычках."""
        prose = {"verify": 'Duplicates — by root, not by text, and the whole root at once.\n'
                           'The path field holds `"file":"path/from/repository/root"`.\n'}
        self.assertFalse(self._named_in_schema(prose, "root"))
        fenced = {"hunter": '```json\n{"block":"H1","root":"имя класса"}\n```\n'}
        self.assertTrue(self._named_in_schema(fenced, "root"))
        span = {"verify": 'дубликаты — `"status":"duplicate","dup_of":"<id основной>"`;\n'}
        self.assertTrue(self._named_in_schema(span, "dup_of"))

    def test_поле_по_флагу_требует_команду_в_том_же_абзаце(self):
        """Вторая сторона для полей, которых в черновике нет: имя поля отдельно от команды,
        которая его пишет, — это имя без способа его заполнить."""
        apart = {"fix": "Причина уходит в `defer_reason`.\n\nОткладывают так: "
                        "`set-finding <ID> deferred --reason '…'`.\n"}
        self.assertFalse(self._named_beside_command(apart, "defer_reason", "set-finding"))
        together = {"fix": "`set-finding <ID> deferred --reason '…'` пишет `defer_reason`.\n"}
        self.assertTrue(self._named_beside_command(together, "defer_reason", "set-finding"))

    def test_словарь_полей_читается_на_выдуманном_исходнике(self):
        """Обе стороны правила на исходнике, которого в инструменте нет: обращение к находке
        любой из трёх форм даёт поле, обращение к чужому словарю — нет."""
        invented = ('def g(rec, other):\n'
                    '    rec.get("claim")\n'
                    '    rec.get("via_get")\n'
                    '    rec.setdefault("via_setdefault", 1)\n'
                    '    rec["via_subscript"]\n'
                    '    other.get("not_a_finding")\n'
                    '    other["neither"]\n')
        self.assertEqual(self._register_fields(invented),
                         {"claim", "via_get", "via_setdefault", "via_subscript"},
                         "запись узнаётся по своим полям, а не по имени переменной")

    def test_шаблоны_ролей_есть_на_обоих_языках(self):
        for lang in self.LANGS:
            for role in self.ROLES:
                suffix = ".md" if not lang else f".{lang}.md"
                self.assertTrue((SKILL / "references" / f"{role}{suffix}").exists(),
                                f"{role}{suffix}")


class NamedExitTest(unittest.TestCase):
    """УЗДА КЛАССА «документ называет выход, которого механизм не даёт».

    Сообщение инструмента и правило шаблона — единственное, откуда агент узнаёт, куда
    писать, каким флагом сузить работу и какой командой выйти из положения. Дважды подряд
    названный выход оказывался не тем, что механизм даёт: `--scope`, который дифф не
    уменьшает, и раздел про охват там, где ворота читают раздел ограничений охвата, —
    отчёт, написанный ровно по предупреждению, ворота отказывали. Список починенных мест
    такое не держит: следующее сообщение напишут копией соседнего.

    Поэтому правило спрашивает КАЖДЫЙ названный выход: раздел — в отчёте той роли,
    которой текст адресован, и такой, который ворота читают; флаг — объявленный точкой
    входа набора; команда — та, у которой есть свой разбор. Кому адресовано сообщение,
    выводится, а не объявляется: ключ `MSG` попадает в промпт через подстановку, а
    подстановку несут шаблоны конкретных ролей.
    """

    ROLES = ("hunter", "verify", "fix", "fixreview")
    LANGS = ("", "ru")
    # Чужая программа объявляет свои флаги сама, и спрашивать их у набора незачем.
    FOREIGN = ("git", "npx", "npm", "python3", "python", "make", "sh", "bash", "pip",
               "ls", "grep", "cd", "claude", "skills-ref")
    # Как текст зовёт сам инструмент: подстановкой, именем из blocks.json, файлом.
    SELF = ("{cli}", "{CLI}", "{{CLI}}", "review", "review.py")
    # Точки входа набора: флаг, названный агенту, обязан быть объявлен одной из них.
    ENTRY_POINTS = ("scripts/review.py", "scripts/axes.py")
    # Чем `check` читает отчёт каждой роли. Имена образцов спрашиваются у инструмента —
    # исчезнувший образец роняет прогон отдельной строкой, а не молча делает раздел
    # «нечитаемым». Отчёт исполнителя и отчёт ревьюера правок проверка не разбирает: она
    # смотрит, что файл есть, — и раздела в них не называет никто.
    REPORT_GATES = {"hunter": ("LIMITS_HEADING", "HYPOTHESIS_HEADING"),
                    "verify": ("COVERAGE_VERDICT", "FINDING_VERDICT")}
    # Название раздела ищется рядом со словом «раздел»: заголовки отчёта — обычные слова
    # («Находки», «Охват»), и без этой пометки правило ловило бы прозу.
    MARK = re.compile(r"section|раздел\w*", re.I)
    QUOTED_NAME = re.compile(r"[\"“«'`]([^\"”»'`\n]{3,60})[\"”»'`]\s*$")
    WORD = re.compile(r"[\w’']+")
    SPAN = re.compile(r"`+([^`\n]+?)`+")
    FLAG = re.compile(r"^--[a-z][\w-]*$")
    # Слово короче трёх букв — служебное («и», «of»), и в названии раздела оно не
    # опознаётся; пяти букв хватает, чтобы «ограничений» и «Ограничения» совпали, а
    # «Охват» и «Ограничения охвата» — разошлись.
    STEM = 5
    # Служебные слова между словом «раздел» и названием: их пропускают, всё остальное
    # обрывает название. Без этого «…что переворачивает половину вердиктов. Раздел,
    # который чаще всего забывают» читалось как упоминание «Находок» через четыре слова.
    GLUE = {"the", "a", "an", "of", "on", "in", "into", "under", "to", "your", "own",
            "its", "this", "that", "my", "report", "reports", "below", "above",
            "в", "во", "об", "о", "про", "по", "своего", "своём", "своем", "этого",
            "отчёта", "отчёте", "отчета", "отчете", "моего", "ниже", "выше"}

    @classmethod
    def _stems(cls, name: str) -> tuple:
        """Слова названия, укороченные до корня: документ склоняет заголовок («раздел
        ограничений охвата») и пишет его через дефис («coverage-limits»), а речь об одном
        и том же названии."""
        return tuple(w[:cls.STEM].lower() for w in cls.WORD.findall(name) if len(w) > 2)

    @classmethod
    def _skeleton(cls, template: str) -> list[str]:
        """Заголовки скелета отчёта — того, что шаблон роли даёт агенту скопировать."""
        for block in re.findall(r"^ {0,3}`{3,4}\w*\n(.*?)^ {0,3}`{3,4}\s*$", template,
                                re.S | re.M):
            if re.match(r"^#\s+\{\{BLOCK_ID\}\}", block):
                return [re.sub(r"^#+\s*", "", ln).strip()
                        for ln in block.splitlines() if re.match(r"^#{2,6}\s+\S", ln)]
        return []

    @staticmethod
    def _assigned(node) -> str | None:
        """Имя, которому модуль присваивает значение: `X = …` и `X: тип = …` — одно и то же
        присваивание, и правило, знавшее только первую запись, от второй слепло бы."""
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            return node.targets[0].id
        if (isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
                and node.value is not None):
            return node.target.id
        return None

    @classmethod
    def _patterns(cls, tree: ast.Module) -> dict:
        """Образцы инструмента — из его же исходника. Своя копия выражения разъехалась бы
        с воротами молча, и узда объявляла бы читаемым раздел, который никто не читает."""
        out = {}
        for node in tree.body:
            name = cls._assigned(node)
            if (name and isinstance(node.value, ast.Call)
                    and ast.unparse(node.value.func) == "re.compile"
                    and node.value.args and isinstance(node.value.args[0], ast.Constant)):
                flags = re.I if "IGNORECASE" in ast.unparse(node.value) else 0
                out[name] = re.compile(node.value.args[0].value, flags)
        return out

    @classmethod
    def _vocabulary(cls, trees: dict) -> tuple[set, set]:
        """Что механизм действительно даёт: флаги и команды точек входа.

        Точка входа с подкомандами объявляет флаги через `add_argument`; та, что разбирает
        `sys.argv` руками (`axes.py`), — обычной строкой, и брать её строки у первой
        нельзя: у инструмента в списках лежат флаги git.
        """
        flags, commands = set(), set()
        for tree in trees.values():
            calls = [n for n in ast.walk(tree)
                     if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)]
            has_parser = any(c.func.attr == "add_parser" for c in calls)
            for c in calls:
                if c.func.attr == "add_argument":
                    flags |= {a.value for a in c.args if isinstance(a, ast.Constant)
                              and isinstance(a.value, str) and cls.FLAG.match(a.value)}
                if c.func.attr == "add_parser" and c.args and isinstance(c.args[0], ast.Constant):
                    commands.add(c.args[0].value)
            if not has_parser:
                flags |= {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant)
                          and isinstance(n.value, str) and cls.FLAG.match(n.value)}
        return flags, commands

    @classmethod
    def _readers(cls, tree: ast.Module, docs: dict) -> dict:
        """Ключ `MSG` → роли, которые это сообщение прочитают.

        Выводится, а не объявляется: сообщение печатает функция, функцию зовёт `cmd_prompt`
        под именем подстановки, подстановку несут шаблоны конкретных ролей. Поэтому и
        обратный снос ловится: подстановку добавили в шаблон роли, у чьего отчёта такого
        раздела нет, — и правило краснеет, хотя ни одного сообщения не трогали.
        """
        emitted, placeholder = {}, {}
        for fn in ast.walk(tree):
            if not isinstance(fn, ast.FunctionDef):
                continue
            for n in ast.walk(fn):
                if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                        and n.func.id == "T" and n.args):
                    continue
                key = n.args[0]
                if isinstance(key, ast.Constant):
                    emitted.setdefault(fn.name, []).append((key.value, None))
                elif isinstance(key, ast.IfExp):
                    # `T("...verify" if role == "verify" else "...")` — домашняя запись
                    # роль-зависимого сообщения (так же написан `proof_rule`).
                    role = next((c.value for c in ast.walk(key.test)
                                 if isinstance(c, ast.Constant) and isinstance(c.value, str)), None)
                    for branch, only in ((key.body, role), (key.orelse, ("not", role))):
                        if isinstance(branch, ast.Constant):
                            emitted.setdefault(fn.name, []).append((branch.value, only))
        for n in ast.walk(tree):
            if not isinstance(n, ast.Dict):
                continue
            for k, v in zip(n.keys, n.values):
                if isinstance(k, ast.Constant) and isinstance(k.value, str) \
                        and k.value.startswith("{{"):
                    for c in ast.walk(v):
                        if isinstance(c, ast.Call) and isinstance(c.func, ast.Name):
                            placeholder[c.func.id] = k.value
        out = {}
        for fn, items in emitted.items():
            ph = placeholder.get(fn)
            if not ph:
                continue
            carry = {r for r in cls.ROLES if ph in docs.get(f"references/{r}.md", "")}
            for key, only in items:
                roles = set(carry)
                if isinstance(only, str):
                    roles &= {only}
                elif isinstance(only, tuple):
                    roles -= {only[1]}
                out[key] = roles
        return out

    @classmethod
    def _texts(cls, tree: ast.Module, docs: dict) -> list:
        """Корпус: (где, текст, кто прочитает, язык). Сообщения инструмента — из `MSG` и
        из отказов; строки документации набора — целиком, шаблон роли со своей ролью."""
        readers = cls._readers(tree, docs)
        out, seen = [], set()
        for node in ast.walk(tree):
            if not (cls._assigned(node) == "MSG" and isinstance(node.value, ast.Dict)):
                continue
            for lang_key, table in zip(node.value.keys, node.value.values):
                lang = "" if lang_key.value == "en" else lang_key.value
                for k, v in zip(table.keys, table.values):
                    if isinstance(v, ast.Constant) and isinstance(v.value, str):
                        seen.add(id(v))
                        out.append((f"MSG[{lang_key.value}][{k.value}]", v.value,
                                    readers.get(k.value), lang))
        docstrings, inner = set(), set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef)) \
                    and ast.get_docstring(node) is not None:
                docstrings.add(id(node.body[0].value))
            if isinstance(node, ast.JoinedStr):
                inner |= {id(p) for p in ast.walk(node) if p is not node}
        for node in ast.walk(tree):
            if id(node) in docstrings or id(node) in inner or id(node) in seen:
                continue
            if isinstance(node, ast.JoinedStr):
                # Отказ собирают f-строкой, и имя раздела в ней разорвано подстановкой:
                # части склеиваются обратно, иначе команду `{CLI} init` не видно.
                text = "".join(p.value if isinstance(p, ast.Constant)
                               else "{" + ast.unparse(p.value) + "}" for p in node.values)
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                text = node.value
            else:
                continue
            # Короткая строка — имя поля или ключ, а не обращение к человеку.
            if len(text) > 40:
                out.append((f"review.py:{node.lineno}", text, None, ""))
        for name, text in docs.items():
            lang = "ru" if name.endswith(".ru.md") else ""
            role = re.fullmatch(r"references/(\w+?)(?:\.ru)?\.md", name)
            who = {role.group(1)} if role and role.group(1) in cls.ROLES else None
            out.append((name, text, who, lang))
        return out

    @classmethod
    def _mentions(cls, text: str, known: dict) -> list:
        """Где текст называет раздел отчёта — по слову «раздел» рядом с названием.

        Название в кавычках берётся целиком («What is NOT a finding» — раздел инвариантов,
        а не отчёта, и совпасть ни с чем не должен). Без кавычек название обязано ПРИМЫКАТЬ
        к слову «раздел» через служебные слова, и берётся самый ДЛИННЫЙ совпавший
        заголовок, иначе «coverage-limits» читается как «Coverage».
        """
        out = []
        for m in cls.MARK.finditer(text):
            # Только свой абзац: за пустой строкой стоит соседний, и его последнее слово
            # («## Контекст, меняющий оценку находок») названием этого раздела не является.
            before = re.split(r"\n\s*\n", text[:m.start()])[-1]
            after = re.split(r"\n\s*\n", text[m.end():])[0]
            quoted = cls.QUOTED_NAME.search(before[-80:])
            if not quoted and after[:1].strip() == "" and after.lstrip()[:1] in "\"“«'`":
                quoted = re.match(r"[\"“«'`]([^\"”»'`\n]{3,60})[\"”»'`]", after.lstrip())
            if quoted:
                hit = [h for h in known if cls._stems(h) == cls._stems(quoted.group(1))]
                out += [(quoted.group(1), h) for h in hit[:1]]
                continue
            tail = cls.WORD.findall(before)
            while tail and tail[-1].lower() in cls.GLUE:
                tail.pop()
            head_side = cls.WORD.findall(after)
            while head_side and head_side[0].lower() in cls.GLUE:
                head_side.pop(0)
            best = None
            for head in known:
                st = cls._stems(head)
                if not st:
                    continue
                for run in (tail[-len(st):], head_side[:len(st)]):
                    if len(run) == len(st) and cls._stems(" ".join(run)) == st:
                        if best is None or len(st) > len(cls._stems(best[1])):
                            best = (" ".join(run), head)
            if best:
                out.append(best)
        return out

    @classmethod
    def _named_exits(cls, sources: dict, docs: dict) -> list[str]:
        """Названные выходы, которых механизм не даёт: раздел, флаг, команда.

        Исходники разбираются здесь, один раз: помощники получают готовое дерево, и правило
        у набора одно — то, что выносит приговор, — а не каждый, кто читает его куски.
        """
        trees = {name: ast.parse(src) for name, src in sources.items()}
        tool = trees["scripts/review.py"]
        patterns = cls._patterns(tool)
        flags, commands = cls._vocabulary(trees)
        bad = []
        gates = {}
        for role, named in cls.REPORT_GATES.items():
            for gate in named:
                if gate not in patterns:
                    bad.append(f"{gate}: образца, которым `check` читает отчёт роли "
                               f"{role}, в инструменте нет — перепишите REPORT_GATES под "
                               f"новое имя, иначе узда считает раздел нечитаемым")
            gates[role] = [patterns[g] for g in named if g in patterns]
        skeleton, readable = {}, {}
        for lang in cls.LANGS:
            for role in cls.ROLES:
                suffix = ".md" if not lang else f".{lang}.md"
                heads = cls._skeleton(docs.get(f"references/{role}{suffix}", ""))
                skeleton[(role, lang)] = heads
                readable[(role, lang)] = [h for h in heads
                                          if any(g.search("## " + h) for g in gates.get(role, []))]
        for where, text, who, lang in cls._texts(tool, docs):
            known = {h for (role, l), heads in skeleton.items() if l == lang for h in heads}
            for name, head in cls._mentions(text, known):
                owners = {r for r in cls.ROLES if head in skeleton[(r, lang)]}
                if who is None:
                    # Текст без адресата — общий документ набора: он описывает метод, и
                    # названный раздел обязан читаться хоть у кого-то.
                    if not any(head in readable[(r, lang)] for r in owners):
                        bad.append(f"{where}: «{name}» — раздел, которого `check` не читает "
                                   f"ни в одном отчёте")
                    continue
                for role in sorted(who):
                    if head in readable[(role, lang)]:
                        continue
                    reads = ", ".join(sorted(readable[(role, lang)]) or ["ничего"])
                    bad.append(
                        f"{where}: «{name}» — раздел, которого отчёт роли {role} не имеет"
                        if role not in owners else
                        f"{where}: «{name}» — раздел отчёта роли {role}, которого `check` "
                        f"не читает; читает: {reads}")
            for span in cls.SPAN.findall(text):
                tokens = span.split()
                if not tokens or tokens[0] in cls.FOREIGN or tokens[0].endswith(".sh"):
                    continue
                rest = tokens
                if tokens[0] in cls.SELF:
                    rest = tokens[1:]
                    if rest and re.fullmatch(r"[a-z][a-z-]+", rest[0]) and rest[0] not in commands:
                        bad.append(f"{where}: `{span}` — команды `{rest[0]}` у инструмента "
                                   f"нет; есть: {', '.join(sorted(commands))}")
                elif tokens[0] in commands:
                    rest = tokens[1:]
                for token in rest:
                    token = token.strip(",.;:)»")
                    if cls.FLAG.match(token) and token not in flags:
                        bad.append(f"{where}: `{span}` — флага `{token}` не объявляет ни "
                                   f"одна точка входа набора")
        return sorted(bad)

    @classmethod
    def _sources(cls) -> dict:
        return {name: (SKILL / name).read_text(encoding="utf-8") for name in cls.ENTRY_POINTS}

    @classmethod
    def _documents(cls) -> dict:
        return {p.relative_to(SKILL).as_posix(): p.read_text(encoding="utf-8")
                for p in sorted(SKILL.rglob("*.md"))}

    def test_каждый_названный_агенту_выход_механизм_действительно_даёт(self):
        """УЗДА КЛАССА «документ называет выход, которого механизм не даёт».

        Предупреждение о непомерном блоке звало охотника назвать непрочитанное в разделе
        про охват, а ворота читают раздел ограничений охвата: отчёт, написанный ровно по
        предупреждению, ворота отказывали — на обоих языках. Правило накрывает корень
        целиком: все сообщения инструмента и все документы скилла, а не найденные места.
        """
        self.assertEqual(
            self._named_exits(self._sources(), self._documents()), [],
            "текст называет агенту выход, которого механизм не даёт: раздел, которого "
            "ворота в отчёте этой роли не читают, несуществующий флаг или команду")

    # Порча по одной на строку: сообщение называет соседний раздел, раздел чужой роли,
    # несуществующий флаг, несуществующую команду. Каждая — то, как этот класс уже
    # появлялся, и на каждой правило обязано покраснеть.
    SPOILED = {
        "соседний раздел (en)": ("in the coverage-limits section of your report",
                                 "in the coverage section of your report"),
        "соседний раздел (ru)": ("в разделе своего отчёта об ограничениях охвата",
                                 "в разделе своего отчёта про охват"),
        "раздел чужой роли": ("in the block-coverage-status section",
                              "in the coverage-limits section"),
        "несуществующий флаг": ("`--diff <first part>`", "`--scope-half <first part>`"),
        "несуществующая команда": ("`{cli} findings`", "`{cli} finding-list`"),
    }

    def test_узда_краснеет_на_каждой_порче_сообщения(self):
        """Страж доказывается мутацией: на неиспорченном исходнике он молчит (тест выше),
        на каждой порче — называет её. Порча ставится в КОПИИ исходника."""
        docs = self._documents()
        for why, (was, now) in self.SPOILED.items():
            spoiled = dict(self._sources())
            source = spoiled["scripts/review.py"]
            self.assertIn(was, source, f"порча «{why}» ставится мимо исходника: {was!r}")
            spoiled["scripts/review.py"] = source.replace(was, now)
            with self.subTest(порча=why):
                compile(spoiled["scripts/review.py"], "review.py", "exec")
                self.assertNotEqual(self._named_exits(spoiled, docs), [],
                                    "узда не увидела порчи")

    def test_узда_краснеет_когда_замер_уезжает_в_чужую_роль(self):
        """Снос с другой стороны: сообщение не трогали, а подстановку с ним добавили в
        шаблон роли, у чьего отчёта названного раздела нет. Адресат выводится из шаблонов,
        поэтому такое правило видит."""
        docs = dict(self._documents())
        self.assertNotIn("{{VOLUME}}", docs["references/fix.md"])
        docs["references/fix.md"] += "\n# Volume of work\n\n{{VOLUME}}\n"
        self.assertNotEqual(self._named_exits(self._sources(), docs), [],
                            "узда не увидела, что замер уехал к роли без такого раздела")

    # Вторая сторона: что правило обязано ПРОПУСКАТЬ. Иначе первая же переформулировка
    # сообщения окажется «нарушением», и узду снимут.
    INNOCENT = {
        "другими словами про тот же раздел": (
            "in the coverage-limits section of your report",
            "in the section on coverage limits of your report"),
        "раздел инвариантов, а не отчёта": (
            "Do not pretend you read it.",
            "Do not pretend you read it. The “What is NOT a finding” section of the "
            "invariants is mandatory."),
        "флаг чужой программы": (
            "Do not pretend you read it.",
            "Do not pretend you read it. Compare with `git log HEAD..origin/master "
            "--oneline` first."),
        "команда и флаг, которые есть": (
            "Do not pretend you read it.",
            "Do not pretend you read it. The lead splits the block: `{cli} coverage "
            "--no-write`."),
    }

    def test_узда_пропускает_верно_названный_выход(self):
        docs = self._documents()
        for why, (was, now) in self.INNOCENT.items():
            innocent = dict(self._sources())
            source = innocent["scripts/review.py"]
            self.assertIn(was, source, f"образец «{why}» ставится мимо исходника")
            innocent["scripts/review.py"] = source.replace(was, now, 1)
            with self.subTest(образец=why):
                self.assertEqual(self._named_exits(innocent, docs), [],
                                 "узда придирается к верно названному выходу")

    # Фраза, а не имя флага: `"--scope"` в add_argument — это объявление, а не текст,
    # который человек читает. Порог отсекает его и оставляет предложения.
    SCOPE_PHRASE = 40

    @classmethod
    def _scope_without_diff(cls, source: str) -> list[tuple[int, str]]:
        """Строки инструмента, которые называют `--scope` и молчат про `--diff`: (строка, текст).

        Второй экземпляр того же класса: флаг существует, но делает не то, за чем его
        зовут, — правило выше такое не ловит, оно спрашивает словарь, а не смысл.
        """
        return sorted((node.lineno, node.value) for node in ast.walk(ast.parse(source))
                      if isinstance(node, ast.Constant) and isinstance(node.value, str)
                      and "--scope" in node.value and len(node.value) > cls.SCOPE_PHRASE
                      and "--diff" not in node.value)

    def test_везде_где_назван_scope_назван_и_флаг_уменьшающий_дифф(self):
        """УЗДА КЛАССА «документ называет выход, которого механизм не даёт».

        `--scope` дифф не уменьшает: промпт с ним на 120 байт БОЛЬШЕ. Любой текст,
        предлагающий его там, где речь об объёме, обязан назвать рядом `--diff` — флаг,
        который единственный и уменьшает. Правило накрывает и то, что ещё не написано:
        строки инструмента и документы скилла целиком, а не четыре найденных места.
        """
        offenders = [f"{TOOL.name}:{n}"
                     for n, _ in self._scope_without_diff(TOOL.read_text(encoding="utf-8"))]
        for path in sorted(SKILL.rglob("*.md")):
            for para in re.split(r"\n\s*\n", path.read_text(encoding="utf-8")):
                if "--scope" in para and "--diff" not in para:
                    offenders.append(path.relative_to(SKILL).as_posix())
        self.assertEqual(offenders, [],
                         "`--scope` назван без `--diff` рядом: он делит ответственность за "
                         "отчёт и не уменьшает дифф, и текст, предлагающий его как выход из "
                         "объёма, посылает за тем, чего механизм не даёт — " + "; ".join(offenders))

    def test_правило_про_scope_читается_на_выдуманном_исходнике(self):
        """Обе стороны правила на исходнике, которого в инструменте нет."""
        guilty = ('MSG = {"vol": "не помещается — возьми половину через `--scope <половина>`,'
                  ' ведущая запустит второго"}\n')
        self.assertEqual([n for n, _ in self._scope_without_diff(guilty)], [1])
        innocent = ('MSG = {"vol": "не помещается — проси более узкий `--diff`; `--scope` '
                    'называет половину в отчёте"}\n'
                    'c.add_argument("--scope", help="половина правок этого ревьюера")\n')
        self.assertEqual(self._scope_without_diff(innocent), [],
                         "имя флага и текст, который называет оба флага, — не нарушение")

    def test_узда_читает_образцы_ворот_у_инструмента(self):
        """Без этого правило молча объявило бы нечитаемым любой раздел: имена образцов
        записаны здесь, а выражения — в инструменте, и разъехаться им нельзя."""
        said = self._named_exits(self._sources(), self._documents())
        for role, named in self.REPORT_GATES.items():
            for gate in named:
                with self.subTest(роль=role, образец=gate):
                    self.assertEqual([b for b in said if b.startswith(f"{gate}:")], [],
                                     f"{gate} в инструменте не найден")
        docs = self._documents()
        for role, lang, expect in (("hunter", "", "Coverage limits"),
                                   ("hunter", "ru", "Ограничения охвата"),
                                   ("verify", "", "Block coverage status"),
                                   ("verify", "ru", "Состояние охвата блока")):
            suffix = ".md" if not lang else f".{lang}.md"
            heads = self._skeleton(docs[f"references/{role}{suffix}"])
            with self.subTest(роль=role, язык=lang or "en"):
                self.assertIn(expect, heads, "скелет отчёта роли прочитан неверно")


class DraftByTheTemplateTest(unittest.TestCase):
    """Черновик находок, написанный ровно по шаблону, проходит `import` и `check`.

    Обратная сторона узды: правило выше держит, что поле названо, а это — что запись,
    сделанная по названному образцу, не роняет ворота.
    """

    def setUp(self) -> None:
        self.s = Stand()
        self.addCleanup(self.s.cleanup)
        for i in range(4):
            self.s.write(f"src/f{i}.ts", "a\n")
        self.s.blocks(paths=["src"])
        self.s.manifest(hypotheses=1)

    def draft(self, *rows: dict) -> None:
        self.s.write("docs/review/reports/H1-findings.jsonl",
                     "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))

    def row(self, n: int, **extra) -> dict:
        return {"block": "H1", "severity": "medium", "confidence": "confirmed",
                "status": "open", "file": f"src/f{n}.ts", "line": 1,
                "claim": f"рукописная копия предиката {n}", "scenario": "на границе",
                **extra}

    def _import(self) -> None:
        self.s.commit()
        self.s.run("init")
        self.s.run("coverage")
        out = self.s.run("import", "H1")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.s.run("findings")

    def test_корень_из_образца_собирает_класс_и_зажигает_ворота_про_узду(self):
        klass = "рукописная копия предиката"
        self.draft(*(self.row(i, root=klass) for i in range(3)))
        self._import()
        self.assertIn("3 × " + klass, self.s.run("roots").stdout)
        self.assertIn("and no guard", refused(self.s.run("check")),
                      "три экземпляра одного корня обязаны потребовать узду — отказом, "
                      "а не предупреждением")

    def test_без_поля_root_тот_же_черновик_ворота_не_зажигает(self):
        """Мера дефекта: ровно те же три находки без `root` не группируются никак."""
        self.draft(*(self.row(i) for i in range(3)))
        self._import()
        self.assertIn("no roots recorded", self.s.run("roots").stdout)
        self.assertNotIn("and no guard", self.s.run("check").stdout)

    def test_отказ_написанный_по_образцу_не_роняет_проверку(self):
        self.draft(self.row(0, status="rejected", confidence="rejected",
                            reject_reason="маршрут обёрнут в RequirePermission, сценарий недостижим"),
                   self.row(1))
        self._import()
        out = self.s.run("check")
        self.assertNotIn("reject reason is not recorded", out.stdout)
        self.assertEqual(out.returncode, 0, out.stdout)

    def test_отказ_с_причиной_только_в_claim_по_прежнему_ловится(self):
        """Вторая сторона: причина, спрятанная в заголовке, — не запись причины."""
        self.draft(self.row(0, status="rejected", confidence="rejected",
                            claim="дефекта нет: маршрут обёрнут в RequirePermission"))
        self._import()
        self.assertIn("reject reason is not recorded", refused(self.s.run("check")),
                      "причина, спрятанная в заголовке, обязана ронять проверку, "
                      "а не печататься предупреждением")

    def test_дубль_написанный_по_образцу_не_роняет_проверку(self):
        self.draft(self.row(0), self.row(1, status="duplicate", dup_of="H1-001"))
        self._import()
        out = self.s.run("check")
        self.assertNotIn("marked duplicate", out.stdout)
        self.assertEqual(out.returncode, 0, out.stdout)


class ShippedSampleTest(unittest.TestCase):
    """УЗДА КЛАССА «образец, который инструмент сам отвергает».

    На образцы ссылаются и `SKILL.md`, и три отказа `check_definition`, и README примера:
    их открывают первыми и по ним делают своё. Найдено четыре штуки сразу — пример
    `examples/toy` не проходил `check` по двум причинам, называл номер находки в коде,
    а `blocks.example.json` нарушал порядок фаз, — то есть единственное показательное
    состояние ревью учило тому, что набор запрещает. Список мест такое не держит: правило
    гоняет сами ворота по тому, что уезжает пользователю.
    """

    def stand(self, src: Path) -> Path:
        root = Path(tempfile.mkdtemp(prefix="finetooth-sample-"))
        self.addCleanup(shutil.rmtree, root, True)
        shutil.copytree(src, root, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("__pycache__"))
        for cmd in (["init", "-q", "."], ["config", "user.email", "t@example.com"],
                    ["config", "user.name", "t"], ["add", "-A"], ["commit", "-qm", "sample"]):
            subprocess.run(["git", "-C", str(root), *cmd], capture_output=True, check=True,
                           env=child_env())
        return root

    def run_in(self, root: Path, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(TOOL), *args], cwd=root,
                              capture_output=True, text=True, env=child_env())

    def test_пример_toy_проходит_ворота_как_обещает_его_README(self):
        """README примера велит скопировать его в свежий репозиторий и позвать `check`."""
        root = self.stand(KIT / "examples" / "toy")
        for cmd in (("check",), ("refs",), ("coverage", "--no-write")):
            out = self.run_in(root, *cmd)
            self.assertEqual(out.returncode, 0,
                             f"`{' '.join(cmd)}` на примере: " + out.stdout + out.stderr)

    def test_образец_определения_блоков_проходит_ворота(self):
        """`blocks.example.json` — то, на что показывают три отказа самого инструмента."""
        root = self.stand(KIT / "examples" / "toy")
        shutil.rmtree(root / "docs" / "review")
        (root / "docs" / "review" / "blocks").mkdir(parents=True)
        (root / "docs" / "review" / "reports").mkdir(parents=True)
        d = json.loads((SKILL / "assets" / "blocks.example.json").read_text(encoding="utf-8"))
        # Пути образца обобщены и в этом дереве не существуют; ворота про мёртвый шаблон
        # проверяются своим тестом, а здесь проверяется само определение.
        d["exclusions"] = [{"pattern": "docs/review", "reason": "аппарат"},
                           {"pattern": "README.md", "reason": "не код"},
                           {"pattern": ".gitignore", "reason": "не код"}]
        for b in d["blocks"]:
            b["paths"] = ["src", "tests"] if b["paths"] else []
            b["ref_paths"] = []
        (root / "docs/review/blocks.json").write_text(
            json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "-A"], capture_output=True, check=True,
                       env=child_env())
        subprocess.run(["git", "-C", str(root), "commit", "-qm", "sample definition"],
                       capture_output=True, check=True, env=child_env())
        self.assertEqual(self.run_in(root, "init").returncode, 0)
        out = self.run_in(root, "check")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)

    def test_ворота_про_порядок_фаз_живы(self):
        """Обратная сторона: переставленный образец по-прежнему краснеет."""
        root = self.stand(KIT / "examples" / "toy")
        bj = root / "docs/review/blocks.json"
        d = json.loads(bj.read_text(encoding="utf-8"))
        d["blocks"].reverse()
        bj.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "commit", "-qam", "phases"],
                       capture_output=True, check=True, env=child_env())
        self.assertIn("comes after phase", self.run_in(root, "check").stdout)


class BilingualAssetTest(unittest.TestCase):
    """УЗДА КЛАССА «перевод, который не переведён, и подсказка не из CLI».

    Договор двуязычия: строка, которая есть на одном языке и нет на другом, — дефект.
    Русский баннер нёс английский текст слово в слово (переведено было только пояснение
    вокруг), а `setup --lang ru` называл в своём списке дел английские образцы — и четыре
    русских файла набора не были упомянуты нигде. Рядом второй класс: тот же баннер
    вписывал `make review-status` намертво, и проект без Makefile рассылал каждой своей
    сессии несуществующую команду.
    """

    WORD = re.compile(r"[A-Za-z]{3,}")
    CYRILLIC = re.compile(r"[А-Яа-яЁё]")
    # Ассеты, которые уезжают в чужой проект и читаются там человеком и агентом: команду
    # они обязаны брать из {{CLI}}. Образцы целей сборки (`makefile-snippet.mk`,
    # `package-json-snippet.json`) — наоборот, сами и есть эти команды.
    HANDED_OVER = ("entry-point", "agent-banner")
    PROJECT_COMMANDS = re.compile(r"\b(make review|npm run review|just review)")

    def ru_pairs(self) -> list[tuple[Path, Path]]:
        out = []
        for d in ("references", "assets"):
            for ru in sorted((SKILL / d).glob("*.ru.*")):
                en = ru.with_name(ru.name.replace(".ru.", ".", 1))
                self.assertTrue(en.exists(), f"{ru.name} без английского оригинала")
                out.append((en, ru))
        return out

    def english_prose(self, text: str) -> list[str]:
        """Строки без единой кириллической буквы, которые при этом являются прозой.

        Команда, путь и код по-английски и должны быть; пять и больше слов подряд вне
        ограды и вне обратных кавычек — это непереведённый текст.
        """
        out, fenced = [], False
        for line in text.splitlines():
            if line.lstrip().startswith(("```", "~~~")):
                fenced = not fenced
                continue
            if fenced or self.CYRILLIC.search(line):
                continue
            bare = re.sub(r"`[^`]*`", " ", re.sub(r"https?://\S+", " ", line))
            if len(self.WORD.findall(bare)) >= 5:
                out.append(line)
        return out

    def test_русская_копия_действительно_переведена(self):
        pairs = self.ru_pairs()
        self.assertGreater(len(pairs), 5, "русских копий стало подозрительно мало")
        for en, ru in pairs:
            with self.subTest(file=ru.name):
                left = self.english_prose(ru.read_text(encoding="utf-8"))
                self.assertEqual(
                    left[:3], [],
                    f"{ru.name}: {len(left)} строк английской прозы — суффикс .ru для того "
                    f"и нужен, чтобы вставляли перевод, а не оригинал")

    def test_ассеты_для_чужого_проекта_берут_команду_из_подстановки(self):
        for name in self.HANDED_OVER:
            for path in sorted((SKILL / "assets").glob(f"{name}*")):
                with self.subTest(file=path.name):
                    text = path.read_text(encoding="utf-8")
                    hit = self.PROJECT_COMMANDS.search(text)
                    self.assertIsNone(
                        hit, f"{path.name} называет команду конкретного проекта "
                             f"({hit.group(0) if hit else ''}) — подсказки собираются из CLI")
                    self.assertIn("{{CLI}}", text,
                                  f"{path.name} не берёт команду проекта ниоткуда")

    def test_образцы_целей_сборки_команду_называть_обязаны(self):
        """Обратная сторона правила: снипеты целей и есть эти команды."""
        self.assertRegex((SKILL / "assets" / "makefile-snippet.mk").read_text(encoding="utf-8"),
                         r"review-status")
        self.assertIn("review", json.loads(
            (SKILL / "assets" / "package-json-snippet.json").read_text(encoding="utf-8"))["scripts"])


class SetupLanguageTest(unittest.TestCase):
    """`setup --lang ru` называет русские образцы, а баннер печатает готовым к вставке."""

    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="finetooth-setup-lang-"))
        self.addCleanup(shutil.rmtree, self.root, True)
        subprocess.run(["git", "init", "-q", "-b", "master", str(self.root)], check=True,
                       env=child_env())
        for k, v in (("user.email", "t@example.com"), ("user.name", "t")):
            subprocess.run(["git", "-C", str(self.root), "config", k, v], check=True,
                           env=child_env())
        (self.root / "app.ts").write_text("x\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.root), "add", "-A"], check=True, env=child_env())
        subprocess.run(["git", "-C", str(self.root), "commit", "-qm", "init"], check=True,
                       env=child_env())

    def setup(self, *extra: str) -> str:
        out = subprocess.run([sys.executable, str(TOOL), "setup", *extra], cwd=self.root,
                             capture_output=True, text=True, env=child_env())
        self.assertEqual(out.returncode, 0, out.stderr)
        return out.stdout

    def named_assets(self, text: str) -> list[str]:
        # Каталог образцов — тот, что рядом с ИСПЫТУЕМЫМ инструментом, а не путь с сегментом
        # `skills`: скилл ставят куда угодно, а копия мутационной узды лежит в `<tmp>/finetooth`.
        assets = re.escape(str(TOOL.resolve().parent.parent / "assets") + os.sep)
        return re.findall(assets + r"([\w.\-]+)", text)

    def test_русское_ревью_получает_русские_образцы(self):
        out = self.setup("--lang", "ru", "--project", "Проект", "--cli", "npm run review --")
        named = self.named_assets(out)
        self.assertTrue(named, "список дел перестал называть образцы: " + out)
        for name in named:
            with self.subTest(asset=name):
                self.assertTrue((SKILL / "assets" / name).exists(), name)
                ru_name = re.sub(r"\.(\w+)$", r".ru.\1", name.replace(".ru.", ".", 1))
                if (SKILL / "assets" / ru_name).exists():
                    self.assertEqual(name, ru_name,
                                     f"русскому ревью назван английский образец {name}")
        # Точку входа setup не называет, а переносит: её достижимость видна в том, что
        # записано на диск.
        self.assertIn("# Сплошное ревью Проект",
                      (self.root / "docs/review/README.md").read_text(encoding="utf-8"),
                      "точка входа взята не на языке ревью")
        # Остальные русские ассеты обязаны быть названы: иначе они едут в поставке, и
        # найти их пользователю неоткуда — ровно так и жили четыре из них.
        for ru in sorted((SKILL / "assets").glob("*.ru.*")):
            if ru.name.startswith("entry-point"):
                continue
            self.assertIn(ru.name, named, f"{ru.name} не назван ничем в наборе")

    @unittest.skipIf(os.environ.get("FINETOOTH_TOOL"), "прогон уже идёт на копии скилла")
    def test_образцы_находятся_у_скилла_в_каталоге_с_любым_именем(self):
        """Скилл живёт «где угодно» — и тесты образцов обязаны это выдерживать. Прежде они
        искали в выводе сегмент `/skills/finetooth/`, и на копии в `<tmp>/finetooth` — ровно
        там, куда кладёт скилл мутационная узда, — краснели оба, ничего не сломав."""
        with tempfile.TemporaryDirectory(prefix="finetooth-elsewhere-") as d:
            skill = Path(d, "tools", "review-kit")
            shutil.copytree(SKILL, skill, ignore=shutil.ignore_patterns("__pycache__"))
            out = subprocess.run(
                [sys.executable, "-m", "unittest", "discover", "-s", str(KIT / "tests"),
                 "-k", "test_русское_ревью_получает_русские_образцы",
                 "-k", "test_английское_ревью_получает_английские_образцы"],
                cwd=KIT, capture_output=True, text=True,
                env=child_env(FINETOOTH_TOOL=str(skill / "scripts" / "review.py")))
        self.assertIn("Ran 2 tests", out.stderr, out.stderr[-500:])
        self.assertEqual(out.returncode, 0, out.stderr[-2000:])

    def test_английское_ревью_получает_английские_образцы(self):
        """Вторая сторона: русские копии не должны протечь в английский список дел."""
        named = self.named_assets(self.setup("--project", "Demo"))
        self.assertTrue(named)
        for name in named:
            self.assertNotIn(".ru.", name, f"английскому ревью назван русский образец {name}")

    def test_баннер_печатается_готовым_и_с_командой_проекта(self):
        out = self.setup("--project", "Demo", "--cli", "npm run review --")
        self.assertIn("npm run review -- status", out,
                      "баннер обязан называть команду, которой проект зовёт инструмент")
        self.assertIn("A whole-repository review of Demo is in progress", out)
        self.assertNotIn("{{", out, "в напечатанном баннере не осталось подстановок")
        ru = self.setup("--lang", "ru", "--project", "Проект")
        self.assertIn("Идёт сплошное ревью проекта Проект", ru)
        self.assertNotIn("{{", ru)


class DocumentedSurfaceTest(unittest.TestCase):
    """УЗДА КЛАССА «документация отстала от инструмента».

    Три места сразу: `roots` — вид на класс дефекта, на который опираются ворота про третий
    экземпляр, — не называли ни сообщения инструмента, ни `SKILL.md`, ни точка входа, и
    узнать о ней было неоткуда; `--round` у исполнителя был настоящим и недокументированным,
    из-за чего второй круг затирал отчёт первого, а ревьюер правок того круга смотрел на
    файл, который никто не писал; сама точка входа не знала ни роли fixreview, ни ворот
    починки. Список команд берётся из ИСХОДНИКА: команда, которой ещё нет, тоже обязана
    быть названа.
    """

    @staticmethod
    def subcommands(source: str) -> list[str]:
        """Команды инструмента — из его исходника, а не из `--help`.

        Имя команды читается там, где его СОБРАЛИ: имя, вынесенное в переменную, — та же
        команда, и правило, знавшее один литерал в доводе, о ней бы не узнало. Исходник
        правилу передают, а не читают внутри: иначе его нечем покормить, кроме уже
        написанного кода, и мутацией оно не доказано.
        """
        vals = _Values(source)
        out = set()
        for n in ast.walk(vals.tree):
            if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                    and n.func.attr == "add_parser" and n.args):
                continue
            try:
                name = vals.literal(n.args[0])
            except (ValueError, TypeError, SyntaxError):
                continue
            if isinstance(name, str):
                out.add(name)
        return sorted(out)

    def test_каждая_команда_инструмента_названа_в_skill_md(self):
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        # Названа — значит показана КОМАНДОЙ: слова `version` и `hypotheses` встречаются в
        # прозе сами по себе, и правило, читающее их как упоминание команды, пропустило бы
        # обе (измерено на прежнем SKILL.md).
        missing = [c for c in self.subcommands(TOOL.read_text(encoding="utf-8"))
                   if not re.search(rf"review(?:\.py)?\s+{re.escape(c)}\b", text)]
        self.assertEqual(
            missing, [],
            "команды инструмента, которых нет в SKILL.md: ведущая сессия читает его и точку "
            "входа — о том, чего там нет, она не узнает ниоткуда")

    def test_узда_видит_команду_имя_которой_собрали_заранее(self):
        """Обе стороны правила на исходниках, которых в инструменте нет: команда, чьё имя
        вынесли в переменную, — та же команда; имя, которого в исходнике нет вовсе
        (приходит доводом), правилу не видно, и это его известный предел."""
        self.assertEqual(self.subcommands('sub.add_parser("check")\n'), ["check"])
        self.assertEqual(self.subcommands('NAME = "check"\nsub.add_parser(NAME)\n'), ["check"])
        self.assertEqual(self.subcommands("def add(name):\n    sub.add_parser(name)\n"), [])

    def test_точка_входа_знает_про_роли_и_ворота_инструмента(self):
        """Точку входа `setup` кладёт в проект, и дальше её читают вместо SKILL.md."""
        for name in ("entry-point.md", "entry-point.ru.md"):
            text = (SKILL / "assets" / name).read_text(encoding="utf-8")
            for token in ("fixreview", "--append", "restamp", "backfill", "fix_gate", "deferred"):
                with self.subTest(file=name, token=token):
                    self.assertIn(token, text,
                                  f"{name} не знает про {token} — а `check` про него знает")

    def test_круг_починки_виден_и_в_промпте_и_в_имени_отчёта(self):
        s = Stand()
        self.addCleanup(s.cleanup)
        s.write("src/one.ts", "a\n")
        s.blocks(paths=["src/one.ts"])
        s.manifest(hypotheses=1)
        s.commit()
        s.run("init")
        first = s.run("prompt", "H1", "--role", "fix").stdout
        self.assertIn("H1-demo.fix.md", first)
        self.assertIn("Круг починки: **1**", first, "исполнитель обязан знать свой круг")
        second = s.run("prompt", "H1", "--role", "fix", "--round", "2").stdout
        self.assertIn("H1-demo.fix-2.md", second,
                      "второй круг обязан писать в свой файл, а не затирать первый")
        self.assertIn("Круг починки: **2**", second)
        base = s.git("rev-parse", "HEAD").stdout.strip()
        s.write("src/one.ts", "a\nfixed\n")
        s.commit("fix")
        review = s.run("prompt", "H1", "--role", "fixreview", "--diff", f"{base}...HEAD",
                       "--round", "2").stdout
        self.assertIn("H1-demo.fix-2.md", review.split("````diff")[0],
                      "ревьюер правок круга 2 читает отчёт исполнителя того же круга")


class CliContractTest(unittest.TestCase):
    """Значение поля `cli` подставляется в КАЖДУЮ подсказку вместе с флагами.

    `SKILL.md` предлагал в качестве примера `make review`, а make читает `--role` и
    `--reason` своими опциями и останавливается: подсказка `make review prompt H1 --role
    verify` не работает, и обобщённой цели `review` в образце целей нет — а `npm run
    review --` работает и в образце определён.
    """

    def test_документация_не_предлагает_make_как_значение_cli(self):
        for name, path in (("SKILL.md", SKILL / "SKILL.md"), ("review.py", TOOL)):
            with self.subTest(file=name):
                self.assertNotRegex(
                    path.read_text(encoding="utf-8"), r"`make review`",
                    f"{name} предлагает как `cli` команду, которая не донесёт флаг")
        self.assertIn("cli", (SKILL / "assets" / "makefile-snippet.mk").read_text(encoding="utf-8"),
                      "образец целей обязан сказать, почему make не годится в `cli`")

    def test_предложенная_форма_cli_определена_образцом_и_доносит_флаги(self):
        """Обратная сторона: то, что документация называет, обязано существовать."""
        scripts = json.loads((SKILL / "assets" / "package-json-snippet.json")
                             .read_text(encoding="utf-8"))["scripts"]
        self.assertIn("review", scripts, "обобщённая цель обязана быть в образце")
        self.assertIn("npm run review --", (SKILL / "SKILL.md").read_text(encoding="utf-8"))
        s = Stand()
        self.addCleanup(s.cleanup)
        s.write("src/one.ts", "a\n")
        s.blocks(paths=["src/one.ts"])
        bj = s.root / "docs/review/blocks.json"
        d = json.loads(bj.read_text(encoding="utf-8"))
        d["cli"] = "npm run review --"
        bj.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        s.write("lib/orphan.ts", "b\n")
        s.commit()
        s.run("init")
        out = s.run("coverage")
        self.assertEqual(out.returncode, 1)
        self.assertIn("npm run review -- status", out.stdout,
                      "подсказка собирается из `cli` целиком, вместе с подкомандой")
        s.run("coverage")
        s.write("docs/review/reports/H1-findings.jsonl", json.dumps({
            "block": "H1", "severity": "low", "confidence": "confirmed", "status": "rejected",
            "file": "src/one.ts", "claim": "дефекта нет"}, ensure_ascii=False) + "\n")
        s.run("import", "H1")
        s.run("findings")
        self.assertIn("npm run review -- set-finding H1-001 rejected --reason",
                      s.run("check").stdout,
                      "отказ обязан донести до пользователя и флаг, а не только подкоманду")


class DeferredIsAnAcceptedRiskTest(unittest.TestCase):
    """Что такое отложенная находка к концу ревью — у набора один ответ, а не два.

    Урок 13 требовал перед завершением каждую отложенную починить или отвергнуть, а
    инструмент отправляет её в сводку принятым риском и требует только причину; условия
    завершения в `SKILL.md` и в точке входа отложенного не упоминали вовсе. Ведущая сессия,
    прочитавшая уроки первыми, держала ревью открытым ради находок, которые ревью и должны
    были покинуть; прочитавшая в другом порядке — считала дефектом сам раздел сводки.
    """

    def setUp(self) -> None:
        self.s = Stand()
        self.addCleanup(self.s.cleanup)

    def test_отложенная_с_причиной_доживает_до_сводки_принятым_риском(self):
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=1)
        self.s.write("docs/review/reports/H1-findings.jsonl", json.dumps({
            "block": "H1", "severity": "medium", "confidence": "confirmed", "status": "open",
            "file": "src/one.ts", "claim": "дефект", "scenario": "сценарий"},
            ensure_ascii=False) + "\n")
        self.s.reports(hunter="# охотник\n## Гипотезы\n- H1.1 — проверена: да\n"
                              "## Ограничения охвата\nнет\n",
                       verify="# отчёт проверяющего\n\n## Вердикты по находкам охотника\n"
                              "Находка охотника подтверждена: воспроизвёл вызовом на матрице значений.\n\n"
                              "## Состояние охвата блока\nОхват полный: файл прочитан, гипотеза прогнана.\n")
        self.s.commit()
        self.s.run("init")
        self.s.run("coverage")
        self.s.run("import", "H1")
        out = self.s.run("set-finding", "H1-001", "deferred", "--reason", "ждёт блок H2")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.s.run("findings")
        self.s.run("set-status", "H1", "closed")
        check = self.s.run("check")
        self.assertEqual(check.returncode, 0,
                         "отложенная с причиной не должна держать ревью красным: " + check.stdout)
        self.assertIn("all blocks closed", self.s.run("status").stdout,
                      "ревью с отложенной находкой считается завершённым")
        self.assertEqual(self.s.run("summary").returncode, 0)
        summary = (self.s.root / "docs" / "review-summary.md").read_text(encoding="utf-8")
        self.assertIn("Принятые риски", summary)
        self.assertIn("ждёт блок H2", summary,
                      "принятый риск уезжает из ревью вместе с причиной")

    def test_отложенная_без_причины_по_прежнему_роняет_проверку(self):
        """Вторая сторона: запрещено не откладывать, а откладывать молча."""
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=1)
        self.s.write("docs/review/reports/H1-findings.jsonl", json.dumps({
            "block": "H1", "severity": "medium", "confidence": "confirmed", "status": "deferred",
            "file": "src/one.ts", "claim": "дефект", "scenario": "сценарий"},
            ensure_ascii=False) + "\n")
        self.s.commit()
        self.s.run("init")
        self.s.run("coverage")
        self.s.run("import", "H1")
        self.s.run("findings")
        out = self.s.run("check")
        self.assertIn("deferred without a reason", refused(out),
                      "отложенная без причины обязана ронять проверку, а не печататься "
                      "предупреждением: иначе ревью закрывается с неподписанным риском")

    def test_отказ_ворот_говорит_то_же_что_сводка(self):
        """Хвост самого отказа держался ничем: откаченный к прежней формулировке, он снова
        обещал, что к концу ревью каждую отложенную чинят или отвергают, — обещание,
        которого инструмент не держит, а сводка ему прямо противоречит."""
        self.s.write("src/one.ts", "a\n")
        self.s.blocks(paths=["src/one.ts"])
        self.s.manifest(hypotheses=1)
        self.s.write("docs/review/reports/H1-findings.jsonl", json.dumps({
            "block": "H1", "severity": "medium", "confidence": "confirmed", "status": "deferred",
            "file": "src/one.ts", "claim": "дефект", "scenario": "сценарий"},
            ensure_ascii=False) + "\n")
        self.s.commit()
        self.s.run("init")
        self.s.run("coverage")
        self.s.run("import", "H1")
        self.s.run("findings")
        message = refused(self.s.run("check"))
        self.assertIn("accepted risk", message,
                      "отказ обязан назвать то, чем отложенная находка станет: принятым риском")
        self.assertNotIn("fixed or rejected", message,
                         "отказ обещал починку или отказ к концу ревью — инструмент этого "
                         "не требует, а сводка публикует находку принятым риском")

    # Тексты, отвечающие на вопрос «что такое отложенная находка к концу ревью», и место
    # ответа в каждом: слово-указатель, от которого ответ обязан стоять рядом. Ответ один
    # на все — урок держался тестом, а условия завершения в `SKILL.md` не держались ничем,
    # и откат одной фразы проходил всей сюитой молча.
    ANSWERS = (
        ("references/lessons.md", "`deferred`", "accepted risk"),
        ("references/lessons.ru.md", "`deferred`", "принятый риск"),
        ("references/fix.md", "deferred --reason", "accepted risk"),
        ("references/fix.ru.md", "deferred --reason", "принят"),
        ("assets/entry-point.md", "`deferred`", "accepted risk"),
        ("assets/entry-point.ru.md", "`deferred`", "принятый риск"),
        ("SKILL.md", "When the review is finished", "accepted risk"),
    )
    # Ответ обязан стоять при указателе, а не где-то в файле: окно взято с запасом от
    # измеренного — самый далёкий из семи ответов отстоит на 128 символов (`SKILL.md`,
    # условия завершения), ближайший на 43. Триста — примерно абзац, и файл, где ответ
    # уехал дальше абзаца, читается как файл без ответа.
    ANSWER_WINDOW = 300

    def test_все_тексты_набора_дают_один_ответ_об_отложенной(self):
        for rel, anchor, token in self.ANSWERS:
            text = (SKILL / rel).read_text(encoding="utf-8")
            windows = [text[m.end():m.end() + self.ANSWER_WINDOW]
                       for m in re.finditer(re.escape(anchor), text)]
            with self.subTest(файл=rel):
                self.assertTrue(windows, f"{rel}: не нашлось даже `{anchor}`")
                self.assertTrue(
                    any(token in w for w in windows),
                    f"{rel}: рядом с «{anchor}» не сказано, что отложенная находка — это "
                    f"{token}; инструмент отвечает на этот вопрос так, и документ, "
                    f"поправленный в одном месте, противоречит остальным шести")


class SweepTest(unittest.TestCase):
    """The ceiling counted the block's files, while an enumeration criterion ("every place
    that changes data") sweeps the whole program — a live block of 5.7k lines demanded 47k
    (issue #25). The sweep is declared, sized apart and proven by a script."""

    def setUp(self):
        self.s = Stand()
        self.addCleanup(self.s.cleanup)
        self.s.write("src/one.ts", "a\n")
        for i in range(3):
            self.s.write(f"lib/w{i}.ts", "write()\n" * 50)

    def manifest(self, criterion: str):
        self.s.manifest(hypotheses=1)
        m = Path(self.s.root, "docs/review/blocks/H1-demo.md")
        text = m.read_text(encoding="utf-8")
        head = text[:text.index("## Критерий приёмки")]
        m.write_text(head + "## Критерий приёмки\n\n" + criterion + "\n", encoding="utf-8")

    def blocks(self, sweep=None):
        self.s.blocks(paths=["src/one.ts"], exclusions=[{"pattern": "lib/**", "reason": "стенд"}])
        if sweep is not None:
            bj = Path(self.s.root, "docs/review/blocks.json")
            d = json.loads(bj.read_text(encoding="utf-8"))
            d["blocks"][0]["sweep"] = sweep
            bj.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")

    def prepare(self, sweep=None, criterion="Таблица: перечислены все места, где меняются данные.", status=None):
        self.blocks(sweep)
        self.manifest(criterion)
        self.s.commit()
        self.s.run("init")
        self.s.run("coverage")
        if status:
            self.s.run("set-status", "H1", status)

    # forbidden
    def test_перечисление_без_sweep_краснеет(self):
        self.prepare()
        out = self.s.run("check")
        self.assertIn("declares no `sweep`", refused(out), out.stdout)

    def test_sweep_без_скрипта_после_охоты_краснеет(self):
        self.prepare(sweep=["lib/**"], status="hunted")
        out = self.s.run("check")
        self.assertIn("no sweep script", refused(out), out.stdout)

    # allowed
    def test_критерий_без_перечисления_не_требует_sweep(self):
        self.prepare(criterion="Таблица «вход → ожидание → факт» по каждой гипотезе.")
        out = self.s.run("check").stdout
        self.assertNotIn("declares no `sweep`", out)

    def test_объявленный_обход_со_скриптом_проходит_и_виден_в_размерах(self):
        self.prepare(sweep=["lib/**"])
        self.s.write("docs/review/sweeps/H1.sh", "git grep -n 'write(' -- lib\n")
        self.s.git("add", "-A")
        self.s.git("commit", "-q", "-m", "sweep")
        self.s.run("set-status", "H1", "hunted")
        out = self.s.run("check").stdout
        self.assertNotIn("declares no `sweep`", out)
        self.assertNotIn("no sweep script", out)
        sizes = self.s.run("sizes").stdout
        self.assertIn("+ sweep 3 files / 150 lines", sizes)
        prompt = self.s.run("prompt", "H1", "--role", "hunter").stdout
        self.assertIn("docs/review/sweeps/H1", prompt)

if __name__ == "__main__":
    unittest.main()
