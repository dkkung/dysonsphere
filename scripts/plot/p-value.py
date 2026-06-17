import altair as alt
import numpy as np
import polars as pl

import theme

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

theme.options(markSize=15, markFillOpacity=0.6)

chart = (
    alt.Chart(df)
    .mark_point()
    .encode(
        x=alt.X("group:N", sort=CATEGORIES, title="Treatment"),
        y=alt.Y("value:Q", title="Response (AU)"),
        color=alt.Color("group:N", sort=CATEGORIES, legend=None),
    )
)

# normal bracket above data
ann_a = theme.pvalue_layer(
    df,
    "group",
    "value",
    "Control",
    "Drug A",
    test="mannwhitneyu",
    categories=CATEGORIES,
    y=21,
)

# reversed bracket below data
ann_b = theme.pvalue_layer(
    df,
    "group",
    "value",
    "Control",
    "Drug B",
    test="mannwhitneyu",
    categories=CATEGORIES,
    y=5,
    reverse=True,
)

theme.save(chart + ann_a + ann_b, "p-value")
print("saved p-value")
