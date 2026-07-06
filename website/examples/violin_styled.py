import dysonsphere as ds
from vega_datasets import data

ds.theme()

cars = data.cars().dropna(subset=["Horsepower"])
origins = ["USA", "Europe", "Japan"]

# Style the silhouette and the embedded boxplot independently.
chart = ds.mark_violin(
    cars, "Origin", "Horsepower", origins,
    palette=ds.palette("dusk", 3), fillOpacity=0.85,
    boxplotColor="black", medianColor="white",
    yTitle="Horsepower",
)
