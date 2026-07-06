import altair as alt
import dysonsphere as ds
from vega_datasets import data

ds.theme()

cars = ds.ensure_polars(data.cars()).drop_nulls(["Miles_per_Gallon"])

# add_beeswarm() computes collision-avoiding x-offsets per group.
cars = ds.add_beeswarm(cars, "Miles_per_Gallon", groupBy=["Origin"])

chart = (
    alt.Chart(cars)
    .mark_circle()
    .encode(
        x=alt.X("Origin:N", title=None),
        y=alt.Y("Miles_per_Gallon:Q", title="Miles per gallon"),
        xOffset=alt.XOffset("beeswarm_x:Q", scale=None),
    )
)
