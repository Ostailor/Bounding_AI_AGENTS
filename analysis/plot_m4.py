#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import os
from typing import Any, Dict, List, Tuple


def try_import_matplotlib():
    try:
        import matplotlib.pyplot as plt  # type: ignore
        return plt
    except Exception:
        return None


def load_index(csv_path: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with open(csv_path, "r") as f:
        r = csv.DictReader(f)
        for row in r:
            # Convert numeric fields if present
            for k, v in row.items():
                try:
                    row[k] = float(v)
                except Exception:
                    pass
            rows.append(row)
    return rows


def group_by_share_capacity(rows: List[Dict[str, Any]], key: str) -> Dict[float, Dict[float, Tuple[float, float, float]]]:
    # Returns mapping: share -> {capacity -> (mean, ci_lo, ci_hi)} averaged across refill tokens
    out: Dict[float, Dict[float, Tuple[float, float, float]]] = {}
    # Accumulate by (share, capacity)
    tmp: Dict[Tuple[float, float], List[Tuple[float, float, float]]] = {}
    for r in rows:
        share = float(r.get("optimizer_share", float("nan")))
        cap = float(r.get("capacity_tokens", float("nan")))
        mean = float(r.get(f"{key}_mean", float("nan")))
        lo = float(r.get(f"{key}_ci_lo", float("nan")))
        hi = float(r.get(f"{key}_ci_hi", float("nan")))
        if not (mean == mean and cap == cap and share == share):
            continue
        tmp.setdefault((share, cap), []).append((mean, lo, hi))
    for (share, cap), vals in tmp.items():
        if not vals:
            continue
        m = sum(v[0] for v in vals) / len(vals)
        lo = sum(v[1] for v in vals) / len(vals)
        hi = sum(v[2] for v in vals) / len(vals)
        out.setdefault(share, {})[cap] = (m, lo, hi)
    return out


def plot_lines_by_share(out_dir: str, series: Dict[float, Dict[float, Tuple[float, float, float]]], title: str, ylabel: str, filename: str):
    plt = try_import_matplotlib()
    if plt is None:
        print("matplotlib not available. Install matplotlib to generate plots.")
        return
    plt.figure(figsize=(7, 4))
    for share, caps in sorted(series.items()):
        xs = sorted(caps.keys())
        ys = [caps[c][0] for c in xs]
        los = [caps[c][1] for c in xs]
        his = [caps[c][2] for c in xs]
        plt.plot(xs, ys, marker='o', label=f"share={share}")
        # CI band
        plt.fill_between(xs, los, his, alpha=0.2)
    plt.xlabel("RL capacity tokens")
    plt.ylabel(ylabel)
    plt.title(title)
    plt.legend(loc='best', fontsize=8)
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, filename)
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    print(f"Saved {path}")


def group_by_capacity_share(rows: List[Dict[str, Any]], key: str, capacities: List[float]) -> Dict[float, Dict[float, Tuple[float, float, float]]]:
    # Returns mapping: capacity -> {share -> (mean, ci_lo, ci_hi)} averaged across refill tokens
    out: Dict[float, Dict[float, Tuple[float, float, float]]] = {}
    tmp: Dict[Tuple[float, float], List[Tuple[float, float, float]]] = {}
    for r in rows:
        share = float(r.get("optimizer_share", float("nan")))
        cap = float(r.get("capacity_tokens", float("nan")))
        mean = float(r.get(f"{key}_mean", float("nan")))
        lo = float(r.get(f"{key}_ci_lo", float("nan")))
        hi = float(r.get(f"{key}_ci_hi", float("nan")))
        if not (mean == mean and cap == cap and share == share):
            continue
        tmp.setdefault((cap, share), []).append((mean, lo, hi))
    for (cap, share), vals in tmp.items():
        if not vals:
            continue
        m = sum(v[0] for v in vals) / len(vals)
        lo = sum(v[1] for v in vals) / len(vals)
        hi = sum(v[2] for v in vals) / len(vals)
        out.setdefault(cap, {})[share] = (m, lo, hi)
    # filter to requested capacities if provided
    if capacities:
        out = {c: out.get(c, {}) for c in capacities}
    return out


def plot_lines_by_capacity(out_dir: str, series: Dict[float, Dict[float, Tuple[float, float, float]]], title: str, ylabel: str, filename: str):
    plt = try_import_matplotlib()
    if plt is None:
        print("matplotlib not available. Install matplotlib to generate plots.")
        return
    plt.figure(figsize=(7, 4))
    for cap, shares in sorted(series.items()):
        xs = sorted(shares.keys())
        ys = [shares[s][0] for s in xs]
        los = [shares[s][1] for s in xs]
        his = [shares[s][2] for s in xs]
        plt.plot(xs, ys, marker='o', label=f"cap={cap}")
        plt.fill_between(xs, los, his, alpha=0.2)
    plt.xlabel("optimizer_share")
    plt.ylabel(ylabel)
    plt.title(title)
    plt.legend(loc='best', fontsize=8)
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, filename)
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    print(f"Saved {path}")


def main():
    ap = argparse.ArgumentParser(description="Plot M4 sweep metrics from index.csv")
    ap.add_argument("--index_csv", required=True)
    ap.add_argument("--out_dir", required=True)
    ap.add_argument("--capacities", nargs="*", type=float, default=[])
    args = ap.parse_args()

    rows = load_index(args.index_csv)

    # Lines: realized_vol_mean vs capacity by share
    vol_series = group_by_share_capacity(rows, "realized_vol")
    plot_lines_by_share(args.out_dir, vol_series, "Realized vol vs capacity (by share)", "realized_vol_mean", "vol_vs_capacity_by_share.png")

    # Lines: mean_spread_mean vs capacity by share
    spr_series = group_by_share_capacity(rows, "mean_spread")
    plot_lines_by_share(args.out_dir, spr_series, "Spread vs capacity (by share)", "mean_spread_mean", "spread_vs_capacity_by_share.png")

    # Lines: gini_pnl_mean vs share for selected capacities
    gini_series = group_by_capacity_share(rows, "gini_pnl", args.capacities)
    plot_lines_by_capacity(args.out_dir, gini_series, "Gini PnL vs optimizer_share (by capacity)", "gini_pnl_mean", "gini_vs_share_by_capacity.png")


if __name__ == "__main__":
    main()

