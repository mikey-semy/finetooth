"""Where the review lives on disk (docs/review/…) and how the project calls this tool."""

from __future__ import annotations

import json
from pathlib import Path

from .base import die
from .git import ROOT, git_files


REVIEW = ROOT / "docs" / "review"


def default_cli() -> str:
    """How to call THIS instance of the tool — from its real path.

    The string goes only into hints: a refusal must say what to type. It used to be
    written in by the installer, and a copy installed by hand advised a command that did
    not exist. Now the path is known on its own: inside the project — relative, in the
    home directory — via `~`, otherwise absolute. A project that calls the tool its own
    way writes that in the `cli` field of `blocks.json` — and it has to be a command that
    takes the subcommand and its flags after it (`npm run review --`, a shell wrapper).
    `make` is not one: it reads `--role` as its own option, so a project on `make` keeps
    the targets for the everyday commands and leaves `cli` unset.
    """
    # the command is scripts/review.py; this module is scripts/finetooth/workspace.py
    here = Path(__file__).resolve().parents[1] / "review.py"
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
# The human's decisions on a block, one JSON line each (`decide`). A file of its own, not a
# field in state.json: state is "where we are now" and `init --force` rewrites it from
# scratch, while a decision is history the next round's prompt must keep carrying — the
# same append-only shape as the register, next to it.
DECISIONS_FILE = REVIEW / "decisions.jsonl"


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        die(f"{path.relative_to(ROOT)} is missing — run `{CLI} init`")
    except json.JSONDecodeError as exc:
        die(f"{path.relative_to(ROOT)} is not valid JSON: {exc}")


def save_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def named_file(rel: str) -> bool:
    """Is this NAME a tracked file?

    A name is not a pattern: `:(literal)` keeps a `[handle]` in the path a directory and
    not a character class. Next.js routes — `app/[id]/page.tsx` — are the kit's stated
    target, and without this a guard or a `--fixed-in` path that really exists is refused.
    """
    return bool(git_files([f":(literal){rel}"]))


COUPLING_FILE = REVIEW / "coupling.tsv"
SUMMARY_DEFAULT = "docs/review-summary.md"
#
# The same summary as one self-contained HTML file for a reader who never saw the review's
# conversation: opened from disk, attached to a PR, read on a phone. Built from
# `summary_facts` and nothing else. Nothing is fetched: no font, no script, no stylesheet,
# no image — a file that loads something from the network is not the same file a year later,
# and a page that runs code is not something to attach to a PR. Charts are SVG drawn here;
# a segment's count is its `<title>` (the browser's own tooltip, no script needed).
#
# Colours (the palette validated for colour-blind separation in both themes, the dataviz
# skill's reference instance): severity is ordered, so it is one blue ramp — darker is more
# severe on the light surface, lighter on the dark one; a finding's status is an identity,
# so it takes categorical hues other than blue (orange, aqua, yellow, magenta, violet — the
# reference order with blue left to the severity ramp, so the two bars never share a hue). Every colour is a custom property
# redefined for `prefers-color-scheme: dark`; the chart reads the same properties.

SUMMARY_HTML_DEFAULT = "docs/review-summary.html"
