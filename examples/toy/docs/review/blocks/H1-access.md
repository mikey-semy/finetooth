# H1 — Access: who may read what

## Why
The token is parsed by hand and the guard is the only place that checks ownership.

## What counts as a finding here
A request that reads data outside its token's ownership; a token that parses into
someone else's identity.

## Hypotheses
1. A token with an empty role part still parses into a user — `"u1:"` should not be a
   session, or the guard should not trust it.
2. A token containing a second colon, `"u1:admin:x"`, is parsed as admin — role must be
   compared exactly, not by prefix.
3. `canRead` for an unknown owner id returns false for everyone except admins.

## Acceptance criterion
A table "input token → expected → actual" for each hypothesis, produced by running
`sessionFor` and `canRead`, not by reading them.
