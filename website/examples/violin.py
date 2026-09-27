from vega_datasets import data

import dysonsphere as ds

ds.theme()

cars = data.cars().dropna(subset=["Horsepower"])
origins = ["USA", "Europe", "Japan"]

chart = ds.mark_violin(cars, "Origin", "Horsepower", origins, yTitle="Horsepower")
