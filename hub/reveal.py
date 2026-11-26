"""Reveal page: one self-contained HTML file built from the session database.

Read top to bottom at the end of the night:
1. the verdict (how often the narrator fooled the room),
2. every statement, TRUE or LIE, with who believed it,
3. the detectives table (per player),
4. the timeline of where everyone really was; hover a statement to light up its moment.

Everything from the database is HTML-escaped (names are user input). No external assets.

    python -m hub.reveal sessions/<file>.db
"""
from __future__ import annotations

import html
import json
import sqlite3
import sys
from pathlib import Path

from .design import ROOM_COLORS, base_css, logo_svg
from .model import WINDOW_S

CSS = """
main{max-width:1040px;margin:0 auto;padding:28px 16px 72px}
header.top{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}
.meta{font-size:14px}
.hero{margin:36px 0 8px}
.hero h1{font-size:clamp(30px,5vw,46px);line-height:1.1;margin:0 0 10px;font-weight:600}
.hero h1 em{font-style:normal;color:var(--lie)}
.hero h1 em.win{color:var(--true)}
.hero p{margin:0;font-size:18px;max-width:640px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin:26px 0 8px}
.tile{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:14px 16px;box-shadow:var(--shadow)}
.tile b{display:block;font-size:30px;line-height:1.15;font-weight:650}
.tile span{font-size:14px;color:var(--muted)}
h2{font-size:22px;margin:44px 0 6px;font-weight:600}
h2+p{margin:0 0 14px;color:var(--muted);font-size:15px}
.round-h{font-size:13px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin:22px 0 8px;font-weight:650}
.st{display:grid;grid-template-columns:auto 1fr;gap:4px 14px;background:var(--surface);border:1px solid var(--line);
  border-radius:12px;padding:14px 16px;margin:8px 0;box-shadow:var(--shadow);transition:border-color .15s}
.st:hover,.st:focus-within{border-color:var(--ink)}
.st .tag{margin-top:3px}
.st q{quotes:none;font-size:18px;line-height:1.4}
.st .truth{grid-column:2;font-size:14px;color:var(--muted)}
.st .who{grid-column:2;display:flex;gap:6px;flex-wrap:wrap;margin-top:6px}
.chip{font-size:13px;padding:2px 9px;border-radius:999px;border:1px solid var(--line);background:var(--surface-2)}
.chip.fooled{background:var(--lie-soft);border-color:transparent}
.chip.caught{background:var(--true-soft);border-color:transparent}
.chip.wrong{background:var(--warn-soft);border-color:transparent}
table{width:100%;border-collapse:collapse;background:var(--surface);border:1px solid var(--line);border-radius:12px;
  overflow:hidden;box-shadow:var(--shadow);font-size:15px}
th,td{text-align:left;padding:10px 14px;border-bottom:1px solid var(--line)}
th{font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);font-weight:650;background:var(--surface-2)}
td.n,th.n{text-align:right}
tr:last-child td{border-bottom:0}
.tl{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:16px;box-shadow:var(--shadow);
  overflow-x:auto}
.grid{display:grid;grid-template-columns:96px 1fr;gap:4px 10px;min-width:calc(96px + var(--n) * 14px)}
.grid .name{font-size:14px;align-self:center;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.cells,.axis{display:grid;grid-template-columns:repeat(var(--n),minmax(12px,1fr));gap:2px}
.c{height:24px;border-radius:4px;display:grid;place-items:center;font-size:10px;font-weight:700;
  color:#111;position:relative;background:var(--cell-empty)}
.c.unsure{color:var(--muted);font-weight:500}
.c.hit{outline:2.5px solid var(--ink);outline-offset:1px;z-index:1}
.c.hit.lie{outline-color:var(--lie)}
.axis{font-size:11px;color:var(--muted)}
.axis span{white-space:nowrap;overflow:visible;width:0}
.legend{display:flex;flex-wrap:wrap;gap:8px 18px;margin:0 0 14px;font-size:14px}
.legend span{display:inline-flex;align-items:center;gap:7px}
.legend i{width:18px;height:18px;border-radius:4px;display:inline-grid;place-items:center;font-style:normal;font-size:10px;
  font-weight:700;color:#111}
#tip{position:fixed;pointer-events:none;background:var(--ink);color:var(--bg);font-size:13px;padding:6px 9px;border-radius:6px;
  opacity:0;transition:opacity .1s;z-index:9}
footer{margin-top:48px;font-size:13px;color:var(--muted)}
@media (max-width:560px){.st{grid-template-columns:1fr}.st .truth,.st .who{grid-column:1}.grid{grid-template-columns:64px 1fr}}
@media print{.st,.tile,table,.tl{box-shadow:none}}
"""

JS = """
const tip=document.getElementById('tip');
document.querySelectorAll('.c').forEach(c=>{
  c.addEventListener('mouseenter',e=>{tip.textContent=c.dataset.tip;tip.style.opacity=1});
  c.addEventListener('mousemove',e=>{tip.style.left=(e.clientX+12)+'px';tip.style.top=(e.clientY+12)+'px'});
  c.addEventListener('mouseleave',()=>tip.style.opacity=0);
});
document.querySelectorAll('.st').forEach(s=>{
  const on=v=>document.querySelectorAll(s.dataset.cells).forEach(c=>c.classList.toggle('hit',v));
  s.addEventListener('mouseenter',()=>on(true));s.addEventListener('mouseleave',()=>on(false));
  s.addEventListener('focusin',()=>on(true));s.addEventListener('focusout',()=>on(false));
});
"""


def fmt(w: int) -> str:
    s = w * WINDOW_S
    return f"{s // 60}:{s % 60:02d}"


def _place(zone: str | None) -> str:
    if not zone:
        return "somewhere the sensors weren't sure of"
    return f"{'on' if zone in ('balcony', 'porch', 'terrace', 'deck', 'stairs') else 'in'} the {zone}"


def letters_for(zones: list[str]) -> dict[str, str]:
    """Unique 1-2 letter label per room: first letter, or first + next distinct letter on clashes."""
    out: dict[str, str] = {}
    for z in zones:
        cand = z[0].upper()
        if cand in out.values():
            cand = next((z[0].upper() + ch for ch in z[1:].replace(" ", "")
                         if z[0].upper() + ch not in out.values()), z[:2].title())
        out[z] = cand
    return out


def build(con: sqlite3.Connection) -> str:
    e = html.escape
    meta = dict(con.execute("SELECT key, value FROM meta").fetchall())
    est = con.execute("SELECT player, window, zone, confidence FROM zone_estimates").fetchall()
    sts = con.execute("SELECT idx, round, source, text, players, window, is_lie FROM statements ORDER BY idx").fetchall()
    votes = con.execute("SELECT voter, statement_idx, believes_true FROM votes").fetchall()
    arms = dict(con.execute("SELECT round, arm FROM rounds").fetchall())

    players = sorted({r[0] for r in est} | {v[0] for v in votes})
    windows = sorted({r[1] for r in est})
    zone_order = [z for z in meta.get("zones", "").split(",") if z]
    zones = zone_order + sorted({r[2] for r in est if r[2] and r[2] not in zone_order})
    slot = {z: i % len(ROOM_COLORS) for i, z in enumerate(zones)}
    letter = letters_for(zones)
    cell = {(p, w): (z, c) for p, w, z, c in est}
    is_lie = {s[0]: bool(s[6]) for s in sts}

    lie_votes = [v for v in votes if is_lie.get(v[1])]
    true_votes = [v for v in votes if v[1] in is_lie and not is_lie[v[1]]]
    fooled = sum(v[2] for v in lie_votes)
    caught = len(lie_votes) - fooled
    doubted = sum(1 - v[2] for v in true_votes)
    rate = fooled / len(lie_votes) if lie_votes else 0.0
    n_lies = sum(is_lie.values())

    mode = meta.get("mode", "?")
    sim = mode != "LIVE"
    if not lie_votes:
        headline, sub = "No votes were recorded.", "The narrator spoke, but nobody pressed a button in time."
    elif rate >= 0.5:
        headline = f"The narrator fooled you <em>{rate:.0%}</em> of the time."
        sub = "The machine wins this one. Below is every lie it told, and who fell for it."
    else:
        headline = f"You caught <em class='win'>{1 - rate:.0%}</em> of the narrator's lies."
        sub = "The humans win this one. Below is every lie it told, and who still fell for it."

    o = [f"<!doctype html><html lang='en'><head><meta charset='utf-8'>"
         f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
         f"<title>Reveal · The Unreliable Narrator</title><style>{base_css()}{CSS}</style></head><body><main>"]
    o.append(f"<header class='top'><span class='mark'>{logo_svg()}The Unreliable Narrator</span>"
             f"<span class='meta muted'>{e(meta.get('started', '').replace('T', ' · '))} · session "
             f"{e(meta.get('session', '?'))} {'<span class=\"tag sim\">Simulated players</span>' if sim else ''}</span></header>")
    o.append(f"<section class='hero'><h1 class='serif'>{headline}</h1><p class='muted'>{e(sub)}</p></section>")
    o.append("<div class='tiles'>"
             f"<div class='tile'><b>{n_lies}</b><span>lies told</span></div>"
             f"<div class='tile'><b>{fooled}</b><span>times a lie was believed</span></div>"
             f"<div class='tile'><b>{caught}</b><span>times a lie was caught</span></div>"
             f"<div class='tile'><b>{doubted}</b><span>times the truth was called a lie</span></div></div>")

    # statements, grouped by round
    o.append("<h2 class='serif'>Every statement</h2><p>Hover one to see that moment on the timeline below.</p>")
    for rnd in sorted({s[1] for s in sts}):
        arm = arms.get(rnd, "")
        o.append(f"<div class='round-h'>Round {rnd}{' · liar: ' + e(arm) if arm else ''}</div>")
        for idx, _, source, text, ps, w, lie in (s for s in sts if s[1] == rnd):
            names = json.loads(ps)
            if lie:
                truth = "; ".join(f"{e(p)} was really {e(_place(cell.get((p, w), (None, 0))[0]))}" for p in names)
            else:
                truth = "Matches the badges."
            chips = []
            for voter, vi, b in sorted(v for v in votes if v[1] == idx):
                if lie:
                    cls, label = ("fooled", "believed it") if b else ("caught", "caught it")
                else:
                    cls, label = ("", "believed it") if b else ("wrong", "called it a lie")
                chips.append(f"<span class='chip {cls}'>{e(voter)} · {label}</span>")
            sel = ",".join(f"[data-k=\"{e(p)}|{w}\"]" for p in names)
            fill_note = " · topped up by the random liar" if source == "template-fill" else ""
            o.append(f"<article class='st' tabindex='0' data-cells='{e(sel)}'>"
                     f"{'<span class=\"tag lie\">Lie</span>' if lie else '<span class=\"tag true\">True</span>'}"
                     f"<q class='serif'>{e(text)}</q><div class='truth'>{truth}{fill_note}</div>"
                     f"<div class='who'>{''.join(chips) or '<span class=\"muted\">No votes</span>'}</div></article>")

    # detectives
    rows = []
    for p in players:
        mine = [v for v in votes if v[0] == p]
        c = sum(1 for v in mine if is_lie.get(v[1]) and not v[2])
        f = sum(1 for v in mine if is_lie.get(v[1]) and v[2])
        d = sum(1 for v in mine if v[1] in is_lie and not is_lie[v[1]] and not v[2])
        rows.append((c - f - d, p, c, f, d))
    rows.sort(key=lambda r: (-r[0], r[1]))
    o.append("<h2 class='serif'>Detectives</h2><p>Ranked by lies caught, minus lies believed and truths doubted.</p>"
             "<table><thead><tr><th>Player</th><th class='n'>Lies caught</th><th class='n'>Lies believed</th>"
             "<th class='n'>Truths doubted</th></tr></thead><tbody>")
    for _, p, c, f, d in rows:
        o.append(f"<tr><td>{e(p)}</td><td class='n'>{c}</td><td class='n'>{f}</td><td class='n'>{d}</td></tr>")
    o.append("</tbody></table>")

    # timeline
    o.append("<h2 class='serif'>Where everyone really was</h2><p>What the badges recorded, every "
             f"{WINDOW_S} seconds. Grey means the sensors weren't sure, so the narrator wasn't allowed to use it.</p>")
    o.append("<div class='legend'>")
    for z in zones:
        o.append(f"<span><i style='background:var(--room-{slot[z]})'>{e(letter[z])}</i>{e(z)}</span>")
    o.append("<span><i style='background:var(--cell-empty);color:var(--muted)'>?</i>not sure</span></div>")
    o.append(f"<div class='tl'><div class='grid' style='--n:{len(windows)}'><div></div><div class='axis'>")
    o += [f"<span>{fmt(w) if w % 6 == 0 else ''}</span>" for w in windows]
    o.append("</div>")
    lie_cells = {(p, s[5]) for s in sts if s[6] for p in json.loads(s[4])}
    for p in players:
        cells = []
        for w in windows:
            z, c = cell.get((p, w), (None, 0.0))
            sure = bool(z) and c >= 0.8
            style = f" style='background:var(--room-{slot[z]})'" if sure else ""
            label = letter[z] if sure else "?"
            tipt = f"{p} · {fmt(w)} · {z if sure else 'not sure'}" + (f" ({c:.0%})" if z else "")
            cls = "c" + ("" if sure else " unsure") + (" lie" if (p, w) in lie_cells else "")
            cells.append(f"<div class='{cls}' data-k='{e(p)}|{w}' data-tip='{e(tipt)}'{style}>{e(label)}</div>")
        o.append(f"<div class='name'>{e(p)}</div><div class='cells'>{''.join(cells)}</div>")
    o.append("</div></div>")
    o.append(f"<footer>Every claim was checked against this log by code before it was spoken; the AI chose which "
             f"lies to tell, never what was true. {'These players were simulated, not people.' if sim else ''}</footer>")
    o.append(f"<div id='tip' role='tooltip'></div><script>{JS}</script></main></body></html>")
    return "".join(o)


def write_reveal(con: sqlite3.Connection, path: Path) -> Path:
    path = Path(path)
    path.write_text(build(con), encoding="utf-8")
    return path


if __name__ == "__main__":
    p = Path(sys.argv[1])
    print(write_reveal(sqlite3.connect(p), p.with_suffix(".html")))
