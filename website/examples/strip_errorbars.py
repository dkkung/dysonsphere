import dysonsphere as ds
from vega_datasets import data

ds.theme()

cars = ds.ensure_polars(data.cars()).drop_nulls(["Miles_per_Gallon"])
origins = ["USA", "Europe", "Japan"]

# Mean +/- error bars overlaid on the points; errorbarExtent is "sem" (default)
# for the standard error of the mean, or "sd" for the standard deviation.
chart = ds.mark_strip(
    cars, "Origin", "Miles_per_Gallon", origins,
    errorbars=True, errorbarExtent="sd", yTitle="Miles per gallon",
)
