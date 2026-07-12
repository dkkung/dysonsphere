"""Confusion matrix - a classifier's predictions, cell counts via add_text (australis)."""

import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

ds.theme(chartWidth=150, chartHeight=150)

classes = ["cat", "dog", "bird", "fish", "frog"]
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
        x=alt.X("pred:N", title="predicted", sort=classes),
        y=alt.Y("true:N", title="actual", sort=classes),
        color=alt.Color("n:Q", title=None, legend=None),
    )
)

labels = None
for i, tc in enumerate(classes):
    for j, pc in enumerate(classes):
        col = "white" if M[i, j] < 40 else "black"
        layer = ds.add_text(str(int(M[i, j])), x=pc, y=tc, fontSize=6, color=col)
        labels = layer if labels is None else labels + layer

chart = heat + labels

