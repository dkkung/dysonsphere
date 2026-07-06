"""Tests for dysonsphere._placement - the pure pixel-space label placement engine."""

import math

from dysonsphere._placement import _repel_labels, _sample_spread


class TestSampleSpread:
    def test_returns_n_indices(self):
        assert len(_sample_spread([float(i) for i in range(10)], [0.0] * 10, 3)) == 3

    def test_n_ge_len_returns_all(self):
        assert sorted(_sample_spread([1.0, 2.0, 3.0], [1.0, 2.0, 3.0], 5)) == [0, 1, 2]

    def test_n_le_zero_empty(self):
        assert _sample_spread([1.0, 2.0], [1.0, 2.0], 0) == []

    def test_deterministic(self):
        xs = [float(i) for i in range(20)]
        ys = [float((i * 7) % 20) for i in range(20)]
        assert _sample_spread(xs, ys, 5) == _sample_spread(xs, ys, 5)

    def test_spread_reaches_extremes(self):
        # an even spread over a line must include both ends
        idx = _sample_spread([float(i) for i in range(10)], [0.0] * 10, 3)
        assert 0 in idx and 9 in idx


class TestRepelLabelsObstacles:
    def test_obstacles_shift_placement(self):
        # background points near where the label would sit must push it off them
        anchor = [(150.0, 150.0)]
        size = [(20.0, 8.0)]
        base = _repel_labels(anchor, size, width=300, height=300)[0]  # obstacles default to anchor
        obs = [(150.0, 150.0), (140.0, 138.0), (144.0, 140.0), (138.0, 142.0)]  # a cluster up-left
        shifted = _repel_labels(anchor, size, width=300, height=300, obstacles=obs)[0]
        assert math.dist(base, shifted) > 1.0  # the extra points moved the label

    def test_labels_avoid_each_others_connectors(self):
        # two labels with nearby points: repel must keep each label off the OTHER's connector line
        anchors = [(150.0, 150.0), (156.0, 150.0)]
        sizes = [(30.0, 8.0), (30.0, 8.0)]
        pos = _repel_labels(anchors, sizes, width=400, height=400)
        hw, hh = 30 / 2 + 2, 8 / 2 + 2  # box half-size incl. padding

        def connector_crosses_box(anchor, label, box_center):
            ax, ay = anchor
            lx, ly = label
            vx, vy = lx - ax, ly - ay
            L2 = vx * vx + vy * vy
            t = 0.0 if L2 == 0 else min(1.0, max(0.0, ((box_center[0] - ax) * vx + (box_center[1] - ay) * vy) / L2))
            cx, cy = ax + t * vx, ay + t * vy
            return abs(box_center[0] - cx) < hw and abs(box_center[1] - cy) < hh

        assert not connector_crosses_box(anchors[0], pos[0], pos[1])
        assert not connector_crosses_box(anchors[1], pos[1], pos[0])


class TestRepelLabels:
    def test_empty(self):
        assert _repel_labels([], [], width=100, height=100) == []

    def test_one_position_per_anchor(self):
        out = _repel_labels([(10.0, 10.0), (20.0, 20.0), (30.0, 30.0)], [(8.0, 4.0)] * 3, width=100, height=100)
        assert len(out) == 3

    def test_deterministic(self):
        anchors, sizes = [(50.0, 50.0)] * 5, [(10.0, 5.0)] * 5
        assert _repel_labels(anchors, sizes, width=100, height=100) == _repel_labels(
            anchors, sizes, width=100, height=100
        )

    def test_separates_coincident_anchors(self):
        # 5 labels stacked on one point must fan out (force-show, never dropped).
        out = _repel_labels([(150.0, 150.0)] * 5, [(12.0, 6.0)] * 5, width=300, height=300)
        dists = [math.dist(out[i], out[j]) for i in range(5) for j in range(i + 1, 5)]
        assert min(dists) > 1.0  # none coincide
        assert max(dists) > 12.0  # spread beyond a single label width

    def test_stays_in_panel(self):
        out = _repel_labels([(0.0, 0.0), (100.0, 100.0)], [(20.0, 10.0)] * 2, width=100, height=100)
        for x, y in out:
            assert 0 <= x <= 100
            assert 0 <= y <= 100
