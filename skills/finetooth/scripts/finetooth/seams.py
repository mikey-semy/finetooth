"""Seams between blocks: imports across them and co-changes, for the hunter's prompt."""

from __future__ import annotations

import ast
import json
import posixpath
import re

from .git import ROOT, all_files, git_files
from .i18n import MSG, T, review_lang
from .fingerprint import text_lines
from .blocks import blocks
from .coverage import coverage_map
from .history import (
    COUPLING_MIN_SHARE, COUPLING_MIN_TOGETHER, commit_file_sets, joint_changes, mass_cutoff,
)


# Seams INSIDE a block: pairs of its own files that depend on each other. `coupling` sees
# pairs across blocks; inside a block the hunter reads both files, but a defect that exists
# only where they are joined (one side assumes what the other does not hold on every path)
# was the weakest class of the recall measurement — of 7 cross-file cases on blocks of real
# size, the kit found 3 in full. The link is shown, the assumption is not: what one side
# assumes about the other is the manifest author's hypothesis, not something to generate.
#
# How many seams the prompt and the default listing carry: the manifest holds 10–15
# hypotheses (the kit's guidance since the first project), and one hypothesis per seam at
# the lower edge of that range is as many as a manifest can take without the seams crowding
# out every other question.
SEAMS_TOP = 10
JS_EXTS = (".ts", ".tsx", ".mts", ".cts", ".js", ".jsx", ".mjs", ".cjs")
# A specifier written with the emitted extension names the source file: TypeScript's ESM
# rule (`./x.js` resolves to `./x.ts`).
# From a TypeScript importer the source extensions are tried BEFORE the written one: with
# both `x.ts` and a built `x.js` beside it, the compiler reads `x.ts`.
JS_EMITTED = {".js": (".ts", ".tsx", ".d.ts"), ".jsx": (".tsx", ".d.ts"), ".mjs": (".mts", ".d.mts"),
              ".cjs": (".cts", ".d.cts")}
TS_IMPORTERS = (".ts", ".tsx", ".mts", ".cts")
PY_EXTS = (".py",)
TS_CONFIGS = ("tsconfig.json", "jsconfig.json")
# All five are searched in the text with comments and string contents blanked
# (`js_code_mask`) — that, not the pattern, is what keeps a commented-out `require(…)` or a
# string holding `import(…)` from counting. Static forms are also anchored at the start of a
# statement's line, as they are written; `require(…)` and `import(…)` are calls and can
# stand anywhere.
JS_IMPORT = re.compile(
    r"^[ \t]*import\s+(?:type\s+)?(?P<clause>[\w$*{},\s]+?)\s+from\s*(['\"])(?P<spec>[^'\"\n]+)\2",
    re.M)
JS_BARE_IMPORT = re.compile(r"^[ \t]*import\s*(['\"])(?P<spec>[^'\"\n]+)\1", re.M)
JS_REEXPORT = re.compile(
    r"^[ \t]*export\s+(?:type\s+)?(?P<clause>\*(?:\s+as\s+[\w$]+)?|\{[^}]*\})\s*from\s*"
    r"(['\"])(?P<spec>[^'\"\n]+)\2", re.M)
JS_REQUIRE = re.compile(
    r"(?:(?:const|let|var)\s+(?P<bind>\{[^}]*\}|[\w$]+)\s*=\s*)?"
    r"\brequire\s*\(\s*(['\"])(?P<spec>[^'\"\n]+)\2\s*\)")
JS_DYNAMIC = re.compile(r"\bimport\s*\(\s*(['\"])(?P<spec>[^'\"\n]+)\1\s*\)")


def js_code_mask(text: str) -> str:
    """The text with comments and the CONTENTS of string literals replaced by spaces — same
    length, same line breaks, the quote characters kept.

    Not a parser: a regex literal holding a quote (`/'/`) opens a "string", and a `'`/`"`
    string is closed at the end of its line, so the damage stays on that one line. A template
    literal is blanked whole, `${…}` included.
    """
    out = list(text)
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if text.startswith("//", i):
            while i < n and text[i] != "\n":
                out[i] = " "
                i += 1
            continue
        if text.startswith("/*", i):
            end = text.find("*/", i + 2)
            end = n if end < 0 else end + 2
            for j in range(i, end):
                if text[j] != "\n":
                    out[j] = " "
            i = end
            continue
        if c in "'\"`":
            i += 1
            while i < n and text[i] != c and not (c != "`" and text[i] == "\n"):
                if text[i] == "\\" and i + 1 < n:
                    out[i] = " "
                    i += 1
                if text[i] != "\n":
                    out[i] = " "
                i += 1
            i += 1
            continue
        i += 1
    return "".join(out)


def jsonc(text: str):
    """JSON with comments and trailing commas — what `tsconfig.json` is allowed to be.

    A strict `json.loads` refuses most real configs (`create-next-app` writes none of the
    extras, but half the projects add a comment): the comments are cut outside strings, a
    comma before `}` or `]` is dropped. None when it still does not parse.
    """
    out, i, n, quote_ch = [], 0, len(text), None
    while i < n:
        c = text[i]
        if quote_ch:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 1
            elif c == quote_ch:
                quote_ch = None
        elif c == '"':
            quote_ch = c
            out.append(c)
        elif text.startswith("//", i):
            while i < n and text[i] != "\n":
                i += 1
            continue
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            i = n if end < 0 else end + 2
            continue
        else:
            out.append(c)
        i += 1
    try:
        return json.loads(re.sub(r",(\s*[}\]])", r"\1", "".join(out)))
    except ValueError:
        return None


class TsConfig:
    """`compilerOptions.paths` and `baseUrl` of one config, with its relative `extends`.

    Read, not guessed: an alias resolves only as the project's own config declares it. A
    `paths` target and `baseUrl` are resolved the way TypeScript does — against `baseUrl`
    when one is set, else against the directory of the config that declares `paths`. An
    `extends` naming a package (`@tsconfig/node20`) is not followed: that file is not in
    the repository.
    """

    def __init__(self, rel: str) -> None:
        self.rel = rel
        self.paths: list[tuple[str, list[str]]] = []   # (pattern, targets from the root)
        self.base: str | None = None                   # baseUrl from the root
        base_url, paths, seen, at = None, None, set(), rel
        while at and at not in seen:
            seen.add(at)
            conf = jsonc((ROOT / at).read_text(encoding="utf-8", errors="replace")) \
                if (ROOT / at).is_file() else None
            if not isinstance(conf, dict):
                break
            opts = conf.get("compilerOptions") or {}
            here = posixpath.dirname(at)
            if base_url is None and isinstance(opts.get("baseUrl"), str):
                base_url = posixpath.normpath(posixpath.join(here, opts["baseUrl"]))
            if paths is None and isinstance(opts.get("paths"), dict):
                paths = (here, opts["paths"])
            ext = conf.get("extends")
            if not (isinstance(ext, str) and ext.startswith(".")):
                break
            nxt = posixpath.normpath(posixpath.join(here, ext))
            if nxt.startswith(".."):
                break   # outside the repository: not a file of the project under review
            at = nxt if nxt.endswith(".json") else nxt + ".json"
        self.base = base_url
        if paths:
            anchor = base_url if base_url is not None else paths[0]
            for pattern, targets in paths[1].items():
                if isinstance(targets, list):
                    self.paths.append((pattern, [posixpath.normpath(posixpath.join(anchor, t))
                                                 for t in targets if isinstance(t, str)]))
            # The longest prefix before `*` wins, as in TypeScript.
            self.paths.sort(key=lambda p: -len(p[0].split("*")[0]))

    def candidates(self, spec: str) -> list[str]:
        for pattern, targets in self.paths:
            if "*" in pattern:
                head, _, tail = pattern.partition("*")
                if spec.startswith(head) and spec.endswith(tail) and len(spec) >= len(head) + len(tail):
                    mid = spec[len(head):len(spec) - len(tail)]
                    return [t.replace("*", mid, 1) for t in targets]
            elif spec == pattern:
                return targets
        return [posixpath.normpath(posixpath.join(self.base, spec))] if self.base is not None else []

    def described(self) -> str:
        if not self.paths and self.base is None:
            return ""
        shown = [f"{p} → {', '.join(t or '.' for t in ts)}" for p, ts in self.paths]
        if self.base is not None:
            shown.append(f"baseUrl {self.base or '.'}")
        return f"{self.rel}: {'; '.join(shown)}"


class Imports:
    """Import edges between tracked files: who imports whom and which names.

    TS/JS by pattern (static `import … from`, `export … from`, `require`, `import()`),
    Python by `ast`. A specifier resolves to a tracked file or not at all: a package, an
    alias the configs do not declare, a file that is not in the repository are counted and
    skipped — never matched by a guess at the nearest name.
    """

    def __init__(self, tracked: set[str]) -> None:
        self.tracked = tracked
        self.configs: dict[str, TsConfig | None] = {}
        self.resolved = self.unresolved = 0

    def config_for(self, rel: str) -> TsConfig | None:
        """The nearest `tsconfig.json`/`jsconfig.json` above the file — the one the compiler uses."""
        d = posixpath.dirname(rel)
        while True:
            if d not in self.configs:
                found = None
                for name in TS_CONFIGS:
                    cand = posixpath.join(d, name) if d else name
                    if (ROOT / cand).is_file():
                        found = TsConfig(cand)
                        break
                self.configs[d] = found
            if self.configs[d] is not None or not d:
                return self.configs[d]
            d = posixpath.dirname(d)

    def file_of(self, base: str, exts: tuple[str, ...], index: str,
                source_first: bool = False) -> str | None:
        if base.startswith("..") or base.startswith("/"):
            return None
        tries = [base]
        stem, ext = posixpath.splitext(base)
        if exts == JS_EXTS:
            # `./x.js` names `./x.ts`; `./types` may be a declaration file only
            emitted = [stem + e for e in JS_EMITTED.get(ext, ())]
            tries = emitted + tries if source_first else tries + emitted
            exts = exts + (".d.ts",)
        tries += [base + e for e in exts]
        tries += [posixpath.normpath(posixpath.join(base, index + e)) for e in exts]
        return next((t for t in tries if t in self.tracked), None)

    def js_target(self, rel: str, spec: str) -> str | None:
        ts = rel.endswith(TS_IMPORTERS)
        if spec.startswith("."):
            return self.file_of(posixpath.normpath(posixpath.join(posixpath.dirname(rel), spec)),
                                JS_EXTS, "index", ts)
        conf = self.config_for(rel)
        for cand in (conf.candidates(spec) if conf else []):
            hit = self.file_of(cand, JS_EXTS, "index", ts)
            if hit:
                return hit
        return None

    @staticmethod
    def js_names(clause: str) -> list[str]:
        clause = re.sub(r"^type\s+", "", clause.strip())
        names: list[str] = []
        if clause.startswith("*"):
            return ["*"]
        brace = re.search(r"\{([^}]*)\}", clause)
        head = clause[:brace.start()] if brace else clause
        if head.strip(" ,"):
            names.append("default")
        if brace:
            for part in brace.group(1).split(","):
                word = re.sub(r"^type\s+", "", part.strip()).split()
                if word:
                    names.append(word[0].split(":")[0])
        return names

    def js_edges(self, rel: str, text: str) -> list[tuple[str, list[str]]]:
        # The forms are searched in the MASKED text (comments and string contents blanked,
        # offsets kept) and the specifier is read back from the original at the same span:
        # `// const old = require('./x')` or a string holding `import('./x')` is not a link.
        code = js_code_mask(text)
        spec = lambda m: text[m.start("spec"):m.end("spec")]
        found: list[tuple[str, list[str]]] = []
        for m in JS_IMPORT.finditer(code):
            found.append((spec(m), self.js_names(m["clause"])))
        for m in JS_BARE_IMPORT.finditer(code):
            found.append((spec(m), []))
        for m in JS_REEXPORT.finditer(code):
            found.append((spec(m), self.js_names(m["clause"])))
        for m in JS_REQUIRE.finditer(code):
            bind = m["bind"] or ""
            found.append((spec(m), self.js_names(bind) if bind.startswith("{")
                          else (["*"] if bind else [])))
        for m in JS_DYNAMIC.finditer(code):
            found.append((spec(m), []))
        return [(t, names) for spec, names in found if (t := self.counted(self.js_target(rel, spec)))]

    def counted(self, target: str | None) -> str | None:
        if target:
            self.resolved += 1
        else:
            self.unresolved += 1
        return target

    def py_module(self, rel: str, dotted: str, level: int) -> str | None:
        """A module name to its file. Relative (`level` dots) from the importer's package; an
        absolute one from the nearest directory above the importer that holds it — the
        script's own directory first, the root last, as `sys.path` would have them for a
        project run from its tree. `pyproject` package maps are not read."""
        parts = [p for p in dotted.split(".") if p]
        if level:
            d = posixpath.dirname(rel)
            for _ in range(level - 1):
                d = posixpath.dirname(d)
            roots = [d]
        else:
            roots, d = [], posixpath.dirname(rel)
            while True:
                roots.append(d)
                if not d:
                    break
                d = posixpath.dirname(d)
        for r in roots:
            base = posixpath.join(r, *parts) if parts else r
            hit = self.file_of(base, PY_EXTS, "__init__") if parts else (
                posixpath.join(r, "__init__.py") if posixpath.join(r, "__init__.py") in self.tracked
                else None)
            if hit:
                return hit
        return None

    def py_edges(self, rel: str, text: str) -> list[tuple[str, list[str]]]:
        try:
            tree = ast.parse(text)
        except (SyntaxError, ValueError):
            return []
        found: list[tuple[str | None, list[str]]] = []
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                for a in n.names:
                    found.append((self.py_module(rel, a.name, 0), []))
            elif isinstance(n, ast.ImportFrom):
                module = n.module or ""
                whole: list[str] = []
                for a in n.names:
                    # `from pkg import mod` imports a submodule when there is one
                    sub = (self.py_module(rel, f"{module}.{a.name}" if module else a.name, n.level)
                           if a.name != "*" else None)
                    if sub:
                        found.append((sub, []))
                    else:
                        whole.append(a.name)
                if whole:
                    found.append((self.py_module(rel, module, n.level), whole))
        return [(t, names) for t, names in found if self.counted(t)]

    def edges(self, rel: str) -> list[tuple[str, list[str]]]:
        ext = posixpath.splitext(rel)[1]
        if ext not in JS_EXTS and ext not in PY_EXTS:
            return []
        lines = text_lines(rel)
        if lines is None:
            return []
        text = b"\n".join(lines).decode("utf-8", "replace")
        return self.js_edges(rel, text) if ext in JS_EXTS else self.py_edges(rel, text)


def block_seams(b: dict, min_together: int, min_share: float,
                since: str | None = None) -> dict:
    """The pairs of the block's files linked by an import, by joint changes, or both —
    sorted: both kinds first, then by joint changes, then by imported names."""
    defn = blocks()
    excluded = git_files([e["pattern"] for e in defn.get("exclusions", [])])
    files = sorted(git_files(b.get("paths", [])) - excluded)
    inside = set(files)
    imp = Imports(all_files())
    pairs: dict[tuple[str, str], dict] = {}

    def pair(a: str, c: str) -> dict:
        return pairs.setdefault(tuple(sorted((a, c))), {"imports": {}, "together": 0,
                                                         "share": (0.0, 0.0)})
    outside = 0
    for f in files:
        for target, names in imp.edges(f):
            if target == f:
                continue
            if target not in inside:
                outside += 1
                continue
            got = pair(f, target)["imports"].setdefault((f, target), set())
            got.update(names)
    owned, _, _ = coverage_map()
    sets, merges = commit_file_sets(since)
    cutoff = mass_cutoff(sets) if sets else 0
    changes, together, skipped = joint_changes(owned, sets, cutoff,
                                               lambda a, c: a in inside and c in inside)
    for (a, c), n in together.items():
        share = (n / changes[a], n / changes[c])
        if n >= min_together and max(share) >= min_share:
            got = pair(a, c)
            got["together"], got["share"] = n, share
    rows = []
    for (a, c), p in pairs.items():
        names = set().union(*p["imports"].values()) if p["imports"] else set()
        rows.append({"a": a, "b": c, **p, "names": names,
                     "both": bool(p["imports"]) and p["together"] > 0})
    rows.sort(key=lambda r: (not r["both"], -r["together"], -len(r["names"]), r["a"], r["b"]))
    configs = sorted({c.described() for c in imp.configs.values() if c and c.described()})
    return {"files": files, "rows": rows, "resolved": imp.resolved, "unresolved": imp.unresolved,
            "outside": outside, "configs": configs, "sets": sets, "merges": merges,
            "cutoff": cutoff, "skipped": skipped}


SEAM_CO = "co-change {n}× ({a} / {b} of each file's changes)"


def seam_lines(rows: list[dict], indent: str = "  ", co: str = SEAM_CO) -> list[str]:
    """The pairs as the listing and the hunter prompt print them — one shape for both; `co`
    words the joint-change line in the language of the reader."""
    out = []
    for i, r in enumerate(rows, 1):
        out.append(f"{indent}{i}. {r['a']}  ↔  {r['b']}")
        for (src, dst), names in sorted(r["imports"].items()):
            shown = ", ".join(sorted(names)) if names else "—"
            out.append(f"{indent}     import {src} → {dst}: {shown}")
        if r["together"]:
            out.append(f"{indent}     " + co.format(n=r["together"], a=f"{r['share'][0]:.0%}",
                                                     b=f"{r['share'][1]:.0%}"))
    return out


def render_seams_for(b: dict) -> str:
    """`{{SEAMS}}`: the block's top seams for the hunter — where reading must join two files."""
    found = block_seams(b, COUPLING_MIN_TOGETHER, COUPLING_MIN_SHARE)
    rows = found["rows"]
    if not rows:
        return T("seams_none")
    head = T("seams_head", n=len(rows), top=min(SEAMS_TOP, len(rows)))
    return head + "\n\n```\n" + "\n".join(
        seam_lines(rows[:SEAMS_TOP], indent="", co=MSG[review_lang()]["seams_co"])) + "\n```"
