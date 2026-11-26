"""The visual language shared by every screen.

Concept: the reveal is the narrator's manuscript, corrected in red by an editor who has
read the surveillance log. Everything is printed in two inks, black and red, on paper,
the way a risograph zine would be:

- black ink for anything true or neutral, red ink only for lies and corrections;
- serif for what the narrator *says*, monospace for what the machines *record*;
- rooms are told apart by print textures (solid, hatch, dots...), never by colour, so
  the log reads the same in colour-blind vision, in greyscale and on paper;
- paper grain and worn rubber stamps are drawn with SVG noise, so everything stays offline.
"""
from __future__ import annotations

from urllib.parse import quote

SERIF = '"Iowan Old Style","Palatino Linotype",Palatino,"Book Antiqua",Georgia,serif'
MONO = '"SF Mono",ui-monospace,Menlo,"Cascadia Mono",Consolas,monospace'


def _svg_uri(svg: str) -> str:
    return "url(\"data:image/svg+xml," + quote(svg) + "\")"


def grain(alpha: float, rgb: str) -> str:
    r, g, b = (int(rgb[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return _svg_uri(
        "<svg xmlns='http://www.w3.org/2000/svg' width='220' height='220'><filter id='n'>"
        "<feTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='3' stitchTiles='stitch'/>"
        f"<feColorMatrix values='0 0 0 0 {r:.3f} 0 0 0 0 {g:.3f} 0 0 0 0 {b:.3f} 0 0 0 {alpha} 0'/></filter>"
        "<rect width='100%' height='100%' filter='url(#n)'/></svg>")


# worn rubber: alpha noise pushed through a steep curve leaves small ink gaps
WORN = _svg_uri(
    "<svg xmlns='http://www.w3.org/2000/svg' width='160' height='60'><filter id='w'>"
    "<feTurbulence type='fractalNoise' baseFrequency='.7' numOctaves='2' seed='4'/>"
    "<feColorMatrix values='0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 -9 6.4'/></filter>"
    "<rect width='100%' height='100%' filter='url(#w)'/></svg>")

# print textures for rooms, in ink; index = room slot
ROOM_TEXTURES = [
    "background:var(--ink);color:var(--paper)",  # solid
    "background:repeating-linear-gradient(45deg,var(--ink) 0 1.6px,transparent 1.6px 4.5px)",  # hatch
    "background:radial-gradient(var(--ink) 1.1px,transparent 1.4px) 0 0/4.5px 4.5px",  # dots
    "background:repeating-linear-gradient(45deg,var(--ink) 0 1.2px,transparent 1.2px 5px),"
    "repeating-linear-gradient(-45deg,var(--ink) 0 1.2px,transparent 1.2px 5px)",  # cross-hatch
    "background:repeating-linear-gradient(0deg,var(--ink) 0 1.4px,transparent 1.4px 4.5px)",  # rules
    "background:repeating-linear-gradient(90deg,var(--ink) 0 1.4px,transparent 1.4px 4.5px)",  # columns
    "background:transparent;box-shadow:inset 0 0 0 1.6px var(--ink)",  # outline
    "background:radial-gradient(var(--ink) 1.6px,transparent 1.9px) 0 0/4px 4px",  # heavy dots
]

_LIGHT = ("--paper:#f2ecdf;--paper-2:#ebe3d2;--ink:#1f1c19;--muted:#6f675b;--rule:#cbbfa9;--red:#cf2e25;"
          "--red-wash:rgba(207,46,37,.09)")
_DARK = ("--paper:#1a1815;--paper-2:#221f1b;--ink:#ece3d1;--muted:#a39a89;--rule:#433d35;--red:#ff5e4f;"
         "--red-wash:rgba(255,94,79,.12)")


def base_css() -> str:
    return f"""
:root{{color-scheme:light;{_LIGHT};--grain:{grain(.11, '#1f1c19')}}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{color-scheme:dark;{_DARK};--grain:{grain(.10, '#ffffff')}}}}}
:root[data-theme="dark"]{{color-scheme:dark;{_DARK};--grain:{grain(.10, '#ffffff')}}}
*{{box-sizing:border-box}}
html{{-webkit-text-size-adjust:100%}}
body{{margin:0;background:var(--paper) var(--grain);color:var(--ink);font:17px/1.55 {SERIF};
  font-variant-numeric:lining-nums}}
.mono{{font-family:{MONO};font-size:.78em;letter-spacing:.04em}}
.caps{{font-family:{MONO};font-size:11.5px;letter-spacing:.16em;text-transform:uppercase}}
.muted{{color:var(--muted)}}
.red{{color:var(--red)}}
.stamp{{display:inline-block;font:700 11.5px/1 {MONO};letter-spacing:.2em;text-transform:uppercase;
  padding:6px 7px 5px 9px;border:2px solid currentColor;border-radius:3px;transform:rotate(-2.5deg);
  -webkit-mask-image:{WORN};mask-image:{WORN};-webkit-mask-size:160px 60px;mask-size:160px 60px;white-space:nowrap}}
.stamp.lie{{color:var(--red);box-shadow:inset 0 0 0 1px currentColor;transform:rotate(3deg)}}
.stamp.true{{color:var(--ink)}}
.stamp.sim{{color:var(--muted);transform:rotate(-1.5deg)}}
"""


def logo_svg(size: int = 28) -> str:
    """Two quotation marks; the second is overprinted in red, slightly off-register."""
    return (f'<svg viewBox="0 0 52 40" width="{size * 1.3:.0f}" height="{size}" aria-hidden="true" '
            'style="overflow:visible">'
            '<path d="M3 30c0-11 5-19 14-23l2.6 4.2C14.4 14 12 17.6 12 21.6h6.4V36H3z" fill="var(--ink)"/>'
            '<path d="M26 30c0-11 5-19 14-23l2.6 4.2C37.4 14 35 17.6 35 21.6h6.4V36H26z" fill="var(--red)" '
            'transform="translate(1.6 -1.2)"/></svg>')


ARM_NAMES = {"template": "random", "heuristic": "rule-based", "llm": "Claude", "template-fill": "random"}
