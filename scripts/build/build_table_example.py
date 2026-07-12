"""
Generates docs/table_example.png - the README preview for mark_table().

A differential-expression results table: gene labels, a log2 fold-change column
shaded by value (diverging pinksblues, auto-contrast text), an adjusted p-value in
scientific notation, and a plain hit count - with outer border, header separator,
and per-row rules.

Usage (from project root):
    uv run python scripts/build/build_table_example.py
"""

from pathlib import Path

import polars as pl

import dysonsphere as ds

ROOT = Path(__file__).resolve().parents[2]

df = pl.DataFrame(
    {
        "gene": ["TP53", "EGFR", "MYC", "BRCA1", "KRAS", "PTEN"],
        "log2FC": [2.31, -1.84, 0.42, 3.10, -2.67, 1.05],
        "padj": [1.2e-14, 3.4e-3, 4.2e-1, 5.6e-9, 8.9e-6, 2.7e-2],
        "hits": [128, 44, 12, 301, 77, 59],
    }
)

ds.theme(fontSize=5)

table = ds.mark_table(
    df,
    columnFormat={"log2FC": ".2f", "padj": "scientific", "hits": "d"},
    headerLabels={"gene": "Gene", "log2FC": "log₂FC", "padj": "p (adj)"},
    # cellColor={"log2FC": "pinksblues"},
    strokes=("outer", "header", "rows", "cols"),
)

out_png = ROOT / "docs" / "table_example.png"
ds.save(table, str(out_png.with_suffix("")), format="png", background="light", transparent=False)
print(f"saved {out_png}")
