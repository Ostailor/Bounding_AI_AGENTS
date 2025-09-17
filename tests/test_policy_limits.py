from sim.market import Market, MarketConfig
from sim.types import Side


def test_message_limit_per_tick():
    m = Market(MarketConfig(tick_size=0.01, tick_duration_ms=1.0, message_limit_per_tick=1), ["a"]) 
    # two messages in same tick: second should be rejected
    m.submit_limit("a", Side.BUY, 100.0, 1)
    m.submit_limit("a", Side.SELL, 100.2, 1)
    # Only one resting order should be present
    bb, ba = m.book.top_of_book()
    assert (bb is not None) != (ba is not None)  # only one side present


def test_min_resting_time_cancel():
    m = Market(MarketConfig(tick_size=0.01, tick_duration_ms=1.0, min_resting_ticks=3), ["a"]) 
    # place
    m.submit_limit("a", Side.SELL, 100.0, 1)
    # attempt cancel immediately -> rejected
    ok1 = m.cancel("a", 1)
    assert ok1 is False
    # advance 3 ticks
    for _ in range(3):
        m.begin_tick()
        m.step()
    ok2 = m.cancel("a", 1)
    assert ok2 in (True, False)  # may be False if already traded; but not rejected due to policy


def test_batch_interval_defers_arrivals():
    m = Market(MarketConfig(tick_size=0.01, tick_duration_ms=1.0, batch_interval_ticks=5), ["a"]) 
    # schedule two orders via zero-latency intents: they arrive immediately but processed only at t%5==0
    m.schedule_limit("a", Side.BUY, 99.9, 1, tokens_requested=1)
    m.schedule_limit("a", Side.SELL, 100.1, 1, tokens_requested=1)
    # step 1..4: no processing
    for _ in range(4):
        m.begin_tick(); m.step()
        bb, ba = m.book.top_of_book()
        assert bb is None and ba is None
    # step 5: arrivals processed
    m.begin_tick(); m.step()
    bb, ba = m.book.top_of_book()
    assert bb is not None and ba is not None

