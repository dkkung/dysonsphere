import altair as alt
import dysonsphere as ds
from vega_datasets import data

ds.theme()

cars = ds.ensure_polars(data.cars()).drop_nulls(["Miles_per_Gallon"])
origins = ["Europe", "Japan", "USA"]

box = alt.Chart(cars).mark_boxplot().encode(
    x=alt.X("Origin:N", sort=origins, title=None),
    # Pad the y domain so the corner label clears the stacked brackets below it.
    y=alt.Y("Miles_per_Gallon:Q", scale=alt.Scale(domain=[0, 75]), title="Miles per gallon"),
    color=alt.Color("Origin:N", legend=None),
)

chart = box + ds.add_comparisons(
    cars, "Origin", "Miles_per_Gallon",
    [("Europe", "USA"), ("Japan", "USA")],
    test="anova", categories=origins, yStart=50,
)
