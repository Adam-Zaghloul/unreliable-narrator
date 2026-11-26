"""One SQLite file per game session. This is the whole state of the system."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS pings (badge TEXT, t_ms INTEGER, beacon TEXT, rssi REAL);
CREATE TABLE IF NOT EXISTS zone_estimates (player TEXT, window INTEGER, zone TEXT, confidence REAL,
    PRIMARY KEY (player, window));
CREATE TABLE IF NOT EXISTS statements (idx INTEGER PRIMARY KEY, round INTEGER, source TEXT, text TEXT,
    claim_type TEXT, players TEXT, zone TEXT, window INTEGER, is_lie INTEGER, strategy TEXT);
CREATE TABLE IF NOT EXISTS rejected (round INTEGER, source TEXT, claim TEXT, reason TEXT);
CREATE TABLE IF NOT EXISTS rounds (round INTEGER PRIMARY KEY, arm TEXT);
CREATE TABLE IF NOT EXISTS votes (voter TEXT, statement_idx INTEGER, believes_true INTEGER);
CREATE TABLE IF NOT EXISTS buzzes (player TEXT, window INTEGER);
CREATE TABLE IF NOT EXISTS llm_calls (t REAL, model TEXT, input_tokens INTEGER, output_tokens INTEGER,
    latency_ms INTEGER, cost_usd REAL, stop_reason TEXT, ok INTEGER, error TEXT);
"""


def connect(path: str | Path = ":memory:") -> sqlite3.Connection:
    con = sqlite3.connect(str(path))
    con.executescript(SCHEMA)
    return con


def save_pings(con, pings) -> None:
    con.executemany("INSERT INTO pings VALUES (?,?,?,?)", [(p.badge, p.t_ms, p.beacon, p.rssi) for p in pings])


def save_estimates(con, estimates) -> None:
    con.executemany("INSERT OR REPLACE INTO zone_estimates VALUES (?,?,?,?)",
                    [(e.player, e.window, e.zone, e.confidence) for e in estimates.values()])


def save_statement(con, idx: int, rnd: int, st) -> None:
    c = st.claim
    con.execute("INSERT INTO statements VALUES (?,?,?,?,?,?,?,?,?,?)",
                (idx, rnd, st.source, st.text, c.claim_type, json.dumps(list(c.players)), c.zone, c.window,
                 int(c.is_lie), c.strategy))


def save_rejected(con, rnd: int, source: str, claim, reason: str) -> None:
    con.execute("INSERT INTO rejected VALUES (?,?,?,?)", (rnd, source, repr(claim), reason))


def log_llm_call(con, **row) -> None:
    con.execute("INSERT INTO llm_calls VALUES (:t,:model,:input_tokens,:output_tokens,:latency_ms,:cost_usd,"
                ":stop_reason,:ok,:error)", row)
