"""
Generates docs/pairwise_example_light.png — the README preview for add_comparisons.

Shows labelStyle="p", notation="scientific", and labelStyle="asterisks" on the
same three-group comparison, plus a reverse-bracket + test-name-label demo on the right.

Usage (from project root):
    uv run python scripts/build/build_pairwise_example.py
"""

import tempfile
from pathlib import Path
from typing import Any

import altair as alt
import numpy as np
import polars as pl
import vl_convert as vlc

import dysonsphere as ds
from dysonsphere.export import _fix_superscript_labels, _fix_tick_alignment

ROOT = Path(__file__).resolve().parents[2]


CATEGORIES = ["A", "B", "C"]

rng = np.random.default_rng(42)
df = pl.DataFrame(
    {
        "group": [CATEGORIES[0]] * 40 + [CATEGORIES[1]] * 40 + [CATEGORIES[2]] * 40,
        "value": np.concatenate(
            [
                rng.normal(1.0, 0.35, 40),
                rng.normal(2.2, 0.45, 40),
                rng.normal(1.15, 0.4, 40),
            ]
        ),
    }
)

PAIRS = [("A", "B"), ("A", "C"), ("B", "C")]

THIRD_CATEGORIES = ["A", "B"]
third_df = pl.DataFrame(
    {
        "group": ["A"] * 40 + ["B"] * 40,
        "value": np.concatenate(
            [
                rng.normal(1.5, 0.4, 40),
                rng.normal(2.1, 0.4, 40),
            ]
        ),
    }
)

ds.theme(palette="blues2", chartWidth=75, markSize=13, legend=False)

x = alt.X("group:N", sort=CATEGORIES, title=None)

left_base = (
    alt.Chart(df)
    .mark_boxplot(color=ds.palette("blues")[0])
    .encode(x=x, y=alt.Y("value:Q", title=None), color=alt.Color("group:N"))
)
scientific_base = (
    alt.Chart(df)
    .mark_boxplot(color=ds.palette("blues")[0])
    .encode(x=x, y=alt.Y("value:Q", title=None), color=alt.Color("group:N"))
)
right_base = (
    alt.Chart(df)
    .mark_boxplot(color=ds.palette("blues")[0])
    .encode(x=x, y=alt.Y("value:Q", title=None), color=alt.Color("group:N"))
)

pvalue_kwargs: dict[str, Any] = dict(
    df=df,
    xCol="group",
    yCol="value",
    pairs=PAIRS,
    categories=CATEGORIES,
)

title_params: dict[str, Any] = dict(orient="top", anchor="start", offset=4)
fontSize = alt.theme.options.get("fontSize", 7)

left = (left_base + ds.add_comparisons(**pvalue_kwargs, labelStyle="p", bracketStyle="line")).properties(
    title=alt.TitleParams(['labelStyle="p"', 'bracketStyle="line"'], fontSize=fontSize, **title_params)
)
scientific = (scientific_base + ds.add_comparisons(**pvalue_kwargs, labelStyle="p", notation="scientific")).properties(
    title=alt.TitleParams(['labelStyle="p"', 'notation="scientific"'], fontSize=fontSize, **title_params)
)
right = (right_base + ds.add_comparisons(**pvalue_kwargs, labelStyle="asterisks", bracketStyle="bracket")).properties(
    title=alt.TitleParams(
        ['labelStyle="asterisks"', 'bracketStyle="bracket"'],
        fontSize=fontSize,
        **title_params,
    )
)

third_x = alt.X("group:N", sort=THIRD_CATEGORIES, title=None)
third_base = (
    alt.Chart(third_df)
    .mark_boxplot(color=ds.palette("blues")[0])
    .encode(x=third_x, y=alt.Y("value:Q", title=None), color=alt.Color("group:N"))
)
third = (
    third_base
    + ds.add_comparisons(
        third_df,
        "group",
        "value",
        pairs=[("A", "B")],
        categories=THIRD_CATEGORIES,
        bracketStyle="bracket",
        yStart=float(third_df["value"].min()) - 0.25,  # ty: ignore[invalid-argument-type]
        reverse=[("A", "B")],
        testLabelPosition="topLeft",  # → "Mann-Whitney U" (the default pairwise test)
    )
).properties(
    title=alt.TitleParams(
        ['reverse=[("A", "B")]', 'testLabelPosition="topLeft"'],
        fontSize=fontSize,
        **title_params,
    )
)

chart = alt.hconcat(left, scientific, right, third)

out_png = ROOT / "docs" / "pairwise_example_light.png"
with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as tmp:
    tmp_path = tmp.name
chart.save(tmp_path)
_fix_tick_alignment(
    tmp_path,
    band_padding=alt.theme.options.get("bandPadding", 0.1),
    chart_width=alt.theme.options.get("chartWidth", 100),
)
_fix_superscript_labels(tmp_path)
with open(tmp_path, encoding="utf-8") as f:
    svg_content = f.read()
Path(tmp_path).unlink()
out_png.write_bytes(vlc.svg_to_png(svg_content, ppi=1200))
print(f"saved {out_png}")
