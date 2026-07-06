import math

import altair as alt

from .theme import _opt
from .utils import ensure_polars

# The module's public API - star-imported into the dysonsphere namespace. Everything
# else here is internal (underscore or not); keep this list in sync with __init__.__all__.
__all__ = ["log_label_expr", "add_log_ticks", "add_pow_ticks"]

# ---------------------------------------------------------------------------
# Log-scale axis label helper
# ---------------------------------------------------------------------------

_SUP = "⁰¹²³⁴⁵⁶⁷⁸⁹"


def log_label_expr(base: int = 10, notation: str = "power") -> str:
    """Return a Vega ``labelExpr`` string for base-N log-scale axis labels.

    Four notations are available:

    - ``"power"`` (default): e.g. ``10⁴``, ``2⁻³``, ``2²⁰``.
      Works for any integer base.
    - ``"scientific"``: e.g. ``1×10⁴``, ``1×10⁻³``.
      Base-10 only. Assumes tick values are exact powers of 10 so the
      mantissa is always ``1``; raises ``ValueError`` for other bases.
    - ``"e"``: e.g. ``1e+4``, ``1e-3``.
      Base-10 only. Uses Vega's ``format(datum.value, '.0e')`` internally.
      Best suited for axes whose ``values=`` are exact powers of 10.
    - ``"si"``: e.g. ``10k``, ``1M``, ``100µ``.
      Base-10 only. Uses Vega's ``format(datum.value, '~s')`` internally;
      trims insignificant trailing zeros automatically.

    Supports exponents up to ±99 for ``"power"`` and ``"scientific"``.
    Pass the return value directly to ``alt.Axis(labelExpr=...)``.

    Parameters
    ----------
    base:
        Logarithm base. Defaults to ``10``.
    notation:
        ``"power"`` (default), ``"scientific"``, ``"e"``, or ``"si"``.
        All notations except ``"power"`` require ``base=10``.

    Examples
    --------
    ::

        # power notation — base-10 y-axis: 10⁴, 10⁵, 10⁶, …
        axis=alt.Axis(
            values=[10**e for e in range(4, 8)],
            labelExpr=ds.log_label_expr(),
        )

        # power notation — log2 x-axis: 2⁰, 2¹, …, 2²⁰
        axis=alt.Axis(
            values=[2**e for e in range(0, 21)],
            labelExpr=ds.log_label_expr(base=2),
        )

        # scientific notation — base-10 y-axis: 1×10⁴, 1×10⁵, 1×10⁶, …
        axis=alt.Axis(
            values=[10**e for e in range(4, 8)],
            labelExpr=ds.log_label_expr(notation="scientific"),
        )

        # e-notation — base-10 y-axis: 1e+4, 1e+5, 1e+6, …
        axis=alt.Axis(
            values=[10**e for e in range(4, 8)],
            labelExpr=ds.log_label_expr(notation="e"),
        )

        # SI prefix notation — base-10 y-axis: 10k, 100k, 1M, …
        axis=alt.Axis(
            values=[10**e for e in range(4, 8)],
            labelExpr=ds.log_label_expr(notation="si"),
        )
    """
    if notation not in ("power", "scientific", "e", "si"):
        raise ValueError(f"notation must be 'power', 'scientific', 'e', or 'si', got {notation!r}")
    if notation != "power" and base != 10:
        raise ValueError(f"notation={notation!r} is only defined for base=10.")

    # Vega expression building blocks. abs_exp must be written out in full each
    # time it appears — Vega's restricted expression language has no variable
    # binding, so intermediate values cannot be assigned to names.
    e = f"round(log(datum.value) / log({base}))"
    ae = f"abs(round(log(datum.value) / log({base})))"
    sup = f"'{_SUP}'"
    # two-digit superscript lookup (handles exponents 10–99)
    two = f"({ae} >= 10 ? {sup}[floor({ae}/10)] + {sup}[{ae}%10] : {sup}[{ae}])"

    if notation == "e":
        return "format(datum.value, '.0e')"

    if notation == "si":
        return "format(datum.value, '~s')"

    if notation == "scientific":
        # Mantissa is always 1 because tick values are expected to be exact powers of 10.
        return f"'1×10' + ({e} < 0 ? '⁻' + {two} : {two})"

    # Power notation: b^n
    b = str(base)
    return f"{e} < 0 ? '{b}⁻' + {two} : '{b}' + {two}"


# ---------------------------------------------------------------------------
# Log-scale minor ticks
# ---------------------------------------------------------------------------


def _minor_tick_layer(
    df,
    field: str,
    axis: str,
    minor_values: list[float],
    scale: alt.Scale,
    minor_tick_size: float,
) -> alt.Chart:
    """The invisible minor-tick layer shared by the log and pow constructors.

    A zero-opacity point mark carrying a second axis that draws only unlabeled ticks at
    ``minor_values``. The ``scale`` must set an explicit domain - without it Vega auto-fits
    the independent scale to the data extent, dropping partial edge intervals. The caller
    layers it over the main chart with ``resolve_axis(...="independent")``.
    """
    minor_axis = alt.Axis(
        values=minor_values,
        labels=False,
        domain=False,
        grid=False,
        ticks=True,
        tickSize=minor_tick_size,
        orient="bottom" if axis == "x" else "left",
    )
    layer = alt.Chart(df).mark_point(opacity=0)
    if axis == "y":
        return layer.encode(y=alt.Y(f"{field}:Q", title=None, scale=scale, axis=minor_axis))
    return layer.encode(x=alt.X(f"{field}:Q", title=None, scale=scale, axis=minor_axis))


def _log_minor_layer(
    df,
    field: str,
    axis: str,
    exp_min: int,
    exp_max: int,
    minor_tick_size: float,
    base: int = 10,
    nMinor: int = 1,
) -> alt.Chart:
    if base == 10:
        minor_values = [m * 10**e for e in range(exp_min, exp_max) for m in range(2, 10)]
    else:
        n_divs = nMinor + 1
        minor_values = [base ** (e + k / n_divs) for e in range(exp_min, exp_max) for k in range(1, n_divs)]
    scale = alt.Scale(type="log", base=base, domain=[base**exp_min, base**exp_max])
    return _minor_tick_layer(df, field, axis, minor_values, scale, minor_tick_size)


def _derive_exp(df, field: str, base: int = 10) -> tuple[int, int]:
    col_min = float(df[field].min())
    col_max = float(df[field].max())
    log = math.log10 if base == 10 else lambda x: math.log(x, base)
    return int(math.floor(log(col_min))), int(math.ceil(log(col_max)))


def _infer_field(chart, axis: str) -> str | None:
    """Best-effort field name from a plain ``alt.Chart``'s x/y encoding shorthand.

    Reads ``chart.encoding.<axis>._kwds["shorthand"]`` (the ``.field`` accessor returns a
    ``_PropertySetter`` descriptor, not the value) and strips the ``:Q`` type suffix.
    Returns ``None`` when the field can't be recovered — a ``LayerChart`` (no top-level
    encoding), a missing/complex channel, or an aggregate/expression shorthand — so the
    caller falls back to requiring an explicit ``field=``.
    """
    enc = getattr(chart, "encoding", alt.Undefined)
    channel = getattr(enc, axis, alt.Undefined) if enc is not alt.Undefined else alt.Undefined
    shorthand = getattr(channel, "_kwds", {}).get("shorthand") if channel is not alt.Undefined else None
    if not isinstance(shorthand, str):
        return None
    name = shorthand.split(":")[0]
    # Reject aggregates/expressions (e.g. "mean(x)", "count()") — not a plain column.
    return name if name and "(" not in name else None


def add_log_ticks(
    chart: alt.Chart | alt.LayerChart,
    df,
    field: str | None = None,
    *,
    axis: str = "y",
    base: int = 10,
    nMinor: int = 1,
    expMin: int | None = None,
    expMax: int | None = None,
    xField: str | None = None,
    yField: str | None = None,
    xExpMin: int | None = None,
    xExpMax: int | None = None,
    yExpMin: int | None = None,
    yExpMax: int | None = None,
    minorTickSize: float | None = None,
) -> alt.LayerChart:
    """
    Add unlabeled minor ticks to a log-scale axis.

    Wraps ``chart`` in a layer carrying a second axis of minor ticks.
    The main chart's scale domain is unaffected.

    For ``base=10`` the minor ticks are placed at the 2×–9× integer
    multiples within each decade — the conventional scientific log tick
    pattern. For other bases (e.g. ``base=2``) ticks are placed at
    ``nMinor`` equally-spaced positions (in log space) per interval,
    defaulting to one tick at the geometric midpoint per octave.

    Works with ``alt.Chart``, ``alt.LayerChart``, and any chart type
    composable with ``alt.layer()``. Also works correctly in ``hconcat``
    and ``vconcat`` layouts.

    .. note::
        Minor tick positions are exact at render time (the theme config
        disables Vega's integer tick rounding), so they are correct in
        any renderer. Still prefer ``ds.save()`` over ``chart.save()``
        for the other SVG corrections (grid span, superscript labels)
        and the embedded metadata.

    Parameters
    ----------
    chart:
        The chart to add minor ticks to.
    df:
        DataFrame (Polars or Pandas) used for the main chart.
    field:
        Column name of the log-scale field. When ``axis`` is ``'x'`` or
        ``'y'`` and this is ``None``, it is inferred from the chart's
        matching encoding shorthand (``chart.encoding.x`` / ``.y``); pass
        it explicitly for a ``LayerChart`` (no top-level encoding) or an
        aggregate/expression encoding, where inference is not possible.
        Omit when ``axis='both'`` and use ``xField`` / ``yField`` instead.
    axis:
        ``'x'``, ``'y'`` (default), or ``'both'``. When ``'both'``,
        ``xField`` and ``yField`` must be provided.
    base:
        Logarithm base matching the axis scale. Defaults to ``10``.
        Use ``2`` for log2 axes (e.g. volcano plots, fold-change axes).
        Any integer ≥ 2 is accepted.
    nMinor:
        Number of minor ticks per major interval for non-base-10 scales.
        Ignored when ``base=10`` (which always uses the 2×–9× pattern).
        Defaults to ``1`` (one tick at the geometric midpoint per
        interval). Use ``3`` for quarter-interval ticks.
    expMin:
        Lowest exponent (in the given ``base``) for the single-axis
        case. Auto-derived from ``df[field].min()`` when ``None``.
    expMax:
        Highest exponent. Auto-derived from ``df[field].max()`` when
        ``None``.
    xField:
        Column name for the x log-scale field (``axis='both'`` only).
    yField:
        Column name for the y log-scale field (``axis='both'`` only).
    xExpMin, xExpMax:
        Exponent overrides for the x axis (``axis='both'`` only).
    yExpMin, yExpMax:
        Exponent overrides for the y axis (``axis='both'`` only).
    minorTickSize:
        Length of minor ticks in pixels. Defaults to half the active
        theme's ``tickSize`` (``tickSize / 2``; typically ``1.5`` when
        the default ``tickSize=3`` is in effect).

    Examples
    --------
    ::

        # log10 y-axis — exp range auto-derived
        chart = ds.add_log_ticks(chart, df, "value")

        # log2 x-axis (e.g. fold-change on a volcano plot)
        chart = ds.add_log_ticks(chart, df, "fc", axis="x", base=2)

        # log2 with 3 minor ticks per octave
        chart = ds.add_log_ticks(chart, df, "fc", axis="x", base=2, nMinor=3)

        # both axes log-scaled
        chart = ds.add_log_ticks(
            chart, df, axis="both", xField="fc", yField="pvalue"
        )
    """
    if axis not in ("x", "y", "both"):
        raise ValueError(f"axis must be 'x', 'y', or 'both', got {axis!r}")

    if minorTickSize is None:
        minorTickSize = _opt("tickSize") / 2

    df = ensure_polars(df)

    if axis == "both":
        if xField is None or yField is None:
            raise ValueError("axis='both' requires xField and yField.")
        x_lo, x_hi = _derive_exp(df, xField, base)
        y_lo, y_hi = _derive_exp(df, yField, base)
        x_lo = xExpMin if xExpMin is not None else x_lo
        x_hi = xExpMax if xExpMax is not None else x_hi
        y_lo = yExpMin if yExpMin is not None else y_lo
        y_hi = yExpMax if yExpMax is not None else y_hi
        x_layer = _log_minor_layer(df, xField, "x", x_lo, x_hi, minorTickSize, base, nMinor)
        y_layer = _log_minor_layer(df, yField, "y", y_lo, y_hi, minorTickSize, base, nMinor)
        return alt.layer(chart, x_layer, y_layer).resolve_axis(x="independent", y="independent")

    if field is None:
        field = _infer_field(chart, axis)
    if field is None:
        raise ValueError(
            f"field is required when axis='{axis}' (could not infer it from the chart's "
            f"{axis} encoding; pass field= explicitly for a LayerChart or aggregate encoding)."
        )
    lo, hi = _derive_exp(df, field, base)
    lo = expMin if expMin is not None else lo
    hi = expMax if expMax is not None else hi
    minor_layer = _log_minor_layer(df, field, axis, lo, hi, minorTickSize, base, nMinor)
    if axis == "y":
        return alt.layer(chart, minor_layer).resolve_axis(y="independent")
    else:
        return alt.layer(chart, minor_layer).resolve_axis(x="independent")


# ---------------------------------------------------------------------------
# Power / sqrt-scale minor ticks
# ---------------------------------------------------------------------------


def _pow_minor_layer(
    df,
    field: str,
    axis: str,
    major_values: list[float],
    minor_tick_size: float,
    exponent: float,
    nMinor: int,
) -> alt.Chart:
    n_divs = nMinor + 1
    exp = exponent
    minor_values = []
    for i in range(len(major_values) - 1):
        a, b = float(major_values[i]), float(major_values[i + 1])
        for k in range(1, n_divs):
            # Interpolate linearly in power-transformed space → equal visual spacing.
            val = (a**exp + k / n_divs * (b**exp - a**exp)) ** (1.0 / exp)
            minor_values.append(val)

    scale = alt.Scale(
        type="pow",
        exponent=exponent,
        domain=[float(min(major_values)), float(max(major_values))],
    )
    return _minor_tick_layer(df, field, axis, minor_values, scale, minor_tick_size)


def add_pow_ticks(
    chart: alt.Chart | alt.LayerChart,
    df,
    field: str | None = None,
    *,
    axis: str = "y",
    exponent: float = 0.5,
    majorValues: list[float] | None = None,
    nMinor: int = 4,
    minorTickSize: float | None = None,
    xField: str | None = None,
    yField: str | None = None,
    xMajorValues: list[float] | None = None,
    yMajorValues: list[float] | None = None,
) -> alt.LayerChart:
    """
    Add unlabeled minor ticks to a power- or sqrt-scale axis.

    Wraps ``chart`` in a layer carrying a second axis of minor ticks.
    The main chart's scale domain is unaffected.

    Minor ticks are placed at positions that are equally spaced in the
    power-transformed (visual) space — i.e. they appear visually uniform
    on screen regardless of where the major ticks fall in data space.
    The formula for minor tick ``k`` of ``nMinor`` between major ticks
    ``a`` and ``b`` is::

        val = (a**exp + k / (nMinor + 1) * (b**exp - a**exp)) ** (1 / exp)

    ``majorValues`` must match the values passed to the main chart's
    ``axis.values`` — the minor layer uses them to infer interval
    boundaries and to set the independent scale domain.

    Use ``exponent=0.5`` (the default) for a square-root axis
    (equivalent to Vega-Lite's ``type="sqrt"``). For a quadratic axis
    use ``exponent=2``, and so on.

    Works with ``alt.Chart``, ``alt.LayerChart``, and any chart type
    composable with ``alt.layer()``. Also works correctly in ``hconcat``
    and ``vconcat`` layouts.

    .. note::
        Minor tick positions are exact at render time (the theme config
        disables Vega's integer tick rounding), so they are correct in
        any renderer. Still prefer ``ds.save()`` over ``chart.save()``
        for the other SVG corrections (grid span, superscript labels)
        and the embedded metadata.

    Parameters
    ----------
    chart:
        The chart to add minor ticks to.
    df:
        DataFrame (Polars or Pandas) used for the main chart.
    field:
        Column name of the power-scaled field. Required when ``axis``
        is ``'x'`` or ``'y'``; omit when ``axis='both'`` and use
        ``xField`` / ``yField`` instead.
    axis:
        ``'x'``, ``'y'`` (default), or ``'both'``. When ``'both'``,
        ``xField``, ``yField``, ``xMajorValues``, and ``yMajorValues``
        must all be provided.
    exponent:
        Power exponent matching the axis scale. Defaults to ``0.5``
        (square root). Use ``2`` for a quadratic axis, etc. Must be
        non-zero.
    majorValues:
        Ordered list of major tick data values for the single-axis
        case. Must match the ``values=`` passed to the main chart's
        ``alt.Axis``. Required — cannot be auto-derived.
    nMinor:
        Number of minor ticks between each pair of major ticks.
        Defaults to ``4`` (divides each interval into five equal
        visual segments).
    minorTickSize:
        Length of minor ticks in pixels. Defaults to half the active
        theme's ``tickSize`` (``tickSize / 2``; typically ``1.5`` when
        the default ``tickSize=3`` is in effect).
    xField:
        Column name for the x power-scaled field (``axis='both'``
        only).
    yField:
        Column name for the y power-scaled field (``axis='both'``
        only).
    xMajorValues:
        Major tick values for the x axis (``axis='both'`` only).
    yMajorValues:
        Major tick values for the y axis (``axis='both'`` only).

    Examples
    --------
    ::

        # sqrt y-axis (exponent=0.5 is the default)
        major_values = [0, 1, 4, 9, 16, 25]
        chart = (
            alt.Chart(df)
            .mark_point()
            .encode(
                y=alt.Y("value:Q",
                    scale=alt.Scale(type="pow", exponent=0.5),
                    axis=alt.Axis(values=major_values),
                )
            )
        )
        chart = ds.add_pow_ticks(chart, df, "value", majorValues=major_values)

        # quadratic x-axis
        chart = ds.add_pow_ticks(
            chart, df, "x_val", axis="x", exponent=2,
            majorValues=[0, 1, 2, 3, 4, 5],
        )

        # both axes power-scaled (same exponent)
        chart = ds.add_pow_ticks(
            chart, df, axis="both",
            xField="x_val", yField="value",
            xMajorValues=[0, 1, 4, 9], yMajorValues=[0, 1, 4, 9, 16, 25],
        )
    """
    if axis not in ("x", "y", "both"):
        raise ValueError(f"axis must be 'x', 'y', or 'both', got {axis!r}")
    if exponent == 0:
        raise ValueError("exponent must be non-zero.")

    if minorTickSize is None:
        minorTickSize = _opt("tickSize") / 2

    df = ensure_polars(df)

    if axis == "both":
        if xField is None or yField is None:
            raise ValueError("axis='both' requires xField and yField.")
        if xMajorValues is None or yMajorValues is None:
            raise ValueError("axis='both' requires xMajorValues and yMajorValues.")
        if len(xMajorValues) < 2 or len(yMajorValues) < 2:
            raise ValueError("majorValues must contain at least two values.")
        x_layer = _pow_minor_layer(df, xField, "x", xMajorValues, minorTickSize, exponent, nMinor)
        y_layer = _pow_minor_layer(df, yField, "y", yMajorValues, minorTickSize, exponent, nMinor)
        return alt.layer(chart, x_layer, y_layer).resolve_axis(x="independent", y="independent")

    if field is None:
        raise ValueError(f"field is required when axis='{axis}'.")
    if majorValues is None:
        raise ValueError("majorValues is required for add_pow_ticks.")
    if len(majorValues) < 2:
        raise ValueError("majorValues must contain at least two values.")
    minor_layer = _pow_minor_layer(df, field, axis, majorValues, minorTickSize, exponent, nMinor)
    if axis == "y":
        return alt.layer(chart, minor_layer).resolve_axis(y="independent")
    else:
        return alt.layer(chart, minor_layer).resolve_axis(x="independent")
