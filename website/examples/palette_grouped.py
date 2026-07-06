import altair as alt
import polars as pl

import dysonsphere as ds

ds.theme(chartWidth=170, xLabelAngle=-45)

# Paired data: each treatment measured at two timepoints. categorical(members=2) returns a
# hue-major palette - each consecutive pair of categories is one hue climbing in lightness, so
# related bars read as a group. (members=1, the default, gives the tier-major flat palette where
# adjacent categories differ in hue - for UNRELATED groups.)
df = pl.DataFrame(
    {
        "condition": ["A pre", "A post", "B pre", "B post",
                      "C pre", "C post", "D pre", "D post"],
        "response": [4.2, 7.8, 3.9, 6.1, 5.0, 9.2, 4.4, 5.5],
    }
)

chart = (
    alt.Chart(df)
    .mark_bar()
    .encode(
        x=alt.X("condition:N", sort=None, title=None),
        y=alt.Y("response:Q", title="Response (AU)"),
        color=alt.Color(
            "condition:N",
            sort=None,
            scale=alt.Scale(range=ds.categorical(members=2)),
            legend=None,
        ),
    )
)
