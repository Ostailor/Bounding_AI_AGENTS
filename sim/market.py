from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .order_book import OrderBook
from .types import AgentId, Order, Side, Trade


@dataclass
class AgentState:
    cash: float = 0.0
    inventory: int = 0
    last_value_price: Optional[float] = None


@dataclass
class MarketConfig:
    tick_size: float = 0.01
    fee_per_message: float = 0.0
    fee_per_share: float = 0.0  # taker fee per share for marketable volume


class Market:
    def __init__(self, config: MarketConfig, agent_ids: List[AgentId]):
        self.cfg = config
        self.book = OrderBook(tick_size=config.tick_size)
        self.t: int = 0
        self.agents: Dict[AgentId, AgentState] = {a: AgentState() for a in agent_ids}
        self._next_order_id: int = 1
        self._last_trade_price: Optional[float] = None
        self._logs_root: Optional[str] = None
        self._agent_logs: Dict[AgentId, any] = {}
        self._steps_log = None

    # --- Logging setup ---
    def attach_logs(self, root_dir: str):
        os.makedirs(root_dir, exist_ok=True)
        self._logs_root = root_dir
        self._steps_log = open(os.path.join(root_dir, "steps.jsonl"), "w")
        for aid in self.agents:
            path = os.path.join(root_dir, f"agent_{aid}.jsonl")
            self._agent_logs[aid] = open(path, "w")

    def close_logs(self):
        if self._steps_log:
            self._steps_log.close()
        for f in self._agent_logs.values():
            f.close()

    def _log_step(self, payload: dict):
        if self._steps_log:
            self._steps_log.write(json.dumps(payload) + "\n")

    def _log_agent(self, agent_id: AgentId, payload: dict):
        f = self._agent_logs.get(agent_id)
        if f:
            f.write(json.dumps(payload) + "\n")

    # --- Orders ---
    def _new_order_id(self) -> int:
        oid = self._next_order_id
        self._next_order_id += 1
        return oid

    def submit_limit(self, agent_id: AgentId, side: Side, price: float, qty: int) -> List[Trade]:
        self._charge_message_fee(agent_id)
        order = Order(
            id=self._new_order_id(),
            agent_id=agent_id,
            side=side,
            price=price,
            qty=qty,
            ts=self.t,
            is_market=False,
        )
        trades = self.book.place_limit(order)
        self._apply_trades(agent_id, side, trades)
        self._log_agent(agent_id, {"t": self.t, "type": "limit", "side": side.value, "px": price, "qty": qty})
        return trades

    def submit_market(self, agent_id: AgentId, side: Side, qty: int) -> List[Trade]:
        self._charge_message_fee(agent_id)
        order = Order(
            id=self._new_order_id(),
            agent_id=agent_id,
            side=side,
            price=None,
            qty=qty,
            ts=self.t,
            is_market=True,
        )
        trades = self.book.place_market(order)
        self._apply_trades(agent_id, side, trades, taker=True)
        self._log_agent(agent_id, {"t": self.t, "type": "market", "side": side.value, "qty": qty})
        return trades

    def cancel(self, agent_id: AgentId, order_id: int) -> bool:
        self._charge_message_fee(agent_id)
        ok = self.book.cancel(order_id)
        self._log_agent(agent_id, {"t": self.t, "type": "cancel", "order_id": order_id, "ok": ok})
        return ok

    def _charge_message_fee(self, agent_id: AgentId):
        self.agents[agent_id].cash -= self.cfg.fee_per_message

    def _apply_trades(self, initiator: AgentId, side: Side, trades: List[Trade], taker: bool = False):
        for tr in trades:
            self._last_trade_price = tr.price
            qty = tr.qty
            # Update buyer
            b = tr.buy_agent_id
            s = tr.sell_agent_id
            if b not in self.agents:
                self.agents[b] = AgentState()
            if s not in self.agents:
                self.agents[s] = AgentState()
            self.agents[b].inventory += qty
            self.agents[b].cash -= tr.price * qty
            self.agents[s].inventory -= qty
            self.agents[s].cash += tr.price * qty
            # Apply taker fees to the initiating side only
            taker_agent = initiator
            if b == taker_agent:
                self.agents[b].cash -= self.cfg.fee_per_share * qty
            elif s == taker_agent:
                self.agents[s].cash -= self.cfg.fee_per_share * qty

    # --- Tick processing ---
    def step(self):
        self.t += 1
        bb, ba = self.book.top_of_book()
        mid = None
        spread = None
        depth1_bid = None
        depth1_ask = None
        depth5_bid = None
        depth5_ask = None
        if bb is not None and ba is not None:
            mid = (bb + ba) / 2.0
            spread = ba - bb
        # Depth metrics
        snap1 = self.book.snapshot_depth(top_k=1)
        if snap1["bids"]:
            depth1_bid = snap1["bids"][0][1]
        if snap1["asks"]:
            depth1_ask = snap1["asks"][0][1]
        snap5 = self.book.snapshot_depth(top_k=5)
        depth5_bid = sum(x[1] for x in snap5["bids"]) if snap5["bids"] else 0
        depth5_ask = sum(x[1] for x in snap5["asks"]) if snap5["asks"] else 0
        payload = {
            "t": self.t,
            "best_bid": bb,
            "best_ask": ba,
            "mid": mid,
            "spread": spread,
            "depth1_bid": depth1_bid,
            "depth1_ask": depth1_ask,
            "depth5_bid": depth5_bid,
            "depth5_ask": depth5_ask,
            "last_trade": self._last_trade_price,
        }
        self._log_step(payload)
        return payload

    # --- PnL ---
    def mark_to_market(self, agent_id: AgentId, price: Optional[float] = None) -> float:
        px = price
        if px is None:
            bb, ba = self.book.top_of_book()
            if bb is not None and ba is not None:
                px = (bb + ba) / 2.0
            elif self._last_trade_price is not None:
                px = self._last_trade_price
        if px is None:
            px = 0.0
        st = self.agents[agent_id]
        st.last_value_price = px
        return st.cash + st.inventory * px
