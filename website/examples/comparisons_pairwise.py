import dysonsphere as ds
from vega_datasets import data

ds.theme()

cars = data.cars().dropna(subset=["Horsepower"])
origins = ["USA", "Europe", "Japan"]

# Pairwise Mann-Whitney U with Holm correction; brackets stack automatically.
chart = ds.mark_strip(
    cars, "Origin", "Horsepower", origins,
) + ds.add_comparisons(
    cars, "Origin", "Horsepower",
    [("USA", "Europe"), ("Europe", "Japan"), ("USA", "Japan")],
    test="mannwhitneyu", correction="holm", categories=origins,
)
