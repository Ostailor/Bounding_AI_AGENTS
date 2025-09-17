from sim.market import Market, MarketConfig
from sim.types import Side


def test_step_counters_messages_and_trades():
    m = Market(MarketConfig(tick_size=0.01, fee_per_message=0.0, tick_duration_ms=1.0), ["a", "b"]) 
    # Schedule arrivals without compute budgets (immediate arrival)
    m.schedule_limit("a", Side.SELL, 100.0, 1, tokens_requested=1)
    m.schedule_market("b", Side.BUY, 1, tokens_requested=1)
    payload = m.step()  # process both arrivals this tick
    assert payload["num_messages"] >= 2  # one limit + one market
    assert payload["num_trades"] >= 1
    assert payload["trade_volume"] >= 1

