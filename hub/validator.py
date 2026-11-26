"""Validator: the only thing allowed to decide whether a claim is a lie.

The liar (template, heuristic or LLM) proposes structured claims with an `is_lie` label.
This module recomputes the label from the truth engine and rejects the claim unless:
- every player and zone in it exists,
- every fact it depends on is STABLE (no lying or truth-telling about uncertain data),
- the recomputed label equals the proposed `is_lie`,
- it is not a banned claim type (see BANNED below).

Spoken text is rendered here from the structured claim, so the LLM never writes free text
that a player hears. That removes a whole class of safety and hallucination failures.
"""
from __future__ import annotations

from dataclasses import dataclass

from .model import WINDOW_S, Claim, Statement
from .truth import Truth

MAX_PLAYERS_PER_CLAIM = 2
# Why each rule exists:
# - no "alone together" claims: they insinuate private or romantic situations between real people
# - max 2 players: keeps claims checkable from memory and stops "everyone except X" pile-ons
# - only location facts: nothing about what anyone did, said or felt


@dataclass
class Verdict:
    ok: bool
    reason: str
    actual_is_lie: bool | None = None


def fmt_time(window: int) -> str:
    s = window * WINDOW_S
    return f"{s // 60}:{s % 60:02d}"


ON_ZONES = {"balcony", "porch", "terrace", "deck", "stairs"}


def place(zone: str) -> str:
    return f"{'on' if zone in ON_ZONES else 'in'} the {zone}"


def render(claim: Claim) -> str:
    t = fmt_time(claim.window)
    p = claim.players
    if claim.claim_type == "location":
        return f"At {t}, {p[0]} was {place(claim.zone)}."
    if claim.claim_type == "together":
        return f"At {t}, {p[0]} and {p[1]} were both {place(claim.zone)}."
    return f"At {t}, {p[0]} was not {place(claim.zone)}."


def check(claim: Claim, truth: Truth, zones: set[str]) -> Verdict:
    if claim.claim_type not in ("location", "together", "absent"):
        return Verdict(False, f"banned or unknown claim type {claim.claim_type!r}")
    need = 2 if claim.claim_type == "together" else 1
    if len(claim.players) != need or len(claim.players) > MAX_PLAYERS_PER_CLAIM:
        return Verdict(False, f"{claim.claim_type} needs exactly {need} player(s)")
    if len(set(claim.players)) != len(claim.players):
        return Verdict(False, "duplicate player")
    if claim.zone not in zones:
        return Verdict(False, f"unknown zone {claim.zone!r}")
    for p in claim.players:
        if p not in truth.players:
            return Verdict(False, f"unknown player {p!r}")
        if not truth.stable(p, claim.window):
            return Verdict(False, f"{p} position at window {claim.window} is not certain enough")

    zs = [truth.zone(p, claim.window) for p in claim.players]
    if claim.claim_type == "location":
        true = zs[0] == claim.zone
    elif claim.claim_type == "together":
        true = zs[0] == claim.zone and zs[1] == claim.zone
    else:  # absent
        true = zs[0] != claim.zone
    actual_is_lie = not true
    if actual_is_lie != claim.is_lie:
        return Verdict(False, f"label mismatch: proposed is_lie={claim.is_lie}, actual={actual_is_lie}", actual_is_lie)
    return Verdict(True, "ok", actual_is_lie)


def accept(claims: list[Claim], truth: Truth, zones: set[str], source: str) -> tuple[list[Statement], list[tuple[Claim, str]]]:
    """Split proposals into accepted statements and (claim, reason) rejections."""
    ok, rejected = [], []
    seen = set()
    for c in claims:
        key = (c.claim_type, c.players, c.zone, c.window)
        if key in seen:
            rejected.append((c, "duplicate claim"))
            continue
        v = check(c, truth, zones)
        if v.ok:
            seen.add(key)
            ok.append(Statement(c, render(c), source))
        else:
            rejected.append((c, v.reason))
    return ok, rejected
