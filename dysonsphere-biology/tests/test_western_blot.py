"""Tests for dysonsphere_biology.western_blot - image loading, stacking, and the condition table.

Uses in-memory PIL images (no fixture files). Covers the entry-point resolution, the stroke /
padding controls, multi-strip stacking, and that the generated image sidecar is tagged internal.
"""

import base64
import io

import altair as alt
import dysonsphere_biology as dsbio
import pytest
from PIL import Image

import dysonsphere as ds
from dysonsphere.theme import _opt


def _img(w=60, h=12, color="white"):
    return Image.new("RGB", (w, h), color)


def _image_units(spec):
    """Every unit spec carrying an image mark, anywhere in the (possibly nested) tree."""
    out = []

    def walk(s):
        if not isinstance(s, dict):
            return
        mark = s.get("mark")
        if (isinstance(mark, dict) and mark.get("type") == "image") or mark == "image":
            out.append(s)
        for key in ("vconcat", "hconcat", "concat", "layer"):
            for child in s.get(key, []):
                walk(child)

    walk(spec)
    return out


def test_entry_point_registered():
    assert "biology" in ds.extensions()
    assert ds.biology.western_blot is dsbio.western_blot


def test_returns_vconcat():
    fig = ds.biology.western_blot(_img(), {"A": [True, False]}, categories=["x", "y"])
    assert isinstance(fig, alt.VConcatChart)


def test_single_vs_multiple_images():
    one = ds.biology.western_blot(_img(), categories=["x", "y"]).to_dict()
    three = ds.biology.western_blot([_img(), _img(), _img()], categories=["x", "y"]).to_dict()
    assert len(_image_units(one)) == 1
    assert len(_image_units(three)) == 3


def test_aspect_preserved():
    # a 60x12 image at chartWidth W renders at height W*12/60 = W/5
    ds.theme(chartWidth=200)
    unit = _image_units(ds.biology.western_blot(_img(60, 12), categories=["x", "y"]).to_dict())[0]
    assert unit["height"] == pytest.approx(200 * 12 / 60)
    assert unit["width"] == 200


class TestStroke:
    def _view(self, **kw):
        unit = _image_units(ds.biology.western_blot(_img(), categories=["x", "y"], **kw).to_dict())[0]
        return unit["view"]

    def test_default_border(self):
        view = self._view()  # stroke=True default
        assert view["stroke"] == "black"
        assert view["strokeWidth"] == _opt("markStrokeWidth")

    def test_stroke_false_no_border(self):
        assert self._view(stroke=False).get("stroke") is None

    def test_stroke_float_width(self):
        assert self._view(stroke=1.5)["strokeWidth"] == 1.5

    def test_darkmode_border_is_white(self):
        ds.theme(darkmode=True)  # resolved at build time
        assert self._view()["stroke"] == "white"


def test_padding_sets_stack_spacing():
    spec = ds.biology.western_blot([_img(), _img()], categories=["x", "y"], padding=5).to_dict()
    stack = spec["vconcat"][0]  # the image stack is the first child; the table is second
    assert stack["spacing"] == 5


def test_empty_images_raises():
    with pytest.raises(ValueError, match="at least one image"):
        ds.biology.western_blot([], categories=["x", "y"])


def test_accepts_data_uri():
    buf = io.BytesIO()
    _img().save(buf, "PNG")
    uri = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    assert len(_image_units(ds.biology.western_blot(uri, categories=["x", "y"]).to_dict())) == 1


def test_image_sidecar_tagged_internal():
    # The image URI frame is generated, not user data - it must carry the internal sentinel so
    # read(what="data") never returns it as a phantom user frame.
    spec = ds.biology.western_blot(_img(), categories=["x", "y"]).to_dict()
    data = _image_units(spec)[0]["data"]
    rows = data["values"] if "values" in data else spec["datasets"][data["name"]]
    assert all("__dysonsphere__" in row for row in rows)


def test_tagged_for_provenance():
    # ext.tag_extension marks the figure so save() records dysonsphere-biology's version.
    from dysonsphere.discovery import _used_extensions

    spec = ds.biology.western_blot(_img(), categories=["x", "y"]).to_dict()
    assert "biology" in _used_extensions(spec)
