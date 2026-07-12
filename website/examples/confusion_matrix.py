"""Confusion matrix - a classifier's predictions, cell counts labeled per cell (australis)."""

import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

ds.theme(chartWidth=150, chartHeight=150, xDomain=False, yDomain=False, axisOffset=0, viewPadding=0)

classes = ["Cat", "Dog", "Bird", "Fish", "Frog"]
rng = np.random.default_rng(30)
M = np.zeros((5, 5), dtype=int)
for i in range(5):
    M[i, i] = rng.integers(70, 96)
    for j in range(5):
        if i != j:
            M[i, j] = rng.integers(0, 10)

rows = []
for i, tc in enumerate(classes):
    for j, pc in enumerate(classes):
        rows.append({"true": tc, "pred": pc, "n": int(M[i, j])})
df = pl.DataFrame(rows)

heat = (
    alt.Chart(df)
    .mark_rect()
    .encode(
        x=alt.X("pred:N", title="Predicted", sort=classes),
        y=alt.Y("true:N", title="Actual", sort=classes),
        color=alt.Color("n:Q", title=None, legend=None),
    )
)

# Cell counts as a field-encoded mark_text: sharing the x/y band scales with the heatmap centers
# each label exactly on its cell in every renderer (an add_text datum can drift off the band centre
# in browser Vega). White on the dark high-count cells, black on the light low-count ones.
labels = (
    alt.Chart(df)
    .mark_text(fontSize=6)
    .encode(
        x=alt.X("pred:N", sort=classes),
        y=alt.Y("true:N", sort=classes),
        text=alt.Text("n:Q"),
        color=alt.condition("datum.n < 40", alt.value("white"), alt.value("black")),
    )
)

chart = heat + labels

