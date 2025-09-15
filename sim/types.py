from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


OrderId = int
AgentId = str


@dataclass(frozen=True)
class Order:
    id: OrderId
    agent_id: AgentId
    side: Side
    price: Optional[float]  # None for pure market orders
    qty: int
    ts: int  # discrete time tick the order was created
    is_market: bool = False


@dataclass(frozen=True)
class Trade:
    buy_order_id: OrderId
    sell_order_id: OrderId
    buy_agent_id: AgentId
    sell_agent_id: AgentId
    price: float
    qty: int
    ts: int
