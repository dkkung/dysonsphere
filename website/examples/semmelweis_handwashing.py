"""Semmelweis - handwashing and the fall of childbed fever.

At the Vienna General Hospital's First Obstetrical Clinic, maternal mortality from puerperal
(childbed) fever ran as high as one mother in six. In 1847 Ignaz Semmelweis required doctors to wash
their hands in chlorinated lime before deliveries, and deaths collapsed within a year - decades
before germ theory explained why. Annual mortality for the First Clinic, from Semmelweis's statistics.
"""

import altair as alt
import polars as pl

import dysonsphere as ds

ds.theme(chartWidth=235, chartHeight=160)

# year, maternal mortality (% of births) - Vienna General Hospital, First Clinic
DATA = [(1841, 7.8), (1842, 15.8), (1843, 8.9), (1844, 8.2), (1845, 6.8), (1846, 11.4), (1847, 5.0), (1848, 1.3)]
df = pl.DataFrame(DATA, schema=["year", "mortality"], orient="row")

base = alt.Chart(df).mark_line(point=True).encode(
    x=alt.X("year:Q", title="Year", axis=alt.Axis(format="d"), scale=alt.Scale(domain=[1840.5, 1848.5], nice=False)),
    y=alt.Y("mortality:Q", title="Maternal mortality (%)", scale=alt.Scale(domain=[0, 18], nice=False)),
)
rule = ds.add_rule(1847, axis="x", label="handwashing introduced", labelAlign="top", labelPosition="left")

chart = base + rule
