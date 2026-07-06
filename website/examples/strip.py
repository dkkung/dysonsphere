import dysonsphere as ds
from vega_datasets import data

ds.theme()

cars = data.cars().dropna(subset=["Miles_per_Gallon"])
origins = ["USA", "Europe", "Japan"]

chart = ds.mark_strip(cars, "Origin", "Miles_per_Gallon", origins, yTitle="Miles per gallon")
