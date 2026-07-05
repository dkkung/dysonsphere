import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

# Boxplot + beeswarm figure (skewed data: most points low, long tail), with mean "+" markers,
# sample-size x labels, and significance brackets. Group labels are ordered so their lexical
# order matches the display order - add_comparisons brackets don't propagate the chart's `sort`,
# so lexical-order labels keep the bands aligned with the brackets.
rng = np.random.default_rng(7)
GROUPS = ["(181)", "(206)", "(218)", "(230)", "(303)"]
SIZES = [181, 206, 218, 230, 303]
SCALES = [4, 30, 60, 150, 260]  # exponential scale per group - increasing, skewed

rows = []
for g, s, sc in zip(GROUPS, SIZES, SCALES):
    for v in rng.exponential(sc, s):
        rows.append({"g": g, "v": float(min(v, 1000))})
df = pl.DataFrame(rows)

ds.theme()
df = ds.add_beeswarm(df, yCol="v", groupBy=["g"])

x = alt.X("g:N", sort=GROUPS, title=None)
y = alt.Y("v:Q", title=None, scale=alt.Scale(domain=[0, 1000]))

box = (
    alt.Chart(df)
    .mark_boxplot()
    .encode(x=x, y=y, color=alt.Color("g:N", scale=alt.Scale(range=ds.categorical(members=1))))
)
pts = alt.Chart(df).mark_circle().encode(x=x, y=y, xOffset=alt.XOffset("beeswarm_x:Q"))

means = df.group_by("g").agg(pl.col("v").mean().alias("m"))
mean_marks = alt.Chart(means).mark_point(shape="cross", color="black", size=10, strokeWidth=1).encode(x=x, y="m:Q")

brackets = ds.add_comparisons(
    df,
    xCol="g",
    yCol="v",
    pairs=[("(206)", "(218)"), ("(206)", "(230)"), ("(206)", "(303)")],
    yStart=800,
    test="mannwhitneyu",
    notation="scientific",
    sigFigs=2,
)

# chart = pts + box + mean_marks + brackets
chart = pts + box + brackets
ds.save(chart, "beeswarm", format=["png", "svg"])
print("saved beeswarm")
