import altair as alt
import dysonsphere as ds
from vega_datasets import data

ds.theme(palette="blues")

barley = data.barley()

chart = (
    alt.Chart(barley)
    .mark_bar()
    .encode(
        x=alt.X("variety:N", sort="-y", title="Variety"),
        y=alt.Y("mean(yield):Q", title="Mean yield (bu/acre)"),
        color=alt.Color("variety:N", legend=None),
    )
)
