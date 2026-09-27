import altair as alt
import polars as pl
from vega_datasets import data

import dysonsphere as ds

ds.theme(xLabelAngle=-45, width=124)

barley = pl.from_pandas(data.barley())
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
