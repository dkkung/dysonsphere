"""MA plot - RNA-seq log2 fold change vs mean expression, significant genes colored and labeled."""

import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

alt.data_transformers.enable("default", max_rows=None)
ds.theme(chartWidth=190, chartHeight=165)

rng = np.random.default_rng(11)
n = 4000

# A = mean log2 expression (average); M = log2 fold change. An MA cloud fans out at low expression,
# so the null spread of M shrinks as A grows (heteroscedastic), centred on M = 0.
A = rng.uniform(1.0, 15.0, n)
spread = 0.2 + 1.7 / (A - 0.4)  # wide at low A, tight at high A
M = rng.normal(0.0, spread)

# Inject true differentially-expressed genes and label them: overwrite the nearest cloud point at
# each target (A, M) so the hit sits where a real DE gene would.
genes: list[str | None] = [None] * n
de = {
    "MYC": (11.6, 2.9), "CCND1": (10.1, 2.4), "VEGFA": (8.7, 2.0), "FN1": (12.6, 2.5),
    "CDKN1A": (9.4, -2.7), "BAX": (7.9, -2.2), "GADD45A": (9.0, -2.4), "SESN2": (10.9, -1.9),
}
for name, (a, m) in de.items():
    i = int(np.argmin((A - a) ** 2 + M**2))
    A[i], M[i], genes[i] = a, m, name

# Significance ~ how far M sits from the local null spread (a stand-in for an adjusted p-value).
sig = np.abs(M) / spread > 2.5
klass = np.where(~sig, "ns", np.where(M > 0, "up", "down"))

df = pl.DataFrame({"A": A, "M": M, "klass": klass, "gene": genes})

points = (
    alt.Chart(df)
    .mark_circle(size=7, opacity=0.7, clip=True)
    .encode(
        x=alt.X("A:Q", title="mean log₂ expression", scale=alt.Scale(domain=[0, 16], nice=False)),
        y=alt.Y("M:Q", title="log₂ fold change", scale=alt.Scale(domain=[-6, 6], nice=False)),
        color=alt.Color(
            "klass:N",
            scale=alt.Scale(domain=["down", "ns", "up"], range=["#3A68BB", "#9AA0A6", "#E0559A"]),
            legend=None,
        ),
    )
)

zero = ds.add_rule(0.0)  # M = 0: no change
thresh = ds.add_rule([-1.0, 1.0], strokeDash=True)  # 2-fold-change guides

gene_labels = ds.add_labels(df, "A", "M", "gene", labels=df["gene"].is_not_null())

chart = points + zero + thresh + gene_labels
