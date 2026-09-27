import altair as alt
from vega_datasets import data

import dysonsphere as ds

# The verbose omnibus label is long - widen the canvas so it fits.
ds.theme(width=200)

cars = data.cars().dropna(subset=["Miles_per_Gallon"])
origins = ["Europe", "Japan", "USA"]

box = (
    alt.Chart(cars)
    .mark_boxplot()
    .encode(
        x=alt.X("Origin:N", sort=origins, title=None),
        y=alt.Y("Miles_per_Gallon:Q", title="Miles per gallon"),
        color=alt.Color("Origin:N"),
    )
)

chart = box + ds.stats.comparisons(
    cars,
    "Origin",
    "Miles_per_Gallon",
    [("Europe", "USA"), ("Japan", "USA")],
    test="kruskal",
    omnibusVerbose=True,
    categories=origins,
)
