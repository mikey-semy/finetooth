# T1 — fix report, rounds 4–5 (the lead, after stop-and-think)

Fix review round 3 found four defects, all inside the code round 3 changed, one of them a
regression (R3-001 / T1-037). By the rule of the method — a round that finds a defect
introduced by the previous round is a signal to stop and think — the lead took the
quotation class out of the fixer's loop and replaced point fixes with one rule and a
two-sided behaviour table. The first attempt (round 4: "a fence at any indentation, opening
and closing") was itself wrong: fix review round 4 found the inner indented fence closing the
outer one (R4-001, high). Round 5 anchors the close to the opener.

## Closed

| finding | what was done | commit |
|---|---|---|
| T1-037 (R3-001) | a fence opens at any indentation; the rule is held by `QuotationMapTest` row "opening fence deeper than the list column" | round 4, kept in round 5 |
| T1-040 (R3-004) | `run-role.sh` without the EXIT trap; a succeeded run whose journal write failed exits 3, the reply is still printed; tests both ways | round 4 |
| R4-001 | a fence closes only within `FENCE_SLACK` (3) of the column it opened at; table row "indented fence INSIDE a fence does not close it" | round 5 |
| R4-002 | a fence that never closes is read as text (`_quoted_pass` re-runs with the opener excluded); table row "a fence that never closes is text" | round 5 |
| R4-003 | this report; the journal entry below; the rewritten run-role test is now two tests — the failed run keeps its code (7), the lost journal line is exit 3 | round 5 |
| R4-004 | T1-037's scenario shortened under the 700-character limit | round 5 |
| R4-005 | the changelog bullet moved below the section's intro, the intro restated with the real totals | round 5 |

Deferred with a reason: T1-038 (R3-002). Rejected with a reason: T1-039 (R3-003 — both gates
are held by behavioural tests; removing `unquoted()` from either turns the suite red,
measured). T1-007's earlier class guard stands; the quotation class now has a behavioural
guard, not only a source-shape one.

## The guard: `QuotationMapTest`

Ten documents, each line marked Q (quoted) or . (said). Measured red under each earlier
variant of the rule:

- close at any indentation (round 4): `'QQQ.QQ.' != 'QQQQQQ.'`
- no fallback for an unclosed fence: `'.QQQ' != '....'`
- opening limited to three spaces past the content column (round 2): `'.....' != '.QQQ.'`

## The hunter report

Six hypotheses carried contradictory verdicts in `T1-tool.hunter.md` because the report
reviews the verdict parser and therefore quotes verdict syntax — in prose, in code spans and
in its 25-row parser matrix. The lead marked those lines as quotations with `>` (markup only,
text unchanged); every hypothesis keeps the one verdict the hunter gave it in its Hypotheses
section.

## Gates

`python3 -m unittest discover -s tests` — OK (232 tests); `skills-ref validate` — valid.
