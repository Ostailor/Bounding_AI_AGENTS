from sim.market import Market, MarketConfig
from sim.types import Side


def test_conservation_and_pnl():
    m = Market(MarketConfig(tick_size=0.01, fee_per_message=0.0, fee_per_share=0.0), ["a", "b"])
    # a places ask, b buys
    m.submit_limit("a", Side.SELL, 100.0, 3)
    trades = m.submit_market("b", Side.BUY, 2)
    assert trades and sum(t.qty for t in trades) == 2
    # inventories
    assert m.agents["a"].inventory == -2
    assert m.agents["b"].inventory == 2
    # cash
    assert abs(m.agents["a"].cash - 200.0) < 1e-9
    assert abs(m.agents["b"].cash + 200.0) < 1e-9
    # mark-to-market at 100
    assert abs(m.mark_to_market("a", 100.0) - 0.0) < 1e-9
    assert abs(m.mark_to_market("b", 100.0) - 0.0) < 1e-9

