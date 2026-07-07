import polars as pl
import dysonsphere as ds
from vega_datasets import data

ds.theme()

cars = ds.ensure_polars(data.cars()).drop_nulls(["Acceleration"])
# Subsample to 50 cars per origin so the swarm fits its band.
cars = cars.filter(pl.int_range(pl.len()).shuffle(seed=7).over("Origin") < 50)
origins = ["USA", "Europe", "Japan"]

# scatter="beeswarm" packs points analytically instead of random jitter.
chart = ds.mark_strip(
    cars, "Origin", "Acceleration", origins,
    scatter="beeswarm", yTitle="0-60 mph time (s)",
)
