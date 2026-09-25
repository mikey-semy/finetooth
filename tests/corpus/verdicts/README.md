# Verdict corpus (issue #17)

Today's behaviour of `verdict_mentions`, frozen, so that the parser's redesign moves every
answer on purpose and says why.

| file | what |
|---|---|
| `finetooth/` | the kit's own review, block T1: every report, verbatim |
| `expected.json` | what `verdict_mentions` returned on each report when the corpus was taken |
| `index.json` | the block and the kind of each report |
| `template-forms.md` | every verdict form the four role templates prescribe, in both languages, with today's answer and the meaning the template intends |

**The corpus freezes, it does not bless.** Some of today's answers are wrong — a verdict with
"partially" read as checked, a verdict quoted in a code span counted, the template's
unfilled `<…>` counted. They are the redesign's first cases; changing them means editing
`expected.json` line by line with the reason.

**External registers.** The corpus was also taken on two external projects' live registers
(14 started blocks, 46 reports). Their verdict lines carry those projects' own text, so they
are not published. The maintainer keeps them privately in the same layout; with
`FINETOOTH_PRIVATE_CORPUS=<dir>` the test checks them alongside.
