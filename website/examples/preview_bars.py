import altair as alt
import polars as pl
import dysonsphere as ds
from vega_datasets import data

ds.theme(xLabelAngle=-45, chartWidth=124)

barley = ds.ensure_polars(data.barley())
means = barley.group_by("site").agg(pl.col("yield").mean()).sort("yield", descending=True)
sites = means["site"].to_list()

chart = (
    alt.Chart(barley)
    .mark_bar()
    .encode(
        x=alt.X("site:N", sort=sites, title=None),
        y=alt.Y("mean(yield):Q", title="Mean yield (bu/acre)"),
        color=alt.Color("site:N", sort=sites, scale=alt.Scale(domain=sites), legend=None),
    )
)
