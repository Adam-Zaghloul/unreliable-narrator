"""E1 (simulated): how accurate are the facts the narrator is allowed to use?

Sweeps RSSI noise and reports, for STABLE facts only, accuracy vs simulated ground truth and
how many player-windows are usable (coverage). The real E1 replaces the simulator with
scripted walks on real hardware; this script is the template for that report.

    python -m evals.e1_zone_accuracy
"""
from hub.truth import Truth, estimate_zones
from sim.world import simulate

SEEDS = 20


def run(noise_db: float, shadow_p: float):
    right = total = cells = 0
    for seed in range(SEEDS):
        w = simulate(seed, noise_db=noise_db, shadow_p=shadow_p)
        t = Truth(estimate_zones(w.pings, w.zone_of_beacon))
        for p in t.players:
            for win in t.windows:
                cells += 1
                if t.stable(p, win):
                    total += 1
                    right += t.zone(p, win) == w.true_zone_in_window(p, win)
    return right / max(total, 1), total / max(cells, 1)


if __name__ == "__main__":
    print("SIMULATED. noise_dB | body-shadow p | accuracy of stable facts | coverage")
    for noise in (2, 4, 6, 8, 10):
        for shadow in (0.08, 0.25):
            acc, cov = run(noise, shadow)
            print(f"{noise:>8} | {shadow:>13} | {acc:>24.1%} | {cov:>8.1%}")
