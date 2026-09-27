from vega_datasets import data

import dysonsphere as ds

ds.theme()

cars = data.cars().dropna(subset=["Horsepower"])
origins = ["USA", "Europe", "Japan"]

# Custom palette, no outline, and tails trimmed to the data extremes.
chart = ds.mark_violin(
    cars,
    "Origin",
    "Horsepower",
    origins,
    palette=ds.palette("dusk", 3),
    fillOpacity=0.85,
    stroke=None,
    trim=True,
    yTitle="Horsepower",
)
