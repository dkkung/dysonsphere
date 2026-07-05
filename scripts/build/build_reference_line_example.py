"""
Generates docs/reference_line_example.png — the README preview for add_rule().

Left panel:  strip chart with two horizontal reference lines (axis="y").
Right panel: time series with a vertical reference line (axis="x").

Usage (from project root):
    uv run python scripts/build/build_reference_line_example.py
"""

from pathlib import Path
from typing import Any

import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

ROOT = Path(__file__).resolve().parents[2]


GROUPS = ["A", "B", "C", "D"]
SERIES = ["Series 1", "Series 2"]

rng = np.random.default_rng(42)

n = 20
strip_df = pl.DataFrame(
    {
        "group": sum([[g] * n for g in GROUPS], []),
        "value": np.concatenate([rng.normal(loc, 0.8, n) for loc in [5.5, 4.8, 6.2, 5.1]]),
    }
)

t = np.linspace(0, 20, 60)
time_df = pl.DataFrame(
    {
        "time": np.tile(t, 2),
        "value": np.concatenate(
            [
                np.sin(t * 0.5) * 2 + rng.normal(0, 0.15, 60),
                np.cos(t * 0.35) * 1.5 + rng.normal(0, 0.15, 60),
            ]
        ),
        "series": SERIES[0:1] * 60 + SERIES[1:2] * 60,
    }
)

title_params: dict[str, Any] = dict(orient="top", anchor="start", offset=4)

# ── Left: strip chart with horizontal reference lines ─────────────────────
ds.theme(palette="blues2", chartWidth=120, chartHeight=110)
fontSize = alt.theme.options.get("fontSize", 7)

strip = ds.mark_strip(strip_df, "group", "value", GROUPS, yTitle="Measurement")
left = (
    strip
    + ds.add_rule(4.0, label="Lower limit", labelPosition="bottom")
    + ds.add_rule(7.0, label="Upper limit", labelAlign="right")
).properties(
    title=alt.TitleParams(
        [
            'add_rule(4.0, label="Lower limit", labelPosition="bottom")',
            'add_rule(7.0, label="Upper limit", labelAlign="right")',
        ],
        fontSize=fontSize,
        **title_params,
    )
)

# ── Right: time series with vertical reference line ───────────────────────
ds.theme(palette="blues2", chartWidth=120, chartHeight=100)

lines = (
    alt.Chart(time_df)
    .mark_line()
    .encode(
        x=alt.X("time:Q", title=None),
        y=alt.Y("value:Q", title=None),
        color=alt.Color(
            "series:N",
            sort=SERIES,
            title=None,
            scale=alt.Scale(range=[ds.palette("blues2")[2], ds.palette("blues2")[7]]),
        ),
    )
)
right = (
    lines + ds.add_rule(10, axis="x", label="Intervention", labelPosition="right", labelAlign="bottom")
).properties(
    title=alt.TitleParams(
        [
            'add_rule(10, axis="x", label="Intervention",',
            'labelPosition="right", labelAlign="bottom")',
        ],
        fontSize=fontSize,
        **title_params,
    )
)

chart = alt.hconcat(left, right)

out_png = ROOT / "docs" / "reference_line_example.png"
ds.save(chart, str(out_png.with_suffix("")), format="png", background="light", transparent=False)
print(f"saved {out_png}")
