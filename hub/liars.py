"""Liars propose claims. They never decide truth: the validator re-checks every label.

Three liars, so the headline eval has two baselines to beat:
- TemplateLiar:  random true facts, random lies (mutate the zone). No strategy.
- HeuristicLiar: hand-written strategy, no AI: lie about moments nobody else witnessed,
                 and frame the player the group trusts most. If the LLM can't beat this,
                 the AI is decorative and the README must say so.
- LLMLiar:       Claude picks the lies (see llm.py).
"""
from __future__ import annotations

import random

from .model import Claim
from .truth import Truth


def stable_facts(truth: Truth) -> list[tuple[str, int, str]]:
    """(player, window, zone) for every stable fact."""
    return [(p, w, truth.zone(p, w)) for p in truth.players for w in truth.windows if truth.stable(p, w)]


def true_claim(rng: random.Random, truth: Truth, facts) -> Claim:
    p, w, z = rng.choice(facts)
    others = [q for q in truth.who_was_in(z, w) if q != p and truth.stable(q, w)]
    if others and rng.random() < 0.4:
        return Claim("together", (p, rng.choice(others)), z, w, False, "truth")
    return Claim("location", (p,), z, w, False, "truth")


def lie_about(p: str, w: int, z: str, zones: list[str], rng: random.Random, why: str) -> Claim:
    wrong = rng.choice([x for x in zones if x != z])
    if rng.random() < 0.25:
        return Claim("absent", (p,), z, w, True, why)  # "p was not in z" while p was there
    return Claim("location", (p,), wrong, w, True, why)


class TemplateLiar:
    name = "template"

    def __init__(self, seed: int = 0):
        self.rng = random.Random(seed)

    def propose(self, truth: Truth, zones: list[str], n: int, n_lies: int, history=None) -> list[Claim]:
        facts = stable_facts(truth)
        if not facts:
            return []
        out = [true_claim(self.rng, truth, facts) for _ in range(n - n_lies)]
        for _ in range(n_lies):
            p, w, z = self.rng.choice(facts)
            out.append(lie_about(p, w, z, zones, self.rng, "random"))
        self.rng.shuffle(out)
        return out


class HeuristicLiar(TemplateLiar):
    name = "heuristic"

    def propose(self, truth: Truth, zones: list[str], n: int, n_lies: int, history=None) -> list[Claim]:
        facts = stable_facts(truth)
        if not facts:
            return []
        out = [true_claim(self.rng, truth, facts) for _ in range(n - n_lies)]
        # fewest possible witnesses: nobody else was in the true zone or the claimed zone
        def witnesses(f):
            p, w, z = f
            return len([q for q in truth.who_was_in(z, w) if q != p])
        ranked = sorted(facts, key=lambda f: (witnesses(f), self.rng.random()))
        for p, w, z in ranked[: n_lies * 3][::3][:n_lies]:  # spread lies across moments
            wrong_zones = sorted(
                (x for x in zones if x != z), key=lambda x: (len(truth.who_was_in(x, w)), self.rng.random())
            )
            out.append(Claim("location", (p,), wrong_zones[0], w, True, "unwitnessed moment"))
        self.rng.shuffle(out)
        return out
