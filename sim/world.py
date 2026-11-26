"""Synthetic game world so the whole hub runs with no hardware.

Everything produced here is SIMULATED. Numbers computed from it are development checks,
never reported as human results.

Model (deliberately simple, tune it against bench data later):
- Players dwell in a zone 20-90 s, then walk to another zone.
- Each badge sends a packet every 2 s with one RSSI per beacon it hears.
- RSSI: own-zone beacon around -55 dBm, other zones around -80 dBm, Gaussian noise,
  random packet loss, and occasional body-shadowing (-12 dB on the own-zone beacon).
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from hub.model import PACKET_PERIOD_S, WINDOW_S, Ping

DEFAULT_ZONES = ["kitchen", "living room", "hallway", "balcony"]
DEFAULT_PLAYERS = ["Sara", "Karim", "Lina", "Omar", "Maya", "Theo"]


@dataclass
class World:
    zones: list[str]
    players: list[str]
    duration_s: int
    true_zone: dict[tuple[str, int], str]  # (player, t_s) -> zone, ground truth per second
    pings: list[Ping]
    zone_of_beacon: dict[str, str]

    def true_zone_in_window(self, player: str, window: int) -> str:
        """Majority true zone over the window (what the player actually lived)."""
        counts: dict[str, int] = {}
        for t in range(window * WINDOW_S, (window + 1) * WINDOW_S):
            z = self.true_zone.get((player, t))
            if z:
                counts[z] = counts.get(z, 0) + 1
        return max(counts, key=counts.get)


def simulate(seed: int = 0, players: list[str] | None = None, zones: list[str] | None = None,
             duration_s: int = 360, noise_db: float = 4.0, loss: float = 0.15,
             shadow_p: float = 0.08) -> World:
    rng = random.Random(seed)
    players = players or DEFAULT_PLAYERS
    zones = zones or DEFAULT_ZONES
    zone_of_beacon = {f"B{i + 1}": z for i, z in enumerate(zones)}
    beacon_of_zone = {z: b for b, z in zone_of_beacon.items()}

    true_zone: dict[tuple[str, int], str] = {}
    for p in players:
        t, z = 0, rng.choice(zones)
        while t < duration_s:
            dwell = rng.randint(20, 90)
            for s in range(t, min(t + dwell, duration_s)):
                true_zone[(p, s)] = z
            t += dwell
            z = rng.choice([x for x in zones if x != z])

    pings: list[Ping] = []
    for p in players:
        offset = rng.randint(0, PACKET_PERIOD_S * 1000 - 1)  # badges are not synchronised
        for t_ms in range(offset, duration_s * 1000, PACKET_PERIOD_S * 1000):
            here = true_zone[(p, t_ms // 1000)]
            shadowed = rng.random() < shadow_p
            for z in zones:
                if rng.random() < loss:
                    continue
                base = -55.0 if z == here else -80.0
                if z == here and shadowed:
                    base -= 12.0
                pings.append(Ping(p, t_ms, beacon_of_zone[z], base + rng.gauss(0, noise_db)))
    return World(zones, players, duration_s, true_zone, pings, zone_of_beacon)


def pick_witness_pings(world: World, rng: random.Random, every_s: int = 45) -> dict[str, list[int]]:
    """Which windows each player's badge buzzed in. A buzz makes that moment memorable."""
    buzz: dict[str, list[int]] = {p: [] for p in world.players}
    for t in range(every_s, world.duration_s, every_s):
        p = rng.choice(world.players)
        buzz[p].append(t // WINDOW_S)
    return buzz


@dataclass
class SimVoter:
    """A crude human: remembers what they saw, guesses otherwise.

    - If the voter was in the claimed zone at that time, they saw who was there
      (p_see, higher if their badge buzzed then) and vote correctly.
    - If the claim is about the voter themself, they know the answer.
    - Otherwise they believe the narrator with probability `credulity`.
    """
    name: str
    p_see: float = 0.75
    p_see_buzzed: float = 0.95
    credulity: float = 0.65

    def vote(self, claim, world: World, buzzed_windows: list[int], rng: random.Random) -> bool:
        actual_true = not claim.is_lie
        if self.name in claim.players:
            return actual_true
        my_zone = world.true_zone_in_window(self.name, claim.window)
        involved = {claim.zone} | {world.true_zone_in_window(p, claim.window) for p in claim.players}
        if my_zone in involved:
            p = self.p_see_buzzed if claim.window in buzzed_windows else self.p_see
            if rng.random() < p:
                return actual_true
        return rng.random() < self.credulity
