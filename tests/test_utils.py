import polars as pl
import pytest

from dysonsphere.utils import (
    _nice_domain,
    band_geometry,
    count_n,
    ensure_polars,
    frame_checksum,
)


class TestNiceDomain:
    def test_rounds_outward_to_tick_multiples(self):
        assert _nice_domain(1.13, 3.42) == (1.0, 3.6)
        assert _nice_domain(4.2, 8.9) == (4.0, 9.0)

    def test_already_nice_unchanged(self):
        assert _nice_domain(1.0, 3.0) == (1.0, 3.0)
        assert _nice_domain(0.0, 10.0) == (0.0, 10.0)

    def test_never_shrinks(self):
        lo, hi = _nice_domain(-2.37, 5.81)
        assert lo <= -2.37 and hi >= 5.81

    def test_negative_span(self):
        assert _nice_domain(-8.9, -4.2) == (-9.0, -4.0)

    def test_degenerate_span_unchanged(self):
        # zero-width (or inverted) extents pass through - the caller's `span or 1.0` handles them
        assert _nice_domain(5.0, 5.0) == (5.0, 5.0)
        assert _nice_domain(0.0, 0.0) == (0.0, 0.0)


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


# ── band_geometry() ──────────────────────────────────────────────────────────


class TestBandGeometry:
    def test_offset_scale_formulas(self):
        # paddingInner=0, paddingOuter=bp (xOffset/mark_circle/add_shade rects)
        geo = band_geometry(3, 100, bandPadding=0.1)
        step = 100 / (3 + 2 * 0.1)
        assert geo.step == pytest.approx(step)
        assert list(geo.centers) == pytest.approx([step * (0.1 + i + 0.5) for i in range(3)])
        assert list(geo.starts) == pytest.approx([step * (0.1 + i) for i in range(3)])
        assert list(geo.ends) == pytest.approx([step * (0.1 + i + 1) for i in range(3)])

    def test_band_scale_formulas(self):
        # paddingInner=paddingOuter=bp (mark_boxplot / mark_violin)
        geo = band_geometry(3, 100, scale="band", bandPadding=0.1)
        step = 100 / (3 + 0.1)
        assert geo.step == pytest.approx(step)
        assert list(geo.centers) == pytest.approx([step * (0.5 + 0.05 + i) for i in range(3)])

    def test_point_scale_formulas(self):
        geo = band_geometry(4, 100, scale="point")
        assert geo.step == pytest.approx(25.0)
        assert list(geo.centers) == pytest.approx([12.5, 37.5, 62.5, 87.5])
        assert geo.starts == geo.centers and geo.ends == geo.centers

    def test_adjacent_bands_share_edges(self):
        # end of band i is the start of band i+1 (offset scale) - what add_shade's
        # run merging and flush logic rely on
        geo = band_geometry(5, 200)
        for i in range(4):
            assert geo.ends[i] == pytest.approx(geo.starts[i + 1])

    def test_defaults_read_theme(self):
        import altair as alt

        from dysonsphere.theme import theme

        theme(chartWidth=200, bandPadding=0.2)
        geo = band_geometry(2)
        assert geo.step == pytest.approx(200 / (2 + 2 * 0.2))
        theme()  # reset
        assert alt.theme.options.get("chartWidth") == 100

    def test_band_centers_match_rendered_boxplot(self, tmp_path):
        # the "band" case is the boxplot's actual scale: centres must equal the
        # rendered box centres exactly (which also equal the ticks - see
        # TestExactTickPositions in test_export.py)
        import re

        import altair as alt

        from dysonsphere.export import save
        from dysonsphere.theme import theme

        theme()
        df = pl.DataFrame({"g": ["A", "B", "C"] * 5, "v": [float(i % 4) for i in range(15)]})
        save(
            alt.Chart(df).mark_boxplot().encode(x="g:N", y="v:Q"),
            str(tmp_path / "b"),
            format="svg",
            background="light",
        )
        svg = (tmp_path / "b.svg").read_text(encoding="utf-8")
        boxes = sorted(
            float(x) + float(w) / 2
            for x, w in re.findall(r'aria-roledescription="box"[^>]*d="M([-\d.]+),[-\d.]+h([-\d.]+)', svg)
        )
        geo = band_geometry(3, scale="band")
        assert boxes == pytest.approx(list(geo.centers), abs=1e-9)

    def test_invalid_scale_raises(self):
        with pytest.raises(ValueError, match="scale"):
            band_geometry(3, 100, scale="nope")

    def test_zero_categories_raises(self):
        with pytest.raises(ValueError, match="n must be"):
            band_geometry(0, 100)
