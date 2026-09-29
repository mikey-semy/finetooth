"""The ONE place a process is started: git, its output split once, and the repository root."""

from __future__ import annotations

import subprocess
from pathlib import Path

from .base import die


# Subcommands and options whose output CARRIES PATHS. For them `-z` is not a nicety:
# without it git C-quotes a non-ASCII name (`"src/\320\272…"`) and separates fields with a
# tab, a colon or a newline — all three legal inside a path. The list is what the tool asks
# git for; `git()` below adds `-z` to such a run itself, so no call site can forget it.
GIT_PRINTS_PATHS = ("ls-files", "--name-only", "--name-status", "--others", "grep")


class GitRun:
    """What one git run produced: the exit code, the output, and the paths already split.

    The two traps of reading git are invisible from a call site — the `-z` that has to be
    asked for whenever the output carries paths, and the NUL split that has to read it
    back. They were therefore repeated at every call site and forgotten at some: three
    places parsed a path list line by line, and a review of a repository with a Cyrillic
    file name recorded paths that do not exist. `git()` is the only place in the tool that
    starts git, so the two belong here and nowhere else.
    """

    def __init__(self, argv: list[str], code: int, out, err: str) -> None:
        self.argv, self.code, self.out, self.err = argv, code, out, err

    @property
    def fields(self) -> list[str]:
        """A NUL-separated stream (`ls-files -z`, `show --name-only -z`, `log … -z`) as the
        raw fields git wrote: no unquoting, no line splitting, empty tails dropped."""
        return [f for f in self.out.split("\0") if f]

    @property
    def records(self) -> list[list[str]]:
        """`git grep -z` records: one per line, the fields inside separated by NUL — the
        separator git uses for grep, where a `:` would be ambiguous inside a path."""
        return [ln.split("\0") for ln in self.out.splitlines() if ln]


def git(*args: str, binary: bool = False, at_root: bool = True) -> GitRun:
    """Run git — THE ONE PLACE in the tool where a process is started.

    Everything the callers used to repeat lives here: the repository to work in, `-z` for
    every run whose output carries paths, and the reading of that output. A call site that
    wants a path list cannot get one that is not NUL-separated, because it does not build
    the command line — that is the whole point of a single entry.

    `at_root=False` is for the one run that asks git where the root IS: there is nothing to
    point `-C` at yet.
    """
    rest = list(args)
    # The decision reads the SUBCOMMAND and the options before `--`, never the data: a file
    # named `grep` turned `hash-object -- grep` into `hash-object -z`, git refused, and the
    # file silently dropped out of the block fingerprint.
    opts = rest[:rest.index("--")] if "--" in rest else rest
    asked = rest[:1] + [a for a in opts[1:] if a.startswith("-")]
    if any(a in GIT_PRINTS_PATHS for a in asked) and "-z" not in opts:
        # After the subcommand and before any `--`: that is where an option belongs.
        rest.insert(1, "-z")
    argv = ["git", *(["-C", str(ROOT)] if at_root else []), *rest]
    try:
        out = subprocess.run(argv, capture_output=True, text=not binary, check=False)
    except OSError as exc:
        # Without git the kit cannot answer a single question. Said once, plainly: the
        # alternative is a traceback out of whichever command the user typed first.
        die(f"git does not run ({exc}) — the kit reads the repository through git: "
            f"install it and repeat the command")
    err = out.stderr if isinstance(out.stderr, str) else out.stderr.decode("utf-8", "replace")
    return GitRun(argv, out.returncode, out.stdout, err)


def repo_root() -> Path | None:
    """Root of the repository UNDER REVIEW — taken from the working directory, not from the file.

    While the tool was copied into the project, the root was asked from git relative to
    the tool's own location. The skill lives anywhere — in `~/.claude/skills/`, in
    `.agents/skills/` of someone else's clone — and a root "from the file" would point at
    the skill directory or even at `~/.claude`, if that is under git: the tool would
    silently write its state there. The repository under review is the one you work in —
    that is the one we ask.
    """
    out = git("rev-parse", "--show-toplevel", at_root=False)
    top = out.out.strip()
    return Path(top) if out.code == 0 and top else None


IN_REPO = repo_root()
ROOT = IN_REPO or Path.cwd()
# Modes in the git index that look like files but are not files.
# Verified by experiment: a submodule (160000) is one entry in `ls-files`, but a directory
# on disk, and the line counter dies on it with IsADirectoryError. Its code lives in
# another repository and is reviewed there.
# A symlink (120000) is NOT excluded: a link can be re-pointed, and that is a change
# someone must see. Excluding it removed it from everywhere — no owner, no "unowned",
# no fingerprint. There is no double counting either: lines are taken from the index,
# where a symlink holds the link text, not the target's contents; the fingerprint is
# also taken from the link text.
NOT_A_FILE_MODES = ("160000",)


def index_rows(pathspecs: list[str] | None) -> list[tuple[str, str, str]]:
    """Index entries matching the pathspecs: (mode, blob sha, path).

    The patterns come from `blocks.json`, which is edited by hand, and git refuses to
    parse some of them (a typo in the pathspec magic the kit itself invites projects to
    use for exclusions). A refusal from git used to reach the user as a traceback with
    exit 1 — which reads as "the state is red", not as "your pattern is malformed".
    """
    out = git("ls-files", "--stage", *(["--", *pathspecs] if pathspecs is not None else []))
    if out.code != 0:
        where = ", ".join(f"`{p}`" for p in pathspecs or []) or "(no patterns)"
        die(f"git refuses the pattern(s) {where}: {out.err.strip() or 'unknown error'}\n"
            f"The patterns are the `paths`, `ref_paths` and `exclusions` fields of "
            f"docs/review/blocks.json — fix the one git names and re-run. "
            f"They are git pathspecs: `src/**/*.ts`, `:(exclude)src/generated/**`.")
    rows = []
    for row in out.fields:
        head, _, path = row.partition("\t")
        mode, _, rest = head.partition(" ")
        rows.append((mode, rest.split(" ", 1)[0], path))
    return rows


def listed(pathspecs: list[str] | None) -> set[str]:
    """Tracked files — real files, without submodules (a symlink is a file here, see above)."""
    return {path for mode, _, path in index_rows(pathspecs) if mode not in NOT_A_FILE_MODES}


def untracked_files(specs: list[str]) -> list[str]:
    """Files on disk that match the specs but are not in the index (`npx skills add`,
    a fresh generator, an unpacked archive): `check` would otherwise call them absent."""
    return git("ls-files", "--others", "--exclude-standard", "--", *specs).fields


def git_files(pathspecs: list[str]) -> set[str]:
    """Tracked files matching git pathspecs.

    An empty pathspec list means an empty set, NOT everything: a block that
    declares no paths (the ones that work on the running stand) owns no files,
    and must not be able to claim coverage it never earned. Use all_files() to
    ask for the whole repository on purpose.
    """
    if not pathspecs:
        return set()
    return listed(pathspecs)


def all_files() -> set[str]:
    return listed(None)


def mainline_ref() -> str | None:
    """The remote's main line to measure freshness against, or None if git knows of none.

    `refs/remotes/origin/HEAD` is written by `clone` and by `fetch`, but a repository whose
    remote is not called `origin` has no such ref at all — and neither has a copy with no
    remote, which is exactly the vendored copy of a neighbouring service the freshness
    threshold was written for. Every remote is asked, not just `origin`.
    """
    remotes = git("remote").out.split()
    for name in (["origin"] if "origin" in remotes else []) + [r for r in remotes if r != "origin"]:
        ref = git("symbolic-ref", "--short", f"refs/remotes/{name}/HEAD").out.strip()
        if ref:
            return ref
    return None


# `\x01` marks the start of a commit record: with `-z` every field is NUL-terminated, so
# the commit line cannot be told from a path by the separator alone.
LOG_MARK = "\x01"


def log_records(*args: str) -> list[tuple[str, list[str]]]:
    """Commit records of a `git log` run: (sha, the tokens after it). The caller passes the
    rest of the arguments — the record marker and the format are set HERE.

    ONE reader AND the only caller of `git log` in the tool, because the trap is not visible
    from a call site: git terminates the `--format` line with a newline of its own, and `-z`
    leaves that newline GLUED to the first token of the commit — the stream is `…<sha>\\0` +
    `\\nsrc/a.ts\\0`. Read without stripping it, a file that comes first in one commit and
    not in another is counted under two names, and `summary --aged` over-reported the drift
    of every real history for exactly that reason. Two parsers of one stream is how that
    happened: whoever wants records asks here, and nobody else has a marked stream to parse.
    """
    records: list[tuple[str, list[str]]] = []
    for token in git("log", f"--format={LOG_MARK}%H", *args).fields:
        if token.startswith(LOG_MARK):
            records.append((token[1:], []))
        elif records:
            body = records[-1][1]
            body.append(token[1:] if not body and token.startswith("\n") else token)
    return records


def git_head() -> tuple[str, str]:
    return (git("rev-parse", "HEAD").out.strip(),
            git("rev-parse", "--abbrev-ref", "HEAD").out.strip())


def diff_text(rng: str) -> str:
    """The whole diff of a range, for the fix reviewer: it reads the diff, not a report about it."""
    stat = git("diff", "--stat", rng)
    full = git("diff", rng)
    if full.code != 0:
        die(f"git diff {rng}: {full.err.strip()}")
    if not full.out.strip():
        die(f"diff {rng} is empty — the fix reviewer has nothing to read")
    # A fence of four backticks: triple ones occur inside a diff.
    return f"{stat.out}\n````diff\n{full.out}\n````"
