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
