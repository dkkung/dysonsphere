"""
Generates docs/multilabel_span_example.png — the README preview for add_multilabel span.

Shows a boxplot with beeswarm overlay and a two-span multilabel annotation
demonstrating the span= parameter.

Usage (from project root):
    uv run python scripts/build/build_multilabel_span_example.py
"""

import tempfile
from pathlib import Path
from typing import Any

import altair as alt
import numpy as np
import polars as pl
import vl_convert as vlc

import dysonsphere as ds
from dysonsphere.export import _render_fixed_svg

ROOT = Path(__file__).resolve().parents[2]

rng = np.random.default_rng(42)

df = pl.DataFrame(
    {
        "group": (["A"] * 200 + ["B"] * 200 + ["C"] * 200 + ["D"] * 200 + ["E"] * 200 + ["F"] * 200),
        "value": np.concatenate(
            [
                rng.normal(10, 2, 200),
                rng.normal(14, 2, 200),
                rng.normal(11, 2, 200),
                rng.normal(13, 2, 200),
                rng.normal(9, 2, 200),
                rng.normal(10, 2, 200),
            ]
        ),
    }
)

CATEGORIES = ["A", "B", "C", "D", "E", "F"]

ds.theme(cornerRadius=True, chartWidth=125, chartHeight=75, chartFill="white")

df = ds.add_beeswarm(
    df,
    yCol="value",
    groupBy=["group"],
)

palette = ds.palette("blues2", n=6, start=0)

base = alt.Chart(df).encode(
    x=alt.X("group:N", sort=CATEGORIES),
    y=alt.Y("value:Q", title=None),
)

boxplot = base.mark_boxplot().encode(
    color=alt.Color("group:N", sort=CATEGORIES, scale=alt.Scale(range=palette), legend=None),
)

points = base.mark_circle().encode(
    xOffset=alt.XOffset("beeswarm_x:Q"),
)

shade = ds.add_shade(
    CATEGORIES,
    "group",
)

chart = points + boxplot

groups = {
    "Condition 1": [False, False, False, True, True, True],
    "Condition 2": [True, True, True, True, True, True],
}

title_params: dict[str, Any] = dict(orient="top", anchor="start", offset=4)
fontSize = alt.theme.options.get("fontSize", 7)

plot = ds.add_multilabel(
    chart,
    groups,
    categories=CATEGORIES,
    df=df,
    xCol="group",
    categoryLabel=False,
    categoryLabelAngle=-90,
    span=[
        {"Span 1": ["A", "B", "C"]},
        {"Span 2": ["D", "E", "F"]},
    ],
    spanBracketStyle="line",
).properties(
    title=alt.TitleParams(
        [
            "span=[",
            '    {"Span 1": ["A", "B", "C"]},',
            '    {"Span 2": ["D", "E", "F"]},',
            "]",
        ],
        fontSize=fontSize,
        **title_params,
    )
)

out_png = ROOT / "docs" / "multilabel_span_example.png"
with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as tmp:
    tmp_path = tmp.name
svg_content = _render_fixed_svg(plot, tmp_path)
Path(tmp_path).unlink()
out_png.write_bytes(vlc.svg_to_png(svg_content, ppi=1200))
print(f"saved {out_png}")
