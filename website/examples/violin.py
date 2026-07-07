import dysonsphere as ds
from vega_datasets import data

ds.theme()

cars = ds.ensure_polars(data.cars()).drop_nulls(["Horsepower"])
origins = ["USA", "Europe", "Japan"]

chart = ds.mark_violin(cars, "Origin", "Horsepower", origins, yTitle="Horsepower")
