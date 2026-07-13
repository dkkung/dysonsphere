import altair as alt
import dysonsphere as ds
from vega_datasets import data

ds.theme()

cars = ds.ensure_polars(data.cars()).drop_nulls(["Miles_per_Gallon", "Horsepower"])

scatter = alt.Chart(cars).mark_point().encode(
    x=alt.X("Horsepower:Q"),
    y=alt.Y("Miles_per_Gallon:Q", title="Miles per gallon"),
)

# ci=True shades a 95% confidence band around the fit (how tightly the line is pinned down).
# Pass a level like ci=0.99, or interval="prediction" for the wider single-observation band.
chart = scatter + ds.add_correlation(cars, "Horsepower", "Miles_per_Gallon", ci=True)
