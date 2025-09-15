#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import random
import sys
from datetime import datetime, UTC
from pathlib import Path
from typing import Any, Dict, List

# Ensure repo root on path for local package imports when run as a script
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover - optional
    yaml = None

from agents.base import AgentContext
from agents.market_maker_simple import MarketMakerSimple
from agents.zero_intelligence import ZITrader
from sim.market import Market, MarketConfig
from sim.types import Side


def load_config(path: str) -> Dict[str, Any]:
    with open(path, "r") as f:
        text = f.read()
    if path.endswith(".json"):
        return json.loads(text)
    if path.endswith(".yaml") or path.endswith(".yml"):
        if yaml is None:
            print("PyYAML not installed. Install pyyaml or use JSON config.", file=sys.stderr)
            sys.exit(2)
        return yaml.safe_load(text)
    raise ValueError("Unsupported config format; use .json or .yaml")


def build_agents(cfg_agents: List[Dict[str, Any]], seed: int):
    agents = []
    for spec in cfg_agents:
        name = spec["name"]
        cls = spec["class"]
        rng = random.Random(seed + hash(name) % 100000)
        ctx = AgentContext(rng=rng)
        if cls == "MarketMakerSimple":
            agent = MarketMakerSimple(name, ctx, **spec.get("params", {}))
        elif cls == "ZITrader":
            agent = ZITrader(name, ctx, **spec.get("params", {}))
        else:
            raise ValueError(f"Unknown agent class: {cls}")
        agents.append(agent)
    return agents


def main():
    ap = argparse.ArgumentParser(description="Run minimal CDA/LOB simulation episode")
    ap.add_argument("--config", required=True)
    ap.add_argument("--seed", type=int, default=123)
    args = ap.parse_args()

    cfg = load_config(args.config)
    seed = int(cfg.get("seed", args.seed))
    rng = random.Random(seed)
    warmup = int(cfg.get("warmup_steps", 1000))
    measure = int(cfg.get("measure_steps", 2000))
    tick = float(cfg.get("tick_size", 0.01))
    fee_msg = float(cfg.get("fee_per_message", 0.0))
    fee_share = float(cfg.get("fee_per_share", 0.0))

    agents = build_agents(cfg.get("agents", []), seed)
    agent_ids = [a.id for a in agents]
    market = Market(MarketConfig(tick_size=tick, fee_per_message=fee_msg, fee_per_share=fee_share), agent_ids)

    # Logs directory
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_base = cfg.get("out_dir", "logs/runs")
    # Always write to a per-run timestamped folder to avoid appending
    out_dir = os.path.join(out_base, ts)
    os.makedirs(out_dir, exist_ok=True)
    # Minimal run metadata
    meta = {
        "seed": seed,
        "config_path": os.path.abspath(args.config),
        "tick_size": tick,
        "fee_per_message": fee_msg,
        "fee_per_share": fee_share,
        "warmup_steps": warmup,
        "measure_steps": measure,
        "agents": [spec for spec in cfg.get("agents", [])],
        "datetime_utc": ts,
    }
    with open(os.path.join(out_dir, "run.json"), "w") as f:
        json.dump(meta, f, indent=2)

    market.attach_logs(out_dir)

    # Warmup and measure loops
    for a in agents:
        a.on_start(market)
    total_steps = warmup + measure
    for t in range(total_steps):
        # Each agent acts once per tick in fixed order for determinism
        for a in agents:
            a.step(market)
        market.step()

    # Episode summaries (PnL per agent)
    summaries = []
    for aid in agent_ids:
        pnl = market.mark_to_market(aid)
        summaries.append({"agent": aid, "pnl": pnl, "cash": market.agents[aid].cash, "inv": market.agents[aid].inventory})
    with open(os.path.join(out_dir, "summary.json"), "w") as f:
        json.dump({"summaries": summaries}, f, indent=2)

    market.close_logs()
    print(f"Completed run. Logs at: {out_dir}")


if __name__ == "__main__":
    main()
