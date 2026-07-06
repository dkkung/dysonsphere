import polars as pl
import altair as alt
import dysonsphere as ds

ds.theme()

# palette() slices/samples any of the 300+ palettes: n evenly spaced stops,
# or start/end/step/reverse for full control.
df = pl.DataFrame({"dose": ["0", "1", "10", "100"], "response": [8.0, 21.0, 55.0, 89.0]})

chart = (
    alt.Chart(df)
    .mark_bar()
    .encode(
        x=alt.X("dose:N", sort=None, title="Dose (nM)"),
        y=alt.Y("response:Q", title="Response (%)"),
        color=alt.Color(
            "dose:N", legend=None, sort=None,
            scale=alt.Scale(range=ds.palette("ember", 4)),
        ),
    )
)
