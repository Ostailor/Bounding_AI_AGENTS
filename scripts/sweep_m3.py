#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple


@dataclass
class RunSummary:
    seed: int
    out_dir: str
    agent_pnls: Dict[str, float]
    avg_spread: float
    p50_spread: float
    p95_spread: float


def parse_out_dir(stdout: str) -> str:
    m = re.search(r"Logs at:\s*(.+)\s*$", stdout.strip())
    if not m:
        raise RuntimeError("Could not parse log directory from run.py output")
    return m.group(1).strip()


def run_episode(config_path: str, seed: int) -> str:
    cmd = ["python3", "scripts/run.py", "--config", config_path, "--seed", str(seed)]
    res = subprocess.run(cmd, check=True, capture_output=True, text=True)
    out_dir = parse_out_dir(res.stdout)
    return out_dir


def percentile(values: List[float], p: float) -> float:
    if not values:
        return float("nan")
    s = sorted(values)
    k = (len(s) - 1) * p
    f = int(k)
    c = min(len(s) - 1, f + 1)
    if f == c:
        return s[f]
    return s[f] * (c - k) + s[c] * (k - f)


def summarize_run(out_dir: str) -> RunSummary:
    # read run metadata
    meta_path = os.path.join(out_dir, "run.json")
    with open(meta_path, "r") as f:
        meta = json.load(f)
    seed = int(meta.get("seed", 0))
    warmup = int(meta.get("warmup_steps", 0))
    measure = int(meta.get("measure_steps", 0))
    t_start = warmup + 1
    t_end = warmup + measure

    # PnL per agent
    summ_path = os.path.join(out_dir, "summary.json")
    with open(summ_path, "r") as f:
        summ = json.load(f)
    agent_pnls = {row["agent"]: float(row["pnl"]) for row in summ.get("summaries", [])}

    # Spreads across measure window
    spreads: List[float] = []
    steps_path = os.path.join(out_dir, "steps.jsonl")
    with open(steps_path, "r") as f:
        for line in f:
            try:
                rec = json.loads(line)
            except Exception:
                continue
            t = int(rec.get("t", 0))
            if t < t_start or t > t_end:
                continue
            sp = rec.get("spread")
            if sp is not None:
                spreads.append(float(sp))
    avg_spread = sum(spreads) / len(spreads) if spreads else float("nan")
    p50 = percentile(spreads, 0.5)
    p95 = percentile(spreads, 0.95)

    return RunSummary(seed=seed, out_dir=out_dir, agent_pnls=agent_pnls, avg_spread=avg_spread, p50_spread=p50, p95_spread=p95)


def aggregate(results: List[RunSummary]) -> Dict[str, any]:
    # Agent PnL mean/std
    agents = sorted({a for r in results for a in r.agent_pnls.keys()})
    agent_stats: Dict[str, Dict[str, float]] = {}
    for a in agents:
        vals = [r.agent_pnls.get(a, float("nan")) for r in results]
        vals = [v for v in vals if not (v != v)]  # filter NaN
        n = len(vals)
        mean = sum(vals) / n if n else float("nan")
        var = sum((v - mean) ** 2 for v in vals) / n if n else float("nan")
        std = var ** 0.5 if n else float("nan")
        agent_stats[a] = {"mean": mean, "std": std, "n": n}

    spreads = [r.avg_spread for r in results]
    spreads = [v for v in spreads if not (v != v)]
    ns = len(spreads)
    s_mean = sum(spreads) / ns if ns else float("nan")
    s_var = sum((v - s_mean) ** 2 for v in spreads) / ns if ns else float("nan")
    s_std = s_var ** 0.5 if ns else float("nan")
    return {"agent_pnl": agent_stats, "spread": {"mean": s_mean, "std": s_std, "n": ns}}


def main():
    ap = argparse.ArgumentParser(description="Run small M3 sweep and summarize PnL and spreads")
    ap.add_argument("--config", required=True, help="Path to config JSON/YAML")
    ap.add_argument("--seeds", nargs="*", type=int, default=[123, 124, 125])
    ap.add_argument("--out_dir", default="analysis/out", help="Directory for summary outputs")
    args = ap.parse_args()

    results: List[RunSummary] = []
    for s in args.seeds:
        out_dir = run_episode(args.config, s)
        rs = summarize_run(out_dir)
        results.append(rs)

    agg = aggregate(results)
    os.makedirs(args.out_dir, exist_ok=True)
    # Save JSON
    with open(os.path.join(args.out_dir, "m3_sweep_summary.json"), "w") as f:
        json.dump({
            "config": os.path.abspath(args.config),
            "seeds": args.seeds,
            "runs": [r.__dict__ for r in results],
            "aggregate": agg,
        }, f, indent=2)
    # Save CSV for quick viewing
    csv_path = os.path.join(args.out_dir, "m3_sweep_pnl.csv")
    agents = sorted({a for r in results for a in r.agent_pnls})
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["seed", *agents, "avg_spread", "p50_spread", "p95_spread"])
        for r in results:
            row = [r.seed] + [r.agent_pnls.get(a, "") for a in agents] + [r.avg_spread, r.p50_spread, r.p95_spread]
            w.writerow(row)
    print(json.dumps(agg, indent=2))


if __name__ == "__main__":
    main()

