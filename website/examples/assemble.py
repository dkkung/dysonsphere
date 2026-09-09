import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

ds.theme()

rng = np.random.default_rng(7)
DOSES = ["Vehicle", "1 uM", "10 uM"]
HOURS = [0, 6, 12, 24, 36, 48]
DECAY = {"Vehicle": 0.002, "1 uM": 0.010, "10 uM": 0.024}

course = pl.DataFrame(
    [
        {"dose": d, "hour": h, "viability": float(100 * np.exp(-DECAY[d] * h) + rng.normal(0, 2.5))}
        for d in DOSES
        for h in HOURS
        for _ in range(6)
    ]
)
endpoint = course.filter(pl.col("hour") == 48)

GENES = [f"Gene {i}" for i in range(1, 9)]
heat = pl.DataFrame(
    [
        {"gene": g, "sample": f"S{s}", "z": float(rng.normal(0, 1) + (1.5 if i < 4 and s < 3 else -0.5))}
        for i, g in enumerate(GENES)
        for s in range(1, 7)
    ]
)

expression = rng.uniform(2, 10, 60)
activity = pl.DataFrame({"expression": expression, "activity": 0.8 * expression + rng.normal(0, 1.2, 60) + 1})


def time_course():
    x = alt.X("hour:Q", title="Time (h)", scale=alt.Scale(domain=[0, 48]))
    color = alt.Color("dose:N", sort=DOSES, title=None, scale=alt.Scale(range=ds.palette("cat1", 3)))
    base = alt.Chart(course)
    return (
        ds.shade(positions=[(0, 12)], axis="x", opacity=0.5)
        + base.mark_line().encode(x=x, y=alt.Y("mean(viability):Q", title="Viability (%)"), color=color)
        + base.mark_errorbar(extent="stderr").encode(x=x, y=alt.Y("viability:Q", title=""), detail="dose:N")
        + base.mark_point(filled=True).encode(x=x, y=alt.Y("mean(viability):Q", title=""), color=color)
    )


def endpoint_quant():
    return ds.mark_strip(
        endpoint,
        "dose",
        "viability",
        DOSES,
        xTitle=None,
        yTitle="Viability at 48 h (%)",
        palette=ds.palette("cat3", 3),
    ) + ds.stats.comparisons(
        endpoint,
        "dose",
        "viability",
        reference="Vehicle",
        test="ttest_ind",
        correction="holm",
        categories=DOSES,
        labelStyle="asterisks",
    )


def expression_heatmap():
    return (
        alt.Chart(heat)
        .mark_rect()
        .encode(
            x=alt.X("sample:N", title=None),
            y=alt.Y("gene:N", title=None),
            color=alt.Color("z:Q", title="z", scale=alt.Scale(range=ds.palette("australis", 9))),
        )
    )


def activity_fit():
    points = (
        alt.Chart(activity)
        .mark_point(filled=True)
        .encode(
            x=alt.X("expression:Q", title="Expression"),
            y=alt.Y("activity:Q", title="Activity"),
            color=alt.Color("activity:Q", title=None, legend=None, scale=alt.Scale(range=ds.palette("div2", 9))),
        )
    )
    return points + ds.stats.correlation(activity, "expression", "activity", position="topLeft")


chart = ds.assemble(
    [
        [(time_course, 190, 110, "a"), (endpoint_quant, 90, 110, "b")],
        [(expression_heatmap, 130, 110, "c"), (activity_fit, 150, 110, "d")],
    ],
    spacing={"row": 40, "column": 10},
)
