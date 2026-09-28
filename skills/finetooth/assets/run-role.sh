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
# ROLE_MAX_TURNS (override the cap), CLAUDE_MODEL (override the model), ROLE_DENY (tools the
# run must NOT use, passed to `claude -p` as `--disallowedTools`; unset — nothing is denied),
# ALLOW_DIRTY=1 (start a writing role on a dirty tree, see below).
#
# ROLE_DENY is the only limit here. The per-role tool lists below are `--allowedTools`, and
# that flag PRE-APPROVES tools on top of the operator's own permission settings — it does not
# restrict: a measured run given `Read,Grep,Glob,Write` still called Bash (see #27). For a run
# that must not reach something — the repository's history, a neighbouring repository — deny
# it, or run the agent in a sandbox:
#
#   ROLE_DENY="Bash(git *),Read(//home/me/other-repo/**)" assets/run-role.sh H1 hunter
#
# An absolute path in a rule needs `//`: measured, `Read(/home/x/**)` matched nothing and the
# read went through, while `Read(//home/x/**)` refused Read, Grep and `cat` alike.
#
# A role that writes (fix, fixreview) does not start in a dirty tree: uncommitted changes
# outside docs/review/ (where the roles' own reports and drafts live) are refused with exit 4.
# In a field run 16 of 46 fixer runs ended on the turn cap with their edits uncommitted, and
# the next run started on top of that work in progress. ALLOW_DIRTY=1 starts it anyway — the
# operator's call, said out loud. Whatever the role, a tree left dirty after the run is named
# in the output and in the journal line.
#
# Stopping a run: the PID of `claude -p` is written to `<stream>.pid` for as long as it runs
# (the path is printed at the start), so
#
#   kill "$(cat /tmp/finetooth-runs/H1.fix.<stamp>.stream.jsonl.pid)"
#
# stops the agent itself. Stopping this script (Ctrl-C, `kill`) passes the stop on to it as
# well — killing the wrapper alone once left `claude -p` running, and a verifier wrote its
# report after the stop — and the spend of the cut run is still reported.
set -euo pipefail
BLOCK="${1:?block id}"; ROLE="${2:?role}"; shift 2
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REVIEW="${REVIEW:-python3 $HERE/../scripts/review.py}"
# Pre-approvals, not limits: whatever the operator's settings allow is allowed on top of
# these lists, so "the verifier has no network" is not something a list can promise. What a
# run must not do goes into ROLE_DENY (see the header).
case "$ROLE" in
  # The hunter executes too: a block with `proof: measured` is proven by runs, and three
  # blocks of the kit's own review (T1–T3) had their hunter refused `python3` and fall back to
  # reading. It still changes no project file — the role template forbids it. `uv run` is
  # how a uv project runs its tests: a field hunter without it wrapped `.venv/bin` into PATH
  # (see #45). verify, fix and fixreview get `uv *` too — a stand or a fix may need
  # `uv sync` first; the hunter gets only `uv run`, since `uv add` changes project files.
  hunter)    CAP=110; TOOLS="Read,Grep,Glob,Write,Edit,Bash(git *),Bash(grep *),Bash(rg *),Bash(ls *),Bash(wc *),Bash(find *),Bash(cat *),Bash(sed *),Bash(head *),Bash(tail *),Bash(npm test *),Bash(npm run *),Bash(npx *),Bash(node *),Bash(python3 *),Bash(pytest *),Bash(uv run *),Bash(make *)";;
  verify)    CAP=330; TOOLS="Read,Grep,Glob,Write,Edit,Bash(git *),Bash(grep *),Bash(rg *),Bash(ls *),Bash(wc *),Bash(find *),Bash(cat *),Bash(sed *),Bash(head *),Bash(tail *),Bash(npm test *),Bash(npm run *),Bash(npx *),Bash(node *),Bash(python3 *),Bash(pytest *),Bash(uv run *),Bash(uv *),Bash(make *)";;
  fix|fixreview) CAP=330; TOOLS="Read,Grep,Glob,Write,Edit,Bash(git *),Bash(grep *),Bash(rg *),Bash(ls *),Bash(wc *),Bash(find *),Bash(cat *),Bash(sed *),Bash(head *),Bash(tail *),Bash(npm test *),Bash(npm run *),Bash(npx *),Bash(node *),Bash(python3 *),Bash(pytest *),Bash(uv run *),Bash(uv *),Bash(make *)";;
  *) echo "unknown role: $ROLE" >&2; exit 2;;
esac
CAP="${ROLE_MAX_TURNS:-$CAP}"
# The tree as git sees it, minus the review directory: the roles write their reports and
# drafts there by design. Pathspecs from the top, so the answer does not depend on where in
# the tree the script was started.
dirty() { git status --porcelain -- ':/' ':(top,exclude)docs/review'; }
DIRTY_BEFORE="$(dirty)"
case "$ROLE" in
  fix|fixreview)
    if [ -n "$DIRTY_BEFORE" ]; then
      if [ "${ALLOW_DIRTY:-}" != 1 ]; then
        echo "refusing to start $ROLE: the working tree has uncommitted changes outside docs/review/:" >&2
        printf '%s\n' "$DIRTY_BEFORE" >&2
        echo "A $ROLE run edits and commits in this tree, and it would build on work nobody reviewed — often what a previous run left behind when it hit the turn cap. Commit it, stash it or remove it; to start on this tree anyway, run again with ALLOW_DIRTY=1." >&2
        exit 4
      fi
      echo "ALLOW_DIRTY=1: starting $ROLE on a dirty tree" >&2
    fi;;
esac
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
echo "to stop the run: kill \"\$(cat $STREAM.pid)\""
set +e
# The PID file is written by the process that then becomes `claude` (exec keeps the PID), so
# it exists before the agent does anything — a file written after the start raced the run.
( echo "$BASHPID" > "$STREAM.pid"
  exec claude -p --output-format stream-json --verbose --permission-mode acceptEdits \
    --max-turns "$CAP" ${CLAUDE_MODEL:+--model "$CLAUDE_MODEL"} --allowedTools "$TOOLS" \
    ${ROLE_DENY:+--disallowedTools "$ROLE_DENY"} ) \
  < "$PROMPT" > "$STREAM" 2> "$STREAM.err" &
PID=$!
# A stop of this script is a stop of the run: passed on to the agent, and the report below
# still runs on what the stream holds.
trap 'kill -TERM "$PID" 2>/dev/null' TERM INT HUP
wait "$PID"; RC=$?
# A trapped signal interrupts `wait` before the agent has ended — wait for the agent itself.
while kill -0 "$PID" 2>/dev/null; do wait "$PID"; RC=$?; done
trap - TERM INT HUP
rm -f "$STREAM.pid"
# Everything below is reporting. Every step runs even if an earlier one failed — the reply
# must reach the operator — and the exit code tells both endings apart: the run's own code
# when `claude` failed, 3 when the run succeeded but a report was lost (no journal line: the
# only memory the next session has). A trap that always exited with the run's code hid a
# failed journal write behind exit 0 (the kit's own review, fix review round 3).
REPORT_RC=0
echo "claude exit: $RC"
python3 "$HERE/../scripts/axes.py" "$STREAM" || REPORT_RC=$?
LINE="$(python3 "$HERE/../scripts/axes.py" "$STREAM" --journal)" || REPORT_RC=$?
# The journal is the only memory the next session has. A run that died or was cut off at
# the turn cap used to be written there as an ordinary completed one — "hunter — spend: 0
# min, None turns … $0.00" — with no word that the assignment was truncated, and the block
# read as hunted. The exit code goes into the line; what the stream itself says about the
# ending (no result event, a non-success subtype) axes.py has already put there.
if [ "$RC" -ne 0 ]; then
  LINE="RUN FAILED (claude exit $RC — the assignment was NOT completed) · $LINE"
fi
# What the run left behind. A run cut off mid-edit, a scratch file, a draft test: the next
# role starts on it unless someone looks, and the journal is where the next session looks.
DIRTY_AFTER="$(dirty)" || REPORT_RC=$?
if [ -n "$DIRTY_AFTER" ]; then
  COUNT="$(printf '%s\n' "$DIRTY_AFTER" | wc -l | tr -d ' ')"
  SINCE=""
  if [ -n "$DIRTY_BEFORE" ]; then SINCE=", dirty before the run too"; fi
  echo "the working tree is dirty after the run — $COUNT path(s) outside docs/review/$SINCE:"
  printf '%s\n' "$DIRTY_AFTER"
  LINE="TREE LEFT DIRTY ($COUNT path(s) outside docs/review/$SINCE) · $LINE"
fi
$REVIEW log "$BLOCK" "$ROLE — $LINE" || { REPORT_RC=$?; echo "journal write failed — the spend line above is not recorded" >&2; }
# ONE reader for the stream. A second one written here parsed every line with `json.loads`
# and died on the half-written last line a killed run leaves behind — the very line
# `axes.py` counts and reports — so an operator whose run was cut off saw a Python
# traceback instead of the agent's answer.
python3 "$HERE/../scripts/axes.py" "$STREAM" --reply || REPORT_RC=$?
if [ "$RC" -ne 0 ]; then exit "$RC"; fi
if [ "$REPORT_RC" -ne 0 ]; then exit 3; fi
exit 0
