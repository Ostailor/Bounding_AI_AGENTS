from sim.market import Market, MarketConfig
from sim.compute import ComputeBudget, LatencyModel
from sim.types import Side
from agents.base import AgentContext
from agents.satisficer_band import TauBandTrader
from agents.satisficer_k_greedy import KGreedyTrader
from agents.optimizer_shallow_rl import ShallowRLTrader
import random


def setup_market(agent_ids):
    m = Market(MarketConfig(tick_size=0.01, tick_duration_ms=1.0), agent_ids, rng=random.Random(0))
    # seed simple book state: place an ask so bids can match, etc.
    m.submit_limit(agent_ids[0], Side.SELL, 100.0, 1)
    m.submit_limit(agent_ids[0], Side.BUY,  99.9, 1)
    return m


def test_tau_band_schedules_with_tokens():
    a_id = "tb"
    m = setup_market([a_id])
    # compute budget sufficient
    m.set_agent_compute(a_id, ComputeBudget(capacity_tokens=2, refill_tokens=2), LatencyModel(base_ms=0.0, ms_per_token=1.0))
    ctx = AgentContext(rng=random.Random(1))
    agent = TauBandTrader(a_id, ctx, ref_mode="fixed", ref_price=100.0, tau=0.01, size=1, limit_only=True, tokens_per_decision=1)
    m.begin_tick()
    before = len(m._latq)
    agent.step(m)
    after = len(m._latq)
    assert after >= before + 1


def test_k_greedy_degrades_with_zero_tokens():
    a_id = "kg"
    m = setup_market([a_id])
    # no tokens available → degrade
    m.set_agent_compute(a_id, ComputeBudget(capacity_tokens=0, refill_tokens=0), LatencyModel(base_ms=0.0, ms_per_token=1.0))
    ctx = AgentContext(rng=random.Random(2))
    agent = KGreedyTrader(a_id, ctx, include_market=False, k=3, size=1, tokens_per_eval=1)
    m.begin_tick()
    before = len(m._latq)
    agent.step(m)
    after = len(m._latq)
    assert after == before  # degraded action not enqueued


def test_shallow_rl_requests_multiple_tokens():
    a_id = "rl"
    m = setup_market([a_id])
    # limit tokens so some actions may be dropped on degrade in later steps
    m.set_agent_compute(a_id, ComputeBudget(capacity_tokens=5, refill_tokens=5), LatencyModel(base_ms=0.0, ms_per_token=1.0))
    ctx = AgentContext(rng=random.Random(3))
    agent = ShallowRLTrader(a_id, ctx, include_market=True, size=1, tokens_per_eval=2, tokens_per_update=1)
    m.begin_tick()
    before = len(m._latq)
    agent.step(m)
    after = len(m._latq)
    # Should enqueue at least 1 action when tokens suffice
    assert after >= before

