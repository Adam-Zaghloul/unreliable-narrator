"""E1 on real hardware: truth engine vs a naive baseline, against your walk marks.

Ground truth per 10 s window = the room you marked for most of that window. Windows that
contain a room change are reported separately ("boundary"), since that is where errors live.

- baseline: strongest single reading in the window, no median, no hysteresis, no confidence gate
- mine:     hub/truth.py, counting only STABLE facts (what the narrator is allowed to use)

    python -m evals.e1_bench walks/*.db
"""
from __future__ import annotations

import json
import sqlite3
import sys
from collections import Counter, defaultdict

from hub.model import WINDOW_S, Ping
from hub.truth import Truth, estimate_zones, window_of


def zone_of_beacon_from(con) -> dict[str, str]:
    return json.loads(dict(con.execute("SELECT key, value FROM meta")).get("zone_of_beacon", "{}"))


def truth_from_marks(marks: list[tuple[int, str]], end_ms: int) -> dict[int, tuple[str, bool]]:
    """{window: (majority zone, had_transition)} from (t_ms, zone) marks."""
    out = {}
    if not marks:
        return out
    marks = sorted(marks)
    for w in range(window_of(marks[0][0]), window_of(end_ms) + 1):
        counts, changes = Counter(), 0
        prev = None
        for s in range(w * WINDOW_S, (w + 1) * WINDOW_S):
            t = s * 1000
            here = [z for tm, z in marks if tm <= t]
            if not here:
                continue
            z = here[-1]
            counts[z] += 1
            changes += prev is not None and z != prev
            prev = z
        if counts:
            out[w] = (counts.most_common(1)[0][0], changes > 0)
    return out


def baseline(pings: list[Ping], zob: dict[str, str]) -> dict[tuple[str, int], str]:
    best = {}
    for p in pings:
        if p.beacon in zob:
            k = (p.badge, window_of(p.t_ms))
            if k not in best or p.rssi > best[k][1]:
                best[k] = (zob[p.beacon], p.rssi)
    return {k: v[0] for k, v in best.items()}


def evaluate(con) -> dict:
    zob = zone_of_beacon_from(con)
    pings = [Ping(*r) for r in con.execute("SELECT badge, t_ms, beacon, rssi FROM pings")]
    marks = con.execute("SELECT t_ms, zone FROM walk_marks").fetchall()
    if not pings or not marks:
        return {}
    gt = truth_from_marks(marks, max(p.t_ms for p in pings))
    truth = Truth(estimate_zones(pings, zob))
    base = baseline(pings, zob)
    res = defaultdict(lambda: [0, 0])  # name -> [right, total]
    cells = defaultdict(int)
    for badge in truth.players:
        for w, (z, boundary) in gt.items():
            part = "boundary" if boundary else "clean"
            cells[part] += 1
            if (badge, w) in base:
                res[f"baseline {part}"][0] += base[(badge, w)] == z
                res[f"baseline {part}"][1] += 1
            if truth.stable(badge, w):
                res[f"mine {part}"][0] += truth.zone(badge, w) == z
                res[f"mine {part}"][1] += 1
    return {"results": dict(res), "cells": dict(cells)}


def main(paths: list[str]) -> None:
    total = defaultdict(lambda: [0, 0])
    cells = defaultdict(int)
    for p in paths:
        r = evaluate(sqlite3.connect(p))
        for k, (a, b) in r.get("results", {}).items():
            total[k][0] += a
            total[k][1] += b
        for k, v in r.get("cells", {}).items():
            cells[k] += v
    print(f"E1 bench over {len(paths)} walk(s)")
    print("method / windows      | accuracy | coverage")
    for k in ("baseline clean", "baseline boundary", "mine clean", "mine boundary"):
        right, n = total[k]
        part = k.split()[1]
        acc = f"{right / n:.1%}" if n else "-"
        cov = f"{n / cells[part]:.1%}" if cells[part] else "-"
        print(f"{k:<21} | {acc:>8} | {cov:>8}")


if __name__ == "__main__":
    main(sys.argv[1:])
