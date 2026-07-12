"""Clifford strange attractor - a chaotic map's dense point cloud, colored by speed."""

import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

alt.data_transformers.enable("default", max_rows=None)
ds.theme(chartWidth=160, chartHeight=160)

a, b, c, d = -1.7, 1.8, -1.9, -0.4
n = 5000
x = np.empty(n)
y = np.empty(n)
x[0], y[0] = 0.1, 0.1
for i in range(1, n):
    x[i] = np.sin(a * y[i - 1]) + c * np.cos(a * x[i - 1])
    y[i] = np.sin(b * x[i - 1]) + d * np.cos(b * y[i - 1])
speed = np.hypot(np.gradient(x), np.gradient(y))

df = pl.DataFrame({"x": x, "y": y, "speed": speed})

chart = (
    alt.Chart(df)
    .mark_circle(size=1.5, opacity=0.55)
    .encode(
        x=alt.X("x:Q", axis=None),
        y=alt.Y("y:Q", axis=None),
        color=alt.Color("speed:Q", title=None, legend=None),
    )
    .properties(view=alt.ViewConfig(stroke=None))
)

