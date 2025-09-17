# ShallowRLTrader — Model Card

Summary
- Linear contextual bandit over a small action set with online updates.

Policy
- Actions: hold, limit buy/sell; optional market buy/sell.
- Q(s,a) = w_a · φ(s) with features [1, inv, inv^2, spread, depth imbalance].
- Epsilon-greedy selection; bandit-style update on ΔPnL with inventory/message penalties.

Compute/Latency
- Tokens per decision ≈ `tokens_per_eval * |actions| + tokens_per_update`.
- Adjust capacity/refill tokens to control compute budget per tick.

Determinism
- Controlled via per-agent RNG seeds; CPU-only. No CUDA used.

Safety
- No background threads; compute counted via schedule_* tokens.

Known Limitations
- Myopic reward; does not model order execution risk or long-horizon dynamics.
- Linear approximator may underfit complex microstructure signals.
