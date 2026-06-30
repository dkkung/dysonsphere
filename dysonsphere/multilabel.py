import math
from typing import cast

import altair as alt
import polars as pl

from .utils import count_n


def _multilabel_layer(
    groups: dict[str, list],
    categories: list[str],
    *,
    order: list[str] | None = None,
    style: str = "plusminus",
    rowStyles: dict[str, str] | list[str] | None = None,
    labelAlign: str = "left",
    labelPadding: int = 0,
    symbol: str = "circle",
    symbolSize: int | None = None,
    palette: list[str] | None = None,
    strokeWidth: float | None = None,
    connectingLine: bool = True,
    orientation: str = "vertical",
    yPadding: float | None = None,
    chartWidth: int | None = None,
    fontSize: int | None = None,
    rowHeight: int | float | None = None,
    categoryLabel: bool = False,
    categoryLabelPosition: str = "bottom",
    categoryLabelAngle: int = -45,
    categoryLabelHeight: int | None = None,
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

    Parameters
    ----------
    groups:
        Mapping of row-label → list of values, one per category. Values may be:

        - **bool** — ``True`` renders a positive mark; ``False`` renders a negative
          mark. The ``style`` parameter controls how positive/negative are displayed
          (``"plusminus"`` or ``"dots"``).
        - **str, int, or float** — any non-bool value triggers automatic ``style="text"``
          regardless of the ``style`` parameter, and each value is rendered verbatim as
          a string.

        Length of each list must equal ``len(categories)``.
    categories:
        Ordered list of x-axis categories — the same list passed to ``mark_strip``
        or ``mark_violin``.
    order:
        Row display order (top to bottom). Defaults to ``dict`` insertion order.
    style:
        Global default style for all rows. ``"plusminus"`` renders ``True`` as ``+``
        and ``False`` as ``−``. ``"symbol"`` renders ``True`` as a filled mark and
        ``False`` as an unfilled mark, with a connecting rule between consecutive
        ``True`` values (direction set by ``orientation``). The mark shape is
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
    labelAlign:
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
        symbols only. Direction is controlled by ``orientation``.
    orientation:
        Direction of the connecting rule. ``"vertical"`` (default) draws a rule
        down each column spanning consecutive ``True`` rows. ``"horizontal"``
        draws a rule across each row spanning consecutive ``True`` columns.
    yPadding:
        Inner padding between rows as a fraction of the band step (0–1).
        ``0`` means no gap; ``1`` means bands collapse to zero width.
        Defaults to Vega-Lite's band scale default of ``0.1``.
    chartWidth:
        Width of the annotation chart in pixels. Inherits ``chartWidth`` from
        ``ds.theme()`` when not set.
    fontSize:
        Font size for ``"text"`` style symbols and row labels. Inherits ``fontSize``
        from ``ds.theme()`` when not set.
    rowHeight:
        Height in pixels per annotation row. Defaults to ``fontSize * 1.5``.
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

    Notes
    -----
    **Row label alignment.** Row labels are rendered as explicit ``mark_text`` marks
    (not as y-axis labels) so they share the exact same y coordinate as the content
    marks. Vega-Lite's axis label rendering pipeline does not guarantee pixel-perfect
    alignment with ``mark_text`` even when both use ``baseline="middle"``, so the y
    axis is suppressed and labels are placed via ``alt.value(x)`` instead.

    **``bandPosition=0.5``** is set explicitly on the shared ``y_enc`` rather than
    relying on each mark type's default, which differs across mark types and may
    change between Vega-Lite versions.

    **``align="center"``** is required on all ``mark_text`` content marks. Without it,
    Vega-Lite's vertical band placement drifts relative to other marks on some versions.

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
        ds.theme(chartWidth=300)
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

    row_order = order if order is not None else list(groups.keys())

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
        raise ValueError(f"labelAlign must be 'left' or 'right', got {labelAlign!r}")
    if orientation not in ("vertical", "horizontal"):
        raise ValueError(f"orientation must be 'vertical' or 'horizontal', got {orientation!r}")
    if spanBracketStyle not in ("line", "bracket"):
        raise ValueError(f"spanBracketStyle must be 'line' or 'bracket', got {spanBracketStyle!r}")
    if spanLabelPosition not in ("top", "bottom"):
        raise ValueError(f"spanLabelPosition must be 'top' or 'bottom', got {spanLabelPosition!r}")

    # Normalise rowStyles to a dict so the rest of the code has a single code path.
    if isinstance(rowStyles, list):
        if len(rowStyles) != len(row_order):
            raise ValueError(f"rowStyles list has {len(rowStyles)} entries but there are {len(row_order)} rows.")
        rowStyles = dict(zip(row_order, rowStyles))

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
        chartWidth = alt.theme.options.get("chartWidth", 100)
    if fontSize is None:
        fontSize = alt.theme.options.get("fontSize", 7)
    if rowHeight is None:
        rowHeight = 10

    # When categoryLabel="bottom" and spans are present, defer the label row
    # to below the spans section so the visual order is: rows → spans → labels.
    defer_cat_label = bool(categoryLabel and span and categoryLabelPosition != "top")

    band_range = None
    label_y = 0.0
    label_y_offset = 0.0
    extra = 0.0
    if categoryLabel:
        if categoryLabelPosition not in ("top", "bottom"):
            raise ValueError(f"categoryLabelPosition={categoryLabelPosition!r} is invalid. Use 'top' or 'bottom'.")
        max_len = max(len(cat) for cat in categories)
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
            band_range = [
                categoryLabelHeight,
                len(row_order) * rowHeight + categoryLabelHeight,
            ]
            label_y = label_y_offset
        else:
            band_range = [0, len(row_order) * rowHeight]
            if not defer_cat_label:
                label_y = len(row_order) * rowHeight + label_y_offset + extra

    # When spans are present, chart_h will grow beyond n*rowHeight. Without an
    # explicit range, Vega auto-fits the band scale to the full chart height,
    # stretching rows into the span section. Anchoring the range prevents this.
    if span and band_range is None:
        band_range = [0, len(row_order) * rowHeight]

    def _norm(v: object) -> str:
        if isinstance(v, bool):
            return "+" if v else "−"
        return str(v)

    rows = [
        {"__label": label, "__category": cat, "__value": _norm(val)}
        for label in row_order
        for cat, val in zip(categories, groups[label])
    ]
    marks_df = pl.DataFrame(rows)

    chart_h = len(row_order) * rowHeight + (
        0 if defer_cat_label else (categoryLabelHeight or 0 if categoryLabel else 0)
    )

    x_enc = alt.X(
        "__category:N",
        sort=categories,
        axis=alt.Axis(labels=False, ticks=False, domain=False, grid=False, title=None),
    )
    y_scale = alt.Scale(
        domain=row_order,
        **({"range": band_range} if band_range is not None else {}),
        **({"paddingInner": yPadding} if yPadding is not None else {}),
    )
    # Axis suppressed; row labels are explicit mark_text in row_labels layer below.
    # bandPosition=0.5 is explicit because per-mark defaults vary across mark types.
    y_enc = alt.Y(
        "__label:N",
        sort=row_order,
        bandPosition=0.5,
        scale=y_scale,
        axis=alt.Axis(labels=False, ticks=False, domain=False, grid=False, title=None),
    )

    if labelAlign == "right":
        label_x = alt.value(chartWidth + labelPadding)
    else:
        label_x = alt.value(-labelPadding)
    label_text_align = "left" if labelAlign == "right" else "right"
    label_df = pl.DataFrame({"__label": row_order})
    row_labels = (
        alt.Chart(label_df)
        .mark_text(fontSize=fontSize, align=label_text_align, baseline="middle")
        .encode(x=label_x, y=y_enc, text=alt.Text("__label:N"))
    )

    layers: list = [row_labels]

    # --- plusminus rows ---
    if plusminus_rows:
        pm_df = marks_df.filter(pl.col("__label").is_in(plusminus_rows))
        # align="center" is required — without it Vega-Lite's vertical band
        # placement drifts relative to other marks on some versions.
        layers.append(
            alt.Chart(pm_df)
            .mark_text(fontSize=fontSize, align="center", baseline="middle")
            .encode(x=x_enc, y=y_enc, text=alt.Text("__value:N"))
        )

    # --- text rows ---
    if text_rows:
        text_df = marks_df.filter(pl.col("__label").is_in(text_rows))
        layers.append(
            alt.Chart(text_df)
            .mark_text(fontSize=fontSize, align="center", baseline="middle")
            .encode(x=x_enc, y=y_enc, text=alt.Text("__value:N"))
        )

    # --- symbol rows ---
    if symbol_rows:
        # Colours are resolved at call time from alt.theme.options so that darkmode
        # variants are correct. Use a callable with ds.save() to rebuild per variant.
        darkmode = alt.theme.options.get("darkmode", False)
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
            symbolSize = alt.theme.options.get("markSize", 10) * 4
        if strokeWidth is None:
            strokeWidth = alt.theme.options.get("markStrokeWidth", 0.25)

        plus_df = marks_df.filter(pl.col("__label").is_in(symbol_rows) & (pl.col("__value") == "+"))
        minus_df = marks_df.filter(pl.col("__label").is_in(symbol_rows) & (pl.col("__value") == "−"))

        symbol_dy = -fontSize * 0.1

        positive = (
            alt.Chart(plus_df)
            .mark_point(
                shape=symbol,
                filled=True,
                color=positive_color,
                strokeWidth=strokeWidth,
                size=symbolSize,
                dy=symbol_dy,
            )
            .encode(x=x_enc, y=y_enc)
        )
        negative = (
            alt.Chart(minus_df)
            .mark_point(
                shape=symbol,
                filled=True,
                fill=negative_fill,
                stroke=negative_stroke,
                strokeWidth=strokeWidth,
                size=symbolSize,
                dy=symbol_dy,
            )
            .encode(x=x_enc, y=y_enc)
        )

        # Connecting lines only span between symbol rows; non-symbol rows between
        # two symbol rows are skipped in run detection (they don't break runs).
        symbol_row_set = set(symbol_rows)
        line_rows = []
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
            lines_df = pl.DataFrame(line_rows)
            if orientation == "horizontal":
                lines = (
                    alt.Chart(lines_df)
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
                    alt.Chart(lines_df)
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
        label_df = pl.DataFrame({"__category": categories})
        layers.append(
            alt.Chart(label_df)
            .mark_text(
                fontSize=fontSize,
                angle=categoryLabelAngle % 360,
                align="center" if categoryLabelAngle % 360 == 0 else "right",
                baseline="middle",
            )
            .encode(x=x_enc, y=alt.value(label_y), text=alt.Text("__category:N"))
        )

    if span:
        span_pairs: list[tuple[str | None, list[str]]]
        if isinstance(span, list):
            span_pairs = [(k, v) for d in span for k, v in d.items()]
        else:
            span_pairs = list(span.items())

        if spanTickHeight is None:
            spanTickHeight = alt.theme.options.get("tickSize", 3)

        band_padding = alt.theme.options.get("bandPadding", 0.1)
        n_cats = len(categories)
        step = chartWidth / (n_cats + 2 * band_padding)
        axisWidth_val = alt.theme.options.get("axisWidth", 0.25)
        darkmode_val = alt.theme.options.get("darkmode", False)
        span_color = "white" if darkmode_val else "black"
        _one_row = {"values": [{}]}

        span_gap = rowHeight * 0.3 if spanGap is None else spanGap
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

            x1 = step * (band_padding + 0.5 + i_start) - step * 0.30
            x2 = step * (band_padding + 0.5 + i_end) + step * 0.30
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
                    alt.Chart(lbl_df)
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
        label_df = pl.DataFrame({"__category": categories})
        layers.append(
            alt.Chart(label_df)
            .mark_text(
                fontSize=fontSize,
                angle=categoryLabelAngle % 360,
                align="center" if categoryLabelAngle % 360 == 0 else "right",
                baseline="middle",
            )
            .encode(x=x_enc, y=alt.value(label_y), text=alt.Text("__category:N"))
        )

    return cast(
        alt.LayerChart,
        alt.layer(*layers).properties(width=chartWidth, height=chart_h, view={"fill": None, "stroke": None}),
    )


def add_multilabel(
    chart: alt.Chart | alt.LayerChart,
    groups: dict[str, list] | None = None,
    categories: list[str] | None = None,
    *,
    spacing: int = 0,
    showSampleSize: bool = False,
    df=None,
    xCol: str | None = None,
    sampleSizeIndex: int = 0,
    sampleSizeLabel: str = "n =",
    **kwargs,
) -> alt.VConcatChart:
    """
    Compose a chart with a grid annotation table, replacing its x-axis labels.

    Accepts ``alt.Chart`` or ``alt.LayerChart`` (e.g. a strip+boxplot layer).
    Strips x-axis labels and ticks from ``chart``, builds a condition table via
    :func:`_multilabel_layer`, and returns
    ``alt.vconcat(chart, annotation, spacing=spacing).resolve_scale(x="shared")``.

    Both ``groups`` and ``categories`` are optional. Omit ``groups`` (or pass
    ``{}``) when you only need sample sizes or category labels.

    All keyword arguments beyond the named parameters are forwarded to
    :func:`_multilabel_layer` — see its docstring for the full parameter list,
    including ``style``, ``rowStyles``, ``categoryLabel``,
    ``categoryLabelPosition``, ``categoryLabelAngle``, ``categoryLabelHeight``,
    ``span``, ``spanBracketStyle``, ``spanLabelPosition``, ``spanBracketReverse``,
    ``spanTickHeight``, and ``spanGap``.

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
        ``df``. Requires ``df`` and ``xCol``. The row always renders as
        ``"text"`` regardless of the global ``style`` setting.
    df:
        Source DataFrame (Polars or Pandas) for counting samples per category.
        Only used when ``showSampleSize=True``.
    xCol:
        Column name in ``df`` used for x-axis grouping.
        Only used when ``showSampleSize=True``.
    sampleSizeIndex:
        Insertion index among the ``groups`` rows, using ``list.insert()``
        semantics. ``0`` (default) places the n-row first; ``len(groups)``
        places it last. Negative indices follow Python convention (``-1`` is
        second-to-last, not last).
    sampleSizeLabel:
        Row label for the sample size row. Defaults to ``"n ="``.

    Examples
    --------
    ::

        chart = ds.mark_strip(df, "group", "value", CATEGORIES)

        # Full multilabel with sample sizes and category labels
        composed = ds.add_multilabel(
            chart,
            {"Condition A": [False, True, True, True]},
            categories=CATEGORIES,
            style="symbol",
            showSampleSize=True,
            df=df,
            xCol="group",
            categoryLabel=True,
        )
        ds.save(composed, "my_plot")

        # Sample sizes only — no groups needed
        ds.add_multilabel(chart, categories=CATEGORIES, showSampleSize=True, df=df, xCol="group")
    """
    import copy

    if groups is None:
        groups = {}
    if categories is None:
        categories = []

    if showSampleSize:
        if df is None or xCol is None:
            raise ValueError("showSampleSize=True requires both 'df' and 'xCol'.")
        counts = count_n(df, xCol, categories)
        # Normalize rowStyles before modifying groups so that list indices
        # still correspond to the original row order.
        raw_styles = kwargs.pop("rowStyles", None)
        if isinstance(raw_styles, list):
            row_styles = dict(zip(groups.keys(), raw_styles))
        elif isinstance(raw_styles, dict):
            row_styles = dict(raw_styles)
        else:
            row_styles = {}
        # Explicitly force the n-row to text style regardless of the global
        # style setting (e.g. "symbol") — counts always render as plain text.
        row_styles[sampleSizeLabel] = "text"
        kwargs["rowStyles"] = row_styles
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
                    if axis is alt.Undefined or axis is None:
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
    ann = _multilabel_layer(groups, categories, **kwargs)
    return alt.vconcat(modified, ann, spacing=spacing).resolve_scale(x="shared")
