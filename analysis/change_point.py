#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import os
from typing import Any, Dict, List, Tuple


def load_index(csv_path: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with open(csv_path, "r") as f:
        r = csv.DictReader(f)
        for row in r:
            try:
                row["capacity_tokens"] = float(row["capacity_tokens"]) if row.get("capacity_tokens") else float("nan")
                row["realized_vol_mean"] = float(row.get("realized_vol_mean", "nan"))
                row["crash_prob_mean"] = float(row.get("crash_prob_mean", "nan"))
                row["optimizer_share"] = float(row.get("optimizer_share", "nan"))
            except Exception:
                pass
            rows.append(row)
    return rows


def fit_line(xs: List[float], ys: List[float]) -> Tuple[float, float, float]:
    # returns (m, b, sse)
    n = len(xs)
    if n < 2:
        # Not enough points; treat as zero error with flat slope
        return 0.0, ys[0] if n == 1 else float("nan"), 0.0
    mx = sum(xs)/n
    my = sum(ys)/n
    num = sum((x-mx)*(y-my) for x,y in zip(xs, ys))
    den = sum((x-mx)**2 for x in xs)
    m = num/den if den != 0 else 0.0
    b = my - m*mx
    sse = sum((y - (m*x + b))**2 for x,y in zip(xs, ys))
    return m, b, sse


def segmented_break(xs: List[float], ys: List[float]) -> Dict[str, float]:
    # grid search single break among unique sorted xs (excluding extremes)
    pairs = sorted(zip(xs, ys), key=lambda t: t[0])
    xs = [p[0] for p in pairs]
    ys = [p[1] for p in pairs]
    uniq = sorted(set(xs))
    best = {"break_at": float("nan"), "sse": float("inf"), "m_left": float("nan"), "m_right": float("nan")}
    for i in range(1, len(uniq)-1):
        thr = uniq[i]
        lx = [x for x in xs if x <= thr]
        ly = [y for x,y in zip(xs, ys) if x <= thr]
        rx = [x for x in xs if x > thr]
        ry = [y for x,y in zip(xs, ys) if x > thr]
        m1, b1, sse1 = fit_line(lx, ly)
        m2, b2, sse2 = fit_line(rx, ry)
        sse = sse1 + sse2
        if sse < best["sse"]:
            best = {"break_at": thr, "sse": sse, "m_left": m1, "m_right": m2}
    return best


def main():
    ap = argparse.ArgumentParser(description="Change-point estimate for volatility/crash vs compute")
    ap.add_argument("--index_csv", required=True)
    ap.add_argument("--out_json", required=True)
    ap.add_argument("--metric", default="realized_vol_mean", choices=["realized_vol_mean", "crash_prob_mean"]) 
    ap.add_argument("--share_filter", type=float, default=1.0, help="Use rows with optimizer_share equal to this value")
    ap.add_argument("--bootstrap", type=int, default=500, help="Number of bootstrap samples for breakpoint CI (0 to disable)")
    args = ap.parse_args()

    rows = load_index(args.index_csv)
    rows = [r for r in rows if ("optimizer_share" in r and abs(r["optimizer_share"] - args.share_filter) < 1e-9)]
    # aggregate by capacity (mean metric across refill values)
    by_cap: Dict[float, List[float]] = {}
    for r in rows:
        cap = r["capacity_tokens"]
        val = float(r.get(args.metric, float("nan")))
        if val == val:
            by_cap.setdefault(cap, []).append(val)
    caps = sorted(by_cap.keys())
    xs = caps
    ys = [sum(by_cap[c])/len(by_cap[c]) for c in caps]
    best = segmented_break(xs, ys)
    # Fallback for small N: choose median as break if sse not finite
    if not (best["sse"] == best["sse"]) or math.isinf(best["sse"]):
        mid_idx = len(xs)//2
        best = {"break_at": xs[mid_idx], "sse": float("nan"), "m_left": float("nan"), "m_right": float("nan")}
    # Bootstrap CI for break_at if requested
    ci = None
    if args.bootstrap and len(xs) >= 3:
        import random
        bs_vals: List[float] = []
        pairs = list(zip(xs, ys))
        for _ in range(args.bootstrap):
            sample = [pairs[random.randrange(len(pairs))] for __ in range(len(pairs))]
            sx = [p[0] for p in sample]
            sy = [p[1] for p in sample]
            bsei = segmented_break(sx, sy)
            v = bsei.get("break_at")
            if v == v:  # not NaN
                bs_vals.append(float(v))
        if bs_vals:
            bs_vals.sort()
            lo = bs_vals[int(0.025 * len(bs_vals))]
            hi = bs_vals[int(0.975 * len(bs_vals)) - 1 if int(0.975 * len(bs_vals)) > 0 else 0]
            ci = {"lo": lo, "hi": hi, "n": len(bs_vals)}
    os.makedirs(os.path.dirname(args.out_json), exist_ok=True)
    with open(args.out_json, "w") as f:
        json.dump({
            "metric": args.metric,
            "optimizer_share": args.share_filter,
            "xs": xs,
            "ys": ys,
            "break": best,
            "break_ci": ci,
            "notes": "Simple two-segment linear fit; for paper use bootstrap CIs (future work)."
        }, f, indent=2)
    print(json.dumps(best, indent=2))


if __name__ == "__main__":
    main()
