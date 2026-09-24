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
# A failing `review prompt` (an unknown block, a template with a hole) must not leave a
# zero-byte prompt file behind for the next run to find.
$REVIEW prompt "$BLOCK" --role "$ROLE" "$@" > "$PROMPT" || PROMPT_RC=$?
if [ -n "${PROMPT_RC:-}" ]; then
  rm -f "$PROMPT"
  exit "$PROMPT_RC"
fi
echo "prompt: $PROMPT ($(wc -c < "$PROMPT") bytes); cap: $CAP turns; stream: $STREAM"
set +e
claude -p --output-format stream-json --verbose --permission-mode acceptEdits \
  --max-turns "$CAP" ${CLAUDE_MODEL:+--model "$CLAUDE_MODEL"} --allowedTools "$TOOLS" \
  < "$PROMPT" > "$STREAM" 2> "$STREAM.err"
RC=$?
set -e
# Everything below is reporting, and the script's exit code is the RUN's whatever a report
# does: anything scripted on top of run-role.sh reads the ending of `claude`, not the
# ending of a journal write. Under `set -e` a failing report used to abort the script
# before `exit $RC` ever ran, and the operator read the wrong ending.
trap 'exit $RC' EXIT
echo "claude exit: $RC"
python3 "$HERE/../scripts/axes.py" "$STREAM"
LINE="$(python3 "$HERE/../scripts/axes.py" "$STREAM" --journal)"
# The journal is the only memory the next session has. A run that died or was cut off at
# the turn cap used to be written there as an ordinary completed one — "hunter — spend: 0
# min, None turns … $0.00" — with no word that the assignment was truncated, and the block
# read as hunted. The exit code goes into the line; what the stream itself says about the
# ending (no result event, a non-success subtype) axes.py has already put there.
if [ "$RC" -ne 0 ]; then
  LINE="RUN FAILED (claude exit $RC — the assignment was NOT completed) · $LINE"
fi
$REVIEW log "$BLOCK" "$ROLE — $LINE"
# ONE reader for the stream. A second one written here parsed every line with `json.loads`
# and died on the half-written last line a killed run leaves behind — the very line
# `axes.py` counts and reports — so an operator whose run was cut off saw a Python
# traceback instead of the agent's answer.
python3 "$HERE/../scripts/axes.py" "$STREAM" --reply
exit $RC
