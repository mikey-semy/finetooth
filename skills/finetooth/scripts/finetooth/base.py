"""What every module needs and nothing else: the skill's location, the version, errors, time."""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path


# The skill directory: the tool lives in `<skill>/scripts/`, the role templates in
# `<skill>/references/`, the scaffolds in `<skill>/assets/`; this module is
# `<skill>/scripts/finetooth/base.py`.
SKILL_DIR = Path(__file__).resolve().parents[2]


def die(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(2)


# Version of the kit. The skill is installed as a copy (into the project or the home
# directory), and there is nobody else to ask "what do I have installed" — only itself.
VERSION = "0.8.0"


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
