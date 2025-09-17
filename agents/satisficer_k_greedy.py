from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Tuple

from .base import Agent, AgentContext
from sim.market import Market
from sim.types import Side


Action = Tuple[str, Side, int]  # (type: 'limit'|'market'|'hold', side, size)


class KGreedyTrader(Agent):
    """k-greedy/epsilon-greedy satisficer over a small discrete action set.

    - Constructs a candidate set of actions: hold, limit buy/sell at best quote, market buy/sell (optional).
    - Samples up to k candidates uniformly at random, evaluates a simple utility heuristic, and picks the best.
    - With probability epsilon, explores by picking a random action among sampled.

    Utility heuristic (cheap proxy):
      U(action) ≈ inventory_term + value_term − message_cost_term
      where value_term uses (ref - mid), inventory_term nudges towards zero inventory.

    Config:
      - include_market: whether to include market orders in candidate set.
      - k: number of random candidates to sample per decision (bounded by available actions).
      - epsilon: exploration probability.
      - size: order size.
      - ref_price: baseline value reference; if None, use current mid.
      - inv_penalty: coefficient for |inventory| penalty.
      - msg_cost_proxy: proxy weight for message cost.
      - tokens_per_eval: tokens per candidate evaluation (used to set tokens_requested ≈ k * tokens_per_eval).
    """

    def __init__(
        self,
        agent_id: str,
        ctx: AgentContext,
        include_market: bool = False,
        k: int = 3,
        epsilon: float = 0.1,
        size: int = 1,
        ref_price: float | None = None,
        inv_penalty: float = 0.01,
        msg_cost_proxy: float = 1e-5,
        tokens_per_eval: int = 1,
    ):
        super().__init__(agent_id, ctx)
        self.include_market = include_market
        self.k = max(1, int(k))
        self.epsilon = max(0.0, min(1.0, epsilon))
        self.size = size
        self.ref_price = ref_price
        self.inv_penalty = max(0.0, inv_penalty)
        self.msg_cost_proxy = max(0.0, msg_cost_proxy)
        self.tokens_per_eval = max(1, int(tokens_per_eval))

    def _actions(self) -> List[Action]:
        acts: List[Action] = [("hold", Side.BUY, 0)]  # side ignored for hold
        acts.append(("limit", Side.BUY, self.size))
        acts.append(("limit", Side.SELL, self.size))
        if self.include_market:
            acts.append(("market", Side.BUY, self.size))
            acts.append(("market", Side.SELL, self.size))
        return acts

    def _ref(self, market: Market, mid: float) -> float:
        return self.ref_price if self.ref_price is not None else mid

    def _utility(self, market: Market, mid: float, action: Action) -> float:
        a_type, side, size = action
        state = market.agents[self.id]
        ref = self._ref(market, mid)
        value_signal = ref - mid  # positive → undervalued → buy
        inv_term = -self.inv_penalty * abs(state.inventory)
        msg_cost = 0.0 if a_type == "hold" else self.msg_cost_proxy
        sign = 0
        if a_type != "hold":
            sign = +1 if side == Side.BUY else -1
        # crude utility proxy
        return sign * value_signal * size + inv_term - msg_cost

    def step(self, market: Market):
        bb, ba = market.book.top_of_book()
        if bb is None or ba is None:
            return
        mid = (bb + ba) / 2.0

        # Sample candidates
        acts_all = self._actions()
        r = self.ctx.rng
        # sample without replacement up to k
        indices = list(range(len(acts_all)))
        r.shuffle(indices)
        chosen = [acts_all[i] for i in indices[: min(self.k, len(indices))]]

        # evaluate
        utils = [self._utility(market, mid, a) for a in chosen]

        # choose action (epsilon-greedy)
        if r.random() < self.epsilon:
            idx = r.randrange(len(chosen))
        else:
            idx = max(range(len(chosen)), key=lambda i: utils[i])
        a_type, side, size = chosen[idx]

        tokens_req = max(1, self.tokens_per_eval * len(chosen))
        tick = market.cfg.tick_size

        if a_type == "hold" or size <= 0:
            return
        if a_type == "market":
            market.schedule_market(self.id, side, size, tokens_requested=tokens_req)
        else:
            # limit at best quote
            if side == Side.BUY:
                price = bb
                if price is None:
                    price = mid
                price = round(price / tick) * tick
                market.schedule_limit(self.id, Side.BUY, price, size, tokens_requested=tokens_req)
            else:
                price = ba
                if price is None:
                    price = mid
                price = round(price / tick) * tick
                market.schedule_limit(self.id, Side.SELL, price, size, tokens_requested=tokens_req)

