"""Hodgkin-Huxley - the action potential, integrated live from the 1952 equations.

Hodgkin and Huxley's model of the squid giant axon: voltage-gated sodium and potassium conductances
that together generate the nerve impulse. A sustained current injection drives the membrane to fire a
train of action potentials - the sharp depolarization to +40 mV, repolarization, and afterhyperpolar-
ization. Here the four coupled ODEs are integrated in the browser with their original parameters.
"""

import altair as alt
import numpy as np
import polars as pl
from scipy.integrate import solve_ivp
from scipy.signal import find_peaks

import dysonsphere as ds

ds.theme(chartWidth=255, chartHeight=160)

# squid giant axon parameters (Hodgkin & Huxley, 1952)
CM, G_NA, G_K, G_L = 1.0, 120.0, 36.0, 0.3
E_NA, E_K, E_L = 50.0, -77.0, -54.4


def vtrap(x, y):  # x / (exp(x/y) - 1), robust through the removable singularity at x = 0
    return np.where(np.abs(x / y) < 1e-6, y * (1 - x / (2 * y)), x / (np.exp(x / y) - 1))


def a_m(v):
    return 0.1 * vtrap(-(v + 40), 10)


def b_m(v):
    return 4.0 * np.exp(-(v + 65) / 18)


def a_h(v):
    return 0.07 * np.exp(-(v + 65) / 20)


def b_h(v):
    return 1.0 / (1 + np.exp(-(v + 35) / 10))


def a_n(v):
    return 0.01 * vtrap(-(v + 55), 10)


def b_n(v):
    return 0.125 * np.exp(-(v + 65) / 80)


def i_inj(t):
    return 8.0 if 5.0 <= t <= 50.0 else 0.0  # sustained supra-threshold current (uA/cm^2)


def deriv(t, y):
    v, m, h, n = y
    dv = (i_inj(t) - G_NA * m**3 * h * (v - E_NA) - G_K * n**4 * (v - E_K) - G_L * (v - E_L)) / CM
    return [dv, a_m(v) * (1 - m) - b_m(v) * m, a_h(v) * (1 - h) - b_h(v) * h, a_n(v) * (1 - n) - b_n(v) * n]


v0 = -65.0
y0 = [v0, float(a_m(v0) / (a_m(v0) + b_m(v0))), float(a_h(v0) / (a_h(v0) + b_h(v0))), float(a_n(v0) / (a_n(v0) + b_n(v0)))]
sol = solve_ivp(deriv, [0, 55], y0, t_eval=np.linspace(0, 55, 400), max_step=0.05, rtol=1e-6, atol=1e-8)
tt, vv = sol.t, sol.y[0]

# shade each action-potential cycle in alternating greys - the spikes are not perfectly periodic,
# so use the actual afterhyperpolarization minima (troughs) as the band boundaries
troughs = find_peaks(-vv, prominence=5.0)[0]
bounds = [0.0, *(float(tt[i]) for i in troughs), 55.0]
bands = [(bounds[i], bounds[i + 1]) for i in range(len(bounds) - 1)]
shade = ds.add_shade(positions=bands, nShades=2)

# color the trace by voltage: a continuous color straight on mark_line degenerates to disconnected
# points (Vega-Lite groups the line by the color field), so build it from short per-segment lines
idx = np.repeat(np.arange(len(tt)), 2)[1:-1]
seg = pl.DataFrame({
    "t": tt[idx],
    "V": vv[idx],
    "seg": np.repeat(np.arange(len(tt) - 1), 2),
    "mV": np.repeat((vv[:-1] + vv[1:]) / 2, 2),
})
line = alt.Chart(seg).mark_line().encode(
    x=alt.X("t:Q", title="Time (ms)", scale=alt.Scale(domain=[0, 55], nice=False)),
    y=alt.Y("V:Q", title="Membrane potential (mV)", scale=alt.Scale(domain=[-90, 55], nice=False)),
    detail="seg:N",
    color=alt.Color("mV:Q", title="mV"),  # default continuous colormap (australis)
)

chart = shade + line
