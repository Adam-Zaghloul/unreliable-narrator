"""Design tokens shared by every screen (reveal page, big screen). No external fonts or
scripts: game night may have no internet.

Look: paper and ink, one accent. Red is reserved for LIE and green for TRUE; both always
come with the word, never colour alone. Room colours are the first slots of a validated
categorical palette, and every room cell also carries the room's letter, so identity never
depends on colour (colour-blind safe past three rooms).
"""

# categorical slots (light, dark), fixed order, never cycled past 8
ROOM_COLORS = [
    ("#257de0", "#338ced"),  # blue
    ("#f47230", "#e76624"),  # orange
    ("#00b894", "#00a888"),  # aqua
    ("#f2a600", "#d28e05"),  # yellow
    ("#ee7fac", "#e24d8b"),  # magenta
    ("#008a17", "#0aac23"),  # green
    ("#6a4ce2", "#9887ef"),  # violet
    ("#ec4647", "#eb6263"),  # red
]

_LIGHT = """
  --bg:#f5f3ee; --surface:#ffffff; --surface-2:#faf9f6; --ink:#1b1a17; --muted:#6b675e; --line:#e4e0d6;
  --lie:#c23a2e; --lie-soft:#fbe9e6; --true:#1f7047; --true-soft:#e5f2ea; --warn:#8a5a00; --warn-soft:#fbf0d9;
  --cell-empty:#ebe8e0; --shadow:0 1px 2px rgba(27,26,23,.06),0 4px 16px rgba(27,26,23,.05);
"""
_DARK = """
  --bg:#121110; --surface:#1b1a18; --surface-2:#22211e; --ink:#efece6; --muted:#a39e93; --line:#34312c;
  --lie:#f07163; --lie-soft:#3a1f1b; --true:#62c08a; --true-soft:#17301f; --warn:#e0b25a; --warn-soft:#33280f;
  --cell-empty:#2a2825; --shadow:none;
"""


def room_vars() -> tuple[str, str]:
    light = "".join(f"--room-{i}:{c[0]};" for i, c in enumerate(ROOM_COLORS))
    dark = "".join(f"--room-{i}:{c[1]};" for i, c in enumerate(ROOM_COLORS))
    return light, dark


def base_css() -> str:
    rl, rd = room_vars()
    return f"""
:root{{color-scheme:light;{_LIGHT}{rl}}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{color-scheme:dark;{_DARK}{rd}}}}}
:root[data-theme="dark"]{{color-scheme:dark;{_DARK}{rd}}}
*{{box-sizing:border-box}}
html{{-webkit-text-size-adjust:100%}}
body{{margin:0;background:var(--bg);color:var(--ink);
  font:16px/1.5 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;font-feature-settings:"tnum" 1}}
.serif{{font-family:"Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif;letter-spacing:-.01em}}
.muted{{color:var(--muted)}}
.mark{{display:inline-flex;align-items:center;gap:10px;font-weight:650;letter-spacing:.01em}}
.mark svg{{width:26px;height:26px}}
.tag{{display:inline-flex;align-items:center;gap:6px;padding:2px 9px;border-radius:999px;font-size:12px;
  font-weight:700;letter-spacing:.06em;text-transform:uppercase}}
.tag.lie{{background:var(--lie);color:#fff}} .tag.true{{background:var(--true);color:#fff}}
.tag.sim{{background:var(--warn-soft);color:var(--warn)}}
:root[data-theme="dark"] .tag.lie,:root[data-theme="dark"] .tag.true{{color:#111}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]) .tag.lie,
  :root:not([data-theme="light"]) .tag.true{{color:#111}}}}
"""


def logo_svg(size: int = 26) -> str:
    """Two quotation marks; the second one is the lie."""
    return (f'<svg viewBox="0 0 48 48" width="{size}" height="{size}" aria-hidden="true">'
            '<path d="M7 30c0-8 4-14 11-17l2 4c-4 2-6 5-6 8h5v12H7z" fill="currentColor"/>'
            '<path d="M27 30c0-8 4-14 11-17l2 4c-4 2-6 5-6 8h5v12H27z" fill="var(--lie)"/></svg>')
