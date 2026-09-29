"""Commands: setup, init, version."""

from __future__ import annotations

import json
from pathlib import Path

from ..base import SKILL_DIR, VERSION, die, now
from ..git import ROOT
from ..workspace import (
    BLOCKS_FILE, FINDINGS_FILE, INVARIANTS_FILE, REVIEW, STATE_FILE, default_cli, save_json,
)
from ..i18n import (
    ASSET_BANNER, ASSET_BLOCKS, ASSET_ENTRY, ASSET_INVARIANTS, ASSET_JOURNAL, ASSET_MANIFEST,
    LANGS, MSG, asset, fill,
)
from ..blocks import blocks, state, state_text
from ..settings import INVARIANTS_SKELETON, INVARIANTS_SKELETON_EN, deny_report


def cmd_init(args) -> int:
    defn = blocks()
    before = STATE_FILE.read_text(encoding="utf-8") if STATE_FILE.exists() else None
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
    FINDINGS_FILE.touch()
    # A re-run on an unchanged definition must leave the file alone, to the byte. While
    # `updated_at` was rewritten unconditionally, a CI gate of the usual shape — regenerate,
    # then require a clean working tree — went red on a correct state, and the only way to
    # keep it green was to stop running `init` in CI, which is what the gate existed for.
    if before is not None and state_text(st, keep=before) == before:
        print(f"state already matches the definition: {len(st['blocks'])} blocks")
        return 0
    st["updated_at"] = now()
    save_json(STATE_FILE, st)
    print(f"state initialised: {len(st['blocks'])} blocks")
    return 0


def cmd_version(args) -> int:
    print(VERSION)
    return 0


def cmd_setup(args) -> int:
    """Set up the review in a project: the definition skeleton, the invariants, the entry point.

    This used to be done by a separate installer that also copied the tool itself into the
    project. There is nowhere and no reason to copy the skill — it is installed the
    standard way, and what stays in the project is only what belongs to the project: its
    blocks, its rules, its state. Existing files are not touched: the command is run in a
    live project.
    """
    project = args.project or ROOT.name
    lang = args.lang
    if lang not in LANGS:
        die(f"unknown language {lang}; known: {', '.join(LANGS)}")
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
        "lang": lang,
        **({"cli": args.cli} if args.cli else {}),
        "gates": [],
        "note": MSG[lang]["setup_note"],
        "exclusions": [{"pattern": "docs/review/**", "reason": MSG[lang]["excl_apparatus"]}],
        "blocks": [],
    }
    # A skill installed into the project (so that CI runs the same version) is apparatus
    # too: without the exclusion its two dozen files turn the coverage map red from the
    # first commit. The path is the actual one: `.claude/skills/`, `.agents/skills/`,
    # wherever it was installed.
    try:
        own = SKILL_DIR.relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        own = None
    if own:
        skel["exclusions"].append({"pattern": f"{own}/**", "reason": MSG[lang]["excl_skill"]})
    put(BLOCKS_FILE, json.dumps(skel, ensure_ascii=False, indent=2) + "\n")
    put(INVARIANTS_FILE, (INVARIANTS_SKELETON if lang == "ru" else INVARIANTS_SKELETON_EN).format(project=project))
    cli = args.cli or default_cli()
    entry = asset(ASSET_ENTRY, lang).read_text(encoding="utf-8")
    put(REVIEW / "README.md", fill(entry, project, cli))
    for d in ("blocks", "reports"):
        (REVIEW / d).mkdir(parents=True, exist_ok=True)

    for rel in done:
        print(f"  + {rel}")
    # Everything `setup` prints is in the review language, as its scaffolds are: a Russian
    # review was handed its files in Russian and its checklist in English (#46).
    m = MSG[lang]
    for rel in skipped:
        print(m["setup_skipped"].format(rel=rel))
    # Bytecode appears as soon as someone imports the tool as a module, and rides into a
    # commit if the skill lives in the project. In the first project that is exactly what
    # happened. We do not edit someone else's .gitignore — we say so.
    ignore = ROOT / ".gitignore"
    known = ignore.read_text(encoding="utf-8") if ignore.exists() else ""
    if not any(k in known for k in ("__pycache__", "*.pyc", "*.py[cod]")):
        print(m["setup_pycache"])
    denied = deny_report(lang)
    if denied:
        print(denied)
    # The banner is not written anywhere by the tool — it goes into the project's own root
    # instructions file, which is not ours to edit. So it is printed ready to paste: its
    # whole point is to name the command a future session must run, and a sample that says
    # `make review-status` to a project without a Makefile sends every session to a
    # command that does not exist.
    banner = asset(ASSET_BANNER, lang).read_text(encoding="utf-8")
    banner = fill(banner.split("\n---\n", 1)[-1].strip(), project, cli)
    print(m["setup_next"].format(
        cli=cli, banner=banner, invariants=asset(ASSET_INVARIANTS, lang),
        blocks=asset(ASSET_BLOCKS, lang), manifest=asset(ASSET_MANIFEST, lang),
        journal=asset(ASSET_JOURNAL, lang), banner_path=asset(ASSET_BANNER, lang)))
    return 0
