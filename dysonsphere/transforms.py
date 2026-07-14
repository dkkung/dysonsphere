from collections.abc import Callable
from typing import Any

import numpy as np
import polars as pl
from scipy.stats import gaussian_kde

from .theme import _opt
from .utils import ensure_polars

# The module's public API - star-imported into the dysonsphere namespace. Everything
# else here is internal (underscore or not); keep this list in sync with __init__.__all__.
__all__ = ["add_jitter", "add_beeswarm", "add_quasirandom"]


def _beeswarm_offsets(
    yVals,
    heightPx: int | None = None,
    spread: float | None = None,
) -> np.ndarray:
    """
    Compute x offsets (pixels) for a beeswarm plot using collision avoidance.

    Algorithm
    ---------
    1. Map y values linearly to pixel space over ``[0, heightPx]``.
    2. Sort points by y-pixel position (ascending).
    3. For each point, try x = 0, then ±step, ±2·step, … until a position is
       found where no already-placed point is within distance 2·spread (i.e.
       the circles do not overlap).
    4. Return the accepted x offsets in the original row order.

    ``spread`` is the collision radius in pixels — visually, the half-width of
    each point in the offset axis.  The total beeswarm width is emergent:
    it grows with n and shrinks with spread.

    Parameters
    ----------
    yVals:
        Array of y values for one group.
    heightPx:
        Chart height in pixels. Should match ``.properties(height=...)``.
    spread:
        Collision radius in pixels. Points are placed so no two centres are
        closer than ``2 * spread``. Defaults to 2.0.
    step:
        x step size (px) between candidate positions. Defaults to ``spread``
        so the candidate grid aligns with the point diameter.

    Returns
    -------
    numpy.ndarray
        x offsets in pixels, one per input value, in the same order.

    Examples
    --------
    Compute offsets per group with Polars then plot in Altair::

        df = (
            df
            .with_row_index("__idx")
            .group_by(["group", "time"])
            .map_groups(lambda g: g.with_columns(
                pl.Series("beeswarm_x", dysonsphere.transforms._beeswarm_offsets(
                    g["value"].to_numpy(),
                    heightPx=200,
                    spread=2.0,
                ))
            ))
            .sort("__idx")
            .drop("__idx")
        )

        alt.Chart(df).mark_circle().encode(
            x=alt.X("time:O"),
            y=alt.Y("value:Q"),
            xOffset=alt.XOffset("beeswarm_x:Q"),
        )
    """
    if heightPx is None:
        heightPx = _opt("chartHeight")
    if spread is None:
        spread = np.sqrt(_opt("markSize") / np.pi)

    yVals = np.asarray(yVals, dtype=float)
    n = len(yVals)
    if n == 0:
        return np.array([])

    r = spread
    d = 2 * r  # minimum centre-to-centre distance

    y_min, y_max = yVals.min(), yVals.max()
    y_px = (yVals - y_min) / max(y_max - y_min, 1e-9) * heightPx

    order = np.argsort(y_px)
    placed_y = np.empty(n)
    placed_x = np.empty(n)
    offsets = np.zeros(n)
    n_placed = 0

    for idx in order:
        y = y_px[idx]

        # For each already-placed point within vertical range, compute the
        # forbidden x interval: placed_x[j] ± sqrt((2r)² - dy²).
        # The optimal x is the candidate closest to 0 outside all intervals.
        candidates = [0.0]
        for j in range(n_placed):
            dy = abs(placed_y[j] - y)
            if dy >= d:
                continue
            half = np.sqrt(d**2 - dy**2)
            candidates.append(placed_x[j] + half)
            candidates.append(placed_x[j] - half)

        # Pick the candidate closest to 0 that doesn't overlap any placed point.
        candidates.sort(key=abs)
        for cx in candidates:
            dists_sq = (placed_y[:n_placed] - y) ** 2 + (placed_x[:n_placed] - cx) ** 2  # ty: ignore[unsupported-operator]
            if n_placed == 0 or np.all(dists_sq >= d**2 - 1e-9):
                placed_y[n_placed] = y
                placed_x[n_placed] = cx
                n_placed += 1
                offsets[idx] = cx
                break

    return offsets


def _van_der_corput(n: int, base: int = 2) -> np.ndarray:
    """First ``n`` elements of the base-``base`` van der Corput low-discrepancy sequence, in (0, 1).

    The sequence 0.5, 0.25, 0.75, 0.125, ... fills the unit interval evenly: consecutive elements
    land far apart, so points assigned consecutive values spread to alternating sides rather than
    clumping. This is the deterministic core of :func:`_quasirandom_offsets`.

    Vectorised over all ``n`` indices at once; the loop runs only over base-``base`` digits
    (~log(n) iterations), so it is effectively O(n log n) in numpy, not a per-element Python loop.
    """
    idx = np.arange(1, n + 1)
    seq = np.zeros(n, dtype=float)
    denom = 1.0
    while idx.any():
        denom *= base
        seq += (idx % base) / denom
        idx //= base
    return seq


def _quasirandom_offsets(
    yVals,
    heightPx: int | None = None,
    spread: float | None = None,
    width: float | None = None,
    bandwidth: float | None = None,
) -> np.ndarray:
    """
    Compute x offsets (pixels) for a quasirandom beeswarm (the vipor ``geom_quasirandom`` method).

    Unlike :func:`_beeswarm_offsets` (which solves collisions exactly), this spreads points
    *statistically* by local density: the swarm takes a violin/lens outline (wide where the data
    is dense, narrow in the tails), and within that width points are placed by a van der Corput
    low-discrepancy sequence assigned in y-order, so adjacent-y points fan to opposite sides.
    Fully deterministic (KDE + van der Corput, no RNG), so figures are reproducible. It does NOT
    guarantee non-overlap - the trade for a symmetric, evenly-textured spread.

    Algorithm
    ---------
    1. Estimate the value-axis density with a Gaussian KDE; normalise to ``[0, 1]`` per point.
    2. Assign each point (in ascending-y order) the next van der Corput value, mapped to ``[-1, 1]``.
    3. Scale each by its local density (the lens width) and ``width`` (the peak half-width in px).
    4. Recentre the group on its midrange so it sits symmetric about the tick (a rigid shift - safe,
       since there are no solved collisions to disturb - keeping the swarm's left/right extremes
       equidistant from the tick and lifting small even-count groups off the centre line, the swarm
       method's lopsided-even-row artifact).

    Parameters
    ----------
    yVals:
        Array of y values for one group.
    heightPx:
        Chart height in pixels. Used to size the auto ``width`` window. Defaults to the theme's
        ``chartHeight``.
    spread:
        Point radius in pixels - the unit the auto ``width`` is built from. Defaults to
        ``sqrt(markSize / pi)`` from the active theme (matching :func:`_beeswarm_offsets`).
    width:
        Peak half-width of the swarm in pixels (the spread at maximum density). ``None`` (default)
        auto-sizes it to ``spread * peak``, where ``peak`` is the most points falling within any
        ``2 * spread`` tall vertical window - so the densest region lands on roughly the same
        footprint the ``"swarm"`` method would produce.
    bandwidth:
        KDE bandwidth, forwarded to ``scipy.stats.gaussian_kde(bw_method=...)``. ``None`` (default)
        uses Scott's rule; a smaller value tracks the data more tightly, a larger one smooths it.

    Returns
    -------
    numpy.ndarray
        x offsets in pixels, one per input value, in the same order.
    """
    if heightPx is None:
        heightPx = _opt("chartHeight")
    if spread is None:
        spread = np.sqrt(_opt("markSize") / np.pi)

    y = np.asarray(yVals, dtype=float)
    n = len(y)
    if n == 0:
        return np.array([])
    if n == 1:
        return np.array([0.0])

    y_min, y_max = y.min(), y.max()
    y_px = (y - y_min) / max(y_max - y_min, 1e-9) * heightPx

    # Relative local density (the lens width). A degenerate (zero-variance) group has no KDE, so
    # treat it as uniform - every point at the same y spreads across the full width.
    if y_max - y_min < 1e-9:
        dens = np.ones(n)
    else:
        dens = gaussian_kde(y, bw_method=bandwidth)(y)
    dens = dens / dens.max()

    # Auto width: match the swarm's footprint. peak = the most points within one 2*spread-tall
    # window (a swarm "row"); at that density the van der Corput fills +/- spread*peak, giving
    # ~one-diameter horizontal spacing - the same extent the swarm's row would occupy. Vectorised:
    # for each point (sorted), searchsorted finds the window's low edge, so the count is O(n log n).
    if width is None:
        sorted_px = np.sort(y_px)
        lo = np.searchsorted(sorted_px, sorted_px - 2 * spread, side="left")
        peak = int((np.arange(n) - lo + 1).max())
        width = spread * peak

    order = np.argsort(y_px, kind="stable")
    centered = 2.0 * _van_der_corput(n) - 1.0  # (-1, 1), low-discrepancy
    offsets = np.empty(n)
    offsets[order] = centered
    offsets = offsets * dens * width
    # Centre on the midrange: a rigid, overlap-safe shift that seats the swarm's left/right extremes
    # equidistant from the tick (symmetric outline) and lifts small even-count groups off centre.
    return offsets - (offsets.max() + offsets.min()) / 2


def _grouped_offsets(
    df: pl.DataFrame,
    yCol: str,
    groupBy: list[str],
    outCol: str,
    offset_fn: "Callable[[np.ndarray], np.ndarray]",
) -> pl.DataFrame:
    """Apply a per-group offset function over ``yCol`` and attach the result as ``outCol``.

    Shared ``with_row_index`` / ``group_by`` / ``map_groups`` / ``sort`` / ``drop`` plumbing for
    :func:`add_beeswarm` and :func:`add_quasirandom` (both compute one x-offset per row, per group).
    """
    return (
        df.with_row_index("__offset_idx")
        .group_by(groupBy)
        .map_groups(lambda g: g.with_columns(pl.Series(outCol, offset_fn(g[yCol].to_numpy()))))
        .sort("__offset_idx")
        .drop("__offset_idx")
    )


def add_beeswarm(
    df: pl.DataFrame | Any,
    yCol: str,
    groupBy: list[str],
    heightPx: int | None = None,
    spread: float | None = None,
    outCol: str = "beeswarm_x",
) -> pl.DataFrame:
    """
    Add a swarm beeswarm x-offset column to a Polars DataFrame, computed per group.

    Wraps :func:`_beeswarm_offsets` (the greedy exact-collision "swarm" layout, R
    ggbeeswarm's ``geom_beeswarm(method="swarm")``): every point is guaranteed
    non-overlapping. The trade is that tightly-packed rows can look lopsided (an
    even-count row parks a point on the tick, lone points get pushed to one side) -
    inherent to the swarm algorithm. For a symmetric, density-shaped alternative that
    allows mild overlap, see :func:`add_quasirandom`.

    ``spread`` is the collision radius in pixels - set it to roughly half the rendered
    point diameter for non-overlapping points. The total horizontal width is emergent
    and grows with n.

    Parameters
    ----------
    df:
        Input DataFrame.
    yCol:
        Name of the column containing y values.
    groupBy:
        Column name(s) that define each beeswarm group.
    heightPx:
        Chart height in pixels. Defaults to the theme's ``chartHeight``.
    spread:
        Collision radius in pixels. Defaults to ``sqrt(markSize / π)`` from the active
        theme, so points naturally match the rendered mark size.
    outCol:
        Name of the output offset column added to the DataFrame.

    Returns
    -------
    polars.DataFrame
        Original DataFrame with an additional ``outCol`` column.

    Examples
    --------
    ::

        df = ds.add_beeswarm(df, yCol="value", groupBy=["group"])
        m = df["beeswarm_x"].abs().max()  # pin a symmetric xOffset domain so offset 0 sits on the tick

        alt.Chart(df).mark_circle().encode(
            x=alt.X("group:N"),
            y=alt.Y("value:Q"),
            xOffset=alt.XOffset("beeswarm_x:Q", scale=alt.Scale(domain=[-m, m])),
        )

    Without the symmetric ``domain``, Vega-Lite centres the tick on the offset range's midpoint,
    so a leaning swarm renders slightly off the tick (``mark_strip`` pins this domain for you).
    """
    df = ensure_polars(df)
    return _grouped_offsets(df, yCol, groupBy, outCol, lambda y: _beeswarm_offsets(y, heightPx=heightPx, spread=spread))


def add_quasirandom(
    df: pl.DataFrame | Any,
    yCol: str,
    groupBy: list[str],
    heightPx: int | None = None,
    spread: float | None = None,
    outCol: str = "quasirandom_x",
    width: float | None = None,
    bandwidth: float | None = None,
) -> pl.DataFrame:
    """
    Add a quasirandom x-offset column to a Polars DataFrame, computed per group.

    Wraps :func:`_quasirandom_offsets` - a density-scaled quasirandom spread (van der
    Corput low-discrepancy sequence weighted by a Gaussian KDE), R ggbeeswarm's
    ``geom_quasirandom``. It gives a symmetric, violin-shaped swarm that stays centred
    on the tick, sidestepping :func:`add_beeswarm`'s lopsided tightly-packed rows. Fully
    deterministic (no RNG), so figures reproduce. The trade is that it does NOT guarantee
    non-overlap - the cost of the smoother, symmetric look. It is the better choice for
    large or heavily-tied groups; use :func:`add_beeswarm` for small groups where exact
    non-overlap matters.

    Parameters
    ----------
    df:
        Input DataFrame.
    yCol:
        Name of the column containing y values.
    groupBy:
        Column name(s) that define each group.
    heightPx:
        Chart height in pixels. Defaults to the theme's ``chartHeight``.
    spread:
        Point radius in pixels - the unit the auto ``width`` is built from. Defaults to
        ``sqrt(markSize / π)`` from the active theme, matching :func:`add_beeswarm`.
    outCol:
        Name of the output offset column added to the DataFrame.
    width:
        Peak half-width of the swarm in pixels. ``None`` (default) auto-sizes it to the
        swarm's footprint (see :func:`_quasirandom_offsets`).
    bandwidth:
        KDE bandwidth (``gaussian_kde`` ``bw_method``). ``None`` (default) uses Scott's rule.

    Returns
    -------
    polars.DataFrame
        Original DataFrame with an additional ``outCol`` column.

    Examples
    --------
    ::

        df = ds.add_quasirandom(df, yCol="value", groupBy=["group"])
        m = df["quasirandom_x"].abs().max()  # pin a symmetric xOffset domain so offset 0 sits on the tick

        alt.Chart(df).mark_circle().encode(
            x=alt.X("group:N"),
            y=alt.Y("value:Q"),
            xOffset=alt.XOffset("quasirandom_x:Q", scale=alt.Scale(domain=[-m, m])),
        )
    """
    df = ensure_polars(df)
    return _grouped_offsets(
        df,
        yCol,
        groupBy,
        outCol,
        lambda y: _quasirandom_offsets(y, heightPx=heightPx, spread=spread, width=width, bandwidth=bandwidth),
    )


def add_jitter(
    df: pl.DataFrame | Any,
    spread: float | None = None,
    outCol: str = "jitter_x",
    seed: int | None = 2022_07_01,
) -> pl.DataFrame:
    """
    Add a column of random Gaussian x-offsets to a Polars DataFrame.

    Each offset is drawn independently from N(0, spread²), where ``spread``
    is the standard deviation in pixels.  ~68% of points fall within
    ±spread of centre; ~95% within ±2·spread.  There is no collision
    avoidance — points can overlap.  Use :func:`add_beeswarm` instead for
    small n where overlap is undesirable.

    Parameters
    ----------
    df:
        Input DataFrame.
    spread:
        Standard deviation of the jitter in pixels. Defaults to
        ``min(chartWidth, chartHeight) / 50`` from the active theme (2.0 at
        the default 100×100 chart size).
    outCol:
        Name of the output offset column added to the DataFrame.
    seed:
        Optional random seed for reproducibility.

    Returns
    -------
    polars.DataFrame
        Original DataFrame with an additional ``outCol`` column.

    Examples
    --------
    ::

        df = ds.add_jitter(df, spread=5)

        alt.Chart(df).mark_circle().encode(
            x=alt.X("group:N"),
            y=alt.Y("value:Q"),
            xOffset=alt.XOffset("jitter_x:Q"),
        )
    """
    df = ensure_polars(df)
    if spread is None:
        w = _opt("chartWidth")
        h = _opt("chartHeight")
        spread = min(w, h) / 50
    rng = np.random.default_rng(seed)
    return df.with_columns(pl.Series(outCol, rng.normal(0, spread, len(df))))
