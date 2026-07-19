"""Moore's law - the exponential rise of transistor counts.

In 1965 Gordon Moore observed that the number of transistors on a chip was doubling roughly every
two years. Six decades on it has held across more than seven orders of magnitude. Transistor counts
of landmark microprocessors on a log axis; the in-browser log-linear fit recovers the doubling time.
"""

import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

ds.theme(chartWidth=230, chartHeight=175)

# year of introduction, transistor count - landmark microprocessors
DATA = [
    (1971, 2300), (1974, 6000), (1978, 29000), (1982, 134000), (1985, 275000),
    (1989, 1_180_000), (1993, 3_100_000), (1997, 7_500_000), (2000, 42_000_000),
    (2006, 291_000_000), (2010, 1_170_000_000), (2012, 3_100_000_000),
    (2017, 19_200_000_000), (2020, 39_000_000_000),
]
df = pl.DataFrame(DATA, schema=["year", "transistors"], orient="row").with_columns(pl.col("transistors").log10().alias("log_t"))

slope = float(np.polyfit(df["year"].to_numpy(), df["log_t"].to_numpy(), 1)[0])
doubling = np.log10(2.0) / slope

sup = "['⁰','¹','²','³','⁴','⁵','⁶','⁷','⁸','⁹','¹⁰']"
yaxis = alt.Axis(values=[4, 6, 8, 10], labelExpr=f"'10' + {sup}[round(datum.value)]", title="Transistors per chip")
xenc = alt.X("year:Q", title="Year", axis=alt.Axis(format="d"), scale=alt.Scale(domain=[1968, 2023], nice=False))

scatter = alt.Chart(df).mark_point(filled=True, size=26, color="white" if bool(alt.theme.options.get("darkmode")) else "black").encode(
    x=xenc, y=alt.Y("log_t:Q", axis=yaxis, scale=alt.Scale(domain=[3, 11], nice=False))
)
fit = ds.add_correlation(df, "year", "log_t", ci=True, position=None)
label = ds.add_text(f"doubling every {doubling:.1f} years", position="topLeft")

chart = scatter + fit + label
