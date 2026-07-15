"""Learning curves - training vs validation loss and accuracy over epochs, the val loss turning up."""

import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

ds.theme(chartWidth=150, chartHeight=135)

rng = np.random.default_rng(4)
epoch = np.arange(1, 51)


def noisy(curve, sd):
    return curve + rng.normal(0, sd, epoch.size)


# Training keeps improving; validation plateaus then overfits (loss turns up, accuracy stalls).
curves = {
    "train": (
        noisy(1.9 * np.exp(-epoch / 9) + 0.04, 0.015),
        noisy(1 - 0.75 * np.exp(-epoch / 7), 0.006),
    ),
    "val": (
        noisy(1.7 * np.exp(-epoch / 11) + 0.18 + 0.006 * epoch, 0.03),
        noisy(0.9 - 0.62 * np.exp(-epoch / 8), 0.01),
    ),
}
rows = []
for split, (loss, acc) in curves.items():
    for e, ln, an in zip(epoch, loss, acc):
        rows.append({"epoch": int(e), "split": split, "loss": float(ln), "accuracy": float(min(an, 0.995))})
df = pl.DataFrame(rows)

color = alt.Color("split:N", sort=["train", "val"], title=None)
xenc = alt.X("epoch:Q", title="epoch", scale=alt.Scale(domain=[0, 50], nice=False))

loss = alt.Chart(df).mark_line().encode(
    x=xenc, y=alt.Y("loss:Q", title="loss", scale=alt.Scale(domain=[0, 2])), color=color
)
acc = alt.Chart(df).mark_line().encode(
    x=xenc, y=alt.Y("accuracy:Q", title="accuracy", scale=alt.Scale(domain=[0.2, 1])), color=color
)

chart = (loss | acc).resolve_scale(y="independent")
