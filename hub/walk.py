"""Scripted walk recorder: the real-hardware E1 test. Do this before any game.

Carry one or more badges around the rooms. Every time you step into a room, type its zone id
and press Enter. Those marks are the ground truth; the gateway pings are the measurement.

    python -m hub.walk --config game.json --port /dev/cu.usbmodem1101
    python -m evals.e1_bench walks/<file>.db

Walk tips: stay 30-90 s per room, include doorway lingering and turning your back to a beacon
(body shadowing), do at least 10 runs in the house and again in another space.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from . import db
from .config import load
from .ingest import parse_line


def record(transport, clock, con, cfg, read=input, out=print) -> int:
    con.execute("CREATE TABLE IF NOT EXISTS walk_marks (t_ms INTEGER, zone TEXT)")
    con.execute("INSERT OR REPLACE INTO meta VALUES ('mode','WALK'),('zone_of_beacon',?)",
                (json.dumps(cfg.zone_of_beacon),))
    out("Zones: " + ", ".join(f"{i}={z}" for i, z in cfg.zones.items()) + ".  Type an id + Enter on entering a room; q to stop.")
    marks = 0
    while True:
        key = read("> ").strip().lower()
        t = clock.now_ms()
        for at, line in transport.poll():
            pings, _, _ = parse_line(line, at, cfg.name_of_badge)
            db.save_pings(con, pings)
        if key == "q":
            break
        if key.isdigit() and int(key) in cfg.zones:
            con.execute("INSERT INTO walk_marks VALUES (?,?)", (t, cfg.zones[int(key)]))
            marks += 1
            out(f"{t / 1000:7.1f}s  now in {cfg.zones[int(key)]}")
        else:
            out("unknown zone id")
        con.commit()
    con.commit()
    return marks


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--port", required=True)
    ap.add_argument("--out", default="walks")
    a = ap.parse_args(argv)
    from .transport import RealClock, SerialTransport

    cfg = load(a.config)
    Path(a.out).mkdir(exist_ok=True)
    path = Path(a.out) / f"walk-{datetime.now():%Y%m%d-%H%M%S}.db"
    clock = RealClock()
    record(SerialTransport(a.port, clock), clock, db.connect(path), cfg)
    print(f"saved {path}")


if __name__ == "__main__":
    main()
