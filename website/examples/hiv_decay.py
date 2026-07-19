"""HIV viral-load decay - the plasma virus dynamics that revealed a furiously fast infection.

When potent antiretroviral therapy starts, plasma HIV-1 RNA falls exponentially - a straight line
on a log axis. Fitting that decline (in the browser, per patient) recovers a half-life of only
~1-2 days: the result from Ho et al. (1995) and Perelson et al. (1996) that overturned the idea of
HIV as a slow, latent virus. Patient traces here are representative, simulated from the first-phase
decay parameters reported in those papers - not the original data.
"""

import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

ds.theme(chartWidth=215, chartHeight=180)

rng = np.random.default_rng(5)
days = np.array([0, 1, 2, 3, 4, 5, 6, 7], dtype=float)

# (label, baseline copies/mL, first-phase half-life in days) - representative of Perelson 1996
patients = [("Patient 1", 2.2e5, 1.5), ("Patient 2", 5.5e4, 1.9), ("Patient 3", 7.8e5, 1.3)]

rows = []
for name, v0, thalf in patients:
    k = np.log(2.0) / thalf
    for t in days:
        v = v0 * np.exp(-k * t) * np.exp(rng.normal(0, 0.11))  # log-normal measurement noise
        rows.append({"patient": name, "day": float(t), "vl": float(v), "log_vl": float(np.log10(v))})
df = pl.DataFrame(rows)

# recover the mean first-phase half-life from a log-linear fit (in the browser)
halves = []
for name, _v0, _th in patients:
    sub = df.filter(pl.col("patient") == name)
    slope = np.polyfit(sub["day"].to_numpy(), sub["log_vl"].to_numpy(), 1)[0]
    halves.append(np.log10(2.0) / -slope)
thalf_mean = float(np.mean(halves))

# viral load is exponential in time, i.e. linear in log10 - so fit in log space and label the
# axis back as powers of ten
yaxis = alt.Axis(values=[4, 5, 6], labelExpr="'10' + ['⁰','¹','²','³','⁴','⁵','⁶','⁷','⁸','⁹'][round(datum.value)]", title="HIV RNA (copies/mL)")
scatter = alt.Chart(df).mark_point(filled=True, size=22).encode(
    x=alt.X("day:Q", title="Days after starting therapy", scale=alt.Scale(domain=[-0.3, 7.3], nice=False)),
    y=alt.Y("log_vl:Q", axis=yaxis, scale=alt.Scale(domain=[3.35, 6.15], nice=False)),  # explicit title keeps the CI field out of the axis
    color=alt.Color("patient:N", title=None),
)

# one OLS fit + confidence band per patient (position=None hides the r readout)
fits = ds.add_correlation(df, "day", "log_vl", groupCol="patient", ci=True, position=None)
label = ds.add_text(f"first-phase t½ ≈ {thalf_mean:.1f} days", position="topRight")

chart = scatter + fits + label
