#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import itertools
import json
import math
import os
import re
import subprocess
from typing import Any, Dict, List, Tuple


def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r") as f:
        return json.load(f)


def dump_json(obj: Dict[str, Any], path: str):
    with open(path, "w") as f:
        json.dump(obj, f, indent=2)


def parse_out_dir(stdout: str) -> str:
    m = re.search(r"Logs at:\s*(.+)\s*$", stdout.strip())
    if not m:
        raise RuntimeError("Could not parse log directory from run.py output")
    return m.group(1).strip()


def run_episode(config_path: str, seed: int) -> str:
    cmd = ["python3", "scripts/run.py", "--config", config_path, "--seed", str(seed)]
    res = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return parse_out_dir(res.stdout)


def write_variant_cfg(base_cfg: Dict[str, Any], out_dir: str, rl_capacity: int, rl_refill: int, optimizer_share: float, total_agents: int) -> str:
    cfg = json.loads(json.dumps(base_cfg))
    # update RL compute
    for a in cfg.get("agents", []):
        if a.get("class") == "ShallowRLTrader":
            comp = a.setdefault("compute", {})
            comp["capacity_tokens"] = int(rl_capacity)
            comp["refill_tokens"] = int(rl_refill)
    # population mix: set counts
    rl_count = max(0, min(total_agents, int(round(optimizer_share * total_agents))))
    rem = total_agents - rl_count
    # distribute remainder among non-RL agents proportionally to current counts
    non_rl = [a for a in cfg.get("agents", []) if a.get("class") != "ShallowRLTrader"]
    base_counts = [int(a.get("count", 1)) for a in non_rl]
    base_total = sum(base_counts) if base_counts else 1
    for a, bc in zip(non_rl, base_counts):
        a["count"] = max(0, int(round(rem * (bc / base_total))))
    # set RL count
    for a in cfg.get("agents", []):
        if a.get("class") == "ShallowRLTrader":
            a["count"] = rl_count
    # ensure at least 1 non-RL
    if rl_count == total_agents and non_rl:
        non_rl[0]["count"] = 1
        for a in cfg.get("agents", []):
            if a.get("class") == "ShallowRLTrader":
                a["count"] = total_agents - 1
                break
    cfg["out_dir"] = out_dir
    tmp_path = os.path.join(out_dir, "tmp_config.json")
    os.makedirs(out_dir, exist_ok=True)
    dump_json(cfg, tmp_path)
    return tmp_path


def bootstrap_ci(values: List[float], iters: int = 1000, alpha: float = 0.05) -> Tuple[float, float, float]:
    if not values:
        return (float('nan'), float('nan'), float('nan'))
    import random
    n = len(values)
    means: List[float] = []
    for _ in range(iters):
        sample = [values[random.randrange(n)] for _ in range(n)]
        means.append(sum(sample)/n)
    means.sort()
    lo = means[int((alpha/2) * iters)]
    hi = means[int((1 - alpha/2) * iters) - 1]
    return (sum(values)/n, lo, hi)


def main():
    ap = argparse.ArgumentParser(description="M4 sweeps: compute budgets and optimizer share, with stability/fairness metrics")
    ap.add_argument("--base_config", required=True)
    ap.add_argument("--seeds", nargs="*", type=int, default=[123,124,125,126,127,128,129,130,131,132])
    ap.add_argument("--rl_capacity", nargs="*", type=int, default=[4, 8, 12, 20])
    ap.add_argument("--rl_refill", nargs="*", type=int, default=[4, 8, 12, 20])
    ap.add_argument("--optimizer_share", nargs="*", type=float, default=[0.0, 0.2, 0.5, 0.8, 1.0])
    ap.add_argument("--total_agents", type=int, default=20)
    ap.add_argument("--out_dir", default="analysis/out/m4_frontier")
    args = ap.parse_args()

    base_cfg = load_json(args.base_config)
    os.makedirs(args.out_dir, exist_ok=True)

    grid = list(itertools.product(args.rl_capacity, args.rl_refill, args.optimizer_share))
    index_rows: List[Dict[str, Any]] = []

    for cap, ref, share in grid:
        variant_dir = os.path.join(args.out_dir, f"cap{cap}_ref{ref}_share{share}")
        cfg_path = write_variant_cfg(base_cfg, variant_dir, cap, ref, share, args.total_agents)
        # Collect metrics per seed
        per_seed_metrics: Dict[str, List[float]] = {k: [] for k in [
            "mean_agent_pnl",
            "realized_vol",
            "kurtosis",
            "crash_prob",
            "mean_spread",
            "msg_to_trade",
            "gini_pnl",
            "alloc_eff_mid",
            "spread_halflife",
            "alloc_eff_call",
            "depth_halflife",
        ]}
        for s in args.seeds:
            run_dir = run_episode(cfg_path, s)
            # compute metrics for run_dir by importing via path
            import importlib.util, sys
            root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if root not in sys.path:
                sys.path.insert(0, root)
            from analysis.metrics_run import compute_metrics  # type: ignore
            m = compute_metrics(run_dir)
            for k in per_seed_metrics.keys():
                per_seed_metrics[k].append(float(m.get(k)))
        # Aggregate with bootstrap CIs
        row: Dict[str, Any] = {"capacity_tokens": cap, "refill_tokens": ref, "optimizer_share": share}
        for k, vals in per_seed_metrics.items():
            mean, lo, hi = bootstrap_ci(vals)
            row[f"{k}_mean"] = mean
            row[f"{k}_ci_lo"] = lo
            row[f"{k}_ci_hi"] = hi
        index_rows.append(row)
        # Save per-variant aggregate
        with open(os.path.join(variant_dir, "aggregate.json"), "w") as f:
            json.dump(row, f, indent=2)

    # Write index CSV
    csv_path = os.path.join(args.out_dir, "index.csv")
    fields = list(index_rows[0].keys()) if index_rows else []
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in index_rows:
            w.writerow(row)
    print(f"Wrote {len(index_rows)} M4 aggregates to {csv_path}")


if __name__ == "__main__":
    main()
