# The lessons the kit's rules grew out of

Every rule of the kit appeared after a specific case. Here they are collected with what
happened and what follows from it. Worth reading before the first block: most of the
mistakes below looked reasonable at the moment they were made.

The source is two reviews. The first — by the author of the method, Georgiy Khudobandaev,
on his project (~2000 files, 69 blocks; the lessons were handed over together with the second
version of the kit on 23.09.2026 and are retold here in our own words). The second — the
first project where the kit was installed as a skill (69 blocks, 5 completed). Where a
lesson is ours, it says so.

## Honesty of coverage

1. **"Read 25 of 25" is the agent's own word about its own work.** The hunter claimed all 25
   files and named five in the report; the top-up found 11 more defects, a serious one among
   them. → `check` requires every file of a readable block to be named by **full path** in
   at least one report. The base name is not enough: 45 blocks of 59 had files with the same
   name, and "all page.tsx" would have closed six blocks at once.
2. **A block that does not fit in a sitting does not fail — it gets skimmed.** The plan was
   recut from 29 blocks to 59 and a line ceiling per readable block was introduced. →
   `sizes`, `readable_lines`.
3. **A prompt that contradicts its own manifest teaches the agent to pick the convenient
   half.** The template told the test-quality block to "read 807 files in full", while the
   manifest a page below explained why that was impossible; live-system blocks were given
   "0 files — read them all". → Rule 1 of the prompt and the heading of the file list are
   derived from the block's proof kind (`proof`).
4. **An empty list of paths is an empty set, not "everything".** The first version of the
   tool assumed that a block without paths covers the whole repository, and coverage added up
   fictitiously.
5. **A typo in a path pattern narrows a block silently.** → A pattern that matches no file
   is a `check` refusal.
6. **Ownership by directory hides pieces of the interface.** The entity card was assembled
   from route-local components; ownership by directory would have given the comments and the
   other tabs to the "card" block, and the specialized blocks would not have seen them. →
   Ownership by file where a directory mixes subjects.
7. **The acceptance criterion is an artifact that can be rebuilt.** The verifier of the
   first block rebuilt the route table (322 registrations against the hunter's 321 — the
   discrepancy was explained) and rewrote 48 permission-granting statements as queries to
   the live database. That is proof, not "I checked everything".
8. **(ours) The "Coverage limits" section is mandatory and is never empty.** Completeness is
   proven by listing what was not read; a heading without text is the same silence as no
   heading.

## Findings

9. **A finding is a failure scenario, not an opinion.** Without concrete input data and
   incorrect behavior — not a finding. This cuts off style and "could be better".
10. **An agent's report is a claim.** The verifier lowered the severity of two findings and
    struck out unreachable scenarios; in another block 12 findings of 49 had their severity
    lowered, and all three examples from one hunter turned out to be false. → The lead
    session checks every finding itself before fixing.
11. **`claim` is a title, not a log.** The verifier wrote the whole course of the check into
    the field, and the summary table stopped being a table. → A limit of 220 characters,
    `scenario` — 700.
12. **A rejected finding is kept with the reason.** Otherwise the next review finds the same thing.
13. **A deferred finding lives through the whole review unnoticed**, because it does not
    count as open. → `deferred` requires a reason; before the review ends each one is either
    fixed or rejected with a reason.
14. **Finding numbers must not shift.** Ids are assigned by position; without writing the id
    back into the block's file, a finding added later would renumber everything below it. →
    Numbers are written back, a second batch is `import --append`.
15. **A fixed finding is history.** `check` went red when the file of a long-fixed finding
    was renamed. → Only `open` and `deferred` must point at a live file.
16. **(ours) A duplicate is by root, not by text**: two findings are duplicates if fixing the
    root of one makes the other nonexistent. A duplicate points at a live finding, not at a
    duplicate and not at a rejected one.

## Fixing

17. **A test in both directions.** A sweeping fix of access rights passed the linter, the race
    detector and every gate — and took away a manager's log of their subordinates' work.
    Every new test proved that an outsider no longer sees too much; not one that an insider
    still sees their own.
18. **A fake softer than the system turns green what fails in production.** The mock
    answered success on a cancelled context; the default permissions mock answered "sees
    everything". The opposite is dangerous too: a fake stricter than the system stood for a
    whole round and pushed to loosen the check.
19. **A fix is proven by reverting — and the revert must build.** The removed check left an
    unused variable, the build failed without a single failed test, and "zero failures" was
    read as "the test does not depend on the fix". The honest answer was: four failures of five.
20. **A defect with two addresses and one fix is still a defect.** Three rounds in a row
    found one shape of mistake: a shared predicate was replaced on the server and the three
    screens that must agree with it were left untouched. → The rule "the fix goes to every
    address", find them yourself.
21. **Sprawl is a silent fix, not a fix along the way.** The fixer working on one column
    found four more places of the same kind — including the one that broke login — and fixed
    them together. Had it deferred them, half the class would have gone into the main branch.
    The danger is not an extra fix but an unnamed one. → An incidental fix is a separate line
    in the report with its own test.
22. **The heaviest defect can come on the third round and not be yours.** On the third round
    of fix review it turned out: a title longer than 500 characters did not fit the column,
    the audit row was written in the same transaction as the operation — and a person with
    such a browser could neither log in nor create a record. It had been there from the
    start. → Rounds repeat while they pay off; reproduce live where you can.
23. **A rule written through a number goes stale the same day.** "There are exactly two
    seams" went stale while it was being written. → State it through a property; keep the
    checkable part in the gates.
24. **A round that finds a defect introduced by the previous round is a signal.** The machine
    has started working for itself; the fix reviewer says so separately.
25. **(ours) A defect class with a third instance is closed by a guard, not by a list of
    fixes.** 90% of the findings of the file-by-file pass turned out to be repeats of twenty roots.

## Gates — the checks that must go red

26. **Gates are proven by violation, not by reading.** In all six grep gates of the project
    the allowing comment exempted the neighboring call, not its own.
27. **Extending a pattern is the most likely way to switch a gate off.** To catch
    `toLocaleLowerCase` the pattern was rewritten as `toLocale?LowerCase` — the `?` made a
    letter optional, not the word, and the gate stopped catching the original sixteen calls.
    The commit was called "closing the hole". → An extended pattern is checked red on the old
    form and on the new one in a single run.
28. **A gate whose red nobody is obliged to see is not a gate.** The check was
    `allow_failure`, filtered by paths and required a tool that was not on a single machine.
    → Danger goes under cheap mandatory gates.
29. **Gates read the exit code, not empty output.** Twelve calls were written as
    `HITS=$(… || true)` — an engine that failed to start printed "clean".
30. **A check on the real database that runs only at night goes red after the release.** → On
    every merge request.

## A project that moves

31. **A review is a photograph.** Over a four-day pause 59 commits went into the main branch,
    the register broke in three places, nobody noticed. → `check` after every merge; the gate
    "every file is owned by someone" (`coverage --no-write`) in the common set of checks.
32. **The coverage gate sees only tracked files.** A new file before `git add` is invisible.
33. **A block that owns hot files cannot stay closed.** The authorization block was closed
    on 20.09 — by 22.09 four new gateways had appeared in its three files. → It is re-read
    last and until then stays in `blocked` with a note.
34. **(ours) The fingerprint of what was reviewed** — files, context and the text of the
    hypotheses — is taken at check time, and a divergence is caught by `check`, not by memory.
    A change to the context is a warning, a change to the block's files is a refusal.

## The tool itself

35. **The review tool is code too and lies too.** Before the self-test it declared the review
    finished with an unread block in `blocked`, counted `running` hours from the first start
    and accepted phases out of order. Reading the code did not catch that. → A self-test where
    every check is proven red on a fake — with us every check is proven by a mutation.
36. **A lesson in the journal does not reach the agents.** The main conclusion of the first
    block lay in the journal for a week, and the prompts of six dozen blocks did not carry it.
    → A lesson for all blocks is moved into the invariants in the same commit.
37. **Review documents die with the review.** Old review documents described long-fixed
    defects as open for months. → The directory is deleted whole in one change, what lasts
    moves into rules, ADRs and tests; the summary remains.
38. **(ours) The method finds faster than the project fixes.** On the first skill project 12%
    of what was found got fixed; in the file-by-file pass of the first version — zero. The
    next block does not start until the serious findings of the previous one are closed.

## The lead session and the human

39. **A block boundary is a full stop.** The owner sets the order and the pace: every block
    produces fixes across the whole code and a queue of decisions for the owner alone. "Next
    we go into block X" as a settled plan is a mistake; the right thing is to report and wait.
40. **A long-running agent is a bad default.** A repeat fix went to the same agent: 79
    minutes and 600 thousand tokens of context. The assignment was self-contained — a fresh
    agent would have done it more precisely.
41. **Findings go into one file, not into the conversation.** Overlapping findings from
    different agents are merged into one record, each is checked against the code and marked
    as you go.
42. **In plain words, and an open question — in full.** The owner stepped away while the work
    went on and did not understand "the two questions from the previous message still
    stand". A question is repeated in full; each has who decides and a recommendation.
