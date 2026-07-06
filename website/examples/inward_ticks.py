import altair as alt
import dysonsphere as ds
from vega_datasets import data

# inwardTicks=True points tick marks into the plot (physics-journal style);
# it also defaults the frame to closed.
ds.theme(inwardTicks=True)

cars = data.cars().dropna(subset=["Miles_per_Gallon", "Horsepower"])

chart = (
    alt.Chart(cars)
    .mark_point()
    .encode(
        x=alt.X("Horsepower:Q"),
        y=alt.Y("Miles_per_Gallon:Q", title="Miles per gallon"),
    )
)
