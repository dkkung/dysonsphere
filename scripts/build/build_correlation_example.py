"""
Generates docs/correlation_example.png — the README preview for add_correlation.

Three panels:
  left   — method="pearson" default: r + the theme-inherited OLS fit line
  middle — method="spearman", includePvalue=True: rank corr on curved data, no line
  right  — verbose=True + a styled fit line via curated params + the lineStyle passthrough

Usage (from project root):
    uv run python scripts/build/build_correlation_example.py
"""

from pathlib import Path
from typing import Any

import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

ROOT = Path(__file__).resolve().parents[2]

rng = np.random.default_rng(1)

_x = rng.uniform(0, 10, 90)
linear_df = pl.DataFrame({"x": _x, "y": 0.85 * _x + 1.5 + rng.normal(0, 1.4, 90)})

_xc = rng.uniform(0, 10, 90)
curved_df = pl.DataFrame({"x": _xc, "y": np.exp(0.32 * _xc) + rng.normal(0, 1.5, 90)})

ds.theme(chartFill="white", chartWidth=165, chartHeight=115, palette="blues2")

title_params: dict[str, Any] = dict(orient="top", anchor="start", offset=4)
fontSize = alt.theme.options.get("fontSize", 7)


def scatter(df: pl.DataFrame) -> alt.Chart:
    return (
        alt.Chart(df)
        .mark_point(size=alt.theme.options.get("markSize", 10) * 0.6)
        .encode(
            x=alt.X("x:Q", title=None),
            y=alt.Y("y:Q", title=None),
            color=alt.Color("y:Q", scale=alt.Scale(range=ds.palette("blues2")), legend=None),
        )
    )


left = (scatter(linear_df) + ds.add_correlation(linear_df, "x", "y")).properties(
    title=alt.TitleParams(['method="pearson"'], fontSize=fontSize, **title_params)
)

middle = (
    scatter(curved_df) + ds.add_correlation(curved_df, "x", "y", method="spearman", includePvalue=True)
).properties(title=alt.TitleParams(['method="spearman"', "includePvalue=True"], fontSize=fontSize, **title_params))

right = (
    scatter(linear_df)
    + ds.add_correlation(linear_df, "x", "y", verbose=True, color="#c0392b", lineStyle={"strokeDash": [4, 2]})
).properties(
    title=alt.TitleParams(
        ["verbose=True", 'color="#c0392b", lineStyle={"strokeDash": [4, 2]}'], fontSize=fontSize, **title_params
    )
)

chart = alt.hconcat(left, middle, right)

out_png = ROOT / "docs" / "correlation_example.png"
ds.save(chart, str(out_png.with_suffix("")), format="png", background="light", transparent=False)
print(f"saved {out_png}")
