import dysonsphere as ds
from vega_datasets import data

ds.theme()

cars = data.cars().dropna(subset=["Miles_per_Gallon"])
origins = ["USA", "Europe", "Japan"]

# Omnibus Kruskal-Wallis with Dunn post-hoc brackets; the corner label reports
# the omnibus result (verbose adds statistic, df, and effect size).
chart = ds.mark_strip(
    cars, "Origin", "Miles_per_Gallon", origins, yTitle="Miles per gallon",
) + ds.add_comparisons(
    cars, "Origin", "Miles_per_Gallon",
    [("USA", "Europe"), ("USA", "Japan")],
    test="kruskal", omnibusVerbose=True, categories=origins,
)
