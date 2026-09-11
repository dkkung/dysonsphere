import math
from typing import TYPE_CHECKING, Any, cast

import altair as alt
import polars as pl

if TYPE_CHECKING:
    import pandas as pd

from .theme import _opt
from .utils import _band_geometry, _count_n, _internal_data

# The module's public API - star-imported into the dysonsphere namespace. Everything
# else here is internal (underscore or not); keep this list in sync with __init__.__all__.
__all__ = ["add_multilabel"]


def _multilabel_layer(
    groups: dict[str, list[Any]],
    categories: list[str],
    *,
    order: list[str] | None = None,
    style: str = "plusminus",
    rowStyles: dict[str, str] | list[str] | None = None,
    labelAlign: str = "left",
    labelPadding: float = 0,
    symbol: str = "circle",
    symbolSize: float | None = None,
    palette: list[str] | None = None,
    strokeWidth: float | None = None,
    connectingLine: bool = True,
    orientation: str = "vertical",
    chartWidth: float | None = None,
    fontSize: float | None = None,
    rowHeight: int | float | dict[str, int | float] | list[int | float] | None = None,
    rowValueAngle: int | float | dict[str, Any] | list[Any] | None = None,
    categoryLabel: bool = False,
    categoryLabelPosition: str = "bottom",
    labelMap: dict[str, Any] | None = None,
    categoryLabelAngle: float = -45,
    categoryLabelHeight: float | None = None,
    span: dict[str | None, list[str]] | list[dict[str | None, list[str]]] | None = None,
    spanBracketStyle: str = "line",
    spanLabelPosition: str = "bottom",
    spanBracketReverse: bool = True,
    spanTickHeight: float | None = None,
    spanGap: float | None = None,
) -> alt.LayerChart:
    """
    Build a condition-table annotation chart to place below a strip/violin/boxplot.

    Each key in ``groups`` is a row label; its value is a list of booleans (or
    arbitrary strings/numbers), one per category. Combine with the main chart using
    ``alt.vconcat(chart, _multilabel_layer(...)).resolve_scale(x="shared")``.

    Every parameter except ``groups`` and ``categories`` is documented on the public
    :func:`add_multilabel`, which forwards them here; this is the private implementation.

    Notes
    -----
    **Row label alignment.** Row labels are rendered as explicit ``mark_text`` marks
    (not as y-axis labels) so they share the exact same y coordinate as the content
    marks. Vega-Lite's axis label rendering pipeline does not guarantee pixel-perfect
    alignment with ``mark_text`` even when both use ``baseline="middle"``, so the y
    axis is suppressed and labels are placed via ``alt.value(x)`` instead.

    **Pixel rows.** Rows are stacked in pixel space on an identity linear y scale
    (``domain == range``) rather than on an ordinal band scale, because a band scale
    gives every row the same height and a rotated row needs more room than a flat one.
    The identity scale puts the content marks in the same coordinate space as the span
    and category-label marks, which position with ``alt.value``.

    **``align="center"``** is required on all ``mark_text`` content marks — the mark
    rotates about its own anchor, so any other alignment swings a rotated row's text
    off its category tick.

    **Darkmode symbol colours** (``positive_color``, ``negative_fill``, ``negative_stroke``)
    are resolved from ``alt.theme.options`` at call time. When using ``style="symbol"``
    with ``ds.save()``, pass a callable so the chart is rebuilt after each darkmode
    toggle::

        ds.save(
            lambda: ds.add_multilabel(chart, groups, style="symbol", ...),
            "my_plot",
        )

    **hconcat label overflow.** Row label marks are positioned outside the declared
    ``width`` (at ``x < 0`` or ``x > chartWidth``). Vega-Lite does not clip them by
    default and does not reserve space for them in auto-layout. In an ``hconcat``,
    labels from one panel can bleed into adjacent panels; add explicit ``spacing``
    or outer padding to compensate.

    Examples
    --------
    ::

        CATEGORIES = ["Ctrl", "Group A", "Group B", "Group C"]
        ds.theme(width=300)
        chart = ds.mark_strip(df, "group", "value", CATEGORIES)
        ann = ds._multilabel_layer(
            {
                "Group A":         [False, True,  True,  True],
                "Group B":        [False, False, True,  False],
                "Group C": [False, False, False, True],
            },
            categories=CATEGORIES,
            style="symbol",
        )
        alt.vconcat(chart, ann).resolve_scale(x="shared")
    """
    from .palettes import colors

    row_order = list(order) if order is not None else list(groups.keys())

    unknown_rows = [label for label in row_order if label not in groups]
    if unknown_rows:
        raise ValueError(f"order names row(s) {unknown_rows} that are not in groups. Rows are {list(groups)}.")
    duplicate_rows = [label for i, label in enumerate(row_order) if label in row_order[:i]]
    if duplicate_rows:
        raise ValueError(f"order contains duplicate row label(s) {duplicate_rows}.")

    for label in row_order:
        if len(groups[label]) != len(categories):
            raise ValueError(
                f"groups[{label!r}] has {len(groups[label])} values but categories has "
                f"{len(categories)}. Each row must have one value per x-axis category, "
                f"in the same left-to-right order as the main chart."
            )

    if style not in ("plusminus", "text", "symbol"):
        raise ValueError(f"style must be 'plusminus', 'text', or 'symbol', got {style!r}")
    if labelAlign not in ("left", "right"):
        raise ValueError(f"labelPosition must be 'left' or 'right', got {labelAlign!r}")
    if orientation not in ("vertical", "horizontal"):
        raise ValueError(f"lineOrientation must be 'vertical' or 'horizontal', got {orientation!r}")
    if spanBracketStyle not in ("line", "bracket"):
        raise ValueError(f"spanBracketStyle must be 'line' or 'bracket', got {spanBracketStyle!r}")
    if spanLabelPosition not in ("top", "bottom"):
        raise ValueError(f"spanLabelPosition must be 'top' or 'bottom', got {spanLabelPosition!r}")

    # Normalise rowStyles to a dict so the rest of the code has a single code path.
    if isinstance(rowStyles, list):
        if len(rowStyles) != len(row_order):
            raise ValueError(f"rowStyles list has {len(rowStyles)} entries but there are {len(row_order)} rows.")
        rowStyles = dict(zip(row_order, rowStyles))
    elif isinstance(rowStyles, dict):
        unknown = [label for label in rowStyles if label not in groups]
        if unknown:
            raise ValueError(f"rowStyles has unknown row label(s) {unknown}. Rows are {list(groups)}.")

    # Per-row style resolution: rowStyles overrides global style; non-bool values always
    # force "text" regardless. Check isinstance(v, bool) before isinstance(v, int) because
    # bool subclasses int.
    def _row_style(label: str) -> str:
        s = (rowStyles or {}).get(label, style)
        if s not in ("plusminus", "text", "symbol"):
            raise ValueError(f"rowStyles[{label!r}] must be 'plusminus', 'text', or 'symbol', got {s!r}")
        if any(not isinstance(v, bool) for v in groups[label]):
            return "text"
        return s

    row_styles = {label: _row_style(label) for label in row_order}
    plusminus_rows = [r for r in row_order if row_styles[r] == "plusminus"]
    text_rows = [r for r in row_order if row_styles[r] == "text"]
    symbol_rows = [r for r in row_order if row_styles[r] == "symbol"]

    if chartWidth is None:
        chartWidth = _opt("width")
    if fontSize is None:
        fontSize = _opt("fontSize")

    def _norm(v: object) -> str:
        if isinstance(v, bool):
            return "+" if v else "−"
        s = str(v)
        # A lone ASCII hyphen is a "not applicable" placeholder - render it as the same
        # typographic minus a plusminus row uses, so the two match within one table.
        return "−" if s == "-" else s

    def _per_row(value: object, name: str) -> dict[str, Any]:
        """Normalize a scalar / list / dict per-row override to {row label: value}."""
        if value is None:
            return {}
        if isinstance(value, dict):
            mapping = cast(dict[str, Any], value)
            unknown = [k for k in mapping if k not in groups]
            if unknown:
                raise ValueError(f"{name} has unknown row label(s) {unknown}. Rows are {list(groups)}.")
            return dict(mapping)
        if isinstance(value, (list, tuple)):
            seq = cast(list[Any], value)
            if len(seq) != len(row_order):
                raise ValueError(f"{name} list has {len(seq)} entries but there are {len(row_order)} rows.")
            return dict(zip(row_order, seq))
        return {label: value for label in row_order}

    angle_map = _per_row(rowValueAngle, "rowValueAngle")

    def _cell_angles(label: str) -> list[float]:
        """One angle per category - a row's entry may be a scalar or a per-cell list."""
        entry = angle_map.get(label)
        if isinstance(entry, (list, tuple)):
            seq = cast(list[Any], entry)
            if len(seq) != len(categories):
                raise ValueError(
                    f"rowValueAngle[{label!r}] has {len(seq)} entries but categories has {len(categories)}. "
                    f"A per-cell angle list needs one angle per x-axis category."
                )
            return [float(a or 0.0) for a in seq]
        return [float(entry or 0.0)] * len(categories)

    row_angles = {label: _cell_angles(label) for label in row_order}

    # A scalar rowHeight also supplies the floor auto-sizing never drops below.
    default_row_height = float(rowHeight) if isinstance(rowHeight, (int, float)) else 10.0
    height_map = _per_row(rowHeight, "rowHeight")

    def _auto_row_height(label: str) -> float:
        # Each cell needs the height of its own rotated bounding box - the same estimate
        # the category-label row uses, with 0.6 em as the mean glyph advance. The row takes
        # the tallest, so an upright cell never shrinks the row a rotated one needs.
        tallest = 0.0
        for value, angle in zip(groups[label], row_angles[label]):
            rad = math.radians(angle)
            n_chars = len(_norm(value))
            tallest = max(tallest, fontSize * 0.6 * n_chars * abs(math.sin(rad)) + fontSize * abs(math.cos(rad)))
        return max(default_row_height, float(math.ceil(tallest)))

    row_heights = {label: float(height_map.get(label, _auto_row_height(label))) for label in row_order}
    rows_h = sum(row_heights.values())

    # When categoryLabel="bottom" and spans are present, defer the label row
    # to below the spans section so the visual order is: rows → spans → labels.
    defer_cat_label = bool(categoryLabel and span and categoryLabelPosition != "top")

    label_y = 0.0
    label_y_offset = 0.0
    extra = 0.0

    # Display names for the category-label row: labelMap lookup, raw value fallback.
    # Multi-line list labels are space-joined here (mark_text rows are single-line);
    # the axis-label path in the mark constructors renders them as true multi-line.
    def _display(cat: str) -> str:
        label = (labelMap or {}).get(cat, cat)
        return " ".join(label) if isinstance(label, list) else str(label)

    if categoryLabel:
        if categoryLabelPosition not in ("top", "bottom"):
            raise ValueError(f"categoryLabelPosition={categoryLabelPosition!r} is invalid. Use 'top' or 'bottom'.")
        max_len = max(len(_display(cat)) for cat in categories)
        angle_rad = abs(math.radians(categoryLabelAngle))
        tight_height = fontSize * 0.6 * max_len * math.sin(angle_rad) + fontSize * math.cos(angle_rad)
        if categoryLabelHeight is None:
            categoryLabelHeight = math.ceil(tight_height)
        k = 0 if categoryLabelPosition == "top" else len(row_order)
        # Upward extent from anchor for align="right", baseline="middle":
        # min y' = -H/2 * |cos(angle)|. Offset label_y down by this amount so
        # the text stays within the label row and doesn't clip above y=0.
        label_y_offset = fontSize / 2 * abs(math.cos(math.radians(categoryLabelAngle)))
        # Extra space beyond the tight-fit height; for the bottom case this
        # shifts the anchor into the label row so the gap is on the data side.
        extra = max(0.0, categoryLabelHeight - tight_height)
        if k == 0:
            label_y = label_y_offset
        elif not defer_cat_label:
            label_y = rows_h + label_y_offset + extra

    # Rows are stacked in pixel space (not on a band scale) because a band scale gives
    # every row the same height, and a rotated row needs more room than a flat one.
    y0 = float(categoryLabelHeight or 0) if (categoryLabel and categoryLabelPosition == "top") else 0.0
    row_y: dict[str, float] = {}
    _top = y0
    for label in row_order:
        row_y[label] = _top + row_heights[label] / 2
        _top += row_heights[label]

    rows = [
        {
            "__label": label,
            "__category": cat,
            "__value": _norm(val),
            "__y": row_y[label],
            "__angle": angle % 360,
        }
        for label in row_order
        for cat, val, angle in zip(categories, groups[label], row_angles[label])
    ]
    marks_df = pl.DataFrame(rows)

    chart_h = y0 + rows_h + (0 if (defer_cat_label or categoryLabelPosition == "top") else (categoryLabelHeight or 0))

    x_enc = alt.X(
        "__category:N",
        sort=categories,
        # Pin the domain (not just sort) so `resolve_scale(x="shared")` can't re-sort the
        # merged x domain alphabetically - the same shared-scale union fix as `domain=row_order`
        # on the y scale below. Without it the chart's x renders in a different order than its
        # (unshared) colour scale, so category colours stop matching their bars.
        scale=alt.Scale(domain=categories),
        axis=alt.Axis(labels=False, ticks=False, domain=False, grid=False, title=None),
    )
    # Identity linear scale (domain == range) so `__y` is read as pixels, matching the
    # span and category-label marks, which position with alt.value. Pinning both ends
    # also stops Vega stretching the rows into the span section below them.
    rows_extent = y0 + rows_h or 1.0
    y_enc = alt.Y(
        "__y:Q",
        # padding=0: the row centres are precomputed pixels, so viewPadding
        # would compress the identity mapping and squeeze the rows together.
        scale=alt.Scale(domain=[0, rows_extent], range=[0, rows_extent], nice=False, zero=False, padding=0),
        axis=None,
    )
    angle_enc = alt.Angle("__angle:Q", scale=None)

    if labelAlign == "right":
        label_x = alt.value(chartWidth + labelPadding)
    else:
        label_x = alt.value(-labelPadding)
    label_text_align = "left" if labelAlign == "right" else "right"
    label_df = pl.DataFrame({"__label": row_order, "__y": [row_y[label] for label in row_order]})
    row_labels = (
        alt.Chart(_internal_data(label_df))
        .mark_text(fontSize=fontSize, align=label_text_align, baseline="middle")
        .encode(x=label_x, y=y_enc, text=alt.Text("__label:N"))
    )

    layers: list[Any] = [row_labels]

    # --- plusminus rows ---
    if plusminus_rows:
        pm_df = marks_df.filter(pl.col("__label").is_in(plusminus_rows))
        # align="center" keeps rotated text centered on its category - the mark rotates
        # about its own anchor, so any other alignment swings it off the tick.
        layers.append(
            alt.Chart(_internal_data(pm_df))
            .mark_text(fontSize=fontSize, align="center", baseline="middle")
            .encode(x=x_enc, y=y_enc, angle=angle_enc, text=alt.Text("__value:N"))
        )

    # --- text rows ---
    if text_rows:
        text_df = marks_df.filter(pl.col("__label").is_in(text_rows))
        layers.append(
            alt.Chart(_internal_data(text_df))
            .mark_text(fontSize=fontSize, align="center", baseline="middle")
            .encode(x=x_enc, y=y_enc, angle=angle_enc, text=alt.Text("__value:N"))
        )

    # --- symbol rows ---
    if symbol_rows:
        # Colours are resolved at call time from alt.theme.options so that darkmode
        # variants are correct. Use a callable with ds.save() to rebuild per variant.
        darkmode = _opt("darkmode")
        if darkmode:
            positive_color = "white"
            negative_fill = colors["greys"][11]
            negative_stroke = "white"
        else:
            positive_color = "black"
            negative_fill = colors["greys"][0]
            negative_stroke = alt.Undefined

        if palette is not None:
            negative_fill = palette[0]
            positive_color = palette[-1]

        if symbolSize is None:
            symbolSize = _opt("markSize") * 4
        if strokeWidth is None:
            strokeWidth = _opt("markStrokeWidth")

        plus_df = marks_df.filter(pl.col("__label").is_in(symbol_rows) & (pl.col("__value") == "+"))
        minus_df = marks_df.filter(pl.col("__label").is_in(symbol_rows) & (pl.col("__value") == "−"))

        symbol_dy = -fontSize * 0.1

        positive = (
            alt.Chart(_internal_data(plus_df))
            .mark_point(
                shape=symbol,
                filled=True,
                color=positive_color,
                strokeWidth=strokeWidth,
                size=symbolSize,
                dy=symbol_dy,
            )
            .encode(x=x_enc, y=y_enc, angle=angle_enc)
        )
        negative = (
            alt.Chart(_internal_data(minus_df))
            .mark_point(
                shape=symbol,
                filled=True,
                fill=negative_fill,
                stroke=negative_stroke,
                strokeWidth=strokeWidth,
                size=symbolSize,
                dy=symbol_dy,
            )
            .encode(x=x_enc, y=y_enc, angle=angle_enc)
        )

        # Connecting lines only span between symbol rows; non-symbol rows between
        # two symbol rows are skipped in run detection (they don't break runs).
        symbol_row_set = set(symbol_rows)
        line_rows: list[dict[str, Any]] = []
        if orientation == "horizontal":
            for label in row_order:
                if label not in symbol_row_set:
                    continue
                run: list[int] = []
                for i, v in enumerate(groups[label]):
                    if v is True:
                        run.append(i)
                    else:
                        if len(run) >= 2:
                            line_rows.append(
                                {
                                    "__label": label,
                                    "__x_start": categories[run[0]],
                                    "__x_end": categories[run[-1]],
                                }
                            )
                        run = []
                if len(run) >= 2:
                    line_rows.append(
                        {
                            "__label": label,
                            "__x_start": categories[run[0]],
                            "__x_end": categories[run[-1]],
                        }
                    )
        else:  # vertical
            # Emit two rows per segment (start + end) so mark_line can connect them
            # using only __label — avoiding a second ordinal field on the shared y
            # scale, which would corrupt paddingInner and shift row spacing.
            for i, cat in enumerate(categories):
                run = []
                for j, label in enumerate(row_order):
                    if label not in symbol_row_set:
                        continue
                    if groups[label][i] is True:
                        run.append(j)
                    else:
                        if len(run) >= 2:
                            _id = f"{cat}_{run[0]}_{run[-1]}"
                            line_rows.append(
                                {
                                    "__category": cat,
                                    "__label": row_order[run[0]],
                                    "__line_id": _id,
                                }
                            )
                            line_rows.append(
                                {
                                    "__category": cat,
                                    "__label": row_order[run[-1]],
                                    "__line_id": _id,
                                }
                            )
                        run = []
                if len(run) >= 2:
                    _id = f"{cat}_{run[0]}_{run[-1]}"
                    line_rows.append(
                        {
                            "__category": cat,
                            "__label": row_order[run[0]],
                            "__line_id": _id,
                        }
                    )
                    line_rows.append(
                        {
                            "__category": cat,
                            "__label": row_order[run[-1]],
                            "__line_id": _id,
                        }
                    )

        if connectingLine and line_rows:
            for r in line_rows:
                r["__y"] = row_y[cast(str, r["__label"])]
            lines_df = pl.DataFrame(line_rows)
            if orientation == "horizontal":
                lines = (
                    alt.Chart(_internal_data(lines_df))
                    # strokeDash=[0, 0] overrides the theme's dashedRule=True default.
                    .mark_rule(strokeWidth=strokeWidth, strokeDash=[0, 0])
                    .encode(
                        x=alt.X("__x_start:N", sort=categories),
                        x2="__x_end:N",
                        y=y_enc,
                    )
                )
            else:  # vertical
                lines = (
                    alt.Chart(_internal_data(lines_df))
                    .mark_line(strokeWidth=strokeWidth, strokeDash=[0, 0])
                    .encode(
                        x=x_enc,
                        y=y_enc,
                        detail="__line_id:N",
                    )
                )
            layers.extend([lines, negative, positive])
        else:
            layers.extend([negative, positive])

    if categoryLabel and not defer_cat_label:
        label_df = pl.DataFrame({"__category": categories, "__display": [_display(c) for c in categories]})
        layers.append(
            alt.Chart(_internal_data(label_df))
            .mark_text(
                fontSize=fontSize,
                angle=categoryLabelAngle % 360,
                align="center" if categoryLabelAngle % 360 == 0 else "right",
                baseline="middle",
            )
            # __category stays raw (it is the band-scale position); __display is the text
            .encode(x=x_enc, y=alt.value(label_y), text=alt.Text("__display:N"))
        )

    if span:
        span_pairs: list[tuple[str | None, list[str]]]
        if isinstance(span, list):
            span_pairs = [(k, v) for d in span for k, v in d.items()]
        else:
            span_pairs = list(span.items())

        if spanTickHeight is None:
            spanTickHeight = _opt("tickSize")

        geo = _band_geometry(len(categories), chartWidth)
        axisWidth_val = _opt("axisWidth")
        darkmode_val = _opt("darkmode")
        span_color = "white" if darkmode_val else "black"
        _one_row = _internal_data([{}])  # 1-row internal data for the pixel-positioned span marks

        span_gap = default_row_height * 0.3 if spanGap is None else spanGap
        label_gap = 2.0
        has_any_label = any(bool(lbl) for lbl, _ in span_pairs)

        is_bracket_down = spanBracketStyle == "bracket" and not spanBracketReverse
        if spanLabelPosition == "bottom":
            span_y = chart_h + span_gap
            tick_below_h = spanTickHeight if is_bracket_down else 0.0
            label_y = span_y + tick_below_h + label_gap if has_any_label else 0.0
            label_baseline = "top"
            chart_h = span_y + tick_below_h + (fontSize + label_gap if has_any_label else 0.0) + 2.0
        else:  # top
            label_baseline = "top"
            if has_any_label:
                label_y = chart_h + span_gap
                span_y = label_y + fontSize + label_gap
            else:
                label_y = 0.0
                span_y = chart_h + span_gap
            tick_below_h = spanTickHeight if is_bracket_down else 0.0
            chart_h = span_y + tick_below_h + 2.0

        if spanBracketStyle == "bracket":
            tick_y_start = (span_y - spanTickHeight) if spanBracketReverse else span_y
            tick_y_end = span_y if spanBracketReverse else (span_y + spanTickHeight)

        for span_lbl, span_cats in span_pairs:
            if not span_cats:
                raise ValueError(f"span[{span_lbl!r}] must not be empty")
            indices = []
            for cat in span_cats:
                if cat not in categories:
                    raise ValueError(f"span[{span_lbl!r}]: {cat!r} is not in categories")
                indices.append(categories.index(cat))
            i_start, i_end = min(indices), max(indices)

            x1 = geo.centers[i_start] - geo.step * 0.30
            x2 = geo.centers[i_end] + geo.step * 0.30
            x_mid = (x1 + x2) / 2

            # Rule — alt.value() for all positions so no :Q scale is added to the layer
            layers.append(
                alt.Chart(_one_row)
                .mark_rule(color=span_color, strokeWidth=axisWidth_val, strokeDash=[0, 0])
                .encode(x=alt.value(x1), x2=alt.value(x2), y=alt.value(span_y))
            )

            # Bracket ticks
            if spanBracketStyle == "bracket":
                for tick_x in (x1, x2):
                    layers.append(
                        alt.Chart(_one_row)
                        .mark_rule(
                            color=span_color,
                            strokeWidth=axisWidth_val,
                            strokeDash=[0, 0],
                        )
                        .encode(
                            x=alt.value(tick_x),
                            y=alt.value(tick_y_start),
                            y2=alt.value(tick_y_end),
                        )
                    )

            # Label
            if span_lbl:
                lbl_df = pl.DataFrame({"__slabel": [span_lbl]})
                layers.append(
                    alt.Chart(_internal_data(lbl_df))
                    .mark_text(
                        fontSize=fontSize,
                        color=span_color,
                        baseline=label_baseline,
                        align="center",
                    )
                    .encode(
                        x=alt.value(x_mid),
                        y=alt.value(label_y),
                        text=alt.Text("__slabel:N"),
                    )
                )

    if defer_cat_label:
        label_y = chart_h + label_y_offset + extra
        chart_h += categoryLabelHeight or 0
        label_df = pl.DataFrame({"__category": categories, "__display": [_display(c) for c in categories]})
        layers.append(
            alt.Chart(_internal_data(label_df))
            .mark_text(
                fontSize=fontSize,
                angle=categoryLabelAngle % 360,
                align="center" if categoryLabelAngle % 360 == 0 else "right",
                baseline="middle",
            )
            # __category stays raw (it is the band-scale position); __display is the text
            .encode(x=x_enc, y=alt.value(label_y), text=alt.Text("__display:N"))
        )

    return cast(
        alt.LayerChart,
        alt.layer(*layers).properties(width=chartWidth, height=chart_h, view={"fill": None, "stroke": None}),
    )


def add_multilabel(
    chart: alt.Chart | alt.LayerChart | alt.ConcatChart | alt.VConcatChart | alt.HConcatChart,
    groups: dict[str, list[Any]] | None = None,
    categories: list[str] | None = None,
    *,
    spacing: float = 0,
    showSampleSize: bool = False,
    data: "pl.DataFrame | pd.DataFrame | None" = None,
    x: str | None = None,
    sampleSizeIndex: int = 0,
    sampleSizeLabel: str = "n =",
    order: list[str] | None = None,
    style: str = "plusminus",
    rowStyles: dict[str, str] | list[str] | None = None,
    labelPosition: str = "left",
    labelPadding: float = 0,
    symbol: str = "circle",
    symbolSize: float | None = None,
    palette: list[str] | None = None,
    strokeWidth: float | None = None,
    connectingLine: bool = True,
    lineOrientation: str = "vertical",
    chartWidth: float | None = None,
    fontSize: float | None = None,
    rowHeight: int | float | dict[str, int | float] | list[int | float] | None = None,
    rowValueAngle: int | float | dict[str, Any] | list[Any] | None = None,
    categoryLabel: bool = False,
    categoryLabelPosition: str = "bottom",
    labelMap: dict[str, Any] | None = None,
    categoryLabelAngle: float = -45,
    categoryLabelHeight: float | None = None,
    span: dict[str | None, list[str]] | list[dict[str | None, list[str]]] | None = None,
    spanBracketStyle: str = "line",
    spanLabelPosition: str = "bottom",
    spanBracketReverse: bool = True,
    spanTickHeight: float | None = None,
    spanGap: float | None = None,
) -> alt.VConcatChart:
    """
    Compose a chart with a grid annotation table, replacing its x-axis labels.

    Accepts ``alt.Chart`` or ``alt.LayerChart`` (e.g. a strip+boxplot layer), and also a
    concatenated chart - ``_strip_x_labels`` recurses into ``vconcat``/``hconcat`` panels, so a
    stack of panels sharing one x-layout (e.g. ``ds.biology.western_blot``'s image strips) gets
    the table below the whole stack. A ``vconcat`` is the sensible case; a table under an
    ``hconcat`` of differently-x'd panels composes but rarely aligns meaningfully.
    Strips x-axis labels and ticks from ``chart``, builds a condition table via
    :func:`_multilabel_layer`, and returns
    ``alt.vconcat(chart, annotation, spacing=spacing).resolve_scale(x="shared")``.

    Both ``groups`` and ``categories`` are optional. Omit ``groups`` (or pass
    ``{}``) when you only need sample sizes or category labels.


    Parameters
    ----------
    chart:
        The main Altair chart (any type: ``Chart``, ``LayerChart``, etc.).
    groups:
        ``{row_label: [value, ...]}`` mapping, one value per category. Defaults
        to ``{}`` — omit entirely when only ``showSampleSize`` or
        ``categoryLabel`` is needed.
    categories:
        Ordered list of x-axis categories matching the main chart. Defaults to
        ``None`` (empty list); must be provided when ``showSampleSize=True`` or
        when ``categoryLabel=True``.
    spacing:
        Vertical gap in pixels between the chart and the annotation table.
        Defaults to ``0`` so the annotation sits flush below the axis line.
    showSampleSize:
        When ``True``, injects a per-category sample size row computed from
        ``data``. Requires ``data`` and ``x``. The row always renders as
        ``"text"`` regardless of the global ``style`` setting.
    data:
        Source DataFrame (Polars or Pandas) for counting samples per category.
        Only used when ``showSampleSize=True``.
    x:
        Column name in ``data`` used for x-axis grouping.
        Only used when ``showSampleSize=True``.
    sampleSizeIndex:
        Insertion index among the ``groups`` rows, using ``list.insert()``
        semantics. ``0`` (default) places the n-row first; ``len(groups)``
        places it last. Negative indices follow Python convention (``-1`` is
        second-to-last, not last). Applies to ``order`` too when one is given,
        unless that ``order`` names ``sampleSizeLabel`` itself.
    sampleSizeLabel:
        Row label for the sample size row. Defaults to ``"n ="``. Name it in
        ``order`` to place the row yourself.
    order:
        Row display order (top to bottom). Defaults to ``dict`` insertion order.
        Every listed label must be a key of ``groups`` and must occur only once; listing only some
        rows displays only those rows. Per-row mapping options are checked against all keys in
        ``groups``, including rows omitted from ``order``.
    style:
        Global default style for all rows. ``"plusminus"`` renders ``True`` as ``+``
        and ``False`` as ``−``. ``"symbol"`` renders ``True`` as a filled mark and
        ``False`` as an unfilled mark, with a connecting rule between consecutive
        ``True`` values (direction set by ``lineOrientation``). The mark shape is
        controlled by ``symbol``. ``"text"`` renders raw group values as
        center-aligned strings and is forced automatically per row when any value in
        that row is non-bool. Override per row with ``rowStyles``.
    rowStyles:
        Per-row style overrides. Accepts either a ``dict`` mapping row labels to
        style strings (``{"Row A": "symbol", "Row B": "text"}``) or a ``list`` of
        style strings in row-display order (``["symbol", "text"]``). Accepts the
        same values as ``style``. Non-bool rows always render as ``"text"``
        regardless of this setting. Connecting rules only span between ``"symbol"``
        rows; rows of other styles between symbol rows are skipped in run detection.
    labelPosition:
        ``"left"`` (default) places row labels to the left of the grid with
        right-aligned text. ``"right"`` places them to the right with left-aligned text.
    labelPadding:
        Gap in pixels between the plot boundary and the label text. Vega-Lite's
        default is 2. Negative values pull the labels into the plot area.
    symbol:
        Vega-Lite shape name for ``"symbol"`` style marks (e.g. ``"circle"``,
        ``"square"``, ``"diamond"``, ``"triangle-up"``). Defaults to ``"circle"``.
    symbolSize:
        Area (in square pixels) of each symbol. Defaults to ``markSize * 4``
        from ``ds.theme()``.
    palette:
        List of colors used to fill annotation marks in ``"symbol"`` style.
        ``palette[0]`` overrides the ``False`` mark color and ``palette[-1]`` the
        ``True`` mark color. Overrides darkmode defaults when provided. Pass the
        result of ``ds.palette()`` directly.
    strokeWidth:
        Stroke width applied to dot marks and the connecting rule. Defaults
        to ``markStrokeWidth`` from ``ds.theme()``.
    connectingLine:
        When ``True`` (default), draws a rule spanning each consecutive run of
        ``True`` values (``"symbol"`` style only). Set to ``False`` to show
        symbols only. Direction is controlled by ``lineOrientation``.
    lineOrientation:
        Direction of the connecting rule. ``"vertical"`` (default) draws a rule
        down each column spanning consecutive ``True`` rows. ``"horizontal"``
        draws a rule across each row spanning consecutive ``True`` columns.
    chartWidth:
        Width of the annotation chart in pixels. Inherits ``width`` from
        ``ds.theme()`` when not set.
    fontSize:
        Font size for ``"text"`` style symbols and row labels. Inherits ``fontSize``
        from ``ds.theme()`` when not set.
    rowHeight:
        Height in pixels per annotation row. Accepts a single number applied to every
        row, a ``dict`` mapping row labels to heights, or a ``list`` of heights in
        row-display order. A ``dict`` may be partial; unlisted rows are auto-sized.
        Auto-sizing gives an unrotated row ``10`` px and a rotated row the height of
        its rotated text bounding box (never less than ``10``).
    rowValueAngle:
        Rotation of the row's values in degrees, in every style — the text of a
        ``"text"`` or ``"plusminus"`` row, and the marks of a ``"symbol"`` row.
        Accepts a single number applied to every row, a ``dict`` mapping row labels to
        angles, or a ``list`` of angles in row-display order. Defaults to ``0``
        (horizontal). Use ``-90`` to read bottom-to-top and ``90`` to read
        top-to-bottom. Values rotate about their own center, so they stay centered on
        the category, and rotated rows grow to fit their tallest rotated cell unless
        ``rowHeight`` pins them. Row labels are never rotated. Rotating the default
        ``"circle"`` symbol has no visible effect; use a shape with lineOrientation, such
        as ``symbol="triangle-up"``.

        A single row's angle may itself be a ``list`` — one angle per x-axis category —
        to rotate only some cells, e.g. standing dose values on end while leaving the
        ``-`` placeholders of the untreated controls upright::

            rowValueAngle={"dose": [0, 0, -90, -90, -90]}
    categoryLabel:
        When ``True``, renders the x-axis category names as angled text in a
        dedicated row, replacing the main chart's stripped axis labels within the
        annotation. Defaults to ``False``.
    categoryLabelPosition:
        Where to place the category label row relative to the data rows.
        ``"bottom"`` (default) places labels below all rows; ``"top"`` places
        them above.
    categoryLabelAngle:
        Rotation angle of the category name text in degrees. Defaults to ``-45``.
    categoryLabelHeight:
        Height in pixels reserved for the x-label row. Auto-computed from
        ``fontSize``, ``categoryLabelAngle``, and the longest category name when ``None``
        (default): ``ceil(fontSize × 0.6 × max_len × |sin(angle)| + fontSize ×
        |cos(angle)|)``.
    labelMap:
        ``{raw_value: label}`` mapping applied to the category-label row (plain lookup;
        the data and band positions keep the raw values). List labels are space-joined
        here - use the mark constructors' ``labelMap`` for true multi-line axis labels.
    span:
        Dict mapping span label → list of categories, or a list of such
        single-entry dicts (one per span). The span extends from the lowest
        to the highest index in ``categories`` found in the list. Use ``""``
        as a key (or ``None``) to draw a rule/bracket with no label; the list
        form allows multiple unlabeled spans without key collisions::

            span={"Group 1": ["Cat A", "Cat B"], "Group 2": ["Cat C", "Cat D"]}

            span=[{None: ["Cat A", "Cat B"]}, {None: ["Cat C", "Cat D"]}]
    spanBracketStyle:
        ``"line"`` (default) draws a plain horizontal rule. ``"bracket"`` adds
        vertical end ticks at the left and right edges of the span.
    spanLabelPosition:
        Where to place the span label relative to the rule. ``"bottom"``
        (default) places it below; ``"top"`` places it above.
    spanBracketReverse:
        When ``True`` (default), bracket end ticks point toward the annotation
        rows. When ``False``, they point away. No effect when
        ``spanBracketStyle="line"``.
    spanTickHeight:
        Height in pixels of the bracket end ticks. Defaults to the active
        theme ``tickSize``. Only used when ``spanBracketStyle="bracket"``.
    spanGap:
        Vertical gap in pixels between the last annotation row and the span
        rule. Defaults to ``rowHeight × 0.3``.

    Examples
    --------
    ::

        chart = ds.mark_strip(data, "group", "value", CATEGORIES)

        # Full multilabel with sample sizes and category labels
        composed = ds.add_multilabel(
            chart,
            {"Condition A": [False, True, True, True]},
            categories=CATEGORIES,
            style="symbol",
            showSampleSize=True,
            data=data,
            x="group",
            categoryLabel=True,
        )
        ds.save(composed, "my_plot")

        # Sample sizes only — no groups needed
        ds.add_multilabel(chart, categories=CATEGORIES, showSampleSize=True, data=data, x="group")
    """
    xCol = x
    import copy

    if groups is None:
        groups = {}
    if categories is None:
        categories = []

    if showSampleSize:
        if data is None or xCol is None:
            raise ValueError("showSampleSize=True requires both 'data' and 'x'.")
        # The injected row shares the groups dict, so a same-named row of the caller's would
        # be silently replaced - by the counts, or by their own values, depending on `order`.
        if sampleSizeLabel in groups:
            raise ValueError(
                f"groups already has a row labelled {sampleSizeLabel!r}, which is the label "
                f"showSampleSize=True adds. Rename that row, or pass sampleSizeLabel= to use "
                f"a different label for the sample size row."
            )
        counts = _count_n(data, xCol, categories)
        # Pin each list to its row labels before the n-row joins groups, or the entries
        # shift by one. The basis is the DISPLAY order, matching how _multilabel_layer
        # zips a list, and the length is checked here because that check sees a dict.
        list_order = order or list(groups.keys())

        def _pin(value: Any, name: str) -> Any:
            if not isinstance(value, list):
                return value
            if len(value) != len(list_order):
                raise ValueError(f"{name} list has {len(value)} entries but there are {len(list_order)} rows.")
            return dict(zip(list_order, value))

        rowValueAngle = _pin(rowValueAngle, "rowValueAngle")
        rowHeight = _pin(rowHeight, "rowHeight")
        # Explicitly force the n-row to text style regardless of the global
        # style setting (e.g. "symbol") — counts always render as plain text.
        rowStyles = {**(_pin(rowStyles, "rowStyles") or {}), sampleSizeLabel: "text"}
        # An explicit order omits the injected row, so seat it at sampleSizeIndex - after the
        # list normalization above, whose lengths count the caller's own rows.
        if order and sampleSizeLabel not in order:
            order = [*order[:sampleSizeIndex], sampleSizeLabel, *order[sampleSizeIndex:]]
        items = list(groups.items())
        items.insert(sampleSizeIndex, (sampleSizeLabel, counts))
        groups = dict(items)

    modified = copy.deepcopy(chart)

    def _strip_x_labels(node: alt.SchemaBase) -> None:
        # _kwds is used directly because `.axis` on alt.X returns a _PropertySetter
        # descriptor, not the stored value — reading it would not give the Axis object.
        if isinstance(node, alt.Chart):
            enc = node._kwds.get("encoding", alt.Undefined)
            if enc is not alt.Undefined:
                x = enc._kwds.get("x", alt.Undefined)
                if x is not alt.Undefined and isinstance(x, alt.X):
                    axis = x._kwds.get("axis", alt.Undefined)
                    # An explicit axis=None means the layer HIDES its axis (e.g.
                    # mark_violin's internal pixel-x layers) - leave it hidden.
                    # Replacing it with Axis(labels=False) re-enables the domain
                    # line and ticks (a phantom axis above the chart).
                    if axis is alt.Undefined:
                        x._kwds["axis"] = alt.Axis(labels=False, title=None)
                    elif isinstance(axis, alt.Axis):
                        axis._kwds["labels"] = False
                        axis._kwds["title"] = None
        if isinstance(node, alt.LayerChart):
            for layer in node._kwds.get("layer", []):
                _strip_x_labels(layer)
        if hasattr(node, "_kwds"):
            for sub in node._kwds.get("vconcat", []):
                _strip_x_labels(sub)
            for sub in node._kwds.get("hconcat", []):
                _strip_x_labels(sub)

    _strip_x_labels(modified)
    ann = _multilabel_layer(
        groups,
        categories,
        order=order,
        style=style,
        rowStyles=rowStyles,
        labelAlign=labelPosition,
        labelPadding=labelPadding,
        symbol=symbol,
        symbolSize=symbolSize,
        palette=palette,
        strokeWidth=strokeWidth,
        connectingLine=connectingLine,
        orientation=lineOrientation,
        chartWidth=chartWidth,
        fontSize=fontSize,
        rowHeight=rowHeight,
        rowValueAngle=rowValueAngle,
        categoryLabel=categoryLabel,
        categoryLabelPosition=categoryLabelPosition,
        labelMap=labelMap,
        categoryLabelAngle=categoryLabelAngle,
        categoryLabelHeight=categoryLabelHeight,
        span=span,
        spanBracketStyle=spanBracketStyle,
        spanLabelPosition=spanLabelPosition,
        spanBracketReverse=spanBracketReverse,
        spanTickHeight=spanTickHeight,
        spanGap=spanGap,
    )
    return alt.vconcat(modified, ann, spacing=spacing).resolve_scale(x="shared")
