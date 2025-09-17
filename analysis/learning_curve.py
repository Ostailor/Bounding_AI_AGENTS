#!/usr/bin/env python3
from __future__ import annotations

import argparse
import glob
import json
import os
from typing import Dict, List, Tuple


def load_pnl_series(agent_log_path: str) -> List[Tuple[int, float]]:
    out: List[Tuple[int, float]] = []
    with open(agent_log_path, "r") as f:
        for line in f:
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if rec.get("type") != "pnl":
                continue
            t = int(rec.get("t", 0))
            pnl = float(rec.get("pnl", 0.0))
            out.append((t, pnl))
    out.sort(key=lambda x: x[0])
    return out


def align_series(series_list: List[List[Tuple[int, float]]]) -> Tuple[List[int], List[List[float]]]:
    # Intersect timesteps to ensure alignment
    if not series_list:
        return [], []
    common_ts = set(ts for ts, _ in series_list[0])
    for s in series_list[1:]:
        common_ts &= set(ts for ts, _ in s)
    ts_sorted = sorted(common_ts)
    values: List[List[float]] = []
    for s in series_list:
        m = {ts: v for ts, v in s}
        values.append([m[t] for t in ts_sorted])
    return ts_sorted, values


def mean_std(values: List[float]) -> Tuple[float, float]:
    if not values:
        return float("nan"), float("nan")
    mean = sum(values) / len(values)
    var = sum((v - mean) ** 2 for v in values) / len(values)
    return mean, var ** 0.5


def main():
    ap = argparse.ArgumentParser(description="Aggregate per-tick PnL learning curves across runs")
    ap.add_argument("--runs_glob", required=True, help="Glob for run directories (e.g., logs/m3_agents/*)")
    ap.add_argument("--agent_name", default="rl_opt")
    ap.add_argument("--out_json", default="analysis/out/learning_curve.json")
    ap.add_argument("--plot", action="store_true")
    ap.add_argument("--out_plot", default="analysis/out/learning_curve.png")
    args = ap.parse_args()

    run_dirs = [p for p in glob.glob(args.runs_glob) if os.path.isdir(p)]
    if not run_dirs:
        print("No run directories matched.")
        return
    series_list: List[List[Tuple[int, float]]] = []
    for rd in run_dirs:
        log_path = os.path.join(rd, f"agent_{args.agent_name}.jsonl")
        if not os.path.exists(log_path):
            continue
        series = load_pnl_series(log_path)
        if series:
            series_list.append(series)
    if not series_list:
        print("No PnL series found for the specified agent.")
        return
    ts, vals = align_series(series_list)
    # compute mean/std per t
    means: List[float] = []
    stds: List[float] = []
    for i in range(len(ts)):
        col = [v[i] for v in vals]
        m, s = mean_std(col)
        means.append(m)
        stds.append(s)
    os.makedirs(os.path.dirname(args.out_json), exist_ok=True)
    with open(args.out_json, "w") as f:
        json.dump({"t": ts, "mean_pnl": means, "std_pnl": stds, "n_runs": len(series_list)}, f, indent=2)
    print(f"Saved {args.out_json}")

    if args.plot:
        try:
            import matplotlib.pyplot as plt  # type: ignore
        except Exception:
            print("matplotlib not available; skipping plot.")
            return
        plt.figure(figsize=(6, 3))
        plt.plot(ts, means, label="mean PnL")
        # Optional: shaded +-1 std
        up = [m + s for m, s in zip(means, stds)]
        dn = [m - s for m, s in zip(means, stds)]
        plt.fill_between(ts, dn, up, color="C0", alpha=0.2, linewidth=0)
        plt.xlabel("t")
        plt.ylabel("PnL")
        plt.title(f"Learning curve: {args.agent_name} (n={len(series_list)})")
        os.makedirs(os.path.dirname(args.out_plot), exist_ok=True)
        plt.tight_layout()
        plt.savefig(args.out_plot, dpi=150)
        print(f"Saved {args.out_plot}")


if __name__ == "__main__":
    main()

