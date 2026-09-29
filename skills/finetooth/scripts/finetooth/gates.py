"""Refusals and the gates every finding row passes — shared by check and import."""

from __future__ import annotations

from .git import git
from .workspace import CLI
from .model import CLAIM_MAX, CONFIDENCE, FINDING_STATUS, SCENARIO_MAX, SEVERITIES
from .fingerprint import file_sha, locate_region, text_lines
from .register import dup_problem, file_problem, finding_file, location_problems, reject_reason_of


def finding_gates(gates: "Refusals", f: dict, rows: list[dict], idx: dict,
                  tracked: set[str], seen_ids: set[str]) -> None:
    """The gates `check` holds on one finding of the register `rows` — and the ONE place
    they are written: `import --dry-run` asks them of the rows the import would write, so a
    draft the dry run passed cannot be refused by `check` right after the import (fix review
    of the 0.8.0 candidate: the dry run asked a copy of some of these rules of the row as
    written, and `"confidence": null`, a `rejected` confidence with no reason, a `fixed`
    status with no commit were all called clean and refused a minute later). `seen_ids`
    carries the ids already met, for the duplicate-id gate."""
    fid = f.get("id", "<no id>")
    if fid in seen_ids:
        gates.refuse("finding/duplicate-id", f"finding {fid}: duplicate id")
    seen_ids.add(fid)
    for field in ("id", "block", "severity", "confidence", "status", "file", "claim", "scenario"):
        # A `file` that is falsy but not a string (0, false, [], {}) is refused below as
        # not a path — by what was written, not as an empty field on top of that.
        if field == "file" and file_problem(f):
            continue
        if not f.get(field):
            gates.refuse("finding/empty-field", f"finding {fid}: field {field} is empty")
    # An empty field is named above and nowhere else: `"severity": null` used to be refused
    # twice, as empty and as `severity=None is not in the vocabulary`, and the dry run printed
    # both for one row (one message per problem, fix review of the 0.8.0 candidate).
    if f.get("block") and f.get("block") not in idx:
        gates.refuse("finding/unknown-block",
                     f"finding {fid}: refers to nonexistent block {f.get('block')}")
    if f.get("severity") and f.get("severity") not in SEVERITIES:
        gates.refuse("finding/severity-unknown",
                     f"finding {fid}: severity={f.get('severity')} is not in the vocabulary "
                     f"({', '.join(SEVERITIES)})")
    if f.get("confidence") and f.get("confidence") not in CONFIDENCE:
        gates.refuse("finding/confidence-unknown",
                     f"finding {fid}: confidence={f.get('confidence')} is not in the vocabulary "
                     f"({', '.join(CONFIDENCE)})")
    if f.get("status") and f.get("status") not in FINDING_STATUS:
        gates.refuse("finding/status-unknown",
                     f"finding {fid}: status={f.get('status')} is not in the vocabulary "
                     f"({', '.join(FINDING_STATUS)})")
    place = location_problems(f, tracked)
    if "file-not-a-string" in place:
        gates.refuse("finding/file-not-a-string", f"finding {fid}: {place['file-not-a-string']}")
    if "file-missing" in place:
        gates.refuse("finding/file-missing", f"finding {fid}: {place['file-missing']}")
    # A deferred finding does not count as open and therefore survives the whole
    # review unnoticed. The reason is what turns it from silence into a decision: the
    # summary publishes deferred findings as accepted risks, by that reason and no
    # other text. The message used to demand that every deferral be resolved before
    # the end, which is not what the tool holds and not what the summary does with it.
    if f.get("status") == "deferred" and not (f.get("defer_reason") or "").strip():
        gates.refuse(
            "finding/deferred-without-reason",
            f"finding {fid}: deferred without a reason — `{CLI} set-finding {fid} deferred "
            f"--reason '...'`; a deferral is an accepted risk, and the summary publishes it by that reason"
        )
    if f.get("status") == "fixed" and f.get("fix_commit") and ":" in str(f["fix_commit"]):
        # A fix in a NEIGHBOURING repository: `<repository>:<commit>`. It is not here and
        # cannot be, there is nothing to check — but the mark must be explicit. Without
        # it such a commit looks like our own, and the check honestly reports that it
        # does not exist; that is what happened with the finding about the other core.
        repo, _, sha = str(f["fix_commit"]).partition(":")
        if not repo or not sha:
            gates.refuse(
                "finding/external-fix-malformed",
                f"finding {fid}: an external fix is written as `<repository>:<commit>`"
            )
    elif f.get("status") == "fixed" and f.get("fix_commit"):
        # The fix commit must exist and touch the finding's file. Two marks in a
        # neighbouring project pointed at a commit that did not touch the named file at
        # all: the fix was made in another module, and the record stayed as it was. By
        # hand nobody checks that — and nobody did for half a year.
        # The paths are compared as git prints them for `ls-files`: raw and
        # NUL-separated. C-quoted, a Cyrillic name matched nothing, and no finding on
        # such a file could ever be marked fixed — the gate stayed red on a truthful
        # state for ever.
        touched = git("show", "--name-only", "--format=", f["fix_commit"])
        if touched.code != 0:
            gates.refuse("finding/commit-missing",
                         f"finding {fid}: commit {f['fix_commit']} is not in the repository")
        elif finding_file(f) and not ({finding_file(f), *f.get("fixed_in", [])}
                                      & set(touched.fields)):
            gates.refuse(
                "finding/commit-does-not-touch",
                f"finding {fid}: commit {f['fix_commit']} does not touch {finding_file(f)} — "
                f"either the mark belongs to another finding, or the fix was made elsewhere: "
                f"then name it (`{CLI} set-finding {fid} fixed --commit <sha> "
                f"--fixed-in <path>`)"
            )
    if f.get("status") == "fixed" and not f.get("fix_commit"):
        gates.refuse("finding/fixed-without-commit",
                     f"finding {fid}: marked fixed, but no fix commit is given")
    if f.get("status") == "duplicate" and not f.get("dup_of"):
        gates.refuse("finding/duplicate-without-target",
                     f"finding {fid}: marked duplicate, but not of what exactly")
    elif f.get("status") == "duplicate" and (why := dup_problem(fid, f["dup_of"], rows)):
        gates.refuse("finding/duplicate-target-unusable", why)
    if f.get("confidence") == "rejected" and f.get("status") == "open":
        gates.refuse("finding/rejected-but-open",
                     f"finding {fid}: rejected by the verifier, but still open")
    if f.get("status") == "rejected" and f.get("confidence") != "rejected":
        gates.refuse(
            "finding/rejected-without-confidence",
            f"finding {fid}: status rejected but confidence {f.get('confidence')} — "
            f"the register claims 'rejected' and 'not rejected' at once"
        )
    # The code under the finding moved on — so either it was already fixed, or the
    # description is stale. Both demand action, not silence: a finding that is not
    # moved makes the next pass argue with nonexistent code.
    if (f.get("status") in ("open", "deferred") and not f.get("code_sha")
            and not f.get("region_sha") and file_sha(finding_file(f))):
        gates.refuse(
            "finding/no-code-fingerprint",
            f"finding {fid}: no code fingerprint — changes in {finding_file(f)} under it are not "
            f"tracked; `{CLI} backfill`"
        )
    # The region form (#37): only the lines around the finding count, wherever they have
    # moved. The whole-file form is read as before, so a register written by an older
    # kit keeps its meaning until `restamp` moves each record over.
    if (f.get("status") in ("open", "deferred") and f.get("region_sha")
            and file_sha(finding_file(f))):
        lines = text_lines(finding_file(f))
        at = locate_region(f, lines) if lines is not None else None
        if at is None:
            gates.refuse(
                "finding/region-changed",
                f"finding {fid}: the code around {finding_file(f)}:{f.get('line')} changed since "
                f"it was stamped — re-check: either it is already closed (`{CLI} set-finding "
                f"{fid} fixed --commit <sha>`), or the description is stale, or the defect is "
                f"still there (`{CLI} restamp {fid}`, with `--line <N>` if it now sits elsewhere)"
            )
        # Found on another line — nothing to say. Every display shows the line the window
        # sits on now (`shown_lines`), so a shift above the finding is not a stale record;
        # the warning that used to name it (`finding/line-moved`) came on every PR that
        # touched an actively edited file and asked for a `restamp` that changed nothing
        # but a display. The recorded line is still read in one place — to pick the
        # nearest copy when the window repeats in its file — and no cited window repeated
        # from K=2 on in the measurement behind REGION_K, so a drifting record costs
        # nothing measured; a "large shift" threshold would be a number from the head.
    elif f.get("status") in ("open", "deferred") and f.get("code_sha"):
        fresh = file_sha(finding_file(f))
        if fresh and fresh != f["code_sha"]:
            gates.refuse(
                "finding/code-changed",
                f"finding {fid}: code in {finding_file(f)} changed since import — "
                f"re-check: either it is already closed (`{CLI} set-finding {fid} fixed "
                f"--commit <sha>`), or the description is stale, or the defect is still there "
                f"(`{CLI} restamp {fid}`"
                + (" — for a finding with a line it also moves the record to a fingerprint "
                   "of the lines around it, which edits elsewhere in the file leave alone)"
                   if f.get("line") is not None else ")")
            )
    if "line-not-a-number" in place:
        gates.refuse("finding/line-not-a-number", f"finding {fid}: {place['line-not-a-number']}")
    if "line-past-end" in place:
        gates.refuse("finding/line-past-end", f"finding {fid}: {place['line-past-end']}")
    # A rejected finding stays in the register for the sake of the reject reason —
    # without it the record is useless: the next review finds the same thing and
    # spends the time again. The review's completion condition demanded a reason for
    # every rejected finding from the start, but there was no check, and the field stayed empty.
    if f.get("status") == "rejected":
        if not reject_reason_of(f):
            gates.refuse(
                "finding/rejected-without-reason",
                f"finding {fid}: rejected, but the reject reason is not recorded — "
                f"`{CLI} set-finding {fid} rejected --reason '...'` (in a draft not yet imported, "
                f"the field `reject_reason`) or a claim that starts with 'Rejected: …' (in the "
                f"review language)"
            )
    if len(f.get("claim") or "") > CLAIM_MAX:
        gates.refuse(
            "finding/claim-too-long",
            f"finding {fid}: claim is {len(f['claim'])} characters against a limit of {CLAIM_MAX} — "
            "it is a headline for the summary table, the evidence goes into the block report"
        )
    if len(f.get("scenario") or "") > SCENARIO_MAX:
        gates.refuse(
            "finding/scenario-too-long",
            f"finding {fid}: scenario is {len(f['scenario'])} characters against a limit of {SCENARIO_MAX}"
        )


class Refusals:
    """Everything `check` has to say, and the one way for a gate to say it.

    A gate is a mechanism that must not be removable in silence: CONTRIBUTING promises that
    each one comes with a test, and the suite holds a table pairing every gate with the test
    that reddens when it is disabled. For that table to be complete, the gates have to be
    countable — and while a gate was "a line that appends to a list called `problems`", they
    were not: a gate written in a helper whose parameter is called something else, or
    accumulated with `extend`, or assigned, gave no name to pair, no test, and could be
    deleted later with the whole suite green. Three rounds of review found that same shape
    three times, in a new spelling each time.

    So a refusal is a pair — the gate's KEY, which the call site writes itself, and the text
    a human reads. The key is never printed: the user reads the message, and the key is what
    the gate is called by the suite's table and by the mutation run that proves the table.
    There is one container and two verbs, `refuse` (the state is wrong: exit 1) and `warn`
    (worth a look, exit unchanged), so adding a gate anywhere in the tool means naming it.
    """

    def __init__(self) -> None:
        self.said: list[tuple[bool, str, str]] = []      # (fatal, key, message)

    def refuse(self, key: str, message: str) -> None:
        """The state is wrong: `check` prints the message and exits 1."""
        self.said.append((True, key, message))

    def warn(self, key: str, message: str) -> None:
        """Worth a human's eye, but not a red state: printed, exit code unchanged."""
        self.said.append((False, key, message))

    @property
    def problems(self) -> list[str]:
        return [m for fatal, _, m in self.said if fatal]

    @property
    def warnings(self) -> list[str]:
        return [m for fatal, _, m in self.said if not fatal]

    def report(self) -> int:
        """Print what the gates said and give `check` its exit code.

        The code is computed here and nowhere else: a gate that printed its own refusal and
        returned by itself would be outside every table that counts them.
        """
        if self.warnings:
            print("WARNINGS (do not fail the check):\n")
            for w in self.warnings:
                print(f"  · {w}")
            print()
        if self.problems:
            print("CHECK FAILED:\n")
            for p in self.problems:
                print(f"  · {p}")
            return 1
        print("review state is consistent")
        return 0
