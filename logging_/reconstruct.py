"""Turn a decision log into the Round 3 Q1.2 table (markdown / csv). `python -m logging_.reconstruct <log.jsonl>`."""
from __future__ import annotations

import csv
import io
import json
import sys
from pathlib import Path

from logging_.decision_log import read_log

COLS = ["timestamp", "state", "input", "source", "decision", "rule", "action / message", "connector", "result"]


def _row(r: dict) -> list[str]:
    action = r.get("user_message") or (json.dumps(r["tool_call"], ensure_ascii=False) if r.get("tool_call") else r.get("action", ""))
    state = r["state_before"] if r["state_before"] == r["state_after"] else f"{r['state_before']} -> {r['state_after']}"
    inp = r.get("input")
    return [r["ts"], state or "", json.dumps(inp, ensure_ascii=False) if inp is not None else "", r["input_source"],
            r["decision"], r.get("rule", ""), str(action)[:300], r.get("connector") or "", r.get("result", "")]


def to_markdown(records: list[dict]) -> str:
    esc = lambda s: str(s).replace("|", "\\|").replace("\n", " ")  # noqa: E731
    lines = ["| " + " | ".join(COLS) + " |", "|" + "---|" * len(COLS)]
    lines += ["| " + " | ".join(esc(c) for c in _row(r)) + " |" for r in records]
    return "\n".join(lines) + "\n"


def to_csv(records: list[dict]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(COLS)
    w.writerows(_row(r) for r in records)
    return buf.getvalue()


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print("usage: python -m logging_.reconstruct <log.jsonl> [--csv]")
        return 2
    recs = read_log(Path(argv[0]))
    print(to_csv(recs) if "--csv" in argv else to_markdown(recs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
