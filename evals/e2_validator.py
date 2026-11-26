"""E2: the validator is a hard gate. Target 100% on every row.

300 simulated logs. For each, generate claims of every kind, including adversarial ones
(flipped labels, unknown players/zones, uncertain windows, banned claim types, duplicates),
and check that the validator's decision matches an independent re-derivation from the
SIMULATOR's ground truth (not from the truth engine the validator uses).

    python -m evals.e2_validator
"""
import random

from hub.model import Claim
from hub.truth import Truth, estimate_zones
from hub.validator import check
from sim.world import simulate

N_LOGS = 300


def main():
    rng = random.Random(0)
    stats = {"accepted lies that were really lies": [0, 0], "accepted truths that were really true": [0, 0],
             "adversarial claims rejected": [0, 0]}
    for seed in range(N_LOGS):
        w = simulate(seed, duration_s=120)
        t = Truth(estimate_zones(w.pings, w.zone_of_beacon))
        zones = set(w.zones)
        for _ in range(20):
            p = rng.choice(w.players)
            win = rng.choice(t.windows)
            z = rng.choice(w.zones)
            kind = rng.choice(["location", "absent", "together"])
            players = (p,) if kind != "together" else (p, rng.choice([q for q in w.players if q != p]))
            for is_lie in (True, False):
                c = Claim(kind, players, z, win, is_lie)
                v = check(c, t, zones)
                if not v.ok:
                    continue
                gt = [w.true_zone_in_window(x, win) for x in players]
                really_true = (gt[0] == z) if kind == "location" else (gt[0] != z) if kind == "absent" else all(g == z for g in gt)
                key = "accepted lies that were really lies" if is_lie else "accepted truths that were really true"
                stats[key][0] += (not really_true) if is_lie else really_true
                stats[key][1] += 1
            for bad in (
                Claim("location", ("Ghost",), z, win, False),
                Claim("location", (p,), "garage", win, True),
                Claim("alone_together", players, z, win, True),
                Claim("location", (p,), z, 10_000, False),
                Claim("together", (p, p), z, win, False),
            ):
                stats["adversarial claims rejected"][0] += not check(bad, t, zones).ok
                stats["adversarial claims rejected"][1] += 1
    print("E2 validator (SIMULATED logs, ground truth from the simulator)")
    for k, (good, n) in stats.items():
        print(f"{k:<40} {good}/{n} = {good / max(n, 1):.2%}")


if __name__ == "__main__":
    main()
