"""Polycrystalline grain map - Voronoi grains colored by crystal orientation (australis)."""

import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

alt.data_transformers.enable("default", max_rows=None)
ds.theme(chartWidth=160, chartHeight=160, closed=True, viewPadding=False)

rng = np.random.default_rng(14)
N = 95
n_seeds = 55
seeds = rng.uniform(0, N, (n_seeds, 2))
orient = rng.uniform(0, 90, n_seeds)  # grain orientation (deg)

ys, xs = np.mgrid[0:N, 0:N]
d2 = (xs[..., None] - seeds[:, 0]) ** 2 + (ys[..., None] - seeds[:, 1]) ** 2
nearest = d2.argmin(axis=2)
grain = orient[nearest]

step = 100.0 / N
rows = []
for i in range(N):
    for j in range(N):
        rows.append(
            {
                "x0": round(j * step, 3),
                "x1": round((j + 1) * step + step * 0.3, 3),
                "y0": round(i * step, 3),
                "y1": round((i + 1) * step + step * 0.3, 3),
                "theta": round(float(grain[i, j]), 3),
            }
        )
df = pl.DataFrame(rows)

chart = (
    alt.Chart(df)
    .mark_rect(stroke=None, clip=True)
    .encode(
        x=alt.X("x0:Q", title="x (µm)", scale=alt.Scale(domain=[0, 100], nice=False)),
        x2="x1",
        y=alt.Y("y0:Q", title="y (µm)", scale=alt.Scale(domain=[0, 100], nice=False)),
        y2="y1",
        color=alt.Color("theta:Q", title="Orientation (°)"),
    )
)

