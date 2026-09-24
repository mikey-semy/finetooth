# Review findings

> This file is GENERATED from `findings.jsonl` by `python3 <skill>/scripts/review.py findings`.
> Do not edit by hand — edit the jsonl and regenerate.

Open: **2** of 2 records.

## high (1 open / 1)

| id | block | status | location | what is wrong |
|---|---|---|---|---|
| H1-002 | H1 | open | `src/auth/session.ts:4` | A token with extra segments is parsed as admin |

## medium (1 open / 1)

| id | block | status | location | what is wrong |
|---|---|---|---|---|
| H1-001 | H1 | open | `src/auth/session.ts:4` | Empty role parses into a user session |

