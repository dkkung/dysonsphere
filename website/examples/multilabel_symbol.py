import dysonsphere as ds
from vega_datasets import data

ds.theme()

cars = ds.ensure_polars(data.cars()).drop_nulls(["Miles_per_Gallon"])
origins = ["USA", "Europe", "Japan"]

strip = ds.mark_strip(cars, "Origin", "Miles_per_Gallon", origins, yTitle="Miles per gallon")

# Symbol-style rows (filled / open dots) with grouped spans bracketing categories.
chart = ds.add_multilabel(
    strip,
    groups={"Turbocharged": [True, False, True], "Fuel injected": [True, True, False]},
    categories=origins,
    style="symbol",
    span=[{"Domestic": ["USA"]}, {"Imported": ["Europe", "Japan"]}],
    spanBracketStyle="bracket",
)
