"""
Interactive HTML gallery of all custom palettes.

Usage (from project root):
    python scripts/build/build_gallery.py

Output: assets/gallery.html
"""

import math
from pathlib import Path

import altair as alt
import numpy as np
import polars as pl

from dysonsphere.layers import mark_violin
from dysonsphere.palettes import colors

ROOT = Path(__file__).resolve().parents[2]


W = 100  # base chart width / height (px)

# ── Oklab helpers (inlined — no dependency on examples/) ───────────────────


def _lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _hex_to_oklab(hx):
    h = hx.lstrip("#")
    r, g, b = [_lin(int(h[i : i + 2], 16) / 255) for i in (0, 2, 4)]
    lv = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l_, m_, s_ = lv ** (1 / 3), m ** (1 / 3), s ** (1 / 3)
    return (
        0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
        1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
        0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_,
    )


def _de_steps(key):
    hexes = colors[key]
    labs = [_hex_to_oklab(h) for h in hexes]
    return [
        math.sqrt(sum((a - b) ** 2 for a, b in zip(labs[i], labs[i + 1])))
        for i in range(len(labs) - 1)
    ]


def _mad_pct(steps):
    mean = sum(steps) / len(steps)
    mad = sum(abs(s - mean) for s in steps) / len(steps)
    return round(mad / mean * 100, 1)


# ── Palette groups ──────────────────────────────────────────────────────────

GROUPS = [
    (
        "Sequential — Single-hue",
        [
            "blues",
            "greens",
            "purples",
            "lavenders",
            "violets",
            "greys",
            "reds",
            "rose",
            "oranges",
            "browns",
            "yellows",
            "cyans",
            "magentas",
            "neongreens",
        ],
    ),
    (
        "Sequential — Single-hue 2",
        [
            "blues2",
            "greens2",
            "purples2",
            "lavenders2",
            "violets2",
            "greys2",
            "reds2",
            "roses2",
            "oranges2",
            "browns2",
            "yellows2",
            "cyans2",
            "magentas2",
            "neongreens2",
        ],
    ),
    (
        "Sequential — Multi-hue",
        [
            "ember",
            "dusk",
            "shoal",
            "moss",
            "GnBu",
            "YlGnBu",
            "candy",
            "lagoon",
            "bluestlagoon",
            "bluerlagoon",
            "bluelagoon",
        ],
    ),
    (
        "Diverging",
        [
            "RdBu",
            "RdYlBu",
            "PuGn",
            "MgGn",
            "PkTe",
            "GdBu",
            "BrTe",
            "BrGn",
        ],
    ),
    (
        "Diverging — Single-hue 1",
        [
            "greensblues",
            "redsblues",
            "redsgreens",
            "redscyans",
            "redslavenders",
            "redsviolets",
            "redsneongreens",
            "rosesblues",
            "rosescyans",
            "rosesgreens",
            "rosesneongreens",
            "orangesblues",
            "orangescyans",
            "orangespurples",
            "orangeslavenders",
            "orangesviolets",
            "orangesneongreens",
            "yellowsblues",
            "yellowspurples",
            "yellowslavenders",
            "brownsblues",
            "brownsgreens",
            "brownscyans",
            "brownsneongreens",
            "magentasneongreens",
            "magentasgreens",
            "magentasblues",
            "magentascyans",
            "violetsoranges",
            "violetsyellows",
            "purplesgreens",
            "purplesblues",
            "purplesneongreens",
            "lavendersgreens",
            "lavendersblues",
            "lavendersneongreens",
            "cyanspurples",
            "cyanslavenders",
            "cyansviolets",
            "greysblues",
            "greysreds",
            "greysgreens",
            "greyscyans",
            "greysyellows",
            "greysoranges",
            "greysmagentas",
            "greysviolets",
            "greysneongreens",
            "greyspurples",
            "greyslavender",
            "greysrose",
        ],
    ),
    (
        "Diverging — Single-hue 2",
        [
            "greensblues2",
            "redsblues2",
            "redsgreens2",
            "redscyans2",
            "redslavenders2",
            "redsviolets2",
            "redsneongreens2",
            "orangesblues2",
            "orangescyans2",
            "orangespurples2",
            "orangeslavenders2",
            "orangesviolets2",
            "orangesneongreens2",
            "yellowsblues2",
            "yellowspurples2",
            "yellowslavenders2",
            "brownsblues2",
            "brownsgreens2",
            "brownscyans2",
            "brownsneongreens2",
            "magentasneongreens2",
            "magentasgreens2",
            "magentasblues2",
            "magentascyans2",
            "violetsoranges2",
            "violetsyellows2",
            "purplesgreens2",
            "purplesblues2",
            "purplesneongreens2",
            "lavendersgreens2",
            "lavendersblues2",
            "lavendersneongreens2",
            "cyanspurples2",
            "cyanslavenders2",
            "cyansviolets2",
            "greysblues2",
            "greysreds2",
            "greysgreens2",
            "greyscyans2",
            "greysyellows2",
            "greysoranges2",
            "greysmagentas2",
            "greysviolets2",
            "greysneongreens2",
            "greyspurples2",
            "greyslavenders2",
        ],
    ),
    (
        "Discrete",
        [
            "nucleotides",
            "proteins",
        ],
    ),
]
# Keys that are already final variants (no base+suffix convention)
LITERAL_KEYS = []

VARIANTS = [("", "")]

# ── Synthetic data ──────────────────────────────────────────────────────────

# Scatter: exact data from scatter.py
_scatter_rng = np.random.default_rng(42)
_sx = np.linspace(0, 5, 200)
_sy = np.exp(_sx) + _scatter_rng.normal(0, 2, 200)
_smask = _sy >= 0
_scatter_df = pl.DataFrame({"x": _sx[_smask].tolist(), "y": _sy[_smask].tolist()})

# Sequential heatmap: radial Gaussian peak at center, values in [0, 1]
_seq_heat_rows = []
for _xi in range(30):
    for _yi in range(30):
        _x = _xi / 29.0 * 10
        _y = _yi / 29.0 * 10
        _z = np.exp(-0.5 * ((_x - 5.0) ** 2 / 4.0 + (_y - 5.0) ** 2 / 4.0))
        _seq_heat_rows.append({"x": float(_x), "y": float(_y), "z": float(_z)})
_seq_heat_df = pl.DataFrame(_seq_heat_rows)

# Diverging heatmap: two opposing Gaussian bumps, values in [-1, 1]
_heat_rows = []
for _xi in range(30):
    for _yi in range(30):
        _x = _xi / 29.0 * 10
        _y = _yi / 29.0 * 10
        _pos = np.exp(-0.5 * ((_x - 2.5) ** 2 / 2.25 + (_y - 7.5) ** 2 / 2.25))
        _neg = np.exp(-0.5 * ((_x - 7.5) ** 2 / 2.25 + (_y - 2.5) ** 2 / 2.25))
        _heat_rows.append({"x": float(_x), "y": float(_y), "z": float(_pos - _neg)})
_heat_df = pl.DataFrame(_heat_rows)

# Area chart: exact data from area_chart.py
_AREA_GROUPS = ["Group A", "Group B", "Group C", "Group D"]
_AREA_BASES = [0.4, 0.3, 0.2, 0.1]
_area_rng = np.random.default_rng(42)
_area_rows = []
for _t in np.linspace(0, 24, 100):
    for _grp, _base in zip(_AREA_GROUPS, _AREA_BASES):
        _area_rows.append(
            {"time": float(_t), "group": _grp, "value": max(0.0, _base + _area_rng.normal(0, 0.02))}
        )
_area_df = pl.DataFrame(_area_rows)

# Boxplot: 5 groups (dropped 6th), agnostic labels
_BOX_CATS = ["Group A", "Group B", "Group C", "Group D", "Group E"]
_box_rng = np.random.default_rng(42)
_box_raw = pl.DataFrame(
    {
        "group": (
            ["Group A"] * 200
            + ["Group B"] * 200
            + ["Group C"] * 200
            + ["Group D"] * 200
            + ["Group E"] * 200
        ),
        "value": np.concatenate(
            [
                _box_rng.normal(10, 2, 200),
                _box_rng.normal(14, 2, 200),
                _box_rng.normal(11, 2, 200),
                _box_rng.normal(13, 2, 200),
                _box_rng.normal(9, 2, 200),
            ]
        ),
    }
)
_box_df = _box_raw

# Line chart: 4 groups with slopes over 50 timepoints
_LINE_GROUPS = ["Group A", "Group B", "Group C", "Group D"]
_line_rng = np.random.default_rng(42)
_line_slopes = {"Group A": 0.0, "Group B": 0.25, "Group C": 0.15, "Group D": -0.1}
_line_rows = []
for _grp in _LINE_GROUPS:
    for _t in np.linspace(0, 24, 50):
        _line_rows.append(
            {
                "group": _grp,
                "time": float(_t),
                "value": float(10 + _line_slopes[_grp] * _t + _line_rng.normal(0, 0.3)),
            }
        )
_line_df = pl.DataFrame(_line_rows)

# Stacked bar: 5 groups, 2 types
_SBAR_GROUPS = ["Group A", "Group B", "Group C", "Group D", "Group E"]
_SBAR_TYPES = ["Type 1", "Type 2"]
_sbar_rng = np.random.default_rng(42)
_sbar_df = pl.DataFrame(
    {
        "group": ["Group A", "Group B", "Group C", "Group D", "Group E"] * 2,
        "type": ["Type 1"] * 5 + ["Type 2"] * 5,
        "value": _sbar_rng.integers(20, 80, 10).tolist(),
    }
)

# Violin: 5 groups (dropped 6th), 200 pts each
_VIOLIN_CATS = ["Group A", "Group B", "Group C", "Group D", "Group E"]
_violin_rng = np.random.default_rng(42)
_violin_df = pl.DataFrame(
    {
        "group": (
            ["Group A"] * 200
            + ["Group B"] * 200
            + ["Group C"] * 200
            + ["Group D"] * 200
            + ["Group E"] * 200
        ),
        "value": np.concatenate(
            [
                _violin_rng.normal(10, 2, 200),
                _violin_rng.normal(14, 2, 200),
                _violin_rng.normal(11, 2, 200),
                _violin_rng.normal(13, 2, 200),
                _violin_rng.normal(9, 2, 200),
            ]
        ).tolist(),
    }
)

# Histogram: 3 groups, 150 pts each
_HIST_GROUPS = ["Group A", "Group B", "Group C"]
_hist_rng = np.random.default_rng(42)
_hist_df = pl.DataFrame(
    {
        "group": ["Group A"] * 150 + ["Group B"] * 150 + ["Group C"] * 150,
        "value": np.concatenate(
            [
                _hist_rng.normal(10, 2, 150),
                _hist_rng.normal(13, 1.5, 150),
                _hist_rng.normal(7, 3, 150),
            ]
        ).tolist(),
    }
)

# Pre-compute viridis reference steps
_VIR_STEPS = _de_steps("mpl_viridis")
_VIR_MAD = _mad_pct(_VIR_STEPS)

# ── Layout constants ────────────────────────────────────────────────────────

_N_ROW_CHARTS = 11  # colorspace, de_sparkline, area, scatter, line, boxplot, violin, stacked_bar, histogram, seq_heatmap, heatmap  # noqa: E501
_ROW_SPACING = 6
_SWATCH_W = _N_ROW_CHARTS * W + (_N_ROW_CHARTS - 1) * _ROW_SPACING  # 1160px

# ── Chart builders ──────────────────────────────────────────────────────────


def _swatch(key, label):
    p = colors[key]
    n = len(p)
    df = pl.DataFrame({"x1": list(range(n)), "x2": list(range(1, n + 1)), "c": p})
    return (
        alt.Chart(df, title=label)
        .mark_rect(strokeWidth=0)
        .encode(
            x=alt.X("x1:Q", axis=None, scale=alt.Scale(domain=[0, n], nice=False)),
            x2=alt.X2("x2:Q"),
            color=alt.Color("c:N", scale=None, legend=None),
            tooltip=alt.Tooltip("c:N", title="hex"),
        )
        .properties(height=_SWATCH_H)
    )


def _scatter(key):
    p = colors[key]
    return (
        alt.Chart(_scatter_df)
        .mark_point()
        .encode(
            x=alt.X("x:Q", title=None),
            y=alt.Y("y:Q", title=None),
            color=alt.Color("y:Q", title=None, scale=alt.Scale(range=p)),
        )
    )


def _boxplot(key):
    p = colors[key]
    n = len(p)
    box_colors = [p[round(i * (n - 1) / (len(_BOX_CATS) - 1))] for i in range(len(_BOX_CATS))]
    x_enc = alt.X(
        "group:N",
        sort=_BOX_CATS,
        title=None,
        axis=alt.Axis(labelAngle=-45, labelAlign="right"),
    )
    y_enc = alt.Y("value:Q", title=None)
    color_enc = alt.Color(
        "group:N",
        sort=_BOX_CATS,
        title=None,
        scale=alt.Scale(domain=_BOX_CATS, range=box_colors),
    )
    return alt.Chart(_box_df).mark_boxplot().encode(x=x_enc, y=y_enc, color=color_enc)


def _seq_heatmap(key):
    p = colors[key]
    return (
        alt.Chart(_seq_heat_df)
        .mark_rect()
        .encode(
            x=alt.X("x:Q", bin=alt.Bin(maxbins=10), title=None, axis=alt.Axis(format=".0f")),
            y=alt.Y("y:Q", bin=alt.Bin(maxbins=10), title=None, axis=alt.Axis(format=".0f")),
            color=alt.Color("mean(z):Q", title=None, scale=alt.Scale(range=p)),
            tooltip=alt.Tooltip("mean(z):Q", title="value", format=".2f"),
        )
    )


def _heatmap(key):
    p = colors[key]
    return (
        alt.Chart(_heat_df)
        .mark_rect()
        .encode(
            x=alt.X("x:Q", bin=alt.Bin(maxbins=10), title=None, axis=alt.Axis(format=".0f")),
            y=alt.Y("y:Q", bin=alt.Bin(maxbins=10), title=None, axis=alt.Axis(format=".0f")),
            color=alt.Color(
                "mean(z):Q",
                title=None,
                scale=alt.Scale(range=p, domainMid=0),
            ),
            tooltip=alt.Tooltip("mean(z):Q", title="value", format=".2f"),
        )
    )


def _area(key):
    p = colors[key]
    n = len(p)
    palette = [p[round(i * (n - 1) / (len(_AREA_GROUPS) - 1))] for i in range(len(_AREA_GROUPS))]
    return (
        alt.Chart(_area_df)
        .mark_area()
        .encode(
            x=alt.X("time:Q", title=None),
            y=alt.Y("value:Q", title=None, stack="normalize", scale=alt.Scale(domain=[0, 1])),
            color=alt.Color(
                "group:N", sort=_AREA_GROUPS, title=None, scale=alt.Scale(range=palette)
            ),
            order=alt.Order("group:N", sort="descending"),
        )
    )


def _line(key):
    p = colors[key]
    n = len(p)
    palette = [p[round(i * (n - 1) / (len(_LINE_GROUPS) - 1))] for i in range(len(_LINE_GROUPS))]
    return (
        alt.Chart(_line_df)
        .mark_line()
        .encode(
            x=alt.X("time:Q", title=None),
            y=alt.Y("value:Q", title=None),
            color=alt.Color(
                "group:N", sort=_LINE_GROUPS, title=None, scale=alt.Scale(range=palette)
            ),
        )
    )


def _violin(key):
    p = colors[key]
    n = len(p)
    palette = [p[round(i * (n - 1) / (len(_VIOLIN_CATS) - 1))] for i in range(len(_VIOLIN_CATS))]
    return mark_violin(
        _violin_df, "group", "value", _VIOLIN_CATS, palette=palette, legend=True, xLabelAngle=-45
    )


def _stacked_bar(key):
    p = colors[key]
    n = len(p)
    palette = [p[0], p[n - 1]]
    return (
        alt.Chart(_sbar_df)
        .mark_bar()
        .encode(
            x=alt.X(
                "group:N",
                sort=_SBAR_GROUPS,
                title=None,
                axis=alt.Axis(labelAngle=-45, labelAlign="right"),
            ),
            y=alt.Y("value:Q", title=None, stack="normalize", scale=alt.Scale(domain=[0, 1])),
            color=alt.Color("type:N", sort=_SBAR_TYPES, title=None, scale=alt.Scale(range=palette)),
        )
    )


def _histogram(key):
    p = colors[key]
    n = len(p)
    palette = [p[round(i * (n - 1) / (len(_HIST_GROUPS) - 1))] for i in range(len(_HIST_GROUPS))]
    return (
        alt.Chart(_hist_df)
        .mark_bar(binSpacing=0)
        .encode(
            x=alt.X("value:Q", title=None, bin=alt.Bin(maxbins=10), axis=alt.Axis(format=".0f")),
            y=alt.Y("count()", title=None),
            color=alt.Color(
                "group:N", sort=_HIST_GROUPS, title=None, scale=alt.Scale(range=palette)
            ),
        )
    )


def _de_sparkline(key):
    steps = _de_steps(key)
    mad = _mad_pct(steps)
    mid_hex = colors[key][len(colors[key]) // 2]

    pal_rows = [{"step": i, "dE": round(s, 5)} for i, s in enumerate(steps)]
    vir_rows = [{"step": i, "dE": round(s, 5)} for i, s in enumerate(_VIR_STEPS)]
    pal_df = pl.DataFrame(pal_rows)
    vir_df = pl.DataFrame(vir_rows)

    all_de = [r["dE"] for r in pal_rows + vir_rows]
    lo, hi = min(all_de) * 0.82, max(all_de) * 1.18

    max_step = max(len(steps) - 1, len(_VIR_STEPS) - 1)
    x_enc = alt.X(
        "step:Q",
        title="Step",
        scale=alt.Scale(domain=[-0.5, max_step + 0.5]),
        axis=alt.Axis(tickMinStep=1),
    )
    y_enc = alt.Y(
        "dE:Q", title="Oklab ΔE", scale=alt.Scale(domain=[lo, hi]), axis=alt.Axis(format=".3f")
    )

    vir_line = (
        alt.Chart(vir_df)
        .mark_line(point=True, color="#AAAAAA")
        .encode(
            x=x_enc,
            y=y_enc,
            tooltip=[alt.Tooltip("step:Q"), alt.Tooltip("dE:Q", format=".4f", title="viridis ΔE")],
        )
    )
    pal_line = (
        alt.Chart(pal_df)
        .mark_line(point=True, color=mid_hex)
        .encode(
            x=x_enc,
            y=y_enc,
            tooltip=[alt.Tooltip("step:Q"), alt.Tooltip("dE:Q", format=".4f", title="ΔE")],
        )
    )
    mad_label = (
        alt.Chart(pl.DataFrame({"text": [f"MAD {mad}%"]}))
        .mark_text(align="left", baseline="top", dx=4, dy=4)
        .encode(x=alt.value(0), y=alt.value(0), text="text:N")
    )
    return vir_line + pal_line + mad_label


def _colorspace(key):
    """Palette trajectory in Oklab a/b space, each stop colored by its hex."""
    hexes = colors[key]
    labs = [_hex_to_oklab(h) for h in hexes]
    rows = [
        {
            "hex": h,
            "a": round(a, 4),
            "b": round(b, 4),
            "L": round(L, 3),
            "i": i,
            "label": f"#{i} {h}",
        }
        for i, (h, (L, a, b)) in enumerate(zip(hexes, labs))
    ]
    df = pl.DataFrame(rows)
    domain = [r["hex"] for r in rows]

    line = alt.Chart(df).mark_line(color="black").encode(x="a:Q", y="b:Q", order="i:O")
    pts = (
        alt.Chart(df)
        .mark_circle(size=20)
        .encode(
            x=alt.X(
                "a:Q",
                scale=alt.Scale(domain=[-0.3, 0.3]),
                axis=alt.Axis(title="Oklab a", format=".2f"),
            ),
            y=alt.Y(
                "b:Q",
                scale=alt.Scale(domain=[-0.3, 0.3]),
                axis=alt.Axis(title="Oklab b", format=".2f"),
            ),
            color=alt.Color("hex:N", scale=alt.Scale(domain=domain, range=domain), legend=None),
            tooltip=[
                alt.Tooltip("label:N", title="stop"),
                alt.Tooltip("L:Q", format=".2f"),
                alt.Tooltip("a:Q", format=".3f"),
                alt.Tooltip("b:Q", format=".3f"),
            ],
        )
    )
    return (line + pts).resolve_scale(color="independent")


# ── Row: all charts for one palette key (landscape layout) ─────────────────


_SWATCH_H = 14


def _row(key, label):
    row = alt.hconcat(
        _colorspace(key),
        _de_sparkline(key),
        _area(key),
        _stacked_bar(key),
        _histogram(key),
        _seq_heatmap(key),
        _heatmap(key),
        _boxplot(key),
        _violin(key),
        _scatter(key),
        _line(key),
        spacing=6,
    ).resolve_scale(color="independent", opacity="independent")
    return alt.vconcat(
        _swatch(key, label),
        row,
        spacing=2,
    ).resolve_scale(color="independent", opacity="independent")


# ── Compose ─────────────────────────────────────────────────────────────────


def _build_gallery():
    rows = []

    for group_title, base_keys in GROUPS:
        # Group heading row
        heading = (
            alt.Chart(pl.DataFrame({"x": [0]}))
            .mark_text(
                text=group_title,
                align="left",
                baseline="top",
                fontSize=13,
                fontWeight="bold",
                color="#333333",
                dx=2,
            )
            .encode()
            .properties(width=W * 6 + 6 * 5, height=18)
        )
        rows.append(heading)

        for suffix, _vlabel in VARIANTS:
            for bk in base_keys:
                key = bk + suffix
                if key not in colors:
                    continue
                rows.append(_row(key, bk))

    return alt.vconcat(*rows, spacing=12).resolve_scale(color="independent", opacity="independent")


# ── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import dysonsphere as _ds

    _ds.theme(chartWidth=W, chartHeight=W)

    gallery = _build_gallery()

    out = ROOT / "docs" / "index.html"
    gallery.save(str(out))
    print(f"saved {out}")
