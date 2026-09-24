#!/usr/bin/env python3
"""The spend of one headless role run, by axis — from the `claude -p --output-format
stream-json --verbose` stream.

Axes (roadmap direction 9): input from cache / written to cache / uncached, output;
turns and tool calls (the cost is turns × context, not files read); tool output bytes;
re-reads (the same file, the same part, read again). Usage:

    axes.py <stream.jsonl>            full breakdown
    axes.py <stream.jsonl> --journal  one line for `review log`
"""
from __future__ import annotations

import collections
import json
import sys


def read_stream(path: str) -> dict:
    per_msg: dict[str, dict] = {}   # stream-json splits one message into several events with ONE usage — count once
    tool_calls: collections.Counter = collections.Counter()
    tool_bytes: collections.Counter = collections.Counter()
    reads: collections.Counter = collections.Counter()
    pending: dict[str, tuple[str, dict]] = {}
    result = None
    model = None
    unreadable = 0
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                # A killed run leaves its last line half-written. Dying on it costs the
                # journal line, the agent's reply and the run's exit code — everything the
                # measurement was for. The loss is counted and reported, not swallowed.
                unreadable += 1
                continue
            t = ev.get("type")
            if t == "assistant":
                m = ev["message"]
                model = m.get("model") or model
                per_msg[m.get("id")] = m.get("usage") or {}
                for c in m.get("content", []):
                    if c.get("type") == "tool_use":
                        tool_calls[c["name"]] += 1
                        pending[c["id"]] = (c["name"], c.get("input", {}))
            elif t == "user":
                for c in ev.get("message", {}).get("content", []):
                    if isinstance(c, dict) and c.get("type") == "tool_result":
                        name, inp = pending.get(c.get("tool_use_id"), ("?", {}))
                        content = c.get("content")
                        text = ("".join(x.get("text", "") for x in content if isinstance(x, dict))
                                if isinstance(content, list) else (content or ""))
                        tool_bytes[name] += len(text.encode("utf-8"))
                        if name == "Read":
                            key = inp.get("file_path", "?")
                            if inp.get("offset") is not None or inp.get("limit") is not None:
                                key += f"@{inp.get('offset', 0)}+{inp.get('limit', '')}"
                            reads[key] += 1
            elif t == "result":
                # a run can emit several results (a background task finishing after the
                # main answer reports 2 turns and 19 s); the run is the longest of them
                if result is None or (ev.get("num_turns") or 0) >= (result.get("num_turns") or 0):
                    result = ev
    usage: collections.Counter = collections.Counter()
    for u in per_msg.values():
        for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"):
            usage[k] += u.get(k, 0) or 0
    # the per-message output count is a stream artefact; the result carries the real one
    ru = (result or {}).get("usage") or {}
    output = ru.get("output_tokens") if result else None
    total_in = usage["input_tokens"] + usage["cache_creation_input_tokens"] + usage["cache_read_input_tokens"]
    # What the run ENDED as. Without a `result` event there is no measurement at all — the
    # turns, the duration and the cost are unknown, and printing 0 turns and $0.00 in the
    # format of a real measurement recorded an expensive truncated run as a free one. A
    # `result` with a subtype other than `success` is the client's own word that the run was
    # cut off (the turn cap, an error) — the turn cap is the safety switch, and its trips
    # must be visible in the journal.
    subtype = (result or {}).get("subtype")
    if result is None:
        outcome = "NO RESULT EVENT — the run was killed or the stream is truncated"
    elif (result or {}).get("is_error") or (subtype and subtype != "success"):
        outcome = f"RUN CUT OFF — {subtype or 'error'}"
    else:
        outcome = ""
    if unreadable:
        outcome = (outcome + "; " if outcome else "") + f"{unreadable} unreadable line(s)"
    return {
        "model": model, "messages": len(per_msg), "turns": (result or {}).get("num_turns"),
        "duration_s": round(((result or {}).get("duration_ms") or 0) / 1000),
        "cost_usd": (result or {}).get("total_cost_usd"), "outcome": outcome,
        "input": total_in, "cache_read": usage["cache_read_input_tokens"],
        "cache_write": usage["cache_creation_input_tokens"], "uncached": usage["input_tokens"],
        "output": output, "tool_calls": dict(tool_calls), "tool_bytes": dict(tool_bytes),
        "rereads": {f: n for f, n in reads.items() if n > 1},
        "files_read": len(reads),
    }


def journal_line(a: dict) -> str:
    """One line for `review log`. What is not measured is printed as `?`, never as zero:
    the journal is the only memory the next session has, and `0 min, None turns, $0.00`
    reads there as a cheap completed run, not as a run that was cut off."""
    cache = (a["cache_read"] / a["input"] * 100) if a["input"] else 0
    calls = sum(a["tool_calls"].values())
    turns = a["turns"] if a["turns"] is not None else "?"
    minutes = f"{a['duration_s'] // 60}" if a["duration_s"] else "?"
    output = f"{a['output'] / 1e3:.0f}k" if a["output"] is not None else "?"
    cost = f"${a['cost_usd']:.2f}" if a["cost_usd"] is not None else "unknown"
    return ((f"{a['outcome']} · " if a["outcome"] else "")
            + f"spend: {minutes} min, {turns} turns, {calls} tool calls, "
            f"input {a['input'] / 1e6:.1f}M tokens ({cache:.0f}% from cache, "
            f"{a['cache_write'] / 1e3:.0f}k written), output {output}, "
            f"re-reads {sum(n - 1 for n in a['rereads'].values())}, "
            f"cost estimate {cost}, model {a['model']}")


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    a = read_stream(sys.argv[1])
    if "--journal" in sys.argv:
        print(journal_line(a))
        return 0
    if a["outcome"]:
        print(f"⚠️  {a['outcome']}: the numbers below are what the stream still holds, "
              f"not the run's spend")
    print(f"model: {a['model']}; turns: {a['turns'] if a['turns'] is not None else '?'}; "
          f"duration: {a['duration_s']} s; cost estimate: "
          + (f"${a['cost_usd']:.2f}" if a["cost_usd"] is not None else "unknown"))
    share = (lambda k: f"{a[k] / a['input'] * 100:5.1f}%" if a["input"] else "    -")
    print(f"input total   {a['input']:>12,}")
    print(f"  from cache  {a['cache_read']:>12,}  {share('cache_read')}")
    print(f"  to cache    {a['cache_write']:>12,}  {share('cache_write')}")
    print(f"  uncached    {a['uncached']:>12,}  {share('uncached')}")
    print(f"output        {a['output']:>12,}" if a["output"] is not None
          else f"output        {'?':>12}")
    print("tool calls:")
    for name, n in sorted(a["tool_calls"].items(), key=lambda x: -x[1]):
        print(f"  {name:<10} {n:>5} calls  {a['tool_bytes'].get(name, 0):>10,} result bytes")
    total_b = sum(a["tool_bytes"].values())
    print(f"  {'TOTAL':<10} {sum(a['tool_calls'].values()):>5} calls  {total_b:>10,} result bytes (~{total_b // 4:,} tokens)")
    print(f"files read: {a['files_read']}; re-reads: {sum(n - 1 for n in a['rereads'].values())}")
    for f, n in sorted(a["rereads"].items(), key=lambda x: -x[1])[:10]:
        print(f"  {n}x {f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
