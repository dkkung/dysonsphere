"""Luria-Delbruck - the fluctuation test that proved mutations arise at random.

Do bacteria acquire resistance in response to a virus, or do resistant mutants arise spontaneously
beforehand? Luria & Delbruck (1943) grew many parallel cultures and counted resistant colonies. If
resistance were induced by the virus, counts would follow a tight Poisson (variance = mean). Instead
they fluctuated wildly, with rare 'jackpot' cultures - the signature of spontaneous mutations that,
arising early, seed huge resistant clones. Here each point is a simulated culture under the two
hypotheses (Luria-Delbruck model vs Poisson), matched in mean.
"""

import numpy as np
import polars as pl

import dysonsphere as ds

ds.theme(chartWidth=170, chartHeight=195)

rng = np.random.default_rng(7)
n = 46
rate = 1.1  # mean mutational events per culture


def spontaneous():
    # Lea-Coulson clone sizes: P(size >= j) ~ 1/j (heavy tail), capped at the final population
    total = 0
    for _ in range(rng.poisson(rate)):
        total += min(int(1.0 / rng.random()), 80)
    return total


ld = [spontaneous() for _ in range(n)]
induced = rng.poisson(np.mean(ld), n).tolist()  # induced hypothesis: Poisson, same mean

rows = [{"model": "Spontaneous", "count": float(c)} for c in ld]
rows += [{"model": "Induced", "count": float(c)} for c in induced]
df = pl.DataFrame(rows)

chart = ds.mark_strip(df, "model", "count", ["Spontaneous", "Induced"], yTitle="Resistant colonies per culture", xTitle=None)
