"""
Generates docs/shade_example.png — the README preview for add_shade().

Three panels:
  left   — band mode with default arguments (boxplot)
  middle — positions mode, axis='y', top-quarter shade (scatter)
  right  — positions mode, axis='both', top-right corner (scatter)

Usage (from project root):
    uv run python scripts/build/build_shade_example.py
"""

from pathlib import Path
from typing import Any

import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

ROOT = Path(__file__).resolve().parents[2]


CATEGORIES = ["A", "B", "C", "D"]

rng = np.random.default_rng(42)

box_df = pl.DataFrame(
    {
        "group": [cat for cat in CATEGORIES for _ in range(60)],
        "value": np.concatenate(
            [
                rng.normal(1.0, 0.3, 60),
                rng.normal(1.8, 0.35, 60),
                rng.normal(1.3, 0.3, 60),
                rng.normal(2.1, 0.4, 60),
            ]
        ),
    }
)

_n = 100
_x = rng.uniform(0, 10, _n)
_y = (_x * 0.9 + rng.normal(0, 1.0, _n)).clip(0, 10)
scatter_df = pl.DataFrame({"x": _x.tolist(), "y": _y.tolist()})

ds.theme(palette="blues2", chartWidth=100, legend=False)

title_params: dict[str, Any] = dict(orient="top", anchor="start", offset=4)
fontSize = alt.theme.options.get("fontSize", 7)

# ── Left: boxplot, band mode with default add_shade() ─────────────────────
shade_left = ds.add_shade(CATEGORIES, "group")
boxplot = (
    alt.Chart(box_df)
    .mark_boxplot()
    .encode(
        x=alt.X("group:N", sort=CATEGORIES, title=None),
        y=alt.Y("value:Q", title=None),
        color=alt.Color(
            "group:N",
            sort=CATEGORIES,
            scale=alt.Scale(range=ds.palette("blues2", n=4)),
            legend=None,
        ),
    )
)
left = (shade_left + boxplot).properties(
    title=alt.TitleParams(
        ["Default parameters"],
        fontSize=fontSize,
        **title_params,
    )
)

# ── Scatter base (shared by middle and right) ──────────────────────────────
scatter = (
    alt.Chart(scatter_df)
    .mark_point()
    .encode(
        x=alt.X(
            "x:Q",
            title=None,
            scale=alt.Scale(domain=[0, 10]),
            axis=alt.Axis(tickCount=5),
        ),
        y=alt.Y(
            "y:Q",
            title=None,
            scale=alt.Scale(domain=[0, 10]),
            axis=alt.Axis(tickCount=5),
        ),
        color=alt.Color(
            "y:Q",
            scale=alt.Scale(range=ds.palette("blues2"), domain=[0, 10]),
            legend=None,
        ),
    )
)

# ── Middle: axis='y', top-quarter shade, no stroke ─────────────────────────
shade_mid = ds.add_shade(
    positions=[(7.5, 10.0)],
    axis="y",
    palette=[ds.palette("blues")[0]],
)
mid = (shade_mid + scatter).properties(
    title=alt.TitleParams(
        ['axis="y"', "positions=[(7.5, 10.0)]"],
        fontSize=fontSize,
        **title_params,
    )
)

# ── Right: axis='both', top-right corner ──────────────────────────────────
shade_right = ds.add_shade(
    positions=[((7.5, 10.0), (7.5, 10.0))],
    axis="both",
    palette=[ds.palette("blues")[0]],
    stroke=True,
    strokeDash=True,
)
right = (shade_right + scatter).properties(
    title=alt.TitleParams(
        [
            'axis="both"',
            "positions=[((7.5, 10.0), (7.5, 10.0))]",
            "stroke=True, strokeDash=True",
        ],
        fontSize=fontSize,
        **title_params,
    )
)

chart = alt.hconcat(left, mid, right)

out_png = ROOT / "docs" / "shade_example.png"
ds.save(chart, str(out_png.with_suffix("")), format="png", background="light", transparent=False)
print(f"saved {out_png}")
