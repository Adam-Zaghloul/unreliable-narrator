"""LLMLiar: Claude chooses which lies to tell. It never decides what is true.

The model gets the confident facts (who was where, when) plus the vote history, and returns
structured claims with an `is_lie` label. The validator recomputes every label; mismatches
are rejected and logged. On any failure it returns nothing and the round is topped up by the
template liar (marked "template-fill"), so a game never stalls and no fallback counts as "llm".
Every call is logged with tokens, latency and an estimated cost.
"""
from __future__ import annotations

import json
import os
import time

from .liars import stable_facts
from .model import Claim
from .truth import Truth
from .validator import fmt_time

DEFAULT_MODEL = os.environ.get("NARRATOR_MODEL", "claude-opus-5-5")
# USD per million tokens (input, output). Update if prices change.
PRICES = {
    "claude-opus-5-5": (4.00, 20.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
}

SYSTEM = """You are the narrator of an in-person party game. You are secretly the traitor.
Players walked between rooms. You will receive the facts the sensors are certain about.
Your job: propose statements about where players were. Some must be lies.
The players win by catching your lies from their own memory; you win if they believe lies
and start distrusting each other.

Rules you must follow:
- Use only the players, zones and windows given. Claims are only about location.
- claim_type "location": players=[one name], "they were in zone".
- claim_type "together": players=[two names], "both were in zone". Never claim anyone was alone.
- claim_type "absent": players=[one name], "they were NOT in zone".
- is_lie must be true exactly when the claim contradicts the facts.
- Good lies are about moments few other players witnessed, and are plausible
  (a room the player visited around that time). Spread lies across different players.
- In "strategy", say in under 12 words why you chose this statement."""

CLAIM_SCHEMA = {
    "type": "object",
    "properties": {
        "statements": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "claim_type": {"type": "string", "enum": ["location", "together", "absent"]},
                    "players": {"type": "array", "items": {"type": "string"}},
                    "zone": {"type": "string"},
                    "window": {"type": "integer"},
                    "is_lie": {"type": "boolean"},
                    "strategy": {"type": "string"},
                },
                "required": ["claim_type", "players", "zone", "window", "is_lie", "strategy"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["statements"],
    "additionalProperties": False,
}


def facts_table(truth: Truth) -> str:
    rows = ["window | time | player | zone | others in that zone"]
    for p, w, z in stable_facts(truth):
        others = [q for q in truth.who_was_in(z, w) if q != p]
        rows.append(f"{w} | {fmt_time(w)} | {p} | {z} | {', '.join(others) or '-'}")
    return "\n".join(rows)


def build_prompt(truth: Truth, zones: list[str], n: int, n_lies: int, history: list[dict] | None) -> str:
    hist = "\n".join(
        f"- {h['text']} (lie={h['is_lie']}, believed by {h['believed']}/{h['voters']})" for h in (history or [])
    ) or "- none yet"
    return (
        f"Players: {', '.join(truth.players)}\nZones: {', '.join(zones)}\n\n"
        f"Facts (certain):\n{facts_table(truth)}\n\n"
        f"Earlier statements and how players voted:\n{hist}\n\n"
        f"Propose exactly {n} new statements, of which exactly {n_lies} are lies."
    )


class LLMLiar:
    name = "llm"

    def __init__(self, con=None, model: str = DEFAULT_MODEL, client=None, seed: int = 0):
        self.con = con
        self.model = model
        self.client = client

    def _client(self):
        if self.client is None:
            import anthropic
            self.client = anthropic.Anthropic()
        return self.client

    def _log(self, **row):
        if self.con is not None:
            from .db import log_llm_call
            log_llm_call(self.con, **row)

    def propose(self, truth: Truth, zones: list[str], n: int, n_lies: int, history=None) -> list[Claim]:
        import anthropic

        prompt = build_prompt(truth, zones, n, n_lies, history)
        t0 = time.time()
        try:
            resp = self._client().beta.messages.create(
                model=self.model,
                max_tokens=16000,
                system=SYSTEM,
                messages=[{"role": "user", "content": prompt}],
                output_config={"effort": "medium", "format": {"type": "json_schema", "schema": CLAIM_SCHEMA}},
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except (anthropic.APIStatusError, anthropic.APIConnectionError, TypeError) as e:
            # TypeError = no credentials configured. Return nothing: the round is topped up by the
            # template liar and those statements are marked "template-fill", never "llm".
            self._log(t=t0, model=self.model, input_tokens=0, output_tokens=0,
                      latency_ms=int((time.time() - t0) * 1000), cost_usd=0.0, stop_reason=None, ok=0,
                      error=f"{type(e).__name__}: {str(e)[:120]}")
            return []

        latency = int((time.time() - t0) * 1000)
        pin, pout = PRICES.get(self.model, (0.0, 0.0))
        u = resp.usage
        cost = (u.input_tokens * pin + u.output_tokens * pout) / 1e6
        if resp.stop_reason == "refusal":
            self._log(t=t0, model=self.model, input_tokens=u.input_tokens, output_tokens=u.output_tokens,
                      latency_ms=latency, cost_usd=cost, stop_reason="refusal", ok=0, error="refusal")
            return []

        text = next(b.text for b in resp.content if b.type == "text")
        data = json.loads(text)
        self._log(t=t0, model=self.model, input_tokens=u.input_tokens, output_tokens=u.output_tokens,
                  latency_ms=latency, cost_usd=cost, stop_reason=resp.stop_reason, ok=1, error=None)
        return [
            Claim(s["claim_type"], tuple(s["players"]), s["zone"], int(s["window"]), bool(s["is_lie"]),
                  s["strategy"][:120])
            for s in data["statements"]
        ]
