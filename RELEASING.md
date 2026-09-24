# Releasing

A version number tells the user what to expect from an update. It is not a marker for the
end of a working session. Everything below is what it takes for a number to mean that.

## Numbering — semantic versioning, major version zero

- **`0.X.0`** — anything the user has to act on: the on-disk format of `docs/review/`
  changed, a check became stricter, a command or field was renamed, a default changed.
  The CHANGELOG section **Breaking** is mandatory and says what to do with a review already
  in progress (`backfill`, `restamp`, a field to add).
- **`0.X.Y`** — fixes only: the tool did not do what it promised, and now it does. No format
  change, no new requirement on the user.
- **`1.0.0`** — when the ROADMAP conditions hold: misses are measured on a corpus with a known
  answer (direction 1), a second project in another language has been reviewed with the kit
  (direction 2), and the on-disk format has not changed for a year. Not before.

## Cadence

At most one release a week, and only when **Unreleased** in `CHANGELOG.md` holds something a
user would update for. Small fixes accumulate; they are not a reason to cut a version.

## Gates — all mechanical, all before the tag

1. **Tests green**, and every new check named in CHANGELOG together with the mutation that
   proves its test (break the mechanism → the test goes red).
2. **`skills-ref validate skills/finetooth`** — valid skill.
3. **A run on a live project.** The release candidate has taken at least one block through
   hunter and verifier on a real repository, and `check` is green there. The release notes
   link the journal entry. A version nobody has run is a tag, not a release.
4. **CHANGELOG is complete** before the tag: the version section is written, the compare link
   is added, the GitHub release notes are taken from it verbatim.

## Branches

- **`master`** — releases only. Every commit on it is a tagged version or the merge that
  becomes one. Nobody pushes to it directly, including the maintainer.
- **`dev`** — integration, the default branch. Feature branches start here and come back
  here through a PR with green CI. `dev` may be ahead of the last release for weeks; that is
  its job.
- **Feature branches** — `feat/…`, `fix/…`, `docs/…` from `dev`, one problem each, squash
  merged into `dev`.

## How a release happens

1. Feature branches → PRs → green CI → squash merge into `dev`. When **Unreleased** is worth
   a version and the gates above hold, a PR `dev → master` carries the version bump and the
   CHANGELOG section; it is merged with a merge commit, so `master` keeps the release
   history readable.
2. Bump `VERSION` in `scripts/review.py` and `version` in `SKILL.md` in the same PR that
   moves **Unreleased** under the new version heading.
3. After the merge into `master`: annotated tag `vX.Y.Z` on the merge commit, `gh release create` with the
   CHANGELOG section as notes, `--latest` only for the highest version.
4. A release is never rewritten. A mistake in a release gets the next version.

## What is deliberately not automated

The tag and the release are created by hand after a human has read the CHANGELOG section.
Automated release-on-merge would make gate 3 impossible to enforce.
