"""Generate the black-and-white figures used in the report.

Reads the measured data (trials CSV + grid summary) so figures always match the
numbers in the text. Two label sets are produced: zh (Chinese report) and en.

Usage: python scripts/make_figures.py --lang zh --out docs/figures
"""
from __future__ import annotations

import argparse
import csv
import json
import pathlib

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.patches import FancyArrowPatch, Rectangle

ROOT = pathlib.Path(__file__).resolve().parents[1]
TRIALS = ROOT / "data/results/trials_v2.csv"
GRID = ROOT / "data/results/backtest/grid_repro/summary.json"
GRID_LOG = ROOT / "data/results/backtest/grid_repro/trading_memory.md"
SMOKE_LOG = ROOT / "data/memory/trading_memory.md"

TNR = "/System/Library/Fonts/Supplemental/Times New Roman.ttf"
SONG = "/System/Library/Fonts/Supplemental/Songti.ttc"

for path in (TNR, SONG):
    if pathlib.Path(path).exists():
        fm.fontManager.addfont(path)

L = {
    "zh": {
        "font": "Songti SC",
        "fig1_title": "",
        "a1": "基本面分析师", "a2": "情绪分析师", "a3": "新闻分析师", "a4": "技术分析师",
        "analysts": "四名分析师并行",
        "debate": "多空研究员辩论",
        "manager": "研究经理裁决",
        "trader": "交易员拟定方案",
        "risk": "风控三方辩论",
        "pm": "组合经理决策",
        "out": "输出五档评级",
        "f2x": "运行序号", "f2y": "评级", "f2leg": ["基线，温度 0.0", "改动，温度 1.0"], "f2batch": ["基线批次", "改动批次"],
        "f3x": "分析日期与标的", "f3y": "5 日超额收益（%）",
        "cap1": "图 1  TradingAgents 的决策流程",
        "cap2": "图 2  同一标的同一日期重复运行得到的评级分布",
        "cap3": "图 3  四个网格单元格的 5 日超额收益",
    },
    "en": {
        "font": "Times New Roman",
        "fig1_title": "",
        "a1": "Fundamentals", "a2": "Sentiment", "a3": "News", "a4": "Technical",
        "analysts": "Four analysts in parallel",
        "debate": "Bull versus bear debate",
        "manager": "Research manager",
        "trader": "Trader drafts a plan",
        "risk": "Three-way risk debate",
        "pm": "Portfolio manager",
        "out": "Five-tier rating",
        "f2x": "Run number", "f2y": "Rating", "f2leg": ["Baseline, temperature 0.0", "Modified, temperature 1.0"], "f2batch": ["Baseline batch", "Modified batch"],
        "f3x": "Ticker and analysis date", "f3y": "Five-day excess return (%)",
        "cap1": "Figure 1  Decision pipeline of TradingAgents",
        "cap2": "Figure 2  Ratings from repeated runs on one ticker and date",
        "cap3": "Figure 3  Five-day excess return of the four grid cells",
    },
}

RATINGS = ["Buy", "Overweight", "Hold", "Underweight", "Sell", "REVIEW"]


def setup(lang: str) -> None:
    plt.rcParams.update({
        "font.family": L[lang]["font"],
        "font.size": 9,
        "axes.edgecolor": "black",
        "axes.linewidth": 0.6,
        "text.color": "black",
        "axes.labelcolor": "black",
        "xtick.color": "black",
        "ytick.color": "black",
        "figure.dpi": 300,
        "savefig.dpi": 300,
    })


def box(ax, x, y, w, h, text, fs=8.5):
    ax.add_patch(Rectangle((x, y), w, h, facecolor="#f2f2f2", edgecolor="black", linewidth=0.6))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, color="black")


def arrow(ax, x1, y1, x2, y2):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=8,
                                 linewidth=0.6, color="black", shrinkA=0, shrinkB=0))


def fig_pipeline(lang: str, out: pathlib.Path) -> None:
    t = L[lang]
    fig, ax = plt.subplots(figsize=(5.6, 4.5))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 11.2)
    ax.axis("off")

    xs = [0.15, 2.55, 4.95, 7.35]
    for x, name in zip(xs, [t["a1"], t["a2"], t["a3"], t["a4"]]):
        box(ax, x, 9.6, 2.3, 0.85, name, 7.6)

    box(ax, 2.4, 7.9, 5.2, 0.9, t["debate"])
    box(ax, 2.4, 6.3, 5.2, 0.9, t["manager"])
    box(ax, 2.4, 4.7, 5.2, 0.9, t["trader"])
    box(ax, 2.4, 3.1, 5.2, 0.9, t["risk"])
    box(ax, 2.4, 1.5, 5.2, 0.9, t["pm"])
    box(ax, 2.4, 0.1, 5.2, 0.85, t["out"], 8)

    for x in xs:
        arrow(ax, x + 1.15, 9.6, 5.0, 8.85)
    for y1, y2 in [(7.9, 7.25), (6.3, 5.65), (4.7, 4.05), (3.1, 2.45), (1.5, 1.0)]:
        arrow(ax, 5.0, y1, 5.0, y2)

    fig.tight_layout(pad=0.2)
    fig.savefig(out, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def read_trials() -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    with TRIALS.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            out.setdefault(row["tag"], []).append(row["rating"])
    return out


def fig_ratings(lang: str, out: pathlib.Path) -> None:
    """Dot chart: one marker per run, so disagreement shows up as vertical spread."""
    t = L[lang]
    data = read_trials()
    tags = [g for g in ["baseline2", "mod_temp1b"] if g in data]
    if not tags:
        tags = list(data)[:2]

    fig, ax = plt.subplots(figsize=(5.6, 3.1))
    markers = ["o", "^"]
    fills = ["black", "white"]
    x = 0.0
    batch_positions: list[list[float]] = []
    ticks, labels = [], []
    for k, tag in enumerate(tags):
        positions = []
        for rating in data[tag]:
            y = RATINGS.index(rating)
            ax.plot([x], [y], marker=markers[k], markersize=8,
                    markerfacecolor=fills[k], markeredgecolor="black",
                    markeredgewidth=0.8, linestyle="none",
                    label=t["f2leg"][k] if not positions else None)
            positions.append(x)
            x += 1.0
        batch_positions.append(positions)
        ticks.append(sum(positions) / len(positions))
        labels.append(t["f2batch"][k])
        x += 1.4

    if len(batch_positions) == 2:
        sep = (max(batch_positions[0]) + min(batch_positions[1])) / 2
        ax.axvline(sep, color="#888888", linewidth=0.6, linestyle=":")

    ax.set_yticks(range(len(RATINGS)))
    ax.set_yticklabels(RATINGS, fontsize=8.5)
    ax.set_xticks(ticks)
    ax.set_xticklabels(labels, fontsize=8.5)
    ax.set_ylim(-0.6, len(RATINGS) - 0.4)
    ax.set_xlim(-0.8, x - 1.4 + 0.2)
    ax.set_xlabel(t["f2x"], fontsize=9)
    ax.set_ylabel(t["f2y"], fontsize=9)
    ax.grid(axis="y", color="#dddddd", linewidth=0.5)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, fontsize=8, loc="upper center",
              bbox_to_anchor=(0.5, -0.22), ncol=2, handletextpad=0.4, columnspacing=1.6)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout(pad=0.3)
    fig.savefig(out, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def parse_grid() -> list[tuple[str, str, float]]:
    rows = []
    for line in GRID_LOG.read_text(encoding="utf-8").splitlines():
        if not line.startswith("["):
            continue
        parts = [p.strip() for p in line.strip("[]").split("|")]
        if len(parts) < 5:
            continue
        date, ticker, rating, alpha = parts[0], parts[1], parts[2], parts[4]
        try:
            rows.append((ticker, date, float(alpha.rstrip("%"))))
        except ValueError:
            continue
    return rows


def fig_alpha(lang: str, out: pathlib.Path) -> None:
    t = L[lang]
    rows = parse_grid()
    labels = [f"{tk}\n{d[5:]}" for tk, d, _ in rows]
    vals = [a for _, _, a in rows]

    fig, ax = plt.subplots(figsize=(5.4, 2.7))
    positions = range(len(vals))
    ax.bar(positions, vals, width=0.5, edgecolor="black", linewidth=0.6,
           facecolor=("white" if True else "black"))
    for p, v in zip(positions, vals):
        ax.text(p, v + (0.35 if v >= 0 else -0.55), f"{v:+.1f}", ha="center",
                va="bottom" if v >= 0 else "top", fontsize=7.5)
    ax.axhline(0, color="black", linewidth=0.7)
    ax.set_xticks(list(positions))
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_xlabel(t["f3x"], fontsize=9)
    ax.set_ylabel(t["f3y"], fontsize=9)
    lo = min(vals + [0]) - 1.6
    hi = max(vals + [0]) + 1.6
    ax.set_ylim(lo, hi)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout(pad=0.3)
    fig.savefig(out, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", default="zh", choices=["zh", "en"])
    ap.add_argument("--out", default="docs/figures")
    ap.add_argument("--trials", default=None)
    args = ap.parse_args()

    if args.trials:
        global TRIALS
        TRIALS = pathlib.Path(args.trials)
    setup(args.lang)
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    suffix = "" if args.lang == "zh" else "_en"

    fig_pipeline(args.lang, out / f"fig1_pipeline{suffix}.png")
    fig_ratings(args.lang, out / f"fig2_ratings{suffix}.png")
    fig_alpha(args.lang, out / f"fig3_alpha{suffix}.png")
    print("figures written to", out)


if __name__ == "__main__":
    main()
