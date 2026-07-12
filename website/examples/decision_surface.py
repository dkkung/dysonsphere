"""Classifier decision surface - a kernel probability field behind the two-moons data."""

import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

alt.data_transformers.enable("default", max_rows=None)
ds.theme(chartWidth=175, chartHeight=150, divergingPalette="pinksblues", closed=True, viewPadding=False)

rng = np.random.default_rng(0)
n = 120
t = np.linspace(0, np.pi, n)
x0 = np.c_[np.cos(t), np.sin(t)] + rng.normal(0, 0.12, (n, 2))
x1 = np.c_[1 - np.cos(t), 0.4 - np.sin(t)] + rng.normal(0, 0.12, (n, 2))
pts = np.vstack([x0, x1])
lab = np.r_[np.zeros(n), np.ones(n)]

gx = np.linspace(-1.7, 2.7, 108)
gy = np.linspace(-1.3, 1.9, 80)
GX, GY = np.meshgrid(gx, gy)
gamma = 3.0
score = np.zeros_like(GX)
for (px, py), c in zip(pts, lab):
    k = np.exp(-gamma * ((GX - px) ** 2 + (GY - py) ** 2))
    score += k if c == 1 else -k
prob = 1 / (1 + np.exp(-score / 2))

sx = (gx[1] - gx[0])
sy = (gy[1] - gy[0])
rows = []
for i in range(GX.shape[0]):
    for j in range(GX.shape[1]):
        rows.append(
            {
                "x0": round(gx[j], 3),
                "x1": round(gx[j] + sx + sx * 0.3, 3),
                "y0": round(gy[i], 3),
                "y1": round(gy[i] + sy + sy * 0.3, 3),
                "p": round(float(prob[i, j]), 4),
            }
        )
field_df = pl.DataFrame(rows)
pts_df = pl.DataFrame({"x": pts[:, 0], "y": pts[:, 1], "class": [f"class {int(c)}" for c in lab]})

field = (
    alt.Chart(field_df)
    .mark_rect(stroke=None, clip=True)
    .encode(
        x=alt.X("x0:Q", title="x₁", scale=alt.Scale(domain=[gx[0], gx[-1]], nice=False)),
        x2="x1",
        y=alt.Y("y0:Q", title="x₂", scale=alt.Scale(domain=[gy[0], gy[-1]], nice=False)),
        y2="y1",
        color=alt.Color("p:Q", title="P(class 1)", scale=alt.Scale(domainMid=0.5)),
    )
)
scatter = (
    alt.Chart(pts_df)
    .mark_circle(size=14, opacity=0.9, stroke="black", strokeWidth=0.3)
    .encode(
        x="x:Q",
        y="y:Q",
        color=alt.Color("class:N", scale=alt.Scale(range=["#C2506E", "#2C5F8A"]), legend=None),
    )
)

chart = field + scatter

