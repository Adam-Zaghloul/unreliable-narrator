from hub.model import Claim, Ping
from hub.truth import Truth, estimate_zones
from hub.validator import accept, check, render

ZONES = {"B1": "kitchen", "B2": "hallway", "B3": "balcony"}
ZSET = set(ZONES.values())


def make_truth():
    pings = []
    for t in range(0, 40_000, 2000):
        pings += [Ping("Sara", t, "B1", -55), Ping("Sara", t, "B2", -80), Ping("Sara", t, "B3", -82)]
        pings += [Ping("Karim", t, "B1", -56), Ping("Karim", t, "B2", -81), Ping("Karim", t, "B3", -83)]
        pings += [Ping("Lina", t, "B2", -54), Ping("Lina", t, "B1", -79), Ping("Lina", t, "B3", -80)]
    return Truth(estimate_zones(pings, ZONES))


T = make_truth()


def test_true_location_accepted():
    assert check(Claim("location", ("Sara",), "kitchen", 1, False), T, ZSET).ok


def test_lie_accepted_when_labelled_lie():
    assert check(Claim("location", ("Sara",), "hallway", 1, True), T, ZSET).ok


def test_label_mismatch_rejected_both_ways():
    assert not check(Claim("location", ("Sara",), "hallway", 1, False), T, ZSET).ok
    assert not check(Claim("location", ("Sara",), "kitchen", 1, True), T, ZSET).ok


def test_together_and_absent():
    assert check(Claim("together", ("Sara", "Karim"), "kitchen", 1, False), T, ZSET).ok
    assert check(Claim("together", ("Sara", "Lina"), "kitchen", 1, True), T, ZSET).ok
    assert check(Claim("absent", ("Lina",), "kitchen", 1, False), T, ZSET).ok
    assert not check(Claim("absent", ("Sara",), "kitchen", 1, False), T, ZSET).ok


def test_rejects_unknowns_and_bad_shapes():
    assert not check(Claim("location", ("Nobody",), "kitchen", 1, False), T, ZSET).ok
    assert not check(Claim("location", ("Sara",), "garage", 1, True), T, ZSET).ok
    assert not check(Claim("location", ("Sara", "Karim"), "kitchen", 1, False), T, ZSET).ok
    assert not check(Claim("together", ("Sara", "Sara"), "kitchen", 1, False), T, ZSET).ok
    assert not check(Claim("alone_together", ("Sara", "Karim"), "kitchen", 1, False), T, ZSET).ok


def test_rejects_windows_without_stable_data():
    assert not check(Claim("location", ("Sara",), "kitchen", 99, False), T, ZSET).ok


def test_rendered_text_comes_from_claim():
    assert render(Claim("location", ("Sara",), "balcony", 6, True)) == "At 1:00, Sara was on the balcony."
    assert render(Claim("together", ("Sara", "Karim"), "kitchen", 1, False)) == \
        "At 0:10, Sara and Karim were both in the kitchen."


def test_accept_drops_duplicates():
    c = Claim("location", ("Sara",), "kitchen", 1, False)
    ok, rej = accept([c, c], T, ZSET, "test")
    assert len(ok) == 1 and rej[0][1] == "duplicate claim"
