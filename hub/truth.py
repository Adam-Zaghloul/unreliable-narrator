"""Truth engine: turns noisy RSSI pings into "player X was in zone Z during window W".

This is the part you must be able to defend in an interview, so it is kept small.

Per player, per 10 s window:
1. Group pings by beacon and take the MEDIAN RSSI (robust to single spikes).
2. The candidate zone is the beacon with the strongest median (needs >= MIN_SAMPLES).
3. Hysteresis: if the previous window's zone is still heard and its median is within
   HYSTERESIS_DB of the best, keep the previous zone. Stops flicker at room boundaries.
4. Confidence = share of packets in the window whose own strongest beacon is the chosen zone.

A fact is only usable by the narrator when it is CONFIDENT (>= MIN_CONFIDENCE) and
STABLE (same confident zone in the previous or next window, i.e. held for >= 20 s).
"""
from __future__ import annotations

from collections import defaultdict
from statistics import median

from .model import WINDOW_S, Ping, ZoneEstimate

MIN_SAMPLES = 2
HYSTERESIS_DB = 4.0
MIN_CONFIDENCE = 0.8


def window_of(t_ms: int) -> int:
    return t_ms // (WINDOW_S * 1000)


def estimate_zones(pings: list[Ping], zone_of_beacon: dict[str, str]) -> dict[tuple[str, int], ZoneEstimate]:
    """Return {(player, window): ZoneEstimate} for every player/window that has pings."""
    # by_pw[(player, window)][beacon] -> list of rssi
    by_pw: dict[tuple[str, int], dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    # per packet (player, t_ms) -> strongest beacon, for confidence
    packets: dict[tuple[str, int], dict[int, tuple[str, float]]] = defaultdict(dict)
    for p in pings:
        if p.beacon not in zone_of_beacon:
            continue  # another badge or an unknown device; zones only come from beacons
        w = window_of(p.t_ms)
        by_pw[(p.badge, w)][p.beacon].append(p.rssi)
        best = packets[(p.badge, w)].get(p.t_ms)
        if best is None or p.rssi > best[1]:
            packets[(p.badge, w)][p.t_ms] = (p.beacon, p.rssi)

    out: dict[tuple[str, int], ZoneEstimate] = {}
    players = sorted({pl for pl, _ in by_pw})
    for player in players:
        windows = sorted(w for pl, w in by_pw if pl == player)
        prev_zone: str | None = None
        for w in windows:
            medians = {b: median(v) for b, v in by_pw[(player, w)].items() if len(v) >= MIN_SAMPLES}
            if not medians:
                out[(player, w)] = ZoneEstimate(player, w, None, 0.0)
                prev_zone = None
                continue
            best_beacon = max(medians, key=medians.get)
            chosen = best_beacon
            if prev_zone is not None:
                prev_beacons = [b for b in medians if zone_of_beacon[b] == prev_zone]
                if prev_beacons:
                    prev_best = max(prev_beacons, key=medians.get)
                    if medians[best_beacon] - medians[prev_best] < HYSTERESIS_DB:
                        chosen = prev_best
            zone = zone_of_beacon[chosen]
            pk = packets[(player, w)].values()
            agree = sum(1 for b, _ in pk if zone_of_beacon[b] == zone)
            conf = agree / len(pk) if pk else 0.0
            out[(player, w)] = ZoneEstimate(player, w, zone, conf)
            prev_zone = zone
    return out


class Truth:
    """Read-only view used by the validator, liars and simulated voters."""

    def __init__(self, estimates: dict[tuple[str, int], ZoneEstimate]):
        self.est = estimates
        self.players = sorted({p for p, _ in estimates})
        self.windows = sorted({w for _, w in estimates})

    def zone(self, player: str, window: int) -> str | None:
        e = self.est.get((player, window))
        return e.zone if e else None

    def confident(self, player: str, window: int) -> bool:
        e = self.est.get((player, window))
        return bool(e and e.zone and e.confidence >= MIN_CONFIDENCE)

    def stable(self, player: str, window: int) -> bool:
        """Confident here AND the same confident zone in a neighbouring window (held >= 20 s)."""
        if not self.confident(player, window):
            return False
        z = self.zone(player, window)
        return any(self.confident(player, n) and self.zone(player, n) == z for n in (window - 1, window + 1))

    def who_was_in(self, zone: str, window: int) -> list[str]:
        """Players confidently in `zone` during `window` (these are the possible witnesses)."""
        return [p for p in self.players if self.confident(p, window) and self.zone(p, window) == zone]
