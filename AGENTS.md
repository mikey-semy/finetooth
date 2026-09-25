# Working on the kit itself

> ## ⏳ A whole-repository review of the kit itself is in progress — read `docs/review/README.md` first
>
> The kit is being reviewed with its own method, block by block (T1 the tool, T2 the prompts,
> T3 the tests as a gate, T4 the repository contract). All of its state lives on disk, not in
> a conversation: `python3 skills/finetooth/scripts/review.py status` says where it stands and
> which block is next. Do not start a fresh review of your own and do not fix findings outside
> its rules — both are described in that README.
>
> When the review closes, `docs/review/` is deleted in one PR and this banner goes with it;
> what lasts moves into this file, into the knowledge base and into tests.

This file is for the agent that edits **the kit itself**, not one that runs a review with it.
It is read in every session, so it is short.

## What this is

A rig for whole-repository code review by AI agents, packaged as **a skill under the
[Agent Skills](https://agentskills.io/specification) standard**: everything that gets
installed into the agent lives in `skills/finetooth/` — `SKILL.md`, `scripts/review.py`,
`references/`, `assets/`. The rest of the repository (documents, tests, the plan) is not
installed into the agent.

The tool is a single file on the standard library, no dependencies. The skill lives apart from
the repository under review — in its `.claude/skills/`, in the home directory, anywhere — so
everything the tool can do must work in someone else's tree, with someone else's branch names
and directory layout, and the project root is taken from the working directory, not from the
file's location.

The design and intent are in [`README.md`](README.md), the check against world practice in
`comparison-with-practice` in the knowledge base (private repository `finetooth-hq`), the history in
[`CHANGELOG.md`](CHANGELOG.md).

## Rules that must not be broken here

1. **No dependencies.** The standard library and `git`. The kit is installed into projects in
   Go, in Rust, in anything — a Python environment is not guaranteed there, and
   `pip install` in someone else's repository is unacceptable.
2. **Every new gate comes with a test, and the test is proven by mutation.** Break the
   mechanism and make sure the test goes red; a green suite without that proves nothing. In
   `CHANGELOG.md` the mutations are listed by name — keep the tradition.
3. **A failure must say what to do.** Not "coverage incomplete" but "add the path to the block
   responsible for this area; the choice is made by a human because…". The message is read by
   someone seeing the tool for the first time.
4. **Numbers are derived from measurement, not from the head.** The block readability ceiling,
   the tree staleness threshold, the finding title length limit — each has a note next to it
   on where it came from. Adding a constant — add the justification too.
5. **Hints are assembled from `CLI`.** No `make review-check` in strings: the project calls
   the tool its own way (the `cli` field in `blocks.json`), otherwise — the real path to the
   tool.
6. **The skill must pass `skills-ref validate`.** CI runs the same validator. The skill name
   equals the directory name, the description says "what it does and when to apply it", the
   body of `SKILL.md` is shorter than 500 lines; details go to `references/`, links from
   `SKILL.md` go one level deep.
7. **File names in Latin letters**; content in English, with Russian copies in `README.ru.md`
   (`README.ru.md`, `CHANGELOG.ru.md`); research, measurements and the roadmap live in the private knowledge base `finetooth-hq`.
8. **A change to a mechanism is a change to a prompt.** If a gate has started requiring
   something new, the role template must say so: the agent will not guess it from an error
   message that a human will see.
9. **One place starts git; one container holds the refusals.** Every git run goes through
   `git()`: it adds `-z` to any run whose output carries paths and reads that output back
   (`.fields`, `.records`), so no call site can forget either. `git log` is ordered and parsed
   only in `log_records`. Every gate of `check` adds its refusal through `Refusals` with its
   OWN key — `gates.refuse("finding/code-changed", …)` — and that key is what the suite pairs
   with the test holding the gate; `cmd_check` returns nothing but `gates.report()`. A process
   started elsewhere, a refusal with a key assembled on the way, a gate that prints and exits
   by itself: each is a red run, not a style note. This is the answer to a defect class that
   came back three rounds running — a guard that recognises how a call is WRITTEN always
   misses the next spelling.

## Check before committing

```sh
python3 -m unittest discover -s tests
```

393 scenarios, about nine minutes (measured on the author's machine; the number of scenarios
is held by a test, the time is not). The tests create temporary git repositories and call the tool
from the skill folder — internals are deliberately not imported: a move survives the external
contract, not the internal structure. The skill format:

```sh
skills-ref validate skills/finetooth
```

## What is not here and why

- **A package on PyPI.** The skill is installed as a copy (`npx skills add`), and for CI — as
  a copy into the project: a review runs for months, and the version of the rig must be
  pinned to the repository together with the state, not updated underneath it.
- **Configuration beyond `blocks.json`.** Everything the tool needs to know lies in the block
  definitions; a second source of truth will drift from the first.
- **A history of runs.** State is "where we are now", not a journal; what happened is told by
  `git log` on the review directory.
