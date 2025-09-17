# Overview

This repository implements a minimal Continuous Double Auction (CDA) / Limit Order Book (LOB) simulator to study compute–profit–stability trade-offs. Milestone M1 focuses on correctness, determinism, and basic logging.

- Engine: Custom minimal CDA with price–time priority. Rationale: small, auditable core tailored to compute accounting; external engines (e.g., ABIDES) can be integrated later.
- Orders: Limit, market, and cancel (cancel added at book level).
- Frictions: Tick size, per-message fee, and taker fee per share.
- Determinism: Fixed agent iteration order and PRNG seeds per agent.
- Logging: JSONL step and per-agent action logs; run metadata as JSON.

See docs/metrics.md for metric formulas and invariants.

## Compute Model (M2)

- Units: eval tokens per decision; configurable per agent via capacity and refill per tick.
- Enforcement: token bucket per agent; if a decision requests more tokens than available, the action is degraded (held) and logged.
- Latency: completion time = start tick + ceil((base_ms + ms_per_token * tokens_used + jitter)/tick_duration_ms).
- Queue: a global latency queue orders arrivals by completion time and a sequence number for ties; orders execute upon arrival.
- Instrumentation: each scheduled intent logs tokens requested/used, remaining tokens, assigned latency (ms), and arrival tick.

## M3 Agents and Analysis

- Model cards document behavior and compute for each agent:
  - `docs/model_cards/TauBandTrader.md`
  - `docs/model_cards/KGreedyTrader.md`
  - `docs/model_cards/ShallowRLTrader.md`
- Running and tuning sweeps:
  - `scripts/sweep_frontier.py` varies ShallowRLTrader hyperparameters and compute budgets across seeds.
  - `analysis/learning_curve.py` aggregates per-tick PnL to produce learning curves.
- `analysis/plot_pnl_spread.py` plots RL PnL vs capacity and spread time series (requires matplotlib).
 
## M4 Frontiers and Stability

- Metrics per run (analysis/metrics_run.py): realized volatility (log-returns), kurtosis, crash probability, mean spread, message-to-trade, PnL Gini, and mean agent PnL.
- Sweeps (scripts/sweep_m4.py): vary RL compute (capacity/refill) and optimizer share across seeds; writes per-variant aggregates with bootstrap CIs.
- Pareto (analysis/pareto_multi.py): multi-metric undominated set over profit (maximize) and stability/liquidity (minimize spread/vol).
- Change-points (analysis/change_point.py): segmented regression to estimate break in stability vs compute for a fixed optimizer share.
 - Camera-ready plots: analysis/export_figures_m4.py applies consistent styling and exports PNG/PDF figures.

## M6 Policy Interventions

- Policies in simulator (MarketConfig):
  - latency_floor_ms: imposes a minimum decision latency for all intents.
  - batch_interval_ticks: processes arrivals only every K ticks (RBA-style batching) to reduce latency races.
  - message_limit_per_tick: per-agent cap on submissions per tick (subsequent messages are rejected and logged).
  - min_resting_ticks: enforce minimum resting time before cancels are accepted.
- Sweeps and deltas: scripts/sweep_m6_policies.py runs matched seeds vs baseline and reports deltas in profit, volatility, spread, fairness, and resilience.
