"""ROC curves for three classifiers - true vs false positive rate, with the chance diagonal."""

import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

ds.theme(chartWidth=150, chartHeight=150)

rng = np.random.default_rng(5)


def roc(sep, n=500):
    pos, neg = rng.normal(sep, 1, n), rng.normal(0, 1, n)
    thr = np.unique(np.concatenate([pos, neg]))[::-1]
    tpr = np.array([(pos >= t).mean() for t in thr])
    fpr = np.array([(neg >= t).mean() for t in thr])
    order = np.argsort(fpr)
    return fpr[order], tpr[order], float(np.trapezoid(tpr[order], fpr[order]))


rows = []
for name, sep in [("strong", 2.0), ("medium", 1.1), ("weak", 0.5)]:
    fpr, tpr, auc = roc(sep)
    rows += [{"fpr": float(a), "tpr": float(b), "model": f"{name}  (AUC {auc:.2f})"} for a, b in zip(fpr, tpr)]

curves = alt.Chart(pl.DataFrame(rows)).mark_line(interpolate="step-after").encode(
    x=alt.X("fpr:Q", title="false positive rate", scale=alt.Scale(domain=[0, 1], nice=False)),
    y=alt.Y("tpr:Q", title="true positive rate", scale=alt.Scale(domain=[0, 1], nice=False)),
    color=alt.Color("model:N", title=None),
)
chance = alt.Chart(pl.DataFrame({"fpr": [0.0, 1.0], "tpr": [0.0, 1.0]})).mark_line(
    strokeDash=[3, 3], color="gray", opacity=0.7
).encode(x="fpr:Q", y="tpr:Q")

chart = chance + curves
