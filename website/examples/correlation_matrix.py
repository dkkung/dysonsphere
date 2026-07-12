"""A feature correlation matrix - Pearson r on a diverging scale, cells labeled with values."""

import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

from dysonsphere.palettes import colors

ds.theme(chartWidth=150, chartHeight=150)

rng = np.random.default_rng(8)
feats = ["Age", "BMI", "SBP", "Glucose", "HbA1c", "LDL", "HDL"]
p = len(feats)
loadings = rng.normal(0, 1, (p, 3))  # a few latent factors -> realistic structure
cov = loadings @ loadings.T + np.diag(rng.uniform(0.4, 1.2, p))
X = rng.multivariate_normal(np.zeros(p), cov, 400)
X[:, feats.index("HDL")] *= -1  # make HDL anti-correlate
C = np.corrcoef(X.T)

df = pl.DataFrame(
    [{"a": feats[i], "b": feats[j], "r": round(float(C[i, j]), 2)} for i in range(p) for j in range(p)]
)
enc = dict(
    x=alt.X("a:N", title=None, sort=feats, axis=alt.Axis(labelAngle=-45)),
    y=alt.Y("b:N", title=None, sort=feats),
)
rect = alt.Chart(df).mark_rect().encode(
    **enc,
    color=alt.Color("r:Q", title="r", scale=alt.Scale(range=colors["redsblues"], domain=[-1, 1])),
)
text = alt.Chart(df).mark_text(fontSize=5).encode(
    **enc,
    text=alt.Text("r:Q", format=".1f"),
    color=alt.condition("abs(datum.r) > 0.6", alt.value("white"), alt.value("black")),
)

chart = rect + text
