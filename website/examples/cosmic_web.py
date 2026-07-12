"""Cosmic web - large-scale structure density field with filaments, voids, and nodes (borealis)."""

import altair as alt
import numpy as np
import polars as pl
from scipy.ndimage import gaussian_filter

import dysonsphere as ds

alt.data_transformers.enable("default", max_rows=None)
ds.theme(chartWidth=165, chartHeight=165, heatmapPalette="borealis")

rng = np.random.default_rng(19)
N = 100
# ridges of a smoothed Gaussian random field trace a cellular web (walls between voids);
# multiply scales so both big voids and fine filaments appear, then brighten the nodes.
field = gaussian_filter(rng.standard_normal((N, N)), 5.0)
gy, gx = np.gradient(field)
web = np.hypot(gx, gy)
web = gaussian_filter(web, 0.7)
web = (web / web.max()) ** 0.7

fine = gaussian_filter(rng.standard_normal((N, N)), 2.2)
fgy, fgx = np.gradient(fine)
web = web + 0.4 * np.hypot(fgx, fgy) / np.hypot(fgx, fgy).max()

ys, xs = np.mgrid[0:N, 0:N]
for _ in range(40):  # bright galaxy clusters at random web vertices
    cy, cx = rng.uniform(0, N, 2)
    if web[int(cy), int(cx)] > 0.5:
        web += rng.uniform(0.5, 1.2) * np.exp(-((xs - cx) ** 2 + (ys - cy) ** 2) / (2 * 1.3**2))

web = np.clip(web, 0, np.percentile(web, 99.5))
web = web / web.max()

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
                "delta": round(float(web[i, j]), 4),
            }
        )
df = pl.DataFrame(rows)

chart = (
    alt.Chart(df)
    .mark_rect(stroke=None, clip=True)
    .encode(
        x=alt.X("x0:Q", title="comoving distance (Mpc)", scale=alt.Scale(domain=[0, 100], nice=False)),
        x2="x1",
        y=alt.Y("y0:Q", title=None, scale=alt.Scale(domain=[0, 100], nice=False)),
        y2="y1",
        color=alt.Color("delta:Q", title=None, legend=None),
    )
)

