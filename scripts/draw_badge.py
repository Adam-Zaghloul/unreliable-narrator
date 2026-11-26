"""Draws docs/images/badge.svg: an exploded isometric view of the player badge.

Each layer is drawn flat, in millimetres, as seen from above; one isometric transform then
stacks them. Dimensions are the planned ones (50 x 70 mm case, ESP32-C3 SuperMini 18 x 22.5 mm).

    python scripts/draw_badge.py
"""
from __future__ import annotations

import math
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "docs" / "images" / "badge.svg"
S = 2.45  # px per mm
C, Sn = math.cos(math.radians(30)), math.sin(math.radians(30))
W, H = 50, 70  # case, mm
X0, LAYER0, GAP = 330, 52, 104  # screen origin of the top layer, vertical gap between layers


def iso(x: float, y: float, z: float) -> tuple[float, float]:
    """mm on the layer plane (x right, y down the badge) -> screen px; z = layer index."""
    sx = X0 + (x * C - y * C) * S
    sy = LAYER0 + z * GAP + (x * Sn + y * Sn) * S
    return round(sx, 1), round(sy, 1)


def mat(z: float) -> str:
    """SVG matrix that maps layer-plane mm to screen for layer z."""
    ox, oy = iso(0, 0, z)
    return f"matrix({C * S:.4f},{Sn * S:.4f},{-C * S:.4f},{Sn * S:.4f},{ox},{oy})"


def layer(z: float, body: str, side: str | None = None, depth: float = 6) -> str:
    """Flat drawing `body` (in mm) placed on layer z; `side` = a shape extruded downward."""
    out = ""
    if side:
        out += f"<g transform='translate(0 {depth})'><g transform='{mat(z)}'>{side}</g></g>"
    return out + f"<g transform='{mat(z)}'>{body}</g>"


def rrect(x, y, w, h, r, cls, extra=""):
    return f"<rect x='{x}' y='{y}' width='{w}' height='{h}' rx='{r}' class='{cls}' {extra}/>"


BTN = [(15, 54), (35, 54)]  # button centres, mm

shell_top = (rrect(0, 0, W, H, 7, "face w")
             + f"<rect x='20' y='4' width='10' height='3' rx='1.5' class='hole w'/>"
             + "".join(f"<circle cx='{x}' cy='{y}' r='6' class='hole w'/>" for x, y in BTN))
shell_side = rrect(0, 0, W, H, 7, "side w")

caps = (f"<circle cx='{BTN[0][0]}' cy='{BTN[0][1]}' r='5.2' class='inkf'/>"
        f"<circle cx='{BTN[1][0]}' cy='{BTN[1][1]}' r='5.2' class='redf'/>")
caps_side = caps.replace("inkf", "inkf dim").replace("redf", "redf dim")

holes = "".join(f"<circle cx='{x}' cy='{y}' r='.45' class='dotf'/>" for x in range(4, 47, 3) for y in range(4, 67, 3)
                if not (14 <= x <= 36 and 6 <= y <= 31))
supermini = (rrect(16, 7, 18, 22.5, 1, "pcbm w")
             + rrect(21.5, 5.6, 7, 3, 1, "face w")  # USB-C
             + rrect(19, 12, 12, 9, .6, "chip w")  # ESP32-C3 + shield
             + rrect(20.5, 24.5, 9, 3, .4, "chip w")  # ceramic antenna
             + "".join(f"<circle cx='17.4' cy='{9 + i * 2.54:.2f}' r='.6' class='dotf'/>"
                       f"<circle cx='32.6' cy='{9 + i * 2.54:.2f}' r='.6' class='dotf'/>" for i in range(8)))
tact = "".join(rrect(x - 3, y - 3, 6, 6, .5, "chip w") + f"<circle cx='{x}' cy='{y}' r='1.6' class='face w'/>" for x, y in BTN)
mosfet = rrect(40, 36, 3.5, 4.5, .4, "chip w")
pcb = rrect(2, 2, W - 4, H - 4, 3, "pcb w") + holes + supermini + tact + mosfet
pcb_side = rrect(2, 2, W - 4, H - 4, 3, "side w")

lipo = (rrect(6, 10, 38, 30, 2.5, "face w") + rrect(20, 6.5, 10, 3.5, .6, "chip w")
        + "<path d='M23 6.5v-3M27 6.5v-3' class='w'/>"
        + "<path d='M14 25h22' class='w thin' stroke-dasharray='1 1.2'/>")
lipo_side = rrect(6, 10, 38, 30, 2.5, "side w")
motor = ("<circle cx='25' cy='52' r='5' class='face w'/><circle cx='25' cy='52' r='1.6' class='w'/>"
         "<path d='M27 47.5c3-4 8-6 12-6M23 47.5c-2-5-5-8-9-9' class='w thin'/>"
         + rrect(36, 20, 9, 18, 1.2, "face w")  # TP4056 module
         + rrect(38.5, 18.6, 4, 2.4, .6, "chip w"))
motor_side = "<circle cx='25' cy='52' r='5' class='side w'/>" + rrect(36, 20, 9, 18, 1.2, "side w")
back = (rrect(0, 0, W, H, 7, "face w") + "<path d='M7 7h36M7 63h36' class='w thin' stroke-dasharray='1.5 1.5'/>"
        + "<circle cx='25' cy='35' r='9' class='w thin'/>")
back_side = rrect(0, 0, W, H, 7, "side w")

LAYERS = [  # z, body, side, depth, callout point (mm), label, detail
    (0, shell_top, shell_side, 7, (W, 12), "Front shell", "3D-printed PLA, 50 × 70 × 4 mm, lanyard slot"),
    (1, caps, caps_side, 3, BTN[1], "Button caps", "TRUE left, LIE right; red cap marks the lie"),
    (2, pcb, pcb_side, 3, (34, 12), "ESP32-C3 SuperMini on perfboard",
     "BLE scan + ESP-NOW · 2 tactile switches · 2N7000"),
    (3, lipo, lipo_side, 5, (44, 22), "450 mAh LiPo", "battery life still to be measured"),
    (4, motor, motor_side, 3, (45, 30), "Coin motor + TP4056", "the witness-ping buzz · USB-C charging"),
    (5, back, back_side, 7, (W, 40), "Back shell", "snap fit, no screws"),
]

CSS = """
.paper{fill:#f2ecdf}.w{fill:none;stroke:#1f1c19;stroke-width:.55;stroke-linejoin:round;stroke-linecap:round;
  vector-effect:non-scaling-stroke}
.thin{stroke-width:.35}.face{fill:#f7f2e7}.side{fill:#1f1c19}.hole{fill:#e3d9c5}.pcb{fill:#e6dcc8}.pcbm{fill:#d8ccb3}
.chip{fill:#ebe3d2}.inkf{fill:#1f1c19}.redf{fill:#cf2e25}.dim{opacity:.55}.dotf{fill:#1f1c19;opacity:.55}
.lead{stroke:#1f1c19;stroke-width:1;fill:none}.axis{stroke:#6f675b;stroke-width:1;stroke-dasharray:2 4;fill:none}
.redl{stroke:#cf2e25;stroke-width:1.2;fill:none}.redt{fill:#cf2e25}
text{font-family:"SF Mono",ui-monospace,Menlo,Consolas,monospace;font-size:11.5px;letter-spacing:.06em;fill:#1f1c19}
.lbl{font-family:"Iowan Old Style",Palatino,Georgia,serif;font-size:17px;letter-spacing:0}
.s{font-size:10.5px;fill:#6f675b}.n{font-weight:700;font-size:11px;fill:#f2ecdf}
@media (prefers-color-scheme:dark){
  .paper{fill:#1a1815}.w{stroke:#ece3d1}.face{fill:#221f1b}.side{fill:#ece3d1}.hole{fill:#2c2823}.pcb{fill:#2a2620}
  .pcbm{fill:#38322a}.chip{fill:#2f2a24}.inkf{fill:#ece3d1}.redf{fill:#ff5e4f}.dotf{fill:#ece3d1}.lead{stroke:#ece3d1}
  .axis{stroke:#a39a89}.redl{stroke:#ff5e4f}.redt{fill:#ff5e4f}text{fill:#ece3d1}.s{fill:#a39a89}.n{fill:#1a1815}}
"""


def build() -> str:
    o = [f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1200 760' width='1200' height='760' role='img' "
         "aria-labelledby='t d'><title id='t'>Player badge, exploded view</title>"
         "<desc id='d'>Exploded isometric drawing of the planned badge, top to bottom: front shell with two button "
         "holes, button caps (the LIE cap in red), an ESP32-C3 SuperMini on perfboard with two tactile switches, a "
         "450 mAh LiPo, a coin vibration motor with a TP4056 charger, and the back shell. Hardware not built yet."
         f"</desc><style>{CSS}</style>",
         "<defs><filter id='grain'><feTurbulence type='fractalNoise' baseFrequency='.9' numOctaves='3' stitchTiles='stitch'/>"
         "<feColorMatrix values='0 0 0 0 .5 0 0 0 0 .45 0 0 0 0 .38 0 0 0 .16 0'/></filter></defs>",
         "<rect class='paper' width='1200' height='760'/><rect width='1200' height='760' filter='url(#grain)'/>"]
    # assembly axes through two case corners and the button centres
    for pt in [(0, 7), (W, 63), BTN[0], BTN[1]]:
        a, b = iso(*pt, 0), iso(*pt, 5)
        o.append(f"<path class='axis' d='M{a[0]} {a[1]}V{b[1]}'/>")
    for z, body, side, depth, *_ in reversed(LAYERS):  # draw bottom first
        o.append(layer(z, body, side, depth))
    # callouts
    for i, (z, _, _, _, pt, label, detail) in enumerate(LAYERS, 1):
        x, y = iso(*pt, z)
        ty = 98 + (i - 1) * 100
        o.append(f"<path class='lead' d='M{x} {y}L{x + 40} {ty - 4}H690'/><circle cx='{x}' cy='{y}' r='2.4' class='inkf'/>")
        o.append(f"<circle cx='706' cy='{ty - 4}' r='11' class='inkf'/><text class='n' x='706' y='{ty}' "
                 f"text-anchor='middle'>{i}</text>")
        o.append(f"<text class='lbl' x='726' y='{ty}'>{label}</text><text class='s' x='726' y='{ty + 18}'>{detail}</text>")
    # dimension line along the front shell's long edge
    a, b = iso(-4, 0, 0), iso(-4, H, 0)
    m = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    o.append(f"<path class='redl' d='M{a[0]} {a[1]}L{b[0]} {b[1]}'/>"
             f"<path class='redl' d='M{a[0] - 4} {a[1] - 6}l8 12M{b[0] - 4} {b[1] - 6}l8 12'/>"
             f"<text class='redt' x='{m[0] - 58}' y='{m[1] - 6}' transform='rotate(-30 {m[0] - 58} {m[1] - 6})'>70 mm</text>")
    a, b = iso(0, -4, 0), iso(W, -4, 0)
    m = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    o.append(f"<path class='redl' d='M{a[0]} {a[1]}L{b[0]} {b[1]}'/>"
             f"<path class='redl' d='M{a[0] - 4} {a[1] + 6}l8 -12M{b[0] - 4} {b[1] + 6}l8 -12'/>"
             f"<text class='redt' x='{m[0] - 8}' y='{m[1] - 10}' transform='rotate(30 {m[0] - 8} {m[1] - 10})'>50 mm</text>")
    # title block
    o.append("<g><rect x='726' y='650' width='444' height='80' class='lead'/><path class='lead' d='M726 690h444M1030 690v40'/>"
             "<text class='s' x='738' y='666'>TITLE</text><text class='lbl' x='738' y='684'>Player badge · exploded view</text>"
             "<text class='s' x='738' y='706'>STATUS</text><text x='738' y='722' class='redt'>DESIGN ONLY · NOT YET BUILT</text>"
             "<text class='s' x='1042' y='706'>SCALE</text><text x='1042' y='722'>NTS · REV A</text></g>")
    o.append("</svg>")
    return "".join(o)


if __name__ == "__main__":
    OUT.write_text(build())
    print("wrote", OUT)
