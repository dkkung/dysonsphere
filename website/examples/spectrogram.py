"""Spectrogram of a frequency-swept chirp with harmonics - time-frequency power, brass."""

import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

alt.data_transformers.enable("default", max_rows=None)
ds.theme(chartWidth=180, chartHeight=130, heatmapPalette="australis", closed=True, viewPadding=False)

rng = np.random.default_rng(3)
fs = 2000
T = 2.0
t = np.arange(0, T, 1 / fs)
f0, f1 = 80, 520
inst = f0 + (f1 - f0) * (t / T) ** 1.7
phase = 2 * np.pi * np.cumsum(inst) / fs
sig = np.sin(phase) + 0.5 * np.sin(2 * phase) + 0.25 * np.sin(3 * phase)
sig += 0.15 * rng.standard_normal(t.size)

win = 256
hop = 40
freqs = np.fft.rfftfreq(win, 1 / fs)
fmask = freqs <= 1000  # Nyquist (fs/2) is the true ceiling
hann = np.hanning(win)
frames = []
centers = []
for start in range(0, t.size - win, hop):
    seg = sig[start : start + win] * hann
    mag = np.abs(np.fft.rfft(seg))[fmask]
    frames.append(20 * np.log10(mag + 1e-3))
    centers.append((start + win / 2) / fs)
S = np.array(frames)
S = np.clip(S, np.percentile(S, 5), None)
fr = freqs[fmask]

dt = centers[1] - centers[0]
rows = []
for i, tc in enumerate(centers):
    for j in range(len(fr) - 1):
        rows.append(
            {
                "t0": round(tc - dt / 2, 4),
                "t1": round(tc + dt / 2 + dt * 0.3, 4),
                "f0": round(float(fr[j]), 2),
                "f1": round(float(fr[j + 1]) + (fr[1] - fr[0]) * 0.35, 2),
                "power": round(float(S[i, j]), 2),
            }
        )
df = pl.DataFrame(rows)

chart = (
    alt.Chart(df)
    .mark_rect(stroke=None, clip=True)
    .encode(
        x=alt.X("t0:Q", title="Time (s)", scale=alt.Scale(domain=[float(centers[0] - dt / 2), float(centers[-1] + dt / 2)], nice=False)),
        x2="t1",
        y=alt.Y("f0:Q", title="Frequency (Hz)", scale=alt.Scale(domain=[0, float(fr[-1])], nice=False)),
        y2="f1",
        color=alt.Color("power:Q", title="dB"),
    )
)

