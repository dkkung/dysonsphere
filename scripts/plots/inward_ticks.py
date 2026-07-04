"""
Inward tick marks - theme(inwardTicks=True).

The physics/astronomy convention: a closed box frame with ticks pointing *into*
the plot, applied to both the major ticks and the log/power minor ticks, on the
primary and any explicitly-enabled secondary axes. No mirrored ticks on the
opposite axes. Setting inwardTicks also defaults closed=True (axisOffset=0).

Usage:
    uv run python scripts/plots/inward_ticks.py
"""

from pathlib import Path

import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

rng = np.random.default_rng(7)

# Band-pass frequency response: gain (dB) vs frequency (log Hz) - a model curve + measurements.
freq_model = np.logspace(0, 4, 200)
w = freq_model / 300.0
gain_model = 20 * np.log10(1.0 / np.sqrt(1 + (w - 1 / w) ** 2))
model = pl.DataFrame({"freq": freq_model, "gain": gain_model})

freq_data = np.logspace(0.15, 3.85, 30)
wd = freq_data / 300.0
gain_data = 20 * np.log10(1.0 / np.sqrt(1 + (wd - 1 / wd) ** 2)) + rng.normal(0, 0.7, len(freq_data))
data = pl.DataFrame({"freq": freq_data, "gain": gain_data})

ds.theme(inwardTicks=True, chartWidth=280, chartHeight=180)

x = alt.X(
    "freq:Q",
    title="Frequency (Hz)",
    scale=alt.Scale(type="log", domain=[1, 1e4]),
    axis=alt.Axis(values=[1, 10, 100, 1000, 10000]),
)
line = alt.Chart(model).mark_line().encode(x=x, y=alt.Y("gain:Q", title="Gain (dB)"))
points = alt.Chart(data).mark_circle().encode(x=x, y="gain:Q")

chart = ds.add_log_ticks(line + points, model, field="freq", axis="x")

ds.save(chart, str(Path(__file__).with_name("inward_ticks")), format=["png", "svg"], background="light")
print("saved inward_ticks")
