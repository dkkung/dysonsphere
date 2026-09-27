from vega_datasets import data

import dysonsphere as ds

ds.theme()

cars = data.cars().dropna(subset=["Horsepower"])
origins = ["Europe", "Japan", "USA"]

# pairs="all" expands to every unique pair, so `correction` covers the real family.
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
    test="mannwhitneyu",
    correction="holm",
    categories=origins,
    labelStyle="asterisks",
)
