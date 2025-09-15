from __future__ import annotations

import heapq
import math
import random
from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple

from .types import Side


@dataclass
class ComputeBudget:
    capacity_tokens: int = 100
    refill_tokens: int = 100  # per tick


@dataclass
class LatencyModel:
    base_ms: float = 0.5
    ms_per_token: float = 0.1
    jitter_ms: float = 0.0


@dataclass
class AgentComputeState:
    tokens: int
    budget: ComputeBudget
    latency: LatencyModel

    def refill(self):
        self.tokens = min(self.budget.capacity_tokens, self.tokens + self.budget.refill_tokens)

    def consume(self, requested: int) -> Tuple[int, bool]:
        """Consume up to requested tokens. Returns (used, degraded_flag).

        degraded_flag True means request couldn't be satisfied fully.
        """
        if requested <= self.tokens:
            self.tokens -= requested
            return requested, False
        # degrade: use 0 tokens
        return 0, True


@dataclass(order=True)
class ScheduledIntent:
    arrival_t: int
    seq: int
    intent_type: str = field(compare=False)
    agent_id: str = field(compare=False)
    side: Optional[Side] = field(default=None, compare=False)
    price: Optional[float] = field(default=None, compare=False)
    qty: Optional[int] = field(default=None, compare=False)
    tokens_used: int = field(default=0, compare=False)
    latency_ms: float = field(default=0.0, compare=False)


class LatencyQueue:
    def __init__(self):
        self._pq: List[ScheduledIntent] = []
        self._seq: int = 0

    def push(self, item: ScheduledIntent):
        heapq.heappush(self._pq, item)

    def next_seq(self) -> int:
        self._seq += 1
        return self._seq

    def pop_ready(self, t: int) -> List[ScheduledIntent]:
        out: List[ScheduledIntent] = []
        while self._pq and self._pq[0].arrival_t <= t:
            out.append(heapq.heappop(self._pq))
        return out

    def __len__(self) -> int:
        return len(self._pq)

