import polars as pl


def count_n(df: pl.DataFrame, xCol: str, categories: list[str]) -> list[int]:
    """
    Count the number of rows in ``df`` belonging to each category.

    Parameters
    ----------
    df:
        A ``polars.DataFrame`` or ``pandas.DataFrame``.
    xCol:
        Column name used for grouping (the x-axis column).
    categories:
        Ordered list of category labels; the returned counts follow this order.
        Categories with no matching rows return 0.

    Returns
    -------
    list[int]
        Per-category row counts in the same order as ``categories``.

    Examples
    --------
    ::

        counts = ds.count_n(df, "group", ["Control", "Group A", "Group B"])
        # [12, 15, 11]
    """
    df = ensure_polars(df)
    return [len(df.filter(pl.col(xCol) == cat)) for cat in categories]


def ensure_polars(df: pl.DataFrame) -> pl.DataFrame:
    """
    Convert a pandas DataFrame to Polars, or pass a Polars DataFrame through unchanged.

    Accepts either a ``polars.DataFrame`` or a ``pandas.DataFrame`` without
    requiring pandas as a hard dependency — the check is done via the module
    name only.  If ``df`` is neither, a ``TypeError`` is raised.

    Parameters
    ----------
    df:
        A ``polars.DataFrame`` or ``pandas.DataFrame``.

    Returns
    -------
    polars.DataFrame
        The original DataFrame if already Polars, otherwise the result of
        ``polars.from_pandas(df)``.

    Examples
    --------
    ::

        import pandas as pd
        pdf = pd.DataFrame({"group": ["A", "B"], "value": [1.0, 2.0]})
        pldf = ds.ensure_polars(pdf)  # returns a polars.DataFrame
    """
    if isinstance(df, pl.DataFrame):
        return df
    if type(df).__module__.startswith("pandas"):
        return pl.from_pandas(df)
    raise TypeError(f"Expected a polars.DataFrame or pandas.DataFrame, got {type(df).__name__}.")
