"""
Double y-axis example — tests that dysonsphere's theme doesn't break
independent y-scale resolution in a layered Altair chart.

Left axis:  temperature (°C), line mark
Right axis: precipitation (mm), bar mark

Usage (from project root):
    uv run python scripts/plots/double-y.py
"""

import altair as alt
import polars as pl

import dysonsphere as ds

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

temp = [2.1, 3.4, 7.2, 11.8, 16.3, 19.8, 22.1, 21.5, 17.4, 12.0, 6.8, 3.2]
precip = [52, 40, 45, 48, 55, 60, 65, 62, 58, 70, 68, 55]

df = pl.DataFrame({"month": MONTHS, "temp": temp, "precip": precip})

ds.theme(palette="blues2", chartWidth=200, chartHeight=100)
palette = ds.palette("blues2", n=12)

base = alt.Chart(df).encode(alt.X("month:N", sort=MONTHS, title=None))

bars = base.mark_bar(opacity=0.4, color=palette[3]).encode(
    alt.Y("precip:Q").axis(title="Precipitation (mm)", orient="right"),
)

line = base.mark_line(color=palette[9], point=True).encode(
    alt.Y("temp:Q").axis(title="Temperature (°C)"),
)

chart = alt.layer(bars, line).resolve_scale(y="independent")

ds.save(chart, "double-y")
print("saved double-y")
