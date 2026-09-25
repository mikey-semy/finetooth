# Security

The tool works locally: it reads the repository through `git` and writes to `docs/review/`.
The prompts it assembles are executed by agents with whatever permissions you gave them —
read the prompt before handing it to an agent.

## What the kit writes, and where

- **`review.py` writes under `docs/review/`** — the state, the register, the coverage map,
  the journal. Nothing else, with the exceptions the user asks for by name:
  - `summary` writes the summary that is meant to outlive the review directory, so it is
    written **outside** it: `docs/review-summary.md` by default, or wherever `--out` says —
    including outside the repository.
  - `sarif` prints the findings as SARIF to stdout and writes nothing; with `--out` it
    writes that one file wherever `--out` says — for CI to hand to code scanning.
  - `setup` creates files under `docs/review/` only, and never overwrites one that exists.
- **`review.py` sends nothing over the network** and runs no command but `git`.
- **`assets/run-role.sh` is the exception, and it is opt-in.** It is a convenience runner,
  not part of the tool: it writes the assembled prompt and the run's whole event stream to
  `$TMPDIR/finetooth-runs` (they are the measurement, and they are kept), and it **sends the
  prompt to the model over the network** by piping it into `claude -p`. The prompt carries
  the block's files. If that is not acceptable in your environment, do not run the script —
  `review.py prompt` prints the same prompt and sends nothing.
- **`scripts/axes.py` reads a stream file** and writes nothing.

## How to report a vulnerability

- Through GitHub: **Security → Report a vulnerability** in this repository (a private report).
- Or by email to the address in the owner's GitHub profile.

A reply **within a week**. The project is maintained by one person; promising faster would be
dishonest.

What counts as a vulnerability here: `review.py` writes anywhere but the places listed above;
an assembled prompt contains what should not be in it (for example, a file from `exclusions`);
the `check` can be bypassed so that it goes green on a false state. The last one matters most:
the kit exists so that such bypasses are impossible.

What does not count as a vulnerability: the behaviour of the agent executing the prompt — the
agent and its permission settings are responsible for that; and what `run-role.sh` sends and
keeps, which is described above and is the point of the script.
