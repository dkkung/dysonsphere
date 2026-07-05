import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

# Four concatenated boxplot + beeswarm panels with deliberately different data ranges, sample
# sizes, group counts, and chart sizes - a stress test for the auto bracket spacing (yPad/yStep
# scale with the per-panel y_range and chartHeight). Built on the beeswarm.py model, with varied
# labelStyle / bracketStyle. The y domain is left to auto-fit so the brackets always have headroom.
rng = np.random.default_rng(11)

# title, y-title, groups, exponential scales, sample sizes, value cap, width, height, labelStyle, bracketStyle
PANELS = [
    ("Assay 1", "Signal (AU)", ["A", "B", "C"], [0.5, 1.2, 2.0], [40, 45, 38], 10, 150, 110, "asterisks", "bracket"),
    ("Assay 2", "Counts", ["A", "B", "C", "D"], [6, 14, 22, 30], [80, 95, 70, 60], 100, 190, 150, "p", "line"),
    ("Assay 3", "Gaps (nt)", ["A", "B", "C"], [60, 150, 260], [181, 206, 230], 1000, 230, 240, "asterisks", "line"),
    (
        "Assay 4",
        "Delta (mV)",
        ["A", "B", "C", "D", "E"],
        [3, 5, 8, 12, 16],
        [50, 55, 48, 52, 60],
        50,
        210,
        130,
        "p",
        "bracket",
    ),  # noqa: E501
]

panels = []
for title, ytitle, groups, scales, sizes, ycap, w, h, label_style, bracket_style in PANELS:
    rows = [
        {"g": g, "v": float(min(v, ycap))} for g, sc, n in zip(groups, scales, sizes) for v in rng.exponential(sc, n)
    ]
    df = pl.DataFrame(rows)

    ds.theme(chartWidth=w, chartHeight=h, markSize=3)
    df = ds.add_beeswarm(df, yCol="v", groupBy=["g"])

    x = alt.X("g:N", sort=groups, title=None)
    y = alt.Y("v:Q", title=ytitle)

    box = alt.Chart(df).mark_boxplot(size=9, outliers=False).encode(x=x, y=y)  # plain band = on the tick
    pts = alt.Chart(df).mark_circle(size=0.5).encode(x=x, y=y, xOffset=alt.XOffset("beeswarm_x:Q"))

    brackets = ds.add_comparisons(
        df,
        xCol="g",
        yCol="v",
        pairs=[(groups[0], groups[-1]), (groups[0], groups[1])],
        test="mannwhitneyu",
        labelStyle=label_style,
        bracketStyle=bracket_style,
    )

    panels.append((pts + box + brackets).properties(width=w, height=h, title=title))

# Independent xOffset per panel: hconcat otherwise shares the xOffset domain across panels, which
# distorts the widest panel's swarm (here A3, ~10px off its box) - the actual visible offset here.
chart = alt.hconcat(*panels).resolve_scale(xOffset="independent")
ds.save(chart, "beeswarm_panels", format="png")
print("saved beeswarm_panels")
