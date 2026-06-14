import altair as alt
import numpy as np
import polars as pl


def beeswarm_offsets(
    y_vals,
    height_px: int | None = None,
    markSize: float = 10,
    step: float | None = None,
) -> np.ndarray:
    """
    Compute x offsets (pixels) for a beeswarm plot using collision avoidance.

    Converts y values to pixel space, then places each point at the nearest
    x position (outward from 0) that does not overlap any already-placed point.
    Use the result as an ``xOffset`` column in Altair.

    Parameters
    ----------
    y_vals:
        Array of y values for one group (e.g. one treatment × time combination).
    height_px:
        Chart height in pixels. Should match ``.properties(height=...)``.
    markSize:
        Altair mark size (area in sq px). Should match the ``size=`` kwarg on
        the mark. Defaults to the theme's ``markSize`` default of 10.
    step:
        x step size (px) between candidate positions. Defaults to the point
        radius derived from ``markSize``.

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
            .group_by(["Metadata_Treatment", "Metadata_Time"])
            .map_groups(lambda g: g.with_columns(
                pl.Series("beeswarm_x", theme.beeswarm_offsets(
                    g["my_column"].to_numpy(),
                    height_px=200,
                    markSize=10,
                ))
            ))
            .sort("__idx")
            .drop("__idx")
        )

        alt.Chart(df).mark_circle(size=10).encode(
            x=alt.X("Metadata_Time:O"),
            y=alt.Y("my_column:Q"),
            xOffset=alt.XOffset("beeswarm_x:Q"),
        )
    """
    if height_px is None:
        height_px = alt.theme.options.get("chartHeight", 300)

    y_vals = np.asarray(y_vals, dtype=float)
    n = len(y_vals)
    if n == 0:
        return np.array([])

    r = np.sqrt(markSize / np.pi)
    if step is None:
        step = r

    y_min, y_max = y_vals.min(), y_vals.max()
    y_px = (y_vals - y_min) / max(y_max - y_min, 1e-9) * height_px

    min_dist_sq = (2 * r) ** 2
    order = np.argsort(y_px)
    placed_y = np.empty(n)
    placed_x = np.empty(n)
    offsets = np.zeros(n)
    n_placed = 0

    for idx in order:
        y = y_px[idx]
        nearby = np.abs(placed_y[:n_placed] - y) <= 4 * r
        for k in range(1000):
            for cx in [0.0] if k == 0 else [k * step, -k * step]:
                ny = placed_y[:n_placed][nearby]
                nx = placed_x[:n_placed][nearby]
                if len(ny) == 0 or np.all((ny - y) ** 2 + (nx - cx) ** 2 >= min_dist_sq):
                    placed_y[n_placed] = y
                    placed_x[n_placed] = cx
                    n_placed += 1
                    offsets[idx] = cx
                    break
            else:
                continue
            break

    return offsets


def add_beeswarm_offsets(
    df: pl.DataFrame,
    y_col: str,
    group_by: list[str],
    height_px: int | None = None,
    markSize: float = 10,
    step: float | None = None,
    out_col: str = "beeswarm_x",
) -> pl.DataFrame:
    """
    Add a beeswarm x-offset column to a Polars DataFrame, computed per group.

    A convenience wrapper around :func:`beeswarm_offsets` that handles the
    ``with_row_index`` / ``map_groups`` / ``sort`` / ``drop`` pattern.

    Parameters
    ----------
    df:
        Input DataFrame.
    y_col:
        Name of the column containing y values.
    group_by:
        Column name(s) that define each beeswarm group (e.g.
        ``["Metadata_Treatment", "Metadata_Time"]``).
    height_px:
        Chart height in pixels.
    markSize:
        Altair mark size (area in sq px).
    step:
        x step size (px). Defaults to the point radius.
    out_col:
        Name of the output offset column added to the DataFrame.

    Returns
    -------
    polars.DataFrame
        Original DataFrame with an additional ``out_col`` column.

    Examples
    --------
    ::

        df = theme.add_beeswarm_offsets(
            df,
            y_col="percent",
            group_by=["Metadata_Treatment", "Metadata_Time"],
            height_px=200,
            markSize=10,
        )

        alt.Chart(df).mark_circle(size=10).encode(
            x=alt.X("Metadata_Time:O"),
            y=alt.Y("percent:Q"),
            xOffset=alt.XOffset("beeswarm_x:Q"),
        )
    """
    return (
        df.with_row_index("__beeswarm_idx")
        .group_by(group_by)
        .map_groups(
            lambda g: g.with_columns(
                pl.Series(
                    out_col,
                    beeswarm_offsets(
                        g[y_col].to_numpy(),
                        height_px=height_px,
                        markSize=markSize,
                        step=step,
                    ),
                )
            )
        )
        .sort("__beeswarm_idx")
        .drop("__beeswarm_idx")
    )


def add_jitter_offsets(
    df: pl.DataFrame,
    scale: float = 5.0,
    out_col: str = "jitter_x",
    seed: int | None = 2022_07_01,
) -> pl.DataFrame:
    """
    Add a column of random Gaussian x-offsets to a Polars DataFrame.

    Each point receives an independent offset drawn from N(0, scale). Use the
    result as an ``xOffset`` column in Altair to jitter points horizontally.

    Unlike :func:`add_beeswarm_offsets`, there is no collision avoidance —
    points can overlap. This is faster and simpler for large datasets where
    some overlap is acceptable.

    Parameters
    ----------
    df:
        Input DataFrame.
    scale:
        Standard deviation of the jitter in pixels.
    out_col:
        Name of the output offset column added to the DataFrame.
    seed:
        Optional random seed for reproducibility.

    Returns
    -------
    polars.DataFrame
        Original DataFrame with an additional ``out_col`` column.

    Examples
    --------
    ::

        df = theme.add_jitter_offsets(df, scale=5)

        alt.Chart(df).mark_circle().encode(
            x=alt.X("group:N"),
            y=alt.Y("value:Q"),
            xOffset=alt.XOffset("jitter_x:Q"),
        )
    """
    rng = np.random.default_rng(seed)
    return df.with_columns(pl.Series(out_col, rng.normal(0, scale, len(df))))
