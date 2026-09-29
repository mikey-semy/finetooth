"""The project's own deny rules against the commands each role needs."""

from __future__ import annotations

import json
import re
from collections.abc import Callable

from .base import SKILL_DIR
from .git import ROOT
from .workspace import BLOCKS_FILE, CLI
from .i18n import MSG


# A role runs under the project's own Claude Code settings as well as its pre-approvals, and a
# deny there wins over any allow (see #45: a project denied `pytest` in its local settings,
# and every role failed on tests until the invariants named `python3 -m pytest`). Both files
# are the project-level ones the Claude Code settings documentation names; the user's own
# `~/.claude/settings.json` is not the project's to report on.
SETTINGS_FILES = (".claude/settings.json", ".claude/settings.local.json")
# Where the roles' pre-approved commands are written. They are read from the script, not
# copied here, so a command added to a role is checked without a second edit.
ROLE_RUNNER = SKILL_DIR / "assets" / "run-role.sh"
# Wrappers Claude Code strips before matching a Bash rule (permissions docs, "Wrappers"):
# `timeout 30 npm test` is matched as `npm test`. `xargs` only without flags, `command` not
# in its `-v` / `-V` query form. For each: the options that take a SEPARATE argument and the
# number of positional arguments before the command, from the man pages (GNU coreutils
# timeout, nice, stdbuf; GNU time; bash for `command`, `builtin`; zsh for `noglob`). Taking
# off only the option word left its argument behind as the command: `timeout -s KILL 5
# pytest` read as `KILL 5 pytest`, and `Bash(pytest *)` did not hit it.
BASH_WRAPPERS: dict[str, tuple[frozenset[str], int]] = {
    "timeout": (frozenset({"-s", "--signal", "-k", "--kill-after"}), 1),  # DURATION
    "nice": (frozenset({"-n", "--adjustment"}), 0),
    "stdbuf": (frozenset({"-i", "-o", "-e", "--input", "--output", "--error"}), 0),
    "time": (frozenset({"-f", "--format", "-o", "--output"}), 0),
    "nohup": (frozenset(), 0),
    "command": (frozenset(), 0),
    "builtin": (frozenset(), 0),
    "noglob": (frozenset(), 0),
    "xargs": (frozenset(), 0),
}
# The separators Claude Code splits a compound command on (permissions docs, "Compound
# commands"); a deny rule applies when any part matches. Longest first.
BASH_SEPARATORS = re.compile(r"\|\||&&|\|&|[;|&\n]")


def bash_rule_matcher(rule: str) -> Callable[[str], bool] | None:
    """A deny rule as a predicate over one simple command, or None if it names no command.

    The format is Claude Code's (https://code.claude.com/docs/en/permissions, "Permission rule
    syntax"): `Tool` or `Tool(specifier)`. `Bash` and `Bash(*)` match every command, as does a
    tool-name glob that matches `Bash` (`*`). In a specifier `*` stands for any text, spaces
    included; a rule without `*` is one exact command; a trailing ` *` that is the rule's only
    wildcard also matches the bare command (`Bash(ls *)` matches `ls`, not `lsof`); `:*` at the
    end is the same as ` *`.
    """
    m = re.fullmatch(r"\s*([^()\s]+)\s*(?:\((.*)\))?\s*", rule, re.S)
    if not m:
        return None
    tool, spec = m.group(1), m.group(2)
    if spec is None:
        glob = re.escape(tool).replace(r"\*", ".*")
        return (lambda cmd: True) if re.fullmatch(glob, "Bash") else None
    if tool != "Bash":
        return None
    # A rule on a tool input, `Bash(run_in_background:true)` ("Match by input parameter"),
    # reads here as a command of that literal text and so hits no gate — as it should.
    spec = spec.strip()
    if spec.endswith(":*"):
        spec = spec[:-2] + " *"
    if spec in ("", "*"):
        return lambda cmd: True
    pattern = re.compile(".*".join(re.escape(part) for part in spec.split("*")), re.S)
    bare = spec[:-2] if spec.endswith(" *") and spec.count("*") == 1 else None
    return lambda cmd: bool(pattern.fullmatch(cmd)) or cmd == bare


def simple_commands(command: str) -> list[str]:
    """The simple commands Claude Code matches a rule against, for one gate command.

    Split on the shell separators, with a leading `VAR=value` and the stripped wrappers taken
    off each part — for a deny rule, any leading assignment (permissions docs). The split does
    not parse quoting: a gate is a command a human typed into blocks.json, not a script.
    """
    parts = []
    for part in BASH_SEPARATORS.split(command):
        words = part.split()
        while words and re.fullmatch(r"[A-Za-z_]\w*=\S*", words[0]):
            words.pop(0)
        while words and words[0] in BASH_WRAPPERS:
            nxt = words[1] if len(words) > 1 else ""
            if words[0] == "command" and nxt in ("-v", "-V"):
                break
            if words[0] == "xargs" and nxt.startswith("-"):
                break
            with_arg, positional = BASH_WRAPPERS[words.pop(0)]
            # The wrapper's options: `-s KILL` takes two words; `-sKILL`, `--signal=KILL`, a
            # flag like `-p`, the old `nice -10` and `--` take one.
            while words and words[0].startswith("-"):
                opt = words.pop(0)
                if opt in with_arg and words:
                    words.pop(0)
            del words[:positional]
        if words:
            parts.append(" ".join(words))
    return parts


def role_commands() -> dict[str, list[str]]:
    """The command prefixes the roles are pre-approved for, read from run-role.sh: for each
    `Bash(prefix *)` in a role's list, the prefix, with the roles that have it."""
    out: dict[str, list[str]] = {}
    try:
        text = ROLE_RUNNER.read_text(encoding="utf-8")
    except OSError:
        return out
    for roles, tools in re.findall(r'^\s*([\w|]+)\)\s*CAP=\d+;\s*TOOLS="([^"]*)"', text, re.M):
        for prefix in re.findall(r"Bash\(([^()*]+?) \*\)", tools):
            for role in roles.split("|"):
                if role not in out.setdefault(prefix, []):
                    out[prefix].append(role)
    return out


def deny_hits(gates: list, lang: str = "en") -> tuple[list[tuple[str, str, list[str]]], list[str]]:
    """Which of the project's deny rules hit a gate command or a command the roles run.

    Returns the hits — (settings file, rule, what it hits) — and the problems: a settings file
    that is not JSON, a `permissions.deny` that is not a list. A file that is not there is
    not a problem: most projects have neither.
    """
    hits: list[tuple[str, str, list[str]]] = []
    problems: list[str] = []
    gates = gates if isinstance(gates, list) else []
    m = MSG[lang]
    targets = [(m["deny_gate"].format(g=g), g) for g in gates if isinstance(g, str)]
    targets += [(m["deny_roles"].format(prefix=prefix, roles=", ".join(roles)), prefix)
                for prefix, roles in role_commands().items()]
    for rel in SETTINGS_FILES:
        path = ROOT / rel
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            problems.append(m["deny_unreadable"].format(rel=rel, exc=exc))
            continue
        perms = data.get("permissions") if isinstance(data, dict) else None
        deny = perms.get("deny", []) if isinstance(perms, dict) else []
        if not isinstance(deny, list):
            problems.append(m["deny_not_list"].format(rel=rel))
            continue
        for rule in deny:
            match = bash_rule_matcher(rule) if isinstance(rule, str) else None
            if match is None:
                continue
            what = [label for label, cmd in targets
                    if any(match(part) for part in simple_commands(cmd))]
            if what:
                hits.append((rel, rule, what))
    return hits, problems


def gates_on_disk() -> list:
    """The gates from blocks.json without the definition checks: `setup` runs before the
    definition is complete, and a half-written file is not this report's business."""
    try:
        gates = json.loads(BLOCKS_FILE.read_text(encoding="utf-8")).get("gates", [])
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, AttributeError):
        return []
    return gates if isinstance(gates, list) else []


def deny_report(lang: str) -> str:
    """The full report for `setup`, in the review language: every rule, what it hits, and what to do."""
    m = MSG[lang]
    hits, problems = deny_hits(gates_on_disk(), lang)
    lines = [f"\n⚠️ {p}" for p in problems]
    if hits:
        lines.append(m["deny_head"])
        for rel, rule, what in hits:
            lines.append(f"  {rel}: {rule}")
            lines += [m["deny_hits"].format(what=w) for w in what]
        lines.append(m["deny_todo"].format(advice=m["deny_advice"]))
    return "\n".join(lines)


def deny_line(gates: list) -> str:
    """One line for `status`: enough to notice; the full list is printed by `setup`."""
    hits, problems = deny_hits(gates)
    said = []
    if hits:
        rules = ", ".join(f"{rule} ({rel})" for rel, rule, _ in hits)
        n = sum(len(what) for _, _, what in hits)
        said.append(f"project deny rules hit {n} command(s) the review runs: {rules} — "
                    f"{MSG['en']['deny_advice']}; the full list: `{CLI} setup`")
    said += problems
    return ("⚠️ " + "; ".join(said)) if said else ""


INVARIANTS_SKELETON_EN = """# {project} invariants

This file is pasted into the prompt of EVERY agent, and it decides what the agent will
count as a defect. Generic words are useless here — write what the project has already
paid for.

## Context that changes how findings are judged

<Is there a production? Legacy data? Target scale? What may be broken and what must never
be, under any circumstances?>

## Rules that must not be broken

<One item per rule, each from your own history. "Limits count successes; the user does not
pay for our failures" beats "the code must be correct".>

## What is NOT a finding

<Style? Limit numbers that live in env? Known and accepted trade-offs? List them, or the
agent will bring nitpicks.>
"""
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
