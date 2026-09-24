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
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            ev = json.loads(line)
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
                result = ev
    usage: collections.Counter = collections.Counter()
    for u in per_msg.values():
        for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"):
            usage[k] += u.get(k, 0) or 0
    # the per-message output count is a stream artefact; the result carries the real one
    ru = (result or {}).get("usage") or {}
    output = ru.get("output_tokens", sum((u.get("output_tokens", 0) or 0) for u in per_msg.values()))
    total_in = usage["input_tokens"] + usage["cache_creation_input_tokens"] + usage["cache_read_input_tokens"]
    return {
        "model": model, "messages": len(per_msg), "turns": (result or {}).get("num_turns"),
        "duration_s": round(((result or {}).get("duration_ms") or 0) / 1000),
        "cost_usd": (result or {}).get("total_cost_usd"),
        "input": total_in, "cache_read": usage["cache_read_input_tokens"],
        "cache_write": usage["cache_creation_input_tokens"], "uncached": usage["input_tokens"],
        "output": output, "tool_calls": dict(tool_calls), "tool_bytes": dict(tool_bytes),
        "rereads": {f: n for f, n in reads.items() if n > 1},
        "files_read": len(reads),
    }


def journal_line(a: dict) -> str:
    cache = (a["cache_read"] / a["input"] * 100) if a["input"] else 0
    calls = sum(a["tool_calls"].values())
    return (f"spend: {a['duration_s'] // 60} min, {a['turns']} turns, {calls} tool calls, "
            f"input {a['input'] / 1e6:.1f}M tokens ({cache:.0f}% from cache, "
            f"{a['cache_write'] / 1e3:.0f}k written), output {a['output'] / 1e3:.0f}k, "
            f"re-reads {sum(n - 1 for n in a['rereads'].values())}, "
            f"cost estimate ${a['cost_usd'] or 0:.2f}, model {a['model']}")


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    a = read_stream(sys.argv[1])
    if "--journal" in sys.argv:
        print(journal_line(a))
        return 0
    print(f"model: {a['model']}; turns: {a['turns']}; duration: {a['duration_s']} s; "
          f"cost estimate: ${a['cost_usd'] or 0:.2f}")
    share = (lambda k: f"{a[k] / a['input'] * 100:5.1f}%" if a["input"] else "    -")
    print(f"input total   {a['input']:>12,}")
    print(f"  from cache  {a['cache_read']:>12,}  {share('cache_read')}")
    print(f"  to cache    {a['cache_write']:>12,}  {share('cache_write')}")
    print(f"  uncached    {a['uncached']:>12,}  {share('uncached')}")
    print(f"output        {a['output']:>12,}")
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
