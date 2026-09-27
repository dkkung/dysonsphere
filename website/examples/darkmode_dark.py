import altair as alt
from vega_datasets import data

import dysonsphere as ds

# darkmode=True inverts the ink; chartFill auto-resolves to black.
ds.theme(darkmode=True, transparent=False)

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
