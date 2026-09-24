# Security

The tool works locally: it reads the repository through `git`, writes to `docs/review/` and
sends nothing over the network. The prompts it assembles are executed by agents with whatever
permissions you gave them — read the prompt before handing it to an agent.

## How to report a vulnerability

- Through GitHub: **Security → Report a vulnerability** in this repository (a private report).
- Or by email to the address in the owner's GitHub profile.

A reply **within a week**. The project is maintained by one person; promising faster would be
dishonest.

What counts as a vulnerability here: the tool writes outside `docs/review/`; an assembled
prompt contains what should not be in it (for example, a file from `exclusions`); the `check`
can be bypassed so that it goes green on a false state. The last one matters most: the kit
exists so that such bypasses are impossible.

What does not count as a vulnerability: the behaviour of the agent executing the prompt — the
agent and its permission settings are responsible for that.
