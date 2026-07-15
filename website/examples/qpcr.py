"""qPCR grouped bars - relative expression of cytokine genes, vehicle vs LPS, mean +/- SEM."""

import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

ds.theme(chartWidth=210, chartHeight=150)

rng = np.random.default_rng(7)
genes = ["GAPDH", "IL6", "TNF", "IL1B", "CXCL10"]
fold = {"GAPDH": 1.0, "IL6": 17.0, "TNF": 8.0, "IL1B": 12.0, "CXCL10": 21.0}  # LPS induction

rows = []
for g in genes:
    for cond, level in [("Vehicle", 1.0), ("LPS", fold[g])]:
        for _ in range(4):  # biological quadruplicate, lognormal technical noise
            rows.append({"gene": g, "condition": cond, "expr": float(level * np.exp(rng.normal(0, 0.16)))})
df = pl.DataFrame(rows)

base = alt.Chart(df).encode(
    x=alt.X("gene:N", title=None, sort=genes, axis=alt.Axis(labelFontStyle="italic")),  # italic gene symbols
    xOffset=alt.XOffset("condition:N", sort=["Vehicle", "LPS"]),
)
bars = base.mark_bar().encode(
    y=alt.Y("mean(expr):Q", title="relative expression (2^−ΔΔCt)", scale=alt.Scale(domain=[0, 26])),
    color=alt.Color("condition:N", sort=["Vehicle", "LPS"], title=None),
)
err = base.mark_errorbar(extent="stderr").encode(y=alt.Y("expr:Q", title=""))

# Significance stars over the LPS bar of each induced gene (paired with the vehicle reference).
stars = pl.DataFrame(
    {"gene": ["IL6", "TNF", "IL1B", "CXCL10"], "expr": [fold[g] for g in ["IL6", "TNF", "IL1B", "CXCL10"]],
     "mark": ["***", "**", "***", "***"]}
)
sig = (
    alt.Chart(stars)
    .mark_text(baseline="bottom", dy=-9, fontSize=8)
    .encode(x=alt.X("gene:N", sort=genes), xOffset=alt.value(9), y="expr:Q", text="mark:N")
)

chart = bars + err + sig
