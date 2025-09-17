from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from .base import Agent, AgentContext
from sim.market import Market
from sim.types import Side


Action = Tuple[str, Side, int]


class ShallowRLTrader(Agent):
    """Shallow linear contextual bandit over a small action set.

    - Actions: hold, limit buy/sell at best, optional market buy/sell.
    - Q(s,a) = w_a · phi(s), per-action linear weights with shared features.
    - Selects argmax_a Q(s,a) with epsilon exploration.
    - Updates online with semi-bandit immediate reward: ΔPnL - inv_penalty*|inv| - msg_cost.

    This is intentionally lightweight (no deep nets); compute tokens requested scale with
    number of evaluated actions and update burden.

    Config:
      - include_market: include market orders in action set.
      - size: lot size.
      - epsilon: exploration rate.
      - alpha: learning rate.
      - inv_penalty: penalty coefficient for absolute inventory.
      - msg_cost_proxy: proxy penalty per non-hold action.
      - tokens_per_eval: tokens per action-value evaluation.
      - tokens_per_update: tokens charged to reflect learning update compute.
    """

    def __init__(
        self,
        agent_id: str,
        ctx: AgentContext,
        include_market: bool = True,
        size: int = 1,
        epsilon: float = 0.1,
        alpha: float = 0.05,
        inv_penalty: float = 0.01,
        msg_cost_proxy: float = 1e-5,
        tokens_per_eval: int = 1,
        tokens_per_update: int = 1,
    ):
        super().__init__(agent_id, ctx)
        self.include_market = include_market
        self.size = max(1, int(size))
        self.epsilon = max(0.0, min(1.0, epsilon))
        self.alpha = max(0.0, alpha)
        self.inv_penalty = max(0.0, inv_penalty)
        self.msg_cost_proxy = max(0.0, msg_cost_proxy)
        self.tokens_per_eval = max(1, int(tokens_per_eval))
        self.tokens_per_update = max(0, int(tokens_per_update))
        # weights per action
        self._actions: List[Action] = [("hold", Side.BUY, 0), ("limit", Side.BUY, self.size), ("limit", Side.SELL, self.size)]
        if self.include_market:
            self._actions.extend([("market", Side.BUY, self.size), ("market", Side.SELL, self.size)])
        self._num_features = 5
        self._w = {i: [0.0] * self._num_features for i in range(len(self._actions))}
        self._last_pnl: float | None = None
        self._last_action_idx: int | None = None

    def _features(self, market: Market, mid: float) -> List[float]:
        state = market.agents[self.id]
        # Simple features: [1, inv, inv^2, spread, depth_imbalance]
        bb, ba = market.book.top_of_book()
        spread = (ba - bb) if (bb is not None and ba is not None) else 0.0
        snap1 = market.book.snapshot_depth(top_k=1)
        bid_depth = snap1["bids"][0][1] if snap1["bids"] else 0.0
        ask_depth = snap1["asks"][0][1] if snap1["asks"] else 0.0
        imb = 0.0
        tot = bid_depth + ask_depth
        if tot > 0:
            imb = (bid_depth - ask_depth) / tot
        return [1.0, float(state.inventory), float(state.inventory ** 2), float(spread), float(imb)]

    def _q(self, idx: int, phi: List[float]) -> float:
        w = self._w[idx]
        return sum(wi * fi for wi, fi in zip(w, phi))

    def _choose_action(self, market: Market, mid: float) -> Tuple[int, Action, int]:
        phi = self._features(market, mid)
        r = self.ctx.rng
        # evaluate all actions
        qs = [self._q(i, phi) for i in range(len(self._actions))]
        if r.random() < self.epsilon:
            idx = r.randrange(len(self._actions))
        else:
            idx = max(range(len(self._actions)), key=lambda i: qs[i])
        tokens_req = max(1, self.tokens_per_eval * len(self._actions) + self.tokens_per_update)
        return idx, self._actions[idx], tokens_req

    def _reward(self, market: Market) -> float:
        pnl = market.mark_to_market(self.id)
        prev = self._last_pnl if self._last_pnl is not None else pnl
        r_immediate = pnl - prev
        # penalties
        inv = abs(market.agents[self.id].inventory)
        r = r_immediate - self.inv_penalty * inv
        # approximate message cost already embedded via tokens, but add proxy if last action non-hold
        if self._last_action_idx is not None:
            a_type, _, size = self._actions[self._last_action_idx]
            if a_type != "hold" and size > 0:
                r -= self.msg_cost_proxy
        self._last_pnl = pnl
        return r

    def _update(self, market: Market, phi: List[float], idx: int, reward: float):
        # one-step bandit-style update: w_a ← w_a + α (r - w_a·φ) φ
        q = self._q(idx, phi)
        td = reward - q
        w = self._w[idx]
        for j in range(self._num_features):
            w[j] += self.alpha * td * phi[j]

    def step(self, market: Market):
        bb, ba = market.book.top_of_book()
        if bb is None or ba is None:
            return
        mid = (bb + ba) / 2.0

        # compute reward from previous action and update
        phi = self._features(market, mid)
        if self._last_action_idx is not None:
            r = self._reward(market)
            self._update(market, phi, self._last_action_idx, r)

        # choose and act
        idx, action, tokens_req = self._choose_action(market, mid)
        a_type, side, size = action
        tick = market.cfg.tick_size
        if a_type == "hold" or size <= 0:
            self._last_action_idx = idx
            return
        if a_type == "market":
            market.schedule_market(self.id, side, size, tokens_requested=tokens_req)
        else:
            if side == Side.BUY:
                price = bb if bb is not None else mid
                price = round(price / tick) * tick
                market.schedule_limit(self.id, Side.BUY, price, size, tokens_requested=tokens_req)
            else:
                price = ba if ba is not None else mid
                price = round(price / tick) * tick
                market.schedule_limit(self.id, Side.SELL, price, size, tokens_requested=tokens_req)
        self._last_action_idx = idx

