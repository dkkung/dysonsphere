import polars as pl
import pytest

from dysonsphere.utils import count_n, ensure_polars, frame_checksum


@pytest.fixture
def simple_df():
    return pl.DataFrame({"group": ["A", "A", "B", "B", "B"], "value": [1.0, 2.0, 3.0, 4.0, 5.0]})


class TestEnsurePolars:
    def test_polars_passthrough(self, simple_df):
        result = ensure_polars(simple_df)
        assert result is simple_df

    def test_invalid_type_raises(self):
        with pytest.raises(TypeError, match="Expected a polars.DataFrame or pandas.DataFrame"):
            ensure_polars("not a dataframe")  # ty: ignore[invalid-argument-type]

    def test_invalid_type_dict_raises(self):
        with pytest.raises(TypeError):
            ensure_polars({"group": ["A", "B"]})  # ty: ignore[invalid-argument-type]


class TestCountN:
    def test_basic_counts(self, simple_df):
        assert count_n(simple_df, "group", ["A", "B"]) == [2, 3]

    def test_order_preserved(self, simple_df):
        assert count_n(simple_df, "group", ["B", "A"]) == [3, 2]

    def test_missing_category_returns_zero(self, simple_df):
        assert count_n(simple_df, "group", ["A", "C"]) == [2, 0]

    def test_empty_categories(self, simple_df):
        assert count_n(simple_df, "group", []) == []


class TestFrameChecksum:
    def test_shape_and_prefix(self, simple_df):
        s = frame_checksum(simple_df)
        assert s.startswith("sha256:") and len(s) == len("sha256:") + 64

    def test_order_independent(self, simple_df):
        shuffled = simple_df.sample(fraction=1.0, shuffle=True, seed=3)
        assert frame_checksum(simple_df) == frame_checksum(shuffled)  # same content, any order

    def test_different_content_differs(self, simple_df):
        other = simple_df.with_columns(pl.col("value") * 2)
        assert frame_checksum(simple_df) != frame_checksum(other)

    def test_pandas_matches_polars(self, simple_df):
        assert frame_checksum(simple_df.to_pandas()) == frame_checksum(simple_df)  # ensure_polars first
