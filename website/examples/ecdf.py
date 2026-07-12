"""Empirical cumulative distributions - step curves for three groups in the categorical palette."""

import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

ds.theme(chartWidth=170, chartHeight=140)

rng = np.random.default_rng(12)
groups = {"control": (0.0, 1.0), "treated": (1.3, 1.15), "washout": (0.6, 0.9)}
rows = []
for g, (m, s) in groups.items():
    x = np.sort(rng.normal(m, s, 140))
    cdf = np.arange(1, x.size + 1) / x.size
    rows += [{"x": float(xi), "cdf": float(c), "group": g} for xi, c in zip(x, cdf)]

chart = (
    alt.Chart(pl.DataFrame(rows))
    .mark_line(interpolate="step-after")
    .encode(
        x=alt.X("x:Q", title="Value"),
        y=alt.Y("cdf:Q", title="Cumulative probability", scale=alt.Scale(domain=[0, 1], nice=False)),
        color=alt.Color("group:N", title=None),
    )
)
