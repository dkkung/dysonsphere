"""A power spectral density - 1/f noise with resonant peaks, on log-log axes with minor ticks."""

import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

ds.theme(chartWidth=185, chartHeight=140)

rng = np.random.default_rng(2)
f = np.logspace(0, 3.3, 600)  # 1 Hz .. ~2 kHz
psd = 1.0 / f**1.7  # pink-noise background
for f0, amp, w in [(12, 6e-2, 0.05), (60, 2.0e-1, 0.02), (180, 4e-2, 0.03)]:
    psd += amp * np.exp(-((np.log10(f) - np.log10(f0)) ** 2) / (2 * w**2))
psd *= np.exp(rng.normal(0, 0.18, f.size))  # multiplicative jitter

df = pl.DataFrame({"f": f, "psd": psd})
base = alt.Chart(df).mark_line().encode(
    x=alt.X("f:Q", title="frequency (Hz)", scale=alt.Scale(type="log", domain=[1, 2000], nice=False)),
    y=alt.Y("psd:Q", title="power (a.u.)", scale=alt.Scale(type="log", nice=False)),
)

chart = ds.add_log_ticks(base, df, axis="x", field="f")
