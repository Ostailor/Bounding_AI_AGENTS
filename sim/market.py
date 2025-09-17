from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .order_book import OrderBook
from .types import AgentId, Order, Side, Trade
from .compute import (
    AgentComputeState,
    ComputeBudget,
    LatencyModel,
    LatencyQueue,
    ScheduledIntent,
)
import math
import random


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
    tick_duration_ms: float = 1.0


class Market:
    def __init__(self, config: MarketConfig, agent_ids: List[AgentId], rng: Optional[random.Random] = None):
        self.cfg = config
        self.book = OrderBook(tick_size=config.tick_size)
        self.t: int = 0
        self.agents: Dict[AgentId, AgentState] = {a: AgentState() for a in agent_ids}
        self._next_order_id: int = 1
        self._last_trade_price: Optional[float] = None
        self._logs_root: Optional[str] = None
        self._agent_logs: Dict[AgentId, any] = {}
        self._steps_log = None
        self._trades_log = None
        self._rng = rng or random.Random(0)
        # Compute + latency
        self._compute: Dict[AgentId, AgentComputeState] = {}
        self._latq = LatencyQueue()
        # Per-tick counters for analysis
        self._trades_this_tick: int = 0
        self._volume_this_tick: int = 0
        self._messages_this_tick: int = 0

    # --- Logging setup ---
    def attach_logs(self, root_dir: str):
        os.makedirs(root_dir, exist_ok=True)
        self._logs_root = root_dir
        self._steps_log = open(os.path.join(root_dir, "steps.jsonl"), "w")
        self._trades_log = open(os.path.join(root_dir, "trades.jsonl"), "w")
        for aid in self.agents:
            path = os.path.join(root_dir, f"agent_{aid}.jsonl")
            self._agent_logs[aid] = open(path, "w")

    def close_logs(self):
        if self._steps_log:
            self._steps_log.close()
        if self._trades_log:
            self._trades_log.close()
        for f in self._agent_logs.values():
            f.close()

    def _log_step(self, payload: dict):
        if self._steps_log:
            self._steps_log.write(json.dumps(payload) + "\n")
            self._steps_log.flush()

    def _log_agent(self, agent_id: AgentId, payload: dict):
        f = self._agent_logs.get(agent_id)
        if f:
            f.write(json.dumps(payload) + "\n")
            f.flush()

    def log_decision_timing(self, agent_id: AgentId, wall_ms: float):
        self._log_agent(agent_id, {"t": self.t, "type": "decision_timing", "wall_ms": wall_ms})

    def log_pnl(self, agent_id: AgentId, pnl: float):
        """Public helper to log per-agent PnL at current tick.

        Analysis scripts can aggregate these to produce learning curves.
        """
        self._log_agent(agent_id, {"t": self.t, "type": "pnl", "pnl": pnl})

    # --- Compute / latency setup ---
    def set_agent_compute(self, agent_id: AgentId, budget: ComputeBudget, latency: LatencyModel):
        self._compute[agent_id] = AgentComputeState(tokens=budget.capacity_tokens, budget=budget, latency=latency)

    def begin_tick(self):
        for st in self._compute.values():
            st.refill()

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
        # Count message
        self._messages_this_tick += 1
        # Apply fee (may be zero)
        self.agents[agent_id].cash -= self.cfg.fee_per_message

    def _apply_trades(self, initiator: AgentId, side: Side, trades: List[Trade], taker: bool = False):
        for tr in trades:
            self._last_trade_price = tr.price
            qty = tr.qty
            # Counters
            self._trades_this_tick += 1
            self._volume_this_tick += qty
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
            # Log trade record for analysis
            if self._trades_log:
                self._trades_log.write(json.dumps({
                    "t": self.t,
                    "price": tr.price,
                    "qty": qty,
                    "buy_agent": b,
                    "sell_agent": s,
                    "taker_agent": taker_agent,
                    "taker_side": side.value
                }) + "\n")
                self._trades_log.flush()

    # --- Intent scheduling (compute + latency) ---
    def schedule_limit(self, agent_id: AgentId, side: Side, price: float, qty: int, tokens_requested: int):
        st = self._compute.get(agent_id)
        if st is None:
            # default: no budget, no latency
            arrival_t = self.t
            seq = self._latq.next_seq()
            self._latq.push(ScheduledIntent(arrival_t=arrival_t, seq=seq, intent_type="limit", agent_id=agent_id, side=side, price=price, qty=qty, tokens_used=0, latency_ms=0.0))
            self._log_agent(agent_id, {
                "t": self.t, "type": "intent", "intent_type": "limit", "side": side.value, "px": price, "qty": qty,
                "tokens_req": tokens_requested, "tokens_used": 0, "tokens_remain": 0, "latency_ms": 0.0, "arrival_t": arrival_t, "degraded": False,
            })
            return
        used, degraded = st.consume(tokens_requested)
        latency_ms = st.latency.base_ms + used * st.latency.ms_per_token
        if st.latency.jitter_ms > 0:
            # symmetric jitter
            jitter = (self._rng.random() * 2 - 1) * st.latency.jitter_ms
            latency_ms = max(0.0, latency_ms + jitter)
        ticks = max(1, math.ceil(latency_ms / max(1e-6, self.cfg.tick_duration_ms)))
        arrival_t = self.t + ticks
        seq = self._latq.next_seq()
        if degraded:
            # drop action
            self._log_agent(agent_id, {
                "t": self.t, "type": "intent", "intent_type": "limit", "side": side.value, "px": price, "qty": qty,
                "tokens_req": tokens_requested, "tokens_used": 0, "tokens_remain": st.tokens, "latency_ms": latency_ms, "arrival_t": arrival_t, "degraded": True,
            })
            return
        self._latq.push(ScheduledIntent(arrival_t=arrival_t, seq=seq, intent_type="limit", agent_id=agent_id, side=side, price=price, qty=qty, tokens_used=used, latency_ms=latency_ms))
        self._log_agent(agent_id, {
            "t": self.t, "type": "intent", "intent_type": "limit", "side": side.value, "px": price, "qty": qty,
            "tokens_req": tokens_requested, "tokens_used": used, "tokens_remain": st.tokens, "latency_ms": latency_ms, "arrival_t": arrival_t, "degraded": False,
        })

    def schedule_market(self, agent_id: AgentId, side: Side, qty: int, tokens_requested: int):
        st = self._compute.get(agent_id)
        if st is None:
            arrival_t = self.t
            seq = self._latq.next_seq()
            self._latq.push(ScheduledIntent(arrival_t=arrival_t, seq=seq, intent_type="market", agent_id=agent_id, side=side, qty=qty, tokens_used=0, latency_ms=0.0))
            self._log_agent(agent_id, {"t": self.t, "type": "intent", "intent_type": "market", "side": side.value, "qty": qty, "tokens_req": tokens_requested, "tokens_used": 0, "tokens_remain": 0, "latency_ms": 0.0, "arrival_t": arrival_t, "degraded": False})
            return
        used, degraded = st.consume(tokens_requested)
        latency_ms = st.latency.base_ms + used * st.latency.ms_per_token
        if st.latency.jitter_ms > 0:
            jitter = (self._rng.random() * 2 - 1) * st.latency.jitter_ms
            latency_ms = max(0.0, latency_ms + jitter)
        ticks = max(1, math.ceil(latency_ms / max(1e-6, self.cfg.tick_duration_ms)))
        arrival_t = self.t + ticks
        seq = self._latq.next_seq()
        if degraded:
            self._log_agent(agent_id, {"t": self.t, "type": "intent", "intent_type": "market", "side": side.value, "qty": qty, "tokens_req": tokens_requested, "tokens_used": 0, "tokens_remain": st.tokens, "latency_ms": latency_ms, "arrival_t": arrival_t, "degraded": True})
            return
        self._latq.push(ScheduledIntent(arrival_t=arrival_t, seq=seq, intent_type="market", agent_id=agent_id, side=side, qty=qty, tokens_used=used, latency_ms=latency_ms))
        self._log_agent(agent_id, {"t": self.t, "type": "intent", "intent_type": "market", "side": side.value, "qty": qty, "tokens_req": tokens_requested, "tokens_used": used, "tokens_remain": st.tokens, "latency_ms": latency_ms, "arrival_t": arrival_t, "degraded": False})


    # --- Tick processing ---
    def step(self):
        # advance time
        self.t += 1
        # reset per-tick counters
        self._trades_this_tick = 0
        self._volume_this_tick = 0
        self._messages_this_tick = 0
        # process arrivals scheduled for this tick
        arrivals = self._latq.pop_ready(self.t)
        for ev in arrivals:
            if ev.intent_type == "limit":
                self.submit_limit(ev.agent_id, ev.side, float(ev.price), int(ev.qty))
            elif ev.intent_type == "market":
                self.submit_market(ev.agent_id, ev.side, int(ev.qty))
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
            "num_trades": self._trades_this_tick,
            "trade_volume": self._volume_this_tick,
            "num_messages": self._messages_this_tick,
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
