from __future__ import annotations

from .base import Agent, AgentContext
from sim.market import Market
from sim.types import Side


class MarketMakerSimple(Agent):
    """Quotes a symmetric spread around mid (or reference) with inventory bounds.

    Config:
      - base_spread: half-spread to quote around mid
      - size: order size per quote
      - inv_limit: inventory cap; if breached, quote only to reduce inventory
    """

    def __init__(self, agent_id: str, ctx: AgentContext, base_spread: float = 0.05, size: int = 1, inv_limit: int = 20):
        super().__init__(agent_id, ctx)
        self.base_spread = base_spread
        self.size = size
        self.inv_limit = inv_limit

    def step(self, market: Market):
        state = market.agents[self.id]
        bb, ba = market.book.top_of_book()
        tick = market.cfg.tick_size
        # Determine mid
        if bb is not None and ba is not None:
            mid = (bb + ba) / 2.0
        else:
            # fallback
            mid = 100.0
        # Choose which side(s) to quote based on inventory
        if state.inventory >= self.inv_limit:
            # too long, only sell
            ask = round((mid + self.base_spread) / tick) * tick
            market.submit_limit(self.id, Side.SELL, ask, self.size)
        elif state.inventory <= -self.inv_limit:
            # too short, only buy
            bid = round((mid - self.base_spread) / tick) * tick
            market.submit_limit(self.id, Side.BUY, bid, self.size)
        else:
            bid = round((mid - self.base_spread) / tick) * tick
            ask = round((mid + self.base_spread) / tick) * tick
            market.submit_limit(self.id, Side.BUY, bid, self.size)
            market.submit_limit(self.id, Side.SELL, ask, self.size)

