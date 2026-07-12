"""Kaplan-Meier survival curves - treatment vs control step estimates with censoring ticks."""

import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds
from dysonsphere.palettes import colors

ds.theme(chartWidth=175, chartHeight=140)

# saturated two-group scale (the default categorical tints read washed-out for two line series)
group_scale = alt.Scale(domain=["Treatment", "Control"], range=[colors["blues"][7], colors["pinks"][7]])

rng = np.random.default_rng(11)
FOLLOWUP = 36.0  # months of follow-up


def km(event_scale, n=90):
    """A Kaplan-Meier step estimate: S drops by 1/at-risk at each death, unchanged at censoring."""
    t_event = rng.exponential(event_scale, n)
    t_censor = rng.exponential(40, n)
    t = np.minimum(np.minimum(t_event, t_censor), FOLLOWUP)
    observed = (t_event <= t_censor) & (t_event <= FOLLOWUP)  # death seen (else censored)
    order = np.argsort(t)
    at_risk, S = n, 1.0
    curve, censored = [{"t": 0.0, "S": 1.0}], []
    for ti, ev in zip(t[order], observed[order]):
        if ev:
            S *= 1 - 1 / at_risk
            curve.append({"t": float(ti), "S": S})
        else:
            censored.append({"t": float(ti), "S": S})
        at_risk -= 1
    return curve, censored


rows, ticks = [], []
for name, scale in [("Treatment", 26.0), ("Control", 13.0)]:
    curve, censored = km(scale)
    rows += [{**r, "group": name} for r in curve]
    ticks += [{**c, "group": name} for c in censored]

lines = (
    alt.Chart(pl.DataFrame(rows))
    .mark_line(interpolate="step-after")
    .encode(
        x=alt.X("t:Q", title="Time (months)", scale=alt.Scale(domain=[0, FOLLOWUP], nice=False)),
        y=alt.Y("S:Q", title="Survival probability", scale=alt.Scale(domain=[0, 1], nice=False)),
        color=alt.Color("group:N", title=None, scale=group_scale),
    )
)
# censoring marks: a tick on the curve at each censored subject, colored to its group
censor = (
    alt.Chart(pl.DataFrame(ticks))
    .mark_tick(thickness=1, size=5)
    .encode(x="t:Q", y="S:Q", color=alt.Color("group:N", legend=None, scale=group_scale))
)

chart = lines + censor
