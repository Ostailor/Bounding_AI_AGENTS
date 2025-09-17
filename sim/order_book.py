from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Deque, Dict, List, Optional, Tuple

from .types import Order, Side, Trade


@dataclass
class PriceLevel:
    price: float
    queue: Deque[Order]


class OrderBook:
    """Price–time priority limit order book with simple matching.

    - Bids sorted descending by price, FIFO within price.
    - Asks sorted ascending by price, FIFO within price.
    - Supports limit, market, cancel.
    - Enforces tick size (rejects nonconforming prices).
    """

    def __init__(self, tick_size: float = 0.01):
        assert tick_size > 0
        self.tick = tick_size
        self._bids: Dict[float, PriceLevel] = {}
        self._asks: Dict[float, PriceLevel] = {}
        self._id_index: Dict[int, Tuple[float, Side]] = {}

    # --- Helpers ---
    def _conform_price(self, price: float) -> bool:
        return abs(round(price / self.tick) * self.tick - price) < 1e-9

    def _best_bid(self) -> Optional[PriceLevel]:
        if not self._bids:
            return None
        p = max(self._bids.keys())
        return self._bids[p]

    def _best_ask(self) -> Optional[PriceLevel]:
        if not self._asks:
            return None
        p = min(self._asks.keys())
        return self._asks[p]

    def top_of_book(self) -> Tuple[Optional[float], Optional[float]]:
        bb = self._best_bid()
        ba = self._best_ask()
        return (bb.price if bb else None, ba.price if ba else None)

    def depth_at_level(self, price: float, side: Side) -> int:
        book = self._bids if side == Side.BUY else self._asks
        lvl = book.get(price)
        if not lvl:
            return 0
        return sum(o.qty for o in lvl.queue)

    # --- Public API ---
    def place_limit(self, order: Order) -> List[Trade]:
        if order.is_market:
            raise ValueError("place_limit requires limit order")
        assert order.price is not None
        if not self._conform_price(order.price):
            raise ValueError("price not aligned with tick size")
        trades: List[Trade] = []
        remaining = order.qty
        # Try to match against opposite book if crossing
        if order.side == Side.BUY:
            while remaining > 0 and self._asks:
                best_ask = self._best_ask()
                assert best_ask is not None
                if order.price < best_ask.price:
                    break
                trades_made, filled = self._execute_against(
                    best_ask, remaining, take_side=Side.BUY, ts=order.ts, taker_agent=order.agent_id, taker_limit=order.price
                )
                trades.extend(trades_made)
                remaining -= filled
                if not best_ask.queue:
                    del self._asks[best_ask.price]
        else:
            while remaining > 0 and self._bids:
                best_bid = self._best_bid()
                assert best_bid is not None
                if order.price > best_bid.price:
                    break
                trades_made, filled = self._execute_against(
                    best_bid, remaining, take_side=Side.SELL, ts=order.ts, taker_agent=order.agent_id, taker_limit=order.price
                )
                trades.extend(trades_made)
                remaining -= filled
                if not best_bid.queue:
                    del self._bids[best_bid.price]
        # If residual, rest on book
        if remaining > 0:
            resting = Order(
                id=order.id,
                agent_id=order.agent_id,
                side=order.side,
                price=order.price,
                qty=remaining,
                ts=order.ts,
                is_market=False,
            )
            book = self._bids if order.side == Side.BUY else self._asks
            lvl = book.get(resting.price)
            if not lvl:
                lvl = PriceLevel(price=resting.price, queue=deque())
                book[resting.price] = lvl
            lvl.queue.append(resting)
            self._id_index[resting.id] = (resting.price, resting.side)
        return trades

    def place_market(self, order: Order) -> List[Trade]:
        if not order.is_market:
            raise ValueError("place_market requires market order")
        trades: List[Trade] = []
        remaining = order.qty
        if order.side == Side.BUY:
            while remaining > 0 and self._asks:
                best_ask = self._best_ask()
                assert best_ask is not None
                trades_made, filled = self._execute_against(
                    best_ask, remaining, take_side=Side.BUY, ts=order.ts, taker_agent=order.agent_id, taker_limit=None
                )
                trades.extend(trades_made)
                remaining -= filled
                if not best_ask.queue:
                    del self._asks[best_ask.price]
        else:
            while remaining > 0 and self._bids:
                best_bid = self._best_bid()
                assert best_bid is not None
                trades_made, filled = self._execute_against(
                    best_bid, remaining, take_side=Side.SELL, ts=order.ts, taker_agent=order.agent_id, taker_limit=None
                )
                trades.extend(trades_made)
                remaining -= filled
                if not best_bid.queue:
                    del self._bids[best_bid.price]
        return trades

    def cancel(self, order_id: int) -> bool:
        ref = self._id_index.get(order_id)
        if not ref:
            return False
        price, side = ref
        book = self._bids if side == Side.BUY else self._asks
        lvl = book.get(price)
        if not lvl:
            return False
        removed = False
        newq: Deque[Order] = deque()
        while lvl.queue:
            o = lvl.queue.popleft()
            if o.id == order_id and not removed:
                removed = True
                continue
            newq.append(o)
        lvl.queue = newq
        if not lvl.queue:
            del book[price]
        if removed:
            del self._id_index[order_id]
        return removed

    # --- Matching core ---
    def _execute_against(
        self, level: PriceLevel, qty: int, take_side: Side, ts: int, taker_agent: str, taker_limit: Optional[float]
    ) -> Tuple[List[Trade], int]:
        trades: List[Trade] = []
        remaining = qty
        while remaining > 0 and level.queue:
            resting = level.queue[0]
            traded = min(remaining, resting.qty)
            price = level.price
            if take_side == Side.BUY:
                trades.append(
                    Trade(
                        buy_order_id=-1,
                        sell_order_id=resting.id,
                        buy_agent_id=taker_agent,
                        sell_agent_id=resting.agent_id,
                        price=price,
                        qty=traded,
                        ts=ts,
                        buyer_limit=taker_limit,
                        seller_limit=resting.price,
                    )
                )
            else:
                trades.append(
                    Trade(
                        buy_order_id=resting.id,
                        sell_order_id=-1,
                        buy_agent_id=resting.agent_id,
                        sell_agent_id=taker_agent,
                        price=price,
                        qty=traded,
                        ts=ts,
                        buyer_limit=resting.price,
                        seller_limit=taker_limit,
                    )
                )
            remaining -= traded
            if traded == resting.qty:
                level.queue.popleft()
                self._id_index.pop(resting.id, None)
            else:
                # reduce in place
                new_rest = Order(
                    id=resting.id,
                    agent_id=resting.agent_id,
                    side=resting.side,
                    price=resting.price,
                    qty=resting.qty - traded,
                    ts=resting.ts,
                    is_market=False,
                )
                level.queue[0] = new_rest
        return trades, qty - remaining

    # --- Introspection ---
    def snapshot_depth(self, top_k: int = 1) -> Dict[str, List[Tuple[float, int]]]:
        bids = sorted(self._bids.items(), key=lambda kv: kv[0], reverse=True)[:top_k]
        asks = sorted(self._asks.items(), key=lambda kv: kv[0])[:top_k]
        return {
            "bids": [(p, sum(o.qty for o in lvl.queue)) for p, lvl in bids],
            "asks": [(p, sum(o.qty for o in lvl.queue)) for p, lvl in asks],
        }
