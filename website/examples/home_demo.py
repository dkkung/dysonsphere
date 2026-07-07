import dysonsphere as ds
from vega_datasets import data

ds.theme(palette="blues2", chartWidth=140)

cars = data.cars().dropna(subset=["Miles_per_Gallon"])
origins = ["Europe", "Japan", "USA"]

# A strip plot (jittered points + median + SEM bars) with significance brackets.
chart = ds.mark_strip(
    cars, "Origin", "Miles_per_Gallon", origins,
    yTitle="Miles per gallon",
) + ds.add_comparisons(
    cars, "Origin", "Miles_per_Gallon",
    [("Europe", "USA"), ("Japan", "USA")],
    test="mannwhitneyu", correction="holm", categories=origins,
)
