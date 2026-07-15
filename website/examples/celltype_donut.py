"""Cell-type composition donut - PBMC fractions as a mark_arc donut with a centred total."""

import altair as alt
import polars as pl

import dysonsphere as ds

ds.theme(chartWidth=175, chartHeight=175)

# PBMC composition from a single-cell run (same cell types as the UMAP example). mark_arc renders a
# donut by default under the dysonsphere theme (innerRadius + padAngle from config.arc).
df = pl.DataFrame(
    {
        "cell type": ["T cells", "B cells", "NK", "Monocytes", "Dendritic", "Platelets"],
        "cells": [5200, 1980, 1240, 2600, 880, 580],
    }
)
total = df["cells"].sum()

donut = alt.Chart(df).mark_arc().encode(
    theta=alt.Theta("cells:Q", stack=True),
    color=alt.Color("cell type:N", sort=list(df["cell type"]), legend=alt.Legend(title="cell type")),
    order=alt.Order("cells:Q", sort="descending"),
)

# Total-count readout in the hole of the donut.
center = (
    alt.Chart(pl.DataFrame({"label": [f"{total:,}\ncells"]}))
    .mark_text(lineBreak="\n", fontSize=9)
    .encode(text="label:N")
)

chart = donut + center
