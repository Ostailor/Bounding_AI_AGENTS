from sim.market import Market, MarketConfig
from sim.compute import ComputeBudget, LatencyModel
from sim.types import Side


def test_token_bucket_never_negative_and_degrade():
    m = Market(MarketConfig(tick_size=0.01, tick_duration_ms=1.0), ["a"], rng=None)
    m.set_agent_compute("a", ComputeBudget(capacity_tokens=1, refill_tokens=1), LatencyModel(base_ms=0.0, ms_per_token=1.0))
    # request more tokens than available → degrade, tokens stay at 1 until consumed/refill
    before = m._compute["a"].tokens
    m.schedule_limit("a", Side.BUY, 100.0, 1, tokens_requested=2)
    after = m._compute["a"].tokens
    assert before == after == 1


def test_latency_queue_ordering():
    m = Market(MarketConfig(tick_size=0.01, tick_duration_ms=1.0), ["a", "b"], rng=None)
    m.set_agent_compute("a", ComputeBudget(capacity_tokens=10, refill_tokens=10), LatencyModel(base_ms=0.0, ms_per_token=1.0))
    m.set_agent_compute("b", ComputeBudget(capacity_tokens=10, refill_tokens=10), LatencyModel(base_ms=0.0, ms_per_token=3.0))
    # At t=0 schedule two buy orders at different latencies
    m.begin_tick()
    m.schedule_limit("a", Side.BUY, 100.0, 1, tokens_requested=1)  # arrival t=1
    m.schedule_limit("b", Side.BUY, 99.0, 1, tokens_requested=1)   # arrival t=3
    # Step to t=1: only agent a order should be present as best bid 100.0
    m.step()  # t=1
    bb, ba = m.book.top_of_book()
    assert bb == 100.0
    # Step to t=3: b's order should now arrive, best bid should remain 100.0 (since it's higher)
    m.step()  # t=2
    m.step()  # t=3
    bb2, _ = m.book.top_of_book()
    assert bb2 == 100.0

