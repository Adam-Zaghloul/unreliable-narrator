"""Shared data types. Everything the hub passes around is one of these."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

WINDOW_S = 10  # truth is computed per 10 s window
PACKET_PERIOD_S = 2  # badges send one packet every 2 s


@dataclass(frozen=True)
class Ping:
    """One RSSI reading: badge `badge` heard beacon `beacon` at time t_ms."""
    badge: str
    t_ms: int
    beacon: str
    rssi: float


@dataclass(frozen=True)
class ZoneEstimate:
    player: str
    window: int
    zone: str | None  # None = no data
    confidence: float  # 0..1, share of packets in the window that agree


ClaimType = Literal["location", "together", "absent"]


@dataclass(frozen=True)
class Claim:
    """A structured statement about the game world.

    location: players[0] was in `zone` during `window`
    together: players[0] and players[1] were both in `zone` during `window`
    absent:   players[0] was NOT in `zone` during `window`
    """
    claim_type: ClaimType
    players: tuple[str, ...]
    zone: str
    window: int
    is_lie: bool
    strategy: str = ""  # why the liar chose it (logged, never spoken)


@dataclass
class Statement:
    claim: Claim
    text: str  # rendered by code from the claim, never by the LLM
    source: str  # "template" | "heuristic" | "llm" | "truth"


@dataclass
class Vote:
    voter: str
    statement_idx: int
    believes_true: bool


@dataclass
class GameResult:
    statements: list[Statement] = field(default_factory=list)
    votes: list[Vote] = field(default_factory=list)
