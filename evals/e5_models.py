"""E5: model tradeoff. Same simulated game states, several models: how often does each model's
output pass the validator, how fast is it, what does a game cost?

THIS SCRIPT CALLS THE CLAUDE API AND COSTS MONEY. It refuses to run without --yes.
Rough cost per state: a few thousand input tokens + ~1k output tokens per model.

    python -m evals.e5_models --states 10 --yes
    python -m evals.e5_models --models claude-haiku-5-5 --states 5 --yes
"""
from __future__ import annotations

import argparse
import statistics

from hub import db
from hub.llm import LLMLiar
from hub.rounds import truth_so_far
from hub.validator import accept
from sim.world import simulate

MODELS = ["claude-haiku-5-5", "claude-sonnet-5-5", "claude-opus-5-5"]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", default=MODELS)
    ap.add_argument("--states", type=int, default=10)
    ap.add_argument("--yes", action="store_true", help="confirm you accept the API cost")
    a = ap.parse_args(argv)
    if not a.yes:
        print(__doc__)
        return 2
    print("model              | valid lies | valid truths | rejected | p50 ms | p95 ms | $/call  | errors")
    for model in a.models:
        con = db.connect()
        liar = LLMLiar(con=con, model=model)
        ok_l = ok_t = rej = 0
        for seed in range(a.states):
            w = simulate(seed, duration_s=240)
            truth = truth_so_far(w.pings, w.zone_of_beacon, 240_000)
            accepted, rejected = accept(liar.propose(truth, w.zones, 4, 2), truth, set(w.zones), model)
            ok_l += sum(s.claim.is_lie for s in accepted)
            ok_t += sum(not s.claim.is_lie for s in accepted)
            rej += len(rejected)
        calls = con.execute("SELECT latency_ms, cost_usd, ok FROM llm_calls").fetchall()
        lat = sorted(c[0] for c in calls if c[2]) or [0]
        cost = statistics.mean(c[1] for c in calls) if calls else 0
        errs = sum(1 for c in calls if not c[2])
        p95 = lat[min(len(lat) - 1, int(0.95 * len(lat)))]
        print(f"{model:<18} | {ok_l:>4}/{2 * a.states:<5} | {ok_t:>5}/{2 * a.states:<6} | {rej:>8} | "
              f"{statistics.median(lat):>6.0f} | {p95:>6} | {cost:7.4f} | {errs}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
