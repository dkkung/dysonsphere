import dysonsphere as ds
from vega_datasets import data

ds.theme()

cars = ds.ensure_polars(data.cars()).drop_nulls(["Miles_per_Gallon"])
origins = ["USA", "Europe", "Japan"]

chart = ds.mark_strip(cars, "Origin", "Miles_per_Gallon", origins, yTitle="Miles per gallon")
