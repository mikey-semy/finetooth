"""The HTML summary: the same facts as tables and charts, no scripts."""

from __future__ import annotations

from ..base import VERSION
from ..workspace import CLI
from ..model import FINDING_STATUS, SEVERITIES
from ..i18n import MSG, names, review_lang
from ..text import CODE_SPAN, h
from ..register import finding_file, root_guards


# The HTML summary's mark, as the Markdown one has its machine line: a page written with
# `--out` elsewhere is still known for what it is (`summary_files`). `generator` is the
# standard name for it (HTML Living Standard, 4.2.5.1 "Standard metadata names").
SUMMARY_HTML_MARK = '<meta name="generator" content="finetooth summary">'
HTML_STYLE = """
:root{color-scheme:light;--bg:#fcfcfb;--panel:#f3f2ef;--ink:#0b0b0b;--muted:#52514e;--line:#dcdad4;
--accent:#1c5cab;--warn-bg:#fdf0d5;--warn-ink:#6b4500;
--sev-critical:#0d366b;--sev-high:#1c5cab;--sev-medium:#3987e5;--sev-low:#86b6ef;
--st-open:#eb6834;--st-fixed:#1baf7a;--st-deferred:#eda100;--st-rejected:#e87ba4;--st-duplicate:#4a3aa7;
--bar:#2a78d6}
@media (prefers-color-scheme: dark){:root{color-scheme:dark;--bg:#1a1a19;--panel:#252523;--ink:#f4f3ee;
--muted:#c3c2b7;--line:#3a3a37;--accent:#86b6ef;--warn-bg:#3d2e0c;--warn-ink:#fad38a;
--sev-critical:#cde2fb;--sev-high:#86b6ef;--sev-medium:#3987e5;--sev-low:#1c5cab;
--st-open:#d95926;--st-fixed:#199e70;--st-deferred:#c98500;--st-rejected:#d55181;--st-duplicate:#9085e9;
--bar:#3987e5}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:1100px;margin:0 auto;padding:16px}
h1{font-size:1.6rem;line-height:1.25;margin:.5rem 0}
h2{font-size:1.25rem;margin:2rem 0 .5rem;padding-top:.5rem;border-top:1px solid var(--line)}
p,li{overflow-wrap:anywhere}
code{font:.9em ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;overflow-wrap:anywhere}
.meta,.note{color:var(--muted);font-size:.9rem}
.scope{background:var(--warn-bg);color:var(--warn-ink);padding:12px 16px;border-radius:8px;font-weight:600}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:8px;margin:1rem 0}
.tile{background:var(--panel);border-radius:8px;padding:10px 12px;min-width:0}
.tile b{display:block;font-size:1.4rem;font-variant-numeric:tabular-nums}
.tile>span{color:var(--muted);font-size:.85rem}
.scroll{overflow-x:auto;max-width:100%;-webkit-overflow-scrolling:touch}
table{border-collapse:collapse;font-size:.9rem;min-width:100%}
th,td{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}
th{color:var(--muted);font-weight:600;white-space:nowrap}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
td.wide{min-width:16rem}td.mid{min-width:10rem}
svg{display:block;width:100%;height:auto;max-width:760px}
svg text{fill:var(--ink);font:12px system-ui,sans-serif}
svg .muted{fill:var(--muted)}
.legend{display:flex;flex-wrap:wrap;gap:4px 16px;margin:.5rem 0;font-size:.85rem;color:var(--muted);padding:0;list-style:none}
.legend i{display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:6px;vertical-align:-1px}
details{margin:.75rem 0}summary{cursor:pointer;color:var(--accent)}
"""


def H(key: str, **kw) -> str:
    """A message of the review's language as HTML. The template is escaped FIRST and the
    values put in after, so a value may carry markup built here (`num`) and the template
    itself can never inject any."""
    return CODE_SPAN.sub(r"<code>\1</code>", h(MSG[review_lang()][key])).format(**kw)


def num(key: str, value) -> str:
    """A number of the summary, tagged with where it comes from. The tag is what the test
    reads to hold every number against the register and the journal."""
    return f'<span data-k="{h(key)}">{h(value)}</span>'


def html_table(head: list[str], rows: list[list[str]], numeric: set[int] = frozenset(),
               wide: set[int] = frozenset(), mid: set[int] = frozenset()) -> str:
    """A table in its own scrolling box: a wide table scrolls inside the box, the page never
    scrolls sideways (the reader is on a phone as often as not)."""
    def cls(i: int) -> str:
        c = "n" if i in numeric else "wide" if i in wide else "mid" if i in mid else ""
        return f' class="{c}"' if c else ""
    th = "".join(f"<th{cls(i)}>{h(c)}</th>" for i, c in enumerate(head))
    body = "".join("<tr>" + "".join(f"<td{cls(i)}>{c}</td>" for i, c in enumerate(r)) + "</tr>"
                   for r in rows)
    return f'<div class="scroll"><table><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div>'


def legend(items: list[tuple[str, str]]) -> str:
    return '<ul class="legend">' + "".join(
        f'<li><i style="background:var({var})"></i>{h(label)}</li>' for var, label in items) + "</ul>"


def stacked_chart(blocks_: list[dict]) -> str:
    """Two stacked bars per block — defects by severity, then every record by status — on
    one scale (the largest bar), so bars compare across blocks. Drawn in viewBox units; the
    SVG scales to the width of the page."""
    sev_names, st_names = names("h_sev_names"), names("h_status_names")
    # 400 units wide: on a phone (~360 px) the 12-unit labels stay ~11 px; wider screens scale up.
    width, label_w, bar_h, gap, row_gap = 400, 48, 14, 3, 14
    plot_w = width - label_w - 36
    most = max([sum(b["statuses"].values()) for b in blocks_] + [1])
    parts, y = [], 8
    for b in blocks_:
        parts.append(f'<text x="0" y="{y + bar_h + 4}">{h(b["id"])}</text>')
        for series, keys, labels, var in (
                (b["by_severity"], SEVERITIES, sev_names, "--sev-"),
                (b["statuses"], FINDING_STATUS, st_names, "--st-")):
            x0 = label_w
            for k, label in zip(keys, labels):
                n = series[k]
                if not n:
                    continue
                w = max(n / most * plot_w - 2, 1)
                parts.append(f'<rect x="{x0:.1f}" y="{y}" width="{w:.1f}" height="{bar_h}" rx="3" '
                             f'style="fill:var({var}{k})"><title>{h(b["id"])} · {h(label)}: {n}</title></rect>')
                x0 += w + 2
            kind = "sev" if var == "--sev-" else "status"
            parts.append(f'<text class="muted" x="{x0 + 4:.1f}" y="{y + bar_h - 3}" '
                         f'data-k="chart.{h(b["id"])}.{kind}">{sum(series.values())}</text>')
            y += bar_h + gap
        y += row_gap
    return (f'<svg viewBox="0 0 {width} {y}" role="img" aria-label="{H("h_chart")}">'
            + "".join(parts) + "</svg>")


def cost_chart(roles: dict[str, dict]) -> str:
    """One bar per role, its measured cost. A single series: the heading names it."""
    live = [(r, s) for r, s in roles.items() if s["runs"]]
    if not any(s["cost_known"] for _, s in live):
        return ""
    if not live:
        return ""
    width, label_w, bar_h, gap = 400, 70, 18, 8
    most = max(s["cost"] for _, s in live) or 1
    parts, y = [], 4
    for role, s in live:
        # A role no run of which reported its cost gets no bar: a bar of zero would say "free".
        w = s["cost"] / most * (width - label_w - 64) if s["cost_known"] else 0
        bar = (f'<rect x="{label_w}" y="{y}" width="{max(w, 1):.1f}" height="{bar_h}" rx="3" '
               f'style="fill:var(--bar)"><title>{h(role)}: {h(s["cost_text"])}</title></rect>'
               if s["cost_known"] else "")
        parts.append(f'<text x="0" y="{y + bar_h - 5}">{h(role)}</text>{bar}'
                     f'<text class="muted" x="{label_w + w + 6:.1f}" y="{y + bar_h - 5}">{h(s["cost_text"])}</text>')
        y += bar_h + gap
    return (f'<svg viewBox="0 0 {width} {y}" role="img" aria-label="{H("h_economy_chart")}">'
            + "".join(parts) + "</svg>")


def render_summary_html(facts: dict) -> str:
    x, lang = facts, review_lang()
    bs, cov = x["by_status"], x["coverage"]
    sev_names, st_names = names("h_sev_names"), names("h_status_names")
    sev_label = dict(zip(SEVERITIES, sev_names))

    def where(f: dict) -> str:
        at = x["at"].get(f.get("id"))
        return f"<code>{h(finding_file(f))}{':' + h(at) if at else ''}</code>"

    def finding_rows(fs: list[dict], last) -> list[list[str]]:
        return [[f"<b>{h(f.get('id'))}</b>", h(sev_label.get(f.get("severity"), f.get("severity"))),
                 where(f), h((f.get("claim") or "").strip()), last(f)] for f in fs]
    out = [f'<!doctype html><html lang="{h(lang)}"><head><meta charset="utf-8">{SUMMARY_HTML_MARK}'
           f'<meta name="viewport" content="width=device-width, initial-scale=1">'
           f'<title>{H("h_title", project=h(x["project"]))}</title><style>{HTML_STYLE}</style></head>'
           f'<body><main>']
    # A partial review says so FIRST (#53): the reader must not take one area for the whole.
    if x["scope_line"]:
        out.append(f'<p class="scope" data-k="scope">{h(x["scope_line"])}</p>')
    out += [f'<h1>{H("h_title", project=h(x["project"]))}</h1>',
            f'<p class="meta">{H("h_meta", date=h(x["date"]), sha="<code>" + h(x["sha"][:12]) + "</code>", branch=h(x["branch"]), version=h(VERSION))}</p>',
            f'<p>{H("h_intro", cli=h(CLI))}</p>']
    # Goal and coverage.
    total = x["spend_total"]
    tiles = [(H("h_of", a=num("blocks.closed", x["closed"]), b=num("blocks.total", x["total_blocks"])), "h_t_blocks"),
             (num("findings.total", x["total_findings"]), "h_t_findings"),
             (num("findings.fixed", bs["fixed"]), "h_t_fixed"),
             (num("findings.open", bs["open"]), "h_t_open"),
             (num("findings.deferred", bs["deferred"]), "h_t_deferred"),
             (H("h_of", a=num("files.covered", cov["covered"]), b=num("files.total", cov["total"])), "h_t_files")]
    if total["runs"]:
        tiles.append((num("cost.total", total["cost_text"]), "h_t_cost"))
    out += [f'<h2 id="goal">{H("h_goal")}</h2>', '<div class="tiles">']
    out += [f'<div class="tile"><b>{v}</b><span>{H(k)}</span></div>' for v, k in tiles]
    out += ['</div>', '<p>' + H("h_coverage", covered=num("files.covered", cov["covered"]),
                                   total=num("files.total", cov["total"]),
                                   unowned=num("files.unowned", cov["unowned"]),
                                   excluded=num("files.excluded", cov["excluded"])) + '</p>',
            f'<p>{H("h_goals")}</p><ul>']
    out += [f'<li><b>{h(b["id"])}</b> {h(b["title"])}{" — " + h(b["goal"]) if b["goal"] else ""}</li>'
            for b in x["blocks"]]
    out.append("</ul>")
    # Blocks.
    rows = []
    for b in x["blocks"]:
        k, sp = f"block.{b['id']}", b["spend"]
        rows.append([f"<b>{h(b['id'])}</b>", h(b["title"]), h(b["status"]), num(f"{k}.files", b["files"])]
                    + [num(f"{k}.sev.{s}", b["by_severity"][s]) for s in SEVERITIES]
                    # Every status, duplicates included: the row adds up to the block's findings.
                    + [num(f"{k}.status.{s}", b["statuses"][s])
                       for s in ("fixed", "open", "deferred", "rejected", "duplicate")]
                    + [num(f"{k}.runs", sp["runs"]), num(f"{k}.turns", sp["turns_text"]),
                       num(f"{k}.cost", sp["cost_text"])])
    out += [f'<h2 id="blocks">{H("h_blocks")}</h2>',
            html_table(names("h_blocks_cols"), rows, numeric=set(range(3, 16))),
            f'<p class="note">{H("h_blocks_note")}</p>']
    # Chart.
    out += [f'<h2 id="chart">{H("h_chart")}</h2>',
            legend([(f"--sev-{s}", n) for s, n in zip(SEVERITIES, sev_names)]),
            legend([(f"--st-{s}", n) for s, n in zip(FINDING_STATUS, st_names)]),
            stacked_chart(x["blocks"]), f'<p class="note">{H("h_chart_note")}</p>']
    # Open findings.
    out.append(f'<h2 id="open">{H("h_open")}</h2>')
    if x["open"]:
        out += [html_table(names("h_open_cols"), finding_rows(
                    x["open"], lambda f: f"<code>{h(x['report'][f.get('id')])}</code>"
                    if x["report"].get(f.get("id")) else "—"),
                    wide={3}), f'<p class="note">{H("h_open_note")}</p>']
    else:
        out.append(f'<p>{H("h_open_none")}</p>')
    # What closed each class: the guards per root, then fixes by commit.
    out += [f'<h2 id="closed">{H("h_closed")}</h2>', f'<p class="note">{H("h_closed_note")}</p>']
    groups = sorted(x["roots"].items()) + ([("", [])] if x["unrooted_rules"] else [])
    trows = []
    for root, items in groups:
        guards = root_guards(items) if root else x["unrooted_rules"]
        ids = [i for g in guards.values() for i in g]
        gtext = "<br>".join((f"<code>{h(g)}</code>" if g else H("h_no_guard")) + " → " + h(", ".join(v))
                            for g, v in guards.items())
        trows.append([h(root) if root else H("h_no_root"), num(f"root.{root or '-'}.findings", len(ids)), gtext])
    if trows:
        out.append(html_table(names("h_roots_cols"), trows, numeric={1}, wide={2}, mid={0}))
    else:
        out.append(f'<p>{H("h_closed_none")}</p>')
    if x["fixed"]:
        out.append(f'<details><summary>{H("h_fixes", n=num("findings.fixed", len(x["fixed"])))}</summary><ul>')
        out += [f"<li>{h(f.get('id'))} → <code>{h(f.get('fix_commit') or ', '.join(f.get('fixed_in', [])))}</code></li>"
                for f in x["fixed"]]
        out.append("</ul></details>")
    # Accepted risks, and what was rejected.
    out += [f'<h2 id="risks">{H("h_risks")}</h2>', f'<p class="note">{H("h_risks_note")}</p>']
    if x["deferred"]:
        out.append(html_table(names("h_risks_cols"), finding_rows(
            x["deferred"], lambda f: h((f.get("defer_reason") or "").strip())), wide={3, 4}))
    else:
        out.append(f'<p>{H("h_risks_none")}</p>')
    if x["rejected"]:
        out.append(f'<details><summary>{H("h_rejected", n=num("findings.rejected", len(x["rejected"])))}</summary>')
        out.append(html_table(names("h_risks_cols"), finding_rows(
            x["rejected"], lambda f: h((f.get("reject_reason") or "").strip())), wide={3, 4}))
        out.append("</details>")
    # Economy.
    out.append(f'<h2 id="economy">{H("h_economy")}</h2>')
    if total["runs"]:
        erows = [[h(role), num(f"role.{role}.runs", s["runs"]), num(f"role.{role}.unknown", s["unknown"]),
                  num(f"role.{role}.turns", s["turns_text"]), num(f"role.{role}.cost", s["cost_text"])]
                 for role, s in x["spend_roles"].items() if s["runs"]]
        erows.append([f"<b>{H('sum_economy_total')}</b>", num("total.runs", total["runs"]),
                      num("total.unknown", total["unknown"]), num("total.turns", total["turns_text"]),
                      num("total.cost", total["cost_text"])])
        out.append(html_table(names("h_economy_cols"), erows, numeric={1, 2, 3, 4}))
        if total["unknown"]:
            out.append(f'<p class="note">{H("sum_economy_unknown", n=num("total.unknown", total["unknown"]))}</p>')
        out += [f'<p class="note">{H("h_economy_chart")}</p>', cost_chart(x["spend_roles"])]
    else:
        out.append(f'<p>{H("sum_economy_none")}</p>')
    # What is left.
    not_closed = [b["id"] for b in x["blocks"] if b["status"] != "closed"]
    left = [H("h_r_open", n=num("findings.open", bs["open"])),
            H("h_r_deferred", n=num("findings.deferred", bs["deferred"])),
            H("h_r_blocks", ids=h(", ".join(not_closed))) if not_closed else H("h_r_blocks_none"),
            H("h_r_unowned", n=num("files.unowned", cov["unowned"]))]
    if x["scope_line"]:
        left.append(H("h_r_outside", n=num("files.outside", cov["outside"])))
    out += [f'<h2 id="left">{H("h_remains")}</h2><ul>'] + [f"<li>{v}</li>" for v in left] + ["</ul>"]
    out.append(f'<p class="note">{H("h_footer", cli=h(CLI))}</p></main></body></html>')
    return "\n".join(out) + "\n"
