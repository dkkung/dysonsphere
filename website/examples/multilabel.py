import dysonsphere as ds
from vega_datasets import data

ds.theme()

cars = data.cars().dropna(subset=["Miles_per_Gallon"])
origins = ["USA", "Europe", "Japan"]

strip = ds.mark_strip(cars, "Origin", "Miles_per_Gallon", origins, yTitle="Miles per gallon")

# A condition table below the chart: +/- rows aligned to each category.
chart = ds.add_multilabel(
    strip,
    groups={"Domestic": [True, False, False], "High volume": [True, True, False]},
    categories=origins,
)
