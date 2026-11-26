"""One round's statements, shared by the simulator game and the live game."""
from __future__ import annotations

import random

from . import db
from .liars import HeuristicLiar, TemplateLiar
from .model import Statement
from .truth import Truth, estimate_zones, window_of
from .validator import accept

ARMS = ("template", "heuristic", "llm")


def make_liar(kind: str, con, seed: int):
    if kind == "template":
        return TemplateLiar(seed)
    if kind == "heuristic":
        return HeuristicLiar(seed)
    if kind == "llm":
        from .llm import LLMLiar
        return LLMLiar(con=con, seed=seed)
    raise ValueError(f"unknown liar {kind!r}")


def arm_order(session: int) -> list[str]:
    """Counterbalanced liar order for a 3-round session (cycles through all 6 permutations)."""
    perms = [(0, 1, 2), (1, 2, 0), (2, 0, 1), (0, 2, 1), (2, 1, 0), (1, 0, 2)]
    return [ARMS[i] for i in perms[session % 6]]


def truth_so_far(pings, zone_of_beacon, now_ms: int) -> Truth:
    truth = Truth(estimate_zones([p for p in pings if p.t_ms < now_ms], zone_of_beacon))
    # only talk about the past, and not the last window (it may still be changing)
    truth.windows = [w for w in truth.windows if w < window_of(now_ms) - 1]
    return truth


def round_statements(rnd: int, truth: Truth, zones: list[str], liar, fill: TemplateLiar, con, n: int, n_lies: int,
                     history: list[dict], used: set[str], rng: random.Random) -> list[Statement]:
    """Exactly n statements with exactly n_lies lies (if the data allows), all validated.

    The liar's own proposals come first; any shortfall is topped up from the template liar and
    marked source="template-fill" so the analysis can exclude it.
    """
    zset = set(zones)
    con.execute("INSERT OR REPLACE INTO rounds VALUES (?,?)", (rnd, liar.name))
    accepted, rejected = accept(liar.propose(truth, zones, n, n_lies, history), truth, zset, liar.name)
    for c, why in rejected:
        db.save_rejected(con, rnd, liar.name, c, why)
    n_truths = n - n_lies
    lies, truths = [], []
    for s in accepted:
        bucket, cap = (lies, n_lies) if s.claim.is_lie else (truths, n_truths)
        if len(bucket) < cap and s.text not in used:
            bucket.append(s)
            used.add(s.text)
    tries = 0
    while (len(lies) < n_lies or len(truths) < n_truths) and tries < 30:
        tries += 1
        extra, _ = accept(fill.propose(truth, zones, 2, 1), truth, zset, "template-fill")
        for s in extra:
            bucket, cap = (lies, n_lies) if s.claim.is_lie else (truths, n_truths)
            if len(bucket) < cap and s.text not in used:
                bucket.append(s)
                used.add(s.text)
    out = lies + truths
    rng.shuffle(out)
    return out
