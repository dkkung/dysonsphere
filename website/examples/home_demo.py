import altair as alt
import dysonsphere as ds
from vega_datasets import data

ds.theme(palette="blues2", chartWidth=140)

cars = ds.ensure_polars(data.cars()).drop_nulls(["Horsepower", "Weight_in_lbs"])

scatter = (
    alt.Chart(cars)
    .mark_point()
    .encode(
        x=alt.X("Weight_in_lbs:Q", title="Weight (lbs)"),
        y=alt.Y("Horsepower:Q", title="Horsepower"),
        color=alt.Color("Horsepower:Q", legend=None),
    )
)

chart = scatter + ds.add_correlation(cars, "Weight_in_lbs", "Horsepower")
