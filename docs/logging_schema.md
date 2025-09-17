# Logging Schema

## steps.jsonl
- One JSON object per tick with fields:
  - `t`: integer tick
  - `best_bid`, `best_ask`: floats or null
  - `mid`, `spread`: floats or null
  - `depth1_bid`, `depth1_ask`, `depth5_bid`, `depth5_ask`: integers (volume)
  - `last_trade`: float or null
  - `num_trades`, `trade_volume`, `num_messages`: integers per tick

## agent_<id>.jsonl
- One JSON object per agent event/record:
  - `type`: one of `intent`, `limit`, `market`, `cancel`, `reject`, `decision_timing`, `pnl`
  - For `intent`: `intent_type`, `side`, `px?`, `qty?`, `tokens_req`, `tokens_used`, `tokens_remain`, `latency_ms`, `arrival_t`, `degraded`
  - For `reject`: `reason` in {`message_limit`, `min_resting_time`} and context.
  - For orders/executions: `side`, `px?`, `qty?` or `order_id`.
  - For timing: `wall_ms`; for PnL: `pnl`.

## trades.jsonl
- One JSON object per executed fill:
  - `t`: integer tick
  - `price`: float
  - `qty`: integer
  - `buy_agent`, `sell_agent`: ids
  - `taker_agent`: id of initiating side
  - `taker_side`: "BUY" or "SELL"

