import polars as pl

import dysonsphere as ds

# mark_table() renders a DataFrame as a styled table: per-column number formatting
# (adjusted p-values in scientific notation, typeset with real superscripts and an
# italic "p"), italic gene names via fontStyle, and strokes between every cell.
ds.theme()

df = pl.DataFrame(
    {
        "gene": ["TP53", "EGFR", "MYC", "BRCA1", "KRAS"],
        "log2FC": [2.31, -1.84, 0.42, 3.10, -2.67],
        "padj": [1.2e-14, 3.4e-3, 4.2e-1, 5.6e-9, 8.9e-6],
    }
)

chart = ds.mark_table(
    df,
    columnFormat={"log2FC": ".2f", "padj": "scientific"},
    headerLabels={"gene": "Gene", "log2FC": "log₂FC", "padj": "adj. p-value"},
    fontStyle={"gene": "italic"},
    strokes=("outer", "header", "all"),
)
