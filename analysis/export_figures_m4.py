#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import List


def apply_style():
    # Force a non-interactive backend to avoid GUI/backend issues in headless environments
    import matplotlib  # type: ignore
    try:
        matplotlib.use("Agg", force=True)
    except Exception:
        pass
    import matplotlib as mpl  # type: ignore
    import matplotlib.pyplot as plt  # type: ignore
    mpl.rcParams.update({
        "font.size": 10,
        "axes.titlesize": 11,
        "axes.labelsize": 10,
        "legend.fontsize": 8,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "figure.dpi": 150,
        "savefig.dpi": 300,
        "axes.grid": True,
        "grid.alpha": 0.3,
    })
    # Try several style aliases; fall back to default if unavailable
    for style in ("seaborn-v0_8-whitegrid", "seaborn-whitegrid", "default"):
        try:
            plt.style.use(style)
            break
        except Exception:
            continue
    return plt


def main():
    ap = argparse.ArgumentParser(description="Export camera-ready M4 figures with consistent styling")
    ap.add_argument("--index_csv", required=True)
    ap.add_argument("--out_dir", required=True)
    ap.add_argument("--capacities", nargs="*", type=float, default=[4, 8, 12])
    ap.add_argument("--formats", nargs="*", default=["png", "pdf"], help="Output formats")
    args = ap.parse_args()

    try:
        plt = apply_style()
    except Exception:
        print("matplotlib not available. Install matplotlib to export figures.")
        return
    # Ensure repo root is on sys.path to import analysis.plot_m4 when run as a script
    ROOT = Path(__file__).resolve().parents[1]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    # Reuse plotting from plot_m4
    import csv
    from analysis.plot_m4 import (
        load_index,
        group_by_share_capacity,
        plot_lines_by_share,
        group_by_capacity_share,
        plot_lines_by_capacity,
    )  # type: ignore

    rows = load_index(args.index_csv)
    os.makedirs(args.out_dir, exist_ok=True)

    # Plot vol vs capacity by share
    vol_series = group_by_share_capacity(rows, "realized_vol")
    plot_lines_by_share(args.out_dir, vol_series, "Realized vol vs capacity (by share)", "realized_vol_mean", "vol_vs_capacity_by_share.png")
    # Plot spread vs capacity by share
    spr_series = group_by_share_capacity(rows, "mean_spread")
    plot_lines_by_share(args.out_dir, spr_series, "Spread vs capacity (by share)", "mean_spread_mean", "spread_vs_capacity_by_share.png")
    # Plot gini vs share by capacity
    gini_series = group_by_capacity_share(rows, "gini_pnl", args.capacities)
    plot_lines_by_capacity(args.out_dir, gini_series, "Gini PnL vs optimizer_share (by capacity)", "gini_pnl_mean", "gini_vs_share_by_capacity.png")

    # Save as requested formats (PNG already saved); convert to others by re-saving
    for name in ["vol_vs_capacity_by_share", "spread_vs_capacity_by_share", "gini_vs_share_by_capacity"]:
        src_png = os.path.join(args.out_dir, f"{name}.png")
        if not os.path.exists(src_png):
            continue
        img = plt.imread(src_png)
        fig = plt.figure(figsize=(7, 4))
        ax = fig.add_subplot(111)
        ax.axis('off')
        ax.imshow(img)
        for fmt in args.formats:
            if fmt == "png":
                continue
            fig.savefig(os.path.join(args.out_dir, f"{name}.{fmt}"), format=fmt, bbox_inches='tight', pad_inches=0)
        plt.close(fig)
    print(f"Exported figures to {args.out_dir}")


if __name__ == "__main__":
    main()
