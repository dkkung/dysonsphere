"""
Generates assets/thumbnail_light.png — the README preview image.

Shows the blues2 palette across all gallery chart types (colorspace and
ΔE sparkline omitted; legends hidden; group labels shortened to A/B/C/…).
Two rows of 5 charts each.

Usage (from project root):
    python scripts/build/build_thumbnail.py
"""

from pathlib import Path

import altair as alt
import numpy as np
import polars as pl

import dysonsphere as theme
import scripts.build.build_gallery as _bg
from dysonsphere.layers import mark_violin
from dysonsphere.palettes import colors

KEY = "blues2"

# ── Patch group labels: "Group A" → "A" ─────────────────────────────────────

_bg._BOX_CATS = ["A", "B", "C", "D", "E"]
_bg._VIOLIN_CATS = ["A", "B", "C", "D", "E"]
_bg._AREA_GROUPS = ["A", "B", "C", "D"]
_bg._LINE_GROUPS = ["A", "B", "C", "D"]
_bg._SBAR_GROUPS = ["A", "B", "C", "D", "E"]
_bg._HIST_GROUPS = ["A", "B", "C"]

for _attr in ("_box_df", "_violin_df", "_area_df", "_line_df", "_sbar_df", "_hist_df"):
    df = getattr(_bg, _attr)
    if "group" in df.columns:
        setattr(_bg, _attr, df.with_columns(pl.col("group").str.replace("Group ", "")))

# re-import patched references used in thumbnail-local functions
from scripts.build.build_gallery import (  # noqa: E402
    _BOX_CATS,
    _LINE_GROUPS,
    _SBAR_GROUPS,
    _SBAR_TYPES,
    _VIOLIN_CATS,
    W,
    _area,
    _box_df,
    _heatmap,
    _histogram,
    _line_df,
    _sbar_df,
    _scatter,
    _seq_heatmap,
    _swatch,
    _violin_df,
)

# ── Volcano data ────────────────────────────────────────────────────────────

_vol_rng = np.random.default_rng(42)
_n = 500
_log2fc = _vol_rng.normal(0, 1.5, _n)
_neg_log10_p = np.abs(_log2fc) * _vol_rng.exponential(1.2, _n) + _vol_rng.exponential(0.3, _n)
_FC_THRESH = 1.0
_P_THRESH = 1.3
_vol_cat = np.where(
    (_log2fc > _FC_THRESH) & (_neg_log10_p > _P_THRESH),
    "Up",
    np.where((_log2fc < -_FC_THRESH) & (_neg_log10_p > _P_THRESH), "Down", "NS"),
)
_vol_df = pl.DataFrame({"log2fc": _log2fc, "neg_log10_p": _neg_log10_p, "category": _vol_cat})
_VOL_CATS = ["Up", "NS", "Down"]

# ── Thumbnail-specific chart overrides (no angled labels, no legends) ────────


def _boxplot_no_angle(key):
    p = colors[key]
    n = len(p)
    box_colors = [p[round(i * (n - 1) / (len(_BOX_CATS) - 1))] for i in range(len(_BOX_CATS))]
    return (
        alt.Chart(_box_df)
        .mark_boxplot()
        .encode(
            x=alt.X("group:N", sort=_BOX_CATS, title=None),
            y=alt.Y("value:Q", title=None),
            color=alt.Color(
                "group:N",
                sort=_BOX_CATS,
                title=None,
                scale=alt.Scale(domain=_BOX_CATS, range=box_colors),
            ),
        )
    )


def _stacked_bar_no_angle(key):
    p = colors[key]
    n = len(p)
    palette = [p[0], p[n - 1]]
    return (
        alt.Chart(_sbar_df)
        .mark_bar()
        .encode(
            x=alt.X("group:N", sort=_SBAR_GROUPS, title=None),
            y=alt.Y("value:Q", title=None, stack="normalize", scale=alt.Scale(domain=[0, 1])),
            color=alt.Color("type:N", sort=_SBAR_TYPES, title=None, scale=alt.Scale(range=palette)),
        )
    )


def _violin_no_legend(key):
    p = colors[key]
    n = len(p)
    palette = [p[round(i * (n - 1) / (len(_VIOLIN_CATS) - 1))] for i in range(len(_VIOLIN_CATS))]
    return mark_violin(
        _violin_df,
        "group",
        "value",
        _VIOLIN_CATS,
        palette=palette,
        legend=False,
        angledX=False,
        y_title=None,
    )


def _volcano(key):
    p = colors[key]
    palette = [p[7], colors["greys"][0], p[0]]  # Up=blues2[7], NS=grey, Down=light
    points = (
        alt.Chart(_vol_df)
        .mark_point()
        .encode(
            x=alt.X("log2fc:Q", title=None),
            y=alt.Y("neg_log10_p:Q", title=None),
            color=alt.Color(
                "category:N",
                sort=_VOL_CATS,
                title=None,
                scale=alt.Scale(domain=_VOL_CATS, range=palette),
                legend=None,
            ),
            opacity=alt.condition(
                alt.datum.category == "NS",
                alt.value(0.5),
                alt.value(1.0),
            ),
        )
    )
    h_rule = alt.Chart(alt.Data(values=[{"y": _P_THRESH}])).mark_rule().encode(y="y:Q")
    v_pos = alt.Chart(alt.Data(values=[{"x": _FC_THRESH}])).mark_rule().encode(x="x:Q")
    v_neg = alt.Chart(alt.Data(values=[{"x": -_FC_THRESH}])).mark_rule().encode(x="x:Q")
    return (points + h_rule + v_pos + v_neg).properties(width=W, height=W)


def _line_no_legend(key):
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
                "group:N",
                sort=_LINE_GROUPS,
                title=None,
                scale=alt.Scale(range=palette),
                legend=None,
            ),
        )
    )


# ── Build and save ───────────────────────────────────────────────────────────


def build_thumbnail():
    theme.options(chartWidth=W, chartHeight=W, legend=False)

    _rs = dict(color="independent", opacity="independent")
    grid = alt.concat(
        _area(KEY),
        _stacked_bar_no_angle(KEY),
        _histogram(KEY),
        _seq_heatmap(KEY),
        _heatmap(KEY),
        _boxplot_no_angle(KEY),
        _violin_no_legend(KEY),
        _volcano(KEY),
        _scatter(KEY),
        _line_no_legend(KEY),
        columns=5,
        spacing=6,
    ).resolve_scale(**_rs)

    chart = alt.vconcat(
        _swatch(KEY, KEY),
        grid,
        spacing=6,
    ).resolve_scale(**_rs)

    out = Path(__file__).parent.parent.parent / "docs" / "thumbnail_light.png"
    chart.save(str(out), ppi=1200)
    print(f"saved {out}")


if __name__ == "__main__":
    build_thumbnail()
