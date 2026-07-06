import dysonsphere as ds
from vega_datasets import data

ds.theme()

cars = data.cars().dropna(subset=["Horsepower"])
origins = ["USA", "Europe", "Japan"]

# Scientific notation for small p-values, 2 significant figures.
chart = ds.mark_strip(
    cars, "Origin", "Horsepower", origins,
) + ds.add_comparisons(
    cars, "Origin", "Horsepower",
    [("USA", "Japan")],
    test="ttest_ind", notation="scientific", sigFigs=2, categories=origins,
)
