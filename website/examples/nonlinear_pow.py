import altair as alt
import dysonsphere as ds
from vega_datasets import data

ds.theme()

cars = ds.ensure_polars(data.cars()).drop_nulls(["Horsepower", "Weight_in_lbs"])

majors = [0, 1000, 2000, 3000, 4000, 5000]
line = alt.Chart(cars).mark_point().encode(
    x=alt.X("Horsepower:Q", title="Horsepower"),
    y=alt.Y(
        "Weight_in_lbs:Q",
        scale=alt.Scale(type="pow", exponent=0.5),
        axis=alt.Axis(values=majors),
        title="Weight (lbs)",
    ),
)

# Minor ticks for a power/sqrt axis, evenly spaced in transformed space.
chart = ds.add_pow_ticks(line, cars, "Weight_in_lbs", axis="y", exponent=0.5, majorValues=majors)
