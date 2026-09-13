"""Private deferred point-label resolution for the shared save/show spec pipeline."""

from __future__ import annotations

import json
import math
import re
from copy import deepcopy
from typing import Any

from . import _placement

_LABEL_GROUP_COL = "__dysonsphere_label_group"
_LABEL_INTENT_PREFIX = "__dslabelintent_"
_LABEL_ITEM_PREFIX = "__dslabelitem_"
_PANEL_PROBE_PREFIX = "__dslabelpanel_"


def _data_values(spec: dict[str, Any], root: dict[str, Any]) -> list[dict[str, Any]]:
    data = spec.get("data", {})
    if "values" in data:
        return data["values"]
    return root.get("datasets", {}).get(data.get("name"), [])


def _intent_registry(spec: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    found: dict[str, list[dict[str, Any]]] = {}

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            mark = node.get("mark")
            description = mark.get("description", "") if isinstance(mark, dict) else ""
            if isinstance(description, str) and description.startswith(_LABEL_INTENT_PREFIX):
                token = description.removeprefix(_LABEL_INTENT_PREFIX)
                found[token] = _data_values(node, spec)
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)

    visit(spec)
    return found


def _marks(node: Any) -> list[dict[str, Any]]:
    result = []
    if isinstance(node, dict):
        if node.get("role") == "mark":
            result.append(node)
        for value in node.values():
            result.extend(_marks(value))
    elif isinstance(node, list):
        for value in node:
            result.extend(_marks(value))
    return result


def _paint_visible(value: Any) -> bool:
    if value is None:
        return False
    if not isinstance(value, str):
        return True
    paint = value.strip().lower()
    if paint in {"none", "transparent"}:
        return False
    if paint.startswith("#") and len(paint) in {5, 9}:
        return int(paint[-1] * 2 if len(paint) == 5 else paint[-2:], 16) > 0
    match = re.match(r"^(?:rgba|hsla)\([^,]+,[^,]+,[^,]+,\s*([\d.]+%?)\s*\)$", paint)
    if match is None:
        match = re.match(r"^(?:rgb|hsl)a?\(.+?/\s*([\d.]+%?)\s*\)$", paint)
    if match is None:
        return True
    alpha = match.group(1)
    return float(alpha[:-1] if alpha.endswith("%") else alpha) > 0


def _visible(item: dict[str, Any], paint: str) -> bool:
    if float(item.get("opacity", 1)) <= 0:
        return False
    opacity = float(item.get(f"{paint}Opacity", 1))
    return opacity > 0 and _paint_visible(item.get(paint))


def _segment(item: dict[str, Any]) -> tuple[tuple[float, float], tuple[float, float]]:
    x, y = float(item["x"]), float(item["y"])
    return (x, y), (
        float(item.get("x2", x + float(item.get("width", 0)))),
        float(item.get("y2", y + float(item.get("height", 0)))),
    )


def _clip_segment(start, end, width: float, height: float):
    x, y = start
    dx, dy = end[0] - x, end[1] - y
    low, high = 0.0, 1.0
    for p, q in ((-dx, x), (dx, width - x), (-dy, y), (dy, height - y)):
        if abs(p) < 1e-12:
            if q < 0:
                return None
        else:
            value = q / p
            low, high = (max(low, value), high) if p < 0 else (low, min(high, value))
    if low > high:
        return None
    return (x + low * dx, y + low * dy), (x + high * dx, y + high * dy)


def _clip_stroked_segment(start, end, width: float, height: float, radius: float):
    shifted = (start[0] + radius, start[1] + radius), (end[0] + radius, end[1] + radius)
    clipped = _clip_segment(shifted[0], shifted[1], width + 2 * radius, height + 2 * radius)
    if clipped is None:
        return None
    return (
        (clipped[0][0] - radius, clipped[0][1] - radius),
        (clipped[1][0] - radius, clipped[1][1] - radius),
    )


def _symbol_obstacle(item: dict[str, Any]):
    center = float(item["x"]), float(item["y"])
    size = max(float(item.get("size", 0)), 0)
    stroke = float(item.get("strokeWidth", 0)) / 2 if _visible(item, "stroke") else 0.0
    root = math.sqrt(size)
    shape = item.get("shape", "circle")
    if shape == "circle":
        circle = _placement._CircleObstacle(center, root / 2 + stroke)
        return circle, circle
    if shape == "square":
        half = (root / 2 + stroke, root / 2 + stroke)
    elif shape == "diamond":
        extent = root / 2 + math.sqrt(2) * stroke
        half = (extent, extent)
    elif shape == "triangle":
        half = (root / 2 + 2 * stroke, root / math.sqrt(3) + 2 * stroke)
    elif shape in {"triangle-up", "triangle-down"}:
        half = (root / 2 + 2 * stroke, root * math.sqrt(3) / 4 + 2 * stroke)
    else:
        return None
    return _placement._BoxObstacle(center, half), _placement._CircleObstacle(center, math.hypot(*half))


def _panel_obstacles(marks: list[dict[str, Any]], width: float, height: float):
    obstacles: list[_placement._GeometryObstacle] = []
    circles: list[_placement._CircleObstacle] = []
    for mark in marks:
        name = str(mark.get("name", ""))
        if "__dsshade_" in name:
            continue
        items = mark.get("items", [])
        if any(_LABEL_INTENT_PREFIX in str(item.get("description", "")) for item in items):
            continue
        items = [item for item in items if _LABEL_ITEM_PREFIX not in str(item.get("description", ""))]
        kind = mark.get("marktype")
        if kind == "symbol":
            for item in items:
                if not (_visible(item, "fill") or _visible(item, "stroke")):
                    continue
                resolved = _symbol_obstacle(item)
                if resolved is not None:
                    obstacle, circle = resolved
                    obstacles.append(obstacle)
                    circles.append(circle)
        elif kind == "rule":
            for item in items:
                if _visible(item, "stroke"):
                    start, end = _segment(item)
                    radius = float(item.get("strokeWidth", 1)) / 2
                    clipped = (
                        _clip_stroked_segment(start, end, width, height, radius) if mark.get("clip") else (start, end)
                    )
                    if clipped is not None:
                        obstacles.append(_placement._SegmentObstacle(clipped[0], clipped[1], radius))
        elif kind == "line":
            if {str(item.get("interpolate", "linear")) for item in items} != {"linear"}:
                continue
            for first, second in zip(items, items[1:]):
                if _visible(first, "stroke") and first.get("defined", True) and second.get("defined", True):
                    start = (float(first["x"]), float(first["y"]))
                    end = (float(second["x"]), float(second["y"]))
                    radius = float(first.get("strokeWidth", 1)) / 2
                    clipped = (
                        _clip_stroked_segment(start, end, width, height, radius) if mark.get("clip") else (start, end)
                    )
                    if clipped is not None:
                        obstacles.append(_placement._SegmentObstacle(clipped[0], clipped[1], radius))
        elif kind == "rect":
            for item in items:
                fill_visible, stroke_visible = _visible(item, "fill"), _visible(item, "stroke")
                if not (fill_visible or stroke_visible):
                    continue
                (x0, y0), (x1, y1) = _segment(item)
                stroke = float(item.get("strokeWidth", 0)) / 2 if stroke_visible else 0
                if fill_visible:
                    fx0, fx1, fy0, fy1 = x0 - stroke, x1 + stroke, y0 - stroke, y1 + stroke
                    if mark.get("clip"):
                        fx0, fx1, fy0, fy1 = max(0, fx0), min(width, fx1), max(0, fy0), min(height, fy1)
                    if fx1 >= fx0 and fy1 >= fy0:
                        obstacles.append(
                            _placement._BoxObstacle(
                                ((fx0 + fx1) / 2, (fy0 + fy1) / 2), ((fx1 - fx0) / 2, (fy1 - fy0) / 2)
                            )
                        )
                else:
                    edges = (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0)))
                    for start, end in dict.fromkeys(edges):
                        clipped = (
                            _clip_stroked_segment(start, end, width, height, stroke)
                            if mark.get("clip")
                            else (start, end)
                        )
                        if clipped is not None:
                            obstacles.append(_placement._SegmentObstacle(clipped[0], clipped[1], stroke))
        elif kind == "text":
            for item in items:
                text = str(item.get("text", ""))
                if not text or not _visible(item, "fill"):
                    continue
                size = _placement._estimate_text_size(
                    text,
                    float(item.get("fontSize", 11)),
                    font_family=item.get("font"),
                    font_weight=item.get("fontWeight"),
                    font_style=item.get("fontStyle"),
                )
                align, baseline = item.get("align", "left"), item.get("baseline", "alphabetic")
                local_x = float(item.get("dx", 0)) + (
                    size[0] / 2 if align == "left" else -size[0] / 2 if align == "right" else 0
                )
                local_y = float(item.get("dy", 0)) + (
                    size[1] / 2
                    if baseline in {"top", "line-top"}
                    else -size[1] / 2
                    if baseline in {"bottom", "line-bottom"}
                    else -0.3 * size[1]
                    if baseline == "alphabetic"
                    else 0
                )
                angle = float(item.get("angle", 0))
                radians = math.radians(angle)
                center = (
                    float(item["x"]) + math.cos(radians) * local_x - math.sin(radians) * local_y,
                    float(item["y"]) + math.sin(radians) * local_x + math.cos(radians) * local_y,
                )
                extent = (
                    abs(math.cos(radians)) * size[0] / 2 + abs(math.sin(radians)) * size[1] / 2,
                    abs(math.sin(radians)) * size[0] / 2 + abs(math.cos(radians)) * size[1] / 2,
                )
                if not mark.get("clip") or not (
                    center[0] + extent[0] < 0
                    or center[0] - extent[0] > width
                    or center[1] + extent[1] < 0
                    or center[1] - extent[1] > height
                ):
                    obstacles.append(_placement._BoxObstacle(center, (size[0] / 2, size[1] / 2), angle))
    return obstacles, circles


def _tag_panel_probes(spec: dict[str, Any]) -> list[dict[str, Any]]:
    """Give evaluation-only intent marks a source-panel identity."""
    targets = _target_specs(spec)
    for index, target in enumerate(targets):

        def visit(node: Any) -> None:
            if isinstance(node, dict):
                mark = node.get("mark")
                if isinstance(mark, dict) and str(mark.get("description", "")).startswith(_LABEL_INTENT_PREFIX):
                    original = str(mark["description"]).removeprefix(_LABEL_INTENT_PREFIX)
                    mark["description"] = f"{_PANEL_PROBE_PREFIX}{index}_{original}"
                for value in node.values():
                    visit(value)
            elif isinstance(node, list):
                for value in node:
                    visit(value)

        visit(target)
    return targets


def _scene_frames(scene: dict[str, Any], count: int) -> list[dict[str, Any]]:
    """Map each source leaf to the nearest rendered frame containing its private probe."""
    frames: dict[int, dict[str, Any]] = {}

    def visit(node: Any, ancestors: list[dict[str, Any]]) -> None:
        if isinstance(node, dict):
            description = str(node.get("description", ""))
            if description.startswith(_PANEL_PROBE_PREFIX):
                match = re.match(rf"{re.escape(_PANEL_PROBE_PREFIX)}(\d+)_", description)
                frame = next(
                    (
                        ancestor
                        for ancestor in reversed(ancestors)
                        if isinstance(ancestor.get("width"), (int, float))
                        and isinstance(ancestor.get("height"), (int, float))
                    ),
                    None,
                )
                if match is not None and frame is not None:
                    index = int(match.group(1))
                    if index in frames and frames[index] is not frame:
                        raise ValueError(
                            "automatic label placement does not support one label specification "
                            "repeated by a facet transform; compose explicit labelled panels instead"
                        )
                    frames[index] = frame
            for value in node.values():
                visit(value, [*ancestors, node])
        elif isinstance(node, list):
            for value in node:
                visit(value, ancestors)

    visit(scene, [])
    if set(frames) != set(range(count)):
        raise ValueError(
            "automatic label placement could not map every source view to its rendered panel "
            f"(mapped {sorted(frames)}, expected {list(range(count))})"
        )
    return [frames[index] for index in range(count)]


def _strip_label_items(node: Any, root: dict[str, Any]) -> None:
    if not isinstance(node, dict):
        return
    layers = node.get("layer")
    if isinstance(layers, list):
        kept = []
        for layer in layers:
            mark = layer.get("mark", {}) if isinstance(layer, dict) else {}
            description = mark.get("description", "") if isinstance(mark, dict) else ""
            values = _data_values(layer, root) if isinstance(layer, dict) else []
            generated = bool(values and _LABEL_GROUP_COL in values[0])
            intent = isinstance(description, str) and description.startswith(_LABEL_INTENT_PREFIX)
            if not generated or intent:
                _strip_label_items(layer, root)
                kept.append(layer)
        node["layer"] = kept
    for key in ("hconcat", "vconcat", "concat"):
        for child in node.get(key, []):
            _strip_label_items(child, root)


def _target_specs(spec: dict[str, Any]) -> list[dict[str, Any]]:
    targets: list[dict[str, Any]] = []

    def contains_intent(node: Any) -> bool:
        if isinstance(node, dict):
            mark = node.get("mark")
            description = mark.get("description", "") if isinstance(mark, dict) else ""
            return str(description).startswith(_LABEL_INTENT_PREFIX) or any(
                contains_intent(value) for value in node.values()
            )
        return isinstance(node, list) and any(contains_intent(value) for value in node)

    def visit(node: dict[str, Any]) -> None:
        children = next(
            (node[key] for key in ("hconcat", "vconcat", "concat") if isinstance(node.get(key), list)), None
        )
        if children is not None:
            for child in children:
                if isinstance(child, dict):
                    visit(child)
        elif contains_intent(node):
            targets.append(node)

    visit(spec)
    return targets


def _generated_layers(entries: list[dict[str, Any]], positions, circles, marker_gaps):
    from .annotations import _rule_cap_marker, _text_bg_props
    from .utils import _internal_data

    layers = []
    for entry, center, marker_gap in zip(entries, positions, marker_gaps, strict=True):
        config = entry["config"]
        token, row = entry["token"], entry["row"]
        marker = f"{_LABEL_ITEM_PREFIX}{token}"
        data = _internal_data([{_LABEL_GROUP_COL: token, "__dslabel_row": row}]).to_dict()
        attachment = entry["attachment"]
        if config["connector"]:
            segment = _placement._shortened_segment(
                entry["anchor"],
                center,
                attachment,
                marker_gap,
                config["textGap"],
                stroke_width=config["strokeWidth"],
                obstacles=[],
                point_radius=entry["pointRadius"],
                circle_obstacles=circles,
            )
            if segment is not None:
                description = marker
                if config["connectorCap"] == "arrow":
                    description = f"{_rule_cap_marker('arrow', None, 0, 0)} {marker}"
                mark = {
                    "type": "rule",
                    "strokeWidth": config["strokeWidth"],
                    "strokeDash": config["connectorStrokeDash"],
                    "description": description,
                }
                for source, target in (("color", "connectorColor"), ("opacity", "connectorOpacity")):
                    if config[target] is not None:
                        mark[source] = config[target]
                layers.append(
                    {
                        "data": data,
                        "mark": mark,
                        "encoding": {
                            "x": {"value": segment[0][0]},
                            "y": {"value": segment[0][1]},
                            "x2": {"value": segment[1][0]},
                            "y2": {"value": segment[1][1]},
                        },
                    }
                )
        if config["fill"] is not None:
            props, xshift, yshift = _text_bg_props(
                entry["text"],
                config["fontSize"],
                "center",
                "middle",
                0,
                0,
                config["fill"],
                config["stroke"],
                config["fillOpacity"],
                config["cornerRadius"],
            )
            props.update(width=entry["size"][0], height=entry["size"][1], description=marker)
            layers.append(
                {
                    "data": data,
                    "mark": {"type": "rect", **props},
                    "encoding": {
                        "x": {"value": center[0]},
                        "y": {"value": center[1]},
                        "xOffset": {"value": xshift},
                        "yOffset": {"value": yshift},
                    },
                }
            )
        text_mark = {
            "type": "text",
            "align": "center",
            "baseline": "middle",
            "fontSize": config["fontSize"],
            "font": config["fontFamily"],
            "fontWeight": config["fontWeight"],
            "fontStyle": config["fontStyle"],
            "description": marker,
        }
        if config["color"] is not None:
            text_mark["color"] = config["color"]
        layers.append(
            {
                "data": data,
                "mark": text_mark,
                "encoding": {"x": {"value": center[0]}, "y": {"value": center[1]}, "text": {"value": entry["text"]}},
            }
        )
    return layers


def _resolve_labels(spec: dict[str, Any]) -> dict[str, Any]:
    registry = _intent_registry(spec)
    if not registry:
        return spec
    import vl_convert as vlc

    prepared = deepcopy(spec)
    evaluation_spec = deepcopy(prepared)
    evaluation_targets = _tag_panel_probes(evaluation_spec)
    scene = vlc.vegalite_to_scenegraph(evaluation_spec)["scenegraph"]
    frames = _scene_frames(scene, len(evaluation_targets))
    targets = _target_specs(prepared)
    panel_results = []
    for panel_index, frame in enumerate(frames):
        marks = _marks(frame)
        entries: list[dict[str, Any]] = []
        for mark in marks:
            descriptions = [str(item.get("description", "")) for item in mark.get("items", [])]
            token = next(
                (
                    value.removeprefix(f"{_PANEL_PROBE_PREFIX}{panel_index}_")
                    for value in descriptions
                    if value.startswith(f"{_PANEL_PROBE_PREFIX}{panel_index}_")
                ),
                None,
            )
            if token is None or token not in registry:
                continue
            rows = sorted(registry[token], key=lambda row: row["__dslabel_row"])
            for item, row in zip(mark.get("items", []), rows, strict=True):
                config = json.loads(row["__dslabel_config"])
                text = str(row["__dslabel_text"])
                size = _placement._estimate_text_size(
                    text,
                    config["fontSize"],
                    chip=config["fill"] is not None,
                    font_family=config["fontFamily"],
                    font_weight=config["fontWeight"],
                    font_style=config["fontStyle"],
                )
                attachment = _placement._estimate_attachment_size(
                    text,
                    config["fontSize"],
                    chip=config["fill"] is not None,
                    font_family=config["fontFamily"],
                    font_weight=config["fontWeight"],
                    font_style=config["fontStyle"],
                )
                entries.append(
                    {
                        "token": row[_LABEL_GROUP_COL],
                        "row": row["__dslabel_row"],
                        "anchor": (float(item["x"]), float(item["y"])),
                        "text": text,
                        "config": config,
                        "size": size,
                        "attachment": attachment,
                        "pointRadius": config["pointRadius"],
                    }
                )
        obstacles, circles = _panel_obstacles(marks, float(frame["width"]), float(frame["height"]))
        marker_gaps = []
        for entry in entries:
            configured = entry["config"]["connectorGap"]
            if entry["config"].get("connectorGapAutomatic", False):
                own = [circle.radius for circle in circles if math.dist(circle.center, entry["anchor"]) < 1e-7]
                configured = max(configured, max(own, default=0) + entry["config"]["textGap"])
            marker_gaps.append(configured)
        positions = _placement._repel_labels(
            [entry["anchor"] for entry in entries],
            [entry["size"] for entry in entries],
            width=float(frame["width"]),
            height=float(frame["height"]),
            obstacles=[],
            geometry_obstacles=obstacles,
            point_radius=max((entry["config"]["pointRadius"] for entry in entries), default=0),
            marker_gap=0,
            marker_gaps=marker_gaps,
            text_gap=max((entry["config"]["textGap"] for entry in entries), default=0),
            connector=any(entry["config"]["connector"] for entry in entries),
            always_show=any(entry["config"]["alwaysShowConnectors"] for entry in entries),
            stroke_width=max((entry["config"]["strokeWidth"] for entry in entries), default=0.25),
            attachment_sizes=[entry["attachment"] for entry in entries],
            connector_circle_obstacles=circles,
            connectors=[entry["config"]["connector"] for entry in entries],
            always_shows=[entry["config"]["alwaysShowConnectors"] for entry in entries],
            text_gaps=[entry["config"]["textGap"] for entry in entries],
            stroke_widths=[entry["config"]["strokeWidth"] for entry in entries],
            point_radii=[entry["config"]["pointRadius"] for entry in entries],
        )
        panel_results.append((entries, positions, circles, marker_gaps))
    _strip_label_items(prepared, prepared)
    targets = _target_specs(prepared)
    for target, (entries, positions, circles, marker_gaps) in zip(targets, panel_results, strict=True):
        target.setdefault("layer", []).extend(_generated_layers(entries, positions, circles, marker_gaps))
    return prepared
