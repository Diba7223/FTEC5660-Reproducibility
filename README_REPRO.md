# Reproduction notes: TradingAgents (FTEC5660)

This repository is a fork of [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents)
pinned at tag `v0.7.1` (commit `9fa1196`), used for a reproducibility study.

**What is reproduced here**: the multi-agent pipeline itself (four analysts → bull/bear
debate → research manager → trader → three-way risk debate → portfolio manager), plus a
measurement of how stable its final rating is when the same ticker and date are analysed
repeatedly.

**Headline finding**: the pipeline runs end to end and grounds its price claims in a
verified data snapshot, but the decision is not reproducible — three runs of the same cell
returned Overweight, Underweight, and an unparseable REVIEW (mode share 0.333). The
paper's headline metrics (cumulative return, Sharpe, max drawdown) cannot be reproduced
from this codebase at all, because `tradingagents/backtest.py` deliberately does not model
positions or a cash ledger.

Full write-up: `submission/复现报告_中文.md` in the parent project folder.

## Install

The documented `pip install .` fails on this machine at the build-backend stage:

```
error: [Errno 17] EEXIST: file already exists, mkdir '.../uv/builds-v0/.tmpXXXX/.tmp-xxxx'
```

This is not caused by the (non-ASCII) checkout path and not by stale `egg-info`: both were
ruled out. Install the dependencies directly and run from source instead — the CLI is
documented to support that path and behaves identically.

```bash
git clone <this repo> && cd TradingAgents
git checkout v0.7.1

uv venv --python 3.13
source .venv/bin/activate

python3 -c "import tomllib;print('\n'.join(tomllib.load(open('pyproject.toml','rb'))['project']['dependencies']))" > /tmp/deps.txt
uv pip install -r /tmp/deps.txt

export PYTHONPATH=$PWD
python -m cli.main --help    # smoke test
```

## Configure

Copy `.env.example` to `.env` (never commit it) and set at least:

```bash
DEEPSEEK_API_KEY=sk-...
TRADINGAGENTS_LLM_PROVIDER=deepseek
TRADINGAGENTS_DEEP_THINK_LLM=deepseek-v4-pro
TRADINGAGENTS_QUICK_THINK_LLM=deepseek-flash
TRADINGAGENTS_OUTPUT_LANGUAGE=Chinese
TRADINGAGENTS_MAX_DEBATE_ROUNDS=1
TRADINGAGENTS_MAX_RISK_ROUNDS=1
TRADINGAGENTS_MAX_TOOL_ROUNDS=8
TRADINGAGENTS_TEMPERATURE=0.0
TRADINGAGENTS_NO_UPDATE_CHECK=1
SEC_EDGAR_USER_AGENT="Your Name you@example.com"

# Keep every artifact inside the repo so a run can be archived with the code.
TRADINGAGENTS_RESULTS_DIR=$PWD/data/results
TRADINGAGENTS_CACHE_DIR=$PWD/data/cache
TRADINGAGENTS_MEMORY_LOG_PATH=$PWD/data/memory/trading_memory.md
```

Without the last three variables the package writes to `~/.tradingagents/`, which fails
under a sandboxed shell and scatters run artifacts outside version control.

## Run

Single analysis:

```bash
python -m cli.main --ticker NVDA --date 2026-11-03 \
    --analysts market,news,fundamentals,social --save --no-show
```

Repeated trials (the harness added for this study):

```bash
python scripts/run_trials.py --ticker NVDA --date 2026-11-03 \
    --trials 3 --tag baseline --analysts market,news,fundamentals,social

TRADINGAGENTS_TEMPERATURE=1.0 python scripts/run_trials.py \
    --ticker NVDA --date 2026-11-03 --trials 3 --tag mod_temp1 \
    --analysts market,news,fundamentals,social
```

Results land in `data/results/trials.csv` and `data/results/summary_<tag>.json`.

## Measured results

| Batch | Memory log | Temperature | Ratings | Mode share | Latency (s) |
|---|---|---|---|---|---|
| first | shared | 0.0 | Overweight, REVIEW, Underweight | 0.333 | 518.8 ± 52.4 |
| second | isolated | 0.0 | Overweight, Overweight, Overweight | 1.0 | 511.4 ± 109.3 |
| third | isolated | 1.0 | Underweight, Hold, Overweight | 0.333 | 506.7 ± 16.4 |

Two lessons. First, trials that share a memory log are not independent: the portfolio
manager reads earlier decisions on the same ticker, so the later runs saw the earlier
conclusions. Isolating the log per trial turned three disagreeing runs into three
identical ones. Second, temperature does matter here, contrary to the note in the
README that reasoning models largely ignore it. With three runs per batch the exact
test on that difference gives p ≈ 0.4, so the direction is clear but the size is not
measured.

A separate finding stands regardless: the paper's cumulative return, Sharpe and
drawdown cannot be recomputed at all, because `tradingagents/backtest.py` refuses to
model positions and a cash ledger.

## Known issues hit while reproducing

| Symptom | Cause | Workaround |
|---|---|---|
| `pip install .` → `EEXIST` in build backend | build-backend temp dir race | install deps directly, run from source |
| `PermissionError` writing `~/.tradingagents/cache/*.tmp` | sandbox blocks writes outside the workspace | point `TRADINGAGENTS_*_DIR` at the repo |
| `Vendor 'fred' not configured` | `FRED_API_KEY` unset | accept missing macro data, record it |
| `Reddit RSS fetch failed … HTTP 403` | Reddit blocks the RSS endpoint | sentiment falls back to StockTwits only |
| `Yahoo Finance news unavailable` | upstream feed intermittently empty | **record it** — it changes the decision |
| `structured-output invocation failed … retrying once as free text` | DeepSeek does not honour the JSON schema | monitor REVIEW rate; it is a plumbing failure, not a neutral call |
