import altair as alt
from vega_datasets import data

import dysonsphere as ds

ds.theme()

cars = data.cars().dropna(subset=["Miles_per_Gallon"])
origins = ["Europe", "Japan", "USA"]

box = (
    alt.Chart(cars)
    .mark_boxplot()
    .encode(
        x=alt.X("Origin:N", sort=origins, title=None),
        y=alt.Y("Miles_per_Gallon:Q", title="Miles per gallon"),
        color=alt.Color("Origin:N", legend=None),
    )
)

chart = box + ds.stats.comparisons(
    cars,
    "Origin",
    "Miles_per_Gallon",
    [("Europe", "USA"), ("Japan", "USA")],
    test="anova",
    categories=origins,
)
