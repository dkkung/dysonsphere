from vega_datasets import data

import dysonsphere as ds

ds.theme()

cars = data.cars().dropna(subset=["Miles_per_Gallon"])
origins = ["USA", "Europe", "Japan"]

strip = ds.mark_strip(cars, "Origin", "Miles_per_Gallon", origins, yTitle="Miles per gallon")

# Positions mode: shade an explicit y-range (e.g. a reference interval).
chart = ds.shade(palette=[ds.palettes.colors["blues"][0]], positions=[(20.0, 30.0)], axis="y", opacity=0.6) + strip
