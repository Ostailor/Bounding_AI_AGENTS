#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
from typing import Any, Dict, List


def parse_out_dir(stdout: str) -> str:
    m = re.search(r"Logs at:\s*(.+)\s*$", stdout.strip())
    if not m:
        raise RuntimeError("Could not parse log directory from run.py output")
    return m.group(1).strip()


def run_episode(config_path: str, seed: int) -> str:
    cmd = ["python3", "scripts/run.py", "--config", config_path, "--seed", str(seed)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print("-- STDOUT --\n" + res.stdout)
        print("-- STDERR --\n" + res.stderr)
        raise RuntimeError(f"run.py failed: {res.returncode}")
    return parse_out_dir(res.stdout)


def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r") as f:
        return json.load(f)


def dump_json(obj: Dict[str, Any], path: str):
    with open(path, "w") as f:
        json.dump(obj, f, indent=2)


def write_variant(base_cfg: Dict[str, Any], out_dir: str, policy: Dict[str, Any]) -> str:
    cfg = json.loads(json.dumps(base_cfg))
    cfg.update(policy)
    cfg["out_dir"] = out_dir
    os.makedirs(out_dir, exist_ok=True)
    tmp = os.path.join(out_dir, "config.json")
    dump_json(cfg, tmp)
    return tmp


def compute_metrics(run_dir: str) -> Dict[str, float]:
    import sys
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if root not in sys.path:
        sys.path.insert(0, root)
    from analysis.metrics_run import compute_metrics  # type: ignore
    return compute_metrics(run_dir)


def bootstrap_ci(values: List[float], iters: int = 1000, alpha: float = 0.05):
    import random
    if not values:
        return (float('nan'), float('nan'), float('nan'))
    means = []
    n = len(values)
    for _ in range(iters):
        s = [values[random.randrange(n)] for _ in range(n)]
        means.append(sum(s)/n)
    means.sort()
    lo = means[int(alpha/2 * iters)]
    hi = means[int((1-alpha/2) * iters) - 1]
    return (sum(values)/n, lo, hi)


def main():
    ap = argparse.ArgumentParser(description="M6 policy sweeps with deltas vs baseline")
    ap.add_argument("--base_config", required=True)
    ap.add_argument("--seeds", nargs="*", type=int, default=[200,201,202,203,204,205,206,207,208,209])
    ap.add_argument("--out_dir", default="analysis/out/m6_policies")
    args = ap.parse_args()

    base_cfg = load_json(args.base_config)
    os.makedirs(args.out_dir, exist_ok=True)

    policies = [
        ("baseline", {}),
        ("latency_floor", {"latency_floor_ms": 2.0}),
        ("batch_5", {"batch_interval_ticks": 5}),
        ("msg_limit_2", {"message_limit_per_tick": 2}),
        ("min_rest_5", {"min_resting_ticks": 5}),
    ]

    index_rows: List[Dict[str, Any]] = []
    baseline_means: Dict[str, float] = {}

    # Metrics to summarize
    keys = ["mean_agent_pnl", "realized_vol", "mean_spread", "gini_pnl", "msg_to_trade", "alloc_eff_mid", "depth_halflife", "spread_halflife"]

    for name, pol in policies:
        pol_dir = os.path.join(args.out_dir, name)
        cfg_path = write_variant(base_cfg, pol_dir, pol)
        per_seed: Dict[str, List[float]] = {k: [] for k in keys}
        for s in args.seeds:
            run_dir = run_episode(cfg_path, s)
            m = compute_metrics(run_dir)
            for k in keys:
                per_seed[k].append(float(m.get(k)))
        row: Dict[str, Any] = {"policy": name}
        for k in keys:
            mean, lo, hi = bootstrap_ci(per_seed[k])
            row[f"{k}_mean"] = mean
            row[f"{k}_ci_lo"] = lo
            row[f"{k}_ci_hi"] = hi
        index_rows.append(row)
        if name == "baseline":
            baseline_means = {f"{k}_mean": row[f"{k}_mean"] for k in keys}

    # Compute deltas vs baseline
    for row in index_rows:
        if row["policy"] == "baseline":
            continue
        for k in keys:
            base = baseline_means.get(f"{k}_mean")
            if base is None or not (base == base):
                continue
            row[f"d_{k}"] = row[f"{k}_mean"] - base

    # Write CSV with a union of all keys (policy first)
    csv_path = os.path.join(args.out_dir, "index.csv")
    all_keys = set()
    for r in index_rows:
        all_keys.update(r.keys())
    fields = ["policy"] + sorted(k for k in all_keys if k != "policy")
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in index_rows:
            w.writerow(r)
    print(f"Wrote policy aggregates to {csv_path}")


if __name__ == "__main__":
    main()
