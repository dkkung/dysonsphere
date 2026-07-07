import dysonsphere as ds
from vega_datasets import data

ds.theme()

cars = data.cars().dropna(subset=["Horsepower"])
origins = ["Europe", "Japan", "USA"]

# bracketStyle and notation accept per-pair dicts (keys matched regardless of
# order); the special "test" notation key styles the omnibus/test label.
chart = ds.mark_strip(
    cars, "Origin", "Horsepower", origins,
) + ds.add_comparisons(
    cars, "Origin", "Horsepower",
    [("USA", "Europe"), ("USA", "Japan")],
    test="mannwhitneyu", correction="holm",
    bracketStyle={("USA", "Japan"): "line"},
    notation={("USA", "Japan"): "scientific"},
    categories=origins,
)
