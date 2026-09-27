import altair as alt
from vega_datasets import data

import dysonsphere as ds

# tickDirection="in" points tick marks into the plot (physics-journal style);
# it also defaults the frame to closed.
ds.theme(tickDirection="in")

cars = data.cars().dropna(subset=["Miles_per_Gallon", "Horsepower"])

chart = (
    alt.Chart(cars)
    .mark_point()
    .encode(
        x=alt.X("Horsepower:Q"),
        y=alt.Y("Miles_per_Gallon:Q", title="Miles per gallon"),
    )
)
