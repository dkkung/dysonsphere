"""TIFF-specific encoding, metadata, and dependency checks."""

import json
import sys

import altair as alt
import polars as pl
import pytest
import vl_convert as vlc
from PIL import Image, TiffImagePlugin, features

import dysonsphere as ds


@pytest.fixture(autouse=True)
def default_theme():
    ds.theme(width=60, height=45)


@pytest.fixture
def data():
    return pl.DataFrame({"group": ["A"] * 4 + ["B"] * 4, "value": [1.0, 2.0, 3.0, 4.0, 2.0, 3.0, 4.0, 5.0]})


@pytest.fixture
def chart(data):
    return alt.Chart(data).mark_point().encode(x="group:N", y="value:Q")


@pytest.mark.parametrize(
    ("background", "transparent", "custom_background"),
    [("light", False, "#cfe3f7"), ("dark", True, None)],
)
def test_tiff_pixels_and_tags(chart, tmp_path, background, transparent, custom_background):
    if custom_background is not None:
        chart = chart.properties(background=custom_background)
    ds.save(chart, tmp_path / "figure", format=["png", "tiff"], background=background, transparent=transparent, ppi=600)
    mode = "RGBA" if transparent else "RGB"
    with Image.open(tmp_path / "figure.png") as png, Image.open(tmp_path / "figure.tiff") as tiff:
        assert isinstance(tiff, TiffImagePlugin.TiffImageFile)
        assert tiff.mode == mode
        assert tiff.size == png.size
        assert tiff.tobytes() == png.convert(mode).tobytes()
        assert tiff.tag_v2[259] == 5  # LZW
        assert float(tiff.tag_v2[282]) == 600
        assert float(tiff.tag_v2[283]) == 600
        assert tiff.tag_v2[296] == 2  # inches
        corner = tiff.getpixel((0, 0))
        assert isinstance(corner, tuple)
        if transparent:
            assert corner[3] == 0
        else:
            assert png.getchannel("A").getextrema() == (255, 255)
            assert corner == (207, 227, 247)


def test_tiff_only_preserves_existing_unrequested_files(chart, tmp_path):
    for ext in ("svg", "png", "json"):
        (tmp_path / f"figure.{ext}").write_text("keep this file")
    ds.save(chart, tmp_path / "figure", format="tiff")
    assert (tmp_path / "figure.tiff").exists()
    for ext in ("svg", "png", "json"):
        assert (tmp_path / f"figure.{ext}").read_text() == "keep this file"


def test_theme_can_select_tiff_without_intermediate_outputs(chart, tmp_path):
    ds.theme(saveFormat="tiff")
    ds.save(chart, tmp_path / "figure")
    assert {p.suffix for p in tmp_path.iterdir()} == {".tiff"}


def test_png_and_tiff_share_one_rasterization_per_background(chart, tmp_path, monkeypatch):
    rasterized = []
    original = vlc.svg_to_png

    def rasterize(*args, **kwargs):
        rasterized.append(kwargs["ppi"])
        return original(*args, **kwargs)

    monkeypatch.setattr(vlc, "svg_to_png", rasterize)
    ds.save(chart, tmp_path / "figure", format=["png", "tiff"], background=["light", "dark"])
    assert rasterized == [1200, 1200]
    assert {p.name for p in tmp_path.iterdir()} == {
        "figure_light.png",
        "figure_light.tiff",
        "figure_dark.png",
        "figure_dark.tiff",
    }


@pytest.mark.parametrize(
    ("save_metadata", "embed_report", "description"),
    [(True, True, "Sample α\nSecond line 😀"), (True, False, None), (False, True, ""), (False, False, None)],
)
def test_tiff_metadata_flags(data, chart, tmp_path, save_metadata, embed_report, description):
    chart += ds.stats.comparisons(data, "group", "value", [("A", "B")], categories=["A", "B"], pvalues=[0.0123456789])
    ds.save(
        chart,
        tmp_path / "figure",
        format=["tiff", "json"],
        description=description,
        saveMetadata=save_metadata,
        embedReport=embed_report,
    )
    with Image.open(tmp_path / "figure.tiff") as image:
        assert isinstance(image, TiffImagePlugin.TiffImageFile)
        text = image.tag_v2.get(270)
        if save_metadata or description is not None:
            assert isinstance(text, str)
            assert text.isascii()
            assert image.tag_v2.tagtype[270] == 2  # TIFF ASCII field
            envelope = json.loads(text)
            assert envelope.get("description") == description
        else:
            assert text is None
    if save_metadata:
        block = ds.metadata.read(tmp_path / "figure.tiff", what="metadata")
        assert block == ds.metadata.read(tmp_path / "figure.json", what="metadata")
        assert ("report" in block) == embed_report
        assert block["statistics"][0]["comparisons"]["pairs"][0]["pvalue"] == 0.0123456789
        if description is not None:
            assert block["description"] == description
        verified = ds.metadata.verify(tmp_path / "figure.tiff", data=data)
        assert verified.dataMatches is True
        assert verified.specValid is None
    else:
        with pytest.raises(ValueError, match="no dysonsphere metadata"):
            ds.metadata.read(tmp_path / "figure.tiff", what="metadata")
        if description is not None:
            assert envelope == {"description": description}


@pytest.mark.parametrize("transparent", [False, True])
def test_tiff_reproducible(chart, tmp_path, monkeypatch, transparent):
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")
    for name in ("one", "two"):
        ds.save(chart, tmp_path / name, format="tiff", transparent=transparent, description="Pinned α")
    assert (tmp_path / "one.tiff").read_bytes() == (tmp_path / "two.tiff").read_bytes()


def test_reader_accepts_tif_extension(chart, tmp_path):
    ds.save(chart, tmp_path / "figure", format="tiff", description="TIFF caption")
    (tmp_path / "figure.tiff").rename(tmp_path / "figure.tif")
    assert ds.metadata.read(tmp_path / "figure.tif", what="metadata")["provenance"]
    assert ds.metadata.read(tmp_path / "figure.tif", what="description") == "TIFF caption"


def test_reader_rejects_tiff_without_dysonsphere_metadata(tmp_path):
    Image.new("RGB", (2, 2)).save(tmp_path / "foreign.tiff", tiffinfo={270: "plain description"})
    with pytest.raises(ValueError, match="no dysonsphere metadata"):
        ds.metadata.read(tmp_path / "foreign.tiff", what="metadata")


@pytest.mark.parametrize("missing", ["Pillow", "libtiff"])
def test_tiff_dependencies_checked_before_any_output(chart, tmp_path, monkeypatch, missing):
    if missing == "Pillow":
        monkeypatch.setitem(sys.modules, "PIL", None)
    else:
        monkeypatch.setattr(features, "check", lambda feature: False)
    with pytest.raises(RuntimeError, match=missing):
        ds.save(chart, tmp_path / "figure", format=["json", "tiff"])
    assert not list(tmp_path.iterdir())


def test_tiff_failure_restores_theme_and_leaves_no_svg(chart, tmp_path, monkeypatch):
    ds.theme(darkmode=True, transparent=False)

    def fail(*args, **kwargs):
        raise OSError("TIFF write failed")

    monkeypatch.setattr(Image.Image, "save", fail)
    with pytest.raises(OSError, match="TIFF write failed"):
        ds.save(chart, tmp_path / "figure", format="tiff", background="light", transparent=True)
    assert alt.theme.options["darkmode"] is True
    assert alt.theme.options["transparent"] is False
    assert not list(tmp_path.iterdir())


def test_rgb_tiff_does_not_silently_drop_alpha(chart, tmp_path):
    chart = chart.properties(background="transparent")
    with pytest.raises(ValueError, match="opaque rendered background"):
        ds.save(chart, tmp_path / "figure", format="tiff", transparent=False)
    assert not list(tmp_path.iterdir())
