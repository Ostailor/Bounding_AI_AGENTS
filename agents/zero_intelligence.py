from __future__ import annotations

from typing import Optional

from .base import Agent, AgentContext
from sim.market import Market
from sim.types import Side


class ZITrader(Agent):
    """Zero-intelligence trader submitting random buy/sell with random prices around a reference.

    Config:
      - ref_price: float baseline price
      - max_abs_spread: absolute deviation from ref to place limit orders
      - limit_prob: probability to submit a limit (else market)
      - cancel_prob: probability to attempt cancel (noop if none)
      - size_min/max: order size range
    """

    def __init__(
        self,
        agent_id: str,
        ctx: AgentContext,
        ref_price: float = 100.0,
        max_abs_spread: float = 0.5,
        limit_prob: float = 0.8,
        cancel_prob: float = 0.05,
        size_min: int = 1,
        size_max: int = 5,
    ):
        super().__init__(agent_id, ctx)
        self.ref_price = ref_price
        self.max_abs_spread = max_abs_spread
        self.limit_prob = limit_prob
        self.cancel_prob = cancel_prob
        self.size_min = size_min
        self.size_max = size_max

    def step(self, market: Market):
        r = self.ctx.rng
        # Possibly cancel: ZI doesn't track order ids; skip for simplicity in M1
        # Submit one order
        side = Side.BUY if r.random() < 0.5 else Side.SELL
        size = r.randint(self.size_min, self.size_max)
        if r.random() < self.limit_prob:
            # Price within band, aligned to tick
            delta = (r.random() * 2 - 1) * self.max_abs_spread
            px_raw = max(0.01, self.ref_price + (delta if side == Side.BUY else -delta))
            # align to tick size
            tick = market.cfg.tick_size
            px = round(px_raw / tick) * tick
            market.submit_limit(self.id, side, px, size)
        else:
            market.submit_market(self.id, side, size)

