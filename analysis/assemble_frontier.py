#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
from typing import Any, Dict, List, Tuple


def load_index(csv_path: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with open(csv_path, "r") as f:
        r = csv.DictReader(f)
        for row in r:
            # convert some fields
            for k in [
                "epsilon",
                "alpha",
                "inv_penalty",
                "tokens_per_eval",
                "tokens_per_update",
                "capacity_tokens",
                "refill_tokens",
                "rl_mean_pnl",
                "rl_std_pnl",
                "mm_mean_pnl",
                "kg_mean_pnl",
                "tb_mean_pnl",
                "spread_mean",
            ]:
                if row.get(k) == "" or row.get(k) is None:
                    continue
                try:
                    row[k] = float(row[k])
                except Exception:
                    pass
            rows.append(row)
    return rows


def pareto_front(points: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    """Compute Pareto frontier maximizing x (P&L) and minimizing y (compute).

    points: list of (pnl, capacity_tokens)
    Returns frontier as a sorted list by compute ascending.
    """
    # sort by compute asc, pnl desc; then filter
    pts = sorted(points, key=lambda t: (t[1], -t[0]))
    frontier: List[Tuple[float, float]] = []
    best_pnl = -1e18
    for pnl, comp in pts:
        if pnl > best_pnl:
            frontier.append((pnl, comp))
            best_pnl = pnl
    return frontier


def main():
    ap = argparse.ArgumentParser(description="Assemble frontier summary and Pareto set from sweep index.csv")
    ap.add_argument("--index_csv", required=True)
    ap.add_argument("--out_dir", default="analysis/out")
    args = ap.parse_args()

    rows = load_index(args.index_csv)
    # Build points for RL PnL vs compute
    pts = []
    for r in rows:
        pnl = float(r.get("rl_mean_pnl", float("nan")))
        comp = float(r.get("capacity_tokens", float("nan")))
        if pnl == pnl and comp == comp:
            pts.append((pnl, comp))
    front = pareto_front(pts)

    os.makedirs(args.out_dir, exist_ok=True)
    # Save front as CSV
    pareto_csv = os.path.join(args.out_dir, "pareto_rl_pnl_vs_capacity.csv")
    with open(pareto_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["rl_mean_pnl", "capacity_tokens"])
        for pnl, comp in front:
            w.writerow([pnl, comp])
    # Save a compact summary JSON with top variants by PnL
    top = sorted(rows, key=lambda r: (float(r.get("rl_mean_pnl", -1e18))), reverse=True)[:10]
    with open(os.path.join(args.out_dir, "frontier_summary.json"), "w") as f:
        json.dump({"top_variants": top}, f, indent=2)
    print(f"Saved Pareto CSV: {pareto_csv} and frontier_summary.json")


if __name__ == "__main__":
    main()

