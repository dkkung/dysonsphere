"""
Demo of add_labels() - force-repel point labels with connectors.

`labels=n` auto-selects n points spread evenly across the plot (unbiased, deterministic) and
labels them with non-overlapping text + connector lines. No scale pinning needed - add_labels
pins the axes to the data extent itself.

Usage (from project root):
    uv run python scripts/plots/point_labels.py
"""

import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

rng = np.random.default_rng(1)
n = 150

# A correlated scatter standing in for, e.g., per-gene measurements.
x = rng.normal(0, 1, n)
df = pl.DataFrame({"x": x, "y": 0.7 * x + rng.normal(0, 0.7, n), "gene": [f"G{i}" for i in range(n)]})

ds.theme(chartWidth=200, chartHeight=150)

points = alt.Chart(df).mark_circle().encode(x=alt.X("x:Q", title="log2 fold change"), y=alt.Y("y:Q", title="score"))

# Label 12 evenly-spread points - no list to curate, no alt.Scale to pin.
chart = points + ds.add_labels(df, "x", "y", "gene", labels=12)

ds.save(chart, "point_labels")
print("saved point_labels")
