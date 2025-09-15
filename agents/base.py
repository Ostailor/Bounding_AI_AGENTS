from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Optional

from sim.market import Market
from sim.types import Side


@dataclass
class AgentContext:
    rng: random.Random


class Agent:
    id: str

    def __init__(self, agent_id: str, ctx: AgentContext):
        self.id = agent_id
        self.ctx = ctx

    def on_start(self, market: Market):
        pass

    def step(self, market: Market):
        """Called once per tick; agent should schedule an intent using compute-aware APIs.

        Keep this non-blocking and deterministic given ctx.rng.
        """
        raise NotImplementedError
