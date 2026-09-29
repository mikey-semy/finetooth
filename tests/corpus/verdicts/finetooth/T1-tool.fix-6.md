# T1 — fix report, round 6 (the lead, option 1 chosen by the owner)

Fix review round 5 named the design question the code could not answer alone: one quotation
tracker serves manifests (a swallowed fence loses hypotheses) and reports (a fence read as
text turns the template's skeleton into answers). The owner chose the principle **"in doubt,
the gate goes red"**.

## Closed

| finding | what was done |
|---|---|
| T1-046 (R5-001, high) | `quoted_lines(lines, unclosed)`: `"text"` for what defines the work (manifests: `section_body`, `section_items_full`, `acceptance_of`, `demote`), `"quoted"` for what reports it (`verdict_mentions`, `unquoted` in the substance and limits gates). Both directions make the gate stricter |
| T1-048 (R5-003) | a verdict inside an inline code span is a quotation (`INLINE_CODE`, own name — a second `CODE_SPAN` from round 2 shadowed it at first); exception: a list item that opens with a span holding the hypothesis id, the old template's answer form. Verdicts counted only inside a hypotheses section when the report has one. The hunter template asks for plain-text verdicts (en, ru). The lead's `>` marks in the hunter report were REVERTED — `check` is green on the report as the hunter wrote it |
| T1-047 (R5-002) | the changelog intro restated from the register: 51 findings, 49 fixed, 1 deferred, 1 rejected |
| T1-049 (R5-004) | `QuotationMapTest` moved above `if __name__ == "__main__"` |
| T1-050 (R5-005) | `import` refuses a draft row over `CLAIM_MAX`/`SCENARIO_MAX` — the first run of it caught two over-long rows of this very draft |
| T1-051 (R5-006) | `fixed_in` of T1-043/044/045 point at the documents they changed |

## Measured on live registers

`hypotheses` on every started block of setfork-app (6 blocks) and arch-dashboard (8), old
tool vs new: not one verdict moved. T1: `closed 15/15`, no conflicts, without editing the
hunter's report.

## Mutations (each red)

unclosed mode ignored → `test_незакрытая_ограда_в_отчёте_остаётся_цитатой`; code spans kept →
`test_вердикт_в_код_спане_прозы_и_таблицы_не_ответ`; section filter off → the same; the old
answer form dropped → two tests (`test_вся_строка_вердикта_в_кавычках_остаётся_вердиктом` and
the span test); `import` limits removed → `test_import_держит_те_же_пределы_что_check`.

## Gates

`python3 -m unittest discover -s tests` — OK (236); `skills-ref validate` — valid.
