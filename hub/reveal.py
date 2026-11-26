"""Reveal page: the narrator's manuscript, corrected in red against the surveillance log.

One self-contained HTML file built from the session database:
  the verdict and the ledger, then
  I.   the statements; lies are struck through and corrected in red
  II.  the detectives
  III. the surveillance log (rooms as print textures); hover a statement to find its moment

Everything from the database is HTML-escaped (names are user input). No external assets.

    python -m hub.reveal sessions/<file>.db
"""
from __future__ import annotations

import html
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from .design import ARM_NAMES, MONO, ROOM_TEXTURES, SERIF, base_css, logo_svg
from .model import WINDOW_S

ON = {"balcony", "porch", "terrace", "deck", "stairs"}

CSS = f"""
main{{max-width:980px;margin:0 auto;padding:30px 22px 80px}}
.folio{{display:flex;justify-content:space-between;align-items:center;gap:14px;flex-wrap:wrap;padding-bottom:12px;
  border-bottom:1.5px solid var(--ink)}}
.folio .brand{{display:inline-flex;align-items:center;gap:12px;font:600 17px {SERIF}}}
.folio .caps{{color:var(--muted)}}
.hero{{padding:46px 0 10px;display:grid;grid-template-columns:1fr auto;gap:24px;align-items:end}}
.hero h1{{font:500 clamp(34px,5.4vw,58px)/1.04 {SERIF};letter-spacing:-.015em;margin:0;max-width:18ch}}
.hero h1 b{{font-weight:600;color:var(--red)}}
.hero p{{margin:16px 0 0;font-style:italic;font-size:19px;color:var(--muted);max-width:44ch}}
.hero .stamp{{font-size:14px;padding:9px 10px 8px 13px;margin-bottom:10px}}
.ledger{{display:grid;grid-template-columns:repeat(4,1fr);margin:34px 0 0;border-top:1px solid var(--rule);
  border-bottom:1px solid var(--rule)}}
.ledger div{{padding:16px 18px 14px;border-left:1px solid var(--rule)}}
.ledger div:first-child{{border-left:0;padding-left:0}}
.ledger b{{display:block;font:500 44px/1 {SERIF};margin-bottom:8px}}
.ledger .red b{{color:var(--red)}}
h2{{display:flex;align-items:baseline;gap:14px;font:500 27px/1.2 {SERIF};margin:62px 0 4px}}
h2 .caps{{color:var(--red);font-size:12px}}
h2+.lede{{margin:0 0 22px;color:var(--muted);font-style:italic}}
.round{{display:flex;align-items:center;gap:12px;margin:30px 0 4px;color:var(--muted)}}
.round::after{{content:"";flex:1;border-top:1px dashed var(--rule)}}
.entry{{display:grid;grid-template-columns:48px 1fr 92px;gap:6px 18px;padding:16px 0;border-bottom:1px solid var(--rule);
  outline:none}}
.entry .t{{font:12px/1.9 {MONO};color:var(--muted)}}
.entry .say{{font-size:21px;line-height:1.42}}
.entry .say::before{{content:"\\201C"}}.entry .say::after{{content:"\\201D"}}
.entry .stamp{{justify-self:end;align-self:start;margin-top:4px}}
.entry del{{text-decoration:line-through;text-decoration-color:var(--red);text-decoration-thickness:2px;color:var(--muted)}}
.entry ins{{text-decoration:none;color:var(--red);font-style:italic;position:relative;margin-left:.15em}}
.entry .note{{grid-column:2/4;font:12.5px/1.7 {MONO};color:var(--muted)}}
.entry .note b{{color:var(--ink);font-weight:600;letter-spacing:.12em}}
.entry .note b.red{{color:var(--red)}}
.entry:hover .say,.entry:focus .say{{background:var(--red-wash);box-shadow:0 0 0 6px var(--red-wash)}}
table{{width:100%;border-collapse:collapse;font-size:17px}}
th{{font:11.5px {MONO};letter-spacing:.16em;text-transform:uppercase;color:var(--muted);font-weight:500;text-align:right;
  padding:0 0 10px;border-bottom:1.5px solid var(--ink)}}
th:first-child,td:first-child{{text-align:left}}
td{{padding:11px 0;border-bottom:1px solid var(--rule);text-align:right;font-family:{MONO};font-size:15px}}
td:first-child{{font-family:{SERIF};font-size:18px}}
td .rank{{display:inline-block;width:2.2em;font:13px {MONO};color:var(--muted)}}
tr:first-child td:first-child::after{{content:"best detective";margin-left:12px;font:600 10.5px {MONO};
  letter-spacing:.16em;text-transform:uppercase;color:var(--red)}}
.key{{display:flex;flex-wrap:wrap;gap:10px 22px;margin:0 0 16px;font:13px {MONO}}}
.key span{{display:inline-flex;align-items:center;gap:8px}}
.sw{{width:20px;height:20px;border-radius:2px;display:inline-block}}
.log{{overflow-x:auto;padding:16px 0 6px;border-top:1.5px solid var(--ink);border-bottom:1px solid var(--rule)}}
.grid{{display:grid;grid-template-columns:84px 1fr;gap:11px 12px;min-width:calc(84px + var(--n) * 13px)}}
.grid .name{{font-size:16px;align-self:center;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.cells,.axis{{display:grid;grid-template-columns:repeat(var(--n),minmax(11px,1fr));gap:2px}}
.axis{{font:11px {MONO};color:var(--muted);height:16px}}
.axis span{{white-space:nowrap;width:0;border-left:1px solid var(--rule);padding-left:4px}}
.axis span:empty{{border:0}}
.c{{height:26px;border-radius:2px;position:relative}}
.c.unsure{{box-shadow:inset 0 0 0 1px var(--rule);background:transparent}}
.c.said::before{{content:"";position:absolute;left:0;right:0;top:-6px;height:3px;background:var(--muted)}}
.c.said.lie::before{{background:var(--red)}}
.c.hit{{outline:2.5px solid var(--red);outline-offset:1.5px;z-index:1}}
#tip{{position:fixed;pointer-events:none;background:var(--ink);color:var(--paper);font:12px/1.4 {MONO};padding:6px 9px;
  border-radius:2px;opacity:0;transition:opacity .1s;z-index:9}}
.colophon{{margin-top:56px;padding-top:14px;border-top:1.5px solid var(--ink);display:flex;justify-content:space-between;
  gap:20px;flex-wrap:wrap;font:12px/1.7 {MONO};color:var(--muted)}}
@media (max-width:640px){{.hero{{grid-template-columns:1fr}}.ledger{{grid-template-columns:repeat(2,1fr)}}
  .ledger div:nth-child(3){{border-left:0;padding-left:0}}.entry{{grid-template-columns:1fr auto}}.entry .t{{grid-column:1/3}}
  .entry .note{{grid-column:1/3}}.grid{{grid-template-columns:60px 1fr}}}}
"""

JS = """
const tip=document.getElementById('tip');
document.querySelectorAll('.c').forEach(c=>{
  c.addEventListener('mouseenter',()=>{tip.textContent=c.dataset.tip;tip.style.opacity=1});
  c.addEventListener('mousemove',e=>{tip.style.left=(e.clientX+12)+'px';tip.style.top=(e.clientY+14)+'px'});
  c.addEventListener('mouseleave',()=>tip.style.opacity=0);
});
document.querySelectorAll('.entry').forEach(s=>{
  const on=v=>document.querySelectorAll(s.dataset.cells).forEach(c=>c.classList.toggle('hit',v));
  ['mouseenter','focus'].forEach(k=>s.addEventListener(k,()=>on(true)));
  ['mouseleave','blur'].forEach(k=>s.addEventListener(k,()=>on(false)));
});
"""


def fmt(w: int) -> str:
    s = w * WINDOW_S
    return f"{s // 60}:{s % 60:02d}"


def place(zone: str | None) -> str:
    if not zone:
        return "somewhere the badges couldn't place"
    return f"{'on' if zone in ON else 'in'} the {zone}"


def corrected(ctype: str, players: list[str], zone: str, w: int, true_zone: dict[str, str | None]) -> str:
    """The statement as the editor marks it up: wrong words struck, the truth written in."""
    e = html.escape
    t = fmt(w)
    if ctype == "location":
        p = players[0]
        return f"At {t}, {e(p)} was <del>{e(place(zone))}</del> <ins>{e(place(true_zone[p]))}</ins>."
    if ctype == "absent":
        return f"At {t}, {e(players[0])} was <del>not</del> {e(place(zone))}."
    a, b = players
    fixes = "; ".join(f"{e(p)} {e(place(true_zone[p]))}" for p in players if true_zone[p] != zone)
    return f"At {t}, {e(a)} and {e(b)} were <del>both {e(place(zone))}</del> <ins>{fixes}</ins>."


def letters_for(zones: list[str]) -> dict[str, str]:
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
    sts = con.execute("SELECT idx, round, source, text, players, window, is_lie, claim_type, zone "
                      "FROM statements ORDER BY idx").fetchall()
    votes = con.execute("SELECT voter, statement_idx, believes_true FROM votes").fetchall()
    arms = dict(con.execute("SELECT round, arm FROM rounds").fetchall())

    players = sorted({r[0] for r in est} | {v[0] for v in votes})
    windows = sorted({r[1] for r in est})
    zone_order = [z for z in meta.get("zones", "").split(",") if z]
    zones = zone_order + sorted({r[2] for r in est if r[2] and r[2] not in zone_order})
    slot = {z: i % len(ROOM_TEXTURES) for i, z in enumerate(zones)}
    cell = {(p, w): (z, c) for p, w, z, c in est}
    is_lie = {s[0]: bool(s[6]) for s in sts}

    lie_votes = [v for v in votes if is_lie.get(v[1])]
    true_votes = [v for v in votes if v[1] in is_lie and not is_lie[v[1]]]
    fooled = sum(v[2] for v in lie_votes)
    caught = len(lie_votes) - fooled
    doubted = sum(1 - v[2] for v in true_votes)
    rate = fooled / len(lie_votes) if lie_votes else 0.0
    sim = meta.get("mode", "?") != "LIVE"

    if not lie_votes:
        h1, deck, verdict = "Nobody voted.", "The narrator spoke into an empty room.", ""
    elif rate >= 0.5:
        h1 = f"The narrator fooled you <b>{rate:.0%}</b> of the time."
        deck = "The machine takes this one. Here is every lie it told, corrected, and who fell for it."
        verdict = "<span class='stamp lie'>Narrator wins</span>"
    else:
        h1 = f"You caught <b>{1 - rate:.0%}</b> of the narrator&rsquo;s lies."
        deck = "The humans take this one. Here is every lie it told, corrected, and who still fell for it."
        verdict = "<span class='stamp true'>Humans win</span>"

    try:
        started = datetime.fromisoformat(meta.get("started", "")).strftime("%-d %b %Y · %H:%M")
    except ValueError:
        started = ""

    o = [f"<!doctype html><html lang='en'><head><meta charset='utf-8'>"
         f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
         f"<title>The Reveal · The Unreliable Narrator</title><style>{base_css()}{CSS}</style></head><body><main>"]
    o.append(f"<header class='folio'><span class='brand'>{logo_svg(22)}The Unreliable Narrator</span>"
             f"<span class='caps'>Case file Nº {e(meta.get('session', '?'))} &nbsp;·&nbsp; {e(started)}</span>"
             f"{'<span class=\"stamp sim\">Simulated players</span>' if sim else ''}</header>")
    o.append(f"<section class='hero'><div><h1>{h1}</h1><p>{e(deck)}</p></div>{verdict}</section>")
    o.append("<div class='ledger'>"
             f"<div><b>{sum(is_lie.values())}</b><span class='caps muted'>lies told</span></div>"
             f"<div class='red'><b>{fooled}</b><span class='caps muted'>times believed</span></div>"
             f"<div><b>{caught}</b><span class='caps muted'>times caught</span></div>"
             f"<div><b>{doubted}</b><span class='caps muted'>truths doubted</span></div></div>")

    o.append("<h2><span class='caps'>I</span>The statements</h2>"
             "<p class='lede'>As the narrator said them, corrected against the badges. Hover one to find it in the log.</p>")
    for rnd in sorted({s[1] for s in sts}):
        o.append(f"<div class='round caps'>Round {rnd} &nbsp;·&nbsp; liar: {e(ARM_NAMES.get(arms.get(rnd, ''), '?'))}</div>")
        for idx, _, source, text, ps, w, lie, ctype, zone in (s for s in sts if s[1] == rnd):
            names = json.loads(ps)
            truth = {p: (cell.get((p, w), (None, 0))[0]) for p in names}
            say = corrected(ctype, names, zone, w, truth) if lie else e(text)
            vs = sorted(v for v in votes if v[1] == idx)
            yes = [v[0] for v in vs if v[2]]
            no = [v[0] for v in vs if not v[2]]
            if lie:
                note = (f"<b class='red'>FELL FOR IT</b> {e(', '.join(yes) or 'nobody')} &nbsp; "
                        f"<b>CAUGHT IT</b> {e(', '.join(no) or 'nobody')}")
            else:
                note = (f"<b>BELIEVED</b> {e(', '.join(yes) or 'nobody')} &nbsp; "
                        f"<b class='red'>DOUBTED</b> {e(', '.join(no) or 'nobody')}")
            if source == "template-fill":
                note += " &nbsp;· topped up by the random liar"
            sel = ",".join(f"[data-k=\"{e(p)}|{w}\"]" for p in names)
            o.append(f"<article class='entry' tabindex='0' data-cells='{e(sel)}'>"
                     f"<span class='t'>{fmt(w)}</span><span class='say'>{say}</span>"
                     f"{'<span class=\"stamp lie\">Lie</span>' if lie else '<span class=\"stamp true\">True</span>'}"
                     f"<span class='note'>{note}</span></article>")

    rows = []
    for p in players:
        mine = [v for v in votes if v[0] == p]
        c = sum(1 for v in mine if is_lie.get(v[1]) and not v[2])
        f = sum(1 for v in mine if is_lie.get(v[1]) and v[2])
        d = sum(1 for v in mine if v[1] in is_lie and not is_lie[v[1]] and not v[2])
        rows.append((c - f - d, p, c, f, d))
    rows.sort(key=lambda r: (-r[0], r[1]))
    o.append("<h2><span class='caps'>II</span>The detectives</h2>"
             "<p class='lede'>Ranked by lies caught, minus lies believed and truths doubted.</p>"
             "<table><thead><tr><th>Player</th><th>Caught</th><th>Fell for</th><th>Doubted</th><th>Score</th></tr></thead><tbody>")
    for i, (score, p, c, f, d) in enumerate(rows, 1):
        o.append(f"<tr><td><span class='rank'>{i:02d}</span>{e(p)}</td><td>{c}</td><td>{f}</td><td>{d}</td>"
                 f"<td>{score:+d}</td></tr>")
    o.append("</tbody></table>")

    o.append("<h2 id='log-h'><span class='caps'>III</span>The surveillance log</h2>"
             f"<p class='lede'>Where every badge really was, in {WINDOW_S}-second frames. Empty frames were too "
             "uncertain, so the narrator was not allowed to use them. A tick marks a moment it talked about; red ticks are lies.</p>")
    o.append("<div class='key'>")
    for z in zones:
        o.append(f"<span><i class='sw' style='{ROOM_TEXTURES[slot[z]]}'></i>{e(z)}</span>")
    o.append("<span><i class='sw c unsure'></i>uncertain</span></div>")
    o.append(f"<div class='log'><div class='grid' style='--n:{len(windows)}'><div></div><div class='axis'>")
    o += [f"<span>{fmt(w) if w % 6 == 0 else ''}</span>" for w in windows]
    o.append("</div>")
    said = {(p, s[5]): bool(s[6]) for s in sts for p in json.loads(s[4])}
    for p in players:
        cells = []
        for w in windows:
            z, c = cell.get((p, w), (None, 0.0))
            sure = bool(z) and c >= 0.8
            style = f" style='{ROOM_TEXTURES[slot[z]]}'" if sure else ""
            cls = "c" + ("" if sure else " unsure")
            if (p, w) in said:
                cls += " said" + (" lie" if said[(p, w)] else "")
            tipt = f"{p} · {fmt(w)} · " + (f"{z} ({c:.0%})" if sure else "uncertain")
            cells.append(f"<div class='{cls}' data-k='{e(p)}|{w}' data-tip='{e(tipt)}'{style}></div>")
        o.append(f"<div class='name'>{e(p)}</div><div class='cells'>{''.join(cells)}</div>")
    o.append("</div></div>")
    o.append("<footer class='colophon'><span>Every claim was checked by code against this log before it was spoken. "
             "The AI chose which lies to tell, never what was true.</span>"
             f"<span>{'Simulated players, not people. ' if sim else ''}Printed in two inks.</span></footer>")
    o.append(f"<div id='tip' role='tooltip'></div><script>{JS}</script></main></body></html>")
    return "".join(o)


def write_reveal(con: sqlite3.Connection, path: Path) -> Path:
    path = Path(path)
    path.write_text(build(con), encoding="utf-8")
    return path


if __name__ == "__main__":
    p = Path(sys.argv[1])
    print(write_reveal(sqlite3.connect(p), p.with_suffix(".html")))
