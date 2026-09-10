from typing import Any

import altair as alt

from .export import _AltairChart
from .theme import _opt, _temporary_theme
from .utils import _internal_data

# The module's public API - star-imported into the dysonsphere namespace. Everything
# else here is internal (underscore or not); keep this list in sync with __init__.__all__.
__all__ = ["assemble"]

# Markers on a labelled wrapper and on a reserved slot. Vega copies a view name into the SVG
# group class, which is how export._align_figure_labels finds figure labels and leaves charts'
# own titles alone. The prefix is deliberately NOT the statistics one: that channel is stripped
# from written output, and these must survive so a ds.load() round trip re-renders identically.
_FIGURE_PREFIX = "__dsfigure_"
_LABEL_NAME = f"{_FIGURE_PREFIX}label_"
_BLANK_NAME = f"{_FIGURE_PREFIX}blank_"
# Placeholder names; the finished figure is renumbered in traversal order so two identical
# figures get identical markers. A process-wide counter made them differ per call, which broke
# the content checksum - and with it SOURCE_DATE_EPOCH reproducibility - for assembled figures.
_PENDING = "pending"


def _renumber_markers(chart: Any) -> None:
    """Number every figure marker by position in the finished chart, depth-first.

    Uniqueness is required (Vega rejects duplicate view names) and so is determinism, which a
    process-wide counter cannot give. Traversal order supplies both, and renumbering at the end
    also covers an ``assemble`` result nested inside another.
    """
    seen = {_LABEL_NAME: 0, _BLANK_NAME: 0}

    def walk(node: Any) -> None:
        kwds = getattr(node, "_kwds", None)
        if kwds is None:
            return
        name = kwds.get("name")
        if isinstance(name, str):
            for prefix in (_LABEL_NAME, _BLANK_NAME):
                if name.startswith(prefix):
                    seen[prefix] += 1
                    kwds["name"] = f"{prefix}{seen[prefix]}"
                    break
        for key in ("vconcat", "hconcat", "concat", "layer"):
            for sub in kwds.get(key) or []:
                walk(sub)

    walk(chart)


# A member is a builder, a builder with its size, or an already-built chart.
_Member = Any
_Spacing = float | dict[str, float] | None


def _label(chart: _AltairChart, text: str, style: dict[str, Any]) -> _AltairChart:
    """Put the figure label at the top-left of the chart's whole area, axes included.

    The label rides a one-member wrapper's title with ``frame="bounds"``. Two reasons that
    is the construction: ``frame="bounds"`` measures the full bounding box, so the label
    lands left of the y-axis title (``frame="group"`` stops at the plot area) without our
    measuring axis text, which cannot be done at build time - a mark at negative pixels
    undershoots into the axes or overshoots and shoves the chart right. And putting it on a
    WRAPPER leaves the chart's own title free, so a member can carry both.

    Colour is left to config.title when unset - that resolves per background, so a save()
    across light and dark gets the right ink without a callable.
    """
    pad = style["padding"]
    dx, dy = pad if isinstance(pad, tuple) else (pad, pad)
    color = {"color": style["color"]} if style["color"] is not None else {}
    return alt.vconcat(
        chart,
        name=f"{_LABEL_NAME}{_PENDING}",
        title=alt.TitleParams(
            text=text,
            anchor="start",
            frame="bounds",
            fontSize=style["fontSize"],
            fontWeight=style["fontWeight"],
            dx=dx,
            dy=dy,
            **color,
        ),
    )


_MEMBER_KEYS = ("chart", "width", "height", "label")


def _unpack(member: _Member) -> tuple[Any, Any, Any, str | None]:
    """Resolve any member form to (source, width, height, label)."""
    if isinstance(member, dict):
        unknown = set(member) - set(_MEMBER_KEYS)
        if unknown:
            raise ValueError(f"member keys must be {list(_MEMBER_KEYS)}, got unknown {sorted(unknown)}")
        if "chart" not in member:
            raise ValueError(f"member dict needs a 'chart' key, got {sorted(member)}")
        return member["chart"], member.get("width"), member.get("height"), member.get("label")
    if isinstance(member, tuple):
        if len(member) == 4:
            return member
        if len(member) == 3:
            return (*member, None)
        raise ValueError(f"member tuple must be (chart, width, height) or (chart, width, height, label), got {member}")
    return member, None, None, None


def _blank() -> _AltairChart:
    """A filled, outlined view that draws nothing and occupies its size.

    It rides ``view`` rather than a rect mark, so it traces the reserved area with no
    encodings; colors are read at build time like ``shade``'s, so a ``save()`` across
    both backgrounds needs a callable. Its row is tagged internal, keeping a reserved slot
    out of ``read(what="data")`` and the provenance checksums.
    """
    darkmode = _opt("darkmode")
    outline = alt.ViewBackground(
        fill=_opt("chartFill") or ("black" if darkmode else "white"),
        stroke="white" if darkmode else "black",
        strokeWidth=_opt("axisWidth"),
        strokeDash=[0, 0],  # solid - config.rule's dash must not reach it
    )
    return (
        alt.Chart(_internal_data([{}])).mark_point(opacity=0).properties(view=outline, name=f"{_BLANK_NAME}{_PENDING}")
    )


def _build(member: _Member, style: dict[str, Any]) -> _AltairChart:
    """Build one member at its own size, then stamp that size on the chart."""
    source, width, height, text = _unpack(member)
    overrides = {k: v for k, v in (("chartWidth", width), ("chartHeight", height)) if v is not None}
    size = {p: overrides[k] for k, p in (("chartWidth", "width"), ("chartHeight", "height")) if k in overrides}
    if source is None:
        # A reserved slot: no builder runs, so there is nothing derived to compute - the size is
        # simply the space held. It carries no axis chrome, so it occupies exactly its width,
        # where a real chart of the same width occupies that plus its axis margin.
        chart = _blank().properties(**size) if size else _blank()
    elif not callable(source):
        # An already-built chart: its derived pixel values are baked, so a size here cannot be
        # honored - stamping one would leave exactly the stale geometry assemble exists to avoid.
        if overrides:
            raise ValueError("a size cannot be applied to an already-built chart - pass a builder instead")
        chart = source
    elif overrides:
        # Re-run theme() so derived geometry follows the member size, but retain save()'s
        # temporary render mode and restore the exact caller state even if the builder fails.
        with _temporary_theme(overrides):
            chart = source()
        chart = chart.properties(**size)
    else:
        chart = source()
    return _label(chart, text, style) if text is not None else chart


def _spacing_kwargs(gap: float | None) -> dict[str, float]:
    return {} if gap is None else {"spacing": gap}


def assemble(
    members: list[_Member],
    *,
    spacing: _Spacing = None,
    labelFontSize: float = 8,
    labelFontWeight: int = 700,
    labelColor: str | None = None,
    labelOffset: float | tuple[float, float] = (-5, 0),
) -> _AltairChart:
    """
    Compose several charts into one figure, each built at its own size.

    Charts in one figure share a single ``config.view``, so :func:`theme` alone cannot give
    them different sizes - the last call wins. Sizing with ``.properties()`` instead leaves
    ``markSize``, the corner and arc radii, and the pixel geometry of every annotation
    (``shade`` spans, comparison brackets, ``labels`` placement) computed for the
    theme's size rather than the one the chart renders at. ``assemble`` builds each member
    while the theme genuinely says its size, so those all land correctly, then stamps the
    size on the chart so the shared config cannot override it.

    Size only: Vega-Lite's ``config`` is spec-level, so palettes, fonts and axis styling
    cannot differ between charts in one figure. Set those on the encoding instead - e.g.
    ``alt.Color(..., scale=alt.Scale(range=ds.palette("cat3", 3)))`` - which is per-view
    and survives. Scales are not shared: concat resolves them independently already.

    Parameters
    ----------
    members:
        The charts, in layout order. Each is a ``(builder, width, height)`` tuple, a bare
        zero-argument builder (built at the theme's current size), or an already-built chart
        (used as-is, so a ``assemble`` result can nest inside another). Nest lists to make
        rows: ``[[a, b], [c, d]]`` is two rows of two, a flat list is a single row.

        Add a fourth element to carry a figure label: ``(time_course, 190, 110, "a")`` puts
        an ``a`` at that chart's top-left. The text is used verbatim, and members without a
        fourth element get no label, so a figure can label some charts and not others.

        A member may also be a dict, for callers who prefer the keys spelled out:
        ``{"chart": time_course, "width": 190, "height": 110, "label": "a"}``. Only
        ``chart`` is required, and it takes a builder or an already-built chart.

        ``None`` as the chart reserves an empty slot of that size - ``(None, 190, 110, "a")``
        holds space to fill in later, labelled so the lettering stays in sequence. A blank
        carries no axis chrome, so it occupies exactly its width, where a real chart of the
        same width occupies that plus its axis margin.
    spacing:
        Gap between charts in pixels - a number for both directions, or
        ``{"row": 40, "column": 10}`` to set them independently. ``None`` uses Vega-Lite's
        default.
    labelFontSize, labelFontWeight, labelColor, labelOffset:
        Figure-label styling. Weight is numeric (700, bold, by default). ``labelColor``
        defaults to the theme's title ink, which follows ``darkmode`` at render, so a
        ``save()`` across both backgrounds gets the right color without a callable.
        ``labelOffset`` offsets the label from the corner - one number for both axes, or
        ``(x, y)``. It defaults to ``(-5, 0)``, holding the label off the chart the way
        ``axisOffset`` detaches the axes. The label already sits at the figure's leftmost
        point, so a negative x cannot move it further left - it widens the canvas and
        indents the chart instead, which reads the same and costs those pixels of width.

    Returns
    -------
    An Altair concat chart, so ``.resolve_scale()``, ``.properties()`` and further nesting
    all work on the result.

    Examples
    --------
    A wide time course beside a narrow endpoint comparison::

        figure = ds.assemble(
            [(time_course, 210, 130), (endpoint_quant, 95, 130)],
            spacing=34,
        )

    Two rows, with more room between the rows than within them::

        figure = ds.assemble(
            [
                [(time_course, 190, 110), (endpoint_quant, 90, 110)],
                [(heatmap, 130, 110), (activity_fit, 150, 110)],
            ],
            spacing={"row": 40, "column": 10},
        )
    """
    if not members:
        raise ValueError("assemble() needs at least one member")
    if isinstance(spacing, dict):
        unknown = set(spacing) - {"row", "column"}
        if unknown:
            raise ValueError(f"spacing keys must be 'row' and/or 'column', got {sorted(unknown)}")
        row_gap, column_gap = spacing.get("row"), spacing.get("column")
    else:
        row_gap = column_gap = spacing

    style = {
        "fontSize": labelFontSize,
        "fontWeight": labelFontWeight,
        "color": labelColor,
        "padding": labelOffset,
    }
    rows = members if isinstance(members[0], list) else [members]
    built: list[_AltairChart] = []
    for row in rows:
        if not isinstance(row, list):
            raise ValueError("mix of rows and bare members - nest every row in its own list, or nest none")
        if not row:
            raise ValueError("assemble() rows cannot be empty")
        charts = [_build(m, style) for m in row]
        if len(charts) == 1:
            built.append(charts[0])
            continue
        # hconcat defaults its legends to shared and DROPS them outright when the panels'
        # colour scales cannot merge; resolving makes each keep its own.
        built.append(alt.hconcat(*charts, **_spacing_kwargs(column_gap)).resolve_scale(color="independent"))
    result = (
        built[0]
        if len(built) == 1
        else alt.vconcat(*built, **_spacing_kwargs(row_gap)).resolve_scale(color="independent")
    )
    _renumber_markers(result)
    return result
