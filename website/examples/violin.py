import dysonsphere as ds
from vega_datasets import data

ds.theme()

cars = data.cars().dropna(subset=["Horsepower"])
origins = ["USA", "Europe", "Japan"]

chart = ds.mark_violin(cars, "Origin", "Horsepower", origins, yTitle="Horsepower")
