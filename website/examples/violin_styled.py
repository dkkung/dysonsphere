import dysonsphere as ds
from vega_datasets import data

ds.theme()

cars = ds.ensure_polars(data.cars()).drop_nulls(["Horsepower"])
origins = ["USA", "Europe", "Japan"]

# Custom palette, no outline, and tails trimmed to the data extremes.
chart = ds.mark_violin(
    cars, "Origin", "Horsepower", origins,
    palette=ds.palette("dusk", 3), fillOpacity=0.85,
    stroke=None, trim=True,
    yTitle="Horsepower",
)
