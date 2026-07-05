"""
Generates docs/text_example.png — the README preview for add_text().

Usage (from project root):
    uv run python scripts/build/build_text_example.py
"""

import tempfile
from pathlib import Path
from typing import Any

import altair as alt
import numpy as np
import polars as pl
import vl_convert as vlc

import dysonsphere as ds
from dysonsphere.export import _render_fixed_svg

ROOT = Path(__file__).resolve().parents[2]


GROUPS = ["Control", "Group A", "Group B", "Group C", "Group D", "Group E"]
n = 20

rng = np.random.default_rng(42)
df = pl.DataFrame(
    {
        "group": sum([[g] * n for g in GROUPS], []),
        "value": np.concatenate([rng.normal(loc, 0.9, n) for loc in [4.0, 4.5, 3.2, 5.4, 8.0, 7.2]]),
    }
)

title_params: dict[str, Any] = dict(orient="top", anchor="start", offset=4)

ds.theme(palette="blues2", chartWidth=150, chartHeight=75)
fontSize = alt.theme.options.get("fontSize", 7)

base = ds.mark_strip(df, "group", "value", GROUPS, yTitle="Response")

chart = (
    base
    + ds.add_text("n = 20", x="Control", y=1.0, align="center")
    + ds.add_text("ANOVA p < 0.001", position="topLeft")
    + ds.add_text("Threshold = 5.0", position="bottomRight")
    + ds.add_rule(5)
).properties(
    title=alt.TitleParams(
        [
            'add_text("ANOVA p < 0.001", position="topLeft")',
            'add_text("Threshold = 5.0", position="bottomRight")',
            'add_text("n = 20", x="Control", y=1.0, align="center")',
        ],
        fontSize=fontSize,
        **title_params,
    )
)

multi = {
    "Condition A": [False, True, True, False, False, False],
    "Condition B": [False, False, True, True, True, True],
}
annotated = ds.add_multilabel(chart, categories=GROUPS, groups=multi, style="plusminus", categoryLabel=True)

out_png = ROOT / "docs" / "text_example.png"
with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as tmp:
    tmp_path = tmp.name
svg_content = _render_fixed_svg(annotated, tmp_path)
Path(tmp_path).unlink()
out_png.write_bytes(vlc.svg_to_png(svg_content, ppi=1200))
print(f"saved {out_png}")
