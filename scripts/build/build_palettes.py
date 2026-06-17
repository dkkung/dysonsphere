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
                 bluestgrotto/bluergrotto/bluegrotto ladder.

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
    python scripts/build_palettes.py

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


# ── Build parameters ─────────────────────────────────────────────────────

N_OUT_SEQ = 12  # stops per sequential palette
N_OUT_DIVERG = 13  # stops per diverging palette (odd → white pivot)
N_DENSE = 4000  # dense path resolution before arc-length resampling

# Default chroma fractions (of gamut max at each L)
SEQ_FRAC = 0.65  # sequential single-hue and multi-hue
DIVERG_FRAC = 0.85  # diverging base palettes
DIVERG_SAT_FRAC = 1.0  # *_sat diverging variants


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
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l_, m_, s_ = l ** (1 / 3), m ** (1 / 3), s ** (1 / 3)
    return (
        0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
        1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
        0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_,
    )


def oklab_to_rgb(L, a, b):
    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b
    l, m, s = l_**3, m_**3, s_**3
    return (
        4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
        -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
        -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s,
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
        arc.append(
            arc[-1]
            + math.sqrt(
                (Ld[i] - Ld[i - 1]) ** 2 + (ad[i] - ad[i - 1]) ** 2 + (bd[i] - bd[i - 1]) ** 2
            )
        )
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


def build_multihue(keyframes, *, space="oklab", frac=SEQ_FRAC, n=N_OUT_SEQ):
    """
    keyframes: list of (L, hue_deg) tuples ordered along the palette.
    Linear interpolation between consecutive keyframes in both L and hue
    (after hue unwrapping); chroma at each interpolated point as in
    recipe 1.  Equal arc-length resample to n stops.
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
        h_arm = math.atan2(b_d, a_d)
        _, a_o, b_o = hex_to(other_dark)
        h_other = math.atan2(b_o, a_o)
        Ld, ad, bd = [], [], []
        for i in range(N_DENSE):
            s = i / (N_DENSE - 1)
            L = L_dark + (L_center - L_dark) * s
            t = 1 - s  # 1 at dark end → 0 at centre
            C = frac * min(max_c(L, h_arm), max_c(L, h_other)) * t
            Ld.append(L)
            ad.append(C * math.cos(h_arm))
            bd.append(C * math.sin(h_arm))
        # Sample HALF stops at equal arc length, ending just shy of centre.
        # (Pivot is inserted separately so it equals center_hex exactly.)
        arc = [0.0]
        for i in range(1, N_DENSE):
            arc.append(
                arc[-1]
                + math.sqrt(
                    (Ld[i] - Ld[i - 1]) ** 2 + (ad[i] - ad[i - 1]) ** 2 + (bd[i] - bd[i - 1]) ** 2
                )
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


# ── Main: build everything and print ─────────────────────────────────────


def _print_palette(name, hexes):
    print(f'    "{name}": [')
    for h in hexes:
        print(f'        "{h}",')
    print(f"    ],")


def main():
    print("# ─── Sequential single-hue (Oklab) ───────────────────────────────")
    for name, (hue, L_lo, L_hi) in SEQ_SINGLE_OKLAB.items():
        _print_palette(name, build_single_hue(hue, L_lo, L_hi))

    print("\n# ─── Sequential multi-hue (Oklab) ────────────────────────────────")
    for name, kf in SEQ_MULTI_OKLAB.items():
        _print_palette(name, build_multihue(kf))

    print("\n# ─── Diverging (Oklab, FRAC=0.85) ────────────────────────────────")
    for name, (arm2, arm1) in DIVERG_OKLAB.items():
        _print_palette(name, build_diverging(arm2, arm1, frac=DIVERG_FRAC))

    print("\n# ─── Diverging maximally saturated (Oklab, FRAC=1.0) ─────────────")
    for name, (arm2, arm1) in DIVERG_OKLAB.items():
        _print_palette(f"{name}_sat", build_diverging(arm2, arm1, frac=DIVERG_SAT_FRAC))

    print("\n# ─── Desaturation ladder example (bluestgrotto → bluergrotto → bluegrotto)")
    base = build_multihue(SEQ_MULTI_OKLAB["bluestgrotto"])
    _print_palette("bluestgrotto", base)
    _print_palette("bluergrotto", desaturate(base, 0.875))
    _print_palette("bluegrotto", desaturate(base, 0.75))


if __name__ == "__main__":
    main()
