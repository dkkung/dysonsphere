"""Regression tests for label obstacle extraction."""

import math
import re
from typing import Any

import altair as alt
import pytest
import vl_convert as vlc

import dysonsphere as ds
from dysonsphere import _label_placement
from dysonsphere._label_resolution import _panel_obstacles


def _marks(node: Any) -> list[dict[str, Any]]:
    if isinstance(node, dict):
        own = [node] if node.get("role") == "mark" else []
        return own + [mark for value in node.values() for mark in _marks(value)]
    if isinstance(node, list):
        return [mark for value in node for mark in _marks(value)]
    return []


def _hits(center, half, obstacle):
    if isinstance(obstacle, _label_placement._CircleObstacle):
        dx = max(abs(center[0] - obstacle.center[0]) - half[0], 0)
        dy = max(abs(center[1] - obstacle.center[1]) - half[1], 0)
        return math.hypot(dx, dy) < obstacle.radius
    if isinstance(obstacle, _label_placement._SegmentObstacle):
        enter, leave = 0.0, 1.0
        for start, end, coordinate, radius in (
            (obstacle.start[0], obstacle.end[0], center[0], half[0] + obstacle.radius),
            (obstacle.start[1], obstacle.end[1], center[1], half[1] + obstacle.radius),
        ):
            delta = end - start
            if abs(delta) < 1e-12:
                if not coordinate - radius <= start <= coordinate + radius:
                    return False
            else:
                low, high = sorted(((coordinate - radius - start) / delta, (coordinate + radius - start) / delta))
                enter, leave = max(enter, low), min(leave, high)
        return enter <= leave
    angle = math.radians(obstacle.angle)
    u, v = (math.cos(angle), math.sin(angle)), (-math.sin(angle), math.cos(angle))
    relative = center[0] - obstacle.center[0], center[1] - obstacle.center[1]
    return all(
        (
            abs(relative[0]) <= half[0] + abs(u[0]) * obstacle.half_size[0] + abs(v[0]) * obstacle.half_size[1],
            abs(relative[1]) <= half[1] + abs(u[1]) * obstacle.half_size[0] + abs(v[1]) * obstacle.half_size[1],
            abs(relative[0] * u[0] + relative[1] * u[1])
            <= obstacle.half_size[0] + half[0] * abs(u[0]) + half[1] * abs(u[1]),
            abs(relative[0] * v[0] + relative[1] * v[1])
            <= obstacle.half_size[1] + half[0] * abs(v[0]) + half[1] * abs(v[1]),
        )
    )


@pytest.mark.parametrize(
    "obstacle",
    [
        _label_placement._CircleObstacle((50, 50), 9),
        _label_placement._SegmentObstacle((20, 50), (80, 50), 4),
        _label_placement._SegmentObstacle((30, 30), (70, 70), 3),
        _label_placement._BoxObstacle((50, 50), (14, 8)),
        _label_placement._BoxObstacle((50, 50), (14, 8), 32),
        _label_placement._SegmentObstacle((50, 50), (50, 50), 3),
        _label_placement._BoxObstacle((50, 50), (0, 0)),
    ],
)
def test_typed_geometry_and_degenerates_move_to_a_deterministic_clear_seat(obstacle):
    def place():
        return _label_placement._repel_labels(
            [(50, 50)],
            [(24, 10)],
            width=100,
            height=100,
            obstacles=[],
            geometry_obstacles=[obstacle],
            connector=False,
        )[0]

    first = place()
    second = place()
    assert first == second
    assert not _hits(first, (12, 5), obstacle)


def test_plain_solver_approved_checkpoint_centers():
    assert _label_placement._repel_labels(
        [(20.0, 30.0), (55.0, 45.0), (80.0, 75.0)],
        [(18.0, 8.0), (22.0, 9.0), (16.0, 7.0)],
        width=100,
        height=90,
        obstacles=[(20.0, 30.0), (55.0, 45.0), (80.0, 75.0), (45.0, 35.0)],
        point_radius=3,
    ) == [(20.0, 22.75), (40.75, 45.0), (68.75, 75.0)]


@pytest.mark.parametrize(("shape", "half"), [("diamond", (5, 5)), ("triangle", (5, 10 / math.sqrt(3)))])
def test_symbol_footprint_contains_renderer_path(shape, half):
    ds.theme(width=100, height=100)
    chart = (
        alt.Chart(alt.Data(values=[{}]))
        .mark_point(shape=shape, filled=True, size=100, stroke=None)
        .encode(x=alt.value(50), y=alt.value(50))
    )
    scene = vlc.vegalite_to_scenegraph(chart.to_dict())["scenegraph"]
    obstacle = _panel_obstacles(_marks(scene), 100, 100)[0][0]
    assert isinstance(obstacle, _label_placement._BoxObstacle)
    assert obstacle.half_size == pytest.approx(half)
    svg = vlc.vegalite_to_svg(chart.to_dict())
    path = re.search(r'transform="translate\(50,50\)" d="([^"]+)"', svg)
    assert path is not None
    coordinates = [float(value) for value in re.findall(r"-?\d+(?:\.\d+)?", path.group(1))]
    assert max(abs(value) for value in coordinates[0::2]) <= obstacle.half_size[0] + 1e-3
    assert max(abs(value) for value in coordinates[1::2]) <= obstacle.half_size[1] + 1e-3


def test_fixed_text_alignment_baseline_offsets_and_rotation():
    marks = [
        {
            "role": "mark",
            "marktype": "text",
            "items": [
                {
                    "x": 50,
                    "y": 40,
                    "text": "Hello",
                    "fill": "black",
                    "font": "Helvetica Neue",
                    "fontSize": 12,
                    "align": "left",
                    "baseline": "alphabetic",
                    "angle": 90,
                    "dx": 7,
                    "dy": -3,
                }
            ],
        }
    ]
    obstacle = _panel_obstacles(marks, 100, 80)[0][0]
    assert isinstance(obstacle, _label_placement._BoxObstacle)
    size = _label_placement._estimate_text_size("Hello", 12, font_family="Helvetica Neue")
    local_x, local_y = 7 + size[0] / 2, -3 - 0.3 * size[1]
    assert obstacle.center == pytest.approx((50 - local_y, 40 + local_x))
    assert obstacle.half_size == pytest.approx((size[0] / 2, size[1] / 2))
    assert obstacle.angle == 90


def test_curves_visibility_clipping_outlines_and_shade_policy():
    marks = [
        {
            "role": "mark",
            "marktype": "line",
            "items": [
                {"x": 0, "y": 0, "stroke": "black", "interpolate": "basis"},
                {"x": 20, "y": 20, "stroke": "black", "interpolate": "basis"},
            ],
        },
        {
            "role": "mark",
            "marktype": "rule",
            "clip": True,
            "items": [{"x": -10, "x2": 110, "y": -0.4, "stroke": "black", "strokeWidth": 2}],
        },
        {
            "role": "mark",
            "marktype": "rect",
            "items": [{"x": 20, "y": 20, "width": 60, "height": 40, "fill": None, "stroke": "black", "strokeWidth": 2}],
        },
        {
            "role": "mark",
            "marktype": "rect",
            "items": [{"x": 1, "y": 1, "width": 8, "height": 8, "fill": "rgba(10,20,30,0)", "stroke": "#11223300"}],
        },
        {
            "role": "mark",
            "name": "__dsshade_background",
            "marktype": "rect",
            "items": [{"x": 0, "y": 0, "width": 100, "height": 80, "fill": "black"}],
        },
        {
            "role": "mark",
            "name": "foreground_bar",
            "marktype": "rect",
            "items": [{"x": 5, "y": 5, "width": 5, "height": 10, "fill": "rgba(1,2,3,0.3)"}],
        },
    ]
    obstacles, _ = _panel_obstacles(marks, 100, 80)
    segments = [item for item in obstacles if isinstance(item, _label_placement._SegmentObstacle)]
    boxes = [item for item in obstacles if isinstance(item, _label_placement._BoxObstacle)]
    assert len(segments) == 5  # clipped rule plus four outline edges; curves are unsupported
    assert len(boxes) == 1  # translucent foreground bar; zero-alpha and shade are excluded
    assert not any(_hits((50, 40), (2, 2), edge) for edge in segments[1:])
    clipped = next(item for item in segments if item.start[1] == pytest.approx(-0.4))
    assert clipped.start[0] == pytest.approx(-1)
    assert clipped.end[0] == pytest.approx(101)
