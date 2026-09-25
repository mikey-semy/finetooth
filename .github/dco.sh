#!/usr/bin/env bash
# Every commit is signed off (CONTRIBUTING.md, "DCO"). The rule was written down and
# nothing checked it: the only artefact was a checkbox in the pull request template, which
# the author ticks and nobody verifies. This is the check.
#
#   .github/dco.sh <base>..<head>
#
# A commit passes when its message carries `Signed-off-by: Name <email>` with the email of
# the commit's own author — that is what the Developer Certificate of Origin asks for: the
# person handing the code over is the one who certifies the right to hand it over. Merge
# commits are not signed: they carry nobody's authorship of the code.
#
# Only git and bash: the kit takes no dependencies, and a check nobody can run locally is
# a check that runs for the first time on someone else's pull request.
set -euo pipefail
RANGE="${1:?commit range, for example origin/dev..HEAD}"

# The addresses of the well-formed `Signed-off-by:` lines of a commit, one per line, folded
# to lower case.
#
# The address is EXTRACTED here and compared as a string by the caller; it is interpolated
# into no pattern. `+` and `.` are legal in a local part — GitHub's privacy-protected
# address, the default for every account that keeps its email private, has the form
# `12345678+login@users.noreply.github.com` — and as regular-expression metacharacters they
# break the check in both directions at once: `+` turns an honest sign-off into a refusal
# whose remedy regenerates the same line, and `.` lets a sign-off naming a different address
# (`aXb@example.com` for an author `a.b@example.com`) count. Case is folded on both sides:
# git keeps the address exactly as it was typed.
signoff_addresses() {
  git show -s --format='%B' "$1" | tr '[:upper:]' '[:lower:]' | sed -n \
    's/^[[:space:]]*signed-off-by:[[:space:]]\{1,\}[^<>]\{1,\}<\([^<>]\{1,\}\)>[[:space:]]*$/\1/p'
}

# The commits are listed BEFORE the loop, and a failure of the listing is fatal. Read through
# a process substitution, `git rev-list` reported its exit code to nobody — `set -e` does not
# see it there — so an unresolvable range (a clone without `origin/dev`, a remote named
# `upstream`) yielded an empty list and the gate announced "all commits are signed off" with
# exit 0, having examined nothing.
if ! commits="$(git rev-list --no-merges "$RANGE")"; then
  cat >&2 <<EOF

git cannot list the commits of \`$RANGE\` (its own message is above), so nothing was checked.

Fetch the branch the range starts from and run it again:

  git fetch origin dev
  .github/dco.sh origin/dev..HEAD

If your remote is not called \`origin\`, name yours: \`.github/dco.sh upstream/dev..HEAD\`.
EOF
  exit 1
fi

failed=0
while IFS= read -r sha; do
  [ -n "$sha" ] || continue
  author="$(git show -s --format='%ae' "$sha")"
  # The line must name THIS commit's author; a sign-off copied from a neighbouring commit
  # certifies nothing.
  want="$(printf '%s' "$author" | tr '[:upper:]' '[:lower:]')"
  if signoff_addresses "$sha" | grep -qxF -- "$want"; then
    continue
  fi
  printf '%s %s — no `Signed-off-by: … <%s>`\n' \
    "$(git show -s --format='%h' "$sha")" "$(git show -s --format='%s' "$sha")" "$author" >&2
  failed=$((failed + 1))
done <<EOF
$commits
EOF

if [ "$failed" -ne 0 ]; then
  cat >&2 <<EOF

$failed commit(s) without a sign-off. Every commit carries
\`Signed-off-by: Name <email>\` — with it you confirm the Developer Certificate of Origin
(https://developercertificate.org/). See CONTRIBUTING.md, section "DCO".

Add it to the commits of this branch and force-push:

  git rebase --signoff $(echo "$RANGE" | sed 's/\.\..*//')

For the next ones: \`git commit -s\`.
EOF
  exit 1
fi
echo "all commits in $RANGE are signed off"
