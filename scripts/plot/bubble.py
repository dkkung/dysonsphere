import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

rng = np.random.default_rng(42)

CLASSES = ["Class A", "Class B", "Class C", "Class D"]
N_PER_CLASS = 6

rows = []
for cls in CLASSES:
    for i in range(N_PER_CLASS):
        rows.append(
            {
                "compound": f"{cls[6]}{i + 1}",
                "class": cls,
                "ic50": float(10 ** rng.uniform(-1, 1.5)),
                "efficacy": float(rng.uniform(40, 100)),
                "selectivity": float(rng.uniform(5, 200)),
            }
        )

df = pl.DataFrame(rows)

palette = ds.palette("mpl_YlGnBu", n=len(CLASSES), start=2)

ds.theme(chartWidth=200, chartHeight=200)

chart = (
    alt.Chart(df)
    .mark_circle()
    .encode(
        x=alt.X("ic50:Q", title="IC₅₀ (nM)", scale=alt.Scale(type="log")),
        y=alt.Y("efficacy:Q", title="Efficacy (%)"),
        size=alt.Size(
            "selectivity:Q",
            title="Selectivity",
            scale=alt.Scale(range=[20, 500]),
        ),
        color=alt.Color("class:N", sort=CLASSES, scale=alt.Scale(range=palette), title=None),
    )
)

ds.save(chart, "bubble")
print("saved bubble")
