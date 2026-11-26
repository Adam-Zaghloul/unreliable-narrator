"""Gateway serial -> Pings. The hub stamps each packet on arrival (badges have no shared clock).

    python -m hub.ingest /dev/cu.usbmodem1101 session.db     # needs: pip install pyserial

players.json (optional, next to the db) maps badge ids to names: {"1": "Sara", "2": "Karim"}
zones.json maps beacon ids to rooms: {"1": "kitchen", "2": "living room"}
"""
from __future__ import annotations

import json
import sys
import time

from .model import Ping


def parse_line(line: str, t_ms: int, players: dict[str, str]) -> tuple[list[Ping], int | None, int]:
    """Return (pings, badge_id, buttons) for one gateway JSON line. Non-packet lines -> no pings."""
    try:
        msg = json.loads(line)
    except json.JSONDecodeError:
        return [], None, 0
    if "badge" not in msg:
        return [], None, 0
    bid = int(msg["badge"])
    name = players.get(str(bid), f"P{bid}")
    pings = [Ping(name, t_ms, f"{kind}{pid}", float(rssi)) for kind, pid, rssi in msg.get("peers", [])]
    return pings, bid, int(msg.get("buttons", 0))


def main(port: str, db_path: str) -> None:
    import serial  # pyserial

    from . import db

    players = _load("players.json")
    con = db.connect(db_path)
    t0 = time.monotonic()
    with serial.Serial(port, 115200, timeout=1) as ser:
        print("listening; Ctrl+C to stop")
        while True:
            line = ser.readline().decode(errors="replace").strip()
            if not line:
                continue
            pings, bid, buttons = parse_line(line, int((time.monotonic() - t0) * 1000), players)
            if pings:
                db.save_pings(con, pings)
                con.commit()
            if buttons:
                print(f"badge {bid} buttons={buttons:02b}")


def _load(path: str) -> dict:
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
