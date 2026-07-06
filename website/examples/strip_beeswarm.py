import dysonsphere as ds
from vega_datasets import data

ds.theme()

cars = data.cars().dropna(subset=["Miles_per_Gallon"])
origins = ["USA", "Europe", "Japan"]

# scatter="beeswarm" packs points analytically instead of random jitter.
chart = ds.mark_strip(
    cars, "Origin", "Miles_per_Gallon", origins,
    scatter="beeswarm", yTitle="Miles per gallon",
)
