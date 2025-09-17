#!/usr/bin/env python3
from __future__ import annotations

import argparse
import glob
import json
import os
from typing import Dict, List


def try_import_matplotlib():
    try:
        import matplotlib.pyplot as plt  # type: ignore
        return plt
    except Exception:
        return None


def load_agg(path: str) -> Dict:
    with open(path, "r") as f:
        return json.load(f)


def plot_from_index(out_dir: str, index_jsons: List[str], title: str = "RL PnL vs Compute/Params"):
    plt = try_import_matplotlib()
    if plt is None:
        print("matplotlib not available. Install matplotlib to generate plots.")
        return
    # Collect (x: capacity_tokens) → mean PnL for rl_name
    xs: List[float] = []
    ys: List[float] = []
    labels: List[str] = []
    for p in index_jsons:
        agg = load_agg(p)
        cap = agg.get("compute", {}).get("capacity_tokens")
        rl_name = agg.get("rl_name", "rl_opt")
        mean = agg.get("aggregate", {}).get("agents", {}).get(rl_name, {}).get("mean")
        xs.append(cap)
        ys.append(mean)
        labels.append(os.path.basename(p))
    # Simple scatter
    plt.figure(figsize=(6, 4))
    plt.scatter(xs, ys)
    for x, y, lab in zip(xs, ys, labels):
        plt.annotate(str(x), (x, y))
    plt.xlabel("RL capacity tokens")
    plt.ylabel("RL mean PnL across seeds")
    plt.title(title)
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "rl_pnl_vs_capacity.png")
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    print(f"Saved {path}")


def plot_spread_time_series(run_dir: str, out_dir: str):
    plt = try_import_matplotlib()
    if plt is None:
        print("matplotlib not available. Install matplotlib to generate plots.")
        return
    steps = []
    spreads = []
    with open(os.path.join(run_dir, "steps.jsonl"), "r") as f:
        for line in f:
            try:
                rec = json.loads(line)
            except Exception:
                continue
            t = int(rec.get("t", 0))
            sp = rec.get("spread")
            if sp is None:
                continue
            steps.append(t)
            spreads.append(float(sp))
    plt.figure(figsize=(6, 3))
    plt.plot(steps, spreads, lw=0.8)
    plt.xlabel("t")
    plt.ylabel("Spread")
    plt.title("Spread over time (example run)")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "spread_over_time.png")
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    print(f"Saved {path}")


def main():
    ap = argparse.ArgumentParser(description="Quick plots for PnL and spread")
    ap.add_argument("--frontier_dir", required=True, help="Path to sweep_frontier output directory")
    ap.add_argument("--example_run_dir", required=False, help="Optional: a single run directory for spread plot")
    ap.add_argument("--out_dir", default="analysis/out/plots")
    args = ap.parse_args()

    # plot RL PnL vs capacity using all agg_*.json
    jsons = glob.glob(os.path.join(args.frontier_dir, "agg_*.json"))
    if jsons:
        plot_from_index(args.out_dir, jsons)
    else:
        print("No agg_*.json found. Run scripts/sweep_frontier.py first.")

    if args.example_run_dir:
        plot_spread_time_series(args.example_run_dir, args.out_dir)


if __name__ == "__main__":
    main()

