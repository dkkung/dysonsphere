import altair as alt
from vega_datasets import data

import dysonsphere as ds

ds.theme(width=124)

cars = data.cars().dropna(subset=["Miles_per_Gallon", "Horsepower"])

chart = (
    alt.Chart(cars)
    .mark_point()
    .encode(
        x=alt.X("Horsepower:Q", title="Horsepower"),
        y=alt.Y("Miles_per_Gallon:Q", title="Miles per gallon"),
        color=alt.Color("Miles_per_Gallon:Q", title="MPG"),
    )
)
