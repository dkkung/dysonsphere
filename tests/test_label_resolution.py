"""Regression tests for automatic point-label placement."""

import json
import math
import re
from copy import deepcopy

import altair as alt
import polars as pl
import pytest

import dysonsphere as ds
from dysonsphere.utils import _apply_spec_fixes


@pytest.fixture(autouse=True)
def _theme():
    ds.theme(width=100, height=100)


def _descriptions(node):
    if isinstance(node, dict):
        mark = node.get("mark")
        own = [mark.get("description", "")] if isinstance(mark, dict) else []
        return own + [description for value in node.values() for description in _descriptions(value)]
    if isinstance(node, list):
        return [description for value in node for description in _descriptions(value)]
    return []


def _generated(node):
    if isinstance(node, dict):
        mark = node.get("mark")
        own = (
            [(mark, node.get("encoding"))]
            if isinstance(mark, dict) and "__dslabelitem_" in mark.get("description", "")
            else []
        )
        return own + [item for value in node.values() for item in _generated(value)]
    if isinstance(node, list):
        return [item for value in node for item in _generated(value)]
    return []


def _scene_marks(spec, kind):
    import vl_convert as vlc

    found = []

    def visit(node):
        if isinstance(node, dict):
            if node.get("role") == "mark" and node.get("marktype") == kind:
                found.extend(node.get("items", []))
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)

    visit(vlc.vegalite_to_scenegraph(spec)["scenegraph"])
    return found


def _chart():
    data = pl.DataFrame({"x": [0.25, 0.75], "y": [0.48, 0.52], "name": ["left", "right"]})
    points = alt.Chart(data).mark_circle(size=36).encode(x=alt.X("x:Q", scale=alt.Scale(domain=[0, 1])), y="y:Q")
    labels = ds.labels(data, "x", "y", "name", xDomain=(0, 1), yDomain=(0, 1), alwaysShowConnectors=True)
    obstacle = ds.rule(x=0.5)
    return data, points, labels, obstacle


def test_no_label_fast_path_returns_same_spec():
    spec = alt.Chart(pl.DataFrame({"x": [1]})).mark_point().encode(x="x:Q").to_dict()
    assert _apply_spec_fixes(spec) is spec


def test_rule_layer_order_and_multiple_groups_resolve_together():
    _, points, labels, obstacle = _chart()
    first = _apply_spec_fixes((points + obstacle + labels + labels).to_dict())
    last = _apply_spec_fixes((points + labels + labels + obstacle).to_dict())
    assert _generated(first) == _generated(last)
    descriptions = _descriptions(first)
    assert sum(value.startswith("__dslabelintent_") for value in descriptions) == 4
    assert sum(value.startswith("__dslabelitem_") for value in descriptions) >= 4


def test_resolved_json_round_trip_is_idempotent(tmp_path):
    _, points, labels, obstacle = _chart()
    chart = points + obstacle + labels
    path = tmp_path / "labels"
    ds.save(chart, path, format="json", saveMetadata=False)
    first = json.loads(path.with_suffix(".json").read_text())
    loaded = ds.load(path.with_suffix(".json"))
    assert not isinstance(loaded, dict)
    second = _apply_spec_fixes(loaded.to_dict())
    assert _descriptions(first) == _descriptions(second)
    assert _apply_spec_fixes(second) == second


def test_nested_concat_with_identical_and_unlabelled_panels(tmp_path):
    data, points, labels, _ = _chart()
    labelled = points + labels
    unlabelled = alt.Chart(data).mark_square().encode(x="x:Q", y="y:Q")
    chart = (labelled | unlabelled | labelled) & (labelled | labelled | unlabelled)
    path = tmp_path / "nested"
    ds.save(chart, path, format="svg", background="light", saveMetadata=False)
    svg = path.with_suffix(".svg").read_text()
    assert len(re.findall(r">left</text>", svg)) == 4
    assert len(re.findall(r">right</text>", svg)) == 4


@pytest.mark.parametrize(
    ("shape", "radius"),
    [
        ("circle", 10.0),
        ("square", math.sqrt(200)),
        ("diamond", math.sqrt(200)),
        ("triangle", math.hypot(10, 20 / math.sqrt(3))),
    ],
)
def test_automatic_gap_uses_rendered_symbol_but_explicit_zero_is_exact(shape, radius):
    data = pl.DataFrame({"x": [0.5], "y": [0.5], "name": ["large"]})
    point = alt.Chart(data).mark_point(size=400, shape=shape).encode(x="x:Q", y="y:Q")

    def start_distance(gap):
        labels = ds.labels(
            data,
            "x",
            "y",
            "name",
            xDomain=(0, 1),
            yDomain=(0, 1),
            connectorGap=gap,
            alwaysShowConnectors=True,
        )
        spec = _apply_spec_fixes((point + labels).to_dict())
        symbol = next(item for item in _scene_marks(spec, "symbol") if float(item.get("opacity", 1)) > 0)
        rule = next(item for item in _scene_marks(spec, "rule") if "__dslabelitem_" in item.get("description", ""))
        return math.hypot(rule["x"] - symbol["x"], rule["y"] - symbol["y"])

    assert start_distance(None) >= radius + 0.5 - 1e-7
    assert start_distance(0) == pytest.approx(0)


@pytest.mark.parametrize("transparent", [False, True])
def test_render_background_preserves_custom_and_explicit_values(tmp_path, transparent):
    chart = alt.Chart(pl.DataFrame({"x": [1]})).mark_point().encode(x="x:Q")
    ds.theme(width=100, height=100, chartFill="#fce8d5", transparent=False)
    themed = tmp_path / f"themed-{transparent}"
    ds.save(chart, themed, format="svg", background="light", transparent=transparent, saveMetadata=False)
    themed_svg = themed.with_suffix(".svg").read_text()
    assert ('fill="#fce8d5"' in themed_svg) is (not transparent)

    explicit = tmp_path / f"explicit-{transparent}"
    ds.save(
        chart.properties(background="#123456"),
        explicit,
        format="svg",
        background="light",
        transparent=transparent,
        saveMetadata=False,
    )
    assert 'fill="#123456"' in explicit.with_suffix(".svg").read_text()


def test_save_formats_evaluate_label_scene_once_and_callable_once(tmp_path, monkeypatch):
    import vl_convert as vlc

    _, points, labels, _ = _chart()
    calls = {"chart": 0, "scene": 0}
    original = vlc.vegalite_to_scenegraph

    def build():
        calls["chart"] += 1
        return points + labels

    def evaluate(spec):
        calls["scene"] += 1
        return original(spec)

    monkeypatch.setattr(vlc, "vegalite_to_scenegraph", evaluate)
    ds.save(
        build,
        tmp_path / "once",
        format=["json", "html", "svg", "png"],
        background="light",
        saveMetadata=False,
        ppi=72,
    )
    assert calls == {"chart": 1, "scene": 1}


def test_save_without_labels_skips_scenegraph_evaluation(tmp_path, monkeypatch):
    import vl_convert as vlc

    def unexpected_scenegraph(_spec):
        raise AssertionError("charts without automatic-label intent must use the no-label fast path")

    monkeypatch.setattr(vlc, "vegalite_to_scenegraph", unexpected_scenegraph)
    data = pl.DataFrame({"x": [0.2, 0.8], "y": [0.7, 0.3]})
    chart = alt.Chart(data).mark_circle().encode(x="x:Q", y="y:Q")
    ds.save(chart, tmp_path / "no-labels", format=["json", "svg", "png"], background="light", ppi=72)


def test_mixed_group_connector_and_chip_styles_render_together(tmp_path):
    ds.theme(width=220, height=120)
    data = pl.DataFrame({"x": [0.25, 0.75], "y": [0.5, 0.5], "name": ["plain", "chip"]})
    points = alt.Chart(data).mark_circle(size=64).encode(x=alt.X("x:Q", scale=alt.Scale(domain=[0, 1])), y="y:Q")
    plain = ds.labels(data, "x", "y", "name", subset=[True, False], connector=False, color="#123456")
    chip = ds.labels(
        data,
        "x",
        "y",
        "name",
        subset=[False, True],
        alwaysShowConnectors=True,
        connectorGap=20,
        connectorCap="arrow",
        connectorColor="#654321",
        fill="#abcdef",
        stroke="#fedcba",
        fontSize=9,
        fontStyle="italic",
    )
    path = tmp_path / "mixed"
    ds.save(points + plain + chip, path, format=["json", "svg"], background="light", saveMetadata=False)
    spec = json.loads(path.with_suffix(".json").read_text())
    texts = {
        item["text"]: item for item in _scene_marks(spec, "text") if "__dslabelitem_" in item.get("description", "")
    }
    connectors = [item for item in _scene_marks(spec, "rule") if "__dslabelitem_" in item.get("description", "")]
    chips = [item for item in _scene_marks(spec, "rect") if "__dslabelitem_" in item.get("description", "")]
    assert set(texts) == {"plain", "chip"}
    assert texts["plain"]["fill"] == "#123456"
    assert texts["chip"]["fontSize"] == 9 and texts["chip"]["fontStyle"] == "italic"
    assert len(connectors) == len(chips) == 1
    assert connectors[0]["stroke"] == "#654321"
    assert chips[0]["fill"] == "#abcdef" and chips[0]["stroke"] == "#fedcba"
    assert 'class="ds-rule-cap"' in path.with_suffix(".svg").read_text()


def test_labels_preserve_statistics_provenance_and_reproducible_resized_exports(tmp_path, monkeypatch):
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")
    ds.stats.clear_stats()
    data = pl.DataFrame(
        {"x": [1.0, 2.0, 3.0, 4.0, 5.0], "y": [2.1, 3.8, 6.2, 7.9, 10.3], "name": ["A", "B", "C", "D", "E"]}
    )
    chart = (
        alt.Chart(data).mark_circle().encode(x="x:Q", y="y:Q")
        + ds.labels(data, "x", "y", "name", subset=["A", "D"])
        + ds.stats.correlation(data, "x", "y")
    )
    original = chart.to_dict()
    first, second, resized = (tmp_path / name for name in ("first", "second", "resized"))
    ds.save(chart, first, format="json", background="light")
    ds.save(chart, second, format="json", background="light")
    assert first.with_suffix(".json").read_bytes() == second.with_suffix(".json").read_bytes()
    assert chart.to_dict() == original
    assert ds.metadata.verify(first.with_suffix(".json"), data=data).ok
    assert ds.metadata.verify([chart, first.with_suffix(".json")], what="spec").ok
    assert ds.metadata.read(first.with_suffix(".json"), what="data").equals(data)

    loaded = ds.load(first.with_suffix(".json"))
    assert not isinstance(loaded, dict)
    ds.save(loaded.properties(width=180, height=140), resized, format=["json", "svg"], background="light")
    assert ds.metadata.verify(resized.with_suffix(".json"), data=data).ok
    before = json.loads(first.with_suffix(".json").read_text())
    after = json.loads(resized.with_suffix(".json").read_text())
    assert before["usermeta"]["dysonsphere"]["statistics"] == after["usermeta"]["dysonsphere"]["statistics"]
    texts = [item for mark, item in _generated(after) if mark["type"] == "text"]
    assert [item["text"]["value"] for item in texts] == ["A", "D"]

    changed_chart = deepcopy(loaded)
    source = next(
        layer.data
        for layer in changed_chart.layer
        if hasattr(layer.data, "values")
        and (rows := layer.data.values.to_dict())
        and {"x", "y", "name"} <= set(rows[0])
        and "__dysonsphere__" not in rows[0]
    )
    changed_rows = source.values.to_dict()
    changed_rows[0]["y"] = 99.0
    source.values = changed_rows
    with pytest.raises(ValueError, match="preserved statistical context changed"):
        ds.save(changed_chart, tmp_path / "changed", format="json", background="light")
    with pytest.raises(ValueError, match="preserved statistical context changed"):
        ds.save(
            changed_chart,
            tmp_path / "changed-no-metadata",
            format="json",
            background="light",
            saveMetadata=False,
        )
