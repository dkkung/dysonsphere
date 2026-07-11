import altair as alt
import dysonsphere as ds
from vega_datasets import data

ds.theme(chartWidth=124)

cars = ds.ensure_polars(data.cars()).drop_nulls(["Miles_per_Gallon", "Horsepower"])

chart = (
    alt.Chart(cars)
    .mark_point()
    .encode(
        x=alt.X("Horsepower:Q", title="Horsepower"),
        y=alt.Y("Miles_per_Gallon:Q", title="Miles per gallon"),
        color=alt.Color("Miles_per_Gallon:Q", legend=alt.Legend(title="MPG", titleOrient="top")),
    )
)
