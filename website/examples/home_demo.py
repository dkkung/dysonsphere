import altair as alt
import dysonsphere as ds
from vega_datasets import data

ds.theme(chartWidth=140)

cars = ds.ensure_polars(data.cars()).drop_nulls(["Miles_per_Gallon"])
origins = ["Europe", "Japan", "USA"]

# Collision-avoiding x-offsets - a beeswarm, no force simulation.
cars = ds.add_beeswarm(cars, "Miles_per_Gallon", groupBy=["Origin"])

swarm = (
    alt.Chart(cars)
    .mark_circle()
    .encode(
        x=alt.X("Origin:N", title=None),
        y=alt.Y("Miles_per_Gallon:Q", title="Miles per gallon"),
        xOffset=alt.XOffset("beeswarm_x:Q"),
    )
)

# A condition table instead of a legend: +/- rows under each category.
chart = ds.add_multilabel(
    swarm,
    groups={"Domestic": [False, False, True], "Tariff exempt": [True, True, False]},
    categories=origins,
    categoryLabel=True,
)
