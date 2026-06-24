import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

rng = np.random.default_rng(42)

df = pl.DataFrame(
    {
        "group": ["Control"] * 30 + ["Drug A"] * 30 + ["Drug B"] * 30,
        "value": np.concatenate(
            [
                rng.normal(10, 2, 30),
                rng.normal(14, 2, 30),
                rng.normal(11, 2, 30),
            ]
        ),
    }
)

CATEGORIES = ["Control", "Drug A", "Drug B"]

ds.theme(markSize=15)

chart = (
    alt.Chart(df)
    .mark_point()
    .encode(
        x=alt.X("group:N", sort=CATEGORIES, title="Treatment"),
        y=alt.Y("value:Q", title="Response (AU)"),
        color=alt.Color("group:N", sort=CATEGORIES, legend=None),
    )
)

ann = ds.add_pvalue(
    df,
    "group",
    "value",
    pairs=[("Control", "Drug A"), ("Control", "Drug B"), ("Drug A", "Drug B")],
    test="mannwhitneyu",
    categories=CATEGORIES,
    y_positions=[21, 5, 24],
    reverse=[("Control", "Drug B")],
)

ds.save(chart + ann, "p-value")
print("saved p-value")
