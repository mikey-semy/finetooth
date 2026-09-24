[Русская версия](ru/measurements.md)

# Measurements

Everything known about this method from facts rather than reasoning. Also here: the
methodology and the boundaries beyond which a number must not be carried.

## 0. What the method has been run on

Three projects, all TypeScript, all owned by one person — an important boundary, see the
caveat at the end of the section. Names are not disclosed: the projects are private, and their
names add nothing to the method.

| project | files | blocks | done | findings | fixed | rejected | duplicates |
|---|---:|---:|---:|---:|---:|---:|---:|
| A | 467 | 27 | **27** | 313 | 81.8% | 2.6% | 1.6% |
| B | 252 | 13 | 8 | 210 | 77.1% | 3.8% | 2.4% |
| C | 1803 | 67 | 4 | 64 | — | ~3% | 6% |

**The first review has been carried to the end:** in project A all 27 blocks are done, 256
findings fixed, 44 deferred with a decision, 8 rejected with a reason.

**The share of rejected findings is stable across three independent projects — about 3%.**
This is the same result the planted-findings measurement gave (section 2), but obtained a
different way and on a sample an order of magnitude larger: 587 findings against 12. A hunter
obliged to present a failure scenario brings little junk — and that is a property of the
method, not the luck of a single run.

**Finding density:** 0.67 and 0.83 findings per file under review. A block averages 17–27 files.

**Distribution by severity** (project B, where it is fully labelled): 3 critical, 30 high,
69 medium, 108 low. Two thirds of findings are not urgent; the method pays for itself not
through critical holes but by showing the whole picture at once.

⚠️ **What these numbers do not prove.** All three projects are TypeScript, all written by one
person, and part of the code in them was written by the same AI that later reviewed it.
Transferability *between projects* is confirmed; transferability *to another language, another
team and someone else's code* — is not.

To future sessions: **extend the tables, do not rewrite them**. A measurement without a
methodology and without caveats is not a measurement.

## 1. What a block costs

Measured on project C (September 2026).

| block | size | findings | agents | tokens | time |
|---|---|---:|---:|---:|---:|
| access and visibility | 58 files, 4017 lines | 12 | 2 | 576k | ~35 min |
| domain core | 13 files | 14 | 2 | 446k | ~34 min |
| writes and versions | 42 files | 17 | 2 | 679k | ~48 min |
| money and quotas | 10 files, 782 lines | 18 | 3 | 557k¹ | ~35 min |

¹ Counted in the two-scheme measurement mode: two hunters (204k + 222k) and a verifier (131k).
A normal pass over the same block — hunter plus verifier — is about 335k.

**What follows from this.** A block costs 400–700 thousand tokens and 35–50 minutes, and the
price depends weakly on the number of files: a 13-file block cost more than a 58-file one,
because checking it required execution. Plan by the number of blocks, not by the volume of
code.

⚠️ Transfer to other projects is unverified: all four blocks are one project, one language, one
model (Opus) in both roles.

## 2. The verifier against planted findings

**Question.** Our share of rejected findings was 6% (2 findings out of 34). Is that the
hunter's precision or the verifier's compliance?

**Method.** Six real findings from a block were mixed with six invented ones, each written so
that execution would refute it (a rule that supposedly is missing; a schema case that
supposedly is not handled; a host boundary that supposedly is checked by substring). The order
was shuffled, the origin was not disclosed to the verifier. The set was run twice — by two
models independently.

| | Opus | Sonnet |
|---|---|---|
| planted rejected | 6 of 6 | 6 of 6 |
| real confirmed | 4 | 3 |
| real rejected | 2 | 3 |

**Conclusion.** Not one lie got through. The six percent rejection rate is explained by the
hunter's precision, not by the verifier's compliance — **provided the check is done by
execution**.

**A caveat that matters more than the conclusion.** The two rejected real findings turned out
to be already fixed — the register did not know that. And the single disagreement between the
models was not resolved in favour of the one that "found the defect": both were wrong, because
the working copy of the neighbouring repository was 12 days behind. The verifier faithfully
executed everything it promised — on yesterday's code.

## 3. Two schemes at equal budget

**Question.** The "hunter + verifier" pair costs twice a single pass. Does it beat the cheapest
rival — two independent passes with the findings merged?

**Method.** One block run twice: hunter A on the normal prompt, hunter B on the same prompt but
with the reading order reversed (a cheap analogue of "shuffling", removing the position
effect). Both blind. The verifier received the union of 18 findings shuffled, not knowing who
found what, with the task of looking for duplicates and contradictions.

| | findings | tokens |
|---|---:|---:|
| hunter A | 10 | 204k |
| hunter B | 8 | 222k |
| verifier over 18 | +3 of its own | 131k |

**Verdicts: 17 confirmed, 1 plausible, 0 rejected.**

**Results.**
- The second hunter brought **4 new findings**; the other 4 turned out to be duplicates of the
  first by root (four pairs matched, including the very same line in both).
- The verifier, for **half the money**, checked all 18, found 3 of its own, corrected details
  in three and merged the duplicates.
- And it did what a pair of hunters cannot: **resolved a direct contradiction** between them
  (one claimed the circuit breaker works only for one provider, the other that it hits all of
  them; the fork ran along the presence of a key).

**Conclusion.** The value of the second role is not a filter but deepening. Zero rejected out
of 18 means there was nothing to filter.

## 4. The verifier's gain over three blocks

| | findings |
|---|---:|
| brought by hunters | 32 |
| added by verifiers | +10 (31%) |
| rejected by verifiers | 2 (6%) |

Plus what cannot be counted: on one block the verifier independently rebuilt the route table
and found **7 missed out of 38**; on another it ran 8 mutations and showed that the test suite
guarded none of the findings.

## 5. How much the main pass catches — a first estimate of misses

**Question.** The main thing we did not know about the method: what share of defects it misses.
It cannot be measured directly — the denominator is unavailable. But two completed reviews
have data sufficient for a **lower-bound estimate**: the register records who found each
finding, and some of them surfaced AFTER the block was closed — during fixing, during diff
review, during a repeat pass.

**Method.** Findings are split by origin: the main pass (hunter and verifier) against
everything found later in the same code. The share of the latter is the lower bound of the
main pass's misses: these are defects it could have found and did not.

| | project A | project B |
|---|---:|---:|
| findings total | 313 | 210 |
| **main pass** | **62%** | **77%** |
| repeat pass (top-up) | 13% | — |
| found by the fixer while fixing | 12% | 5% |
| found during diff review | 12% | 11% |
| external auto-review | — | 7% |

The spread is explained by project A having a separate repeat-pass phase, which project B did
not. Without it the shares converge: **71% and 77%**.

**The main thing is not the share but its composition.**

| severity | project A | project B |
|---|---|---|
| major findings caught by the main pass | 86% (44 of 51) | 88% (29 of 33) |
| what surfaces later | mostly low and medium | same |

**Conclusion.** The main pass finds about three quarters of what will eventually be found, and
**almost nine out of ten major findings**. The misses are skewed towards small stuff — exactly
the behaviour one wants from the method: the expensive gets caught at once, the cheap gets
picked up later, during fixing and diff review.

⚠️ **What this number does not say.** It is a lower bound: the denominator is "everything found
in the end", not "everything there is". Defects found by no one are not in it, and how many
there are is still unknown. The full measurement is in [`../ROADMAP.md`](../ROADMAP.md),
direction 1; here what is measured is what can be seen from the data of two completed reviews.

## 6. What we did not measure

- **How much the method misses FOR GOOD.** Section 5 gives a lower bound over two completed
  reviews; defects found by no one are excluded from it by construction. The procedure for a
  full measurement is in [`../ROADMAP.md`](../ROADMAP.md), direction 1.
- **The cost of fixing.** All numbers above are about searching. The "fixed → diff read" rounds
  cost the kit's author six times more than the survey pass, but that is his measurement, not
  ours.
- **Behaviour in another language and in someone else's project.**
- **Different models in different roles.** The only attempt (Sonnet as verifier) produced a
  disagreement in one case out of twelve, and not in its favour — but not against it either:
  it turned out to be right in the end, though the argument it gave was wrong.

## For comparison: other people's numbers

Not our measurements but reference points from publications — to understand the scale
(analysis and sources in [`comparison-with-practice.md`](comparison-with-practice.md)).

| what | value |
|---|---|
| precision of an AI reviewer on real PRs | 3.56% |
| false discovery rate of an LLM detector on real CVEs | 84.82% |
| best tool on an independent set | no more than 63% of known problems |
| all review agents together | ~40% of tasks |
| same model: dirty dataset vs clean | F1 68% → 3% |
| synthetic mutations vs real bug fixes | F1 0.847 → 0.066 |
| Google in production | target precision 50%, success = 7.5% of comments closed by an edit |
| audit by humans | 6–9 engineer-weeks per repository |

The last row is the reason the method makes sense at all: what costs person-weeks costs an
hour here. At a precision below human.
