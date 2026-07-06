import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

ds.theme(chartWidth=140)

rng = np.random.default_rng(42)
CATEGORIES = ["Control", "Group A", "Group B", "Group C", "Group D", "Group E"]
means = [10, 14, 11, 13, 9, 10]

df = pl.DataFrame(
    {
        "group": [g for g in CATEGORIES for _ in range(200)],
        "value": np.concatenate([rng.normal(m, 2, 200) for m in means]),
    }
)
df = ds.add_beeswarm(df, yCol="value", groupBy=["group"])

base = alt.Chart(df).encode(
    x=alt.X("group:N", sort=CATEGORIES),
    y=alt.Y("value:Q", title="Response (AU)"),
)
boxplot = base.mark_boxplot().encode(
    color=alt.Color("group:N", sort=CATEGORIES, scale=alt.Scale(range=ds.categorical(members=3)), legend=None),
)
points = base.mark_circle().encode(xOffset=alt.XOffset("beeswarm_x:Q"))

groups = {
    "Treatment 1": [False, False, "A", "A", "B", "B"],
    "Treatment 2": [False, True, False, True, False, True],
}

chart = ds.add_multilabel(
    points + boxplot,
    groups,
    categories=CATEGORIES,
    showSampleSize=True,
    df=df,
    xCol="group",
    categoryLabel=True,
)
