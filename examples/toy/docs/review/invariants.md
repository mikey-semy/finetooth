# Toy invariants

## Context that changes how findings are judged
There is no production and no legacy data. Two users and one admin exist in the fixtures.

## Rules that must not be broken
- A token grants access to its owner's data only; `admin` sees everything.
- Limits count successes: a failed attempt must not consume quota.

## What is NOT a finding
- Code style; the absence of a framework.
