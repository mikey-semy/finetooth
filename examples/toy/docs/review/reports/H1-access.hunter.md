# H1 — hunter report

## Coverage
- files read: 3 of 3
- src/auth/session.ts
- src/auth/guard.ts
- tests/guard.test.ts
- not read: none

## Hypotheses
- H1.1 — checked: `sessionFor("u1:")` returns `{userId:"u1", admin:false}` — an empty role is accepted as a user session. Finding H1-001.
- H1.2 — checked: `"u1:admin:x".split(":")` gives role `"admin"` — the third part is dropped and the token is admin. Finding H1-002.
- H1.3 — checked: `canRead("u2:user", "nobody")` → false, `canRead("u9:admin", "nobody")` → true, as intended.

## Tree freshness
Single-commit toy repository, no remote.

## Findings
### H1-001 · medium · Empty role parses into a user session
**Location:** `src/auth/session.ts:4`
**What is wrong:** a token with an empty role part is accepted.
**Failure scenario:** `sessionFor("u1:")` → `{userId:"u1", admin:false}`; a malformed token grants user-level access.
**Why it is a defect:** invariant "a token grants access to its owner's data only" assumes a valid token.
**Confidence:** confirmed

### H1-002 · high · A token with extra segments is parsed as admin
**Location:** `src/auth/session.ts:4`
**What is wrong:** `split(":")` keeps only the first two parts; `"u1:admin:anything"` is admin.
**Failure scenario:** `canRead("u1:admin:x", "u2")` → true.
**Why it is a defect:** role must be compared exactly.
**Confidence:** confirmed

## Coverage limits
Nothing was skipped; the test file has one case and was read in full. No live stand exists for this toy.
