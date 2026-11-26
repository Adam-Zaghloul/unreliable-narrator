from hub.model import Ping
from hub.truth import Truth, estimate_zones
from sim.world import simulate

ZONES = {"B1": "kitchen", "B2": "hallway"}


def pings_for(player, t0_s, t1_s, strong, weak=-80.0, step_ms=2000):
    out = []
    for t in range(t0_s * 1000, t1_s * 1000, step_ms):
        out.append(Ping(player, t, strong, -55.0))
        out.append(Ping(player, t, "B2" if strong == "B1" else "B1", weak))
    return out


def test_clear_signal_gives_confident_zone():
    est = estimate_zones(pings_for("Sara", 0, 30, "B1"), ZONES)
    t = Truth(est)
    assert t.zone("Sara", 1) == "kitchen"
    assert t.confident("Sara", 1)
    assert t.stable("Sara", 1)


def test_hysteresis_keeps_zone_on_small_difference():
    # window 0 clearly kitchen, window 1 hallway only 2 dB stronger -> stay in kitchen
    p = pings_for("Sara", 0, 10, "B1")
    for t in range(10_000, 20_000, 2000):
        p += [Ping("Sara", t, "B1", -60.0), Ping("Sara", t, "B2", -58.0)]
    t = Truth(estimate_zones(p, ZONES))
    assert t.zone("Sara", 1) == "kitchen"


def test_single_window_is_not_stable():
    p = pings_for("Sara", 0, 10, "B1") + pings_for("Sara", 10, 20, "B2", weak=-90)
    t = Truth(estimate_zones(p, ZONES))
    assert t.confident("Sara", 0) and not t.stable("Sara", 0)


def test_window_next_to_a_room_change_is_not_stable():
    # kitchen for 20 s, then hallway for 20 s: windows 1 and 2 border the move, so neither is usable
    p = pings_for("Sara", 0, 20, "B1") + pings_for("Sara", 20, 40, "B2", weak=-90)
    t = Truth(estimate_zones(p, ZONES))
    assert [t.zone("Sara", w) for w in range(4)] == ["kitchen", "kitchen", "hallway", "hallway"]
    assert all(t.confident("Sara", w) for w in range(4))
    assert not t.stable("Sara", 1) and not t.stable("Sara", 2)


def test_other_badges_are_ignored():
    p = pings_for("Sara", 0, 20, "B1") + [Ping("Sara", 1000, "Karim", -30.0)]
    assert Truth(estimate_zones(p, ZONES)).zone("Sara", 0) == "kitchen"


def test_stable_facts_match_simulated_ground_truth():
    """In the simulator, facts the narrator may use must be >= 97% correct."""
    right = total = 0
    for seed in range(10):
        w = simulate(seed)
        t = Truth(estimate_zones(w.pings, w.zone_of_beacon))
        for p in t.players:
            for win in t.windows:
                if t.stable(p, win):
                    total += 1
                    right += t.zone(p, win) == w.true_zone_in_window(p, win)
    assert total > 500
    assert right / total >= 0.97, right / total
