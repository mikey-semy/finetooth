[Русская версия](ru/token-economy.md)

# Where the tokens go and what to do about it

An analysis of 24.09.2026 at the owner's request: "look into optimising token hunger — extra
passes, algorithms". Our numbers are from [`measurements.md`](measurements.md); others' are
by the links, and where a number comes from a retelling, this is marked.

## 1. What our measurements say

| block | volume | tokens | time |
|---|---|---|---|
| access and visibility | 58 files, 4017 lines | 576 thousand | ~35 min |
| domain core | 13 files | 446 thousand | ~34 min |
| writes and versions | 42 files | 679 thousand | ~48 min |
| money and quotas | 10 files, 782 lines | 557 thousand | ~35 min |

**The cost of a block almost does not depend on its size.** A block of 782 lines cost the same
as a block of 4017. So the tokens do not go on reading the block's files: 4000 lines is on the
order of 50–60 thousand tokens, a tenth of the cost.

**The static prompt prefix is not where the money lies.** The role rules, the invariants
(~9 KB ≈ 3 thousand tokens), the manifest and the file list are units of thousands of tokens out
of 400–700 thousand.

One thing remains: **tool results** — the output of tests and runs, `grep`, repeated reads of the
same files, reading context beyond the block. This agrees with others' analyses: in Anthropic's
research agent 96% of the context was taken by file-read results, 1.7% — by reasoning
([cookbook](https://platform.claude.com/cookbook/tool-use-context-engineering-context-engineering-tools));
on SWE-bench trajectories the model spends 76% of its budget on read operations
([SWE-Pruner, arXiv 2601.16746](https://arxiv.org/abs/2601.16746)).

**What we do not know.** For no role is any of this logged: the share of cache reads, the number
of tool calls, repeated reads, the size of `Bash` output. So everything below is hypotheses, and
the first of them is a measurement.

## 2. What others do

| Technique | What it saves | Estimate | Applicable to us |
|---|---|---|---|
| **Prompt cache** (Anthropic) | re-processing the prefix | reads at 0.1× the price, writes at 1.25× (5 min) / 2× (1 h); the TTL is reset by every hit ([docs](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)) | partially: in Claude Code it is on by itself. The risk is not the absence of a cache but **misses**: subagents have a 5-min TTL, and a test longer than five minutes rewrites the whole context at 1.25× ([Claude Code](https://code.claude.com/docs/en/prompt-caching)) |
| **"One file — one read"** (CORVUS) | repeated reads | −9…50% input tokens with the same result ([arXiv 2607.22711](https://arxiv.org/abs/2607.22711)) | **yes**: the hunter's prompt requires reading everything, but does not forbid re-reading |
| **Notes on disk instead of re-reading** | reads in a second session | −50% reads, −48% peak context (cookbook) | partially: the hunter's notes can feed the fixer; the verifier must not get them — it reads independently |
| **Filtering tool output with a hook** | test and log output | "tens of thousands → hundreds of tokens" ([costs](https://code.claude.com/docs/en/costs)) | **yes**: the verifier and the fixer run the gates |
| **Context compaction, clearing results** | peak context | −50% peak, but small details are lost 3 of 3 (cookbook) | **no** for the hunter: a finding lives in the small details |
| **Repository map** (aider: signatures + PageRank) | reading context files | signatures instead of full files ([aider](https://aider.chat/docs/repomap.html)) | partially: for `ref_paths`, not for the block's files |
| **Review only what changed** | repeated passes | CodeRabbit by default looks only at new commits | **yes** for top-up import and fix review; no for the first pass |
| **Cheap model on sub-roles** | token price | on diff review Haiku is no worse than Sonnet at 3.2× cheaper — but F1 0.37 and all on diffs ([arXiv 2606.15689](https://arxiv.org/abs/2606.15689)); Claude Code moved the search subagent from Haiku to the session model for quality | only with a measurement, and not on the hunter |
| **Several hunters** | — | with us the second hunter gave +4 findings for 222 thousand versus +3 and a resolved contradiction from the verifier for 131 thousand | no |

**Multi-agent setups are expensive by design.** Anthropic: an agent spends about 4 times more
tokens than a chat, a multi-agent system — 15 times
([multi-agent research](https://www.anthropic.com/engineering/multi-agent-research-system));
agent teams in Claude Code — about 7× a normal session. Our pair "hunter + verifier" costs 2× a
single hunter and gives +31% findings with zero planted findings let through — by our own
numbers this pays off.

## 3. Hypotheses, by expected saving

A common log for all: the metric `claude_code.token.usage` (type: input/output/cache read/cache
write, agent name, model) and the event `claude_code.tool_result` (tool, duration) —
[monitoring](https://code.claude.com/docs/en/monitoring-usage); from the transcript — the number
of `Read` calls per unique path (repeats = re-reads) and the size of each `Bash` result.

1. **Baseline measurement before any changes.** One block as is, the spend broken down: share of
   cache reads versus writes, share of `Bash` output, share of repeated reads. Saving — zero, but it
   sets the order of everything else.
2. **Cache misses by TTL** — the cheapest possible fix. A block runs 35–50 minutes, and the
   subagent TTL is 5 minutes: every long test run rewrites the context. Check `cache_creation`
   before and after enabling the one-hour TTL for subagents.
3. **Filtering gate output with a hook** for the verifier and the fixer: only what failed and the
   tail. Measure the sum of bytes of `Bash` results; control — the same verdicts on findings.
4. **"One file — one read" plus notes on disk** in the hunter's prompt. Expectation by CORVUS
   9–50% of input. Measure re-reads per unique file; control — findings matching the previous run
   of the same block.
5. **A delta pass by `git diff`** for top-up import and fix review. Right now a repeated pass reads
   the whole block. Measure the share of findings in unchanged files: if it is noticeable, the delta
   cuts completeness.
6. **Signatures instead of full `ref_paths`.** Measure the number of `Read` calls on context paths;
   control — findings of cross-cutting blocks in others' code, those must not be lost.
7. **A cheap model on the fixer and the fix reviewer**, not on the hunter. The only local
   comparison (a Sonnet verifier: rejected all the planted ones, but also rejected more of the real
   ones) is neither for nor against. Measure on three blocks: cost, share of fixes returned from
   review, share of tests green on the old code.
8. **A verifier without its own pass on "low" blocks.** It adds 31% of findings, but most of the
   top-up is low and medium. Where the hunter gave neither critical nor high, limit the verifier to
   verdicts. Works only if in such blocks its top-up is low alone.

## 4. What not to do — there is evidence of quality loss

- **Do not replace execution with reading at the verifier.** Planted findings failed to get
  through only under verification by execution (our measurement).
- **Do not remove the verifier.** +31% findings, resolution of contradictions between hunters —
  our numbers.
- **Do not move the hunter to a cheap model on the strength of benchmarks.** The same works that
  praise cheap models on diffs show F1 falling from 0.85 to 0.07 on real changes and a 15-fold drop
  as the diff grows. Our block is not a small diff.
- **Do not compact the hunter's context in the middle of a block.** Compaction keeps the large
  facts and loses the small ones — and a finding lives in a line number and an `if` branch.
- **Do not multiply hunters for the sake of "consensus".** Self-consistent errors do not go away as
  the sample grows ([arXiv 2505.17656](https://arxiv.org/pdf/2505.17656)).
- **Do not cut blocks smaller to save.** The cost does not depend on volume → more blocks = more
  expensive. Cutting for quality is possible, but that is another hypothesis.
- **Do not change the model or the tool set in the middle of a session** — each such action
  resets the cache entirely.

⚠️ Not verified against a primary source: the claim "a tool definition = 735 tokens per request"
and the Augment Code analysis "where the tokens go" (the pages did not open).
