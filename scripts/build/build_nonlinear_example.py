"""
Generates docs/nonlinear_example.png — README preview for add_log_ticks / add_pow_ticks.

Two panels:
  left  — log10 y-axis with add_log_ticks(base=10)
  right — sqrt x-axis  with add_pow_ticks(exponent=0.5)

Usage (from project root):
    uv run python scripts/build/build_nonlinear_example.py
"""

import math
from pathlib import Path
from typing import Any

import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

ROOT = Path(__file__).resolve().parents[2]


rng = np.random.default_rng(42)

GROUPS = ["Group A", "Group B", "Group C"]
SLOPES = {"Group A": 2.8, "Group B": -0.8, "Group C": 0.1}

BODIES = ["Earth", "Mars", "Moon"]
G = {"Earth": 9.81, "Mars": 3.72, "Moon": 1.62}

ds.theme(palette="blues2", chartWidth=100, chartHeight=100, legend=False)
palette = ds.palette("blues2", n=3)
fontSize = alt.theme.options.get("fontSize", 7)
title_params: dict[str, Any] = dict(orient="top", anchor="start", offset=4)

# ── Left: log10 y-axis ────────────────────────────────────────────────────
log_rows = []
for group in GROUPS:
    for t in [0, 1, 3, 5, 7, 10]:
        if t == 0:
            value = 1e5
        else:
            value = 1e5 * np.exp(SLOPES[group] * t / 9) * rng.lognormal(0, 0.15)
        log_rows.append({"group": group, "time": float(t), "value": float(value)})
df_log = pl.DataFrame(log_rows)

v_min = float(df_log["value"].min())  # ty: ignore[invalid-argument-type]
v_max = float(df_log["value"].max())  # ty: ignore[invalid-argument-type]
exp_min = int(math.floor(math.log10(v_min)))
exp_max = int(math.ceil(math.log10(v_max)))
major_log = [10**e for e in range(exp_min, exp_max + 1)]

log_chart = (
    alt.Chart(df_log)
    .mark_line(point=True)
    .encode(
        x=alt.X("time:Q", title="Time (days)", scale=alt.Scale(domain=[0, 10])),
        y=alt.Y(
            "value:Q",
            title="Count",
            scale=alt.Scale(type="log", base=10),
            axis=alt.Axis(
                values=major_log,
                labelExpr=ds.log_label_expr(),
            ),
        ),
        color=alt.Color(
            "group:N",
            sort=GROUPS,
            scale=alt.Scale(range=palette),
            legend=None,
        ),
    )
)
log_chart = ds.add_log_ticks(log_chart, df_log, "value", axis="y", base=10)
left = log_chart.properties(
    title=alt.TitleParams(
        ['add_log_ticks(field="value")', 'axis="y", base=10'],
        fontSize=fontSize,
        **title_params,
    )
)

# ── Right: sqrt x-axis (pendulum period T = 2π√(L/g)) ────────────────────
L_fit = np.linspace(0.25, 4.0, 100)
pow_rows = []
for body in BODIES:
    for L, T in zip(L_fit, 2 * math.pi * np.sqrt(L_fit / G[body])):
        pow_rows.append({"body": body, "length": float(L), "period": float(T)})
df_pow = pl.DataFrame(pow_rows)

major_pow = [0.25, 1.0, 2.25, 4.0]
x_scale = alt.Scale(type="pow", exponent=0.5, domain=[0.25, 4.0])

pow_chart = (
    alt.Chart(df_pow)
    .mark_line()
    .encode(
        x=alt.X(
            "length:Q",
            title="Pendulum length (m, √ scale)",
            scale=x_scale,
            axis=alt.Axis(values=major_pow),
        ),
        y=alt.Y("period:Q", title="Period (s)"),
        color=alt.Color(
            "body:N",
            sort=BODIES,
            scale=alt.Scale(range=palette),
            legend=None,
        ),
    )
)
pow_chart = ds.add_pow_ticks(
    pow_chart,
    df_pow,
    "length",
    axis="x",
    exponent=0.5,
    majorValues=major_pow,
    nMinor=4,
)
right = pow_chart.properties(
    title=alt.TitleParams(
        ['add_pow_ticks(field="length")', 'axis="x", exponent=0.5', "nMinor=4"],
        fontSize=fontSize,
        **title_params,
    )
)

chart = alt.hconcat(left, right)

out_png = ROOT / "docs" / "nonlinear_example.png"
ds.save(chart, str(out_png.with_suffix("")), format="png", background="light", transparent=False)
print(f"saved {out_png}")
