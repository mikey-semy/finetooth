# V1 — Billing: quotas and limits

## Why
One function decides how much of the monthly quota is left.

## What counts as a finding here
A limit that counts attempts instead of successes, or that can go negative.

## Hypotheses
1. `quotaLeft` is called with the number of attempts, so a failed attempt consumes quota —
   this violates the invariant "limits count successes".
2. A negative `attempts` value yields more than the limit.

## Acceptance criterion
Both hypotheses answered by a call with concrete numbers, with the output pasted.
