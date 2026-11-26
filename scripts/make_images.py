"""Regenerate every screenshot in docs/images from real code paths (no mock-ups).

- reveal-*.png:  a simulated game run through hub.live, rendered by hub.reveal
- screen-*.png:  the big-screen page (hub.screen) in its demo states
- social-preview.png: GitHub social card, rendered from HTML in this file

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
from hub.design import base_css, logo_svg  # noqa: E402
from hub.live import DEMO, LiveGame  # noqa: E402
from hub.reveal import build  # noqa: E402
from hub.screen import page  # noqa: E402
from hub.transport import SimClock, SimTransport  # noqa: E402
from sim.world import simulate  # noqa: E402

OUT = ROOT / "docs" / "images"
CHROME = next((p for p in ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                           shutil.which("google-chrome") or "", shutil.which("chromium") or ""] if p and Path(p).exists()),
              None)


def shoot(html: Path, png: Path, w: int, h: int, scale: int = 2, query: str = "") -> None:
    subprocess.run([CHROME, "--headless=new", "--hide-scrollbars", "--disable-gpu", f"--force-device-scale-factor={scale}",
                    f"--window-size={w},{h}", f"--screenshot={png}", html.as_uri() + query],
                   check=True, capture_output=True)


def themed(src: str, theme: str) -> str:
    return src.replace("<html lang='en'>", f"<html lang='en' data-theme='{theme}'>", 1)


def save(img: Image.Image, name: str) -> None:
    img.convert("RGB").save(OUT / name, optimize=True)
    print("wrote", OUT / name)


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
        # show the hover state: light up the first lie on the timeline
        hl = ("<script>const s=document.querySelector('.st .tag.lie')?.closest('.st');"
              "s&&s.dispatchEvent(new Event('mouseenter'));</script></body>")
        f.write_text(themed(html, theme).replace("</body>", hl, 1))
        png = tmp / f"reveal-{theme}.png"
        shoot(f, png, 1100, 3200)
        im = Image.open(png)
        save(im.crop((0, 0, im.width, 1500)), f"reveal-{theme}.png")
        # the timeline is the last section: crop from its heading to the last non-background row
        bg = im.getpixel((5, 5))
        rows = [y for y in range(im.height) if any(im.getpixel((x, y)) != bg for x in range(0, im.width, 7))]
        bottom = rows[-1] + 60
        save(im.crop((0, max(0, bottom - 980), im.width, min(im.height, bottom))), f"timeline-{theme}.png")


def screen_images(tmp: Path) -> None:
    f = tmp / "screen.html"
    f.write_text(themed(page(), "dark"))
    for state in ("play", "meeting", "over"):
        png = tmp / f"screen-{state}.png"
        shoot(f, png, 1440, 810, query=f"?demo={state}")
        save(Image.open(png), f"screen-{state}.png")


SOCIAL = """<!doctype html><html lang='en' data-theme='dark'><head><meta charset='utf-8'><style>{css}
body{{width:1280px;height:640px;padding:72px 84px;display:flex;flex-direction:column;justify-content:space-between}}
h1{{font-size:76px;line-height:1.02;margin:0;font-weight:600}} p{{font-size:28px;margin:18px 0 0;color:var(--muted);max-width:30ch}}
.card{{display:flex;gap:18px;align-items:center;background:var(--surface);border:1px solid var(--line);border-radius:18px;
padding:22px 26px;font-size:30px;width:max-content}} .card .tag{{font-size:16px;padding:4px 12px}}
.mark{{font-size:24px}} .mark svg{{width:40px;height:40px}}</style></head><body>
<span class='mark'>{logo}The Unreliable Narrator</span>
<div><h1 class='serif'>The AI is the traitor.<br>The badges know the truth.</h1>
<p>An in-person party game. ESP32 badges, a lying narrator, and a reveal.</p></div>
<div class='card'><span class='tag lie'>Lie</span><span class='serif'>At 3:40, Karim was in the living room.</span></div>
</body></html>"""


def social(tmp: Path) -> None:
    f = tmp / "social.html"
    f.write_text(SOCIAL.format(css=base_css(), logo=logo_svg(40)))
    png = tmp / "social.png"
    shoot(f, png, 1280, 640, scale=1)
    save(Image.open(png), "social-preview.png")


if __name__ == "__main__":
    if not CHROME:
        sys.exit("Google Chrome or Chromium is needed for headless screenshots.")
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        reveal_images(tmp)
        screen_images(tmp)
        social(tmp)
