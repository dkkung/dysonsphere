"""Single-cell UMAP embedding - clusters in the categorical palette, labeled at centroids."""

import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

ds.theme(chartWidth=180, chartHeight=170)

rng = np.random.default_rng(5)
types = ["T cells", "B cells", "NK", "Monocytes", "Dendritic", "Platelets"]
centers = [(-4.5, 2.0), (-2.0, -4.0), (3.5, 3.5), (5.0, -2.0), (0.5, 5.5), (-6.0, -3.0)]
spreads = [1.5, 1.2, 1.0, 1.4, 0.9, 0.7]
counts = [900, 700, 400, 650, 300, 200]

xs, ys, labels = [], [], []
for (cx, cy), s, k, name in zip(centers, spreads, counts, types):
    ang = rng.uniform(0, 2 * np.pi, k)
    rad = np.abs(rng.normal(0, s, k))
    warp = rng.normal(0, 0.4, k)  # gentle non-round manifold
    xs += list(cx + rad * np.cos(ang) + warp)
    ys += list(cy + rad * np.sin(ang) - warp)
    labels += [name] * k

df = pl.DataFrame({"UMAP1": xs, "UMAP2": ys, "cell type": labels})

points = (
    alt.Chart(df)
    .mark_circle(size=6, opacity=0.7)
    .encode(
        x=alt.X("UMAP1:Q", axis=None),
        y=alt.Y("UMAP2:Q", axis=None),
        color=alt.Color("cell type:N", legend=None),
    )
    .properties(view=alt.ViewConfig(stroke=None))
)

cent = df.group_by("cell type").agg(
    pl.col("UMAP1").mean().alias("cx"), pl.col("UMAP2").mean().alias("cy")
)
label_layer = ds.add_labels(
    cent,
    "cx",
    "cy",
    "cell type",
    fontSize=7,
    fill=True,  # a chip behind each cell-type label keeps it legible over the point cloud
    xDomain=[df["UMAP1"].min() - 1, df["UMAP1"].max() + 1],
    yDomain=[df["UMAP2"].min() - 1, df["UMAP2"].max() + 1],
)

chart = points + label_layer

