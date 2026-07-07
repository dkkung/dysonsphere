import altair as alt
import dysonsphere as ds
from vega_datasets import data

ds.theme()

cars = ds.ensure_polars(data.cars()).drop_nulls(["Miles_per_Gallon", "Horsepower"])

scatter = alt.Chart(cars).mark_point().encode(
    x=alt.X("Horsepower:Q"),
    y=alt.Y("Miles_per_Gallon:Q", title="Miles per gallon"),
)

# axis="x" draws vertical rules; pass a list for several at once.
chart = scatter + ds.add_rule(150, axis="x", label="150 hp", strokeDash=True)
