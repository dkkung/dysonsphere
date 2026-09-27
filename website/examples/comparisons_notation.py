from vega_datasets import data

import dysonsphere as ds

ds.theme()

cars = data.cars().dropna(subset=["Horsepower"])
origins = ["Europe", "Japan", "USA"]

# Scientific notation for small p-values, 2 significant figures.
chart = ds.mark_strip(
    cars,
    "Origin",
    "Horsepower",
    origins,
) + ds.stats.comparisons(
    cars,
    "Origin",
    "Horsepower",
    [("USA", "Japan")],
    test="ttest_ind",
    notation="scientific",
    sigFigs=2,
    categories=origins,
)
