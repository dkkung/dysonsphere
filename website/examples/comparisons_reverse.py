from vega_datasets import data

import dysonsphere as ds

ds.theme()

cars = data.cars().dropna(subset=["Miles_per_Gallon"])
origins = ["Europe", "Japan", "USA"]
pairs = [("Europe", "Japan"), ("Europe", "USA")]

# reverse= hangs those brackets BELOW their groups with the ticks pointing up, and they
# stack downward. Useful when the space above the data is already spoken for.
chart = ds.mark_strip(
    cars,
    "Origin",
    "Miles_per_Gallon",
    origins,
    yTitle="Miles per gallon",
) + ds.stats.comparisons(
    cars,
    "Origin",
    "Miles_per_Gallon",
    pairs,
    reverse=pairs,
    labelStyle="asterisks",
    categories=origins,
)
