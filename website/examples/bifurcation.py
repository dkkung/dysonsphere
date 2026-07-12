"""The logistic-map bifurcation diagram - the period-doubling road to chaos, colored by state."""

import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

alt.data_transformers.enable("default", max_rows=None)
ds.theme(chartWidth=200, chartHeight=145, rampPalette="australis")

rs = np.linspace(2.8, 4.0, 900)
x = np.full_like(rs, 0.5)
for _ in range(320):  # burn in the transient
    x = rs * x * (1 - x)
pts = []
for _ in range(120):  # sample the attractor
    x = rs * x * (1 - x)
    pts.append(np.column_stack([rs, x]))
P = np.vstack(pts)
idx = np.random.default_rng(0).choice(P.shape[0], size=14000, replace=False)  # thin for a lean spec
P = P[idx]
df = pl.DataFrame({"r": P[:, 0], "x": P[:, 1]})

chart = (
    alt.Chart(df)
    .mark_circle(size=0.6, opacity=0.5)
    .encode(
        x=alt.X("r:Q", title="Growth rate  r", scale=alt.Scale(domain=[2.8, 4.0], nice=False)),
        y=alt.Y("x:Q", title="Population  x", scale=alt.Scale(domain=[0, 1], nice=False)),
        color=alt.Color("x:Q", legend=None),
    )
)
