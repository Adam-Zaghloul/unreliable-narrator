"""Run a game end to end. Today: in the simulator. Later: the same loop fed by the gateway.

    python -m hub.game                      # one simulated game, template liar
    python -m hub.game --liar heuristic     # hand-written strategic liar (no AI)
    python -m hub.game --liar llm           # Claude picks the lies (needs API access, costs cents)
    python -m hub.game --speak              # read statements aloud (macOS `say`)
    python -m hub.game --compare 50         # SIMULATED comparison of liars over 50 seeds
"""
from __future__ import annotations

import argparse
import random
import subprocess
import sys

from sim.world import SimVoter, pick_witness_pings, simulate

from . import db
from .liars import TemplateLiar
from .model import GameResult, Vote
from .rounds import make_liar, round_statements, truth_so_far
from .truth import estimate_zones

ROUNDS = 3
STATEMENTS_PER_ROUND = 4
LIES_PER_ROUND = 2


def play(seed: int = 0, liar_kind: str = "template", con=None, speak: bool = False, quiet: bool = False) -> GameResult:
    con = con or db.connect()
    rng = random.Random(seed + 1000)
    world = simulate(seed)
    buzz = pick_witness_pings(world, rng)
    voters = [SimVoter(p) for p in world.players]
    db.save_pings(con, world.pings)
    con.executemany("INSERT INTO buzzes VALUES (?,?)", [(p, w) for p, ws in buzz.items() for w in ws])
    con.execute("INSERT OR REPLACE INTO meta VALUES ('mode','SIMULATED'),('liar',?),('seed',?)", (liar_kind, seed))

    liar = make_liar(liar_kind, con, seed)
    fill = TemplateLiar(seed + 1)
    result = GameResult()
    history: list[dict] = []
    round_len_ms = world.duration_s * 1000 // ROUNDS

    used: set[str] = set()
    for rnd in range(1, ROUNDS + 1):
        truth = truth_so_far(world.pings, world.zone_of_beacon, rnd * round_len_ms)
        statements = round_statements(rnd, truth, world.zones, liar, fill, con, STATEMENTS_PER_ROUND,
                                      LIES_PER_ROUND, history, used, rng)
        for st in statements:
            idx = len(result.statements)
            result.statements.append(st)
            db.save_statement(con, idx, rnd, st)
            if not quiet:
                print(f"[round {rnd}] NARRATOR: {st.text}")
            if speak:
                subprocess.run(["say", st.text], check=False)
            believed = 0
            for v in voters:
                b = v.vote(st.claim, world, buzz[v.name], rng)
                result.votes.append(Vote(v.name, idx, b))
                con.execute("INSERT INTO votes VALUES (?,?,?)", (v.name, idx, int(b)))
                believed += b
            history.append({"text": st.text, "is_lie": st.claim.is_lie, "believed": believed, "voters": len(voters)})

    db.save_estimates(con, estimate_zones(world.pings, world.zone_of_beacon))
    con.commit()
    if not quiet:
        print_reveal(result)
    return result


def metrics(result: GameResult) -> dict:
    lie_idx = {i for i, s in enumerate(result.statements) if s.claim.is_lie}
    lie_votes = [v for v in result.votes if v.statement_idx in lie_idx]
    true_votes = [v for v in result.votes if v.statement_idx not in lie_idx]
    return {
        "lie_acceptance": sum(v.believes_true for v in lie_votes) / max(len(lie_votes), 1),
        "truth_rejection": sum(not v.believes_true for v in true_votes) / max(len(true_votes), 1),
        "n_statements": len(result.statements),
        "n_votes": len(result.votes),
    }


def print_reveal(result: GameResult) -> None:
    print("\n=== REVEAL (simulated players) ===")
    for i, s in enumerate(result.statements):
        believers = [v.voter for v in result.votes if v.statement_idx == i and v.believes_true]
        tag = "LIE " if s.claim.is_lie else "TRUE"
        print(f"{tag} [{s.source}] {s.text}  believed by: {', '.join(believers) or 'nobody'}")
    m = metrics(result)
    print(f"\nlie acceptance {m['lie_acceptance']:.0%} | truth rejection {m['truth_rejection']:.0%} "
          f"| {m['n_statements']} statements, {m['n_votes']} votes")


def compare(n: int, kinds: list[str]) -> None:
    print(f"SIMULATED comparison over {n} seeds. Simulated voters, not people. Dev check only.\n")
    print("liar       | lie acceptance | truth rejection")
    for k in kinds:
        ms = [metrics(play(seed, k, quiet=True)) for seed in range(n)]
        la = sum(m["lie_acceptance"] for m in ms) / n
        tr = sum(m["truth_rejection"] for m in ms) / n
        print(f"{k:<10} | {la:14.0%} | {tr:15.0%}")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--liar", default="template", choices=["template", "heuristic", "llm"])
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--speak", action="store_true")
    ap.add_argument("--db", default=None, help="save the session to this SQLite file")
    ap.add_argument("--compare", type=int, default=0, metavar="N")
    a = ap.parse_args(argv)
    if a.compare:
        compare(a.compare, ["template", "heuristic"])
        return
    con = db.connect(a.db) if a.db else None
    play(a.seed, a.liar, con=con, speak=a.speak)


if __name__ == "__main__":
    sys.exit(main())
