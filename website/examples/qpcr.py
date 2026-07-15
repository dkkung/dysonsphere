"""qPCR grouped bars - cytokine expression (vehicle vs LPS) with within-gene significance brackets."""

import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

ds.theme(chartWidth=215, chartHeight=160)

rng = np.random.default_rng(7)
genes = ["GAPDH", "IL6", "TNF", "IL1B", "CXCL10"]
fold = {"GAPDH": 1.0, "IL6": 17.0, "TNF": 8.0, "IL1B": 12.0, "CXCL10": 21.0}  # LPS induction

rows = []
for g in genes:
    for cond, level in [("Vehicle", 1.0), ("LPS", fold[g])]:
        for _ in range(4):  # biological quadruplicate, lognormal technical noise
            rows.append({"gene": g, "condition": cond, "expr": float(level * np.exp(rng.normal(0, 0.1)))})
df = pl.DataFrame(rows)

base = alt.Chart(df).encode(
    x=alt.X("gene:N", title="Gene", sort=genes, axis=alt.Axis(labelFontStyle="italic")),  # italic gene symbols
    xOffset=alt.XOffset("condition:N", sort=["Vehicle", "LPS"]),
)
bars = base.mark_bar().encode(
    y=alt.Y("mean(expr):Q", title="Relative expression", scale=alt.Scale(domain=[0, 27])),
    color=alt.Color("condition:N", sort=["Vehicle", "LPS"], title=None),
)
err = base.mark_errorbar(extent="stderr").encode(y=alt.Y("expr:Q", title=""))

# Real within-gene vehicle-vs-LPS test - one bracket per gene, GAPDH (housekeeping) comes out ns.
sig = ds.add_comparisons(
    df, "gene", "expr", xOffsetCol="condition",
    categories=genes, xOffsetSort=["Vehicle", "LPS"],
    test="ttest_ind", labelStyle="asterisks",
)

chart = bars + err + sig
