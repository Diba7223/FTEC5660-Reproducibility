"""Reproduction harness: run the same (ticker, date) N times and record
decision, latency and a decision-text digest, then dump a CSV.

Usage (from the repository root, with PYTHONPATH=. and the venv active):

    python scripts/run_trials.py --ticker NVDA --date 2026-11-03 --trials 5 \
        --tag baseline

Why this exists: one run yields one decision, which cannot separate a real
signal from sampling noise. Repeating the identical cell turns the run-to-run
variation into a measured quantity (rating distribution, mode share, latency
spread), which is exactly what a reproducibility report needs.
"""
from __future__ import annotations

import argparse
import csv
import json
import pathlib
import time
from collections import Counter

from tradingagents.default_config import build_default_config
from tradingagents.graph.trading_graph import TradingAgentsGraph

CSV_FIELDS = [
    "tag", "trial", "ticker", "date", "rating",
    "latency_s", "market_report_chars", "final_decision_chars", "decision_head",
]


def one_trial(ticker: str, date: str, tag: str, index: int, analysts: list[str],
              isolate_memory: bool = True) -> dict:
    # A fresh config per trial: DEFAULT_CONFIG is a module-level dict and the
    # graph mutates its own copy, so reusing it across trials risks leakage.
    config = build_default_config()
    # Nest under the configured results dir (TRADINGAGENTS_RESULTS_DIR) so every
    # artifact of the reproduction stays in one place.
    config["results_dir"] = f"{config['results_dir'].rstrip('/')}/{tag}/run_{index}"
    if isolate_memory:
        # The memory log is read back by the portfolio manager, so trials that
        # share one are not independent: trial 3 sees what trial 1 decided. Give
        # every trial its own log unless the caller explicitly wants the shared
        # behaviour (which is what the shipped CLI does).
        config["memory_log_path"] = (
            f"{config['results_dir'].rstrip('/')}/trading_memory.md"
        )

    started = time.perf_counter()
    graph = TradingAgentsGraph(selected_analysts=analysts, debug=False, config=config)
    state, signal = graph.propagate(ticker, date)
    latency = time.perf_counter() - started

    graph.save_reports(state, ticker)

    market_report = state.get("market_report") or ""
    decision = state.get("final_trade_decision") or state.get("trader_investment_plan") or ""
    return {
        "tag": tag,
        "trial": index,
        "ticker": ticker,
        "date": date,
        "rating": signal,
        "latency_s": round(latency, 1),
        "market_report_chars": len(market_report),
        "final_decision_chars": len(decision),
        "decision_head": decision.strip().replace("\n", " ")[:280],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticker", default="NVDA")
    ap.add_argument("--date", default="2026-11-03")
    ap.add_argument("--trials", type=int, default=5)
    ap.add_argument("--tag", default="baseline", help="labels this batch in the CSV")
    ap.add_argument("--analysts", default="market", help="comma separated analyst keys")
    ap.add_argument("--out", default="results/trials.csv")
    ap.add_argument("--shared-memory", action="store_true",
                    help="let all trials share one memory log (the CLI default); "
                         "off by default so trials stay independent")
    args = ap.parse_args()

    analysts = [a.strip() for a in args.analysts.split(",") if a.strip()]
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    for i in range(args.trials):
        try:
            row = one_trial(args.ticker, args.date, args.tag, i, analysts,
                            isolate_memory=not args.shared_memory)
        except Exception as exc:  # one failed trial must not lose the others
            print(f"[{i + 1}/{args.trials}] FAILED: {type(exc).__name__}: {exc}")
            row = {"tag": args.tag, "trial": i, "ticker": args.ticker, "date": args.date,
                   "rating": f"ERROR:{type(exc).__name__}", "latency_s": "",
                   "market_report_chars": "", "final_decision_chars": "", "decision_head": str(exc)[:280]}
        rows.append(row)
        print(f"[{i + 1}/{args.trials}] {row['latency_s']}s -> {row['rating']}")

    # Append so several batches (baseline / modification) accumulate in one file.
    new_file = not out.exists()
    with out.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        if new_file:
            writer.writeheader()
        writer.writerows(rows)

    ratings = [r["rating"] for r in rows]
    counts = Counter(ratings)
    mode, mode_n = counts.most_common(1)[0]
    latencies = [r["latency_s"] for r in rows if isinstance(r["latency_s"], float)]
    mean = sum(latencies) / len(latencies) if latencies else float("nan")
    var = sum((x - mean) ** 2 for x in latencies) / len(latencies) if latencies else 0.0

    summary = {
        "tag": args.tag,
        "n": len(rows),
        "rating_counts": dict(counts),
        "mode": mode,
        "mode_share": round(mode_n / len(rows), 3),
        "latency_mean_s": round(mean, 1),
        "latency_std_s": round(var ** 0.5, 1),
    }
    (out.parent / f"summary_{args.tag}.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
