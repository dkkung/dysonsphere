"""
Generator for theme/palettes.py custom palette family.

Lives at /scripts/ rather than /theme/theme/ so the build logic is version
controlled but doesn't ship with the installed package.

Documents and reproduces every recipe used to construct the custom
sequential and diverging palettes:

  Recipe 1. Sequential single-hue
       At each L, set chroma = frac × max_gamut_chroma(L, hue).
       Densify path; resample N stops at equal arc length.
       Used for: blues, greens, purples, reds, greys, yellows, cyans,
                 magentas, browns, lavenders, byzantiums.

  Recipe 2. Sequential multi-hue (hue keyframes)
       Interpolate (L, hue) linearly between keyframes; at each
       interpolated point compute chroma as in recipe 1.  Same arc-length
       resample.
       Used for: ember, dusk, moss, GnBu, YlGnBu, candy, oranges, lagoon,
                 bluestgrotto/bluergrotto/bluegrotto ladder, and the
                 celestial family nebula/cosmos/borealis/australis (all
                 with an absolute max_chroma cap, see build_multihue;
                 cosmos/borealis/australis also with FRAC=0.95).

  Recipe 3. Diverging (V-shape with white pivot)
       Two arms meeting at an exact-white centre stop.  Each arm: L sweeps
       from dark→centre; C(L) = frac × min(max_gamut(L, h_arm),
       max_gamut(L, h_other_arm)) × (1 - t) where t goes 0→1 from dark to
       centre.  Each arm sampled at HALF stops at equal arc length;
       concatenated as arm2 + [centre] + reversed(arm1).
       Odd N=13 so the pivot lands exactly on the V-corner.
       Used for: RdBu, PuGn, BrTe, GdBu, MgGn, YlPu (FRAC=0.85)
                 and _sat variants of each (FRAC=1.0).

  Recipe 4. Chroma-scaling desaturation
       Preserve L, scale (a, b) by < 1.  Used to derive the lighter
       bluegrotto / bluergrotto companions from the saturated
       bluestgrotto base.

Color spaces:
  - Oklab (Ottosson 2020) is the working space for all current palettes.
  - CIELAB recipes are kept here for reproducibility; CIELAB palette
    variants were dropped from palettes.py in favor of Oklab, which has
    lower hue non-linearity (especially in the blue region) and is the
    current state of the art for perceptual uniformity.

Usage:
    uv run python scripts/build/print_palettes.py

Prints Python literals for each built palette to stdout.  Use to diff
against palettes.py or to extend with new families.

Note: a few palettes in palettes.py have been hand-tweaked beyond the
canonical recipe (e.g. lagoon's stop 11 was symmetrically reflected to
flatten the final ΔE step; the bluergrotto family was iterated to
sharpen the purple→blue transition).  Where this script and palettes.py
diverge, palettes.py is the source of truth — this script documents the
recipe, not exact byte-for-byte output.
"""

import math

from dysonsphere.palettes import colors as _pal

# ── Build parameters ─────────────────────────────────────────────────────

N_OUT_SEQ = 12  # stops per sequential palette
N_OUT_DIVERG = 13  # stops per diverging palette (odd → white pivot)
N_DENSE = 4000  # dense path resolution before arc-length resampling

# Default chroma fractions (of gamut max at each L)
SEQ_FRAC = 0.65  # sequential single-hue and multi-hue
DIVERG_FRAC = 0.85  # diverging base palettes
DIVERG_SAT_FRAC = 1.0  # *_sat diverging variants
PASTEL_FRAC = 0.35  # sequential single-hue "3" (pastel) variants
PASTEL_L_LO = 0.70  # dark end: stays medium-light (true pastel territory)
PASTEL_L_HI = 0.95  # light end: nearly white


# ── sRGB ↔ linear ───────────────────────────────────────────────────────


def _lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _gamma(c):
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def _clamp(v):
    return max(0.0, min(1.0, v))


def _hex_rgb(hx):
    h = hx.lstrip("#")
    return [int(h[i : i + 2], 16) / 255 for i in (0, 2, 4)]


def _rgb_hex(r, g, b):
    return "#{:02X}{:02X}{:02X}".format(
        round(_clamp(_gamma(_clamp(r))) * 255),
        round(_clamp(_gamma(_clamp(g))) * 255),
        round(_clamp(_gamma(_clamp(b))) * 255),
    )


# ── CIELAB (D65) ─────────────────────────────────────────────────────────


def hex_to_lab(hx):
    r, g, b = [_lin(c) for c in _hex_rgb(hx)]
    X = 0.4124564 * r + 0.3575761 * g + 0.1804375 * b
    Y = 0.2126729 * r + 0.7151522 * g + 0.0721750 * b
    Z = 0.0193339 * r + 0.1191920 * g + 0.9503041 * b
    Xn, Yn, Zn = 0.95047, 1.0, 1.08883
    d = 6 / 29

    def f(t):
        return t ** (1 / 3) if t > d**3 else t / (3 * d * d) + 4 / 29

    fx, fy, fz = f(X / Xn), f(Y / Yn), f(Z / Zn)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def lab_to_rgb(L, a, b):
    fy = (L + 16) / 116
    fx = fy + a / 500
    fz = fy - b / 200
    d = 6 / 29

    def finv(t):
        return t**3 if t > d else 3 * d * d * (t - 4 / 29)

    Xn, Yn, Zn = 0.95047, 1.0, 1.08883
    X = Xn * finv(fx)
    Y = Yn * finv(fy)
    Z = Zn * finv(fz)
    return (
        3.2404542 * X - 1.5371385 * Y - 0.4985314 * Z,
        -0.9692660 * X + 1.8760108 * Y + 0.0415560 * Z,
        0.0556434 * X - 0.2040259 * Y + 1.0572252 * Z,
    )


def lab_to_hex(L, a, b):
    return _rgb_hex(*lab_to_rgb(L, a, b))


def in_gamut_lab(L, a, b):
    return all(-1e-6 <= v <= 1 + 1e-6 for v in lab_to_rgb(L, a, b))


def max_chroma_lab(L, h_rad):
    """Binary search for the largest in-gamut chroma at (L, hue)."""
    lo, hi = 0.0, 180.0
    for _ in range(50):
        mid = (lo + hi) / 2
        if in_gamut_lab(L, mid * math.cos(h_rad), mid * math.sin(h_rad)):
            lo = mid
        else:
            hi = mid
    return lo


# ── Oklab (Ottosson 2020) ────────────────────────────────────────────────


def hex_to_oklab(hx):
    r, g, b = [_lin(c) for c in _hex_rgb(hx)]
    lv = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l_, m_, s_ = lv ** (1 / 3), m ** (1 / 3), s ** (1 / 3)
    return (
        0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
        1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
        0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_,
    )


def oklab_to_rgb(L, a, b):
    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b
    lv, m, s = l_**3, m_**3, s_**3
    return (
        4.0767416621 * lv - 3.3077115913 * m + 0.2309699292 * s,
        -1.2684380046 * lv + 2.6097574011 * m - 0.3413193965 * s,
        -0.0041960863 * lv - 0.7034186147 * m + 1.7076147010 * s,
    )


def oklab_to_hex(L, a, b):
    return _rgb_hex(*oklab_to_rgb(L, a, b))


def in_gamut_oklab(L, a, b):
    return all(-1e-6 <= v <= 1 + 1e-6 for v in oklab_to_rgb(L, a, b))


def max_chroma_oklab(L, h_rad):
    """Binary search for the largest in-gamut chroma at (L, hue)."""
    lo, hi = 0.0, 0.5
    for _ in range(50):
        mid = (lo + hi) / 2
        if in_gamut_oklab(L, mid * math.cos(h_rad), mid * math.sin(h_rad)):
            lo = mid
        else:
            hi = mid
    return lo


# ── Space-agnostic helpers ───────────────────────────────────────────────


def _space(name):
    """Dispatch table for color space conversions."""
    return {
        "oklab": (hex_to_oklab, oklab_to_hex, max_chroma_oklab),
        "cielab": (hex_to_lab, lab_to_hex, max_chroma_lab),
    }[name]


def _unwrap_hues(keyframes):
    """Hue keyframes can cross 360°.  Convert to a monotonic sequence by
    following the shorter rotation direction at the first ambiguous step.
    Required so linear interpolation between keyframes doesn't take the
    wrong way around the colour wheel."""
    out = [keyframes[0]]
    direction = 0
    for L_new, h_new in keyframes[1:]:
        _, h_prev = out[-1]
        h_360 = h_new % 360
        up = (h_360 - h_prev) % 360
        down = (h_prev - h_360) % 360
        if direction == 0:
            direction = +1 if up <= down else -1
        h_un = h_prev + (up if direction == +1 else -down)
        out.append((L_new, h_un))
    return out


def _arc_resample(Ld, ad, bd, n_out, to_hex):
    """Sample n_out stops at equal arc length along a dense (L, a, b) path."""
    arc = [0.0]
    for i in range(1, len(Ld)):
        arc.append(arc[-1] + math.sqrt((Ld[i] - Ld[i - 1]) ** 2 + (ad[i] - ad[i - 1]) ** 2 + (bd[i] - bd[i - 1]) ** 2))
    total = arc[-1]
    out, j = [], 0
    for k in range(n_out):
        target = k * total / (n_out - 1)
        while j < len(Ld) - 1 and arc[j + 1] <= target:
            j += 1
        if j == 0 or arc[j] <= target:
            out.append(to_hex(Ld[j], ad[j], bd[j]))
        else:
            ti = (target - arc[j - 1]) / (arc[j] - arc[j - 1])
            out.append(
                to_hex(
                    Ld[j - 1] + ti * (Ld[j] - Ld[j - 1]),
                    ad[j - 1] + ti * (ad[j] - ad[j - 1]),
                    bd[j - 1] + ti * (bd[j] - bd[j - 1]),
                )
            )
    return out


# ── Recipe 1: sequential single-hue ──────────────────────────────────────


def build_single_hue(hue_deg, L_lo, L_hi, *, space="oklab", frac=SEQ_FRAC, n=N_OUT_SEQ):
    """
    Fixed hue, L sweeping L_hi → L_lo, chroma at each L = frac × gamut_max.
    Equal arc-length resample to n stops.

    L_hi/L_lo are in the working space's L range:
      oklab:  0..1
      cielab: 0..100
    """
    _, to_hex, max_c = _space(space)
    hr = math.radians(hue_deg)
    Ld, ad, bd = [], [], []
    for i in range(N_DENSE):
        s = i / (N_DENSE - 1)
        L = L_hi + s * (L_lo - L_hi)
        C = frac * max_c(L, hr)
        Ld.append(L)
        ad.append(C * math.cos(hr))
        bd.append(C * math.sin(hr))
    return _arc_resample(Ld, ad, bd, n, to_hex)


# ── Recipe 2: sequential multi-hue (keyframe path) ───────────────────────


def build_multihue(keyframes, *, space="oklab", frac=SEQ_FRAC, n=N_OUT_SEQ, max_chroma=None):
    """
    keyframes: list of (L, hue_deg) tuples ordered along the palette.
    Linear interpolation between consecutive keyframes in both L and hue
    (after hue unwrapping); chroma at each interpolated point as in
    recipe 1.  Equal arc-length resample to n stops.

    max_chroma: optional absolute chroma ceiling applied after the frac
    rule.  Paths crossing the sRGB blue gamut bulge (hue ~250-280) pick
    up a chroma spike that bunches the lightness steps under arc-length
    resampling; a cap flattens the spike so the L ramp stays even
    (greyscale-safe).  Used for: nebula (0.14).
    """
    _, to_hex, max_c = _space(space)
    kf = _unwrap_hues(keyframes)
    n_k = len(kf)
    Ld, ad, bd = [], [], []
    for i in range(N_DENSE):
        s = i / (N_DENSE - 1)
        idx = s * (n_k - 1)
        i0 = int(idx)
        i1 = min(i0 + 1, n_k - 1)
        t = idx - i0
        L = kf[i0][0] + t * (kf[i1][0] - kf[i0][0])
        h = kf[i0][1] + t * (kf[i1][1] - kf[i0][1])
        hr = math.radians(h)
        C = frac * max_c(L, hr)
        if max_chroma is not None:
            C = min(C, max_chroma)
        Ld.append(L)
        ad.append(C * math.cos(hr))
        bd.append(C * math.sin(hr))
    return _arc_resample(Ld, ad, bd, n, to_hex)


# ── Recipe 3: diverging (V-shape with white pivot) ───────────────────────


def build_diverging(
    arm2_dark_hex,
    arm1_dark_hex,
    *,
    center_hex="#F6F6F6",
    space="oklab",
    frac=DIVERG_FRAC,
    n=N_OUT_DIVERG,
):
    """
    Two arms meeting at center_hex.  Each arm sampled at HALF stops along
    a chroma-decreasing V path; concatenated as
        arm2_dark...arm2_light + [centre] + arm1_light...arm1_dark.

    n must be odd so the pivot lands exactly on the V-corner (else the
    arc-length sampling produces a small "dip" step at the centre).
    """
    if n % 2 != 1:
        raise ValueError("diverging palettes need odd n (white pivot on V-corner)")
    half = n // 2
    hex_to, to_hex, max_c = _space(space)
    L_center, _, _ = hex_to(center_hex)

    def build_arm(arm_dark, other_dark):
        L_dark, a_d, b_d = hex_to(arm_dark)
        achromatic = (a_d * a_d + b_d * b_d) < 1e-8
        h_arm = math.atan2(b_d, a_d)
        _, a_o, b_o = hex_to(other_dark)
        h_other = math.atan2(b_o, a_o)
        Ld, ad, bd = [], [], []
        for i in range(N_DENSE):
            s = i / (N_DENSE - 1)
            L = L_dark + (L_center - L_dark) * s
            t = 1 - s  # 1 at dark end → 0 at centre
            # Achromatic endpoints (pure greys) have undefined hue; force C=0.
            C = 0.0 if achromatic else frac * min(max_c(L, h_arm), max_c(L, h_other)) * t
            Ld.append(L)
            ad.append(C * math.cos(h_arm))
            bd.append(C * math.sin(h_arm))
        # Sample HALF stops at equal arc length, ending just shy of centre.
        # (Pivot is inserted separately so it equals center_hex exactly.)
        arc = [0.0]
        for i in range(1, N_DENSE):
            arc.append(
                arc[-1] + math.sqrt((Ld[i] - Ld[i - 1]) ** 2 + (ad[i] - ad[i - 1]) ** 2 + (bd[i] - bd[i - 1]) ** 2)
            )
        total = arc[-1]
        out, j = [], 0
        for k in range(half):
            target = k * total / half
            while j < N_DENSE - 1 and arc[j + 1] <= target:
                j += 1
            if j == 0 or arc[j] <= target:
                out.append(to_hex(Ld[j], ad[j], bd[j]))
            else:
                ti = (target - arc[j - 1]) / (arc[j] - arc[j - 1])
                out.append(
                    to_hex(
                        Ld[j - 1] + ti * (Ld[j] - Ld[j - 1]),
                        ad[j - 1] + ti * (ad[j] - ad[j - 1]),
                        bd[j - 1] + ti * (bd[j] - bd[j - 1]),
                    )
                )
        return out

    arm2 = build_arm(arm2_dark_hex, arm1_dark_hex)
    arm1 = build_arm(arm1_dark_hex, arm2_dark_hex)
    return arm2 + [center_hex] + arm1[::-1]


# ── Recipe 4: chroma-scaling desaturation ────────────────────────────────


def desaturate(hexes, scale, *, space="oklab"):
    """
    Preserve L; scale (a, b) by `scale` (< 1 to desaturate, > 1 to push
    further out of gamut → likely clipping).
    """
    hex_to, to_hex, _ = _space(space)
    return [to_hex(L, a * scale, b * scale) for L, a, b in (hex_to(h) for h in hexes)]


# ── Palette specifications ──────────────────────────────────────────────
# These are representative specs — the values in palettes.py have been
# iterated and may differ slightly.  Adjust hues/L to taste; the recipes
# guarantee perceptual uniformity at whatever parameters you supply.

# Single-hue Oklab.  Format: name → (hue_deg, L_lo, L_hi).
# L_hi=0.92 is just below pure-white where gamut chroma collapses to 0;
# L_lo varies by hue because some hues (yellow, cyan) lose their identity
# in sRGB at very low L.
SEQ_SINGLE_OKLAB = {
    "blues": (260, 0.22, 0.92),
    "greens": (140, 0.22, 0.92),
    "purples": (310, 0.22, 0.92),
    "greys": (0, 0.13, 0.94),  # any hue works at chroma=0
    "reds": (20, 0.22, 0.92),
    "rose": (350, 0.22, 0.92),
    "yellows": (110, 0.45, 0.92),
    "cyans": (200, 0.32, 0.92),
    "magentas": (330, 0.25, 0.92),
    "byzantiums": (290, 0.22, 0.92),
    "lavenders": (285, 0.30, 0.95),
}

# All 14 base single-hue palettes in gallery order — used to build "3" pastel set.
SEQ_SINGLE_NAMES = [
    "blues",
    "greens",
    "purples",
    "lavenders",
    "violets",
    "greys",
    "reds",
    "pinks",
    "oranges",
    "browns",
    "yellows",
    "cyans",
    "magentas",
    "neongreens",
]

# Multi-hue Oklab keyframes.  Format: name → [(L, hue_deg), ...] light → dark.
SEQ_MULTI_OKLAB = {
    # Warm-into-magenta sweep (ember stays in the warm/magenta arc).
    "ember": [
        (0.93, 95),
        (0.78, 60),
        (0.62, 25),
        (0.46, 5),
        (0.32, 340),
        (0.20, 320),
    ],
    # Warm cream → coral → magenta → indigo (deeper hue rotation than ember).
    "dusk": [
        (0.93, 85),
        (0.78, 50),
        (0.62, 20),
        (0.46, 350),
        (0.32, 305),
        (0.20, 270),
    ],
    # Cream → gold → green → forest.
    "moss": [
        (0.93, 90),
        (0.78, 95),
        (0.62, 105),
        (0.46, 130),
        (0.32, 145),
        (0.20, 150),
    ],
    # Yellow-green → green → blue (matplotlib analogue).
    "GnBu": [
        (0.93, 110),
        (0.78, 130),
        (0.62, 160),
        (0.46, 195),
        (0.32, 230),
        (0.20, 250),
    ],
    "YlGnBu": [
        (0.93, 100),
        (0.78, 115),
        (0.62, 145),
        (0.46, 180),
        (0.32, 220),
        (0.20, 250),
    ],
    # Cream-pink → magenta → purple.
    "candy": [
        (0.93, 0),
        (0.78, 350),
        (0.62, 335),
        (0.46, 320),
        (0.32, 295),
        (0.20, 275),
    ],
    # Vivid orange: light end slight yellow, dark end slight red.
    "oranges": [
        (0.92, 95),
        (0.78, 80),
        (0.62, 65),
        (0.47, 50),
        (0.38, 40),
    ],
    # Cool single-hue lagoon (deep navy → teal → mint).
    "lagoon": [
        (0.93, 130),
        (0.82, 160),
        (0.62, 180),
        (0.42, 220),
        (0.20, 250),
    ],
    # Showcase: purple-anchored cool sweep with uniform per-segment rotation.
    "bluestgrotto": [
        (0.27, 285),
        (0.41, 260),
        (0.55, 230),
        (0.68, 200),
        (0.80, 178),
        (0.93, 155),
    ],
    # Viridis alternative: deep slate-teal → indigo → periwinkle → orchid →
    # pale rose (stored dark-first, viridis polarity).  Chroma capped at
    # 0.14 to flatten the sRGB blue-gamut spike and keep the L ramp even.
    "nebula": [
        (0.21, 208),
        (0.35, 232),
        (0.50, 262),
        (0.65, 300),
        (0.80, 335),
        (0.93, 365),
    ],
    # nebula's magma: same hue route shifted darker (near-black floor), so
    # the light end stops at a saturated pink instead of near-white rose.
    # FRAC=0.95 supplies the pink's chroma; the 0.14 cap keeps the ramp even.
    "cosmos": [
        (0.13, 205),
        (0.28, 232),
        (0.42, 262),
        (0.56, 300),
        (0.68, 335),
        (0.80, 352),
    ],
    # The viridis analogue (dark-first): rich violet floor → cobalt →
    # azure-teal → luminous emerald, saturated at both ends.  Matches
    # viridis's step uniformity (adjacent ΔE ratio 1.06 vs 1.05) and beats
    # it under protanopia (1.28/min 0.061 vs 2.01/min 0.038, Machado 1.0);
    # L monotonic under both dichromacies.
    "borealis": [
        (0.15, 297),
        (0.33, 268),
        (0.52, 235),
        (0.70, 190),
        (0.86, 143),
    ],
    # borealis's journey extended through cosmos's magenta territory: deep
    # magenta-wine fringe → violet → cobalt → azure → teal → the same
    # emerald curtain (~190° of rotation, the widest in the collection).
    # Adjacent ΔE ratio 1.03 (viridis 1.05); L monotonic under both
    # dichromacies (deut 1.34/min 0.064, prot 1.33/min 0.065, Machado 1.0).
    "australis": [
        (0.13, 335),
        (0.28, 305),
        (0.44, 270),
        (0.60, 235),
        (0.74, 195),
        (0.87, 148),
    ],
}

# Per-palette frac overrides for build_multihue (default SEQ_FRAC).
SEQ_MULTI_FRAC = {
    "cosmos": 0.95,
    "borealis": 0.95,
    "australis": 0.95,
}

# Per-palette max_chroma overrides for build_multihue (see its docstring).
SEQ_MULTI_MAX_CHROMA = {
    "nebula": 0.14,
    "cosmos": 0.14,
    "borealis": 0.14,
    "australis": 0.14,
}

# Diverging arm endpoints.  Format: name → (arm2_dark, arm1_dark) hex.
# Center is always #F6F6F6.  Both the base and _sat variants share these
# endpoints; the difference is FRAC (0.85 vs 1.0).
DIVERG_OKLAB = {
    "RdBu": ("#7C3745", "#215080"),
    "PuGn": ("#574380", "#1A5929"),
    "BrTe": ("#684637", "#1C5464"),
    "GdBu": ("#614931", "#1C5464"),
    "MgGn": ("#6A397E", "#1A5919"),
    "YlPu": ("#574E11", "#2D4D84"),
}

# Pairs of "2"-suffix sequential palettes for diverging construction.
# Endpoints use index 7 of each arm palette — same rule as the regular pairs.
DIVERG_SEQ2_PAIRS = [
    ("reds2", "blues2"),
    ("purples2", "greens2"),
    ("lavenders2", "greens2"),
    ("lavenders2", "blues2"),
    ("purples2", "blues2"),
    ("browns2", "blues2"),
    ("pinks2", "blues2"),
    ("greys2", "blues2"),
    ("greys2", "reds2"),
    ("greys2", "purples2"),
    ("greys2", "lavenders2"),
    ("greys2", "pinks2"),
    ("greens2", "blues2"),
    ("reds2", "greens2"),
    ("reds2", "cyans2"),
    ("reds2", "lavenders2"),
    ("reds2", "violets2"),
    ("reds2", "neongreens2"),
    ("pinks2", "cyans2"),
    ("pinks2", "greens2"),
    ("pinks2", "neongreens2"),
    ("oranges2", "blues2"),
    ("oranges2", "cyans2"),
    ("oranges2", "purples2"),
    ("oranges2", "lavenders2"),
    ("oranges2", "violets2"),
    ("oranges2", "neongreens2"),
    ("yellows2", "blues2"),
    ("yellows2", "purples2"),
    ("yellows2", "lavenders2"),
    ("browns2", "greens2"),
    ("browns2", "cyans2"),
    ("browns2", "neongreens2"),
    ("magentas2", "neongreens2"),
    ("magentas2", "greens2"),
    ("magentas2", "blues2"),
    ("magentas2", "cyans2"),
    ("violets2", "oranges2"),
    ("violets2", "yellows2"),
    ("cyans2", "purples2"),
    ("cyans2", "lavenders2"),
    ("cyans2", "violets2"),
    ("purples2", "neongreens2"),
    ("lavenders2", "neongreens2"),
    ("greys2", "greens2"),
    ("greys2", "yellows2"),
    ("greys2", "oranges2"),
    ("greys2", "cyans2"),
    ("greys2", "magentas2"),
    ("greys2", "violets2"),
    ("greys2", "neongreens2"),
]

DIVERG_SEQ3_PAIRS = [
    ("reds3", "blues3"),
    ("purples3", "greens3"),
    ("lavenders3", "greens3"),
    ("lavenders3", "blues3"),
    ("purples3", "blues3"),
    ("browns3", "blues3"),
    ("pinks3", "blues3"),
    ("greys3", "blues3"),
    ("greys3", "reds3"),
    ("greys3", "purples3"),
    ("greys3", "lavenders3"),
    ("greys3", "pinks3"),
    ("greens3", "blues3"),
    ("reds3", "greens3"),
    ("reds3", "cyans3"),
    ("reds3", "lavenders3"),
    ("reds3", "violets3"),
    ("reds3", "neongreens3"),
    ("pinks3", "cyans3"),
    ("pinks3", "greens3"),
    ("pinks3", "neongreens3"),
    ("oranges3", "blues3"),
    ("oranges3", "cyans3"),
    ("oranges3", "purples3"),
    ("oranges3", "lavenders3"),
    ("oranges3", "violets3"),
    ("oranges3", "neongreens3"),
    ("yellows3", "blues3"),
    ("yellows3", "purples3"),
    ("yellows3", "lavenders3"),
    ("browns3", "greens3"),
    ("browns3", "cyans3"),
    ("browns3", "neongreens3"),
    ("magentas3", "neongreens3"),
    ("magentas3", "greens3"),
    ("magentas3", "blues3"),
    ("magentas3", "cyans3"),
    ("violets3", "oranges3"),
    ("violets3", "yellows3"),
    ("cyans3", "purples3"),
    ("cyans3", "lavenders3"),
    ("cyans3", "violets3"),
    ("purples3", "neongreens3"),
    ("lavenders3", "neongreens3"),
    ("greys3", "greens3"),
    ("greys3", "yellows3"),
    ("greys3", "oranges3"),
    ("greys3", "cyans3"),
    ("greys3", "magentas3"),
    ("greys3", "violets3"),
    ("greys3", "neongreens3"),
]


# ── Main: build everything and print ─────────────────────────────────────


def _print_palette(name, hexes):
    print(f'    "{name}": [')
    for h in hexes:
        print(f'        "{h}",')
    print("    ],")


def main():
    print("# ─── Sequential single-hue (Oklab) ───────────────────────────────")
    for name, (hue, L_lo, L_hi) in SEQ_SINGLE_OKLAB.items():
        _print_palette(name, build_single_hue(hue, L_lo, L_hi))

    print("\n# ─── Sequential multi-hue (Oklab) ────────────────────────────────")
    for name, kf in SEQ_MULTI_OKLAB.items():
        _print_palette(
            name,
            build_multihue(
                kf,
                frac=SEQ_MULTI_FRAC.get(name, SEQ_FRAC),
                max_chroma=SEQ_MULTI_MAX_CHROMA.get(name),
            ),
        )

    print("\n# ─── Diverging (Oklab, FRAC=0.85) ────────────────────────────────")
    for name, (arm2, arm1) in DIVERG_OKLAB.items():
        _print_palette(name, build_diverging(arm2, arm1, frac=DIVERG_FRAC))

    print("\n# ─── Diverging maximally saturated (Oklab, FRAC=1.0) ─────────────")
    for name, (arm2, arm1) in DIVERG_OKLAB.items():
        _print_palette(f"{name}_sat", build_diverging(arm2, arm1, frac=DIVERG_SAT_FRAC))

    print("\n# ─── Diverging — '2'-suffix single-hue pairs ──────────────────────────────")
    for arm1, arm2 in DIVERG_SEQ2_PAIRS:
        name = arm1.removesuffix("2") + arm2  # e.g. "reds2","blues2" → "redsblues2"
        _print_palette(name, build_diverging(_pal[arm1][7], _pal[arm2][7]))

    print("\n# ─── Sequential single-hue '3' (pastel, Oklab) ───────────────────────")
    for name in SEQ_SINGLE_NAMES:
        base = _pal[name]
        _, a, b = hex_to_oklab(base[5])
        hue_deg = math.degrees(math.atan2(b, a)) % 360
        frac = 0.0 if name == "greys" else PASTEL_FRAC
        _print_palette(f"{name}3", build_single_hue(hue_deg, PASTEL_L_LO, PASTEL_L_HI, frac=frac))

    print("\n# ─── Diverging — '3'-suffix single-hue pairs (pastel, FRAC=0.35) ────────────")
    for arm1, arm2 in DIVERG_SEQ3_PAIRS:
        name = arm1.removesuffix("3") + arm2  # e.g. "reds3","blues3" → "redsblues3"
        _print_palette(name, build_diverging(_pal[arm1][11], _pal[arm2][11], frac=PASTEL_FRAC))

    print("\n# ─── Desaturation ladder example (bluestgrotto → bluergrotto → bluegrotto)")
    base = build_multihue(SEQ_MULTI_OKLAB["bluestgrotto"])
    _print_palette("bluestgrotto", base)
    _print_palette("bluergrotto", desaturate(base, 0.875))
    _print_palette("bluegrotto", desaturate(base, 0.75))


if __name__ == "__main__":
    main()
