"""Reaction free-energy profile - transition states and intermediates, annotated."""

import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

ds.theme(chartWidth=240, chartHeight=150)

# control points along the reaction coordinate: R -> TS1 -> Int -> TS2 -> P
xk = np.array([0.0, 1.0, 2.0, 3.0, 4.0])
gk = np.array([0.0, 15.5, 6.0, 11.0, -8.0])
# smooth interpolation with a cosine blend between control points
xs = np.linspace(0, 4, 300)
g = np.empty_like(xs)
for i, x in enumerate(xs):
    k = min(int(x), 3)
    t = x - k
    s = 0.5 - 0.5 * np.cos(np.pi * t)
    g[i] = gk[k] * (1 - s) + gk[k + 1] * s
df = pl.DataFrame({"rc": xs, "G": g})

line = (
    alt.Chart(df)
    .mark_line(strokeWidth=1.0)
    .encode(
        x=alt.X("rc:Q", title="Reaction coordinate", axis=alt.Axis(labels=False, ticks=False)),
        y=alt.Y("G:Q", title="ΔG (kcal/mol)", scale=alt.Scale(domain=[-12, 20])),
    )
)

ann = (
    ds.add_text("Reactants", x=0.0, y=-2.5, fontSize=6, align="left")
    + ds.add_text("TS1", x=1.0, y=18.0, fontSize=6)
    + ds.add_text("Intermediate", x=2.0, y=3.0, fontSize=6)
    + ds.add_text("TS2", x=3.0, y=13.5, fontSize=6)
    + ds.add_text("Product", x=4.0, y=-10.5, fontSize=6, align="right")
)

chart = line + ann

