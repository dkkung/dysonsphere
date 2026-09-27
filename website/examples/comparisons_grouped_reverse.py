"""Grouped comparisons with the brackets hung below each pair, freeing the space above."""

import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

ds.theme(width=200, height=150)

rng = np.random.default_rng(3)
genes = ["IL6", "TNF", "IL1B"]
fold = {"IL6": 14.0, "TNF": 7.0, "IL1B": 11.0}

rows = [
    {"gene": g, "condition": cond, "expr": float(level * np.exp(rng.normal(0, 0.12)))}
    for g in genes
    for cond, level in [("Vehicle", 1.0), ("LPS", fold[g])]
    for _ in range(6)
]
df = pl.DataFrame(rows)

# Points on a non-zero baseline, so there is room under the data for the brackets.
pts = (
    alt.Chart(df)
    .mark_point(filled=True)
    .encode(
        x=alt.X("gene:N", title="Gene", sort=genes, axis=alt.Axis(labelFontStyle="italic")),
        xOffset=alt.XOffset("condition:N", sort=["Vehicle", "LPS"]),
        y=alt.Y("expr:Q", title="Relative expression", scale=alt.Scale(type="log")),
        color=alt.Color("condition:N", sort=["Vehicle", "LPS"], title=None),
    )
)

# reverse= names xOffset LEVELS here, and applies in every category.
chart = pts + ds.stats.comparisons(
    df,
    "gene",
    "expr",
    pairs=[("Vehicle", "LPS")],
    xOffset="condition",
    categories=genes,
    xOffsetSort=["Vehicle", "LPS"],
    test="ttest_ind",
    labelStyle="asterisks",
    reverse=[("Vehicle", "LPS")],
)
