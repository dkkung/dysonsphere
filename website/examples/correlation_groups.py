"""Per-series correlation - biomarker vs drug response across three cell lines, a fit + r each."""

import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

ds.theme(chartWidth=200, chartHeight=175)

rng = np.random.default_rng(5)
# each cell line has its own biomarker-response relationship (predictive, flat, inverse)
lines = {"BT-20": (0.9, 1.5, 1.1), "MCF-7": (0.3, 5.0, 1.0), "HCC-38": (-0.55, 9.5, 1.2)}
rows = []
for cell, (slope, inter, noise) in lines.items():
    x = rng.uniform(0, 10, 45)
    y = slope * x + inter + rng.normal(0, noise, 45)
    rows += [{"biomarker": float(a), "response": float(b), "cell line": cell} for a, b in zip(x, y)]
df = pl.DataFrame(rows)

scatter = alt.Chart(df).mark_circle(size=11, opacity=0.7).encode(
    x=alt.X("biomarker:Q", title="Biomarker (log₂ TPM)"),
    y=alt.Y("response:Q", title="Drug response"),  # explicit title: keeps the CI band's field out of it
    color=alt.Color("cell line:N", title="Cell line"),
)

# One OLS fit + r per cell line, each coloured to match its points (color=groupCol shares the scale).
chart = scatter + ds.add_correlation(df, "biomarker", "response", groupCol="cell line", ci=True)
