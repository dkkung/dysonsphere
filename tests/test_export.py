import math
import re
import textwrap
import xml.etree.ElementTree as ET
from pathlib import Path

import altair as alt
import polars as pl
import pytest

from dysonsphere.export import (
    _fix_log_minor_ticks,
    _fix_tick_alignment,
    _layer_axes_to_front,
    _simplify_svg,
    save,
)
from dysonsphere.theme import theme

NS = "http://www.w3.org/2000/svg"


def _write(tmp_path, name, content):
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return str(p)


def _tick_xs(path):
    """Collect x-axis tick translate-x values from a test SVG."""
    root = ET.parse(path).getroot()
    xs = []

    def collect(el):
        for child in el:
            if child.get("class", "") == "mark-rule role-axis-tick":
                for line in child:
                    m = re.match(r"translate\(([\d.]+),", line.get("transform", ""))
                    if m:
                        xs.append(float(m.group(1)))
            else:
                collect(child)

    collect(root)
    return xs


def _y_minor_positions(path, minor_size):
    """Y-axis minor tick y values, identified by x2 == -minor_size."""
    root = ET.parse(path).getroot()
    ys = []
    for line in root.iter(f"{{{NS}}}line"):
        m = re.match(r"translate\(0,([\d.]+)\)$", line.get("transform", ""))
        if m and line.get("x2") == f"-{minor_size}":
            ys.append(float(m.group(1)))
    return sorted(ys)


def _x_minor_positions(path, minor_size):
    """X-axis minor tick x values, identified by y2 == minor_size."""
    root = ET.parse(path).getroot()
    xs = []
    for line in root.iter(f"{{{NS}}}line"):
        m = re.match(r"translate\(([\d.]+),0\)$", line.get("transform", ""))
        if m and line.get("y2") == str(minor_size):
            xs.append(float(m.group(1)))
    return sorted(xs)


def _y_tick_svg(major_ys, minor_ys, major_size=5, minor_size=3):
    lines = [f'  <line transform="translate(0,{y})" x1="0" y1="0" x2="-{major_size}" y2="0"/>'
             for y in major_ys]
    lines += [f'  <line transform="translate(0,{y})" x1="0" y1="0" x2="-{minor_size}" y2="0"/>'
              for y in minor_ys]
    return f'<svg xmlns="{NS}">\n' + "\n".join(lines) + "\n</svg>"


def _x_tick_svg(major_xs, minor_xs, major_size=5, minor_size=3):
    lines = [f'  <line transform="translate({x},0)" x1="0" y1="0" x2="0" y2="{major_size}"/>'
             for x in major_xs]
    lines += [f'  <line transform="translate({x},0)" x1="0" y1="0" x2="0" y2="{minor_size}"/>'
              for x in minor_xs]
    return f'<svg xmlns="{NS}">\n' + "\n".join(lines) + "\n</svg>"


_TICK_SVG = (
    f'<svg xmlns="{NS}">'
    '<g class="mark-rule role-axis-tick">'
    '<line transform="translate({x0},0)" x1="0" y1="0" x2="0" y2="-3"/>'
    '<line transform="translate({x1},0)" x1="0" y1="0" x2="0" y2="-3"/>'
    '<line transform="translate({x2},0)" x1="0" y1="0" x2="0" y2="-3"/>'
    "</g></svg>"
)


@pytest.fixture(autouse=True)
def default_theme():
    theme()


@pytest.fixture
def simple_chart():
    df = pl.DataFrame({"x": ["A", "B", "C"], "y": [1.0, 2.0, 3.0]})
    return alt.Chart(df).mark_point().encode(x="x:N", y="y:Q")


# ── save() ───────────────────────────────────────────────────────────────────


class TestSave:
    def test_light_files_created(self, simple_chart, tmp_path):
        save(simple_chart, str(tmp_path / "out"), background=["light"])
        assert (tmp_path / "out_light.png").exists()
        assert (tmp_path / "out_light.svg").exists()

    def test_dark_files_created(self, simple_chart, tmp_path):
        save(simple_chart, str(tmp_path / "out"), background=["dark"])
        assert (tmp_path / "out_dark.png").exists()
        assert (tmp_path / "out_dark.svg").exists()

    def test_both_variants_by_default(self, simple_chart, tmp_path):
        save(simple_chart, str(tmp_path / "out"))
        for suffix in ["_light", "_dark"]:
            assert (tmp_path / f"out{suffix}.png").exists()
            assert (tmp_path / f"out{suffix}.svg").exists()

    def test_vega_spec_saved(self, simple_chart, tmp_path):
        save(simple_chart, str(tmp_path / "out"), background=["light"])
        assert (tmp_path / "out_vegalite.json").exists()

    def test_vega_spec_skipped(self, simple_chart, tmp_path):
        save(simple_chart, str(tmp_path / "out"), saveVegaSpec=False, background=["light"])
        assert not (tmp_path / "out_vegalite.json").exists()

    def test_layer_chart(self, tmp_path):
        df = pl.DataFrame({"x": ["A", "B"], "y": [1.0, 2.0]})
        base = alt.Chart(df).mark_point().encode(x="x:N", y="y:Q")
        layer = alt.layer(base)
        save(layer, str(tmp_path / "out"), background=["light"])
        assert (tmp_path / "out_light.png").exists()

    def test_callable_chart(self, tmp_path):
        df = pl.DataFrame({"x": ["A", "B"], "y": [1.0, 2.0]})
        save(
            lambda: alt.Chart(df).mark_point().encode(x="x:N", y="y:Q"),
            str(tmp_path / "out"),
            background=["light"],
        )
        assert (tmp_path / "out_light.png").exists()

    def test_darkmode_restored_after_full_save(self, simple_chart, tmp_path):
        theme(darkmode=False)
        save(simple_chart, str(tmp_path / "out"))
        assert alt.theme.options["darkmode"] is False

    def test_darkmode_restored_after_light_only(self, simple_chart, tmp_path):
        theme(darkmode=True)
        save(simple_chart, str(tmp_path / "out"), background=["light"])
        assert alt.theme.options["darkmode"] is True

    def test_invalid_background_raises(self, simple_chart, tmp_path):
        with pytest.raises(ValueError, match="background"):
            save(simple_chart, str(tmp_path / "out"), background=["invalid"])

    def test_no_theme_raises(self, simple_chart, tmp_path):
        alt.theme.options = {}
        try:
            with pytest.raises(RuntimeError, match="ds.theme"):
                save(simple_chart, str(tmp_path / "out"))
        finally:
            theme()

    def test_png_nonempty(self, simple_chart, tmp_path):
        save(simple_chart, str(tmp_path / "out"), background=["light"])
        assert (tmp_path / "out_light.png").stat().st_size > 100

    def test_description_in_spec(self, simple_chart, tmp_path):
        save(simple_chart, str(tmp_path / "out"), description="my chart", background=["light"])
        assert "my chart" in (tmp_path / "out_vegalite.json").read_text()


# ── _fix_tick_alignment() ─────────────────────────────────────────────────────


class TestFixTickAlignment:
    def test_point_scale_corrected(self, tmp_path):
        # 3 categories, W=200, point scale: step=W/n, position=round(step*(0.5+i))
        step = 200 / 3
        path = _write(tmp_path, "t.svg", _TICK_SVG.format(x0=33, x1=100, x2=167))
        _fix_tick_alignment(path, band_padding=0.1, chart_width=200)
        xs = _tick_xs(path)
        assert xs == pytest.approx([step * 0.5, step * 1.5, step * 2.5], abs=0.001)

    def test_band_inner_scale_corrected(self, tmp_path):
        # paddingInner=paddingOuter=band_padding, W=200: step=W/(n+bp)
        step = 200 / (3 + 0.1)
        x0, x1, x2 = int(step * 0.55), int(step * 1.55), int(step * 2.55)
        path = _write(tmp_path, "t.svg", _TICK_SVG.format(x0=x0, x1=x1, x2=x2))
        _fix_tick_alignment(path, band_padding=0.1, chart_width=200)
        xs = _tick_xs(path)
        assert xs == pytest.approx([step * 0.55, step * 1.55, step * 2.55], abs=0.001)

    def test_xoffset_scale_corrected(self, tmp_path):
        # paddingInner=0, paddingOuter=band_padding, W=200: step=W/(n+2*bp)
        step = 200 / (3 + 2 * 0.1)  # 62.5
        x0, x1, x2 = int(step * 0.6), int(step * 1.6), int(step * 2.6)
        path = _write(tmp_path, "t.svg", _TICK_SVG.format(x0=x0, x1=x1, x2=x2))
        _fix_tick_alignment(path, band_padding=0.1, chart_width=200)
        xs = _tick_xs(path)
        assert xs == pytest.approx([step * 0.6, step * 1.6, step * 2.6], abs=0.001)

    def test_no_match_leaves_file_unchanged(self, tmp_path):
        # Positions that don't match any formula → early return, file untouched
        content = _TICK_SVG.format(x0=25, x1=75, x2=125)
        path = _write(tmp_path, "t.svg", content)
        _fix_tick_alignment(path, band_padding=0.1, chart_width=200)
        assert Path(path).read_text() == content


# ── _fix_log_minor_ticks() ───────────────────────────────────────────────────


class TestFixLogMinorTicks:
    def test_y_log10_corrected(self, tmp_path):
        # 1 decade: major at y=0 (value=10) and y=100 (value=1), span=100
        # m=2 → integer 70, exact 69.897;  m=5 → integer 30, exact 30.103
        minor_ints = [5, 10, 22, 30, 40, 52, 70]
        path = _write(tmp_path, "t.svg", _y_tick_svg([0, 100], minor_ints))
        _fix_log_minor_ticks(path)
        ys = _y_minor_positions(path, minor_size=3)
        m2 = [y for y in ys if abs(y - 69.897) < 1.0]
        assert len(m2) == 1
        assert m2[0] == pytest.approx(100 - math.log10(2) * 100, abs=0.01)
        m5 = [y for y in ys if abs(y - 30.103) < 1.0]
        assert len(m5) == 1
        assert m5[0] == pytest.approx(100 - math.log10(5) * 100, abs=0.01)

    def test_y_uniform_corrected(self, tmp_path):
        # Power-scale: major at y=0 and y=97 (non-divisible span), 4 equal-space minors
        # Exact: k/5*97 for k=1..4 → 19.4, 38.8, 58.2, 77.6; ints → 19, 39, 58, 78
        path = _write(tmp_path, "t.svg", _y_tick_svg([0, 97], [19, 39, 58, 78]))
        _fix_log_minor_ticks(path)
        ys = _y_minor_positions(path, minor_size=3)
        assert sorted(ys) == pytest.approx([97 * k / 5 for k in range(1, 5)], abs=0.01)

    def test_y_single_tick_size_no_change(self, tmp_path):
        # Only one tick size → no minor ticks identified → file not rewritten
        content = _y_tick_svg([0, 100], [])
        path = _write(tmp_path, "t.svg", content)
        _fix_log_minor_ticks(path)
        assert Path(path).read_text() == content

    def test_x_log10_corrected(self, tmp_path):
        # 1 decade: major at x=0 and x=100, minor at integer-rounded log positions
        # m=2 → integer 30, exact 30.103;  m=5 → integer 70, exact 69.897
        minor_ints = [30, 48, 60, 70, 78, 85, 90, 95]
        path = _write(tmp_path, "t.svg", _x_tick_svg([0, 100], minor_ints))
        _fix_log_minor_ticks(path)
        xs = _x_minor_positions(path, minor_size=3)
        m2 = [x for x in xs if abs(x - 30.103) < 1.0]
        assert len(m2) == 1
        assert m2[0] == pytest.approx(math.log10(2) * 100, abs=0.01)

    def test_x_uniform_corrected(self, tmp_path):
        # Power-scale x-axis: major at x=0 and x=97, 4 equal-space minors
        path = _write(tmp_path, "t.svg", _x_tick_svg([0, 97], [19, 39, 58, 78]))
        _fix_log_minor_ticks(path)
        xs = _x_minor_positions(path, minor_size=3)
        assert sorted(xs) == pytest.approx([97 * k / 5 for k in range(1, 5)], abs=0.01)


# ── _layer_axes_to_front() ───────────────────────────────────────────────────


class TestLayerAxesToFront:
    def test_non_grid_axis_moved_to_end(self, tmp_path):
        svg = textwrap.dedent(f"""\
            <svg xmlns="{NS}">
              <g class="mark-group role-axis">
                <g><line x1="0" y1="0" x2="10" y2="0"/></g>
              </g>
              <g class="data-layer"/>
            </svg>
        """)
        path = _write(tmp_path, "t.svg", svg)
        _layer_axes_to_front(path)
        children = list(ET.parse(path).getroot())
        assert children[-1].get("class") == "mark-group role-axis"

    def test_grid_axis_stays_in_place(self, tmp_path):
        svg = textwrap.dedent(f"""\
            <svg xmlns="{NS}">
              <g class="mark-group role-axis">
                <g><g class="mark-rule role-axis-grid">
                  <line x1="0" y1="0" x2="100" y2="0"/>
                </g></g>
              </g>
              <g class="data-layer"/>
            </svg>
        """)
        path = _write(tmp_path, "t.svg", svg)
        _layer_axes_to_front(path)
        children = list(ET.parse(path).getroot())
        assert children[0].get("class") == "mark-group role-axis"

    def test_background_fill_and_stroke_split(self, tmp_path):
        # viewFill + closed: fill stays behind marks, stroke clone appended in front
        svg = textwrap.dedent(f"""\
            <svg xmlns="{NS}">
              <path class="background" fill="#eeeeee" stroke="black"/>
              <g class="data-layer"/>
            </svg>
        """)
        path = _write(tmp_path, "t.svg", svg)
        _layer_axes_to_front(path)
        root = ET.parse(path).getroot()
        paths = list(root.iter(f"{{{NS}}}path"))
        assert any(p.get("stroke") == "none" for p in paths)  # original → stroke removed
        assert any(p.get("fill") == "none" for p in paths)    # clone → fill=none


# ── _simplify_svg() ──────────────────────────────────────────────────────────


class TestSimplifySvg:
    def test_class_only_group_inlined(self, tmp_path):
        svg = textwrap.dedent(f"""\
            <svg xmlns="{NS}">
              <g class="wrapper">
                <rect x="0" y="0" width="10" height="10"/>
              </g>
            </svg>
        """)
        path = _write(tmp_path, "t.svg", svg)
        _simplify_svg(path)
        root = ET.parse(path).getroot()
        assert root.find(f"{{{NS}}}g") is None
        assert root.find(f"{{{NS}}}rect") is not None

    def test_transform_group_preserved(self, tmp_path):
        svg = textwrap.dedent(f"""\
            <svg xmlns="{NS}">
              <g transform="translate(10,20)">
                <rect x="0" y="0" width="10" height="10"/>
              </g>
            </svg>
        """)
        path = _write(tmp_path, "t.svg", svg)
        _simplify_svg(path)
        root = ET.parse(path).getroot()
        g = root.find(f"{{{NS}}}g")
        assert g is not None and g.get("transform") == "translate(10,20)"

    def test_noop_translate_inlined(self, tmp_path):
        svg = textwrap.dedent(f"""\
            <svg xmlns="{NS}">
              <g transform="translate(0,0)">
                <rect x="0" y="0" width="10" height="10"/>
              </g>
            </svg>
        """)
        path = _write(tmp_path, "t.svg", svg)
        _simplify_svg(path)
        root = ET.parse(path).getroot()
        assert root.find(f"{{{NS}}}g") is None
        assert root.find(f"{{{NS}}}rect") is not None

    def test_clip_path_group_preserved(self, tmp_path):
        svg = textwrap.dedent(f"""\
            <svg xmlns="{NS}">
              <g clip-path="url(#clip1)">
                <rect x="0" y="0" width="10" height="10"/>
              </g>
            </svg>
        """)
        path = _write(tmp_path, "t.svg", svg)
        _simplify_svg(path)
        root = ET.parse(path).getroot()
        assert root.find(f"{{{NS}}}g") is not None

    def test_nested_redundant_groups_flattened(self, tmp_path):
        svg = textwrap.dedent(f"""\
            <svg xmlns="{NS}">
              <g class="outer">
                <g class="inner">
                  <rect x="0" y="0" width="5" height="5"/>
                </g>
              </g>
            </svg>
        """)
        path = _write(tmp_path, "t.svg", svg)
        _simplify_svg(path)
        root = ET.parse(path).getroot()
        assert root.find(f"{{{NS}}}g") is None
        assert root.find(f"{{{NS}}}rect") is not None
