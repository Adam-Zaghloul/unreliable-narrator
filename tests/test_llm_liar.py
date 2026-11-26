"""LLMLiar with a fake client: no network, no cost. Checks parsing, logging and fallbacks."""
import json
from types import SimpleNamespace

from hub import db
from hub.llm import LLMLiar
from hub.truth import Truth, estimate_zones
from sim.world import simulate


class FakeClient:
    def __init__(self, payload, stop_reason="end_turn"):
        self.payload, self.stop_reason, self.calls = payload, stop_reason, []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self.create))

    def create(self, **kw):
        self.calls.append(kw)
        return SimpleNamespace(
            stop_reason=self.stop_reason,
            usage=SimpleNamespace(input_tokens=1000, output_tokens=200),
            content=[SimpleNamespace(type="text", text=json.dumps(self.payload))],
        )


def world_truth():
    w = simulate(1)
    return w, Truth(estimate_zones(w.pings, w.zone_of_beacon))


def test_parses_claims_and_logs_cost():
    w, t = world_truth()
    payload = {"statements": [{"claim_type": "location", "players": ["Sara"], "zone": "kitchen", "window": 3,
                               "is_lie": True, "strategy": "nobody saw her"}]}
    con = db.connect()
    claims = LLMLiar(con=con, client=FakeClient(payload), model="claude-haiku-5-5").propose(t, w.zones, 1, 1)
    assert claims[0].players == ("Sara",) and claims[0].is_lie
    row = con.execute("SELECT model, input_tokens, cost_usd, ok FROM llm_calls").fetchone()
    assert row[0] == "claude-haiku-5-5" and row[1] == 1000 and row[2] > 0 and row[3] == 1


def test_refusal_falls_back_to_template():
    w, t = world_truth()
    con = db.connect()
    claims = LLMLiar(con=con, client=FakeClient({}, stop_reason="refusal")).propose(t, w.zones, 4, 2)
    assert len(claims) == 4
    assert con.execute("SELECT error FROM llm_calls").fetchone()[0] == "refusal"


def test_prompt_contains_only_confident_facts():
    w, t = world_truth()
    fake = FakeClient({"statements": []})
    LLMLiar(client=fake).propose(t, w.zones, 4, 2)
    prompt = fake.calls[0]["messages"][0]["content"]
    assert "Facts (certain)" in prompt and "exactly 2 are lies" in prompt
