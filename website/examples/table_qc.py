import polars as pl

import dysonsphere as ds

# A sequencing QC summary as a mark_table: read counts in SI notation, per-metric
# formatting, and the mapping rate shaded by value - a quality heatmap column.
ds.theme()

df = pl.DataFrame(
    {
        "sample": ["Ctrl-1", "Ctrl-2", "Trt-1", "Trt-2", "Trt-3"],
        "reads": [41_200_000, 38_900_000, 52_600_000, 47_300_000, 44_100_000],
        "q30": [94.6, 93.8, 95.1, 94.2, 92.9],
        "mapped": [96.8, 95.9, 97.4, 96.1, 94.3],
        "dup": [11.2, 13.6, 9.8, 12.1, 15.4],
    }
)

chart = ds.mark_table(
    df,
    columnFormat={"reads": "si", "q30": ".1f", "mapped": ".1f", "dup": ".1f"},
    headerLabels={"sample": "Sample", "reads": "Reads", "q30": "Q30 %", "mapped": "Mapped %", "dup": "Dup %"},
    cellColor={"mapped": "greens"},
    strokes=("outer", "header", "rows"),
)
