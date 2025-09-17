#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import os
from typing import Any, Dict, List


def load_index(csv_path: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with open(csv_path, "r") as f:
        r = csv.DictReader(f)
        for row in r:
            # cast numeric fields if present
            for k in row.keys():
                try:
                    row[k] = float(row[k])
                except Exception:
                    pass
            rows.append(row)
    return rows


def dominates(a: Dict[str, Any], b: Dict[str, Any], maximize_keys: List[str], minimize_keys: List[str]) -> bool:
    better_or_equal = True
    strictly_better = False
    for k in maximize_keys:
        if k in a and k in b:
            if a[k] < b[k]:
                better_or_equal = False
            if a[k] > b[k]:
                strictly_better = True
    for k in minimize_keys:
        if k in a and k in b:
            if a[k] > b[k]:
                better_or_equal = False
            if a[k] < b[k]:
                strictly_better = True
    return better_or_equal and strictly_better


def pareto_set(rows: List[Dict[str, Any]], maximize_keys: List[str], minimize_keys: List[str]) -> List[Dict[str, Any]]:
    undominated: List[Dict[str, Any]] = []
    for i, a in enumerate(rows):
        dominated = False
        for j, b in enumerate(rows):
            if i == j:
                continue
            if dominates(b, a, maximize_keys, minimize_keys):
                dominated = True
                break
        if not dominated:
            undominated.append(a)
    return undominated


def main():
    ap = argparse.ArgumentParser(description="Build multi-metric Pareto set for M4 index.csv")
    ap.add_argument("--index_csv", required=True)
    ap.add_argument("--out_dir", required=True)
    # default metrics: maximize mean_agent_pnl_mean, minimize spread and volatility
    ap.add_argument("--maximize", nargs="*", default=["mean_agent_pnl_mean"]) 
    ap.add_argument("--minimize", nargs="*", default=["mean_spread_mean", "realized_vol_mean"]) 
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    rows = load_index(args.index_csv)
    und = pareto_set(rows, args.maximize, args.minimize)

    # Save
    with open(os.path.join(args.out_dir, "pareto_multi.json"), "w") as f:
        json.dump({"maximize": args.maximize, "minimize": args.minimize, "points": und}, f, indent=2)
    # Also write CSV of frontier
    if und:
        fields = list(und[0].keys())
        with open(os.path.join(args.out_dir, "pareto_multi.csv"), "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            for row in und:
                w.writerow(row)
    print(f"Wrote Pareto frontier with {len(und)} points to {args.out_dir}")


if __name__ == "__main__":
    main()

