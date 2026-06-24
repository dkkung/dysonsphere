import math

import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds
from dysonsphere.palettes import colors

W = 65  # chart width / height

# ── Oklab helpers (for ΔE overlay) ────────────────────────────────────────


def _lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hex_to_oklab(hx):
    h = hx.lstrip("#")
    r, g, b = [_lin(int(h[i : i + 2], 16) / 255) for i in (0, 2, 4)]
    lv = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l_, m_, s_ = lv ** (1 / 3), m ** (1 / 3), s ** (1 / 3)
    L = 0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_
    a = 1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_
    b_ = 0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_
    return L, a, b_


def oklab_de(h1, h2):
    lab1, lab2 = hex_to_oklab(h1), hex_to_oklab(h2)
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(lab1, lab2)))


# ── Scatter data ───────────────────────────────────────────────────────────

rng = np.random.default_rng(42)
x = np.linspace(0, 5, 200)
y = np.exp(x) + rng.normal(0, 2, 200)
mask = y >= 0
x, y = x[mask], y[mask]
scatter_df = pl.DataFrame({"x": x, "y": y})

# ── Palette groups ─────────────────────────────────────────────────────────

narrow = [("ember", "ember"), ("dusk", "dusk"), ("rose", "rose"), ("sienna", "sienna")]
broad = [("moss", "moss"), ("cobalt", "cobalt"), ("lavender", "lavender")]
mono1 = [("blues", "blues"), ("greens", "greens"), ("purples", "purples")]
mono2 = [("greys", "greys"), ("reds", "reds"), ("oranges", "oranges")]
multi = [("GnBu", "GnBu"), ("YlGnBu", "YlGnBu"), ("RdPu", "RdPu")]
diverg = [("RdBu", "RdBu"), ("PuGn", "PuGn"), ("BrTe", "BrTe")]
diverg2 = [("GdBu", "GdBu"), ("MgGn", "MgGn"), ("YlPu", "YlPu")]


def variant(group, suffix, label_suffix):
    return [(k + suffix, lbl + label_suffix) for k, lbl in group]


# ── Chart builders ─────────────────────────────────────────────────────────


def make_swatch(key):
    p = colors[key]
    df = pl.DataFrame({"i": list(range(len(p))), "c": p})
    return (
        alt.Chart(df)
        .mark_rect(strokeWidth=0)
        .encode(
            x=alt.X("i:O", axis=None, scale=alt.Scale(paddingInner=0, paddingOuter=0)),
            color=alt.Color("c:N", scale=alt.Scale(domain=p, range=p), legend=None),
        )
        .properties(width=W, height=10)
    )


def make_scatter(key):
    p = colors[key]
    return (
        alt.Chart(scatter_df)
        .mark_point()
        .encode(
            x=alt.X("x:Q", title="x"),
            y=alt.Y("y:Q", axis=None),
            color=alt.Color("y:Q", title=None, scale=alt.Scale(range=p)),
        )
        .properties(width=W, height=W)
    )


def make_de_overlay(key_sat2, key_oklab):
    """Oklab ΔE steps for sat2 (grey) and oklab (red) on shared zoomed axis."""
    rows = []
    for label, key in [("sat2", key_sat2), ("oklab", key_oklab)]:
        hexes = colors[key]
        steps = [oklab_de(hexes[i], hexes[i + 1]) for i in range(len(hexes) - 1)]
        for i, s in enumerate(steps):
            rows.append({"series": label, "step": i, "dE": round(s, 5)})
    df = pl.DataFrame(rows)
    vals = [r["dE"] for r in rows]
    lo, hi = min(vals) * 0.85, max(vals) * 1.15
    return (
        alt.Chart(df, title="ΔE (Oklab)")
        .mark_line(point=True, strokeWidth=1)
        .encode(
            x=alt.X("step:Q", title=None, axis=alt.Axis(tickMinStep=1)),
            y=alt.Y("dE:Q", title="ΔE", scale=alt.Scale(domain=[lo, hi])),
            color=alt.Color(
                "series:N",
                scale=alt.Scale(domain=["sat2", "oklab"], range=["#999999", "#E45756"]),
                legend=None,
            ),
        )
        .properties(width=W, height=45)
    )


def make_col(key, label):
    cielab_key = key + "_cielab"
    oklab_key = key + "_oklab"
    return alt.vconcat(
        make_swatch(cielab_key).properties(title=label + " cielab"),
        make_scatter(cielab_key),
        make_swatch(oklab_key).properties(title=label + " oklab"),
        make_scatter(oklab_key),
        make_de_overlay(cielab_key, oklab_key),
        spacing=4,
    ).resolve_scale(color="independent")


def make_row(group, title=""):
    cols = [make_col(k, lbl) for k, lbl in group]
    return alt.hconcat(*cols, spacing=10, title=title).resolve_scale(color="independent")


# ── Compose ────────────────────────────────────────────────────────────────

chart = alt.vconcat(
    make_row(narrow, "Narrow range"),
    make_row(broad, "Broad range"),
    make_row(mono1, "Single-hue analogs"),
    make_row(mono2),
    make_row(multi, "Multi-hue analogs"),
    make_row(diverg, "Diverging"),
    make_row(diverg2, "Diverging II"),
    spacing=8,
).resolve_scale(color="independent")

ds.theme(chartWidth=W, chartHeight=W)
ds.save(chart, "palette_test")
print("saved palette_test")
