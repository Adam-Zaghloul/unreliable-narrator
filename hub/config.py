"""Game config (game.json). Player names are checked here because they are spoken aloud,
shown on the reveal page and sent to the LLM: a name is also a prompt-injection surface."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

NAME_RE = re.compile(r"^[A-Za-zÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ' -]{0,19}$")
ZONE_RE = re.compile(r"^[a-z][a-z ]{0,23}$")


@dataclass
class GameConfig:
    players: dict[int, str]  # badge id -> name
    zones: dict[int, str]  # beacon id -> room name
    rounds: int = 3
    round_minutes: float = 5.0
    statements_per_round: int = 4
    lies_per_round: int = 2
    vote_seconds: int = 15
    witness_ping_every_s: int = 45
    session: int = 0  # picks the counterbalanced liar order
    speak: bool = True
    errors: list[str] = field(default_factory=list)

    @property
    def zone_of_beacon(self) -> dict[str, str]:
        return {f"B{i}": z for i, z in self.zones.items()}

    @property
    def name_of_badge(self) -> dict[str, str]:
        return {str(i): n for i, n in self.players.items()}


def validate(cfg: GameConfig) -> list[str]:
    errs = []
    for bid, name in cfg.players.items():
        if not NAME_RE.match(name):
            errs.append(f"player name {name!r}: use 1-20 letters, spaces, ' or -")
    if len(set(n.lower() for n in cfg.players.values())) != len(cfg.players):
        errs.append("player names must be unique")
    for zid, zone in cfg.zones.items():
        if not ZONE_RE.match(zone):
            errs.append(f"zone {zone!r}: use 1-24 lowercase letters and spaces")
    if not 2 <= len(cfg.zones) <= 8:
        errs.append("use 2-8 zones")
    if not 3 <= len(cfg.players) <= 12:
        errs.append("use 3-12 players")
    if not 0 < cfg.lies_per_round < cfg.statements_per_round:
        errs.append("lies_per_round must be between 1 and statements_per_round - 1")
    return errs


def load(path: str) -> GameConfig:
    with open(path) as f:
        raw = json.load(f)
    cfg = GameConfig(
        players={int(k): v.strip() for k, v in raw["players"].items()},
        zones={int(k): v.strip() for k, v in raw["zones"].items()},
        **{k: raw[k] for k in ("rounds", "round_minutes", "statements_per_round", "lies_per_round",
                               "vote_seconds", "witness_ping_every_s", "session", "speak") if k in raw},
    )
    cfg.errors = validate(cfg)
    return cfg
