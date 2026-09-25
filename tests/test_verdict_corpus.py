#!/usr/bin/env python3
"""The verdict corpus: today's parser behaviour, frozen (issue #17).

Two halves, both under `tests/corpus/verdicts/`:

- the reports of every started block of the live registers, with `expected.json` — what
  `verdict_mentions` returned on each ORIGINAL report when the corpus was taken;
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
import re
import unittest
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]
TOOL = KIT / "skills" / "finetooth" / "scripts" / "review.py"
CORPUS = Path(__file__).resolve().parent / "corpus" / "verdicts"
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
        cls.expected = json.loads((CORPUS / "expected.json").read_text(encoding="utf-8"))
        cls.index = json.loads((CORPUS / "index.json").read_text(encoding="utf-8"))

    def test_корпус_отчётов_воспроизводится_дословно(self):
        moved = []
        for rel, want in sorted(self.expected.items()):
            text = (CORPUS / rel).read_text(encoding="utf-8")
            got = self.mod.verdict_mentions(text, self.index[rel]["block"])
            if got != want:
                moved.append(f"{rel} [{self.index[rel]['block']}]\n  was: {want}\n  now: {got}")
        self.assertFalse(moved, "the parser moved on the corpus — update expected.json line by "
                                "line, with the reason, or fix the change:\n" + "\n".join(moved))

    def test_корпус_полон_и_без_сирот(self):
        """Every report on disk is in expected.json and index.json, and nothing is listed
        that is not on disk: a report dropped from the corpus is a case the redesign loses."""
        on_disk = {p.relative_to(CORPUS).as_posix()
                   for p in CORPUS.glob("*/*.md")}
        self.assertEqual(on_disk, set(self.expected))
        self.assertEqual(on_disk, set(self.index))
        # The live registers the corpus was taken from — two external projects, 14 started
        # blocks between them, and the kit's own T1. Shrinking it must be deliberate.
        blocks = {(rel.split("/")[0], v["block"]) for rel, v in self.index.items()}
        self.assertEqual(len([b for b in blocks if b[0] != "finetooth"]), 14)
        self.assertIn(("finetooth", "T1"), blocks)

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
