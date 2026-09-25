#!/usr/bin/env python3
"""The verdict corpus: today's parser behaviour, frozen (issue #17).

Two halves, both under `tests/corpus/verdicts/`:

- the reports of every started block of the kit's own review, with `expected.json` — what
  `verdict_mentions` returned on each report when the corpus was taken. The registers of
  external projects are part of the corpus too, but they carry those projects' text and are
  not published: set FINETOOTH_PRIVATE_CORPUS to a directory of the same layout (its own
  `expected.json` and `index.json`) and they are checked alongside;
- `template-forms.md` — every verdict form the role templates prescribe, with what the
  parser returns on it today.

The corpus freezes behaviour, it does not bless it: some of the frozen answers are wrong,
and the redesign exists to change them. A change to the parser that moves any of them must
update `expected.json` / `template-forms.md` line by line and say why — this test is what
makes the move visible instead of silent.

Run: python3 -m unittest discover -s tests
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import unittest
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]
TOOL = KIT / "skills" / "finetooth" / "scripts" / "review.py"
CORPUS = Path(__file__).resolve().parent / "corpus" / "verdicts"
PRIVATE = Path(os.environ["FINETOOTH_PRIVATE_CORPUS"]) if os.environ.get("FINETOOTH_PRIVATE_CORPUS") else None
FORMS = CORPUS / "template-forms.md"
BLOCK = "T1"


def load_tool():
    spec = importlib.util.spec_from_file_location("finetooth_review", TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


FORM = re.compile(
    r"^## (\d+)\. (.+?)\n.*?^~~~~report\n(.*?)\n~~~~\n\s*^expect: (.+?)$",
    re.MULTILINE | re.DOTALL)


def template_forms() -> list[tuple[str, str, dict]]:
    """(title, snippet, expected) for every entry of template-forms.md."""
    text = FORMS.read_text(encoding="utf-8")
    return [(f"{n}. {title}", snippet, json.loads(expect))
            for n, title, snippet, expect in FORM.findall(text)]


class VerdictCorpusTest(unittest.TestCase):
    """`verdict_mentions` reproduces the frozen corpus exactly."""

    @classmethod
    def setUpClass(cls):
        cls.mod = load_tool()
        cls.roots = [CORPUS] + ([PRIVATE] if PRIVATE else [])
        cls.expected, cls.index, cls.where = {}, {}, {}
        for root in cls.roots:
            exp = json.loads((root / "expected.json").read_text(encoding="utf-8"))
            idx = json.loads((root / "index.json").read_text(encoding="utf-8"))
            cls.expected.update(exp)
            cls.index.update(idx)
            cls.where.update({rel: root for rel in exp})

    def test_корпус_отчётов_воспроизводится_дословно(self):
        moved = []
        for rel, want in sorted(self.expected.items()):
            text = (self.where[rel] / rel).read_text(encoding="utf-8")
            got = self.mod.verdict_mentions(text, self.index[rel]["block"])
            if got != want:
                moved.append(f"{rel} [{self.index[rel]['block']}]\n  was: {want}\n  now: {got}")
        self.assertFalse(moved, "the parser moved on the corpus — update expected.json line by "
                                "line, with the reason, or fix the change:\n" + "\n".join(moved))

    def test_корпус_полон_и_без_сирот(self):
        """Every report on disk is in expected.json and index.json, and nothing is listed
        that is not on disk: a report dropped from the corpus is a case the redesign loses."""
        on_disk = {p.relative_to(root).as_posix()
                   for root in self.roots for p in root.glob("*/*.md")}
        self.assertEqual(on_disk, set(self.expected))
        self.assertEqual(on_disk, set(self.index))
        blocks = {(rel.split("/")[0], v["block"]) for rel, v in self.index.items()}
        self.assertIn(("finetooth", "T1"), blocks)
        if PRIVATE:
            # two external projects, 14 started blocks between them; shrinking is deliberate
            self.assertEqual(len([b for b in blocks if b[0] != "finetooth"]), 14)

    def test_формы_из_шаблонов_дают_ожидаемый_вердикт(self):
        forms = template_forms()
        # Every numbered entry was parsed: a malformed entry must not drop out silently.
        headers = re.findall(r"^## \d+\. ", FORMS.read_text(encoding="utf-8"), re.MULTILINE)
        self.assertEqual(len(forms), len(headers))
        self.assertGreater(len(forms), 0)
        for title, snippet, want in forms:
            with self.subTest(title):
                got = self.mod.verdict_mentions(snippet.replace("{{BLOCK_ID}}", BLOCK), BLOCK)
                self.assertEqual(got, want)

    def test_формы_покрывают_все_четыре_шаблона_на_обоих_языках(self):
        titles = [t for t, _, _ in template_forms()]
        for role in ("hunter", "verify", "fix", "fixreview"):
            for suffix in (".md", ".ru.md"):
                name = role + suffix
                self.assertTrue(any(re.match(rf"\d+\. {re.escape(name)} — ", t) for t in titles),
                                f"no form from {name}")


if __name__ == "__main__":
    unittest.main()
