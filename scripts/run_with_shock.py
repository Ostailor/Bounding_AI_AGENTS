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

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import yaml  # type: ignore
except Exception:
    yaml = None

from agents.base import AgentContext
from agents.market_maker_simple import MarketMakerSimple
from agents.zero_intelligence import ZITrader
from agents.satisficer_band import TauBandTrader
from agents.satisficer_k_greedy import KGreedyTrader
from agents.optimizer_shallow_rl import ShallowRLTrader
from sim.market import Market, MarketConfig
from sim.types import Side
from sim.compute import ComputeBudget, LatencyModel


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
        base_name = spec["name"]
        cls = spec["class"]
        count = int(spec.get("count", 1))
        for i in range(count):
            name = base_name if count == 1 else f"{base_name}_{i+1}"
            rng = random.Random(seed + hash(name) % 100000)
            ctx = AgentContext(rng=rng)
            if cls == "MarketMakerSimple":
                agent = MarketMakerSimple(name, ctx, **spec.get("params", {}))
            elif cls == "ZITrader":
                agent = ZITrader(name, ctx, **spec.get("params", {}))
            elif cls == "TauBandTrader":
                agent = TauBandTrader(name, ctx, **spec.get("params", {}))
            elif cls == "KGreedyTrader":
                agent = KGreedyTrader(name, ctx, **spec.get("params", {}))
            elif cls == "ShallowRLTrader":
                agent = ShallowRLTrader(name, ctx, **spec.get("params", {}))
            else:
                raise ValueError(f"Unknown agent class: {cls}")
            agents.append(agent)
    return agents


def main():
    ap = argparse.ArgumentParser(description="Run sim with an explicit shock (large market order)")
    ap.add_argument("--config", required=True)
    ap.add_argument("--seed", type=int, default=123)
    ap.add_argument("--shock_t", type=int, default=600, help="Tick to inject shock (absolute tick in episode)")
    ap.add_argument("--shock_side", choices=["BUY", "SELL"], default="BUY")
    ap.add_argument("--shock_qty", type=int, default=50)
    args = ap.parse_args()

    cfg = load_config(args.config)
    seed = int(cfg.get("seed", args.seed))
    warmup = int(cfg.get("warmup_steps", 1000))
    measure = int(cfg.get("measure_steps", 2000))
    tick = float(cfg.get("tick_size", 0.01))
    fee_msg = float(cfg.get("fee_per_message", 0.0))
    fee_share = float(cfg.get("fee_per_share", 0.0))

    agent_specs = cfg.get("agents", [])
    agents = build_agents(agent_specs, seed)
    # Add shock agent id to market state for accounting
    agent_ids = [a.id for a in agents] + ["shock"]
    market = Market(MarketConfig(tick_size=tick, fee_per_message=fee_msg, fee_per_share=fee_share, tick_duration_ms=float(cfg.get("tick_duration_ms", 1.0))), agent_ids)

    # Logs directory
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    out_base = cfg.get("out_dir", "logs/runs")
    out_dir = os.path.join(out_base, f"{ts}_seed{seed}")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "run.json"), "w") as f:
        json.dump({**cfg, "shock": {"t": args.shock_t, "side": args.shock_side, "qty": args.shock_qty}, "datetime_utc": ts}, f, indent=2)

    market.attach_logs(out_dir)
    # Configure compute/latency per agent
    for spec in agent_specs:
        base_name = spec["name"]
        count = int(spec.get("count", 1))
        comp = spec.get("compute", {})
        budget = ComputeBudget(capacity_tokens=int(comp.get("capacity_tokens", 10)), refill_tokens=int(comp.get("refill_tokens", 10)))
        lat = LatencyModel(base_ms=float(comp.get("base_latency_ms", 0.5)), ms_per_token=float(comp.get("latency_ms_per_token", 0.2)), jitter_ms=float(comp.get("jitter_ms", 0.0)))
        if count == 1:
            market.set_agent_compute(base_name, budget, lat)
        else:
            for i in range(count):
                name = f"{base_name}_{i+1}"
                market.set_agent_compute(name, budget, lat)
    # Shock agent fast/no compute
    market.set_agent_compute("shock", ComputeBudget(capacity_tokens=1_000_000, refill_tokens=1_000_000), LatencyModel(base_ms=0.0, ms_per_token=0.0))

    for a in agents:
        a.on_start(market)
    total_steps = warmup + measure
    shock_side = Side[args.shock_side]
    for _ in range(total_steps):
        market.begin_tick()
        for a in agents:
            a.step(market)
        # Inject shock at chosen tick (absolute)
        if market.t + 1 == args.shock_t:
            market.schedule_market("shock", shock_side, int(args.shock_qty), tokens_requested=1)
        market.step()
        # PnL logs
        for aid in agent_ids:
            market.log_pnl(aid, market.mark_to_market(aid))

    # Summaries
    summaries = []
    for aid in agent_ids:
        pnl = market.mark_to_market(aid)
        summaries.append({"agent": aid, "pnl": pnl, "cash": market.agents[aid].cash, "inv": market.agents[aid].inventory})
    with open(os.path.join(out_dir, "summary.json"), "w") as f:
        json.dump({"summaries": summaries}, f, indent=2)
    market.close_logs()
    print(f"Completed shock run. Logs at: {out_dir}")


if __name__ == "__main__":
    main()
