import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

ds.theme()
rng = np.random.default_rng(11)

coverage = pl.DataFrame({"pos": np.arange(0, 400), "depth": np.abs(np.cumsum(rng.normal(0, 1, 400))) + 5})

GENOTYPES = ["WT", "het", "null"]
pheno = pl.DataFrame(
    [{"genotype": g, "value": float(rng.normal(m, 1.4))} for g, m in zip(GENOTYPES, (8.0, 6.4, 3.1)) for _ in range(14)]
)

decades = pl.DataFrame({"conc": [10.0**e for e in range(-3, 3)], "signal": [2, 9, 26, 58, 83, 94]})

area = rng.uniform(0, 12, 40)
motility = pl.DataFrame({"area": area, "speed": -0.4 * area + rng.normal(0, 0.9, 40) + 8})


def coverage_track():
    return (
        alt.Chart(coverage)
        .mark_area()
        .encode(x=alt.X("pos:Q", title="Position (kb)"), y=alt.Y("depth:Q", title="Depth"))
    )


def phenotype_strip():
    return ds.mark_strip(pheno, "genotype", "value", GENOTYPES, xTitle=None, yTitle="Score") + ds.stats.comparisons(
        pheno, "genotype", "value", reference="WT", test="ttest_ind", categories=GENOTYPES, labelStyle="asterisks"
    )


def dose_curve():
    return (
        alt.Chart(decades)
        .mark_line(point=True)
        .encode(
            x=alt.X(
                "conc:Q",
                scale=alt.Scale(type="log"),
                title="Conc (µM)",
                axis=alt.Axis(values=list(decades["conc"]), labelExpr=ds.log_label_expr()),
            ),
            y=alt.Y("signal:Q", title="Response"),
        )
    )


def motility_fit():
    points = (
        alt.Chart(motility)
        .mark_point(filled=True)
        .encode(x=alt.X("area:Q", title="Area (µm^2)"), y=alt.Y("speed:Q", title="Speed (µm/min)"))
    )
    return points + ds.stats.correlation(motility, "area", "speed", position="topRight")


# The track's 372 px is chosen so its rendered width matches the row beneath it: that row
# comes to 422 px, and a single chart carries 50 px of axis chrome around its plot area.
chart = ds.assemble(
    [
        [{"chart": coverage_track, "width": 372, "height": 70, "label": "a"}],
        [
            {"chart": phenotype_strip, "width": 85, "height": 95, "label": "b"},
            {"chart": dose_curve, "width": 95, "height": 95, "label": "c"},
            {"chart": motility_fit, "width": 95, "height": 95, "label": "d"},
        ],
    ],
    spacing={"row": 30, "column": 14},
)
