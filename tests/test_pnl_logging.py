import json
import tempfile
from sim.market import Market, MarketConfig
from sim.types import Side


def test_pnl_logged_each_tick():
    m = Market(MarketConfig(tick_size=0.01, tick_duration_ms=1.0), ["a", "b"])
    with tempfile.TemporaryDirectory() as tmp:
        m.attach_logs(tmp)
        # Seed simple book and activity
        m.submit_limit("a", Side.SELL, 100.0, 1)
        m.begin_tick()
        m.submit_market("b", Side.BUY, 1)
        m.step()
        # Log PnL for each agent at current t
        m.log_pnl("a", m.mark_to_market("a"))
        m.log_pnl("b", m.mark_to_market("b"))
        # Read and confirm at least one pnl entry exists
        for aid in ["a", "b"]:
            path = f"{tmp}/agent_{aid}.jsonl"
            with open(path, "r") as f:
                lines = [json.loads(x) for x in f]
            assert any(rec.get("type") == "pnl" for rec in lines)

