import altair as alt
from vega_datasets import data

import dysonsphere as ds

# closed=True draws a full frame around the plot (all four spines).
ds.theme(closed=True)

cars = data.cars().dropna(subset=["Miles_per_Gallon", "Horsepower"])

chart = (
    alt.Chart(cars)
    .mark_point()
    .encode(
        x=alt.X("Horsepower:Q"),
        y=alt.Y("Miles_per_Gallon:Q", title="Miles per gallon"),
    )
)
