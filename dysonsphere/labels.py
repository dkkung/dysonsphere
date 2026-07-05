"""Display-label helpers: map raw data values to presentable labels at render time."""

from typing import Any

# Escapes for embedding a Python string inside a single-quoted Vega expression literal.
_JS_ESCAPE = str.maketrans({"\\": "\\\\", "'": "\\'"})


def _js_literal(value: Any) -> str:
    """Render a Python value as a Vega expression literal (string, number, or bool)."""
    if isinstance(value, str):
        return f"'{value.translate(_JS_ESCAPE)}'"
    if isinstance(value, bool):  # before int: bool is an int subclass
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    raise TypeError(f"label_expr keys and labels must be str, int, float, or bool; got {type(value).__name__}")


def label_expr(mapping: dict[Any, str | list[str]]) -> str:
    """
    Build a Vega ``labelExpr`` that maps raw data values to display labels.

    The common Altair pain: the dataframe holds machine values (``metadata_group1``)
    but the plot needs presentable labels (``group 1``), and hand-writing the Vega
    expression is tedious and quoting-fragile. This returns that expression for you::

        expr = ds.label_expr({"metadata_group1": "group 1", "metadata_group2": "group 2"})
        alt.X("treatment:N", axis=alt.Axis(labelExpr=expr))

    The same string works everywhere Vega-Lite accepts a label expression: axis tick
    labels (``alt.Axis(labelExpr=)``), legend entries (``alt.Legend(labelExpr=)``),
    and facet headers (``alt.Header(labelExpr=)``). Only the rendered labels change -
    the data, exported JSON, checksums, and statistics records keep the raw values.

    Parameters
    ----------
    mapping:
        ``{raw_value: label}``. Keys may be strings or numbers (compared against
        ``datum.value``). A label may be a single string, or a **list of strings for a
        multi-line label** (each list item renders as one line). Values not present in
        the mapping fall back to the raw value; map a value to ``""`` to hide it.

    Returns
    -------
    str
        A Vega expression - a ternary chain, e.g.
        ``"datum.value == 'a' ? 'A' : datum.value == 'b' ? 'B' : datum.value"``.
        (A ternary chain rather than the object-lookup idiom
        ``{...}[datum.value] || datum.value``, whose ``||`` fallback silently
        misfires for falsy labels like ``""`` or ``0``.)

    Examples
    --------
    ::

        labels = {"tnf_10ng": ["TNF-α", "(10 ng/mL)"], "ctrl": "Control"}  # multi-line + plain
        chart = alt.Chart(df).mark_point().encode(
            x=alt.X("treatment:N", axis=alt.Axis(labelExpr=ds.label_expr(labels))),
            color=alt.Color("treatment:N", legend=alt.Legend(labelExpr=ds.label_expr(labels))),
            y="value:Q",
        )
    """
    if not isinstance(mapping, dict) or not mapping:
        raise ValueError(f"mapping must be a non-empty dict, got {mapping!r}")
    parts = []
    for raw, label in mapping.items():
        if isinstance(label, list):
            if not label or not all(isinstance(line, str) for line in label):
                raise TypeError(f"a multi-line label must be a non-empty list of str, got {label!r}")
            rendered = "[" + ", ".join(_js_literal(line) for line in label) + "]"
        elif isinstance(label, str):
            rendered = _js_literal(label)
        else:
            raise TypeError(f"label for {raw!r} must be a str or list of str, got {type(label).__name__}")
        parts.append(f"datum.value == {_js_literal(raw)} ? {rendered}")
    return " : ".join(parts) + " : datum.value"
