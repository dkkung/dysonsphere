import altair as alt
from vega_datasets import data

import dysonsphere as ds

ds.theme()

cars = data.cars().dropna(subset=["Miles_per_Gallon", "Horsepower"])

scatter = (
    alt.Chart(cars)
    .mark_point()
    .encode(
        x=alt.X("Horsepower:Q"),
        y=alt.Y("Miles_per_Gallon:Q", title="Miles per gallon"),
    )
)

# An x coordinate draws a vertical rule; pass a list for several at once.
chart = scatter + ds.rule(x=150, label="150 hp", strokeDash=True)
