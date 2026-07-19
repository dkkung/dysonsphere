"""Benford's law - why leading digits aren't uniform.

In many datasets the leading digit is a 1 about 30% of the time and a 9 under 5% - not the 1-in-9
you might expect. Benford's law, P(d) = log10(1 + 1/d), captures it. Here the leading digits of the
powers of two (2, 4, 8, 16, 32, ...) - a classic example - are tallied in the browser and matched
against the law.
"""

from collections import Counter

import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds
from dysonsphere.palettes import colors

ds.theme(chartWidth=215, chartHeight=175)
dark = bool(alt.theme.options.get("darkmode"))
ACCENT = colors["cat_blues"][5 if dark else 9]

# leading digit of 2**n for n = 1..2000 (Python big integers, tallied in the browser)
tally = Counter(int(str(2**n)[0]) for n in range(1, 2001))
total = sum(tally[d] for d in range(1, 10))
rows = [(d, 100.0 * tally[d] / total, 100.0 * float(np.log10(1 + 1 / d))) for d in range(1, 10)]
df = pl.DataFrame(rows, schema=["digit", "observed", "benford"], orient="row")

xenc = alt.X("digit:O", title="Leading digit")
bars = alt.Chart(df).mark_bar().encode(x=xenc, y=alt.Y("observed:Q", title="Frequency (%)", scale=alt.Scale(domain=[0, 34])))
law_line = alt.Chart(df).mark_line(color=ACCENT, point=alt.OverlayMarkDef(color=ACCENT, filled=True, size=34)).encode(
    x=xenc, y=alt.Y("benford:Q")
)

chart = bars + law_line
