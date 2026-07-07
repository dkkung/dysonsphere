import dysonsphere as ds
from vega_datasets import data

ds.theme()

cars = ds.ensure_polars(data.cars()).drop_nulls(["Horsepower"])
origins = ["Europe", "Japan", "USA"]

# Asterisk labels (* / ** / *** / ns) and plain-line brackets.
chart = ds.mark_strip(
    cars, "Origin", "Horsepower", origins,
) + ds.add_comparisons(
    cars, "Origin", "Horsepower",
    [("USA", "Europe"), ("Europe", "Japan")],
    test="mannwhitneyu", correction="holm",
    labelStyle="asterisks", bracketStyle="line", categories=origins,
)
