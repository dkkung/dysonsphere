"""
Interactive HTML export - ds.save(chart, ..., format="html").

Writes a self-contained, interactive HTML file (the Vega JS runtime is bundled in, so
it works offline): hover for tooltips, drag to pan, scroll to zoom. Because it renders
live in the browser, it's the "interactive / approximate" tier - fully themed and with
the metadata block embedded, but without the static SVG fixers (pixel-perfect tick
alignment, inward ticks, superscript typesetting) that ds.save()'s SVG/PNG get. For a
publication-accurate static figure, use format="svg"/"png".

Usage:
    uv run python scripts/plots/html_export.py
    # then open scripts/plots/html_export.html in a browser
"""

from pathlib import Path

import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

rng = np.random.default_rng(3)
n = 140
df = pl.DataFrame(
    {
        "x": rng.normal(0, 1, n),
        "y": rng.normal(0, 1, n),
        "group": rng.choice(["A", "B", "C", "D"], n),
    }
)

ds.theme()

chart = (
    alt.Chart(df)
    .mark_point()
    .encode(
        x=alt.X("x:Q", title="x"),
        y=alt.Y("y:Q", title="y"),
        color=alt.Color("group:N", title="Group"),
        tooltip=["group:N", "x:Q", "y:Q"],
    )
    .interactive()  # pan + zoom
)

ds.save(chart, str(Path(__file__).with_name("html_export")), format="html", background="light")
print("saved html_export.html - open it in a browser (hover for tooltips, drag/scroll to pan+zoom)")
