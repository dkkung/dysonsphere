"""Western blot figure: stacked blot-strip images with a dysonsphere condition table below.

Built on public surfaces - core (``ds.add_multilabel`` / ``ds.ensure_polars``) plus the
extension primitive surface (``dysonsphere.ext``). Each blot image is loaded, scaled to the
shared chart width (aspect preserved), optionally bordered, and stacked; the stack is handed to
``ds.add_multilabel`` so the whole condition-table machinery (``+``/``-`` rows, symbols, spans,
sample sizes, category labels) annotates the lanes below the blots.

The condition table is ALWAYS evenly spaced (dysonsphere's band geometry) - it is not aligned to
the physical lane positions in the image. Molecular-weight markers are intentionally out of scope:
composite a cropped image of the ladder standards in post-processing instead.
"""

from __future__ import annotations

import base64
import io
from typing import Any

import altair as alt

import dysonsphere as ds
from dysonsphere import ext


def _load_image(image: Any) -> tuple[str, int, int]:
    """Return ``(data_uri, width_px, height_px)`` for a blot image.

    Accepts a file path, an existing ``data:`` URI, or a PIL ``Image``. A file path embeds its
    ORIGINAL bytes (no re-encode) with the detected MIME type, so the exported spec is
    self-contained; a PIL image is re-encoded to PNG. Pillow is used only to read the pixel
    dimensions (for the aspect-preserving display height).
    """
    try:
        from PIL import Image
    except ImportError as e:  # pragma: no cover - environment-dependent
        raise ImportError("western_blot() needs Pillow to read blot images (pip install pillow).") from e

    if isinstance(image, str) and image.startswith("data:"):
        _, b64 = image.split(",", 1)
        im = Image.open(io.BytesIO(base64.b64decode(b64)))
        return image, im.width, im.height
    if isinstance(image, str):
        raw = open(image, "rb").read()
        im = Image.open(io.BytesIO(raw))
        mime = Image.MIME.get(im.format or "", "image/png")
        return f"data:{mime};base64," + base64.b64encode(raw).decode(), im.width, im.height
    if hasattr(image, "save"):  # a PIL Image
        buf = io.BytesIO()
        image.convert("RGB").save(buf, "PNG")
        return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode(), image.width, image.height
    raise TypeError(f"image must be a file path, data URI, or PIL Image; got {type(image).__name__}")


def western_blot(
    images: Any,
    groups: dict[str, list[Any]] | None = None,
    categories: list[str] | None = None,
    *,
    stroke: bool | float = True,
    padding: float = 0.0,
    **kwargs: Any,
) -> ext.AltairChart:
    """Compose western blot strip image(s) with a dysonsphere condition table.

    Each image is scaled to the theme's ``chartWidth`` (aspect preserved), the strips are stacked
    vertically, and the stack is annotated with :func:`dysonsphere.add_multilabel` - so the
    lane/condition table (``+``/``-`` rows, dot symbols, spans, sample sizes, category labels)
    renders beneath the blots. Returns an ``alt.VConcatChart``; pass it to ``ds.save()``.

    The condition table is always evenly spaced across the width (it is not warped to the physical
    lane positions); crop your blots so the lanes are roughly even, or align by hand in
    post-processing. Molecular-weight ladders are out of scope - composite an image of the
    standards separately.

    The blot border is darkmode-aware (resolved from the active theme at call time), so build
    inside a ``ds.save(lambda: western_blot(...))`` callable for correct light/dark export.

    Parameters
    ----------
    images:
        One blot strip or several, stacked top-to-bottom. Each is a file path, a ``data:`` URI,
        or a PIL ``Image``.
    groups:
        The condition-table rows, ``{row_label: [value, ...]}`` with one value per lane - passed
        straight to :func:`dysonsphere.add_multilabel` (booleans render as ``+``/``-`` or dot
        symbols; other values render as text).
    categories:
        The lane labels, left to right - the ``categories`` argument of
        :func:`dysonsphere.add_multilabel`.
    stroke:
        Border around each blot image, following the ``bool | float`` pattern: ``True`` (default)
        -> a darkmode-aware ``markStrokeWidth`` border; ``False`` -> no border; a float -> that
        stroke width.
    padding:
        Vertical gap in pixels between stacked blot strips (default ``0`` - the strips abut).
    **kwargs:
        Forwarded to :func:`dysonsphere.add_multilabel` (e.g. ``style``, ``categoryLabel``,
        ``showSampleSize`` with ``df``/``xCol``, ``span``, ``rowStyles``, and ``spacing`` - the
        gap between the blot stack and the table).

    Raises
    ------
    ValueError
        If ``images`` is empty.

    Examples
    --------
    ::

        fig = ds.biology.western_blot(
            ["pakt.png", "akt.png", "gapdh.png"],   # three antibody strips, stacked
            {"EGF": [False, True, True], "Inhibitor": [False, False, True]},
            categories=["Ctrl", "EGF", "EGF + Inh"],
            categoryLabel=True,
        )
        ds.save(fig, "blot")
    """
    image_list = [images] if isinstance(images, str) or hasattr(images, "save") else list(images)
    if not image_list:
        raise ValueError("western_blot() needs at least one image.")

    cw = ext.opt("chartWidth")
    if stroke is False:
        view: dict[str, Any] = {"fill": None, "stroke": None}
    else:
        width = ext.opt("markStrokeWidth") if stroke is True else float(stroke)
        view = {"fill": None, "stroke": "white" if ext.opt("darkmode") else "black", "strokeWidth": width}

    strips: list[Any] = []
    for image in image_list:
        uri, iw, ih = _load_image(image)
        h = cw * ih / iw  # preserve the blot's aspect at the shared chart width
        strips.append(
            alt.Chart(ext.internal_data([{"__blot": uri}]))
            .mark_image(aspect=False)
            .encode(url="__blot:N", x=alt.value(0), x2=alt.value(cw), y=alt.value(0), y2=alt.value(h))
            .properties(width=cw, height=h, view=view)
        )

    stack = strips[0] if len(strips) == 1 else alt.vconcat(*strips, spacing=padding)
    # add_multilabel's _strip_x_labels recurses into vconcat/hconcat children, so a multi-strip
    # stack is handled even though the parameter is typed Chart | LayerChart.
    result = ds.add_multilabel(stack, groups, categories, **kwargs)  # ty: ignore[invalid-argument-type]
    return ext.tag_extension(result, "biology")
