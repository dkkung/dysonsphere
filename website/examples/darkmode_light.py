import altair as alt
from vega_datasets import data

import dysonsphere as ds

# transparent=False fills the chart with its chartFill background (auto: white).
ds.theme(transparent=False)

cars = data.cars().dropna(subset=["Miles_per_Gallon", "Horsepower"])

chart = (
    alt.Chart(cars)
    .mark_point()
    .encode(
        x=alt.X("Horsepower:Q"),
        y=alt.Y("Miles_per_Gallon:Q", title="Miles per gallon"),
        color=alt.Color("Origin:N"),
    )
)
