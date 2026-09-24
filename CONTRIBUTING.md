# How to contribute

The project is maintained by one person, and PRs are looked at roughly once a week. That is
not a promised response time but an honest description of the pace.

## What is customary here

- **Language.** English for code, commits, PRs and issues; documentation is maintained in
  English with Russian copies (`README.ru.md`, `CHANGELOG.ru.md`). File names and identifiers in Latin
  letters.
- **No dependencies.** The tool is the Python standard library and `git`. A PR that adds a
  dependency will be rejected: the kit is installed into projects on any stack.
- **Every new check comes with a test, and the test is proven by mutation.** Break the
  mechanism and make sure the test goes red; a green test without that proves nothing. In the
  PR description name the mutation: what you broke and which test caught it.
- **A failure must say what to do.** The error message is read by someone seeing the tool for
  the first time.
- **Numbers come from measurement, not from the head.** A threshold, a limit, an interval —
  the source sits next to it.
- **A change to a mechanism is a change to a prompt.** If a gate has started requiring
  something new, the role template in `skills/finetooth/references/` must say so.
- **The skill passes `skills-ref validate`.** The name equals the directory, the description
  says "what it does and when to apply it", the body of `SKILL.md` is shorter than 500 lines.

More in `AGENTS.md`: it is written for the agent that edits the kit, and it suits a human too.

## How changes are accepted

Rules borrowed from projects that have been taking outside changes for years (curl,
Terraform, Next.js, Better Auth); each has a reason.

- **A new feature starts with an issue, not with code.** A large PR opened without an
  agreed issue may not be reviewed at all. Reviewer attention is the scarcest resource of a
  one-person project.
- **One PR — one problem.** A patch that "fixes eleven things" stalls on the ten that are
  disputed, and it cannot be bisected.
- **Trivial PRs — typo, formatting, wording — are closed** unless they fix a real mistake in
  a document. Open an issue instead; it costs less than a review.
- **A test, or an explanation of how you verified it.** For a fix: the test must go red
  without the fix, and its docstring links the issue (`# see #123`). For a new check: the
  mutation that proves the test.
- **AI-assisted changes are welcome; the responsibility is yours.** Say in the PR that AI
  was used. The PR description is written by a human who understands the change well enough
  to discuss it; AI is a tool, not a co-author.
- **A reproducible error is not automatically a defect.** Show which documented behaviour of
  the tool it violates; if the behaviour is intentional but confusing, the fix is a clearer
  message or a doc line.
- **Silence is a no.** A PR whose author does not answer review comments is closed after 30
  days of inactivity, with an invitation to reopen when things move again. Nothing personal:
  it is how the queue stays honest.
- **Write access is given for work done**, not for intent: after several accepted changes,
  ask.

## Releases

Branches: `master` holds releases only, `dev` is where work lands — open your PR against
`dev` (it is the default). How a version number is chosen and what has to be true before a
tag exists — `RELEASING.md`.
In short: semantic versioning with a zero major, at most one release a week, four mechanical
gates including a run on a live project, and no direct pushes to `master` for anyone.

## Before a PR

```sh
python3 -m unittest discover -s tests          # ~1 minute, needs only git
skills-ref validate skills/finetooth            # pip install skills-ref
```

An entry in `CHANGELOG.md`, section "Unreleased": what changed and why. If the change breaks
the on-disk state format — a "Breaking" section with what to do about a review already in
progress.

## DCO

Every commit is signed with the line `Signed-off-by: Name <email>` (`git commit -s`). With it
you confirm the [Developer Certificate of Origin](https://developercertificate.org/): you have
the right to hand over this code under the project's license. There is no CLA.

## What we will not accept

- Dependencies, a web interface, a database — see "What not to do" in the roadmap in the knowledge base (private repository `finetooth-hq`).
- Turning the kit into a diff reviewer: that is a different class of tools, and it is taken.
- Changes without a test and a CHANGELOG entry.

## Found a defect with the kit?

Open an issue with the "Trophy" template: a link to the finding (it may be anonymised) and
which step produced it. That is the only way to count what the method actually finds.
