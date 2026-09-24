#!/usr/bin/env bash
# Run one review role headless with the spend measured and written to the journal.
#
#   assets/run-role.sh <BLOCK> <hunter|verify|fix|fixreview> [extra args for `review prompt`]
#
# Runs `claude -p` on the role's prompt from the root of the repository under review, keeps
# the event stream (it is the measurement), prints the spend by axis (scripts/axes.py) and
# appends one line to docs/review/journal.md. The cost of a run is turns × context, so the
# turn cap is the safety switch: the defaults are twice what the first measured run of each
# role needed (hunter 55 turns, verifier 165) — a run that needs more is a run to look at.
#
# Environment: REVIEW (how the project calls the tool; default: this skill's review.py),
# ROLE_MAX_TURNS (override the cap), CLAUDE_MODEL (override the model).
set -euo pipefail
BLOCK="${1:?block id}"; ROLE="${2:?role}"; shift 2
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REVIEW="${REVIEW:-python3 $HERE/../scripts/review.py}"
case "$ROLE" in
  hunter)    CAP=110; TOOLS="Read,Grep,Glob,Write,Edit,Bash(git *),Bash(grep *),Bash(rg *),Bash(ls *),Bash(wc *),Bash(find *),Bash(cat *),Bash(sed *),Bash(head *),Bash(tail *)";;
  verify)    CAP=330; TOOLS="Read,Grep,Glob,Write,Edit,Bash(git *),Bash(grep *),Bash(rg *),Bash(ls *),Bash(wc *),Bash(find *),Bash(cat *),Bash(sed *),Bash(head *),Bash(tail *),Bash(npm test *),Bash(npm run *),Bash(npx *),Bash(node *),Bash(python3 *),Bash(pytest *),Bash(make *)";;
  fix|fixreview) CAP=330; TOOLS="Read,Grep,Glob,Write,Edit,Bash(git *),Bash(grep *),Bash(rg *),Bash(ls *),Bash(wc *),Bash(find *),Bash(cat *),Bash(sed *),Bash(head *),Bash(tail *),Bash(npm test *),Bash(npm run *),Bash(npx *),Bash(node *),Bash(python3 *),Bash(pytest *),Bash(make *)";;
  *) echo "unknown role: $ROLE" >&2; exit 2;;
esac
CAP="${ROLE_MAX_TURNS:-$CAP}"
OUT="${TMPDIR:-/tmp}/finetooth-runs"; mkdir -p "$OUT"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
PROMPT="$OUT/$BLOCK.$ROLE.$STAMP.prompt.md"
STREAM="$OUT/$BLOCK.$ROLE.$STAMP.stream.jsonl"
$REVIEW prompt "$BLOCK" --role "$ROLE" "$@" > "$PROMPT"
echo "prompt: $PROMPT ($(wc -c < "$PROMPT") bytes); cap: $CAP turns; stream: $STREAM"
set +e
claude -p --output-format stream-json --verbose --permission-mode acceptEdits \
  --max-turns "$CAP" ${CLAUDE_MODEL:+--model "$CLAUDE_MODEL"} --allowedTools "$TOOLS" \
  < "$PROMPT" > "$STREAM" 2> "$STREAM.err"
RC=$?
set -e
echo "claude exit: $RC"
python3 "$HERE/../scripts/axes.py" "$STREAM"
LINE="$(python3 "$HERE/../scripts/axes.py" "$STREAM" --journal)"
$REVIEW log "$BLOCK" "$ROLE — $LINE"
python3 - "$STREAM" <<'PY'
import json, sys
for line in open(sys.argv[1], encoding="utf-8"):
    ev = json.loads(line) if line.strip() else {}
    if ev.get("type") == "result":
        print("\n--- agent reply ---\n" + (ev.get("result") or "")[:4000])
PY
exit $RC
