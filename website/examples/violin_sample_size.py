import numpy as np
import polars as pl

import dysonsphere as ds

ds.theme(chartWidth=150, chartHeight=120)

rng = np.random.default_rng(21)
conds = ["vehicle", "low dose", "high dose"]
data = {
    "vehicle": rng.normal(52, 8, 90),
    "low dose": np.concatenate([rng.normal(46, 7, 70), rng.normal(60, 5, 20)]),
    "high dose": rng.normal(34, 9, 90),
}
rows = []
for c in conds:
    for v in data[c]:
        rows.append({"condition": c, "response": float(v)})
df = pl.DataFrame(rows)

violin = ds.mark_violin(df, "condition", "response", conds, trim=True, yTitle="response (a.u.)")

# per-group sample sizes in a multilabel table below the axis
chart = ds.add_multilabel(
    violin,
    categories=conds,
    showSampleSize=True,
    df=df,
    xCol="condition",
    categoryLabel=True,
)
