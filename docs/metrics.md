# Metrics and Invariants (M1)

Definitions
- Midprice: (best_ask + best_bid)/2 when both sides exist.
- Spread: best_ask - best_bid when both sides exist.
- Depth_k: cumulative volume at top-k levels per side.
- Mark-to-market value v_i = cash_i + inventory_i * price_ref.

Invariants (tested)
- Price–time priority: FIFO within price; best price matched first.
- Conservation: Traded quantity changes buyer/seller inventories by ±qty and cash by ∓price*qty.
- No negative token balances (applies to compute in later milestones; for M1, message fees and cash tracked).
- Tick size: all resting prices align to tick size.

Logging
- steps.jsonl: {t, best_bid, best_ask, mid, spread, last_trade}
- agent_<id>.jsonl: {t, type, side, px?, qty?, ok?}
- run.json: configuration, seed, and environment details.

