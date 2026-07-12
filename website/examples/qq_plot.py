"""A normal Q-Q plot - a right-skewed sample departing from the y = x reference line."""

import altair as alt
import numpy as np
import polars as pl
from scipy import stats

import dysonsphere as ds

ds.theme(chartWidth=150, chartHeight=150, axisOffset=0)

rng = np.random.default_rng(15)
n = 220
sample = rng.standard_gamma(2.2, n)  # right-skewed
sample = (sample - sample.mean()) / sample.std()
theo = stats.norm.ppf((np.arange(1, n + 1) - 0.5) / n)  # theoretical normal quantiles
df = pl.DataFrame({"theo": theo, "samp": np.sort(sample)})

pts = alt.Chart(df).mark_circle(size=9, opacity=0.7).encode(
    x=alt.X("theo:Q", title="Theoretical quantiles", scale=alt.Scale(domain=[-3, 3], nice=False)),
    y=alt.Y("samp:Q", title="Sample quantiles", scale=alt.Scale(domain=[-3, 4], nice=False)),
)
ref = alt.Chart(pl.DataFrame({"q": [-3.0, 3.0]})).mark_line(strokeDash=[3, 3], color="gray", opacity=0.8).encode(
    x="q:Q", y="q:Q",
)

chart = ref + pts
