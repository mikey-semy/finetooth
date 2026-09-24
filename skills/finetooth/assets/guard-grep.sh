#!/usr/bin/env bash
#
# The engine behind the `*-check` grep gates in the Makefile.
#
# A gate looks for a forbidden pattern in source files and lets a call escape it
# with a marker comment in the few lines directly above. That pairing is the
# whole subtlety, and doing it with `grep -B N` — as every gate here did until
# this script existed — is wrong in a way that only shows up under review: grep
# runs consecutive hits together into ONE block when their context windows
# touch, so a marker granted to the first call silently exempts the second one
# three lines below it. The escape hatch freed the neighbour instead of itself.
#
# Here each hit is paired with the marker by LINE NUMBER, inside its own file,
# so a marker covers exactly the call it was written above and nothing else.
#
# Usage:
#   guard-grep.sh --pattern <ERE> --marker <text> [--exclude <ERE>]
#                 [--window N] [--skip <glob>] -- <path> [<path>...]
#
#   --pattern   the forbidden pattern (extended regex)
#   --marker    the escape-hatch text, e.g. "audit-log-allowed:"
#   --exclude   a hit ALSO matching this is not a violation (e.g. ".LogTx(")
#   --window    how many lines above a hit the marker may sit (default 3)
#   --skip      filename glob to leave out entirely, repeatable (e.g. "*_test.go")
#
# Prints one `path:line: source` per violation and exits 1; silent with exit 0
# when the tree is clean. It scans files, not directories, so a path that does
# not exist is simply skipped — a gate must not go green because someone moved
# a package.
set -euo pipefail

pattern=""
marker=""
exclude=""
window=3
skips=()

while [ $# -gt 0 ]; do
	case "$1" in
	--pattern) pattern="$2"; shift 2 ;;
	--marker) marker="$2"; shift 2 ;;
	--exclude) exclude="$2"; shift 2 ;;
	--window) window="$2"; shift 2 ;;
	--skip) skips+=("$2"); shift 2 ;;
	--) shift; break ;;
	*) echo "guard-grep: unknown argument: $1" >&2; exit 2 ;;
	esac
done

if [ -z "$pattern" ] || [ -z "$marker" ]; then
	echo "guard-grep: --pattern and --marker are required" >&2
	exit 2
fi
if [ $# -eq 0 ]; then
	echo "guard-grep: no paths to scan" >&2
	exit 2
fi

find_args=(-type f)
for skip in ${skips+"${skips[@]}"}; do
	find_args+=(! -name "$skip")
done

files=()
while IFS= read -r -d '' file; do
	files+=("$file")
done < <(
	for path in "$@"; do
		[ -e "$path" ] || continue
		find "$path" "${find_args[@]}" -print0
	done
)

[ ${#files[@]} -gt 0 ] || exit 0

# The regexes travel through the environment, not through `awk -v`: -v runs the
# value through escape processing, so `\.broker\.Publish\(` would reach the
# program as `.broker.Publish(` — a regex with an unmatched paren, and awk would
# die rather than quietly under-match. ENVIRON hands the text over verbatim.
GG_PATTERN="$pattern" GG_MARKER="$marker" GG_EXCLUDE="$exclude" GG_WINDOW="$window" \
awk '
BEGIN {
	pattern = ENVIRON["GG_PATTERN"]
	marker  = ENVIRON["GG_MARKER"]
	exclude = ENVIRON["GG_EXCLUDE"]
	window  = ENVIRON["GG_WINDOW"] + 0
}
FNR == 1 { delete line }
{ line[FNR] = $0 }
$0 ~ pattern {
	if (exclude != "" && $0 ~ exclude) next
	# The marker may sit on the hit itself (a trailing comment) or in the
	# window of lines directly above it — and nowhere else.
	if (index($0, marker) > 0) next
	for (i = FNR - window; i < FNR; i++) {
		if (i > 0 && index(line[i], marker) > 0) next
	}
	printf "%s:%d: %s\n", FILENAME, FNR, $0
	found = 1
}
END { exit(found ? 1 : 0) }
' "${files[@]}"
