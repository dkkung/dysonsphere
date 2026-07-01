"""
Generates docs/omnibus_example_light.png — the README preview for the
omnibus mode of add_comparisons.

Two panels, each a boxplot with an omnibus test reported in the corner (via the
add_text hook) plus post-hoc brackets for all three comparisons against Control
(auto-stacked at the default yStep):
  left  — test="anova" (verbose corner label) + Tukey HSD brackets
  right — test="kruskal" (terse asterisk label) + Dunn brackets

Category names are alphabetical by design so the shared band scale keeps the
intended left-to-right order, and the y domain is padded so the corner label
clears the brackets.

Usage (from project root):
    uv run python scripts/build/build_omnibus_example.py
"""

import tempfile
from pathlib import Path
from typing import Any

import altair as alt
import numpy as np
import polars as pl
import vl_convert as vlc

import dysonsphere as ds
from dysonsphere.export import _fix_tick_alignment

ROOT = Path(__file__).resolve().parents[2]


CATEGORIES = ["Control", "Dose A", "Dose B", "Dose C"]

rng = np.random.default_rng(7)
df = pl.DataFrame(
    {
        "group": [c for c in CATEGORIES for _ in range(40)],
        "value": np.concatenate(
            [
                rng.normal(1.0, 0.4, 40),
                rng.normal(1.4, 0.45, 40),
                rng.normal(2.4, 0.5, 40),
                rng.normal(2.9, 0.45, 40),
            ]
        ),
    }
)

PAIRS = [("Control", "Dose A"), ("Control", "Dose B"), ("Control", "Dose C")]

ds.theme(chartFill="white", palette="blues2", chartWidth=150, chartHeight=120, markSize=13, legend=False)

x = alt.X("group:N", sort=CATEGORIES, title=None)
y = alt.Y("value:Q", title="Value", scale=alt.Scale(domain=[0, 6]))


def boxplot() -> alt.Chart:
    return alt.Chart(df).mark_boxplot(color=ds.palette("blues")[0]).encode(x=x, y=y, color=alt.Color("group:N"))


common: dict[str, Any] = dict(
    df=df,
    xCol="group",
    yCol="value",
    pairs=PAIRS,
    categories=CATEGORIES,
    yStart=3.5,
)

title_params: dict[str, Any] = dict(orient="top", anchor="start", offset=4)
fontSize = alt.theme.options.get("fontSize", 7)

left = (boxplot() + ds.add_comparisons(**common, test="anova", omnibusVerbose=True)).properties(
    title=alt.TitleParams(
        ['test="anova"', "omnibusVerbose=True", "post-hoc: Tukey HSD"], fontSize=fontSize, **title_params
    )
)

right = (boxplot() + ds.add_comparisons(**common, test="kruskal", labelStyle="asterisks")).properties(
    title=alt.TitleParams(
        ['test="kruskal"', 'labelStyle="asterisks"', "post-hoc: Dunn"], fontSize=fontSize, **title_params
    )
)

chart = alt.hconcat(left, right)

out_png = ROOT / "docs" / "omnibus_example_light.png"
with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as tmp:
    tmp_path = tmp.name
chart.save(tmp_path)
_fix_tick_alignment(
    tmp_path,
    band_padding=alt.theme.options.get("bandPadding", 0.1),
    chart_width=alt.theme.options.get("chartWidth", 100),
)
with open(tmp_path, encoding="utf-8") as f:
    svg_content = f.read()
Path(tmp_path).unlink()
out_png.write_bytes(vlc.svg_to_png(svg_content, ppi=1200))
print(f"saved {out_png}")
