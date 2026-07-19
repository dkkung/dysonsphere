"""Mendel's peas - the 3:1 ratio that founded genetics.

Gregor Mendel's F2 counts for seven pea traits. In every case the dominant phenotype appears in about
three-quarters of offspring and the recessive in one-quarter - the 3:1 ratio that revealed genes as
discrete, independently-segregating units. Each bar is the observed dominant fraction; the line marks
the 3:1 (0.75) expectation. Counts from Mendel's 1866 paper.
"""

import altair as alt
import polars as pl

import dysonsphere as ds

ds.theme(chartWidth=220, chartHeight=180)

# (trait, dominant-phenotype count, recessive count) - Mendel (1866), F2 generation
TRAITS = [
    ("seed shape", 5474, 1850),
    ("seed color", 6022, 2001),
    ("seed-coat color", 705, 224),
    ("pod shape", 882, 299),
    ("pod color", 428, 152),
    ("flower position", 651, 207),
    ("stem length", 787, 277),
]
df = pl.DataFrame(TRAITS, schema=["trait", "dominant", "recessive"], orient="row").with_columns(
    (pl.col("dominant") / (pl.col("dominant") + pl.col("recessive"))).alias("frac")
)
order = [t[0] for t in TRAITS]

bars = alt.Chart(df).mark_bar().encode(
    x=alt.X("frac:Q", title="Fraction showing the dominant trait", scale=alt.Scale(domain=[0, 1])),
    y=alt.Y("trait:N", sort=order, title=None),
)
ref = ds.add_rule(0.75, axis="x", label="expected 3 : 1", labelAlign="top", labelPosition="right")

chart = bars + ref
