from typing import Any

import altair as alt
import numpy as np
import polars as pl

from .utils import ensure_polars


def beeswarm_offsets(
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
                pl.Series("beeswarm_x", ds.beeswarm_offsets(
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
        heightPx = alt.theme.options.get("chartHeight", 300)
    if spread is None:
        spread = np.sqrt(alt.theme.options.get("markSize", 10) / np.pi)

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


def add_beeswarm(
    df: pl.DataFrame | Any,
    yCol: str,
    groupBy: list[str],
    heightPx: int | None = None,
    spread: float | None = None,
    outCol: str = "beeswarm_x",
) -> pl.DataFrame:
    """
    Add a beeswarm x-offset column to a Polars DataFrame, computed per group.

    A convenience wrapper around :func:`beeswarm_offsets` that handles the
    ``with_row_index`` / ``map_groups`` / ``sort`` / ``drop`` pattern.

    ``spread`` is the collision radius in pixels — set it to roughly half the
    rendered point diameter for non-overlapping points.  The total horizontal
    width of the beeswarm grows with n.

    Parameters
    ----------
    df:
        Input DataFrame.
    yCol:
        Name of the column containing y values.
    groupBy:
        Column name(s) that define each beeswarm group.
    heightPx:
        Chart height in pixels.
    spread:
        Collision radius in pixels. Defaults to ``sqrt(markSize / π)`` from
        the active theme, so points naturally match the rendered mark size.
    outCol:
        Name of the output offset column added to the DataFrame.

    Returns
    -------
    polars.DataFrame
        Original DataFrame with an additional ``outCol`` column.

    Examples
    --------
    ::

        df = ds.add_beeswarm(df, yCol="value", groupBy=["group"], spread=2.0)

        alt.Chart(df).mark_circle().encode(
            x=alt.X("group:N"),
            y=alt.Y("value:Q"),
            xOffset=alt.XOffset("beeswarm_x:Q"),
        )
    """
    df = ensure_polars(df)
    return (
        df.with_row_index("__beeswarm_idx")
        .group_by(groupBy)
        .map_groups(
            lambda g: g.with_columns(
                pl.Series(
                    outCol,
                    beeswarm_offsets(
                        g[yCol].to_numpy(),
                        heightPx=heightPx,
                        spread=spread,
                    ),
                )
            )
        )
        .sort("__beeswarm_idx")
        .drop("__beeswarm_idx")
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
        w = alt.theme.options.get("chartWidth", 100)
        h = alt.theme.options.get("chartHeight", 100)
        spread = min(w, h) / 50
    rng = np.random.default_rng(seed)
    return df.with_columns(pl.Series(outCol, rng.normal(0, spread, len(df))))
