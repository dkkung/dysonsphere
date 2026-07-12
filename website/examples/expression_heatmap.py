"""A gene-expression heatmap - z-scored RNA-seq across samples, grouped by condition (redsblues)."""

import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds
from dysonsphere.palettes import colors

# bandPadding=0 makes the band scales' cells sit flush (config.scale.bandPaddingInner/Outer)
ds.theme(chartWidth=165, chartHeight=180, closed=True, viewPadding=0, bandPadding=0)

rng = np.random.default_rng(4)
n_rep = 6  # replicates per condition
samples = [f"C{i + 1}" for i in range(n_rep)] + [f"T{i + 1}" for i in range(n_rep)]
treated = np.array([0] * n_rep + [1] * n_rep)  # 0 = control, 1 = treated

# three gene programs: up in treated (proliferation), down in treated (tumor suppressors),
# and flat housekeeping controls - ordered so the pattern reads top to bottom
up = ["MYC", "CCND1", "VEGFA", "MMP9", "CDK4"]
down = ["CDKN1A", "PTEN", "BAX", "TP53", "FAS"]
flat = ["ACTB", "GAPDH", "TUBB", "B2M", "RPL13"]
genes = up + down + flat

expr = rng.normal(0, 0.4, (len(genes), 2 * n_rep))
expr[0:5] += treated * rng.uniform(1.2, 2.2, (5, 1))  # induced in treated
expr[5:10] -= treated * rng.uniform(1.2, 2.2, (5, 1))  # repressed in treated
z = (expr - expr.mean(1, keepdims=True)) / expr.std(1, keepdims=True)  # z-score per gene (row)

df = pl.DataFrame(
    [
        {"gene": genes[i], "sample": samples[j], "z": round(float(z[i, j]), 2)}
        for i in range(len(genes))
        for j in range(2 * n_rep)
    ]
)

chart = (
    alt.Chart(df)
    .mark_rect()
    .encode(
        x=alt.X("sample:N", title=None, sort=samples),
        # gene symbols are italicized by convention; cells sit flush via theme(bandPadding=0)
        y=alt.Y("gene:N", title=None, sort=genes, axis=alt.Axis(labelFontStyle="italic")),
        color=alt.Color("z:Q", title="z-score", scale=alt.Scale(range=colors["redsblues"], domain=[-2, 2])),
    )
)
