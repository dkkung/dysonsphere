"""Rendered regressions for the point-label layout model, independent of slot ordering."""

import json
import math
from pathlib import Path
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
                found[kind].extend(node.get("items", []))
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


def _point_distance(line: dict[str, Any], point: dict[str, Any]) -> float:
    dx, dy = line["x2"] - line["x"], line["y2"] - line["y"]
    length2 = dx * dx + dy * dy
    fraction = ((point["x"] - line["x"]) * dx + (point["y"] - line["y"]) * dy) / length2 if length2 else 0
    fraction = min(1, max(0, fraction))
    return math.hypot(point["x"] - line["x"] - fraction * dx, point["y"] - line["y"] - fraction * dy)


def _cars() -> pl.DataFrame:
    # Reuse only the full input table from the maintained offline example, never its saved label
    # positions as an oracle. This keeps the exact user-reported fixture without a network dependency.
    source = Path(__file__).parents[1] / "website/public/charts/labels-light.json"

    def table(node: Any) -> list[dict[str, Any]] | None:
        if isinstance(node, list):
            if node and isinstance(node[0], dict) and "Horsepower" in node[0] and "Name" in node[0]:
                return node
            children = node
        elif isinstance(node, dict):
            children = node.values()
        else:
            return None
        for child in children:
            result = table(child)
            if result is not None:
                return result
        return None

    rows = table(json.loads(source.read_text()))
    assert rows is not None
    return pl.DataFrame(rows).select("Horsepower", "Miles_per_Gallon", "Name")


def test_cars_use_local_clear_leaders():
    ds.theme(width=160, height=120)
    data = _cars()
    assert len(data) == 392
    base = alt.Chart(data).mark_circle().encode(x="Horsepower:Q", y="Miles_per_Gallon:Q")
    chart = base + ds.labels(data, "Horsepower", "Miles_per_Gallon", "Name", subset=8)
    rendered = _marks(chart)
    assert len(rendered["text"]) == 8
    assert {"toyota corona", "pontiac grand prix", "oldsmobile cutlass ciera (diesel)"} <= {
        text["text"] for text in rendered["text"]
    }
    lengths = [math.hypot(line["x2"] - line["x"], line["y2"] - line["y"]) for line in rendered["rule"]]
    # Readable edge-interior attachments can be longer than corner contacts, but each route must
    # stay local: less than a tenth of the unchanged 160 px panel (old maximum: 44.57 px).
    assert lengths and max(lengths) < 16.0
    assert sum(lengths) < 35.0  # Old total: 207.62 px.
    for line in rendered["rule"]:
        for point in rendered["symbol"]:
            # Vega circle paths have radius sqrt(size)/2. Include the painted line half-width.
            assert _point_distance(line, point) > math.sqrt(point["size"]) / 2 + 0.125
    boxes = []
    for text in rendered["text"]:
        # These bounds test correspondence to the portable model, not exact installed glyph ink.
        width, height = _placement._estimate_text_size(text["text"], 6)
        box = text["x"] - width / 2, text["y"] - height / 2, text["x"] + width / 2, text["y"] + height / 2
        assert box[0] >= -1e-8 and box[1] >= -1e-8 and box[2] <= 160 + 1e-8 and box[3] <= 120 + 1e-8
        attachment_width, attachment_height = _placement._estimate_attachment_size(text["text"], 6)
        attachment_box = (
            text["x"] - attachment_width / 2,
            text["y"] - attachment_height / 2,
            text["x"] + attachment_width / 2,
            text["y"] + attachment_height / 2,
        )
        for line in rendered["rule"]:
            assert not _segment_box(line, attachment_box)
        for other in boxes:
            assert box[0] >= other[2] or box[2] <= other[0] or box[1] >= other[3] or box[3] <= other[1]
        for point in rendered["symbol"]:
            assert not (box[0] < point["x"] < box[2] and box[1] < point["y"] < box[3])
        boxes.append(box)


@pytest.mark.parametrize("fill", [False, True])
@pytest.mark.parametrize("gap", [None, 0.0, 3.5])
def test_forced_cars_reserve_full_clearances(fill, gap):
    ds.theme(width=160, height=120)
    data = _cars()
    base = alt.Chart(data).mark_circle().encode(x="Horsepower:Q", y="Miles_per_Gallon:Q")
    rendered = _marks(
        base
        + ds.labels(
            data,
            "Horsepower",
            "Miles_per_Gallon",
            "Name",
            subset=8,
            alwaysShowConnectors=True,
            connectorGap=gap,
            fill=fill,
        )
    )
    assert len(rendered["rule"]) == len(rendered["text"]) == 8
    lengths = [math.hypot(line["x2"] - line["x"], line["y2"] - line["y"]) for line in rendered["rule"]]
    assert min(lengths) >= 1.0 - 1e-8
    assert max(lengths) < 16.0
    expected_gap = math.sqrt(12 / (2 * math.pi)) + 0.25 + 0.5 if gap is None else gap
    selected = _placement._sample_spread(data["Horsepower"].to_list(), data["Miles_per_Gallon"].to_list(), 8)
    for line, text, index in zip(rendered["rule"], rendered["text"], selected):
        point = rendered["symbol"][index]
        assert math.hypot(line["x"] - point["x"], line["y"] - point["y"]) == pytest.approx(expected_gap)
        width, height = _placement._estimate_attachment_size(text["text"], 6, chip=fill)
        box = text["x"] - width / 2, text["y"] - height / 2, text["x"] + width / 2, text["y"] + height / 2
        assert all(not _segment_box(other, box) for other in rendered["rule"])
        length = math.hypot(line["x2"] - line["x"], line["y2"] - line["y"])
        ux, uy = (line["x2"] - line["x"]) / length, (line["y2"] - line["y"]) / length
        # Extending the painted centerline by the promised text gap reaches the owner's boundary,
        # not its padded safety box. This check does not call the connector geometry helper.
        x, y = line["x2"] + 0.5 * ux, line["y2"] + 0.5 * uy
        assert box[0] - 1e-8 <= x <= box[2] + 1e-8 and box[1] - 1e-8 <= y <= box[3] + 1e-8
        assert min(abs(x - box[0]), abs(x - box[2]), abs(y - box[1]), abs(y - box[3])) < 1e-8
        if not fill and gap is None and text["text"] in ("mercury monarch", "mazda glc"):
            corner = min(abs(x - box[0]), abs(x - box[2])) < 1e-8 and min(abs(y - box[1]), abs(y - box[3])) < 1e-8
            if corner:
                assert min(abs(ux), abs(uy)) >= 0.1 * max(abs(ux), abs(uy)) - 1e-8
            elif min(abs(x - box[0]), abs(x - box[2])) < 1e-8:
                assert abs(y - text["y"]) <= height / 4 + 1e-8


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
        if reverse:
            x, y = 160 - x, 120 - y
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
