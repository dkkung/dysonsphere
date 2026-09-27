"""Coordinate a highlighted bar and label in a deterministic synthetic benchmark."""

import altair as alt
import polars as pl

import dysonsphere as ds

ds.theme(width=180, height=120)

data = pl.DataFrame(
    {
        "pipeline": ["Baseline", "Cached", "Vectorized", "Optimized"],
        "throughput": [18, 27, 34, 46],
        "status": ["reference", "reference", "reference", "selected"],
    }
)
x = alt.X("pipeline:N", title=None, sort=data["pipeline"].to_list())
y = alt.Y("throughput:Q", title="Throughput (samples/s)", scale=alt.Scale(domain=[0, 52]))
context = alt.Chart(data.filter(pl.col("status") == "reference")).mark_bar().encode(x=x, y=y)
selected = (
    alt.Chart(data.filter(pl.col("status") == "selected"))
    .mark_bar(color=ds.palettes.accents["orange"])
    .encode(x=x, y=y)
)
label = (
    alt.Chart(data.filter(pl.col("status") == "selected"))
    .mark_text(dy=-5, color=ds.palettes.accents["orange"], text="best")
    .encode(x=x, y=y)
)
chart = context + selected + label
