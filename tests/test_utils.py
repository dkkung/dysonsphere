import polars as pl
import pytest

from dysonsphere.metadata import frame_checksum
from dysonsphere.theme import theme
from dysonsphere.utils import (
    _ROW_HASH_PREFIX,
    _band_geometry,
    _canonicalize,
    _count_n,
    _ensure_polars,
    _json_safe,
    _nested_band_centers,
    _nice_domain,
    stripe_colors,
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
        result = _ensure_polars(simple_df)
        assert result is simple_df

    def test_invalid_type_raises(self):
        with pytest.raises(TypeError, match="Expected a polars.DataFrame or pandas.DataFrame"):
            _ensure_polars("not a dataframe")  # ty: ignore[invalid-argument-type]

    def test_invalid_type_dict_raises(self):
        with pytest.raises(TypeError):
            _ensure_polars({"group": ["A", "B"]})  # ty: ignore[invalid-argument-type]

    def test_pandas_subclass_is_accepted_without_changing_rows(self):
        import pandas as pd

        class Frame(pd.DataFrame):
            @property
            def _constructor(self):
                return Frame

        frame = Frame({"group": ["A", "B"], "value": [1.0, None]})
        result = _ensure_polars(frame)
        assert result.height == 2
        assert result.columns == ["group", "value"]
        assert result.to_dict(as_series=False) == {"group": ["A", "B"], "value": [1.0, None]}

    def test_polars_subclass_is_passed_through(self, simple_df):
        class Frame(pl.DataFrame):
            pass

        frame = Frame(simple_df)
        assert _ensure_polars(frame) is frame

    def test_pandas_series_is_rejected(self):
        import pandas as pd

        with pytest.raises(TypeError, match="Expected a polars.DataFrame or pandas.DataFrame"):
            _ensure_polars(pd.Series([1, 2]))  # ty: ignore[invalid-argument-type]

    @pytest.mark.parametrize("value", [[{"group": "A"}], pl.Series([1, 2]), "data.csv"])
    def test_non_dataframe_inputs_are_rejected(self, value):
        with pytest.raises(TypeError, match="Expected a polars.DataFrame or pandas.DataFrame"):
            _ensure_polars(value)


class TestCountN:
    def test_basic_counts(self, simple_df):
        assert _count_n(simple_df, "group", ["A", "B"]) == [2, 3]

    def test_order_preserved(self, simple_df):
        assert _count_n(simple_df, "group", ["B", "A"]) == [3, 2]

    def test_missing_category_returns_zero(self, simple_df):
        assert _count_n(simple_df, "group", ["A", "C"]) == [2, 0]

    def test_empty_categories(self, simple_df):
        assert _count_n(simple_df, "group", []) == []


class TestFrameChecksum:
    def test_shape_and_prefix(self, simple_df):
        s = frame_checksum(simple_df)
        assert s.startswith(_ROW_HASH_PREFIX) and len(s) == len(_ROW_HASH_PREFIX) + 64

    def test_order_independent(self, simple_df):
        shuffled = simple_df.sample(fraction=1.0, shuffle=True, seed=3)
        assert frame_checksum(simple_df) == frame_checksum(shuffled)  # same content, any order

    def test_different_content_differs(self, simple_df):
        other = simple_df.with_columns(pl.col("value") * 2)
        assert frame_checksum(simple_df) != frame_checksum(other)

    def test_pandas_matches_polars(self, simple_df):
        assert frame_checksum(simple_df.to_pandas()) == frame_checksum(simple_df)  # _ensure_polars first


# ── canonicalization ─────────────────────────────────────────────────────────


class TestJsonSafe:
    """Only non-finite floats are replaced - everything else is written unchanged."""

    def test_replaces_non_finite(self):
        assert _json_safe(float("nan")) is None
        assert _json_safe(float("inf")) is None
        assert _json_safe(float("-inf")) is None

    def test_preserves_finite_floats_exactly(self):
        # 1.0 must NOT collapse to 1: a Float64 column has to survive save() -> read().
        assert _json_safe(1.0) == 1.0 and isinstance(_json_safe(1.0), float)
        assert _json_safe(1.5) == 1.5

    def test_leaves_other_types_alone(self):
        assert _json_safe("a") == "a"
        assert _json_safe(3) == 3
        assert _json_safe(None) is None
        assert _json_safe(True) is True

    def test_recurses_into_nested_structures(self):
        got = _json_safe({"rows": [{"v": float("nan")}, {"v": 2.5}], "n": [float("inf")]})
        assert got == {"rows": [{"v": None}, {"v": 2.5}], "n": [None]}


class TestCanonicalize:
    """Hashing normalization - equal data must produce one representation."""

    def test_non_finite_becomes_none(self):
        assert _canonicalize(float("nan")) is None
        assert _canonicalize(float("inf")) is None

    def test_integral_float_becomes_int(self):
        assert _canonicalize(1.0) == 1 and isinstance(_canonicalize(1.0), int)
        assert isinstance(_canonicalize(2.5), float)  # non-integral untouched

    def test_recurses(self):
        assert _canonicalize({"a": [1.0, float("nan")]}) == {"a": [1, None]}


class TestChecksumCanonicalization:
    def test_int_and_float_columns_agree(self):
        di = pl.DataFrame({"g": ["a", "b"], "v": [1, 2]})
        df = pl.DataFrame({"g": ["a", "b"], "v": [1.0, 2.0]})
        assert frame_checksum(di) == frame_checksum(df)  # dtype alone must not change identity

    def test_nan_and_null_agree(self):
        dn = pl.DataFrame({"g": ["a", "b"], "v": [1.0, float("nan")]})
        dnull = pl.DataFrame({"g": ["a", "b"], "v": [1.0, None]})
        assert frame_checksum(dn) == frame_checksum(dnull)  # both mean "absent"

    def test_still_distinguishes_real_differences(self):
        a = pl.DataFrame({"g": ["a", "b"], "v": [1.0, 2.0]})
        b = pl.DataFrame({"g": ["a", "b"], "v": [1.0, 2.5]})
        assert frame_checksum(a) != frame_checksum(b)


# ── _band_geometry() ─────────────────────────────────────────────────────────


class TestPrivateBandGeometry:
    def test_offset_scale_formulas(self):
        # paddingInner=0, paddingOuter=bp (xOffset/mark_circle/shade rects)
        geo = _band_geometry(3, 100, bandPadding=0.1)
        step = 100 / (3 + 2 * 0.1)
        assert geo.step == pytest.approx(step)
        assert list(geo.centers) == pytest.approx([step * (0.1 + i + 0.5) for i in range(3)])
        assert list(geo.starts) == pytest.approx([step * (0.1 + i) for i in range(3)])
        assert list(geo.ends) == pytest.approx([step * (0.1 + i + 1) for i in range(3)])

    def test_band_scale_formulas(self):
        # paddingInner=paddingOuter=bp (mark_bar)
        geo = _band_geometry(3, 100, scale="band", bandPadding=0.1)
        step = 100 / (3 + 0.1)
        assert geo.step == pytest.approx(step)
        assert list(geo.centers) == pytest.approx([step * (0.5 + 0.05 + i) for i in range(3)])

    def test_rect_scale_formulas(self):
        # paddingInner=rectPadding (0 by default, so cells abut), paddingOuter=outerPadding
        from dysonsphere.theme import theme

        theme()
        geo = _band_geometry(4, 100, scale="rect")
        step = 100 / (4 + 2 * 0.1)
        assert geo.step == pytest.approx(step)
        assert list(geo.starts) == pytest.approx([step * (0.1 + i) for i in range(4)])
        assert list(geo.ends) == pytest.approx([step * (0.1 + i + 1) for i in range(4)])
        # abutting cells - the whole point of rectPadding=0
        for i in range(3):
            assert geo.ends[i] == pytest.approx(geo.starts[i + 1])

    def test_point_scale_formulas(self):
        geo = _band_geometry(4, 100, scale="point")
        assert geo.step == pytest.approx(25.0)
        assert list(geo.centers) == pytest.approx([12.5, 37.5, 62.5, 87.5])
        assert geo.starts == geo.centers and geo.ends == geo.centers

    def test_singleton_full_inner_padding_matches_d3_clamp_and_alignment(self):
        theme(barPadding=1, outerPadding=0)
        geo = _band_geometry(1, 100, scale="band")
        assert geo.step == pytest.approx(100)
        assert geo.starts == pytest.approx((50,))
        assert geo.centers == pytest.approx((50,))
        assert geo.ends == pytest.approx((50,))

    def test_singleton_high_inner_padding_with_outer_padding(self):
        theme(rectPadding=0.9, outerPadding=0.2)
        geo = _band_geometry(1, 100, scale="rect")
        step = 100 / max(1, 1 - 0.9 + 2 * 0.2)
        start = (100 - step * (1 - 0.9)) / 2
        assert geo.step == pytest.approx(step)
        assert geo.starts == pytest.approx((start,))
        assert geo.ends == pytest.approx((start + step * 0.1,))

    def test_multiple_categories_nonzero_outer_keeps_normal_positions(self):
        theme(barPadding=0.3, outerPadding=0.4)
        geo = _band_geometry(3, 120, scale="band")
        step = 120 / (3 - 0.3 + 0.8)
        assert geo.step == pytest.approx(step)
        assert geo.starts == pytest.approx(tuple(step * (0.4 + i) for i in range(3)))

    def test_singleton_endpoint_matches_rendered_bar_center(self):
        import re

        import altair as alt
        import vl_convert as vlc

        theme(width=100, barPadding=1, outerPadding=0)
        chart = alt.Chart({"values": [{"g": "A", "v": 1}]}).mark_bar().encode(x="g:N", y="v:Q")
        svg = vlc.vegalite_to_svg(chart.to_dict())
        bar = re.search(r'aria-roledescription="bar"[^>]*d="M([\d.]+),[^h]+h([\d.]+)', svg)
        assert bar is not None
        assert float(bar.group(1)) == pytest.approx(50)
        # Vega emits the configured 0.25px stroke as a minimum visible path width,
        # while the scale's zero-width band starts at the centered x=50 position.
        assert float(bar.group(2)) == pytest.approx(0.25)

    def test_adjacent_bands_share_edges(self):
        # end of band i is the start of band i+1 (offset scale) - what shade's
        # run merging and flush logic rely on
        geo = _band_geometry(5, 200)
        for i in range(4):
            assert geo.ends[i] == pytest.approx(geo.starts[i + 1])

    def test_defaults_read_theme(self):
        import altair as alt

        from dysonsphere.theme import theme

        theme(width=200, outerPadding=0.2)
        geo = _band_geometry(2)
        assert geo.step == pytest.approx(200 / (2 + 2 * 0.2))
        theme()  # reset
        assert alt.theme.options.get("width") == 100

    def test_rect_centers_match_rendered_boxplot(self, tmp_path):
        # Vega-Lite routes boxplot through rectBandPaddingInner ("rect and other marks"),
        # NOT barBandPaddingInner - so the "rect" variant is the boxplot's actual scale and
        # its centres must equal the rendered box centres exactly (which also equal the
        # ticks - see TestExactTickPositions in test_export.py)
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
        geo = _band_geometry(3, scale="rect")
        assert boxes == pytest.approx(list(geo.centers), abs=1e-9)

    def test_invalid_scale_raises(self):
        with pytest.raises(ValueError, match="scale"):
            _band_geometry(3, 100, scale="nope")

    def test_zero_categories_raises(self):
        with pytest.raises(ValueError, match="n must be"):
            _band_geometry(0, 100)


class TestNestedBandCenters:
    """_nested_band_centers - sub-bar positions of a grouped (xOffset) chart."""

    def test_shape_and_ordering(self):
        theme()
        got = _nested_band_centers(3, 4, 100.0)
        assert len(got) == 3 and all(len(row) == 4 for row in got)
        flat = [x for row in got for x in row]
        assert flat == sorted(flat)
        assert all(0.0 < x < 100.0 for x in flat)

    def test_sub_bars_sit_inside_their_own_band(self):
        # Each category's sub-bars must fall within that category's band, or a bracket would
        # point at the neighbouring group.
        theme()
        outer = _band_geometry(3, 100.0, scale="band", bandPadding=0.2)
        for i, row in enumerate(_nested_band_centers(3, 3, 100.0)):
            assert all(outer.starts[i] <= x <= outer.ends[i] for x in row)

    def test_matches_vega_rendered_positions(self):
        # Pinned against sub-bar centres measured from real rendered SVG (2 categories,
        # 3 levels, 100px). _band_geometry's own variants do NOT reproduce these - they
        # resolve barPadding/outerPadding instead of the nested offset keys.
        theme()
        got = [round(x, 3) for row in _nested_band_centers(2, 3, 100.0) for x in row]
        assert got == [15.152, 27.273, 39.394, 60.606, 72.727, 84.848]

    def test_single_level_centres_on_the_band(self):
        theme()
        outer = _band_geometry(4, 100.0, scale="band", bandPadding=0.2)
        got = _nested_band_centers(4, 1, 100.0)
        assert [row[0] for row in got] == pytest.approx(list(outer.centers))

    def test_full_group_and_subgroup_padding_matches_nested_renderer_geometry(self):
        theme(groupPadding=1, subgroupPadding=1)
        outer = _band_geometry(2, 100.0, scale="band", bandPadding=1)
        got = _nested_band_centers(2, 2, 100.0)
        for i, row in enumerate(got):
            inner = _band_geometry(2, outer.ends[i] - outer.starts[i], scale="band", bandPadding=1)
            assert row == pytest.approx([outer.starts[i] + center for center in inner.centers])
        assert got[0] == pytest.approx([100 / 3, 100 / 3])
        assert got[1] == pytest.approx([200 / 3, 200 / 3])


class TestStripeColors:
    """Row-striping fills: the lightest n stops, or the darkest in darkmode."""

    def test_light_takes_the_lightest_stops(self):
        from dysonsphere.palettes import colors

        assert stripe_colors("greys", 2, darkmode=False) == colors["greys"][:2]

    def test_dark_takes_the_darkest_stops(self):
        from dysonsphere.palettes import colors

        assert stripe_colors("greys", 2, darkmode=True) == colors["greys"][-2:]

    def test_hex_list_passes_through(self):
        assert stripe_colors(["#111111", "#222222", "#333333"], 2, darkmode=False) == ["#111111", "#222222"]

    def test_unknown_palette_raises(self):
        with pytest.raises(ValueError, match="unknown palette"):
            stripe_colors("not-a-palette", 2, darkmode=False)

    def test_zero_raises(self):
        with pytest.raises(ValueError, match="must be >= 1"):
            stripe_colors("greys", 0, darkmode=False)

    def test_matches_what_mark_table_emits(self):
        """The helper must reproduce mark_table's stripe fills exactly."""
        import polars as pl

        from dysonsphere.table import mark_table
        from dysonsphere.theme import theme

        theme()
        spec = mark_table(pl.DataFrame({"a": [1, 2, 3, 4], "b": [1.0, 2.0, 3.0, 4.0]})).to_dict()
        fills = {
            layer["mark"]["fill"]
            for layer in spec["layer"]
            if isinstance(layer.get("mark"), dict) and layer["mark"].get("type") == "rect" and "fill" in layer["mark"]
        }
        assert set(stripe_colors("greys", 2, darkmode=False)) <= fills
