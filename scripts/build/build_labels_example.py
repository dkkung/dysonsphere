"""
Generates docs/labels_example.png — the README preview for add_labels().

Usage (from project root):
    uv run python scripts/build/build_labels_example.py
"""

from pathlib import Path

import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

ROOT = Path(__file__).resolve().parents[2]

rng = np.random.default_rng(7)
n = 120
x = rng.normal(0, 1, n)
df = pl.DataFrame(
    {
        "x": x,
        "y": 0.7 * x + rng.normal(0, 0.7, n),
        "name": [f"P{i + 1}" for i in range(n)],
    }
)

ds.theme(chartWidth=180, chartHeight=150)
fontSize = alt.theme.options.get("fontSize", 7)

base = (
    alt.Chart(df)
    .mark_point()
    .encode(
        x=alt.X("x:Q", title="x"),
        y=alt.Y("y:Q", title="y"),
    )
)

# labels=8 auto-selects 8 evenly-spread points; the repel places them in open space with connectors.
chart = (base + ds.add_labels(df, "x", "y", "name", labels=8)).properties(
    title=alt.TitleParams(
        ['add_labels(df, "x", "y", "name", labels=8)'],
        fontSize=fontSize,
        orient="top",
        anchor="start",
        offset=4,
    )
)

out_png = ROOT / "docs" / "labels_example.png"
ds.save(chart, str(out_png.with_suffix("")), format="png", background="light", transparent=False)
print(f"saved {out_png}")
