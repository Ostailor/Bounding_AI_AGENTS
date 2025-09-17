#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import itertools
import json
import os
import re
import subprocess
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple


def parse_out_dir(stdout: str) -> str:
    m = re.search(r"Logs at:\s*(.+)\s*$", stdout.strip())
    if not m:
        raise RuntimeError("Could not parse log directory from run.py output")
    return m.group(1).strip()


def run_episode(config_path: str, seed: int) -> str:
    cmd = ["python3", "scripts/run.py", "--config", config_path, "--seed", str(seed)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"ERROR: run failed (code={res.returncode}) for seed={seed} config={config_path}")
        if res.stdout:
            print("-- STDOUT --\n" + res.stdout)
        if res.stderr:
            print("-- STDERR --\n" + res.stderr)
        raise RuntimeError(f"run.py failed with code {res.returncode}")
    return parse_out_dir(res.stdout)


def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r") as f:
        return json.load(f)


def dump_json(obj: Dict[str, Any], path: str):
    with open(path, "w") as f:
        json.dump(obj, f, indent=2)


def write_temp_config(base_cfg: Dict[str, Any], variant: Dict[str, Any], tmp_path: str) -> Dict[str, Any]:
    cfg = json.loads(json.dumps(base_cfg))  # deep copy
    # Merge variant fields: currently supports agent param/compute overrides and out_dir suffix
    out_suffix = variant.get("out_suffix", "")
    if out_suffix:
        cfg["out_dir"] = os.path.join(cfg.get("out_dir", "logs/runs"), out_suffix)
    # Agent overrides keyed by 'name'
    overrides: Dict[str, Dict[str, Any]] = variant.get("agent_overrides", {})
    for agent in cfg.get("agents", []):
        name = agent.get("name")
        ov = overrides.get(name)
        if not ov:
            continue
        if "params" in ov:
            agent.setdefault("params", {}).update(ov["params"]) 
        if "compute" in ov:
            agent.setdefault("compute", {}).update(ov["compute"])
    dump_json(cfg, tmp_path)
    return cfg


def summarize_run(out_dir: str) -> Tuple[Dict[str, float], float]:
    summaries = load_json(os.path.join(out_dir, "summary.json")).get("summaries", [])
    pnl_map = {row["agent"]: float(row["pnl"]) for row in summaries}
    # compute avg spread over measure window
    meta = load_json(os.path.join(out_dir, "run.json"))
    warmup = int(meta.get("warmup_steps", 0))
    measure = int(meta.get("measure_steps", 0))
    t_start = warmup + 1
    t_end = warmup + measure
    spreads: List[float] = []
    with open(os.path.join(out_dir, "steps.jsonl"), "r") as f:
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
    return pnl_map, avg_spread


def aggregate(rows: List[Tuple[int, Dict[str, float], float]]) -> Dict[str, Any]:
    # rows: (seed, pnl_map, avg_spread)
    agents = sorted({a for _, pm, _ in rows for a in pm.keys()})
    out: Dict[str, Any] = {"agents": {}, "spread": {}}
    for a in agents:
        vals = [pm.get(a) for _, pm, _ in rows if a in pm]
        n = len(vals)
        mean = sum(vals) / n if n else float("nan")
        var = sum((v - mean) ** 2 for v in vals) / n if n else float("nan")
        out["agents"][a] = {"mean": mean, "std": var ** 0.5, "n": n}
    sp = [s for _, __, s in rows]
    ns = len(sp)
    s_mean = sum(sp) / ns if ns else float("nan")
    s_var = sum((v - s_mean) ** 2 for v in sp) / ns if ns else float("nan")
    out["spread"] = {"mean": s_mean, "std": s_var ** 0.5, "n": ns}
    return out


def main():
    ap = argparse.ArgumentParser(description="Frontier sweep: vary RL params and compute budgets")
    ap.add_argument("--base_config", required=True, help="Path to base config JSON")
    ap.add_argument("--rl_name", default="rl_opt", help="Agent name for RL optimizer in config")
    ap.add_argument("--seeds", nargs="*", type=int, default=[123,124,125,126,127])
    # RL param grids
    ap.add_argument("--epsilons", nargs="*", type=float, default=[0.05, 0.1])
    ap.add_argument("--alphas", nargs="*", type=float, default=[0.02, 0.05])
    ap.add_argument("--inv_penalties", nargs="*", type=float, default=[0.02, 0.05])
    ap.add_argument("--tokens_eval", nargs="*", type=int, default=[2, 4])
    ap.add_argument("--tokens_update", nargs="*", type=int, default=[1])
    # Compute budgets (capacity/refill are the same per tick)
    ap.add_argument("--rl_capacity", nargs="*", type=int, default=[8, 12, 20])
    ap.add_argument("--rl_refill", nargs="*", type=int, default=[8, 12, 20])
    ap.add_argument("--out_dir", default="analysis/out/frontier_sweep", help="Where to save summaries")
    ap.add_argument("--continue_on_error", action="store_true", help="Continue variants on failure")
    args = ap.parse_args()

    base_cfg = load_json(args.base_config)
    os.makedirs(args.out_dir, exist_ok=True)

    # Build variant grid
    grid = list(itertools.product(args.epsilons, args.alphas, args.inv_penalties, args.tokens_eval, args.tokens_update, args.rl_capacity, args.rl_refill))
    results_index: List[Dict[str, Any]] = []

    for (eps, alpha, inv_pen, t_eval, t_upd, cap, ref) in grid:
        variant_key = f"eps{eps}_a{alpha}_inv{inv_pen}_te{t_eval}_tu{t_upd}_cap{cap}_ref{ref}"
        tmp_cfg_path = os.path.join(args.out_dir, f"tmp_{variant_key}.json")
        # prepare overrides for RL agent only
        overrides = {
            args.rl_name: {
                "params": {
                    "epsilon": eps,
                    "alpha": alpha,
                    "inv_penalty": inv_pen,
                    "tokens_per_eval": t_eval,
                    "tokens_per_update": t_upd,
                },
                "compute": {
                    "capacity_tokens": cap,
                    "refill_tokens": ref,
                },
            }
        }
        variant = {"out_suffix": variant_key, "agent_overrides": overrides}
        cfg = write_temp_config(base_cfg, variant, tmp_cfg_path)

        rows: List[Tuple[int, Dict[str, float], float]] = []
        for s in args.seeds:
            try:
                out_dir = run_episode(tmp_cfg_path, s)
            except Exception as e:
                if args.continue_on_error:
                    print(f"WARN: Skipping seed {s} due to error: {e}")
                    continue
                else:
                    raise
            pnl_map, avg_spread = summarize_run(out_dir)
            rows.append((s, pnl_map, avg_spread))

        agg = aggregate(rows)
        # save aggregate summary per variant
        with open(os.path.join(args.out_dir, f"agg_{variant_key}.json"), "w") as f:
            json.dump({
                "variant": variant_key,
                "rl_name": args.rl_name,
                "params": overrides[args.rl_name]["params"],
                "compute": overrides[args.rl_name]["compute"],
                "seeds": args.seeds,
                "aggregate": agg,
            }, f, indent=2)
        # pull baseline agent stats for summary table
        a_agents = agg.get("agents", {})
        mm = a_agents.get("mm_simple", {})
        kg = a_agents.get("k_greedy", {})
        tb = a_agents.get("tau_band", {})
        results_index.append({
            "variant": variant_key,
            "epsilon": eps,
            "alpha": alpha,
            "inv_penalty": inv_pen,
            "tokens_per_eval": t_eval,
            "tokens_per_update": t_upd,
            "capacity_tokens": cap,
            "refill_tokens": ref,
            "rl_mean_pnl": agg["agents"].get(args.rl_name, {}).get("mean"),
            "rl_std_pnl": agg["agents"].get(args.rl_name, {}).get("std"),
            "mm_mean_pnl": mm.get("mean"),
            "kg_mean_pnl": kg.get("mean"),
            "tb_mean_pnl": tb.get("mean"),
            "spread_mean": agg["spread"]["mean"],
        })

    # write index CSV
    csv_path = os.path.join(args.out_dir, "index.csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(results_index[0].keys()))
        w.writeheader()
        for row in results_index:
            w.writerow(row)
    print(f"Wrote {len(results_index)} aggregates to {args.out_dir}. Index: {csv_path}")


if __name__ == "__main__":
    main()
