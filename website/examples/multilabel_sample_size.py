import dysonsphere as ds
from vega_datasets import data

ds.theme()

cars = data.cars().dropna(subset=["Miles_per_Gallon"])
origins = ["USA", "Europe", "Japan"]

strip = ds.mark_strip(cars, "Origin", "Miles_per_Gallon", origins, yTitle="Miles per gallon")

# Add per-category sample sizes and the category labels as annotation rows.
chart = ds.add_multilabel(
    strip,
    categories=origins,
    showSampleSize=True, df=cars, xCol="Origin",
    categoryLabel=True,
)
