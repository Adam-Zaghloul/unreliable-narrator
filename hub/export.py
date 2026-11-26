"""Anonymised dataset export: one JSONL file per session, names replaced by P1..Pn.

Raw RSSI pings are NOT exported (they are a movement trace); only the 10 s zone estimates,
statements, votes and LLM call costs. Statement text is re-rendered with the anonymous names.

    python -m hub.export sessions/*.db --out dataset.jsonl
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from .model import Claim
from .validator import render


def session_records(path: Path) -> list[dict]:
    con = sqlite3.connect(path)
    meta = dict(con.execute("SELECT key, value FROM meta"))
    names = sorted({r[0] for r in con.execute("SELECT player FROM zone_estimates")} |
                   {r[0] for r in con.execute("SELECT voter FROM votes")})
    anon = {n: f"P{i + 1}" for i, n in enumerate(names)}
    sid = path.stem
    arms = dict(con.execute("SELECT round, arm FROM rounds"))
    out = [{"type": "session", "session": sid, "mode": meta.get("mode"), "arms": meta.get("arms"),
            "n_players": len(names)}]
    for p, w, z, c in con.execute("SELECT player, window, zone, confidence FROM zone_estimates"):
        out.append({"type": "zone", "session": sid, "player": anon[p], "window": w, "zone": z,
                    "confidence": round(c, 3)})
    for idx, rnd, src, ctype, ps, zone, w, lie, strat in con.execute(
            "SELECT idx, round, source, claim_type, players, zone, window, is_lie, strategy FROM statements"):
        players = tuple(anon[p] for p in json.loads(ps))
        text = render(Claim(ctype, players, zone, w, bool(lie)))
        out.append({"type": "statement", "session": sid, "idx": idx, "round": rnd, "round_arm": arms.get(rnd),
                    "source": src, "claim_type": ctype, "players": list(players), "zone": zone, "window": w,
                    "is_lie": bool(lie), "strategy": strat, "text": text})
    for voter, idx, b in con.execute("SELECT voter, statement_idx, believes_true FROM votes"):
        out.append({"type": "vote", "session": sid, "voter": anon[voter], "idx": idx, "believes_true": bool(b)})
    for model, it, ot, lat, cost, ok in con.execute(
            "SELECT model, input_tokens, output_tokens, latency_ms, cost_usd, ok FROM llm_calls"):
        out.append({"type": "llm_call", "session": sid, "model": model, "input_tokens": it, "output_tokens": ot,
                    "latency_ms": lat, "cost_usd": cost, "ok": bool(ok)})
    return out


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("dbs", nargs="+")
    ap.add_argument("--out", default="dataset.jsonl")
    a = ap.parse_args(argv)
    n = 0
    with open(a.out, "w") as f:
        for d in a.dbs:
            for rec in session_records(Path(d)):
                f.write(json.dumps(rec) + "\n")
                n += 1
    print(f"wrote {n} records to {a.out}")


if __name__ == "__main__":
    main()
