"""Subscripts with `__` and superscripts with `^`, typeset on export."""

import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

ds.theme()
rng = np.random.default_rng(0)
t = np.linspace(0.0, 5.0, 50)
df = pl.DataFrame({"t": t, "C": 5.0 * np.exp(-0.8 * t) + rng.normal(0.0, 0.04, t.size)})

chart = alt.Chart(df).mark_line().encode(
    x=alt.X("t:Q", title="t (s)"),
    y=alt.Y("C:Q", title="C__t (mmol/L)"),  # `__` lowers -> C with a subscript t
) + ds.add_text("rate = kC^2", position="topRight")  # `^` raises -> C squared
