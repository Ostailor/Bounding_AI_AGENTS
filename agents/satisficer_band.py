from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

from .base import Agent, AgentContext
from sim.market import Market
from sim.types import Side


class TauBandTrader(Agent):
    """Threshold-band satisficer.

    Acts only when the observed price deviates from a reference by more than a band τ.
    If |mid - ref| <= τ, holds (does nothing). Otherwise, submits a single order:
      - If mid < ref - τ: buys (limit by default) to revert towards ref.
      - If mid > ref + τ: sells (limit by default).

    Config:
      - ref_price: optional fixed reference price. If None, uses current mid when first observed.
      - ref_mode: 'fixed' uses the configured ref_price; 'mid' uses the current mid each step.
      - tau: non-negative band size.
      - size: order size.
      - limit_only: if True, always submits limit orders at best quotes; else may use market when band is large.
      - market_thresh_mult: if not limit_only, switch to market when |mid - ref| >= market_thresh_mult * tau.
      - inv_limit: inventory cap; if breached, only act to reduce inventory.
      - price_skew: optional additive skew to the quote price relative to best bid/ask (in price units).
      - tokens_per_decision: compute tokens requested for each action.
    """

    def __init__(
        self,
        agent_id: str,
        ctx: AgentContext,
        ref_price: Optional[float] = None,
        ref_mode: Literal["fixed", "mid"] = "mid",
        tau: float = 0.05,
        size: int = 1,
        limit_only: bool = True,
        market_thresh_mult: float = 2.0,
        inv_limit: int = 50,
        price_skew: float = 0.0,
        tokens_per_decision: int = 1,
    ):
        super().__init__(agent_id, ctx)
        self._ref_fixed = ref_price
        self.ref_mode = ref_mode
        self.tau = max(0.0, tau)
        self.size = size
        self.limit_only = limit_only
        self.market_thresh_mult = max(1.0, market_thresh_mult)
        self.inv_limit = inv_limit
        self.price_skew = price_skew
        self.tokens_per_decision = max(1, int(tokens_per_decision))

    def _current_ref(self, market: Market) -> Optional[float]:
        if self.ref_mode == "fixed":
            return self._ref_fixed
        # dynamic: use current mid as ref
        bb, ba = market.book.top_of_book()
        if bb is None or ba is None:
            return self._ref_fixed
        return (bb + ba) / 2.0

    def step(self, market: Market):
        bb, ba = market.book.top_of_book()
        if bb is None or ba is None:
            return  # wait for book to form
        mid = (bb + ba) / 2.0
        ref = self._current_ref(market)
        if ref is None:
            # initialize fixed ref if not set
            self._ref_fixed = mid
            ref = mid
        gap = mid - ref

        state = market.agents[self.id]
        tick = market.cfg.tick_size

        # Inventory guardrails: if too long, prefer selling; too short, prefer buying
        inv_bias: Optional[Side] = None
        if state.inventory >= self.inv_limit:
            inv_bias = Side.SELL
        elif state.inventory <= -self.inv_limit:
            inv_bias = Side.BUY

        if abs(gap) <= self.tau and inv_bias is None:
            return  # hold inside band

        # Decide action side
        if inv_bias is not None:
            side = inv_bias
        else:
            side = Side.SELL if gap > 0 else Side.BUY

        # Order type decision
        use_market = False
        if not self.limit_only and abs(gap) >= self.market_thresh_mult * self.tau:
            use_market = True

        if use_market:
            market.schedule_market(self.id, side, self.size, tokens_requested=self.tokens_per_decision)
            return

        # Limit: place at best quote with optional skew
        if side == Side.BUY:
            price = bb if bb is not None else (mid - self.tau)
            price = round((price + self.price_skew) / tick) * tick
            market.schedule_limit(self.id, Side.BUY, price, self.size, tokens_requested=self.tokens_per_decision)
        else:
            price = ba if ba is not None else (mid + self.tau)
            price = round((price + self.price_skew) / tick) * tick
            market.schedule_limit(self.id, Side.SELL, price, self.size, tokens_requested=self.tokens_per_decision)

