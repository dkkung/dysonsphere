"""A power spectral density - 1/f noise with resonant peaks, on log-log axes with minor ticks."""

import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

ds.theme(chartWidth=185, chartHeight=140, axisOffset=0)

rng = np.random.default_rng(2)
f = np.logspace(0, 3.3, 600)  # 1 Hz .. ~2 kHz
psd = 1.0 / f**1.7  # pink-noise background
for f0, amp, w in [(12, 6e-2, 0.05), (60, 2.0e-1, 0.02), (180, 4e-2, 0.03)]:
    psd += amp * np.exp(-((np.log10(f) - np.log10(f0)) ** 2) / (2 * w**2))
psd *= np.exp(rng.normal(0, 0.18, f.size))  # multiplicative jitter

df = pl.DataFrame({"f": f, "psd": psd})
base = alt.Chart(df).mark_line().encode(
    # major ticks on the decades only; add_log_ticks() supplies the half-size minors (without
    # decade-only values, Vega draws its own full-size ticks at 2-9 and they double up)
    x=alt.X(
        "f:Q", title="Frequency (Hz)", scale=alt.Scale(type="log", domain=[1, 2000], nice=False),
        axis=alt.Axis(values=[1, 10, 100, 1000], labelExpr=ds.log_label_expr(notation="power")),
    ),
    y=alt.Y(
        "psd:Q", title="Power (a.u.)", scale=alt.Scale(type="log", nice=False),
        axis=alt.Axis(values=[1e-5, 1e-4, 1e-3, 1e-2, 1e-1, 1], labelExpr=ds.log_label_expr(notation="power")),
    ),
)

# cap the top decade on each axis (x at 10^3, y at 10^0) so add_log_ticks does not round the
# shared minor-tick domain OUT to the next full decade (10^4 / 10^1) and leave whitespace past
# where the data ends
chart = ds.add_log_ticks(base, df, axis="both", xField="f", yField="psd", xExpMax=3, yExpMax=0)
