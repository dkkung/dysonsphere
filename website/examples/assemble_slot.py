import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

ds.theme()
rng = np.random.default_rng(11)

GENOTYPES = ["WT", "het", "null"]
pheno = pl.DataFrame(
    [{"genotype": g, "value": float(rng.normal(m, 1.4))} for g, m in zip(GENOTYPES, (8.0, 6.4, 3.1)) for _ in range(14)]
)

decades = pl.DataFrame({"conc": [10.0**e for e in range(-3, 3)], "signal": [2, 9, 26, 58, 83, 94]})

area = rng.uniform(0, 12, 40)
motility = pl.DataFrame({"area": area, "speed": -0.4 * area + rng.normal(0, 0.9, 40) + 8})


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


# Panel a is reserved: 150 x 100 of space held for content composited in during final assembly.
chart = ds.assemble(
    [
        [(None, 150, 100, "a"), (phenotype_strip, 85, 100, "b")],
        [(dose_curve, 110, 90, "c"), (motility_fit, 110, 90, "d")],
    ],
    spacing={"row": 32, "column": 16},
)
