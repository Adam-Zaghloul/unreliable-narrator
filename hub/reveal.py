"""Reveal page: one self-contained HTML file built from the session database.

Shows where everyone really was (a room timeline), every statement with TRUE/LIE, who
believed it, and the score. Everything from the database is HTML-escaped (names are user input).

    python -m hub.reveal sessions/<file>.db
"""
from __future__ import annotations

import html
import json
import sqlite3
import sys
from pathlib import Path

from .model import WINDOW_S

PALETTE = ["#4e79a7", "#f28e2b", "#59a14f", "#b07aa1", "#edc948", "#76b7b2", "#ff9da7", "#9c755f"]

CSS = """
:root{--bg:#fafaf7;--fg:#1d1d1b;--muted:#6b6b66;--card:#fff;--line:#e4e2dc;--lie:#c0392b;--true:#2e7d32}
@media (prefers-color-scheme:dark){:root{--bg:#161614;--fg:#ecebe6;--muted:#a3a29c;--card:#1f1f1c;--line:#34332f;--lie:#ef6f5e;--true:#7cc47f}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.45 system-ui,-apple-system,Segoe UI,sans-serif}
main{max-width:1000px;margin:0 auto;padding:24px 16px 64px}h1{font-size:28px;margin:0 0 4px}h2{font-size:19px;margin:32px 0 10px}
.muted{color:var(--muted)}.badge{display:inline-block;padding:1px 8px;border-radius:99px;font-size:12px;font-weight:700;letter-spacing:.04em}
.lie{background:var(--lie);color:#fff}.true{background:var(--true);color:#fff}
.score{display:flex;gap:12px;flex-wrap:wrap;margin:18px 0}.tile{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 16px;min-width:150px}
.tile b{display:block;font-size:26px}.st{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px;margin:8px 0}
.st.is-lie{border-left:5px solid var(--lie)}.st.is-true{border-left:5px solid var(--true)}
.tl{overflow-x:auto;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px}
.row{display:flex;align-items:center;gap:6px;margin:3px 0}.who{width:90px;flex:none;font-size:14px}
.cells{display:flex;gap:1px}.c{width:14px;height:18px;border-radius:2px;position:relative}.c.mark{outline:2px solid var(--fg);outline-offset:-2px}
.legend span{display:inline-flex;align-items:center;gap:5px;margin-right:14px;font-size:14px}.legend i{width:12px;height:12px;border-radius:2px;display:inline-block}
small{font-size:13px}
"""


def fmt(w: int) -> str:
    s = w * WINDOW_S
    return f"{s // 60}:{s % 60:02d}"


def build(con: sqlite3.Connection) -> str:
    e = html.escape
    meta = dict(con.execute("SELECT key, value FROM meta").fetchall())
    est = con.execute("SELECT player, window, zone, confidence FROM zone_estimates").fetchall()
    sts = con.execute("SELECT idx, round, source, text, players, window, is_lie FROM statements ORDER BY idx").fetchall()
    votes = con.execute("SELECT voter, statement_idx, believes_true FROM votes").fetchall()
    arms = dict(con.execute("SELECT round, arm FROM rounds").fetchall())

    players = sorted({r[0] for r in est})
    windows = sorted({r[1] for r in est})
    zones = sorted({r[2] for r in est if r[2]})
    color = {z: PALETTE[i % len(PALETTE)] for i, z in enumerate(zones)}
    cell = {(p, w): (z, c) for p, w, z, c in est}
    marked = {(p, w) for _, _, _, _, ps, w, _ in sts for p in json.loads(ps)}

    lie_votes = [v for v in votes if sts and any(s[0] == v[1] and s[6] for s in sts)]
    true_votes = [v for v in votes if sts and any(s[0] == v[1] and not s[6] for s in sts)]
    fooled = sum(v[2] for v in lie_votes)
    caught = len(lie_votes) - fooled
    distrust = sum(1 - v[2] for v in true_votes)

    out = [f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' "
           f"content='width=device-width,initial-scale=1'><title>Unreliable Narrator Reveal</title><style>{CSS}</style>"
           f"</head><body><main>"]
    mode = meta.get("mode", "?")
    out.append(f"<h1>What really happened</h1><p class='muted'>{e(meta.get('started', ''))} · session "
               f"{e(meta.get('session', '?'))} · <b>{e(mode)}</b>{' (simulated players, not people)' if mode != 'LIVE' else ''}</p>")
    out.append("<div class='score'>"
               f"<div class='tile'><b>{caught}</b>lie votes caught</div>"
               f"<div class='tile'><b>{fooled}</b>times a lie was believed</div>"
               f"<div class='tile'><b>{distrust}</b>times a truth was called a lie</div></div>")

    out.append("<h2>Every statement</h2>")
    for idx, rnd, source, text, ps, w, is_lie in sts:
        believers = sorted(v[0] for v in votes if v[1] == idx and v[2])
        doubters = sorted(v[0] for v in votes if v[1] == idx and not v[2])
        truth_bits = []
        for p in json.loads(ps):
            z = cell.get((p, w), (None, 0))[0]
            truth_bits.append(f"{e(p)} was really in the {e(z or 'unknown')}")
        tag = "<span class='badge lie'>LIE</span>" if is_lie else "<span class='badge true'>TRUE</span>"
        out.append(f"<div class='st {'is-lie' if is_lie else 'is-true'}'>{tag} {e(text)}<br>"
                   f"<small class='muted'>Round {rnd} · {e('; '.join(truth_bits))}</small><br>"
                   f"<small>Believed: {e(', '.join(believers) or 'nobody')} · Called it a lie: "
                   f"{e(', '.join(doubters) or 'nobody')}</small></div>")

    out.append("<h2>Where everyone was</h2><div class='legend'>")
    out += [f"<span><i style='background:{color[z]}'></i>{e(z)}</span>" for z in zones]
    out.append("<span><i style='background:var(--line)'></i>not sure</span><span><i style='outline:2px solid var(--fg)'>"
               "</i>talked about</span></div><div class='tl'>")
    for p in players:
        cells = []
        for w in windows:
            z, c = cell.get((p, w), (None, 0))
            bg = color[z] if z and c >= 0.8 else "var(--line)"
            title = f"{fmt(w)} {z or '?'} ({c:.0%})"
            cells.append(f"<div class='c{' mark' if (p, w) in marked else ''}' style='background:{bg}' "
                         f"title='{e(title)}'></div>")
        out.append(f"<div class='row'><div class='who'>{e(p)}</div><div class='cells'>{''.join(cells)}</div></div>")
    out.append(f"</div><p class='muted'><small>Each square is {WINDOW_S} s. Liars by round: "
               f"{e(', '.join(f'{r}: {a}' for r, a in sorted(arms.items())))}.</small></p></main></body></html>")
    return "".join(out)


def write_reveal(con: sqlite3.Connection, path: Path) -> Path:
    path = Path(path)
    path.write_text(build(con), encoding="utf-8")
    return path


if __name__ == "__main__":
    p = Path(sys.argv[1])
    print(write_reveal(sqlite3.connect(p), p.with_suffix(".html")))
