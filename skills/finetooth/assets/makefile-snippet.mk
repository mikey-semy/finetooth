# `make` targets for the review. Pasted into the project's Makefile as is.
#
# The point of the targets is not to save keystrokes but to remove choice: the
# path to the tool and the argument names are written here once, and the prompt
# cannot be assembled "slightly wrong". If the project has no Makefile, the same
# list lives in package.json, a justfile or anything else — see
# package-json-snippet.json next to this file.
#
# ⚠️ In the kit as it was handed over, this file's place was taken by a fragment
# of another project's SAST targets, and not one of the `make review-*` commands
# promised in the documentation existed. Hence the rule: commands written in an
# instruction are run at the very first install, otherwise the instruction
# describes an intention, not work.
#
# ⚠️ Do NOT put `make review` in the `cli` field of blocks.json. Every hint and
# refusal the tool prints is assembled from that field — `<cli> coverage`,
# `<cli> prompt H1 --role verify`, `<cli> set-finding H1-003 rejected --reason …`
# — and `make` reads `--role` and `--reason` as its own options and stops. These
# targets cover the everyday commands; for the rest, leave `cli` unset and the
# tool prints the real path to itself. A project that wants one command for
# everything writes a shell wrapper and names that.

REVIEW := python3 .claude/skills/finetooth/scripts/review.py

.PHONY: review-init review-status review-next review-coverage review-check \
        review-prompt review-import review-findings

review-init: ## Create state.json from blocks.json
	@$(REVIEW) init

review-status: ## Where we are: blocks by phase, findings, next block
	@$(REVIEW) status

review-next: ## id of the next unclosed block
	@$(REVIEW) next

review-coverage: ## Rebuild the file → block map; fails if a file is unowned
	@$(REVIEW) coverage

review-check: ## The state is consistent: statuses, reports, findings, coverage
	@$(REVIEW) check

review-findings: ## Regenerate findings.md from findings.jsonl
	@$(REVIEW) findings

# The default role is the hunter: every block starts with it.
# make review-prompt BLOCK=H1 ROLE=verify
review-prompt: ## Assemble a prompt for an agent: BLOCK=H1 [ROLE=hunter|verify|fix]
	@test -n "$(BLOCK)" || { echo "name the block: make review-prompt BLOCK=H1"; exit 2; }
	@$(REVIEW) prompt $(BLOCK) --role $(or $(ROLE),hunter)

review-import: ## Pull the block's findings into the register: BLOCK=H1
	@test -n "$(BLOCK)" || { echo "name the block: make review-import BLOCK=H1"; exit 2; }
	@$(REVIEW) import $(BLOCK)
	@$(REVIEW) findings
	@$(REVIEW) check
