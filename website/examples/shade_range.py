import dysonsphere as ds
from vega_datasets import data

ds.theme()

cars = data.cars().dropna(subset=["Miles_per_Gallon"])
origins = ["USA", "Europe", "Japan"]

strip = ds.mark_strip(cars, "Origin", "Miles_per_Gallon", origins, yTitle="Miles per gallon")

# Positions mode: shade an explicit y-range (e.g. a reference interval).
chart = ds.add_shade(positions=[(20.0, 30.0)], axis="y", opacity=0.6) + strip
