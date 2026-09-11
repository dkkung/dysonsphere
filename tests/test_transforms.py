import numpy as np
import polars as pl
import pytest

from dysonsphere.theme import theme
from dysonsphere.transforms import (
    _beeswarm_offsets,
    _quasirandom_offsets,
    _van_der_corput,
    beeswarm,
    jitter,
    quasirandom,
)


@pytest.fixture(autouse=True)
def default_theme():
    theme(width=200, height=200)


@pytest.fixture
def group_df():
    rng = np.random.default_rng(0)
    return pl.DataFrame(
        {
            "group": ["A"] * 20 + ["B"] * 20,
            "value": np.concatenate([rng.normal(0, 1, 20), rng.normal(2, 1, 20)]),
        }
    )


class TestBeeswarmOffsets:
    def test_empty_input(self):
        result = _beeswarm_offsets(np.array([]))
        assert len(result) == 0

    def test_single_point_zero_offset(self):
        result = _beeswarm_offsets(np.array([5.0]))
        assert result[0] == pytest.approx(0.0)

    def test_output_length_matches_input(self):
        vals = np.linspace(0, 10, 30)
        result = _beeswarm_offsets(vals, spread=3.0)
        assert len(result) == len(vals)

    def test_no_overlaps(self):
        rng = np.random.default_rng(42)
        y = rng.uniform(0, 100, 40)
        spread = 4.0
        x = _beeswarm_offsets(y, heightPx=200, spread=spread)
        y_px = (y - y.min()) / max(y.max() - y.min(), 1e-9) * 200
        for i in range(len(y)):
            for j in range(i + 1, len(y)):
                dist_sq = (x[i] - x[j]) ** 2 + (y_px[i] - y_px[j]) ** 2
                assert dist_sq >= (2 * spread) ** 2 - 1e-6, (
                    f"Points {i} and {j} overlap: dist²={dist_sq:.4f}, min²={(2 * spread) ** 2:.4f}"
                )

    def test_identical_y_values_spread_out(self):
        y = np.array([5.0, 5.0, 5.0, 5.0])
        spread = 2.0
        x = _beeswarm_offsets(y, heightPx=100, spread=spread)
        assert len(set(x)) > 1


class TestJitter:
    def test_adds_offset_column(self, group_df):
        result = jitter(group_df)
        assert "jitter_x" in result.columns

    def test_output_length_unchanged(self, group_df):
        result = jitter(group_df)
        assert len(result) == len(group_df)

    def test_custom_column_name(self, group_df):
        result = jitter(group_df, outCol="my_jitter")
        assert "my_jitter" in result.columns

    def test_spread_controls_width(self, group_df):
        tight = jitter(group_df, spread=0.5, seed=0)
        wide = jitter(group_df, spread=20.0, seed=0)
        assert tight["jitter_x"].abs().max() < wide["jitter_x"].abs().max()  # ty: ignore[unsupported-operator]


class TestBeeswarm:
    def test_adds_offset_column(self, group_df):
        result = beeswarm(group_df, column="value", groupBy=["group"])
        assert "beeswarm_x" in result.columns

    def test_output_length_unchanged(self, group_df):
        result = beeswarm(group_df, column="value", groupBy=["group"])
        assert len(result) == len(group_df)

    def test_custom_column_name(self, group_df):
        result = beeswarm(group_df, column="value", groupBy=["group"], outCol="my_swarm")
        assert "my_swarm" in result.columns

    def test_multiple_grouping_columns_preserve_rows(self):
        data = pl.DataFrame({"group": ["B", "A", "B", "A"], "condition": [2, 1, 1, 2], "value": [4.0, 1.0, 3.0, 2.0]})
        result = beeswarm(data, column="value", groupBy=["group", "condition"])
        assert result.select(data.columns).equals(data)


class TestQuasirandom:
    def test_adds_offset_column(self, group_df):
        result = quasirandom(group_df, column="value", groupBy=["group"])
        assert "quasirandom_x" in result.columns

    def test_output_length_unchanged(self, group_df):
        result = quasirandom(group_df, column="value", groupBy=["group"])
        assert len(result) == len(group_df)

    def test_custom_column_name(self, group_df):
        result = quasirandom(group_df, column="value", groupBy=["group"], outCol="my_q")
        assert "my_q" in result.columns

    def test_rows_map_back_in_order(self, group_df):
        # the offset must line up with its own row after the group_by/sort round-trip
        result = quasirandom(group_df, column="value", groupBy=["group"])
        assert result["value"].to_list() == group_df["value"].to_list()

    def test_multiple_grouping_columns_preserve_rows(self):
        data = pl.DataFrame(
            {
                "row": [3, 0, 2, 1, 4, 5],
                "group": ["B", "A", "B", "A", "A", "A"],
                "condition": [2, 1, 1, 2, 1, 1],
                "value": [4.0, 1.0, 3.0, 2.0, 1.5, 2.5],
            }
        )
        result = quasirandom(data, column="value", groupBy=["group", "condition"])
        assert result.select(data.columns).equals(data)

    def test_width_and_bandwidth_accepted(self, group_df):
        result = quasirandom(group_df, column="value", groupBy=["group"], width=20.0, bandwidth=0.5)
        assert "quasirandom_x" in result.columns and len(result) == len(group_df)

    @pytest.mark.parametrize("value", [float("nan"), None, float("inf"), float("-inf")])
    def test_kde_rejects_missing_or_nonfinite_observations(self, value):
        data = pl.DataFrame({"group": ["A", "A", "B"], "value": [1.0, value, 3.0]})
        with pytest.raises(ValueError, match="quasirandom KDE column 'value'.*group 'A'"):
            quasirandom(data, column="value", groupBy=["group"])

    @pytest.mark.parametrize("values", [[1e308, 1e308 - 1e292, 1e308 - 2e292]])
    def test_kde_rejects_finite_but_numerically_unusable_values(self, values):
        data = pl.DataFrame({"group": ["A"] * len(values), "value": values})
        with pytest.raises(ValueError, match="quasirandom KDE column 'value'.*group 'A'"):
            quasirandom(data, column="value", groupBy=["group"])

    def test_constant_and_singleton_groups_keep_fallback(self):
        constant = pl.DataFrame({"group": ["A"] * 4, "value": [5.0] * 4})
        singleton = pl.DataFrame({"group": ["A"], "value": [5.0]})
        assert len(quasirandom(constant, column="value", groupBy=["group"])) == 4
        assert quasirandom(singleton, column="value", groupBy=["group"])["quasirandom_x"].to_list() == [0.0]

    def test_empty_input_preserves_existing_grouped_apply_error(self):
        data = pl.DataFrame({"group": pl.Series([], dtype=pl.String), "value": pl.Series([], dtype=pl.Float64)})
        with pytest.raises(pl.exceptions.ComputeError, match="empty"):
            quasirandom(data, column="value", groupBy=["group"])


class TestVanDerCorput:
    def test_length_and_range(self):
        seq = _van_der_corput(8)
        assert len(seq) == 8 and np.all((seq > 0) & (seq < 1))

    def test_known_sequence(self):
        # base-2 van der Corput: 1/2, 1/4, 3/4, 1/8, 5/8, 3/8, 7/8
        expected = [0.5, 0.25, 0.75, 0.125, 0.625, 0.375, 0.875]
        assert _van_der_corput(7).tolist() == pytest.approx(expected)


class TestQuasirandomOffsets:
    def test_empty_input(self):
        assert len(_quasirandom_offsets(np.array([]))) == 0

    def test_single_point_zero_offset(self):
        assert _quasirandom_offsets(np.array([5.0]))[0] == pytest.approx(0.0)

    def test_output_length_matches_input(self):
        y = np.linspace(0, 10, 30)
        assert len(_quasirandom_offsets(y, heightPx=200)) == 30

    def test_deterministic(self):
        y = np.array([1.0, 1.0, 2.0, 2.0, 2.0, 3.0])
        a = _quasirandom_offsets(y, heightPx=200)
        b = _quasirandom_offsets(y, heightPx=200)
        assert a.tolist() == b.tolist()

    def test_symmetric_and_no_point_on_centre_even_group(self):
        # the raison d'etre: an even-count group straddles the tick - centred on 0, with no point
        # parked exactly on the centre line (the swarm method's lopsided-even-row artifact).
        y = np.array([5.0, 5.0, 5.0, 5.0])
        x = _quasirandom_offsets(y, heightPx=100, spread=2.0)
        assert x.max() == pytest.approx(-x.min(), abs=1e-9)  # symmetric outline about the tick
        assert np.min(np.abs(x)) > 1e-6  # no point welded to centre

    def test_width_scales_spread(self):
        y = np.array([1.0, 1.0, 1.0, 1.0, 1.0, 1.0])
        narrow = np.abs(_quasirandom_offsets(y, heightPx=100, width=5.0)).max()
        wide = np.abs(_quasirandom_offsets(y, heightPx=100, width=50.0)).max()
        assert wide > narrow

    def test_density_narrows_tails(self):
        # a tight cluster plus a couple of far outliers: the dense core spreads wider than the tails
        y = np.concatenate([np.full(40, 5.0) + np.linspace(-0.1, 0.1, 40), [50.0, 51.0]])
        x = _quasirandom_offsets(y, heightPx=200)
        core = np.abs(x[:40]).max()
        tail = np.abs(x[40:]).max()
        assert core > tail

    @pytest.mark.parametrize(
        ("y", "expected"),
        [
            ([0.0, 5e-11, 1e-10], [0.0, -1.2615662610100802, 1.2615662610100802]),
            ([1e-320, 2e-320, 3e-320], [0.0, -3.7846987830302403, 3.7846987830302403]),
        ],
    )
    def test_nonconstant_tiny_ranges_keep_uniform_fallback(self, y, expected):
        assert _quasirandom_offsets(np.array(y)) == pytest.approx(expected)

    def test_nonpositive_density_normalizer_is_rejected(self, monkeypatch):
        import dysonsphere.transforms as transforms

        class ZeroDensityKDE:
            covariance = np.array([[1.0]])

            def __call__(self, values):
                return np.zeros(len(values))

        monkeypatch.setattr(transforms, "gaussian_kde", lambda values, bw_method=None: ZeroDensityKDE())
        with pytest.raises(ValueError, match="invalid density normalizer"):
            _quasirandom_offsets(np.array([0.0, 1.0]), column="signal", group="A")
