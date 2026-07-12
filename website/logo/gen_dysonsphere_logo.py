#!/usr/bin/env python
"""Generate the dysonsphere logo family, in both colour schemes.

Default (mono identity - the black/white brand scheme):
  - dysonsphere_logo.svg                              : the mark alone (no text)
  - dysonsphere_favicon.svg                           : the mark cropped tight for a tab icon
  - dysonsphere_logo_portrait_with_text.svg           : mark + wordmark as live <text> (Graphik Light)
  - dysonsphere_logo_portrait_with_text_outlined.svg  : mark + wordmark outlined to <path> paths,
                                                        with the brand chips behind the two words
                                                        (font-independent; renders anywhere)
  - dysonsphere_logo_horizontal_with_text.svg         : mark LEFT, wordmark RIGHT, vertically centred
                                                        (a hero/lockup title), as live <text>
  - dysonsphere_logo_horizontal_with_text_outlined.svg: the same horizontal lockup, glyphs -> <path>
                                                        (font-independent; the README/OG-image asset)
Heritage (australis) set: the same six files with a `dysonsphere_australis_` prefix.

The mark is a sphere of flat panels shaded by one lighting model; each scheme maps the light
intensity onto its own ramp. Mono: warm paper on the lit side falling into deep ink shadow
(bimodal for graphic punch - NOT the smooth `eclipse` data palette, which shares the endpoints),
ink strokes, a dark core glowing lighter outward through the panel gaps. Australis: emerald lit
side through cobalt into violet shadow, mid-teal strokes, a warm star core with teal corona.

Run:  uv run --no-project --with fonttools python website/logo/gen_dysonsphere_logo.py
(fonttools + Graphik installed are needed for the outlined variants AND both horizontal variants -
the horizontal live-text one measures the wordmark to size its tight viewBox; the mark/favicon/
portrait-live-text always build.)
"""
from __future__ import annotations

import glob
import math
from pathlib import Path

# Per-scheme colour sets. Ramps are light-first (index 0 = brightest); the shader uses
# MINIDX..MAXIDX so the extremes stay reserved for glow/chip accents.
SCHEMES: dict[str, dict] = {
    # The mono identity: warm off-whites jumping to deep inks (bimodal, for punch).
    "": {
        "ramp": ["#FFFFFF", "#FCFBF7", "#F5F4EF", "#EEECE6", "#E4E2DB", "#3F3F3B",
                 "#2C2C29", "#1D1D1B", "#111110", "#070707", "#040404", "#000000"],
        "pstroke": "#8F8F89",
        "dyson": "#141413",
        "sphere": "#8F8F89",
        "corona": [("0.35", "#EEECE6", "0.5"), ("0.72", "#E4E2DB", "0.3"), ("1", "#E4E2DB", "0")],
        # dark core, lighter outward: the panel gaps read as rim light
        "starcore": [("0", "#141413"), ("0.30", "#3F3F3B"), ("0.62", "#8F8F89"), ("1", "#FCFBF7")],
        # the wordmark chips (outlined lockup): [dyson chip bg, dyson text], [sphere chip bg, sphere text]
        "chips": (("#EEECE6", "#141413"), ("#2C2C29", "#FCFBF7")),
    },
    # The heritage set: colors["australis"] (lifted) reversed to light-first.
    "_australis": {
        "ramp": ["#91EE9F", "#4DE0B4", "#28CDC5", "#23B5C9", "#1D9CCB", "#1D83CA",
                 "#3A68BB", "#484DA6", "#4D338C", "#4C196E", "#43044D", "#32022B"],
        "pstroke": "#1D9CCB",
        "dyson": "#1D83CA",
        "sphere": "#4DE0B4",
        "corona": [("0.35", "#5ee7d6", "0.55"), ("0.72", "#45e0cf", "0.35"), ("1", "#45e0cf", "0")],
        "starcore": [("0", "#ffffff"), ("0.28", "#ffe6a3"), ("0.6", "#8fe6df"), ("1", "#45e0cf")],
        "chips": None,  # two-tone text, no chips (the pre-mono wordmark)
    },
}

W, H = 200, 227  # tall enough for the wordmark sitting clear below the sphere AND its corona glow
CX, CY, R = 100, 92, 84
TILT = math.radians(13)
M, N = 5, 12
LON0 = math.pi / N
LATMAX = math.radians(74)
INSET = 0.9
LIGHT = (-0.42, 0.55, 0.72)
_l = math.dist((0, 0, 0), LIGHT); LIGHT = tuple(c / _l for c in LIGHT)
MINIDX, MAXIDX = 1, 9
FONT = "'Graphik Light', 'Graphik-Light', 'Graphik', sans-serif"
WORD, SPLIT, SIZE, BASELINE, WEIGHT = "dysonsphere", 5, 29, 217, 300  # split after "dyson"; chip top clears the corona glow (r = R*1.15 ~ 188.6)
# The horizontal lockup (mark left, wordmark right): a larger wordmark than the portrait's SIZE
# so it reads proportionate beside the sphere, tucked in tight (mark cropped to R+H_MARK_PAD like
# the favicon, so most of the soft corona air is dropped; H_GAP px between the mark and the ink).
H_SIZE, H_GAP, H_MARK_PAD, H_VPAD = 110, 10, 6, 3
HERE = Path(__file__).parent


def normal(lat, lon):
    x, y, z = math.cos(lat) * math.sin(lon), math.sin(lat), math.cos(lat) * math.cos(lon)
    return x, y * math.cos(TILT) - z * math.sin(TILT), y * math.sin(TILT) + z * math.cos(TILT)


def intensity(n) -> float:
    return max(0.0, sum(a * b for a, b in zip(n, LIGHT))) ** 0.85


quads = []
for i in range(M):
    lat0, lat1 = (-LATMAX + 2 * LATMAX * k / M for k in (i, i + 1))
    for j in range(N):
        lo0, lo1 = LON0 + 2 * math.pi * j / N, LON0 + 2 * math.pi * (j + 1) / N
        quads.append([normal(lat0, lo0), normal(lat0, lo1), normal(lat1, lo1), normal(lat1, lo0)])
quads.append([normal(LATMAX, LON0 + 2 * math.pi * j / N) for j in range(N)])

panels = []  # (depth, points, light intensity) - scheme-independent geometry
for c in quads:
    cn = [sum(p[k] for p in c) / len(c) for k in range(3)]
    _c = math.dist((0, 0, 0), cn); cn = [v / _c for v in cn]
    if cn[2] <= 0.05:
        continue
    pts = [(CX + R * x, CY - R * y) for x, y, _ in c]
    mx, my = sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)
    pts = [(mx + INSET * (x - mx), my + INSET * (y - my)) for x, y in pts]
    panels.append((cn[2], pts, intensity(cn)))
panels.sort(key=lambda p: p[0])

xs = [x for _, pts, _ in panels for x, _ in pts]
ys = [y for _, pts, _ in panels for _, y in pts]
CENTER_X = (min(xs) + max(xs)) / 2
CENTER_Y = (min(ys) + max(ys)) / 2

PWIDTH = 0.5


def star_block(scheme: dict) -> list[str]:
    # The star inside the shell: a radial-gradient sphere glowing through the panel gaps,
    # plus a soft corona. Centered on the panel bbox, which coincides with the sphere centre.
    corona = "".join(
        f'\n      <stop offset="{o}" stop-color="{c}" stop-opacity="{a}"/>' for o, c, a in scheme["corona"]
    )
    core = "".join(f'\n      <stop offset="{o}" stop-color="{c}"/>' for o, c in scheme["starcore"])
    return [
        "  <defs>",
        f'    <radialGradient id="corona" cx="50%" cy="50%" r="50%">{corona}',
        "    </radialGradient>",
        f'    <radialGradient id="starcore" cx="50%" cy="50%" r="60%">{core}',
        "    </radialGradient>",
        "  </defs>",
        f'  <circle cx="{CENTER_X:.2f}" cy="{CENTER_Y:.2f}" r="{R * 1.15:.1f}" fill="url(#corona)"/>',
        f'  <circle cx="{CENTER_X:.2f}" cy="{CENTER_Y:.2f}" r="{R * 0.72:.1f}" fill="url(#starcore)"/>',
    ]


def polys(scheme: dict) -> list[str]:
    ramp = scheme["ramp"]
    out = []
    for _, pts, inten in panels:
        fill = ramp[MINIDX + round((1 - inten) * (MAXIDX - MINIDX))]
        out.append(
            f'  <polygon points="{" ".join(f"{x:.2f},{y:.2f}" for x, y in pts)}" fill="{fill}" '
            f'stroke="{scheme["pstroke"]}" stroke-width="{PWIDTH}" stroke-linejoin="round"/>'
        )
    return out


def doc(scheme: dict, body: list[str], viewbox: str | None = None) -> str:
    head = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{viewbox or f"0 0 {W} {H}"}" fill="none">'
    return "\n".join([head, *star_block(scheme), *polys(scheme), *body, "</svg>"]) + "\n"


def mark_viewbox() -> str:
    # The mark alone gets a tight square centered on the sphere + corona (the portrait canvas
    # would leave the wordmark's dead band below and clip the corona's top edge - the sphere
    # sat visibly off-center wherever the mark is sized by height, e.g. the site header).
    s = R * 1.15 + 2  # corona radius + a hair of padding
    return f"{CENTER_X - s:.2f} {CENTER_Y - s:.2f} {2 * s:.2f} {2 * s:.2f}"


def favicon_doc(scheme: dict) -> str:
    # A tab-icon variant: the mark cropped tight around the sphere (centre CX,CY, radius R) so it
    # fills the tiny canvas. The corona's soft outer edge falls outside the square and is dropped,
    # which reads cleaner at 16-32 px than a fuzzy halo.
    pad = 6
    side = 2 * (R + pad)
    head = (f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'viewBox="{CX - R - pad} {CY - R - pad} {side} {side}" fill="none">')
    return "\n".join([head, *star_block(scheme), *polys(scheme), "</svg>"]) + "\n"


def live_text(scheme: dict) -> list[str]:
    return [
        f'  <text x="{CENTER_X:.4f}" y="{BASELINE}" text-anchor="middle" font-family="{FONT}" '
        f'font-size="{SIZE}" font-weight="{WEIGHT}" fill="{scheme["dyson"]}">dyson'
        f'<tspan fill="{scheme["sphere"]}">sphere</tspan></text>',
    ]


def outlined_text(scheme: dict) -> list[str]:
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

    parts: list[str] = []
    if scheme["chips"]:
        # The brand chips behind the two words, replicating the site wordmark: each chip spans
        # its word's ink extents plus the CSS chip padding (0.09em); one shared vertical box
        # (the union of both words' ink) so the chips align like a CSS line box.
        pad = 0.09 * SIZE
        rx = 0.12 * SIZE
        y_lo = min(b[1] for b in bounds if b)
        y_hi = max(b[3] for b in bounds if b)
        top = BASELINE - y_hi * scale - pad
        height = (y_hi - y_lo) * scale + 2 * pad
        # the chips ABUT at the words' ADVANCE boundary (the pen position where 's'
        # begins) - the typographic split, so each word keeps its own side bearing and
        # the seam reads optically even (an ink midpoint crowded the closed 'n' against
        # the open 's'); outer edges keep the chip padding
        word_ink = []
        for lo_i, hi_i in ((0, SPLIT), (SPLIT, len(WORD))):
            wb = [(pu + b[0], pu + b[2]) for pu, b in list(zip(pens, bounds))[lo_i:hi_i] if b]
            word_ink.append((min(w[0] for w in wb) * scale + x0, max(w[1] for w in wb) * scale + x0))
        mid = pens[SPLIT] * scale + x0
        edges = ((word_ink[0][0] - pad, mid), (mid, word_ink[1][1] + pad))
        for (x_lo, x_hi), (bg, _text) in zip(edges, scheme["chips"]):
            parts.append(
                f'  <rect x="{x_lo:.2f}" y="{top:.2f}" width="{x_hi - x_lo:.2f}" '
                f'height="{height:.2f}" rx="{rx:.2f}" fill="{bg}"/>'
            )

    for idx, (g, pu, b) in enumerate(zip(glyphs, pens, bounds)):
        if not b:
            continue
        if scheme["chips"]:
            fill = scheme["chips"][0][1] if idx < SPLIT else scheme["chips"][1][1]
        else:
            fill = scheme["dyson"] if idx < SPLIT else scheme["sphere"]
        pen = SVGPathPen(gs); gs[g].draw(pen)
        parts.append(
            f'  <path transform="translate({x0 + pu * scale:.3f} {BASELINE}) '
            f'scale({scale:.6f} {-scale:.6f})" fill="{fill}" d="{pen.getCommands()}"/>'
        )
    return parts


def _graphik_font():
    from fontTools.ttLib import TTFont

    ttc = next(iter(glob.glob("/System/Library/AssetsV2/com_apple_MobileAsset_Font*/*/AssetData/Graphik.ttc")), None)
    if not ttc:
        raise FileNotFoundError("Graphik.ttc not found")
    return TTFont(ttc, fontNumber=6)  # 6 = Graphik Light


def _horizontal_layout(font):
    """Shared geometry for the horizontal lockup - mark left, wordmark right, vertically centred.

    Returns ``(scale, x0, baseline, pens, bounds, glyphs, gs, viewbox)``: the wordmark's glyph
    origins (``pens``, font units), ink ``bounds``, the font-unit->px ``scale``, the left origin
    ``x0`` and ``baseline`` px positions, and the tight ``viewbox`` (mark cropped to R+H_MARK_PAD,
    the wordmark ink starting H_GAP px right of it, its baseline->cap body centred on the sphere).
    Shared so the live-text and outlined horizontal variants lay out identically.
    """
    from fontTools.pens.boundsPen import BoundsPen

    scale = H_SIZE / font["head"].unitsPerEm
    cmap, gs, hmtx = font.getBestCmap(), font.getGlyphSet(), font["hmtx"]
    glyphs = [cmap[ord(c)] for c in WORD]
    pens, acc = [], 0
    for g in glyphs:
        pens.append(acc)
        acc += hmtx[g][0]
    bounds = []
    for g in glyphs:
        bp = BoundsPen(gs)
        gs[g].draw(bp)
        bounds.append(bp.bounds)
    ink_lo = min(pu + b[0] for pu, b in zip(pens, bounds) if b)
    ink_hi = max(pu + b[2] for pu, b in zip(pens, bounds) if b)
    y_hi = max(b[3] for b in bounds if b)  # ascender/cap top (font units)

    mh = R + H_MARK_PAD  # mark half-extent: crop to the sphere, drop most of the soft corona air
    x0 = (CENTER_X + mh + H_GAP) - ink_lo * scale  # leftmost ink sits H_GAP px right of the mark
    baseline = CENTER_Y + y_hi / 2 * scale  # centre the baseline->cap body on the sphere centre
    text_right = x0 + ink_hi * scale
    vb_x, vb_y = CENTER_X - mh - H_VPAD, CENTER_Y - mh - H_VPAD
    vb_w, vb_h = (text_right + H_VPAD) - vb_x, 2 * mh + 2 * H_VPAD
    viewbox = f"{vb_x:.2f} {vb_y:.2f} {vb_w:.2f} {vb_h:.2f}"
    return scale, x0, baseline, pens, bounds, glyphs, gs, viewbox


def horizontal_live_text(scheme: dict) -> str:
    _s, x0, baseline, *_rest, viewbox = _horizontal_layout(_graphik_font())
    text = [
        f'  <text x="{x0:.4f}" y="{baseline:.4f}" text-anchor="start" font-family="{FONT}" '
        f'font-size="{H_SIZE}" font-weight="{WEIGHT}" fill="{scheme["dyson"]}">dyson'
        f'<tspan fill="{scheme["sphere"]}">sphere</tspan></text>',
    ]
    return doc(scheme, text, viewbox)


def horizontal_outlined_text(scheme: dict) -> str:
    from fontTools.pens.svgPathPen import SVGPathPen

    scale, x0, baseline, pens, bounds, glyphs, gs, viewbox = _horizontal_layout(_graphik_font())
    parts = []
    for idx, (g, pu, b) in enumerate(zip(glyphs, pens, bounds)):
        if not b:
            continue
        fill = scheme["dyson"] if idx < SPLIT else scheme["sphere"]
        pen = SVGPathPen(gs)
        gs[g].draw(pen)
        parts.append(
            f'  <path transform="translate({x0 + pu * scale:.3f} {baseline:.3f}) '
            f'scale({scale:.6f} {-scale:.6f})" fill="{fill}" d="{pen.getCommands()}"/>'
        )
    return doc(scheme, parts, viewbox)


for suffix, scheme in SCHEMES.items():
    prefix = f"dysonsphere{suffix}"
    (HERE / f"{prefix}_logo.svg").write_text(doc(scheme, [], mark_viewbox()))
    (HERE / f"{prefix}_logo_portrait_with_text.svg").write_text(doc(scheme, live_text(scheme)))
    (HERE / f"{prefix}_favicon.svg").write_text(favicon_doc(scheme))
    print(f"wrote {prefix}_logo.svg (mark) + _portrait_with_text.svg + {prefix}_favicon.svg")
    try:
        (HERE / f"{prefix}_logo_portrait_with_text_outlined.svg").write_text(doc(scheme, outlined_text(scheme)))
        (HERE / f"{prefix}_logo_horizontal_with_text.svg").write_text(horizontal_live_text(scheme))
        (HERE / f"{prefix}_logo_horizontal_with_text_outlined.svg").write_text(horizontal_outlined_text(scheme))
        print(f"wrote {prefix}_logo_portrait_with_text_outlined.svg + _horizontal_with_text{{,_outlined}}.svg")
    except Exception as e:  # noqa: BLE001
        print(f"skipped outlined/horizontal variants: {e}  (needs `--with fonttools` and Graphik installed)")
