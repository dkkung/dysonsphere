from vega_datasets import data

import dysonsphere as ds

ds.theme()

cars = data.cars().dropna(subset=["Horsepower"])
origins = ["Europe", "Japan", "USA"]

# Left alone each bracket hugs the data it spans, so they sit at uneven heights when the
# groups do. yStart + yStep overrides that with an even ladder in data units.
chart = ds.mark_strip(
    cars,
    "Origin",
    "Horsepower",
    origins,
) + ds.stats.comparisons(
    cars,
    "Origin",
    "Horsepower",
    pairs="all",
    categories=origins,
    labelStyle="asterisks",
    yStart=250.0,
    yStep=28.0,
)
