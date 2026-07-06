import altair as alt
import dysonsphere as ds
from vega_datasets import data

ds.theme()

cars = data.cars().dropna(subset=["Miles_per_Gallon", "Horsepower"])

scatter = alt.Chart(cars).mark_point().encode(
    x=alt.X("Horsepower:Q", title="Horsepower"),
    y=alt.Y("Miles_per_Gallon:Q", title="Miles per gallon"),
)

# Compose the readout from independent parts: coefficient="both" shows r and r-squared,
# includePvalue adds P. The default (coefficient="r") shows just r = ...; verbose=True is a
# shortcut that turns all of them on plus the fit equation.
chart = scatter + ds.add_correlation(
    cars, "Horsepower", "Miles_per_Gallon",
    coefficient="both", includePvalue=True,
)
