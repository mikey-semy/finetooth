# Template verdict forms

Every verdict form the four role templates (`skills/finetooth/references/`) prescribe, in
both languages, as literal report lines. `tests/test_verdict_corpus.py` feeds each snippet to
`verdict_mentions(snippet, "T1")` with `{{BLOCK_ID}}` replaced by `T1` and compares with
`expect`. **`expect` is what today's parser returns**, frozen; `intent` is what the template
says the form means. Where the two differ, the entry says so — those are cases for the
redesign (issue #17), not for this file.

The fix and fix-review templates prescribe no hypothesis verdict at all: their forms are
verdicts on findings, listed so that a parser change cannot start reading them as
hypothesis verdicts unnoticed.

## 1. hunter.md — ## Hypotheses — the verdict line exactly as printed (bullet, backticks, placeholder basis)

intent: none — an unfilled skeleton gives no basis (issue #17)

~~~~report
- `{{BLOCK_ID}}.1 — checked: <what exactly proves it>`
~~~~

expect: {"T1.1": ["checked"]}

**Differs from the intent** — today's parser reads this form differently.

## 2. hunter.md — ## Hypotheses — the line filled in, in backticks as printed

intent: checked

~~~~report
- `{{BLOCK_ID}}.1 — checked: ran the test; it goes red on the reverted fix`
~~~~

expect: {"T1.1": ["checked"]}

## 3. hunter.md — ## Hypotheses — the line filled in, without the backticks

intent: checked

~~~~report
- {{BLOCK_ID}}.1 — checked: ran the test; it goes red on the reverted fix
~~~~

expect: {"T1.1": ["checked"]}

## 4. hunter.md — ## Hypotheses — the verdict line exactly as printed (bullet, backticks, placeholder basis)

intent: none — an unfilled skeleton gives no basis (issue #17)

~~~~report
- `{{BLOCK_ID}}.2 — not checked: <what got in the way>`
~~~~

expect: {"T1.2": ["not checked"]}

**Differs from the intent** — today's parser reads this form differently.

## 5. hunter.md — ## Hypotheses — the line filled in, in backticks as printed

intent: not checked

~~~~report
- `{{BLOCK_ID}}.2 — not checked: no live database in the sandbox`
~~~~

expect: {"T1.2": ["not checked"]}

## 6. hunter.md — ## Hypotheses — the line filled in, without the backticks

intent: not checked

~~~~report
- {{BLOCK_ID}}.2 — not checked: no live database in the sandbox
~~~~

expect: {"T1.2": ["not checked"]}

## 7. hunter.md — ## Hypotheses — the verdict line exactly as printed (bullet, backticks, placeholder basis)

intent: none — an unfilled skeleton gives no basis (issue #17)

~~~~report
- `{{BLOCK_ID}}.3 — not applicable: <why the question is not about this code>`
~~~~

expect: {"T1.3": ["not applicable"]}

**Differs from the intent** — today's parser reads this form differently.

## 8. hunter.md — ## Hypotheses — the line filled in, in backticks as printed

intent: not applicable

~~~~report
- `{{BLOCK_ID}}.3 — not applicable: the block has no network code`
~~~~

expect: {"T1.3": ["not applicable"]}

## 9. hunter.md — ## Hypotheses — the line filled in, without the backticks

intent: not applicable

~~~~report
- {{BLOCK_ID}}.3 — not applicable: the block has no network code
~~~~

expect: {"T1.3": ["not applicable"]}

## 10. hunter.md — ## Hypotheses — a verdict word alone in backticks is a quotation of the word

intent: none

~~~~report
- {{BLOCK_ID}}.1 — `checked`
~~~~

expect: {}

## 11. hunter.md — ## Hypotheses — proof written indented under the verdict belongs to it

intent: checked

~~~~report
- {{BLOCK_ID}}.1 — checked: ran the test; it goes red on the reverted fix
    - <what exactly proves it>
~~~~

expect: {"T1.1": ["checked"]}

## 12. hunter.md — ## Hypotheses — a ``` fence is an example

intent: none

~~~~report
```markdown
- {{BLOCK_ID}}.1 — checked: <what exactly proves it>
```
~~~~

expect: {}

## 13. hunter.md — ## Hypotheses — a ~~~ fence is an example

intent: none

~~~~report
~~~
- {{BLOCK_ID}}.1 — checked: <what exactly proves it>
~~~
~~~~

expect: {}

## 14. hunter.md — ## Hypotheses — a block indented by four spaces is an example

intent: none

~~~~report
text

    - {{BLOCK_ID}}.1 — checked: <what exactly proves it>
~~~~

expect: {}

## 15. hunter.md — ## Hypotheses — a line behind `>` is an example

intent: none

~~~~report
> - {{BLOCK_ID}}.1 — checked: <what exactly proves it>
~~~~

expect: {}

## 16. hunter.md — ## Hypotheses — an html comment is an example

intent: none

~~~~report
<!-- - {{BLOCK_ID}}.1 — checked: <what exactly proves it> -->
~~~~

expect: {}

## 17. hunter.md — ## Findings — a finding's confidence is not a hypothesis verdict

intent: none — not a hypothesis verdict

~~~~report
## Findings
### {{BLOCK_ID}}-001 · <severity> · <short title>
**Confidence:** confirmed | plausible
~~~~

expect: {}

## 18. hunter.ru.md — ## Гипотезы — the verdict line exactly as printed (bullet, backticks, placeholder basis)

intent: none — an unfilled skeleton gives no basis (issue #17)

~~~~report
- `{{BLOCK_ID}}.1 — проверена: <чем именно доказано>`
~~~~

expect: {"T1.1": ["checked"]}

**Differs from the intent** — today's parser reads this form differently.

## 19. hunter.ru.md — ## Гипотезы — the line filled in, in backticks as printed

intent: checked

~~~~report
- `{{BLOCK_ID}}.1 — проверена: прогнал тест, на откаченной правке он краснеет`
~~~~

expect: {"T1.1": ["checked"]}

## 20. hunter.ru.md — ## Гипотезы — the line filled in, without the backticks

intent: checked

~~~~report
- {{BLOCK_ID}}.1 — проверена: прогнал тест, на откаченной правке он краснеет
~~~~

expect: {"T1.1": ["checked"]}

## 21. hunter.ru.md — ## Гипотезы — the verdict line exactly as printed (bullet, backticks, placeholder basis)

intent: none — an unfilled skeleton gives no basis (issue #17)

~~~~report
- `{{BLOCK_ID}}.2 — не проверена: <что помешало>`
~~~~

expect: {"T1.2": ["not checked"]}

**Differs from the intent** — today's parser reads this form differently.

## 22. hunter.ru.md — ## Гипотезы — the line filled in, in backticks as printed

intent: not checked

~~~~report
- `{{BLOCK_ID}}.2 — не проверена: в песочнице нет живой базы`
~~~~

expect: {"T1.2": ["not checked"]}

## 23. hunter.ru.md — ## Гипотезы — the line filled in, without the backticks

intent: not checked

~~~~report
- {{BLOCK_ID}}.2 — не проверена: в песочнице нет живой базы
~~~~

expect: {"T1.2": ["not checked"]}

## 24. hunter.ru.md — ## Гипотезы — the verdict line exactly as printed (bullet, backticks, placeholder basis)

intent: none — an unfilled skeleton gives no basis (issue #17)

~~~~report
- `{{BLOCK_ID}}.3 — неприменима: <почему вопрос не про этот код>`
~~~~

expect: {"T1.3": ["not applicable"]}

**Differs from the intent** — today's parser reads this form differently.

## 25. hunter.ru.md — ## Гипотезы — the line filled in, in backticks as printed

intent: not applicable

~~~~report
- `{{BLOCK_ID}}.3 — неприменима: в блоке нет сетевого кода`
~~~~

expect: {"T1.3": ["not applicable"]}

## 26. hunter.ru.md — ## Гипотезы — the line filled in, without the backticks

intent: not applicable

~~~~report
- {{BLOCK_ID}}.3 — неприменима: в блоке нет сетевого кода
~~~~

expect: {"T1.3": ["not applicable"]}

## 27. hunter.ru.md — ## Гипотезы — a verdict word alone in backticks is a quotation of the word

intent: none

~~~~report
- {{BLOCK_ID}}.1 — `проверена`
~~~~

expect: {}

## 28. hunter.ru.md — ## Гипотезы — proof written indented under the verdict belongs to it

intent: checked

~~~~report
- {{BLOCK_ID}}.1 — проверена: прогнал тест, на откаченной правке он краснеет
    - <чем именно доказано>
~~~~

expect: {"T1.1": ["checked"]}

## 29. hunter.ru.md — ## Гипотезы — a ``` fence is an example

intent: none

~~~~report
```markdown
- {{BLOCK_ID}}.1 — проверена: <чем именно доказано>
```
~~~~

expect: {}

## 30. hunter.ru.md — ## Гипотезы — a ~~~ fence is an example

intent: none

~~~~report
~~~
- {{BLOCK_ID}}.1 — проверена: <чем именно доказано>
~~~
~~~~

expect: {}

## 31. hunter.ru.md — ## Гипотезы — a block indented by four spaces is an example

intent: none

~~~~report
text

    - {{BLOCK_ID}}.1 — проверена: <чем именно доказано>
~~~~

expect: {}

## 32. hunter.ru.md — ## Гипотезы — a line behind `>` is an example

intent: none

~~~~report
> - {{BLOCK_ID}}.1 — проверена: <чем именно доказано>
~~~~

expect: {}

## 33. hunter.ru.md — ## Гипотезы — an html comment is an example

intent: none

~~~~report
<!-- - {{BLOCK_ID}}.1 — проверена: <чем именно доказано> -->
~~~~

expect: {}

## 34. hunter.ru.md — ## Находки — a finding's confidence is not a hypothesis verdict

intent: none — not a hypothesis verdict

~~~~report
## Находки
### {{BLOCK_ID}}-001 · <severity> · <краткое название>
**Уверенность:** confirmed | plausible
~~~~

expect: {}

## 35. verify.md — section 3 — the hypothesis verdict clause, on the hypothesis's id

intent: checked

~~~~report
- {{BLOCK_ID}}.1 — checked: what proves it
~~~~

expect: {"T1.1": ["checked"]}

## 36. verify.md — section 3 — the hypothesis verdict clause, on the hypothesis's id

intent: not checked

~~~~report
- {{BLOCK_ID}}.2 — not checked: what got in the way
~~~~

expect: {"T1.2": ["not checked"]}

## 37. verify.md — section 3 — the hypothesis verdict clause, on the hypothesis's id

intent: not applicable

~~~~report
- {{BLOCK_ID}}.3 — not applicable: why
~~~~

expect: {"T1.3": ["not applicable"]}

## 38. verify.md — ## Verdicts on hunter findings — the verifier's verdict on a finding, not a hypothesis verdict

intent: none — not a hypothesis verdict

~~~~report
## Verdicts on hunter findings
| id | verdict | severity after checking | justification |
|---|---|---|---|
| {{BLOCK_ID}}-001 | confirmed | medium | … |
| {{BLOCK_ID}}-002 | plausible | medium | … |
| {{BLOCK_ID}}-003 | rejected | medium | … |
| {{BLOCK_ID}}-004 | duplicate | medium | … |
~~~~

expect: {}

## 39. verify.md — «Verdicts on recorded findings» — a separate table, not a hypothesis verdict

intent: none — not a hypothesis verdict

~~~~report
## Verdicts on recorded findings
| id | verdict | reason |
|---|---|---|
| {{BLOCK_ID}}-001 | confirmed | … |
| {{BLOCK_ID}}-002 | rejected | … |
| {{BLOCK_ID}}-003 | fixed already | … |
~~~~

expect: {}

## 40. verify.md — ## Block coverage status — the coverage line, not a hypothesis verdict

intent: none — not a hypothesis verdict

~~~~report
## Block coverage status
Complete / incomplete — and what exactly remains.
~~~~

expect: {}

## 41. verify.ru.md — section 3 — the hypothesis verdict clause, on the hypothesis's id

intent: checked

~~~~report
- {{BLOCK_ID}}.1 — проверена: чем доказано
~~~~

expect: {"T1.1": ["checked"]}

## 42. verify.ru.md — section 3 — the hypothesis verdict clause, on the hypothesis's id

intent: not checked

~~~~report
- {{BLOCK_ID}}.2 — не проверена: что помешало
~~~~

expect: {"T1.2": ["not checked"]}

## 43. verify.ru.md — section 3 — the hypothesis verdict clause, on the hypothesis's id

intent: not applicable

~~~~report
- {{BLOCK_ID}}.3 — неприменима: почему
~~~~

expect: {"T1.3": ["not applicable"]}

## 44. verify.ru.md — ## Вердикты по находкам охотника — the verifier's verdict on a finding, not a hypothesis verdict

intent: none — not a hypothesis verdict

~~~~report
## Вердикты по находкам охотника
| id | вердикт | severity после проверки | обоснование |
|---|---|---|---|
| {{BLOCK_ID}}-001 | confirmed | medium | … |
| {{BLOCK_ID}}-002 | plausible | medium | … |
| {{BLOCK_ID}}-003 | rejected | medium | … |
| {{BLOCK_ID}}-004 | duplicate | medium | … |
~~~~

expect: {}

## 45. verify.ru.md — «Вердикты по записанным находкам» — a separate table, not a hypothesis verdict

intent: none — not a hypothesis verdict

~~~~report
## Вердикты по записанным находкам
| номер | вердикт | причина |
|---|---|---|
| {{BLOCK_ID}}-001 | подтверждена | … |
| {{BLOCK_ID}}-002 | отвергнута | … |
| {{BLOCK_ID}}-003 | уже починена | … |
~~~~

expect: {}

## 46. verify.ru.md — ## Состояние охвата блока — the coverage line, not a hypothesis verdict

intent: none — not a hypothesis verdict

~~~~report
## Состояние охвата блока
Полный / неполный — и что именно осталось.
~~~~

expect: {}

## 47. fix.md — What to deliver — the table finding → verdict → commit

intent: none — not a hypothesis verdict

~~~~report
| finding | verdict | commit |
|---|---|---|
| {{BLOCK_ID}}-001 | closed | abc1234 |
| {{BLOCK_ID}}-002 | rejected | abc1234 |
~~~~

expect: {}

## 48. fix.ru.md — What to deliver — the table finding → verdict → commit

intent: none — not a hypothesis verdict

~~~~report
| находка | вердикт | коммит |
|---|---|---|
| {{BLOCK_ID}}-001 | закрыта | abc1234 |
| {{BLOCK_ID}}-002 | отклонена | abc1234 |
~~~~

expect: {}

## 49. fixreview.md — ## Findings — a fix-review finding's confidence

intent: none — not a hypothesis verdict

~~~~report
## Findings
### R2-001 · <severity> · <short title>
**Confidence:** confirmed | plausible
~~~~

expect: {}

## 50. fixreview.md — the closing section — whether another round is needed

intent: none — not a hypothesis verdict

~~~~report
## Is another round needed
Yes/no and why
~~~~

expect: {}

## 51. fixreview.ru.md — ## Находки — a fix-review finding's confidence

intent: none — not a hypothesis verdict

~~~~report
## Находки
### R2-001 · <severity> · <краткое название>
**Уверенность:** confirmed | plausible
~~~~

expect: {}

## 52. fixreview.ru.md — the closing section — whether another round is needed

intent: none — not a hypothesis verdict

~~~~report
## Нужен ли следующий круг
Да/нет и почему
~~~~

expect: {}
