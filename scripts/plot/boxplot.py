import altair as alt
import numpy as np
import polars as pl

import theme

rng = np.random.default_rng(42)

df = pl.DataFrame(
    {
        "group": (
            ["Control"] * 200
            + ["Drug A"] * 200
            + ["Drug B"] * 200
            + ["Drug C"] * 200
            + ["Drug D"] * 200
            + ["Drug E"] * 200
        ),
        "value": np.concatenate(
            [
                rng.normal(10, 2, 200),
                rng.normal(14, 2, 200),
                rng.normal(11, 2, 200),
                rng.normal(13, 2, 200),
                rng.normal(9, 2, 200),
                rng.normal(10, 2, 200),
            ]
        ),
    }
)

CATEGORIES = ["Control", "Drug A", "Drug B", "Drug C", "Drug D", "Drug E"]

theme.options()

df = theme.add_beeswarm_offsets(
    df,
    y_col="value",
    group_by=["group"],
    step=10,
)

# palette = theme.palette_range("greys", n=1, start=2)
# palette = theme.palette_range("mpl_viridis", n=len(CATEGORIES), start=4)
palette = theme.palette_range("lavenders", n=6, start=0)

base = alt.Chart(df).encode(
    x=alt.X(
        "group:N",
        sort=CATEGORIES,
        title="Treatment",
        axis=alt.Axis(labelAngle=-45, labelAlign="right"),
    ),
    y=alt.Y("value:Q", title="Response (AU)"),
)

boxplot = base.mark_boxplot().encode(
    color=alt.Color("group:N", sort=CATEGORIES, scale=alt.Scale(range=palette), legend=None),
)

points = base.mark_circle(size=5).encode(
    xOffset=alt.XOffset("beeswarm_x:Q"),
)

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

ann_b = theme.pvalue_layer(
    df,
    "group",
    "value",
    "Control",
    "Drug B",
    test="mannwhitneyu",
    categories=CATEGORIES,
    y=23,
)

theme.save(points + boxplot + ann_a + ann_b, "boxplot")
print("saved boxplot")
