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

failed=0
while IFS= read -r sha; do
  [ -n "$sha" ] || continue
  author="$(git show -s --format='%ae' "$sha")"
  # The line must name THIS commit's author; a sign-off copied from a neighbouring commit
  # certifies nothing. The comparison is case-insensitive: git keeps the address as typed.
  if git show -s --format='%B' "$sha" \
      | grep -qiE "^[[:space:]]*Signed-off-by:[[:space:]]+.+<${author}>[[:space:]]*$"; then
    continue
  fi
  printf '%s %s — no `Signed-off-by: … <%s>`\n' \
    "$(git show -s --format='%h' "$sha")" "$(git show -s --format='%s' "$sha")" "$author" >&2
  failed=$((failed + 1))
done < <(git rev-list --no-merges "$RANGE")

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
