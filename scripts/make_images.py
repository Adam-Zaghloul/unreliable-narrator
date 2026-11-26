"""Regenerate every screenshot in docs/images from real code paths (no mock-ups).

- reveal-*.png, timeline-*.png:  a simulated game run through hub.live, rendered by hub.reveal
- screen-*.png:                  the big-screen page (hub.screen) in its demo states
- social-preview.png:            GitHub social card, in the same print language
- badge.svg:                     scripts/draw_badge.py

Needs Google Chrome (headless) and Pillow:  python scripts/make_images.py
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hub import db  # noqa: E402
from hub.design import MONO, SERIF, base_css, logo_svg  # noqa: E402
from hub.live import DEMO, LiveGame  # noqa: E402
from hub.reveal import build  # noqa: E402
from hub.screen import page  # noqa: E402
from hub.transport import SimClock, SimTransport  # noqa: E402
from sim.world import simulate  # noqa: E402

OUT = ROOT / "docs" / "images"
CHROME = next((p for p in ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                           shutil.which("google-chrome") or "", shutil.which("chromium") or ""] if p and Path(p).exists()),
              None)


def shoot(html: Path, png: Path, w: int, h: int, scale: int = 2, query: str = "") -> Image.Image:
    subprocess.run([CHROME, "--headless=new", "--hide-scrollbars", "--disable-gpu", f"--force-device-scale-factor={scale}",
                    f"--window-size={w},{h}", f"--screenshot={png}", html.as_uri() + query],
                   check=True, capture_output=True)
    return Image.open(png)


def themed(src: str, theme: str) -> str:
    return src.replace("<html lang='en'>", f"<html lang='en' data-theme='{theme}'>", 1)


def save(img: Image.Image, name: str) -> None:
    img.convert("RGB").save(OUT / name, optimize=True)
    print("wrote", OUT / name)


# shows only the surveillance log (and lights up the first lie), for the README strip
ONLY_LOG = ("<script>let on=false;for(const el of [...document.querySelector('main').children]){"
            "if(el.id==='log-h')on=true;if(!on&&!el.classList.contains('folio'))el.style.display='none';"
            "if(el.tagName==='FOOTER'||el.id==='tip')el.style.display='none'}"
            "document.querySelector('#log-h').style.marginTop='28px';"
            "const s=[...document.querySelectorAll('.entry')].find(x=>x.querySelector('.stamp.lie'));"
            "s&&s.dispatchEvent(new Event('mouseenter'));</script></body>")


def reveal_images(tmp: Path) -> None:
    cfg = DEMO
    cfg.round_minutes = 2
    world = simulate(2, players=list(cfg.players.values()), zones=list(cfg.zones.values()), duration_s=520)
    clock = SimClock()
    con = db.connect(tmp / "demo.db")
    LiveGame(cfg, SimTransport(world, clock, 2), clock, con, 2, mode="SIMULATED").run()
    con.execute("UPDATE meta SET value='2026-11-26T20:14:05' WHERE key='started'")
    html = build(con)
    for theme in ("light", "dark"):
        f = tmp / f"reveal-{theme}.html"
        f.write_text(themed(html, theme))
        save(shoot(f, tmp / f"reveal-{theme}.png", 1100, 1460), f"reveal-{theme}.png")
        f2 = tmp / f"log-{theme}.html"
        f2.write_text(themed(html, theme).replace("</body>", ONLY_LOG, 1))
        save(shoot(f2, tmp / f"log-{theme}.png", 1100, 545), f"timeline-{theme}.png")


def screen_images(tmp: Path) -> None:
    f = tmp / "screen.html"
    f.write_text(themed(page(), "dark"))
    for state in ("play", "meeting", "over"):
        save(shoot(f, tmp / f"screen-{state}.png", 1440, 810, query=f"?demo={state}"), f"screen-{state}.png")


SOCIAL = """<!doctype html><html lang='en' data-theme='light'><head><meta charset='utf-8'><style>{css}
body{{width:1280px;height:640px;margin:0;position:relative;overflow:hidden}}
.wrap{{position:absolute;inset:56px 72px}}
.top{{display:flex;justify-content:space-between;align-items:center;border-bottom:1.5px solid var(--ink);padding-bottom:14px}}
.brand{{display:inline-flex;align-items:center;gap:14px;font:600 24px {serif}}}
h1{{font:400 84px/1.02 {serif};letter-spacing:-.025em;margin:58px 0 0}}
.line{{font:400 40px/1.3 {serif};margin-top:34px}}
.line del{{text-decoration:line-through;text-decoration-color:var(--red);text-decoration-thickness:3px;color:var(--muted)}}
.line ins{{text-decoration:none;color:var(--red);font-style:italic}}
.line .stamp{{font-size:18px;padding:10px 11px 9px 14px;margin-left:22px;vertical-align:8px}}
.foot{{position:absolute;left:0;right:0;bottom:0;display:flex;justify-content:space-between;border-top:1px solid var(--rule);
  padding-top:12px;font:15px {mono};letter-spacing:.14em;text-transform:uppercase;color:var(--muted)}}
.reg{{position:absolute;width:26px;height:26px}}
.reg::before,.reg::after{{content:"";position:absolute;background:var(--ink)}}
.reg::before{{left:12px;top:0;width:1.2px;height:26px}}.reg::after{{top:12px;left:0;height:1.2px;width:26px}}
.reg i{{position:absolute;inset:6px;border:1.2px solid var(--ink);border-radius:50%}}
</style></head><body>
<span class='reg' style='left:20px;top:20px'><i></i></span><span class='reg' style='right:20px;top:20px'><i></i></span>
<span class='reg' style='left:20px;bottom:20px'><i></i></span><span class='reg' style='right:20px;bottom:20px'><i></i></span>
<div class='wrap'>
<div class='top'><span class='brand'>{logo}The Unreliable Narrator</span><span class='caps muted'>A party game · ESP32 · Claude</span></div>
<h1>The AI is the traitor.<br>The badges know the truth.</h1>
<div class='line'>&ldquo;At 3:40, Karim was <del>in the living room</del> <ins>in the kitchen</ins>.&rdquo;<span class='stamp lie'>Lie</span></div>
<div class='foot'><span>Badges on · phones away</span><span>Every lie corrected in red</span></div>
</div></body></html>"""


def social(tmp: Path) -> None:
    f = tmp / "social.html"
    f.write_text(SOCIAL.format(css=base_css(), logo=logo_svg(30), serif=SERIF, mono=MONO))
    save(shoot(f, tmp / "social.png", 1280, 640, scale=1), "social-preview.png")


if __name__ == "__main__":
    if not CHROME:
        sys.exit("Google Chrome or Chromium is needed for headless screenshots.")
    OUT.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, str(ROOT / "scripts" / "draw_badge.py")], check=True)
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        reveal_images(tmp)
        screen_images(tmp)
        social(tmp)
