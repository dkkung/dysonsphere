"""k-means clusters - Gaussian blobs in the categorical palette, with their centroids marked."""

import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

ds.theme(chartWidth=165, chartHeight=155)

rng = np.random.default_rng(1)
centers = [(0, 0), (4.5, 3), (-3.5, 4), (3, -3.5), (-4, -2.5)]
xs, ys, lab = [], [], []
for i, (cx, cy) in enumerate(centers):
    n = int(rng.integers(70, 130))
    pts = rng.multivariate_normal([cx, cy], [[0.8, 0.25], [0.25, 0.8]], n)
    xs += list(pts[:, 0])
    ys += list(pts[:, 1])
    lab += [f"cluster {i + 1}"] * n
df = pl.DataFrame({"x": xs, "y": ys, "cluster": lab})
cen = pl.DataFrame({"x": [float(c[0]) for c in centers], "y": [float(c[1]) for c in centers]})

pts = alt.Chart(df).mark_circle(size=10, opacity=0.65).encode(
    x=alt.X("x:Q", axis=None),
    y=alt.Y("y:Q", axis=None),
    color=alt.Color("cluster:N", title=None),
)
centroids = alt.Chart(cen).mark_point(shape="cross", size=90, strokeWidth=2, filled=False, opacity=1).encode(
    x="x:Q", y="y:Q", color=alt.value("black"),
)

chart = (pts + centroids).properties(view=alt.ViewConfig(stroke=None))
