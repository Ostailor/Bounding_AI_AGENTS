#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from typing import Any, Dict, Optional


def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r") as f:
        return json.load(f)


def choose_best(summary: Dict[str, Any]) -> Dict[str, Any]:
    tops = summary.get("top_variants", [])
    if not tops:
        raise RuntimeError("No top_variants in summary.")
    # Choose highest rl_mean_pnl; tie-break on lower capacity_tokens, then lower epsilon
    def key(rec: Dict[str, Any]):
        return (
            float(rec.get("rl_mean_pnl", float("-inf"))),
            -float(rec.get("capacity_tokens", float("inf"))),  # reversed for min capacity
            -float(rec.get("epsilon", float("inf")))  # reversed for min epsilon
        )
    best = max(tops, key=key)
    return best


def update_json_config(cfg_path: str, rl_name: str, best: Dict[str, Any]):
    cfg = load_json(cfg_path)
    for agent in cfg.get("agents", []):
        if agent.get("name") == rl_name:
            params = agent.setdefault("params", {})
            params["epsilon"] = float(best.get("epsilon"))
            params["alpha"] = float(best.get("alpha"))
            params["inv_penalty"] = float(best.get("inv_penalty"))
            params["tokens_per_eval"] = int(best.get("tokens_per_eval"))
            params["tokens_per_update"] = int(best.get("tokens_per_update"))
            # keep include_market as-is
            comp = agent.setdefault("compute", {})
            comp["capacity_tokens"] = int(best.get("capacity_tokens"))
            comp["refill_tokens"] = int(best.get("refill_tokens"))
            break
    with open(cfg_path, "w") as f:
        json.dump(cfg, f, indent=2)


def update_yaml_config(cfg_path: str, rl_name: str, best: Dict[str, Any]):
    try:
        import yaml  # type: ignore
    except Exception:
        print("PyYAML not installed; skipping YAML config update.")
        return
    with open(cfg_path, "r") as f:
        cfg = yaml.safe_load(f)
    for agent in cfg.get("agents", []):
        if agent.get("name") == rl_name:
            params = agent.setdefault("params", {})
            params["epsilon"] = float(best.get("epsilon"))
            params["alpha"] = float(best.get("alpha"))
            params["inv_penalty"] = float(best.get("inv_penalty"))
            params["tokens_per_eval"] = int(best.get("tokens_per_eval"))
            params["tokens_per_update"] = int(best.get("tokens_per_update"))
            comp = agent.setdefault("compute", {})
            comp["capacity_tokens"] = int(best.get("capacity_tokens"))
            comp["refill_tokens"] = int(best.get("refill_tokens"))
            break
    with open(cfg_path, "w") as f:
        yaml.safe_dump(cfg, f, sort_keys=False)


def main():
    ap = argparse.ArgumentParser(description="Update m3_agents.* with best RL params from frontier summary")
    ap.add_argument("--summary", required=True, help="Path to frontier_summary.json")
    ap.add_argument("--json", required=True, help="Path to m3_agents.json")
    ap.add_argument("--yaml", required=False, help="Path to m3_agents.yaml")
    ap.add_argument("--rl_name", default="rl_opt")
    args = ap.parse_args()

    summary = load_json(args.summary)
    best = choose_best(summary)
    update_json_config(args.json, args.rl_name, best)
    if args.yaml:
        update_yaml_config(args.yaml, args.rl_name, best)
    print("Updated configs with best RL params:")
    print(json.dumps(best, indent=2))


if __name__ == "__main__":
    main()

