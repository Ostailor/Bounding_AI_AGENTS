#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import os
from typing import Any, Dict, List


def try_import_matplotlib():
    try:
        import matplotlib  # type: ignore
        try:
            matplotlib.use("Agg", force=True)
        except Exception:
            pass
        import matplotlib.pyplot as plt  # type: ignore
        return plt
    except Exception:
        return None


def load_index(csv_path: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with open(csv_path, "r") as f:
        r = csv.DictReader(f)
        for row in r:
            rows.append(row)
    return rows


def float_or_nan(v: Any) -> float:
    try:
        return float(v)
    except Exception:
        return float("nan")


def plot_bars(out_dir: str, rows: List[Dict[str, Any]], metric: str, title: str, sort_by_improvement: bool = False):
    plt = try_import_matplotlib()
    if plt is None:
        print("matplotlib not available; skipping plots")
        return
    os.makedirs(out_dir, exist_ok=True)
    # prefer delta column if available
    dkey = f"d_{metric}"
    mean_key = f"{metric}_mean"
    lo_key = f"{metric}_ci_lo"
    hi_key = f"{metric}_ci_hi"
    use_delta = any(dkey in r for r in rows)
    xs: List[str] = []
    ys: List[float] = []
    yerr: List[float] = []
    colors: List[str] = []
    # collect raw entries
    entries = []  # (policy, y, err, color)
    for r in rows:
        pol = str(r.get("policy", ""))
        if not pol:
            continue
        if use_delta:
            if pol == "baseline":
                y = 0.0
            else:
                y = float_or_nan(r.get(dkey))
            # CI for delta not computed; show mean-only in that case
            err = 0.0
            # color by sign (green=improve, red=worse), baseline gray
            if pol == "baseline":
                c = "#7f7f7f"
            else:
                c = "#2ca02c" if y < 0 else "#d62728"
        else:
            m = float_or_nan(r.get(mean_key))
            lo = float_or_nan(r.get(lo_key))
            hi = float_or_nan(r.get(hi_key))
            y = m
            err = max(0.0, hi - m)
            c = "#1f77b4"
        entries.append((pol, y, err, c))

    # optionally sort by improvement (ascending delta → bigger improvement first), keep baseline first
    if use_delta and sort_by_improvement:
        base = [e for e in entries if e[0] == "baseline"]
        others = [e for e in entries if e[0] != "baseline"]
        others.sort(key=lambda t: (t[1], t[0]))
        entries = base + others

    for pol, y, err, c in entries:
        xs.append(pol)
        ys.append(y)
        yerr.append(err)
        colors.append(c)
    fig, ax = plt.subplots(figsize=(7, 4))
    xpos = list(range(len(xs)))
    ax.bar(xpos, ys, yerr=yerr if (not use_delta) else None, capsize=3, color=colors if colors else None)
    ax.set_xticks(xpos)
    ax.set_xticklabels(xs, rotation=30, ha='right')
    ax.set_title(title)
    ax.set_ylabel(dkey if use_delta else mean_key)
    # Legend for deltas
    if use_delta:
        import matplotlib.patches as mpatches  # type: ignore
        leg_elems = [
            mpatches.Patch(color="#2ca02c", label="improvement (negative)"),
            mpatches.Patch(color="#d62728", label="worsening (positive)"),
            mpatches.Patch(color="#7f7f7f", label="baseline (0)")
        ]
        ax.legend(handles=leg_elems, fontsize=8, loc="best")
    plt.tight_layout()
    path = os.path.join(out_dir, f"m6_{metric}.png")
    plt.savefig(path, dpi=150)
    print(f"Saved {path}")


def main():
    ap = argparse.ArgumentParser(description="Plot M6 policy deltas (bar charts with CIs)")
    ap.add_argument("--index_csv", required=True)
    ap.add_argument("--out_dir", required=True)
    ap.add_argument("--metrics", nargs="*", default=[
        "mean_agent_pnl", "realized_vol", "mean_spread", "gini_pnl", "msg_to_trade", "alloc_eff_mid", "depth_halflife", "spread_halflife"
    ])
    ap.add_argument("--sort_by_improvement", action="store_true", help="Sort policies by delta (ascending) for clearer comparison")
    args = ap.parse_args()

    rows = load_index(args.index_csv)
    for m in args.metrics:
        ttl = f"Policy results: {m} ({'delta' if any(f'd_{m}' in r for r in rows) else 'mean with CI'})"
        plot_bars(args.out_dir, rows, m, ttl, sort_by_improvement=args.sort_by_improvement)


if __name__ == "__main__":
    main()
