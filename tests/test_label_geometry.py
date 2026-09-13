"""Rendered regressions for the point-label layout model, independent of slot ordering."""

from typing import Any

import altair as alt
import polars as pl
import pytest
import vl_convert as vlc

import dysonsphere as ds
from dysonsphere import _placement
from dysonsphere.utils import _apply_spec_fixes


def _marks(chart: Any) -> dict[str, list[dict[str, Any]]]:
    found: dict[str, list[dict[str, Any]]] = {"symbol": [], "text": [], "rule": []}

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            kind = node.get("marktype")
            if kind in found and node.get("role") == "mark":
                # Labels keep zero-size, zero-opacity anchors for export-time mapping; they are not
                # painted point marks.
                found[kind].extend(item for item in node.get("items", []) if float(item.get("opacity", 1)) > 0)
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)

    visit(vlc.vegalite_to_scenegraph(_apply_spec_fixes(chart.to_dict())))
    return found


def _segment_box(line: dict[str, Any], box: tuple[float, float, float, float]) -> bool:
    """Independent closed-segment/slab check in rendered pixels."""
    enter, leave = 0.0, 1.0
    for start, delta, low, high in (
        (line["x"], line["x2"] - line["x"], box[0], box[2]),
        (line["y"], line["y2"] - line["y"], box[1], box[3]),
    ):
        if abs(delta) < 1e-10:
            if not low <= start <= high:
                return False
        else:
            t0, t1 = sorted(((low - start) / delta, (high - start) / delta))
            enter, leave = max(enter, t0), min(leave, t1)
    return enter <= leave


@pytest.mark.parametrize(
    ("text", "width"), [("W", 5.556), ("iiii", 5.328), ("111", 10.008), ("oldsmobile cutlass ciera (diesel)", 85.116)]
)
def test_default_attachment_uses_reference_font_advances(text, width):
    attachment = _placement._estimate_attachment_size(text, 6)
    collision = _placement._estimate_text_size(text, 6)
    assert attachment[0] == pytest.approx(width)
    assert collision[0] == pytest.approx(width + 2.1)
    assert collision[1] > attachment[1]


def test_short_segment_is_omitted_instead_of_compressing_gaps():
    assert _placement._shortened_segment((0, 0), (5, 0), (4, 4), 2, 0.5) is None


def test_disabled_connectors_do_not_reserve_extra_room():
    ds.theme()
    data = pl.DataFrame({"x": [10.0, 30.0, 50.0], "y": [15.0, 35.0, 55.0], "label": ["a", "b", "c"]})
    ordinary = ds.labels(data, "x", "y", "label", connector=False)
    forced = ds.labels(data, "x", "y", "label", connector=False, alwaysShowConnectors=True)
    assert ordinary.to_dict() == forced.to_dict()


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("explicit", [False, True])
@pytest.mark.parametrize("padding", [0.0, 5.0])
def test_pixel_model_matches_native_linear_scales(monkeypatch, reverse, explicit, padding):
    ds.theme(width=160, height=120, viewPadding=padding)
    data = pl.DataFrame({"x": [20.0, 50.0, 100.0], "y": [10.0, 25.0, 40.0], "label": ["one", "two", "three"]})
    kwargs: dict[str, Any] = {}
    xscale: dict[str, Any] = {"reverse": reverse}
    yscale: dict[str, Any] = {"reverse": reverse}
    if explicit:
        kwargs.update(xDomain=(20.0, 100.0), yDomain=(10.0, 40.0))
        xscale.update(domain=[20, 100], zero=False, nice=False)
        yscale.update(domain=[10, 40], zero=False, nice=False)
    base = (
        alt.Chart(data)
        .mark_circle()
        .encode(
            x=alt.X("x:Q", title="X title", scale=alt.Scale(**xscale)),
            y=alt.Y("y:Q", title="Y title", scale=alt.Scale(**yscale)),
        )
    )
    captured = {}
    original = _placement._repel_labels

    def capture(anchors, sizes, **options):
        positions = original(anchors, sizes, **options)
        captured.update(anchors=anchors, positions=positions)
        return positions

    monkeypatch.setattr(_placement, "_repel_labels", capture)
    chart = base + ds.labels(data, "x", "y", "label", **kwargs)
    before, after = _marks(base), _marks(chart)
    assert [(p["x"], p["y"]) for p in before["symbol"]] == [(p["x"], p["y"]) for p in after["symbol"]]
    for expected, actual in zip(captured["positions"], after["text"]):
        x, y = expected
        assert (actual["x"], actual["y"]) == pytest.approx((x, y), abs=1e-8)


def test_route_never_enters_its_own_label():
    # A point blocking the nearest endpoint must not send the line to the hidden far side.
    line = _placement._shortened_segment(
        (0.0, 0.0),
        (10.0, 0.0),
        (8.0, 8.0),
        1.0,
        0.5,
        obstacles=[(3.0, 0.0)],
        point_radius=1.0,
    )
    assert line is not None
    start, end = line
    assert not _segment_box(dict(x=start[0], y=start[1], x2=end[0], y2=end[1]), (6.0, -4.0, 14.0, 4.0))
