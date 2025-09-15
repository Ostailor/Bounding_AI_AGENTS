#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import glob
import json
import math
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass
class IntentRecord:
    t: int
    agent: str
    intent_type: str
    side: Optional[str]
    px: Optional[float]
    qty: Optional[int]
    tokens_req: int
    tokens_used: int
    tokens_remain: int
    latency_ms: float
    arrival_t: int
    degraded: bool


@dataclass
class TimingRecord:
    t: int
    agent: str
    wall_ms: float


def load_agent_logs(run_dir: str) -> Tuple[List[IntentRecord], List[TimingRecord]]:
    intents: List[IntentRecord] = []
    timings: List[TimingRecord] = []
    for path in glob.glob(os.path.join(run_dir, "agent_*.jsonl")):
        agent = os.path.basename(path).replace("agent_", "").replace(".jsonl", "")
        with open(path, "r") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                if rec.get("type") == "intent":
                    intents.append(
                        IntentRecord(
                            t=int(rec.get("t", 0)),
                            agent=agent,
                            intent_type=str(rec.get("intent_type")),
                            side=rec.get("side"),
                            px=rec.get("px"),
                            qty=rec.get("qty"),
                            tokens_req=int(rec.get("tokens_req", 0)),
                            tokens_used=int(rec.get("tokens_used", 0)),
                            tokens_remain=int(rec.get("tokens_remain", 0)),
                            latency_ms=float(rec.get("latency_ms", 0.0)),
                            arrival_t=int(rec.get("arrival_t", 0)),
                            degraded=bool(rec.get("degraded", False)),
                        )
                    )
                elif rec.get("type") == "decision_timing":
                    timings.append(TimingRecord(t=int(rec.get("t", 0)), agent=agent, wall_ms=float(rec.get("wall_ms", 0.0))))
    return intents, timings


def correlate(xs: List[float], ys: List[float]) -> float:
    n = len(xs)
    if n == 0:
        return float("nan")
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    denx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    deny = math.sqrt(sum((y - my) ** 2 for y in ys))
    if denx == 0 or deny == 0:
        return float("nan")
    return num / (denx * deny)


def percentile(values: List[float], p: float) -> float:
    if not values:
        return float("nan")
    s = sorted(values)
    k = (len(s) - 1) * p
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return s[int(k)]
    d0 = s[f] * (c - k)
    d1 = s[c] * (k - f)
    return d0 + d1


def main():
    ap = argparse.ArgumentParser(description="Compute timers vs tokens diagnostics from agent logs")
    ap.add_argument("--run_dir", required=True, help="Path to a single run directory with agent_*.jsonl files")
    ap.add_argument("--out_dir", default="analysis/out", help="Directory to write reports")
    args = ap.parse_args()

    intents, timings = load_agent_logs(args.run_dir)
    if not intents:
        print("No intent records found. Exiting.")
        return
    # index timings by (agent, t)
    tmap: Dict[Tuple[str, int], float] = {(tr.agent, tr.t): tr.wall_ms for tr in timings}

    # pair records: for each intent, lookup timing at same tick
    pairs: List[Tuple[str, int, int, float, float, bool]] = []
    # columns: agent, t, tokens_used, latency_ms, wall_ms, degraded
    for ir in intents:
        wall = tmap.get((ir.agent, ir.t))
        if wall is None:
            continue
        pairs.append((ir.agent, ir.t, ir.tokens_used, ir.latency_ms, wall, ir.degraded))

    os.makedirs(args.out_dir, exist_ok=True)
    csv_path = os.path.join(args.out_dir, "timers_vs_tokens_pairs.csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["agent", "t", "tokens_used", "latency_ms", "wall_ms", "degraded"])
        for row in pairs:
            w.writerow(row)

    tokens = [p[2] for p in pairs]
    lat_ms = [p[3] for p in pairs]
    wall_ms = [p[4] for p in pairs]
    degraded = [p[5] for p in pairs]
    n = len(pairs)
    frac_degraded = sum(1 for d in degraded if d) / n if n else 0.0
    # correlations
    corr_wall_tokens = correlate(tokens, wall_ms)
    corr_wall_latency = correlate(lat_ms, wall_ms)
    # ratios
    ratios = [w / (l if l > 1e-9 else 1e-9) for l, w in zip(lat_ms, wall_ms)]
    abs_diff_pct = [abs(w - l) / (l if l > 1e-9 else 1.0) for l, w in zip(lat_ms, wall_ms)]
    report = {
        "run_dir": args.run_dir,
        "n_pairs": n,
        "frac_degraded": frac_degraded,
        "corr_wall_tokens_used": corr_wall_tokens,
        "corr_wall_vs_assigned_latency": corr_wall_latency,
        "ratio_wall_over_assigned_latency": {
            "p50": percentile(ratios, 0.5),
            "p90": percentile(ratios, 0.9),
            "p95": percentile(ratios, 0.95),
        },
        "abs_diff_over_assigned_latency": {
            "p50": percentile(abs_diff_pct, 0.5),
            "p90": percentile(abs_diff_pct, 0.9),
            "p95": percentile(abs_diff_pct, 0.95),
        },
        "notes": "Assigned latency is a policy-derived proxy; decision wall time measures computation observed in step(). Expect correlation, not equality.",
    }
    with open(os.path.join(args.out_dir, "timers_vs_tokens_report.json"), "w") as f:
        json.dump(report, f, indent=2)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

