import polars as pl
import altair as alt
import dysonsphere as ds

ds.theme(palette="blues")

df = pl.DataFrame({"group": ["A", "B", "C", "D"], "value": [3.0, 5.0, 2.0, 6.0]})

chart = (
    alt.Chart(df)
    .mark_bar()
    .encode(x="group:N", y="value:Q", color=alt.Color("group:N", legend=None))
)
