"""The Higgs boson diphoton 'bump' - reconstructed from ATLAS Open Data.

The binned diphoton invariant-mass spectrum (H->gamma-gamma channel) around 125 GeV. The
2-GeV-binned counts below were reconstructed offline from the full 2016 ATLAS Open Data
photon ntuples (CERN Open Data record 15006, CC0): ~7.8M events, standard photon selection,
m(gamma-gamma) computed per event. Here we fit an exponential-polynomial background plus a
Gaussian signal (in the browser) and show the classic spectrum + background-subtracted residual,
where the ~125 GeV excess stands clear of the sidebands. A reconstruction, not the official
ATLAS figure.
"""

import altair as alt
import numpy as np
import polars as pl
from scipy.optimize import curve_fit

import dysonsphere as ds
from dysonsphere.palettes import colors

# binned diphoton spectrum: bin center m (GeV), event count in a 2-GeV bin
MASS = [
    101, 103, 105, 107, 109, 111, 113, 115, 117, 119, 121, 123, 125, 127, 129,
    131, 133, 135, 137, 139, 141, 143, 145, 147, 149, 151, 153, 155, 157, 159,
]
COUNT = [
    6833, 6427, 6006, 5590, 5218, 4876, 4486, 4241, 3890, 3662, 3505, 3254, 3186, 2919, 2658,
    2483, 2388, 2266, 2078, 1945, 1944, 1869, 1694, 1634, 1508, 1413, 1358, 1272, 1157, 1106,
]

mass = np.array(MASS, dtype=float)
count = np.array(COUNT, dtype=float)
err = np.sqrt(count)


def background(m, p0, p1, p2, p3):
    t = (m - 125.0) / 25.0
    return np.exp(p0 + p1 * t + p2 * t**2 + p3 * t**3)


def signal(m, a, mu, sigma):
    return a * np.exp(-0.5 * ((m - mu) / sigma) ** 2)


def total(m, p0, p1, p2, p3, a, mu, sigma):
    return background(m, p0, p1, p2, p3) + signal(m, a, mu, sigma)


p0 = [np.log(count.max()), -1.0, 0.0, 0.0, count.max() * 0.15, 125.0, 1.6]
bounds = ([-20, -20, -20, -20, 0, 123, 1.2], [20, 20, 20, 20, count.max(), 128, 4.0])
popt, _ = curve_fit(total, mass, count, p0=p0, sigma=err, absolute_sigma=True, bounds=bounds, maxfev=100000)
bg_p = popt[:4]
a, mu, sigma = popt[4:]

mf = np.linspace(mass.min() - 1, mass.max() + 1, 400)
curves = pl.DataFrame({"mass": mf, "sb": total(mf, *popt), "bo": background(mf, *bg_p), "sig": signal(mf, a, mu, sigma)})
binned = pl.DataFrame({
    "mass": mass, "count": count, "lo": count - err, "hi": count + err,
    "resid": count - background(mass, *bg_p),
    "rlo": count - background(mass, *bg_p) - err,
    "rhi": count - background(mass, *bg_p) + err,
})

ds.theme()
dark = bool(alt.theme.options.get("darkmode"))  # the site injects darkmode per light/dark spec
ink = "white" if dark else "black"  # data markers, darkmode-aware
W = 210
RED = colors["pinksblues"][0]  # signal + background curve (an ATLAS-red homage; reads on both modes)
GREY = colors["greys"][4] if dark else colors["greys"][7]  # background-only + zero line, darkmode-aware
xscale = alt.Scale(domain=[float(mass.min()) - 2, float(mass.max()) + 2], nice=False)

# proper error bars: dashed stems, no caps
EB = dict(ticks=False, rule=alt.MarkConfig(strokeDash=[3, 2]))

# --- top panel: spectrum (no x-axis; the shared axis shows on the bottom panel only) ---
x_top = alt.X("mass:Q", scale=xscale, axis=alt.Axis(title=None, labels=False, ticks=False, domain=False))
base_top = alt.Chart(binned).encode(x=x_top)
ebars = base_top.mark_errorbar(**EB).encode(y=alt.Y("lo:Q", title="Events / 2 GeV"), y2="hi:Q")
pts = base_top.mark_point(filled=True, color=ink).encode(y="count:Q")
sb_line = alt.Chart(curves).mark_line(color=RED).encode(x=x_top, y="sb:Q")
bo_line = alt.Chart(curves).mark_line(color=GREY, strokeDash=[4, 3]).encode(x=x_top, y="bo:Q")
top = (bo_line + sb_line + ebars + pts).properties(width=W, height=125)

# --- bottom panel: background-subtracted residual (the bump) ---
yscale_bot = alt.Scale(domain=[-200, 200], nice=False)


def y_bot(field):
    # identical y spec on every layer so the shared axis keeps its title + tick values
    return alt.Y(field, title="Data − bkg", scale=yscale_bot, axis=alt.Axis(values=[-200, -100, 0, 100, 200]))


zero_df = pl.DataFrame({"y": [0.0], "mass": [float(mass.min())], "mass2": [float(mass.max())]})
zero = alt.Chart(zero_df).mark_rule(color=GREY).encode(x=alt.X("mass:Q", scale=xscale), x2="mass2:Q", y=y_bot("y:Q"))
base_bot = alt.Chart(binned).encode(x=alt.X("mass:Q", scale=xscale, title="m(γγ)  [GeV]"))
rbars = base_bot.mark_errorbar(**EB).encode(y=y_bot("rlo:Q"), y2="rhi:Q")
rpts = base_bot.mark_point(filled=True, color=ink).encode(y=y_bot("resid:Q"))
sig_line = alt.Chart(curves).mark_line(color=RED).encode(x=alt.X("mass:Q", scale=xscale), y=y_bot("sig:Q"))
bottom = (zero + sig_line + rbars + rpts).properties(width=W, height=70)

chart = alt.vconcat(top, bottom, spacing=6).resolve_scale(x="shared")
