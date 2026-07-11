#!/usr/bin/env python
"""Generate the dysonsphere logo family.

  - dysonsphere_logo.svg                              : the mark alone (no text)
  - dysonsphere_favicon.svg                           : the mark cropped tight for a tab icon
  - dysonsphere_logo_portrait_with_text.svg           : mark + wordmark as live <text> (Graphik Light)
  - dysonsphere_logo_portrait_with_text_outlined.svg  : mark + wordmark outlined to <path> paths
                                                        (font-independent; renders anywhere)

The mark is a sphere of flat panels shaded across the MID of the australis palette (a single
dual-mode logo: no near-white to vanish on light, no near-black to vanish on dark) - the star-lit
side emerald, falling through cobalt into deep violet shadow - each facet outlined with a thin
mid-teal stroke, with a bright star glowing inside the shell (through the panel gaps), transparent
background. The wordmark is two-tone (dyson / sphere), Graphik Light, centered on the panel group's
exact horizontal center.

Run:  uv run --no-project --with fonttools python website/logo/gen_dysonsphere_logo.py
(fonttools + Graphik installed are needed only for the outlined variant; the other two always build.)
"""
from __future__ import annotations
import glob
import math
from pathlib import Path

# colors["australis"] reversed to light-first (the palette is stored dark-first).
AUSTRALIS = ["#91EE9F", "#48DEB3", "#27C6C1", "#20ABC1", "#1A90BE", "#1374BA",
             "#2E57AA", "#3A3B92", "#3D1E76", "#370453", "#27022E", "#130010"]

W, H = 200, 210
CX, CY, R = 100, 92, 84
TILT = math.radians(13)
M, N = 5, 12
LON0 = math.pi / N
LATMAX = math.radians(74)
INSET = 0.9
LIGHT = (-0.42, 0.55, 0.72)
_l = math.dist((0, 0, 0), LIGHT); LIGHT = tuple(c / _l for c in LIGHT)
MINIDX, MAXIDX = 1, 9
DYSON, SPHERE = "#1374BA", "#48DEB3"
FONT = "'Graphik Light', 'Graphik-Light', 'Graphik', sans-serif"
WORD, SPLIT, SIZE, BASELINE, WEIGHT = "dysonsphere", 5, 29, 200, 300  # split after "dyson"
HERE = Path(__file__).parent


def normal(lat, lon):
    x, y, z = math.cos(lat) * math.sin(lon), math.sin(lat), math.cos(lat) * math.cos(lon)
    return x, y * math.cos(TILT) - z * math.sin(TILT), y * math.sin(TILT) + z * math.cos(TILT)


def shade(n):
    inten = max(0.0, sum(a * b for a, b in zip(n, LIGHT))) ** 0.85
    return AUSTRALIS[MINIDX + round((1 - inten) * (MAXIDX - MINIDX))]


quads = []
for i in range(M):
    lat0, lat1 = (-LATMAX + 2 * LATMAX * k / M for k in (i, i + 1))
    for j in range(N):
        lo0, lo1 = LON0 + 2 * math.pi * j / N, LON0 + 2 * math.pi * (j + 1) / N
        quads.append([normal(lat0, lo0), normal(lat0, lo1), normal(lat1, lo1), normal(lat1, lo0)])
quads.append([normal(LATMAX, LON0 + 2 * math.pi * j / N) for j in range(N)])

panels = []
for c in quads:
    cn = [sum(p[k] for p in c) / len(c) for k in range(3)]
    _c = math.dist((0, 0, 0), cn); cn = [v / _c for v in cn]
    if cn[2] <= 0.05:
        continue
    pts = [(CX + R * x, CY - R * y) for x, y, _ in c]
    mx, my = sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)
    pts = [(mx + INSET * (x - mx), my + INSET * (y - my)) for x, y in pts]
    panels.append((cn[2], pts, shade(cn)))
panels.sort(key=lambda p: p[0])

xs = [x for _, pts, _ in panels for x, _ in pts]
ys = [y for _, pts, _ in panels for _, y in pts]
CENTER_X = (min(xs) + max(xs)) / 2
CENTER_Y = (min(ys) + max(ys)) / 2

# The star inside the shell: a bright radial-gradient sphere (white-hot -> warm gold -> soft cyan ->
# turquoise) smaller than the shell, glowing out through the panel gaps, plus a turquoise corona.
# Centered (cx/cy 50%) on the panel bbox, which coincides with the sphere centre. Vivid on dark; a
# soft inner luminosity on light.
STAR = [
    "  <defs>",
    '    <radialGradient id="corona" cx="50%" cy="50%" r="50%">',
    '      <stop offset="0.35" stop-color="#5ee7d6" stop-opacity="0.55"/>',
    '      <stop offset="0.72" stop-color="#45e0cf" stop-opacity="0.35"/>',
    '      <stop offset="1" stop-color="#45e0cf" stop-opacity="0"/>',
    "    </radialGradient>",
    '    <radialGradient id="starcore" cx="50%" cy="50%" r="60%">',
    '      <stop offset="0" stop-color="#ffffff"/>',
    '      <stop offset="0.28" stop-color="#ffe6a3"/>',
    '      <stop offset="0.6" stop-color="#8fe6df"/>',
    '      <stop offset="1" stop-color="#45e0cf"/>',
    "    </radialGradient>",
    "  </defs>",
    f'  <circle cx="{CENTER_X:.2f}" cy="{CENTER_Y:.2f}" r="{R * 1.15:.1f}" fill="url(#corona)"/>',
    f'  <circle cx="{CENTER_X:.2f}" cy="{CENTER_Y:.2f}" r="{R * 0.72:.1f}" fill="url(#starcore)"/>',
]
# Panel stroke: a thin mid-teal outline on every facet (an australis stop). Mid-range so it reads
# on both light and dark (dual-mode, like the fills); it firms up the faceting without competing
# with the star glow.
PSTROKE, PWIDTH = "#1A90BE", 0.5
POLYS = [f'  <polygon points="{" ".join(f"{x:.2f},{y:.2f}" for x, y in pts)}" fill="{f}" '
         f'stroke="{PSTROKE}" stroke-width="{PWIDTH}" stroke-linejoin="round"/>'
         for _, pts, f in panels]


def doc(body: list[str], viewbox: str | None = None) -> str:
    head = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{viewbox or f"0 0 {W} {H}"}" fill="none">'
    return "\n".join([head, *STAR, *POLYS, *body, "</svg>"]) + "\n"


def mark_viewbox() -> str:
    # The mark alone gets a tight square centered on the sphere + corona (the portrait canvas
    # would leave the wordmark's dead band below and clip the corona's top edge - the sphere
    # sat visibly off-center wherever the mark is sized by height, e.g. the site header).
    s = R * 1.15 + 2  # corona radius + a hair of padding
    return f"{CENTER_X - s:.2f} {CENTER_Y - s:.2f} {2 * s:.2f} {2 * s:.2f}"


def favicon_doc() -> str:
    # A tab-icon variant: the mark cropped tight around the sphere (centre CX,CY, radius R) so it
    # fills the tiny canvas. The corona's soft outer edge falls outside the square and is dropped,
    # which reads cleaner at 16-32 px than a fuzzy halo.
    pad = 6
    side = 2 * (R + pad)
    head = (f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'viewBox="{CX - R - pad} {CY - R - pad} {side} {side}" fill="none">')
    return "\n".join([head, *STAR, *POLYS, "</svg>"]) + "\n"


def live_text() -> list[str]:
    return [
        f'  <text x="{CENTER_X:.4f}" y="{BASELINE}" text-anchor="middle" font-family="{FONT}" '
        f'font-size="{SIZE}" font-weight="{WEIGHT}" fill="{DYSON}">dyson'
        f'<tspan fill="{SPHERE}">sphere</tspan></text>',
    ]


def outlined_text() -> list[str]:
    from fontTools.pens.boundsPen import BoundsPen
    from fontTools.pens.svgPathPen import SVGPathPen
    from fontTools.ttLib import TTFont

    ttc = next(iter(glob.glob("/System/Library/AssetsV2/com_apple_MobileAsset_Font*/*/AssetData/Graphik.ttc")), None)
    if not ttc:
        raise FileNotFoundError("Graphik.ttc not found")
    font = TTFont(ttc, fontNumber=6)  # 6 = Graphik Light
    scale = SIZE / font["head"].unitsPerEm
    cmap, gs, hmtx = font.getBestCmap(), font.getGlyphSet(), font["hmtx"]
    glyphs = [cmap[ord(c)] for c in WORD]

    pens, acc = [], 0  # left origin of each glyph, in font units
    for g in glyphs:
        pens.append(acc)
        acc += hmtx[g][0]
    bounds = []
    ink_lo, ink_hi = math.inf, -math.inf
    for g, pu in zip(glyphs, pens):
        bp = BoundsPen(gs); gs[g].draw(bp)
        bounds.append(bp.bounds)
        if bp.bounds:
            ink_lo, ink_hi = min(ink_lo, pu + bp.bounds[0]), max(ink_hi, pu + bp.bounds[2])
    x0 = CENTER_X - (ink_lo + ink_hi) / 2 * scale  # center the ink (not the advance) exactly

    paths = []
    for idx, (g, pu, b) in enumerate(zip(glyphs, pens, bounds)):
        if not b:
            continue
        pen = SVGPathPen(gs); gs[g].draw(pen)
        fill = DYSON if idx < SPLIT else SPHERE
        paths.append(
            f'  <path transform="translate({x0 + pu * scale:.3f} {BASELINE}) '
            f'scale({scale:.6f} {-scale:.6f})" fill="{fill}" d="{pen.getCommands()}"/>'
        )
    return paths


(HERE / "dysonsphere_logo.svg").write_text(doc([], mark_viewbox()))
(HERE / "dysonsphere_logo_portrait_with_text.svg").write_text(doc(live_text()))
(HERE / "dysonsphere_favicon.svg").write_text(favicon_doc())
print(f"wrote dysonsphere_logo.svg (mark) + _portrait_with_text.svg + dysonsphere_favicon.svg "
      f"(wordmark centered at x={CENTER_X:.4f})")
try:
    (HERE / "dysonsphere_logo_portrait_with_text_outlined.svg").write_text(doc(outlined_text()))
    print("wrote dysonsphere_logo_portrait_with_text_outlined.svg (glyphs -> paths)")
except Exception as e:  # noqa: BLE001
    print(f"skipped outlined variant: {e}  (needs `--with fonttools` and Graphik installed)")
