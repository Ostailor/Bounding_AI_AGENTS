import json
import os
import tempfile
from sim.market import Market, MarketConfig
from sim.types import Side


def test_trades_jsonl_written():
    m = Market(MarketConfig(tick_size=0.01, fee_per_message=0.0, tick_duration_ms=1.0), ["a", "b"]) 
    with tempfile.TemporaryDirectory() as tmp:
        m.attach_logs(tmp)
        # Create a trade
        m.submit_limit("a", Side.SELL, 100.0, 1)
        m.submit_market("b", Side.BUY, 1)
        path = os.path.join(tmp, "trades.jsonl")
        assert os.path.exists(path)
        with open(path, "r") as f:
            lines = [json.loads(x) for x in f]
        assert any(rec.get("price") == 100.0 for rec in lines)

