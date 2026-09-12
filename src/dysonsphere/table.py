"""Render a DataFrame as a publication-styled table via a composite Altair mark."""

import math
import re
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, cast

import altair as alt
import polars as pl

if TYPE_CHECKING:
    import pandas as pd

from .theme import _opt
from .utils import _SUP, _ensure_polars, _internal_data, resolve_palette, stripe_colors

# The module's public API - star-imported into the dysonsphere namespace. Everything
# else here is internal (underscore or not); keep this list in sync with __init__.__all__.
__all__ = ["mark_table"]

# The stroke placements composable via the `strokes` set. "grid" expands to rows+cols (the
# interior grid); "all" expands to every rule (outer+header+rows+cols).
_STROKE_KINDS = frozenset({"outer", "header", "rows", "cols", "grid", "all"})
# d3 parses a single alphabetic type slot and intentionally falls back to its default formatter
# for letters without a specialised type. Keep that grammar permissive so the width estimate never
# rejects a format the renderer accepts.
_D3_FORMAT_RE = re.compile(
    r"^(?:(?P<fill>.)(?P<align>[<>=^])|(?P<align_only>[<>=^]))?"
    r"(?P<sign>[+\-( ])?(?P<symbol>[$#])?(?P<zero>0)?(?P<width>\d+)?(?P<comma>,)?"
    r"(?:\.(?P<precision>\d+))?(?P<trim>~)?(?P<type>[A-Za-z%])?$"
)


# ── Number formatting ────────────────────────────────────────────────────────
# Two parallel formatters keep the recovered df byte-identical: display strings are
# measured in Python (Vega can't measure text at build time) but RENDERED without
# mutating the frame - d3/e/si via native alt.Text(format=), and the two Unicode
# superscript notations via a transform_calculate expression (a computed field is never
# inlined into data.values, so read(what="data") returns the frame untouched).


def _is_missing(value: Any) -> bool:
    """Match the non-finite-to-null policy used when export data is serialized."""
    if value is None:
        return True
    try:
        return not math.isfinite(value)
    except TypeError:
        return False


def _sup(n: int) -> str:
    """Unicode-superscript the decimal digits of a non-negative integer."""
    return "".join(_SUP[int(d)] for d in str(n))


def _fmt_scientific(v: float, sig_figs: int) -> str:
    """``1.23×10⁻⁵`` - Python side, for width measurement + sidecar rendering."""
    if _is_missing(v):
        return ""
    if v == 0:
        return "0"
    mant, _, exp = f"{abs(v):.{max(sig_figs - 1, 0)}e}".partition("e")
    e = int(exp)
    return f"{'−' if v < 0 else ''}{mant}×10{'⁻' if e < 0 else ''}{_sup(abs(e))}"


def _fmt_power(v: float, sig_figs: int) -> str:
    """``10⁻⁵`` (nearest power of ten) - Python side."""
    if _is_missing(v):
        return ""
    if v == 0:
        return "0"
    e = round(math.log10(abs(v)))
    return f"{'−' if v < 0 else ''}10{'⁻' if e < 0 else ''}{_sup(abs(e))}"


def _fmt_si(v: float, sig_figs: int) -> str:
    """Rough SI-prefix string - width measurement only (render uses native ``~s``)."""
    if _is_missing(v):
        return ""
    if v == 0:
        return "0"
    for exp, suffix in ((9, "G"), (6, "M"), (3, "k"), (0, ""), (-3, "m"), (-6, "µ"), (-9, "n")):
        if abs(v) >= 10.0**exp or exp == -9:
            return f"{v / 10.0**exp:.{max(sig_figs, 1)}g}{suffix}"
    return f"{v:g}"


def _sup_js(abs_exp: str) -> str:
    """Vega sub-expression: superscript the (already-absolute) exponent expression."""
    result = f"format({abs_exp}, 'd')"
    for digit, superscript in enumerate(_SUP):
        result = f"replace({result}, regexp('{digit}', 'g'), '{superscript}')"
    return result


def _parse_d3_format(spec: str) -> dict[str, Any]:
    """Parse the small, stable d3-format grammar used by Vega-Lite text marks."""
    if not isinstance(spec, str):
        raise ValueError(f"format must be a string, got {spec!r}")
    match = _D3_FORMAT_RE.fullmatch(spec)
    if match is None:
        raise ValueError(f"invalid d3 format {spec!r}")
    groups = match.groupdict()
    return {
        "align": groups["align"] or groups["align_only"],
        "sign": groups["sign"],
        "symbol": groups["symbol"],
        "zero": groups["zero"] is not None,
        "width": int(groups["width"]) if groups["width"] is not None else None,
        "comma": groups["comma"] is not None,
        "precision": int(groups["precision"]) if groups["precision"] is not None else None,
        "trim": groups["trim"] is not None,
        "type": groups["type"],
    }


def _d3_width_estimate(value: Any, spec: str) -> str:
    """Return a non-rendering width estimate without applying Python's incompatible format grammar."""
    parts = _parse_d3_format(spec)
    if _is_missing(value):
        return ""
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return str(value).rjust(parts["width"] or 0)
    if not math.isfinite(numeric):
        return ""

    precision = parts["precision"]
    format_type = parts["type"]
    if format_type == "s":
        length = len(_fmt_si(numeric, max(6 if precision is None else precision, 1)))
    elif format_type in ("f", "%", "p"):
        log10 = math.floor(math.log10(abs(numeric))) if numeric else 0
        integer_digits = max(1, log10 + 1)
        if format_type in ("%", "p"):
            integer_digits = max(1, integer_digits + 2)
        decimals = 6 if precision is None else precision
        length = integer_digits + (decimals + 1 if decimals else 0)
        if parts["comma"]:
            length += max(0, (integer_digits - 1) // 3)
        if format_type in ("%", "p"):
            length += 1
    elif format_type == "e":
        decimals = 6 if precision is None else precision
        exponent_digits = max(2, len(str(abs(math.floor(math.log10(abs(numeric))))) if numeric else "0"))
        length = 1 + (decimals + 1 if decimals else 0) + 1 + 1 + exponent_digits
    else:
        try:
            length = len(format(numeric, f".{precision}g")) if precision is not None else len(str(value))
        except (ValueError, TypeError):
            length = len(str(value))
        if parts["comma"]:
            length += max(0, (len(str(int(abs(numeric)))) - 1) // 3)

    if numeric < 0 or parts["sign"] in ("+", " "):
        length += 1
    if parts["symbol"] is not None:
        length += 1
    if parts["sign"] == "(" and numeric < 0:
        length += 1
    return "0" * max(length, parts["width"] or 0)


def _calc_expr(col: str, notation: str, sig_figs: int) -> str:
    """A Vega ``transform_calculate`` expression producing the superscript label for ``col``.

    Used for the ``scientific`` / ``power`` notations, which native ``format()`` cannot render
    as Unicode superscripts. The computed field is never inlined into ``data.values``, so the
    source frame stays pristine. Vega has no variable binding, so sub-terms are written out
    in full each time they appear.
    """
    v = f"datum[{col!r}]"
    av = f"abs({v})"
    log10 = f"(log({av})/log(10))"
    sign = f"({v} < 0 ? '−' : '')"
    if notation == "power":
        e = f"round({log10})"
        superscript = _sup_js(f"abs({e})")
        return f"(!isValid({v}) ? '' : {v} == 0 ? '0' : {sign} + '10' + ({e} < 0 ? '⁻' : '') + {superscript})"
    # Use d3's native scientific formatter to split the mantissa and exponent. Dividing by
    # 10**exponent looks simple, but underflows for subnormal values and mishandles rounding carry
    # (e.g. 9.999 -> 10.00 x 10^0 instead of 1.00 x 10^1).
    decimals = max(sig_figs - 1, 0)
    formatted = f"format({av}, '.{decimals}e')"
    exponent_start = f"indexof({formatted}, 'e')"
    mant = f"slice({formatted}, 0, {exponent_start})"
    e = f"+slice({formatted}, {exponent_start} + 1, length({formatted}))"
    superscript = _sup_js(f"abs({e})")
    return f"(!isValid({v}) ? '' : {v} == 0 ? '0' : {sign} + {mant} + '×10' + ({e} < 0 ? '⁻' : '') + {superscript})"


# ── Value-based cell colouring ───────────────────────────────────────────────


def _rel_luminance(hex_color: str) -> float:
    """WCAG relative luminance of an ``#rrggbb`` string (0 = black, 1 = white)."""

    def lin(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (int(hex_color[i : i + 2], 16) / 255 for i in (1, 3, 5))
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def _contrast_expr(col: str, hexes: list[str], domain: tuple[float, float]) -> str:
    """Vega expression → ``'black'`` / ``'white'`` picking the readable text colour per cell.

    The palette maps ``domain`` linearly across its stops, so each stop sits at a known data
    value; where the stop luminance crosses the mid-point the text colour flips. Emits a short
    ternary chain over ``datum[col]`` with thresholds at the crossing midpoints.
    """
    n = len(hexes)
    d0, d1 = domain
    vals = [d0 + (d1 - d0) * i / (n - 1) for i in range(n)]
    text_for = ["black" if _rel_luminance(h) > 0.4 else "white" for h in hexes]
    segments: list[tuple[float, str]] = []
    prev = text_for[0]
    for i in range(1, n):
        if text_for[i] != prev:
            segments.append(((vals[i - 1] + vals[i]) / 2, prev))
            prev = text_for[i]
    expr = "".join(f"datum[{col!r}] < {thr} ? '{c}' : " for thr, c in segments)
    return expr + f"'{prev}'"


def mark_table(
    data: "pl.DataFrame | pd.DataFrame",
    columns: list[str] | None = None,
    *,
    header: bool = True,
    headerLabels: dict[str, str] | None = None,
    columnFormat: dict[str, str] | None = None,
    sigFigs: int | None = None,
    align: dict[str, str] | str | None = None,
    strokes: Sequence[str] | str = ("outer", "header"),
    stripePalette: "str | list[str]" = "greys",
    striping: bool = True,
    nStripes: int = 2,
    cellPalette: dict[str, str] | None = None,
    textColor: "str | dict[str, str] | None" = None,
    fontStyle: "str | dict[str, str] | None" = None,
    fontSize: float | None = None,
    headerFontStyle: str | None = None,
    headerFontWeight: "str | int" = "bold",
    headerColor: str | None = None,
    headerFill: str | bool = False,
    cellPadding: float | None = None,
    rowHeight: float | None = None,
    columnWidths: "list[float] | dict[str, float] | None" = None,
    strokeColor: str | None = None,
    strokeWidth: float | None = None,
) -> alt.LayerChart:
    """
    Render ``data`` as a styled table: an ``alt.LayerChart`` that composes like any other mark.

    The table lays cells out in pixel space (so it drops into ``+`` / ``hconcat`` / ``vconcat``
    without scale-merge surprises) but drives every per-row mark off the **user's dataframe** via
    ``transform_window`` (row index) and ``transform_calculate`` (formatted labels, contrast
    colours). Those transforms never touch the inlined data, so ``read(what="data")`` and the
    provenance ``dataChecksum`` recover the frame you passed **byte-for-byte** - only the fixed
    chrome (strokes, header text) rides on internal sidecar datasets.

    Because a table cannot render at the 100×100 default canvas, ``mark_table`` sizes itself from
    the row/column counts and a per-column content estimate, overriding theme ``width`` /
    ``height``. Column widths are proportional-font estimates (Vega cannot measure text at
    build time); pass ``columnWidths`` for exact control.

    **Darkmode** is resolved at BUILD time (like ``shade`` / ``add_multilabel``): the stripe
    fills sample the dark end of the palette and the strokes / auto-contrast colours flip when the
    table is built under ``theme(dark=True)`` (cell text with no explicit colour follows the
    theme's dark-mode-aware ``config.text`` at render). So set the theme before building, or - to
    export light AND dark from one call - pass a **callable** to ``ds.save()`` so the table is
    rebuilt per background::

        ds.save(lambda: ds.mark_table(data, ...), "table", background=["light", "dark"])

    Missing and non-finite values serialize as ``null`` and render as blank cells. They do not
    remove their rows, and the recovered user dataframe is unchanged; zero remains a displayed
    zero. Named numeric formats raise on non-missing string values. An explicit valid d3 format
    may format a string column, while an all-missing column remains blank.

    Parameters
    ----------
    data:
        The data to tabulate (Polars or Pandas). Never mutated.
    columns:
        Columns to show, in order. ``None`` (default) uses every column in ``data`` order.
    header:
        Draw the header row of column labels. Default ``True``.
    headerLabels:
        ``{column: display label}`` to rename headers (unlisted columns keep their name). This is
        a permissive display map; unknown keys are ignored.
    columnFormat:
        ``{column: format}`` for numeric columns. Each value is either a **notation keyword** -
        ``"scientific"`` (``1.23×10⁻⁵``), ``"power"`` (``10⁻⁵``, nearest power of ten), ``"e"``
        (``1.2e-5``), ``"si"`` (``12k``) - honouring ``sigFigs``, or any **Vega/d3 format
        spec** (``".2g"``, ``".1f"``, ``","`` …). The two superscript notations reuse the SVG
        typesetting the rest of dysonsphere applies, so exponents render aligned and any leading
        statistical symbol is italicised. Unlisted numeric columns default to ``sigFigs``
        significant figures; string columns render verbatim. ``"power"`` uses the nearest power
        of ten and ignores ``sigFigs``. An explicit d3 format uses Vega's format expression and
        supplies its own precision; it can also format string columns. Boolean columns support
        numeric formatting. Named numeric notations raise for non-missing string values, while an
        all-missing column remains blank.
    sigFigs:
        Significant figures for the notation keywords and the numeric default. ``None`` (default)
        reads ``theme(sigFigs=…)``.
    align:
        Text alignment. ``None`` (default) is **type-aware**: numeric columns are right-aligned
        (so decimals and units line up) and everything else is left-aligned. A single
        ``"left"``/``"center"``/``"right"`` forces all columns; a ``{column: side}`` dict overrides
        per column (unlisted columns keep the type-aware default).
    strokes:
        Which rules to draw, as any combination of ``"outer"`` (the border), ``"header"`` (the
        header/body separator), ``"rows"`` (between data rows), ``"cols"`` (between columns),
        ``"grid"`` (= ``rows`` + ``cols``, the interior grid), and ``"all"`` (every rule -
        ``outer`` + ``header`` + ``rows`` + ``cols``). A single string is accepted. Default
        ``("outer", "header")``.
    stripePalette:
        Palette (name or hex list) for row striping. Default ``"greys"``. The lightest ``nStripes``
        stops are used in light mode, the darkest in dark mode.
    striping:
        Shade alternating rows. Default ``True``.
    nStripes:
        Number of stripe colours to alternate through. Default ``2``.
    cellPalette:
        ``{column: palette}`` to shade cells by value (a heatmap column). The column's values map
        across the palette (a 13-stop diverging palette is centred on 0; otherwise the domain is
        the column's ``[min, max]``), and each cell's text switches to black or white for
        contrast. Overrides striping within that column. Mapping keys must be input column names;
        a known column need not be in ``columns``.
    textColor:
        Body cell text colour. ``None`` (default) inherits the theme's darkmode-aware text
        colour. A single string colours every body cell; a ``{column: colour}`` dict colours
        per column (unlisted columns inherit). A ``cellPalette`` (value-shaded) column keeps its
        automatic black/white contrast unless you give it an explicit **dict** entry here (a
        per-column colour is taken as deliberate; a global string does not override the
        heatmap's contrast).
    fontStyle:
        Body cell font style (``"italic"`` / ``"normal"``; bold is a weight, not a style). ``None`` (default)
        inherits. A single string styles every body cell; a ``{column: style}`` dict styles per
        column (unlisted columns inherit) - e.g. ``{"gene": "italic"}`` for italic gene names.
    fontSize:
        Cell font size. ``None`` (default) reads ``theme(fontSize=…)``.
    headerFontStyle:
        Font style for header labels (``"italic"`` / ``"normal"``). ``None`` (default) inherits.
    headerFontWeight:
        Font weight for header labels. Default ``"bold"``; pass ``"normal"`` or a number for
        regular weight.
    headerColor:
        Header text colour. ``None`` (default) inherits the theme's text colour, or - when
        ``headerFill`` is set - auto-contrasts (black/white) against the fill. A string sets a
        fixed colour.
    headerFill:
        Background band behind the header row, following the ``bool | str`` pattern: ``False``
        (default) → none; ``True`` → a darkmode-aware default grey band; a string → that colour.
    cellPadding:
        Horizontal padding inside a cell, in px. ``None`` (default) → ``fontSize * 0.6``.
    rowHeight:
        Row height in px. ``None`` (default) → ``round(fontSize * 2)``. The header row uses the
        same height.
    columnWidths:
        Override the estimated widths: a list in ``columns`` order, or a ``{column: width}`` dict
        (unlisted shown columns keep their estimate). Mapping keys must be input column names.
        The same known-input-column rule applies to ``columnFormat``, dict ``align``,
        ``cellPalette``, dict ``textColor``, and dict ``fontStyle``; known columns may be omitted
        from ``columns``. ``headerLabels`` is the permissive exception.
    strokeColor:
        Rule colour. ``None`` (default) → darkmode-aware black/white.
    strokeWidth:
        Rule width in px. ``None`` (default) → the theme's ``axisWidth``.

    Returns
    -------
    alt.LayerChart
        A self-sized table. Compose with ``+`` or concatenate; export with ``ds.save()``.

    Examples
    --------
    ::

        tbl = ds.mark_table(
            data,
            columns=["gene", "log2FC", "pvalue"],
            columnFormat={"log2FC": ".2f", "pvalue": "scientific"},
            cellPalette={"log2FC": "pinksblues"},
            strokes=("outer", "header", "rows"),
        )
        ds.save(tbl, "table")
    """
    data = _ensure_polars(data)
    if data.height == 0:
        raise ValueError("mark_table requires a non-empty dataframe.")

    cols = list(data.columns) if columns is None else list(columns)
    if not cols:
        raise ValueError("mark_table requires at least one column.")
    for c in cols:
        if c not in data.columns:
            raise ValueError(f"column {c!r} is not in data (has {list(data.columns)}).")

    # Resolve the stroke set.
    strokes_seq = [strokes] if isinstance(strokes, str) else list(strokes)
    bad = set(strokes_seq) - _STROKE_KINDS
    if bad:
        raise ValueError(f"unknown strokes {sorted(bad)}; choose from {sorted(_STROKE_KINDS)}.")
    stroke_set = set(strokes_seq)
    if "grid" in stroke_set:
        stroke_set |= {"rows", "cols"}
    if "all" in stroke_set:
        stroke_set |= {"outer", "header", "rows", "cols"}

    if nStripes < 1:
        raise ValueError(f"nStripes must be >= 1, got {nStripes}.")

    cellPalette = cellPalette or {}
    for name, mapping in (
        ("columnFormat", columnFormat),
        ("align", align if isinstance(align, dict) else None),
        ("cellPalette", cellPalette),
        ("textColor", textColor if isinstance(textColor, dict) else None),
        ("fontStyle", fontStyle if isinstance(fontStyle, dict) else None),
        ("columnWidths", columnWidths if isinstance(columnWidths, dict) else None),
    ):
        if mapping is not None:
            unknown = [column for column in mapping if column not in data.columns]
            if unknown:
                raise ValueError(f"{name} has unknown column(s) {unknown}; data columns are {list(data.columns)}.")

    for c in cellPalette:
        if c in cols and not data[c].dtype.is_numeric():
            raise ValueError(f"cellPalette column {c!r} must be numeric.")

    # Theme-derived defaults.
    fs = _opt("fontSize") if fontSize is None else fontSize
    sig_figs = _opt("sigFigs") if sigFigs is None else sigFigs
    pad = fs * 0.6 if cellPadding is None else cellPadding
    row_h = round(fs * 2) if rowHeight is None else rowHeight
    axis_w = _opt("axisWidth")
    stroke_w = axis_w if strokeWidth is None else strokeWidth
    dark = _opt("dark")
    stroke_c = ("white" if dark else "black") if strokeColor is None else strokeColor

    # Header background band + text colour (darkmode-aware, resolved at build like shade).
    if headerFill is True:
        from .palettes import colors

        header_fill_c: str | None = colors["greys"][9 if dark else 3]
    elif isinstance(headerFill, str):
        header_fill_c = headerFill
    else:
        header_fill_c = None
    if headerColor is not None:
        header_text_c: str | None = headerColor
    elif header_fill_c is not None:
        header_text_c = "black" if _rel_luminance(header_fill_c) > 0.4 else "white"
    else:
        header_text_c = None  # inherit the theme text colour

    headerLabels = headerLabels or {}
    columnFormat = columnFormat or {}
    for col, notation in columnFormat.items():
        if not isinstance(notation, str):
            raise ValueError(f"columnFormat[{col!r}] must be a named notation or a d3 format string.")
        if notation not in ("scientific", "power", "e", "si"):
            try:
                _parse_d3_format(notation)
            except ValueError as exc:
                raise ValueError(f"columnFormat[{col!r}] is not a valid Vega/d3 format: {notation!r}.") from exc

    def _col_align(col: str, numeric: bool) -> str:
        # Explicit align wins (global string, or a per-column dict entry); otherwise the default is
        # type-aware - numeric columns right-aligned (so decimals/units line up) and everything
        # else left-aligned.
        if isinstance(align, str):
            return align
        if isinstance(align, dict) and col in align:
            return align[col]
        return "right" if numeric else "left"

    def _text_color(col: str) -> tuple[str, str | None]:
        # ("fixed", colour) | ("contrast", None) | ("inherit", None).
        # A per-column dict entry wins everywhere (deliberate override, even on a heatmap
        # column); otherwise a cellPalette column auto-contrasts; a global string colours the
        # rest; None inherits the theme text colour.
        if isinstance(textColor, dict) and col in textColor:
            return ("fixed", textColor[col])
        if col in cellPalette:
            return ("contrast", None)
        if isinstance(textColor, str):
            return ("fixed", textColor)
        return ("inherit", None)

    def _font_style(col: str) -> str | None:
        # Body cell font style: a per-column dict entry, else a global string, else None.
        if isinstance(fontStyle, dict):
            return fontStyle.get(col)
        return fontStyle

    # Per-column plan: display strings (for width), render method, alignment.
    n_rows = data.height
    plans: list[dict[str, Any]] = []
    for col in cols:
        numeric = data[col].dtype.is_numeric()
        numeric_format = numeric or data[col].dtype == pl.Boolean
        values = data[col].to_list()
        notation = columnFormat.get(col)
        # render = (method, spec_or_expr, numeric_flag); method ∈ {calc, d3, raw}.
        render: tuple[str, Any, Any]
        if notation in ("scientific", "power") and numeric_format:
            disp = [
                _fmt_scientific(v, sig_figs) if notation == "scientific" else _fmt_power(v, sig_figs) for v in values
            ]
            render = ("calc", _calc_expr(col, notation, sig_figs), None)
        elif notation == "e" and numeric_format:
            spec = f".{max(sig_figs - 1, 0)}e"
            disp = [format(v, spec) if not _is_missing(v) else "" for v in values]
            render = ("d3", spec, True)
        elif notation == "si" and numeric_format:
            disp = [_fmt_si(v, sig_figs) if not _is_missing(v) else "" for v in values]
            render = ("d3", f".{sig_figs}~s", True)
        elif notation in ("scientific", "power", "e", "si"):
            if any(not _is_missing(v) for v in values):
                raise ValueError(f"columnFormat[{col!r}] requires numeric values for {notation!r} notation.")
            # All-missing columns can have Null or String dtype; there is nothing to format.
            disp = [""] * len(values)
            render = ("raw", None, False)
        elif notation is not None:  # explicit d3 spec
            disp = [_d3_width_estimate(v, notation) for v in values]
            # Vega-Lite ignores format on nominal text; apply d3 explicitly for string columns.
            render = (
                ("d3", notation, True) if numeric_format else ("calc", f"format(datum[{col!r}], {notation!r})", None)
            )
        elif numeric:
            spec = f".{sig_figs}g"
            disp = [format(v, spec) if not _is_missing(v) else "" for v in values]
            render = ("d3", spec, True)
        else:
            disp = [("" if _is_missing(v) else str(v)) for v in values]
            render = ("raw", None, False)

        label = str(headerLabels.get(col, col))
        longest = max([len(label)] + [len(s) for s in disp]) if disp else len(label)
        plans.append(
            {
                "col": col,
                "numeric": numeric,
                "render": render,
                "align": _col_align(col, numeric),
                "label": label,
                "longest": longest,
            }
        )

    # Column widths (px): content estimate unless overridden.
    est = [max(p["longest"] * fs * 0.6 + 2 * pad, fs * 3) for p in plans]
    if columnWidths is None:
        widths = est
    elif isinstance(columnWidths, dict):
        widths = [float(columnWidths.get(p["col"], est[i])) for i, p in enumerate(plans)]
    else:
        if len(columnWidths) != len(cols):
            raise ValueError(f"columnWidths has {len(columnWidths)} entries but there are {len(cols)} columns.")
        widths = [float(w) for w in columnWidths]

    lefts = [sum(widths[:i]) for i in range(len(widths))]
    total_w = sum(widths)
    header_h = row_h if header else 0.0
    total_h = header_h + n_rows * row_h

    def _anchor(i: int, a: str) -> float:
        left, w = lefts[i], widths[i]
        if a == "left":
            return left + pad
        if a == "right":
            return left + w - pad
        return left + w / 2  # center

    # Row positions in PIXELS (not a band scale): abutting per-cell rects otherwise leave a
    # sub-pixel gap that shows the page through at the browser's chart zoom (invisible at print
    # DPI, so a PNG looks clean - the same seam the gallery heatmaps avoid). Each rect spans
    # [__ytop, __ybot] where __ybot overhangs the next row by `_seam`, and _cell_x2 overhangs the
    # next column the same way, so the cell backgrounds are gapless in BOTH directions -
    # invisible between same-colour stripe cells, a value-coloured cell bleeds <=`_seam` px into
    # its neighbours (hidden under any cell stroke). Text sits at __ymid (the row centre). An
    # identity linear y scale (range == domain) maps the pixel field straight through, shared by
    # every df-driven layer so they align; the header/stroke marks use alt.value pixels directly.
    _seam = 0.5
    # padding=0: the row spans are precomputed pixels, so viewPadding would compress the
    # identity mapping and shrink every row.
    y_scale = alt.Scale(domain=[0, total_h], range=[0, total_h], nice=False, zero=False, padding=0)

    def _y(field: str) -> alt.Y:
        return alt.Y(field=field, type="quantitative", scale=y_scale, axis=None)

    def _df_base() -> alt.Chart:
        return (
            alt.Chart(data)
            .transform_window(__rowidx="row_number()")
            .transform_calculate(
                __ytop=f"{header_h} + (datum.__rowidx - 1) * {row_h}",
                __ybot=f"min({header_h} + datum.__rowidx * {row_h} + {_seam}, {total_h})",  # clamp last row
                __ymid=f"{header_h} + (datum.__rowidx - 0.5) * {row_h}",
            )
        )

    layers: list[alt.Chart] = []
    one = _internal_data([{}])  # 1-row sidecar for the pixel-positioned chrome (band, strokes, header)

    # --- header background band (bottom) ---
    if header and header_fill_c is not None:
        layers.append(
            alt.Chart(one)
            .mark_rect(fill=header_fill_c, stroke=None, strokeWidth=0)
            .encode(x=alt.value(0), x2=alt.value(total_w), y=alt.value(0), y2=alt.value(header_h))
        )

    # Each cell's right edge overhangs the next column by `_seam` (see the row-position note);
    # the last column clamps to the table edge.
    def _cell_x2(i: int) -> float:
        return min(lefts[i] + widths[i] + _seam, total_w)

    # --- row striping ---
    # One rect PER CELL (per column span), never a full-width per-row rect, so every cell
    # background is an independent <rect> - individually editable in Illustrator.
    if striping:
        stripe_cols = stripe_colors(stripePalette, nStripes, darkmode=dark)
        for i in range(len(cols)):
            for k, color in enumerate(stripe_cols):
                layers.append(
                    _df_base()
                    .transform_filter(f"(datum.__rowidx - 1) % {nStripes} == {k}")
                    # stroke pinned off: config.rect leaks a black border onto mark_rect otherwise.
                    .mark_rect(fill=color, stroke=None, strokeWidth=0)
                    .encode(x=alt.value(lefts[i]), x2=alt.value(_cell_x2(i)), y=_y("__ytop"), y2=alt.Y2("__ybot"))
                )

    # --- value-coloured cells ---
    for i, p in enumerate(plans):
        col = p["col"]
        if col not in cellPalette:
            continue
        hexes = resolve_palette(cellPalette[col])
        series = data[col].drop_nulls()
        series = series.filter(series.is_finite())
        lo = float(series.min()) if series.len() else 0.0
        hi = float(series.max()) if series.len() else 1.0
        if len(hexes) == 13:  # diverging → symmetric about 0
            m = max(abs(lo), abs(hi)) or 1.0
            domain = (-m, m)
        else:
            domain = (lo, hi) if hi > lo else (lo, lo + 1.0)
        p["domain"] = domain
        p["hexes"] = hexes
        layers.append(
            _df_base()
            .mark_rect(stroke=None, strokeWidth=0)
            .encode(
                x=alt.value(lefts[i]),
                x2=alt.value(_cell_x2(i)),
                y=_y("__ytop"),
                y2=alt.Y2("__ybot"),
                color=alt.Color(
                    field=col, type="quantitative", scale=alt.Scale(range=list(hexes), domain=list(domain)), legend=None
                ),
            )
        )

    # --- strokes ---
    rules: list[dict[str, float]] = []
    if header and "header" in stroke_set:
        rules.append({"o": 0, "x1": 0, "x2": total_w, "y": header_h})
    if "rows" in stroke_set:
        for i in range(1, n_rows):
            rules.append({"o": 0, "x1": 0, "x2": total_w, "y": header_h + i * row_h})
    if "cols" in stroke_set:
        for x in lefts[1:]:
            rules.append({"o": 1, "x": x, "y1": 0, "y2": total_h})
    if "outer" in stroke_set:
        rules.append({"o": 0, "x1": 0, "x2": total_w, "y": 0})
        rules.append({"o": 0, "x1": 0, "x2": total_w, "y": total_h})
        rules.append({"o": 1, "x": 0, "y1": 0, "y2": total_h})
        rules.append({"o": 1, "x": total_w, "y1": 0, "y2": total_h})
    for r in rules:
        rule = alt.Chart(one).mark_rule(color=stroke_c, strokeWidth=stroke_w, strokeDash=[0, 0])
        if r["o"] == 0:  # horizontal
            layers.append(rule.encode(x=alt.value(r["x1"]), x2=alt.value(r["x2"]), y=alt.value(r["y"])))
        else:  # vertical
            layers.append(rule.encode(x=alt.value(r["x"]), y=alt.value(r["y1"]), y2=alt.value(r["y2"])))

    # --- cell text (per column) ---
    for i, p in enumerate(plans):
        col, a = p["col"], p["align"]
        base = _df_base()
        # Vega's text formatter renders a null quantitative value as the literal string "null"
        # (and a nominal null similarly). Filtering only this generated text layer leaves the row,
        # its stripe, and the original user dataset intact while making every missing/non-finite cell blank.
        base = base.transform_filter(f"isValid(datum[{col!r}])")
        render = p["render"]
        if render[0] == "calc":
            fmt_field = f"__fmt_{i}"
            base = base.transform_calculate(**{fmt_field: render[1]})
            text = alt.Text(field=fmt_field, type="nominal")
        elif render[0] == "d3":
            text = alt.Text(field=col, type="quantitative" if render[2] else "nominal", format=render[1])
        else:
            text = alt.Text(field=col, type="nominal")
        enc: dict[str, Any] = {"x": alt.value(_anchor(i, a)), "y": _y("__ymid"), "text": text}
        mark_kwargs: dict[str, Any] = {"fontSize": fs, "align": a, "baseline": "middle"}
        style = _font_style(col)
        if style is not None:
            mark_kwargs["fontStyle"] = style
        kind, color_val = _text_color(col)
        if kind == "contrast":
            tc_field = f"__tc_{i}"
            base = base.transform_calculate(**{tc_field: _contrast_expr(col, p["hexes"], p["domain"])})
            enc["color"] = alt.Color(field=tc_field, type="nominal", scale=None)
        elif kind == "fixed":
            mark_kwargs["color"] = color_val
        layers.append(base.mark_text(**mark_kwargs).encode(**enc))

    # --- header text (per column) ---
    if header:
        header_center = header_h / 2
        # bold is fontWeight, NOT fontStyle - Vega only takes normal/italic/oblique there, so the
        # old headerFontStyle="bold" default rendered a regular-weight header.
        hdr_kwargs: dict[str, Any] = {"fontSize": fs, "fontWeight": headerFontWeight, "baseline": "middle"}
        if headerFontStyle is not None:
            hdr_kwargs["fontStyle"] = headerFontStyle
        if header_text_c is not None:
            hdr_kwargs["color"] = header_text_c
        for i, p in enumerate(plans):
            a = p["align"]
            layers.append(
                alt.Chart(one)
                .mark_text(align=a, **hdr_kwargs)
                .encode(x=alt.value(_anchor(i, a)), y=alt.value(header_center), text=alt.value(p["label"]))
            )

    return cast(
        alt.LayerChart,
        alt.layer(*layers)
        .resolve_scale(color="independent")
        .properties(width=total_w, height=total_h, view={"fill": None, "stroke": None}),
    )
