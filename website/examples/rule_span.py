import altair as alt
import polars as pl
from vega_datasets import data

import dysonsphere as ds

ds.theme()

cars = ds.ensure_polars(data.cars()).drop_nulls(["Miles_per_Gallon", "Cylinders"])
cats = ["3", "4", "5", "6", "8"]

by_cyl = (
    cars.with_columns(pl.col("Cylinders").cast(pl.Utf8).alias("cyl"))
    .group_by("cyl")
    .agg(pl.col("Miles_per_Gallon").mean().alias("mpg"))
)
bars = alt.Chart(by_cyl).mark_bar().encode(
    x=alt.X("cyl:N", sort=cats, title="Cylinders"),
    y=alt.Y("mpg:Q", title="Miles per gallon"),
)

# The 4-cylinder benchmark, sliced with span= across just the 6- and 8-cylinder
# bars it is being compared against (category-name bounds, resolved like add_shade).
four_cyl = float(by_cyl.filter(pl.col("cyl") == "4")["mpg"].item())
chart = bars + ds.add_rule(four_cyl, span=("6", "8"), categories=cats, label="4-cyl avg")
