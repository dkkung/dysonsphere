from vega_datasets import data

import dysonsphere as ds

ds.theme()

cars = data.cars().dropna(subset=["Acceleration"])
origins = ["Europe", "Japan", "USA"]

# bracketStyle="drop" reaches each end tick down toward the group it sits over. It suits a
# few brackets over groups of comparable height - a tall outlying group lifts the whole
# stack, and every tick below it gets long.
chart = ds.mark_strip(
    cars,
    "Origin",
    "Acceleration",
    origins,
    yTitle="Acceleration (s)",
) + ds.stats.comparisons(
    cars,
    "Origin",
    "Acceleration",
    [("Europe", "Japan"), ("Europe", "USA")],
    bracketStyle="drop",
    labelStyle="asterisks",
    categories=origins,
)
