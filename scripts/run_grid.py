"""Run the repository's own backtest grid and print the summary it produces.

This is the closest available stand-in for the paper's Table 1 metrics: the
paper reports cumulative return / Sharpe / max drawdown on a portfolio equity
curve, which this codebase deliberately does not model. What it does report is,
per rating, the directional hit rate and the mean alpha against the regional
benchmark over `holding_period_days`.

Usage:
    python scripts/run_grid.py --tickers NVDA,AAPL \
        --dates 2026-10-06,2026-10-20 --analysts market,news,fundamentals,social
"""
from __future__ import annotations

import argparse
import json
import pathlib

from tradingagents.backtest import run_backtest, summarize
from tradingagents.default_config import build_default_config


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickers", default="NVDA,AAPL")
    ap.add_argument("--dates", required=True, help="comma separated YYYY-MM-DD")
    ap.add_argument("--analysts", default="market,news,fundamentals,social")
    ap.add_argument("--run-id", default=None)
    args = ap.parse_args()

    tickers = [t.strip() for t in args.tickers.split(",") if t.strip()]
    dates = [d.strip() for d in args.dates.split(",") if d.strip()]
    analysts = [a.strip() for a in args.analysts.split(",") if a.strip()]

    config = build_default_config()
    result = run_backtest(
        tickers, dates, config,
        selected_analysts=analysts,
        run_id=args.run_id,
        progress=lambda done, total, ticker, date: print(f"[{done}/{total}] {ticker} {date}", flush=True),
    )

    print(f"\ncells_run={result.cells_run} skipped={result.skipped} "
          f"failures={len(result.failures)} settlement_failures={len(result.settlement_failures)}")
    for t, d, why in result.failures:
        print(f"  FAIL {t} {d}: {why[:160]}")

    summary = summarize(result)
    rendered = summary.render()
    print("\n" + rendered)

    out = pathlib.Path(config["results_dir"]) / "backtest" / result.run_id / "summary.txt"
    out.write_text(rendered, encoding="utf-8")
    print(f"\nsaved -> {out}")

    payload = {
        "run_id": result.run_id,
        "cells_run": result.cells_run,
        "resolved": summary.resolved,
        "pending": summary.pending,
        "unscored": summary.unscored,
        "by_rating": {k: {"count": v.count, "hit_rate": v.hit_rate, "mean_alpha": v.mean_alpha}
                      for k, v in summary.by_rating.items()},
    }
    (out.parent / "summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
