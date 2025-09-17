# TauBandTrader — Model Card

Summary
- Satisficer threshold-band policy: acts only when |mid − ref| > τ.

Policy
- Action: buy if mid < ref − τ; sell if mid > ref + τ.
- Order type: limit-at-best by default; optional market if deviation is large.
- Inventory guardrails: only act to reduce inventory when beyond ±inv_limit.

Compute/Latency
- Tokens per decision: `tokens_per_decision` (default 1).
- Latency = base_ms + tokens_used * ms_per_token (sim config).

Safety
- No background threads; all compute counts via schedule_* tokens.

Known Limitations
- Fixed τ and reference can be suboptimal under regime shifts.
- Limit-only behavior may stall if book is empty.
