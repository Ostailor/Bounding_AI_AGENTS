from sim.order_book import OrderBook
from sim.types import Order, Side


def mk_order(i, side, price, qty, ts, agent="a"):
    return Order(id=i, agent_id=agent, side=side, price=price, qty=qty, ts=ts, is_market=False)


def test_price_time_priority_basic():
    ob = OrderBook(tick_size=0.01)
    # Two asks at same price, FIFO
    ob.place_limit(mk_order(1, Side.SELL, 100.0, 5, 1, agent="s1"))
    ob.place_limit(mk_order(2, Side.SELL, 100.0, 5, 2, agent="s2"))
    # Buy 7 market: should fill s1 5, s2 2
    trades = ob.place_market(Order(id=3, agent_id="b", side=Side.BUY, price=None, qty=7, ts=3, is_market=True))
    assert len(trades) == 2
    assert trades[0].sell_agent_id == "s1" and trades[0].qty == 5
    assert trades[1].sell_agent_id == "s2" and trades[1].qty == 2


def test_tick_size_enforced():
    ob = OrderBook(tick_size=0.05)
    try:
        ob.place_limit(mk_order(1, Side.BUY, 100.03, 1, 1))
        assert False, "Expected tick size violation"
    except ValueError:
        pass

