"""
Generates docs/multilabel_example_light.png — the README preview for add_multilabel.

Shows all three grid label styles (plusminus, symbol, text) side by side,
each attached below a strip chart via add_multilabel().

Usage (from project root):
    uv run python scripts/build/build_multilabel_example.py
"""

import tempfile
from pathlib import Path

import altair as alt
import numpy as np
import polars as pl
import vl_convert as vlc

import dysonsphere as ds
from dysonsphere.export import _fix_tick_alignment

CATEGORIES = ["Control", "Drug A", "Drug B", "Drug C"]

rng = np.random.default_rng(42)
df = pl.DataFrame(
    {
        "group": (["Control"] * 38 + ["Drug A"] * 45 + ["Drug B"] * 52 + ["Drug C"] * 41),
        "value": np.concatenate(
            [
                rng.normal(1.0, 0.1, 38),
                rng.normal(2.1, 0.3, 45),
                rng.normal(5.4, 0.8, 52),
                rng.normal(7.2, 0.6, 41),
            ]
        ),
    }
)

CONDITIONS = {
    "Condition 1": [False, False, False, True],
    "Condition 2": [False, False, True, True],
    "Condition 3": [False, True, True, True],
}

SCORES = {
    "Score A": ["1.2", "3.4", "0.8", "2.1"],
    "Score B": ["0.4", "0.1", "1.7", "0.9"],
    "Score C": ["5", "12", "8", "20"],
}


def build_multilabel_example():
    ds.theme(chartFill="white", palette="blues2")

    out_base = str(Path(__file__).parent.parent.parent / "docs" / "multilabel_example")

    def make_chart() -> alt.HConcatChart:
        chart = ds.mark_strip(df, "group", "value", CATEGORIES, yTitle="Value")
        KWARGS = dict(categories=CATEGORIES, labelAlign="left")

        def corner_label(text: str) -> alt.LayerChart:
            lines = text.split("\n")
            label = (
                alt.Chart(alt.Data(values=[{}]))
                .mark_text(align="left", baseline="top", text=lines if len(lines) > 1 else lines[0])
                .encode(x=alt.value(4), y=alt.value(4))
            )
            return chart + label

        pm = ds.add_multilabel(
            corner_label('style = "plusminus"'), CONDITIONS, style="plusminus", **KWARGS
        )
        dot = ds.add_multilabel(
            corner_label('style = "symbol"'), CONDITIONS, style="symbol", **KWARGS
        )
        txt = ds.add_multilabel(
            corner_label('showSampleSize = True\nstyle = "text"'),
            {"Score A": SCORES["Score B"], "Score B": SCORES["Score C"]},
            style="text",
            showSampleSize=True,
            df=df,
            xCol="group",
            **KWARGS,
        )
        return alt.hconcat(pm, dot, txt)

    out_png = Path(out_base + "_light.png")
    with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as tmp:
        tmp_path = tmp.name
    make_chart().save(tmp_path)
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


if __name__ == "__main__":
    build_multilabel_example()
