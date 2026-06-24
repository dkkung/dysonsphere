"""
US county population choropleth using mark_geoshape and the mpl_viridis palette.

County boundaries: vega-datasets CDN (us-10m TopoJSON, "counties" feature).
Population data: US Census Bureau 2020 county population estimates.
"""

from pathlib import Path

import altair as alt
import polars as pl

import dysonsphere as ds
from dysonsphere.palettes import colors

# ── County population (Census Bureau 2020 vintage county estimates) ───────────

_census_url = (
    "https://www2.census.gov/programs-surveys/popest/"
    "datasets/2010-2020/counties/totals/co-est2020-alldata.csv"
)
county_pop = (
    pl.read_csv(_census_url, encoding="latin-1")
    .filter(pl.col("COUNTY") != 0)  # drop state-total rows (COUNTY == 0)
    .with_columns(
        (pl.col("STATE") * 1000 + pl.col("COUNTY")).alias("id"),
        pl.col("POPESTIMATE2020").alias("population"),
        pl.col("CTYNAME").alias("county"),
        pl.col("STNAME").alias("state"),
    )
    .select(["id", "county", "state", "population"])
)

# ── Chart ─────────────────────────────────────────────────────────────────────

ds.theme(
    chartWidth=700,
    chartHeight=430,
    legend=True,
    ticks=False,
    closed=False,
)

pal = colors["mpl_viridis"]

counties = alt.topo_feature(
    "https://cdn.jsdelivr.net/npm/vega-datasets@2/data/us-10m.json",
    "counties",
)

chart = (
    alt.Chart(counties)
    .mark_geoshape(stroke="white", strokeWidth=0.25)
    .transform_lookup(
        lookup="id",
        from_=alt.LookupData(data=county_pop, key="id", fields=["county", "state", "population"]),
    )
    .encode(
        color=alt.Color(
            "population:Q",
            title="Population",
            scale=alt.Scale(type="log", range=pal),
        ),
        tooltip=[
            alt.Tooltip("county:N", title="County"),
            alt.Tooltip("state:N", title="State"),
            alt.Tooltip("population:Q", title="Population", format=","),
        ],
    )
    .project("albersUsa")
    .properties(width=700, height=430)
)

out = str(Path(__file__).parent / "geomark")
ds.save(chart, out)
print(f"saved {out}  ({len(county_pop)} counties)")
