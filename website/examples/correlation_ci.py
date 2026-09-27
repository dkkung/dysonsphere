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

# ci=True shades a 95% confidence band around the fit (how tightly the line is pinned down).
# Pass a level like ci=0.99, or interval="prediction" for the wider single-observation band.
chart = scatter + ds.stats.correlation(cars, "Horsepower", "Miles_per_Gallon", ci=True)
