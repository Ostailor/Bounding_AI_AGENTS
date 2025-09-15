# Overview

This repository implements a minimal Continuous Double Auction (CDA) / Limit Order Book (LOB) simulator to study compute–profit–stability trade-offs. Milestone M1 focuses on correctness, determinism, and basic logging.

- Engine: Custom minimal CDA with price–time priority. Rationale: small, auditable core tailored to compute accounting; external engines (e.g., ABIDES) can be integrated later.
- Orders: Limit, market, and cancel (cancel added at book level).
- Frictions: Tick size, per-message fee, and taker fee per share.
- Determinism: Fixed agent iteration order and PRNG seeds per agent.
- Logging: JSONL step and per-agent action logs; run metadata as JSON.

See docs/metrics.md for metric formulas and invariants.

