"""Messages in the review's language (en, ru) and the scaffolds taken from assets/."""

from __future__ import annotations

import json
from pathlib import Path

from .base import SKILL_DIR
from .workspace import BLOCKS_FILE


# Review languages. The tool's own messages are always English; what is translated into
# the project's language is what the agent reads in the prompt and what a human reads in
# the docs/review/ artifacts: rule 1, headings, the reading budget, findings.md, the
# journal, the setup scaffolds.
LANGS = ("en", "ru")
# Assets the setup hands to the project. The English name is the canonical one; a copy in
# another language sits next to it with the language before the extension
# (`entry-point.ru.md`). The names live here and not in the text of `cmd_setup`, because a
# checklist that hardcodes them names the English samples to a Russian review — and the
# translated copies were then reachable from nowhere in the kit.
ASSET_ENTRY = "entry-point.md"
ASSET_BANNER = "agent-banner.md"
ASSET_INVARIANTS = "invariants.example.md"
ASSET_MANIFEST = "manifest.example.md"
ASSET_JOURNAL = "journal.example.md"
ASSET_BLOCKS = "blocks.example.json"


def asset(name: str, lang: str) -> Path:
    """The asset in the review language, falling back to the English one.

    A definition sample is the same in any language, and a project may translate only
    part of the set: a missing copy is not a refusal, it is the English file.
    """
    assets = SKILL_DIR / "assets"
    stem, dot, ext = name.rpartition(".")
    localized = assets / f"{stem}.{lang}{dot}{ext}"
    return localized if lang != "en" and localized.exists() else assets / name


def fill(text: str, project: str, cli: str) -> str:
    """Substitutions of the scaffolds: the project's name and the command it calls the
    tool by. A scaffold that names `make review-status` to a project without a Makefile
    sends every future session to a command that does not exist."""
    return text.replace("{{PROJECT}}", project).replace("{{CLI}}", cli)


MSG = {
 "en": {
  "none": "(none)",
  "refs_cut": "\n\n({n} files. The list is collapsed to patterns — expand the part you need yourself: `git ls-files -- <pattern>`.)",
  "vol_head": "Files: {n}. Lines: {lines}. Order of magnitude: ~{k}k tokens just to read, before any reasoning or tool calls.",
  "vol_fits": "This fits what can be read in one session (ceiling {limit} lines).",
  "vol_sweep": "\n**The acceptance criterion sweeps beyond the block:** {n} more files, {lines} lines (`sweep` in blocks.json). Do not read them one by one — attention falls off at the end of a long list. Enumerate the places mechanically: a script at `docs/review/sweeps/{id}.<ext>` (grep, a parser) that prints every place with its path and line; commit it, then read the places it found. The script is the proof that the list is complete.",
  "vol_over": "\n⚠️ **The block is larger than one session can read** — {lines} lines against a ceiling of {limit}. Reading everything carefully will not work, and the only honest way out is to read as much as you can and **name the rest by path** in the coverage-limits section of your report. Do not pretend you read it. The block will not be accepted as hunted until it is split (`set-status` refuses it), so open the report by saying it must be split and along which subjects.",
  "vol_over_verify": "\n⚠️ **The block is larger than one session can read** — {lines} lines against a ceiling of {limit}. Reading everything carefully will not work, and the only honest way out is to read as much as you can and **name the rest by path** in the block-coverage-status section of your report, opening it with the words \"Coverage is incomplete\". Do not pretend you read it.",
  "vol_border": "\nWhere the budget line runs (largest first, cumulative):",
  "vol_more": "  … and {n} more file(s)",
  "vol_legend": "\n▲ — beyond the line. Not a ban on opening them: it is what you must name as unread if you did not.",
  "vol_lines": "lines",
  "gates_missing": "(the \"gates\" field in blocks.json is empty — list the project's gate commands)",
  "commit_dco": "**The project requires a DCO sign-off** — stated in {where}. Commit every fix with `git commit -s`, under the name and email the project expects: the sign-off must name the commit's own author, and the global git identity of this machine is not that by default. The rest of the commit rules (message convention, language) are in the same files — read them before the first commit.",
  "commit_no_docs": "the contribution docs (the project has neither CONTRIBUTING nor AGENTS.md)",
  "commit_none": "(no commit rules of the project were found: no sign-off requirement in {docs} or in `.github/` — look at CONTRIBUTING and at the CI jobs about commits yourself before the first commit)",
  "commit_dco_review": "**The project requires a DCO sign-off** — stated in {where}. Check every commit of the diff range: {gate} A commit without `Signed-off-by`, or signed off by someone other than its own author, is a finding — the project's CI refuses it, and the change cannot land until the history is rewritten.",
  "commit_gate_script": "run the project's own check, `{script} {range}`, and put its output in the report.",
  "commit_gate_log": "the project has no script for it, so read the trailers: `git log --format='%h %an <%ae> %(trailers:key=Signed-off-by,valueonly,separator=%x2C )' {range}`.",
  "commit_none_review": "(no commit rules of the project were found: no sign-off requirement in {docs} or in `.github/` — if CONTRIBUTING or a CI job states one after all, check the commits of the range against it)",
  "proof_live": "**The block owns no files: it works against the running system.** What to bring up, what to run and which artifact to hand in is in the manifest below; without that artifact the block is not closed. Read code only as much as is needed to set up the experiment and explain its outcome.",
  "proof_measured_verify": "**The block is proven by artifacts, not by reading** (`proof: measured`). Do not re-read files after the hunter: rebuild every artifact from the manifest with the same command and compare line by line with what was handed in. A discrepancy is a finding; an artifact that cannot be rebuilt means the block is not closed.",
  "proof_measured": "**The block is proven by artifacts, not by reading** (`proof: measured`). The file list below outlines the area, not a reading assignment: which artifacts to hand in and how to obtain them is in the manifest, and without them the block is not closed. Read what the artifact needs and do not report reading that did not happen.",
  "proof_read_verify": "**Every file in the list below had to be read in full by someone.** If the hunter admitted skipping part of it, read that part yourself; if the hunter is silent about a file, that does not mean it was read.",
  "proof_read": "**Read EVERY file in the list below in full.** Not selectively, not \"the key ones\". The list is generated mechanically and is the subject of your work. If a file is too large, read it in parts — but read all of it.",
  "files_live": "Block files: none — the block works against the running system",
  "files_measured": "Block files ({n}) — the block's area; proof is the manifest's artifacts",
  "files_read": "Block files ({n}) — read all",
  "scope_line": " Your half of the fixes: **{scope}** — you file findings for this half; whatever else is in the diff below, read it for context.",
  "diff_vol": "The diff below: {kb} KB, {lines} lines. Order of magnitude: ~{k}k tokens just to read it, before any reasoning or tool calls. If that does not fit what you can hold at once, do not read half of it and report on the whole: say so in the report, and the lead splits the RANGE — `--diff <first part>` for you and `--diff <second>` for a second reviewer; that is what makes the diff smaller. `--scope <half>` does not: it names your half in the report and in its file name.",
  "no_open_findings": "(no open findings for this block — ask the lead session why the fixer was started)",
  "fix_batch": "**This run takes {cap} of the {n} open findings: {ids}.** They are the first {cap} by severity in the list below. Close them — each committed as it lands — and stop: leave the rest `open`, the next fixer run takes them. The limit is measured, not a guess: in a field run, 16 of 46 fixer runs ended on the turn cap on batches larger than 3–4 findings, their work uncommitted.",
  "rec_none": "(nothing is recorded against this block yet)",
  "rec_row": "- **{id}** · {severity} · {status} · `{where}` — {claim} _(recorded {date})_",
  "dec_none": "(no human decision is recorded for this block — work by the rules above)",
  "loop_stop": "loop signal: the top finding lies in the code the previous round wrote — the human decides. {id} ({sev}, {file}:{line}) of fix review round {prev} sits on a line fix round {prev} changed ({diff}); another round would repeat that pattern. Record the decision — a different mechanism, a revert of the class, or closing the block — with `{cli} decide {block} \"<decision>\"`: it goes into the next fix and fix review prompts. If the decision is to close the block: `{cli} set-status {block} closed`.",
  "dec_row": "- **{date}**, after fix review round {round}: {text}",
  "draft_unimported": "{block}: the draft {draft} holds {n} row(s) the register does not — the findings the block's verification wrote are not in the review: `summary`, `findings.md`, `sarif` and the fix gate do not see them. Take them in: `{cli} import {block}` when the block has nothing recorded yet, `{cli} import {block} --append` on top of what is recorded; then `{cli} findings`.",
  "confirmed_no_finding": "{block}: {report} confirms hypothesis {h} but names no finding. The way out depends on what the verdict means. The defect is there: a confirmed hypothesis is a defect, and a defect that is not a finding reaches neither the register nor the fix gate — write it up in the draft {draft} and put its id on the verdict line: `{h} — confirmed: {block}-NNN — <what proves it>`. It is not a defect, and the word only stands in the proof (\"no defect was confirmed\", \"the guard is there, confirmed by the test\"): rewrite the verdict as `{h} — refuted: <why it is not a defect>`, with no word confirmed on its line or in the proof under it — the gate reads both. The line is the template's sample copied as it stands (`{block}-NNN`, `<what exactly proves it>`): it answers nothing — check the hypothesis and write the verdict you reached.",
  "confirmed_unknown_finding": "{block}: {report} confirms hypothesis {h} with {ids}, which neither the draft {draft} nor the register holds — name the id the finding has (or will get on import, in the draft's order from the prompt's first new id), or write the finding up in the draft. If what was confirmed is not a defect, the verdict is `{h} — refuted: <why it is not a defect>`.",
  "draft_unreadable": "{block}: the draft {draft} cannot be read, so its findings are not in the register — {why}. Fix the line, then `{cli} import {block}` (or `--append` on top of what is recorded).",
  "f_where": "**Location:**", "f_claim": "**What is wrong:**", "f_scenario": "**Failure scenario:**", "f_invariant": "**Violated invariant:**", "f_conf": "confidence",
  "md_title": "# Review findings", "md_gen": "> This file is GENERATED from `findings.jsonl` by `{cli} findings`.", "md_noedit": "> Do not edit by hand — edit the jsonl and regenerate.",
  "md_open": "Open: **{live}** of {total} records.", "md_sev": "## {sev} ({open} open / {total})", "md_cols": "| id | block | status | location | what is wrong |",
  "journal_head": "# Review journal\n\n",
  "sum_title": "# {project} — review summary",
  "sum_intro": "This file outlives `docs/review/`: it describes the past and holds no status that can go stale. Base commit — the revision everything below was read against. To see how far each block has drifted since: `{cli} summary --aged <this file>`.",
  "sum_base": "**Date:** {date}  \n**Base commit:** `{sha}` ({branch})  \n**Blocks:** {closed} closed of {total}; **findings:** {total_f} — fixed {fixed}, rejected {rejected}, deferred {deferred}, duplicates {dups}, still open {open}",
  "sum_blocks": "## Blocks and what counted as checked",
  "sum_blocks_head": "| block | title | status | finished | files | reviewed at | acceptance criterion |",
  "sum_rejected": "## Rejected findings — do not find them again",
  "sum_rejected_none": "No rejected findings.",
  "sum_deferred": "## Accepted risks (deferred with a reason)",
  "sum_deferred_none": "Nothing deferred.",
  "sum_classes": "## What closed each class",
  "sum_classes_rules": "Guards (a test or a rule — and the findings it is recorded on):",
  "sum_classes_fixes": "Fixes by commit:",
  "sum_classes_none": "No guards recorded; fixes, if any, are listed above by commit.",
  "sum_open": "## Still open at the time of the summary",
  "sum_open_none": "Nothing open.",
  "sum_seams": "## Seams between blocks (from `coupling`)",
  "sum_machine": "## For the tool — do not edit",
  "sum_coverage": "**Files:** {covered} of {total} are in blocks, {unowned} without a block, {excluded} excluded from review",
  "sum_economy": "## Economy (measured role runs from the journal)",
  "sum_economy_head": "| role | runs | of them unmeasured | turns | cost |",
  "sum_at_least": "≥ {v}",
  "sum_not_known": "unknown",
  "sum_economy_total": "total",
  "sum_economy_unknown": "Runs whose turns or cost the stream did not report: {n}. They are counted as runs, never as zero: a sum they are part of is a lower bound (≥), and \"unknown\" when no run in it reported the number.",
  "sum_economy_none": "No measured role runs in the journal (`assets/run-role.sh` writes them).",
  "h_title": "{project} — review summary",
  "h_meta": "Date {date} · base commit {sha} ({branch}) · finetooth {version}",
  "h_intro": "What was reviewed, what was found, what was fixed, what it cost and what is left — counted from the review register and journal at the base commit. The Markdown summary (`{cli} summary`) carries the same numbers.",
  "h_goal": "Goal and coverage",
  "h_t_blocks": "blocks closed",
  "h_t_findings": "findings recorded",
  "h_t_fixed": "fixed",
  "h_t_open": "still open",
  "h_t_deferred": "accepted risks",
  "h_t_files": "files in blocks",
  "h_t_cost": "measured cost",
  "h_of": "{a} of {b}",
  "h_coverage": "{covered} of {total} files are in blocks; {unowned} without a block; {excluded} excluded from review with a stated reason.",
  "h_goals": "What each block set out to check:",
  "h_blocks": "Blocks",
  "h_blocks_cols": "block|title|status|files|critical|high|medium|low|fixed|open|deferred|rejected|duplicate|runs|turns|cost",
  "h_blocks_note": "Severity columns count defects (rejected findings and duplicates left out); status columns count every record, so they add up to the block's findings. Runs, turns and cost are the measured role runs in the journal; ≥ marks a sum that a run with an unreported number is part of.",
  "h_chart": "Findings by severity and status, per block",
  "h_chart_note": "Upper bar of each block: defects by severity; lower bar: every record by status. The same numbers are in the table above.",
  "h_sev": "severity",
  "h_stat": "status",
  "h_sev_names": "critical|high|medium|low",
  "h_status_names": "open|fixed|rejected|duplicate|deferred",
  "h_open": "Open findings",
  "h_open_cols": "finding|severity|where|claim|block report",
  "h_open_note": "The place is the line the finding's code sits on now (as in findings.md), not necessarily the line it was recorded at.",
  "h_open_none": "Nothing open.",
  "h_closed": "What closed each class",
  "h_closed_note": "A defect class (root) is closed by a guard — a test or a rule — recorded on the findings it holds.",
  "h_roots_cols": "defect class|findings|guard → findings it is recorded on",
  "h_no_guard": "no guard recorded",
  "h_no_root": "(no class named)",
  "h_closed_none": "No defect classes or guards recorded.",
  "h_fixes": "Fixes by commit ({n})",
  "h_risks": "Accepted risks",
  "h_risks_note": "Deferred findings stay in the code; each carries the reason it was accepted.",
  "h_risks_cols": "finding|severity|where|claim|reason",
  "h_risks_none": "Nothing deferred.",
  "h_rejected": "Rejected findings — do not find them again ({n})",
  "h_economy": "Economy",
  "h_economy_cols": "role|runs|of them unmeasured|turns|cost",
  "h_economy_chart": "Measured cost by role",
  "h_remains": "What is left",
  "h_r_open": "{n} open findings",
  "h_r_deferred": "{n} accepted risks stay in the code",
  "h_r_blocks": "blocks not closed: {ids}",
  "h_r_blocks_none": "every block is closed",
  "h_r_unowned": "{n} files belong to no block",
  "h_r_outside": "{n} files lie outside the declared scope and were not reviewed",
  "h_footer": "Written by `{cli} summary --html`: one self-contained file, no network, no scripts.",
  "sarif_deferred": "Accepted risk, deferred: ",
  "sarif_deferred_why": "Deferred because: {reason}",
  "sarif_report": "Block report: {path}",
  "sarif_rule_root": "Defect class of the review: {root}",
  "sarif_rule_block": "A finding of review block {block} ({title}) with no defect class named",
  "sarif_rule_guard": "What closes the class: {rules}",
  "sarif_rule_help": "Found by a whole-repository review with finetooth. Findings of this class: {ids}. The evidence and the failure scenario of each are in the block report named in the alert; the review state is in docs/review/.",
  "aged_head": "Drift since the base commit `{sha}` ({n} commits on the branch):",
  "aged_row": "  {block:<6} commits: {commits:<5} files: {files:<5} {title}",
  "aged_none": "nothing changed under the blocks' paths since the base — the summary still describes the tree",
  "scope_partial": "PARTIAL review — only the declared scope {paths} was reviewed, the rest of the repository was not (files in scope: {n} of {total}). Reason: {reason}",
  "sarif_rule_help_partial": "Found by a PARTIAL review with finetooth — only the scope {paths} was reviewed, the rest of the repository was not; reason: {reason}. Findings of this class: {ids}. The evidence and the failure scenario of each are in the block report named in the alert; the review state is in docs/review/.",
  "backfill_note": "Fingerprints stamped retroactively at commit {head}: blocks {blocks}; findings {n}. Changes before this commit are not tracked.",
  "seams_none": "(no two files of the block are linked by an import or by joint changes — every file here can be read on its own)",
  "seams_head": "Pairs of the block's files that depend on each other: {n} found by `seams`, the top {top} below (an import with the names it takes; joint changes from the history). A defect that lives only where two files are joined is invisible from either file alone — for each pair, find what one side assumes about the other and check that the other side holds it on every path.",
  "seams_co": "co-change {n}× ({a} / {b} of each file's changes)",
  "setup_note": "Static definition of the blocks. Progress lives in state.json, findings in findings.jsonl. Array order = execution order.",
  "excl_apparatus": "review apparatus, not its subject", "excl_skill": "the review skill — tooling, not the subject of review",
  "setup_skipped": "  · {rel} — already exists, left untouched",
  "setup_pycache": "\n⚠️ .gitignore has no __pycache__/ — add it, otherwise the tool's bytecode ends up in a commit",
  "deny_unreadable": "{rel} could not be read ({exc}) — its deny rules were not checked",
  "deny_not_list": "{rel}: permissions.deny is not a list — its rules were not checked",
  "deny_gate": "gate `{g}`", "deny_roles": "`{prefix}` (roles: {roles})",
  "deny_head": "\n⚠️ The project's own permission settings deny commands the review runs. A deny wins over the roles' pre-approvals, and a role that cannot run a gate falls back to reading:",
  "deny_hits": "      hits {what}",
  "deny_todo": "  What to do: {advice}.",
  "deny_advice": "name the form that works in docs/review/invariants.md and in the gates (for example `python3 -m pytest` where `pytest` is denied), or lift the rule for the review runs",
  "setup_next": """
Next — by hand, and this is not a formality:

1. docs/review/invariants.md — the rules of YOUR project. The most important file: it is
   pasted to every agent and decides what the agent will count as a defect. Example: {invariants}
2. docs/review/blocks.json — `gates` (the project's gate commands) and the blocks: cross-cutting
   first, domain ones next, live-system ones last. Example: {blocks}
3. The manifest of the first block — docs/review/blocks/<ID>-<slug>.md: 10–15 hypotheses about your
   project and the acceptance criterion. Example: {manifest}
   `{cli} seams <ID>` lists the pairs of the block's files linked by an import or by joint
   changes: for each of the top ones write a hypothesis on what one side assumes about the
   other — nobody else joins them, and the hunter gets the same list in its prompt.
4. `{cli} init`, then `{cli} coverage` — and deal with the unowned files until there are
   none left. This is where everything forgotten surfaces. Reviewing only a part on purpose
   (a trial run, a release gate, one risky area)? Declare `"scope": {{"paths": [...], "reason": "..."}}`
   in blocks.json instead of excluding the rest: coverage counts inside it, and every report says the review is partial.
5. `{cli} log <ID> "what was decided and why"` — from the first decision on: findings a
   re-run recovers, decisions it does not. What a useful line looks like: {journal}
6. The banner in the root instructions file ({banner_path}), otherwise a new session
   will not know a review is in progress and will start its own parallel one. Ready to paste:

{banner}""",
 },
 "ru": {
  "none": "(нет)",
  "refs_cut": "\n\n({n} файлов. Список сокращён до шаблонов — разверни нужную часть сам: `git ls-files -- <шаблон>`.)",
  "vol_head": "Файлов: {n}. Строк: {lines}. Порядок величины: ~{k}k токенов только на чтение, без рассуждений и вызовов инструментов.",
  "vol_fits": "Это укладывается в то, что читается за сеанс (порог {limit} строк).",
  "vol_sweep": "\n**Критерий приёмки обходит больше, чем блок:** ещё {n} файлов, {lines} строк (`sweep` в blocks.json). Не читай их по одному — к концу длинного списка внимание падает. Перечисли места механически: скрипт `docs/review/sweeps/{id}.<расширение>` (grep, разбор кода) печатает каждое место с путём и строкой; закоммить его и читай найденные места. Скрипт — доказательство, что список полон.",
  "vol_over": "\n⚠️ **Блок больше, чем прочитывается за сеанс** — {lines} строк при пороге {limit}. Прочитать всё внимательно не выйдет, и честный выход один: прочитать столько, сколько получится, и **поимённо назвать остальное** в разделе своего отчёта об ограничениях охвата. Не делайте вид, что прочитали. Прочитанным блок не примут, пока его не разрежут (`set-status` откажет), поэтому начните отчёт с того, что блок надо разрезать и по каким предметам.",
  "vol_over_verify": "\n⚠️ **Блок больше, чем прочитывается за сеанс** — {lines} строк при пороге {limit}. Прочитать всё внимательно не выйдет, и честный выход один: прочитать столько, сколько получится, и **поимённо назвать остальное** в разделе своего отчёта о состоянии охвата блока, открыв его словами «Охват неполный». Не делайте вид, что прочитали.",
  "vol_border": "\nГде проходит граница бюджета (по убыванию размера, накопительно):",
  "vol_more": "  … и ещё {n} файл(ов)",
  "vol_legend": "\n▲ — то, что за границей. Это не запрет их открывать: это то, что вы обязаны назвать непрочитанным, если не открыли.",
  "vol_lines": "строк",
  "gates_missing": "(в blocks.json не заполнено поле \"gates\" — впишите команды ворот проекта)",
  "commit_dco": "**Проект требует подпись DCO** — это сказано в {where}. Каждую правку коммить через `git commit -s` и под тем именем и почтой, которых ждёт проект: подпись обязана называть автора самого коммита, а глобальная идентичность git на этой машине — не она по умолчанию. Остальные правила коммитов (соглашение о сообщениях, язык) — в тех же файлах; прочитай их до первого коммита.",
  "commit_no_docs": "документах для участников (у проекта нет ни CONTRIBUTING, ни AGENTS.md)",
  "commit_none": "(правил коммитов проекта не найдено: требования подписи нет ни в {docs}, ни в `.github/` — до первого коммита сам посмотри CONTRIBUTING и джобы CI о коммитах)",
  "commit_dco_review": "**Проект требует подпись DCO** — это сказано в {where}. Проверь каждый коммит диапазона диффа: {gate} Коммит без `Signed-off-by` или подписанный не своим автором — находка: CI проекта его отвергает, и правка не войдёт, пока историю не перепишут.",
  "commit_gate_script": "прогони собственную проверку проекта, `{script} {range}`, и вклей её вывод в отчёт.",
  "commit_gate_log": "своего скрипта для этого у проекта нет, поэтому прочитай подписи: `git log --format='%h %an <%ae> %(trailers:key=Signed-off-by,valueonly,separator=%x2C )' {range}`.",
  "commit_none_review": "(правил коммитов проекта не найдено: требования подписи нет ни в {docs}, ни в `.github/` — если CONTRIBUTING или джоба CI всё же его ставит, сверь с ним коммиты диапазона)",
  "proof_live": "**У блока нет файлов: он работает на запущенной системе.** Что поднять, что прогнать и какой артефакт сдать — в манифесте ниже; без артефакта блок не закрыт. Код читай ровно настолько, чтобы поставить опыт и объяснить исход.",
  "proof_measured_verify": "**Блок доказывается артефактами, а не чтением** (`proof: measured`). Не перечитывай файлы за охотником: пересобери каждый артефакт манифеста той же командой и сверь построчно с тем, что он сдал. Расхождение — находка; артефакт, который не пересобирается, — блок не закрыт.",
  "proof_measured": "**Блок доказывается артефактами, а не чтением** (`proof: measured`). Список файлов ниже очерчивает область, а не задание на прочтение: какие артефакты сдать и как их получить — в манифесте, без них блок не закрыт. Читай то, что нужно для артефакта, и не отчитывайся о чтении, которого не было.",
  "proof_read_verify": "**Каждый файл из списка ниже кто-то обязан был прочитать целиком.** Если охотник признался, что часть не прочитал, — прочитай её сам; если он молчит о файле, это не значит, что файл прочитан.",
  "proof_read": "**Прочитай КАЖДЫЙ файл из списка ниже целиком.** Не выборочно, не «по ключевым». Список сгенерирован механически и является предметом твоей работы. Если файл слишком велик — читай его частями, но прочитай весь.",
  "files_live": "Файлы блока: нет — блок работает на запущенной системе",
  "files_measured": "Файлы блока ({n} шт.) — область блока; доказательство — артефакты манифеста",
  "files_read": "Файлы блока ({n} шт.) — прочитать все",
  "scope_line": " Твоя половина правок: **{scope}** — находки ты оформляешь по ней; то, что кроме неё есть в диффе ниже, читай для контекста.",
  "diff_vol": "Дифф ниже: {kb} КБ, {lines} строк. Порядок величины: ~{k}k токенов только на чтение, до рассуждений и вызовов инструментов. Если это не помещается в то, что ты держишь за раз, — не читай половину, отчитываясь за целое: скажи об этом в отчёте, и ведущая сессия разделит ДИАПАЗОН — `--diff <первая часть>` тебе и `--diff <вторая>` второму ревьюеру; уменьшает дифф именно это. `--scope <половина>` его не уменьшает: он называет твою половину в отчёте и в его имени.",
  "no_open_findings": "(открытых находок по блоку нет — уточни у ведущей сессии, зачем запущен фиксер)",
  "fix_batch": "**Этот прогон берёт {cap} из {n} открытых находок: {ids}.** Это первые {cap} по серьёзности в списке ниже. Закрой их — каждую коммитом, как только она закрыта, — и остановись: остальные оставь `open`, их возьмёт следующий прогон исполнителя. Предел измерен, а не придуман: в полевом прогоне 16 из 46 прогонов исполнителя упёрлись в предел ходов на пачках крупнее 3–4 находок, оставив работу незакоммиченной.",
  "rec_none": "(за блоком пока ничего не записано)",
  "rec_row": "- **{id}** · {severity} · {status} · `{where}` — {claim} _(записана {date})_",
  "dec_none": "(решений человека по блоку не записано — работай по правилам выше)",
  "loop_stop": "сигнал петли: главная находка лежит в коде, который написал прошлый круг, — решает человек. {id} ({sev}, {file}:{line}) из ревью правок круга {prev} стоит на строке, которую изменил круг починки {prev} ({diff}); ещё один круг повторит тот же узор. Запишите решение — другой механизм, откат класса или закрытие блока — командой `{cli} decide {block} \"<decision>\"`: оно попадёт в задания следующего круга починки и ревью правок. Если решено закрыть блок: `{cli} set-status {block} closed`.",
  "dec_row": "- **{date}**, после ревью правок круга {round}: {text}",
  "draft_unimported": "{block}: в черновике {draft} есть строки, которых нет в реестре (неимпортированных строк: {n}) — находки, записанные проверкой блока, в ревью не попали: их не видят `summary`, `findings.md`, `sarif` и ворота починки. Внесите их: `{cli} import {block}`, если по блоку ещё ничего не записано, `{cli} import {block} --append` — поверх записанного; затем `{cli} findings`.",
  "confirmed_no_finding": "{block}: {report} подтверждает гипотезу {h}, но не называет ни одной находки. Выход зависит от того, что значит вердикт. Дефект есть: подтверждённая гипотеза есть дефект, а дефект, не оформленный находкой, не попадает ни в реестр, ни в ворота починки, — оформите его в черновике {draft} и поставьте номер на строку вердикта: `{h} — подтверждена: {block}-NNN — <чем доказано>`. Дефекта нет, а слово стоит только в доказательстве («гард на месте — подтверждена тестом»): перепишите вердикт как `{h} — опровергнута: <почему это не дефект>`, без слова «подтверждена» ни в строке, ни в доказательстве под ней — ворота читают и то и другое. Строка — образец шаблона, скопированный как есть (`{block}-NNN`, `<чем именно доказано>`): она ни на что не отвечает — проверьте гипотезу и запишите вердикт, к которому пришли.",
  "confirmed_unknown_finding": "{block}: {report} подтверждает гипотезу {h} находкой {ids}, которой нет ни в черновике {draft}, ни в реестре — назовите номер, который у находки есть (или будет при импорте: по порядку черновика от первого нового номера из промпта), либо оформите находку в черновике. Если подтверждённое — не дефект, вердикт `{h} — опровергнута: <почему это не дефект>`.",
  "draft_unreadable": "{block}: черновик {draft} не читается, и его находок нет в реестре — {why}. Исправьте строку, затем `{cli} import {block}` (или `--append` поверх записанного).",
  "f_where": "**Место:**", "f_claim": "**Что не так:**", "f_scenario": "**Сценарий отказа:**", "f_invariant": "**Нарушенный инвариант:**", "f_conf": "уверенность",
  "md_title": "# Находки ревью", "md_gen": "> Файл СГЕНЕРИРОВАН из `findings.jsonl` командой `{cli} findings`.", "md_noedit": "> Не редактируй его руками — правь jsonl и перегенерируй.",
  "md_open": "Открыто: **{live}** из {total} записей.", "md_sev": "## {sev} ({open} открыто / {total})", "md_cols": "| id | блок | статус | место | что не так |",
  "journal_head": "# Дневник ревью\n\n",
  "sum_title": "# {project} — итог ревью",
  "sum_intro": "Этот файл переживает снос `docs/review/`: он описывает прошлое и не держит статусов, которые могут протухнуть. Коммит-база — ревизия, относительно которой всё ниже читалось. Насколько каждый блок уехал с тех пор: `{cli} summary --aged <этот файл>`.",
  "sum_base": "**Дата:** {date}  \n**Коммит-база:** `{sha}` ({branch})  \n**Блоки:** закрыто {closed} из {total}; **находки:** {total_f} — починено {fixed}, отвергнуто {rejected}, отложено {deferred}, дублей {dups}, ещё открыто {open}",
  "sum_blocks": "## Блоки и что считалось проверенным",
  "sum_blocks_head": "| блок | название | статус | закрыт | файлов | отпечаток | критерий приёмки |",
  "sum_rejected": "## Отвергнутые находки — не искать заново",
  "sum_rejected_none": "Отвергнутых находок нет.",
  "sum_deferred": "## Принятые риски (отложено с причиной)",
  "sum_deferred_none": "Отложенного нет.",
  "sum_classes": "## Чем закрыт каждый класс",
  "sum_classes_rules": "Узды (тест или правило — и находки, на которые она записана):",
  "sum_classes_fixes": "Починки по коммитам:",
  "sum_classes_none": "Узды не записаны; починки, если есть, перечислены выше по коммитам.",
  "sum_open": "## Ещё открыто на момент итога",
  "sum_open_none": "Открытого нет.",
  "sum_seams": "## Стыки между блоками (из `coupling`)",
  "sum_machine": "## Для инструмента — не править",
  "sum_coverage": "**Файлы:** в блоках {covered} из {total}, без блока {unowned}, исключено из ревью {excluded}",
  "sum_economy": "## Экономика (замеренные прогоны ролей из журнала)",
  "sum_economy_head": "| роль | прогонов | из них без замера | ходов | цена |",
  "sum_at_least": "≥ {v}",
  "sum_not_known": "неизвестно",
  "sum_economy_total": "всего",
  "sum_economy_unknown": "Прогонов, чьи ходы или цену поток не сообщил: {n}. Они посчитаны как прогоны и никогда как ноль: сумма, в которую они входят, — нижняя граница (≥), а «неизвестно» — когда ни один прогон в ней числа не сообщил.",
  "sum_economy_none": "Замеренных прогонов ролей в журнале нет (их пишет `assets/run-role.sh`).",
  "h_title": "{project} — итог ревью",
  "h_meta": "Дата {date} · коммит-база {sha} ({branch}) · finetooth {version}",
  "h_intro": "Что проверяли, что нашли, что починили, сколько стоило и что осталось — по реестру и журналу ревью на коммите-базе. Итог в Markdown (`{cli} summary`) несёт те же числа.",
  "h_goal": "Цель и охват",
  "h_t_blocks": "блоков закрыто",
  "h_t_findings": "находок записано",
  "h_t_fixed": "починено",
  "h_t_open": "ещё открыто",
  "h_t_deferred": "принятых рисков",
  "h_t_files": "файлов в блоках",
  "h_t_cost": "замеренная цена",
  "h_of": "{a} из {b}",
  "h_coverage": "В блоках {covered} из {total} файлов; без блока {unowned}; исключено из ревью с названной причиной {excluded}.",
  "h_goals": "Что проверял каждый блок:",
  "h_blocks": "Блоки",
  "h_blocks_cols": "блок|название|статус|файлов|критич.|высокая|средняя|низкая|починено|открыто|отложено|отвергнуто|дублей|прогонов|ходов|цена",
  "h_blocks_note": "Столбцы серьёзности считают дефекты (отвергнутые находки и дубли не входят); столбцы статусов — все записи, и в сумме дают число находок блока. Прогоны, ходы и цена — замеренные прогоны ролей из журнала; ≥ — сумма, в которую вошёл прогон с несообщённым числом.",
  "h_chart": "Находки по серьёзности и статусу, по блокам",
  "h_chart_note": "Верхняя полоса блока — дефекты по серьёзности, нижняя — все записи по статусу. Те же числа — в таблице выше.",
  "h_sev": "серьёзность",
  "h_stat": "статус",
  "h_sev_names": "критическая|высокая|средняя|низкая",
  "h_status_names": "открыта|починена|отвергнута|дубль|отложена",
  "h_open": "Открытые находки",
  "h_open_cols": "находка|серьёзность|место|суть|отчёт блока",
  "h_open_note": "Место — строка, на которой код находки стоит сейчас (как в findings.md), не обязательно та, на которой её записали.",
  "h_open_none": "Открытого нет.",
  "h_closed": "Чем закрыт каждый класс",
  "h_closed_note": "Класс дефекта (корень) закрывает узда — тест или правило, записанная на те находки, которые она держит.",
  "h_roots_cols": "класс дефекта|находки|узда → находки, на которые она записана",
  "h_no_guard": "узда не записана",
  "h_no_root": "(класс не назван)",
  "h_closed_none": "Ни классов дефектов, ни узд не записано.",
  "h_fixes": "Починки по коммитам ({n})",
  "h_risks": "Принятые риски",
  "h_risks_note": "Отложенные находки остаются в коде; у каждой — причина, по которой риск принят.",
  "h_risks_cols": "находка|серьёзность|место|суть|причина",
  "h_risks_none": "Отложенного нет.",
  "h_rejected": "Отвергнутые находки — не искать заново ({n})",
  "h_economy": "Экономика",
  "h_economy_cols": "роль|прогонов|из них без замера|ходов|цена",
  "h_economy_chart": "Замеренная цена по ролям",
  "h_remains": "Что осталось",
  "h_r_open": "открытых находок: {n}",
  "h_r_deferred": "принятых рисков, оставшихся в коде: {n}",
  "h_r_blocks": "не закрыты блоки: {ids}",
  "h_r_blocks_none": "все блоки закрыты",
  "h_r_unowned": "файлов без блока: {n}",
  "h_r_outside": "файлов вне объявленной области, не просмотренных: {n}",
  "h_footer": "Собрано `{cli} summary --html`: один самодостаточный файл, без сети и без скриптов.",
  "sarif_deferred": "Принятый риск, отложено: ",
  "sarif_deferred_why": "Отложено, потому что: {reason}",
  "sarif_report": "Отчёт блока: {path}",
  "sarif_rule_root": "Класс дефекта ревью: {root}",
  "sarif_rule_block": "Находка блока ревью {block} ({title}) без названного класса дефекта",
  "sarif_rule_guard": "Что закрывает класс: {rules}",
  "sarif_rule_help": "Найдено сплошным ревью репозитория с finetooth. Находки этого класса: {ids}. Доказательство и сценарий отказа каждой — в отчёте блока, названном в предупреждении; состояние ревью — в docs/review/.",
  "aged_head": "Дрейф от коммита-базы `{sha}` ({n} коммитов на ветке):",
  "aged_row": "  {block:<6} коммитов: {commits:<5} файлов: {files:<5} {title}",
  "aged_none": "под путями блоков ничего не менялось с базы — итог по-прежнему описывает дерево",
  "scope_partial": "ЧАСТИЧНОЕ ревью — просмотрена только объявленная область {paths}, остальной репозиторий не просматривался (файлов в области: {n} из {total}). Причина: {reason}",
  "sarif_rule_help_partial": "Найдено ЧАСТИЧНЫМ ревью с finetooth — просмотрена только область {paths}, остальной репозиторий не просматривался; причина: {reason}. Находки этого класса: {ids}. Доказательство и сценарий отказа каждой — в отчёте блока, названном в предупреждении; состояние ревью — в docs/review/.",
  "backfill_note": "Отпечатки проставлены задним числом на коммите {head}: блоки {blocks}; находок {n}. Изменения до этого коммита не отслежены.",
  "seams_none": "(ни одна пара файлов блока не связана ни импортом, ни совместными правками — каждый файл здесь читается сам по себе)",
  "seams_head": "Пары файлов блока, которые зависят друг от друга: `seams` нашёл {n}, ниже верхние {top} (импорт — с именами, которые он берёт; совместные правки — из истории). Дефект, живущий только на стыке двух файлов, не виден ни из одного из них по отдельности — на каждой паре найди, что одна сторона предполагает о другой, и проверь, что другая держит это на всех путях.",
  "seams_co": "совместных правок {n}× ({a} / {b} правок каждого файла)",
  "setup_note": "Статическое определение блоков. Прогресс живёт в state.json, находки — в findings.jsonl. Порядок массива = порядок исполнения.",
  "excl_apparatus": "аппарат ревью, а не его предмет", "excl_skill": "скилл ревью — оснастка, а не предмет ревью",
  "setup_skipped": "  · {rel} — уже есть, не тронут",
  "setup_pycache": "\n⚠️ В .gitignore нет __pycache__/ — добавьте, иначе байткод инструмента уедет в коммит",
  "deny_unreadable": "{rel} не читается ({exc}) — его запреты не проверены",
  "deny_not_list": "{rel}: permissions.deny — не список, его правила не проверены",
  "deny_gate": "ворота `{g}`", "deny_roles": "`{prefix}` (роли: {roles})",
  "deny_head": "\n⚠️ Настройки разрешений самого проекта запрещают команды, которые запускает ревью. Запрет сильнее заранее одобренного ролям, и роль, которой не дали запустить ворота, откатывается к чтению:",
  "deny_hits": "      задевает {what}",
  "deny_todo": "  Что делать: {advice}.",
  "deny_advice": "назовите работающую форму в docs/review/invariants.md и в воротах (например, `python3 -m pytest` там, где запрещён `pytest`) или снимите правило на время прогонов ревью",
  "setup_next": """
Дальше — руками, и это не формальность:

1. docs/review/invariants.md — правила ВАШЕГО проекта. Самый важный файл: он вставляется
   каждому агенту и решает, что агент сочтёт дефектом. Образец: {invariants}
2. docs/review/blocks.json — `gates` (команды ворот проекта) и блоки: сначала сквозные,
   потом предметные, последними — на живой системе. Образец: {blocks}
3. Манифест первого блока — docs/review/blocks/<ID>-<slug>.md: 10–15 гипотез о вашем
   проекте и критерий приёмки. Образец: {manifest}
   `{cli} seams <ID>` перечисляет пары файлов блока, связанные импортом или совместными
   правками: на каждую из верхних напишите гипотезу о том, что одна сторона предполагает о
   другой, — больше их никто не сводит, и охотник получает тот же список в промпте.
4. `{cli} init`, затем `{cli} coverage` — и разбирайте ничьи файлы, пока их не останется.
   Здесь всплывает всё забытое. Смотрите намеренно только часть (пробный прогон, ворота
   выпуска, одна рискованная область)? Объявите `"scope": {{"paths": [...], "reason": "..."}}`
   в blocks.json вместо исключения остального: покрытие считается внутри, и каждый отчёт говорит, что ревью частичное.
5. `{cli} log <ID> "что решили и почему"` — с первого же решения: находки повторный прогон
   восстановит, решения — нет. Как выглядит полезная строка: {journal}
6. Баннер в корневой файл инструкций ({banner_path}), иначе новая сессия не узнает, что
   идёт ревью, и начнёт своё параллельное. Готов к вставке:

{banner}""",
 },
}


def review_lang() -> str:
    """The project's review language — the `lang` field in blocks.json; English by default."""
    try:
        lang = json.loads(BLOCKS_FILE.read_text(encoding="utf-8")).get("lang", "en")
    except (OSError, ValueError, AttributeError):
        lang = "en"
    return lang if lang in LANGS else "en"


def T(key: str, **kw) -> str:
    return MSG[review_lang()][key].format(**kw)


def names(key: str) -> list[str]:
    return MSG[review_lang()][key].split("|")
