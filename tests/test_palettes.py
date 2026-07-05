import re
import struct

import pytest

from dysonsphere.palettes import categorical, colors, palette

HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")

SEQUENTIAL = [
    "blues",
    "greens",
    "reds",
    "greys",
    "yellows",
    "cyans",
    "magentas",
    "purples",
    "lavenders",
    "violets",
    "oranges",
    "browns",
    "pinks",
    "neongreens",
]
SEQUENTIAL_2 = [f"{n}2" for n in SEQUENTIAL]
SEQUENTIAL_3 = [f"{n}3" for n in SEQUENTIAL]
DIVERGING = [
    "redsblues",
    "purplesgreens",
    "greensblues",
    "redsblues2",
    "redsblues3",
    "greyspinks",
    "greyspinks2",
    "greyspinks3",
]


def test_all_hex_values_valid():
    for key, stops in colors.items():
        for h in stops:
            assert HEX_RE.match(h), f"{key}: {h!r} is not a valid hex color"


def test_sequential_have_12_stops():
    for name in SEQUENTIAL + SEQUENTIAL_2 + SEQUENTIAL_3:
        assert len(colors[name]) == 12, f"{name} should have 12 stops"


def test_diverging_have_13_stops():
    for name in DIVERGING:
        assert len(colors[name]) == 13, f"{name} should have 13 stops"


def test_greys3_is_achromatic():
    for h in colors["greys3"]:
        r, g, b = int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)
        assert max(r, g, b) - min(r, g, b) <= 2, f"greys3 stop {h!r} is not achromatic"


def test_palette_full_slice():
    result = palette("blues")
    assert result == colors["blues"]


def test_palette_n_sampling():
    result = palette("blues", n=4)
    assert len(result) == 4
    assert result[0] == colors["blues"][0]
    assert result[-1] == colors["blues"][-1]


def test_palette_n_one():
    result = palette("blues", n=1)
    assert result == [colors["blues"][0]]


def test_palette_reverse():
    result = palette("blues", reverse=True)
    assert result == list(reversed(colors["blues"]))


def test_palette_start_end():
    result = palette("blues", start=2, end=5)
    assert result == colors["blues"][2:6]


def test_palette_step():
    result = palette("blues", step=2)
    assert result == colors["blues"][::2]


def test_palette_unknown_key_raises():
    with pytest.raises(KeyError):
        palette("nonexistent_palette_xyz")


class TestCategorical:
    HUES = ("blues", "pinks", "yellows", "greens")

    def test_default_is_members_one(self):
        assert categorical() == categorical(1)

    def test_named_palette_matches_function(self):
        assert colors["categorical"] == categorical(1)

    @pytest.mark.parametrize("members,length", [(1, 12), (2, 8), (3, 12), (4, 16), (5, 20), (6, 24), (10, 40)])
    def test_lengths(self, members, length):
        assert len(categorical(members)) == length

    def test_flat_is_tier_major(self):
        # members=1 cycles the four hues at each tier: hue-inner, stop-outer.
        expected = [colors[h][s] for s in (1, 4, 7) for h in self.HUES]
        assert categorical(1) == expected

    def test_grouped_is_hue_major(self):
        # members>=2 groups by hue: stop-inner, hue-outer.
        expected = [colors[h][s] for h in self.HUES for s in (1, 4)]
        assert categorical(2) == expected

    def test_every_color_derived_from_base_hues(self):
        # Nothing is generated de novo - every color lives in one of the four base hues.
        pool = {hx for h in self.HUES for hx in colors[h]}
        for members in (1, 2, 3, 4, 5, 8, 10):
            assert set(categorical(members)) <= pool

    @pytest.mark.parametrize("members", [2, 3, 4])
    def test_classic_tier_stops_preserved(self, members):
        # members<=4 keep the exact (1, 4, 7, 10)[:members] tier stops - byte-identical
        # to prior versions and consistent with the flat palette's tiers.
        expected = [colors[h][s] for h in self.HUES for s in (1, 4, 7, 10)[:members]]
        assert categorical(members) == expected

    def test_five_members_spread_evenly(self):
        # beyond 4, stops spread evenly across the usable ramp [1, 10]
        expected = [colors[h][s] for h in self.HUES for s in (1, 3, 6, 8, 10)]
        assert categorical(5) == expected

    def test_stops_strictly_increasing_within_hue(self):
        # each hue block must climb monotonically in lightness stops (no duplicates)
        for members in range(2, 11):
            block = categorical(members)[:members]  # first hue block (blues)
            indices = [colors["blues"].index(c) for c in block]
            assert indices == sorted(set(indices)), f"members={members}: {indices}"

    def test_ten_is_the_cap(self):
        assert len(categorical(10)) == 40
        with pytest.raises(ValueError, match="distinct lightness stops"):
            categorical(11)

    @pytest.mark.parametrize("bad", [0, -1])
    def test_below_one_raises(self, bad):
        with pytest.raises(ValueError, match="at least 1"):
            categorical(bad)


class TestExportSwatches:
    def test_creates_jsx_file(self, tmp_path):
        from dysonsphere.palettes import export_swatches

        export_swatches(tmp_path)
        assert (tmp_path / "import_dysonsphere_palettes_to_illustrator.jsx").exists()

    def test_creates_ase_file(self, tmp_path):
        from dysonsphere.palettes import export_swatches

        export_swatches(tmp_path)
        assert (tmp_path / "dysonsphere.ase").exists()

    def test_jsx_contains_palette_names(self, tmp_path):
        from dysonsphere.palettes import export_swatches

        export_swatches(tmp_path)
        content = (tmp_path / "import_dysonsphere_palettes_to_illustrator.jsx").read_text()
        assert '"blues"' in content
        assert '"reds"' in content
        assert "colorGroup.name = paletteName;" in content
        assert 'swatch.name = paletteName + " - "' in content

    def test_ase_signature_and_structure(self, tmp_path):
        from dysonsphere.palettes import export_swatches

        export_swatches(tmp_path)
        data = (tmp_path / "dysonsphere.ase").read_bytes()
        assert data[:4] == b"ASEF"
        major, minor = struct.unpack(">HH", data[4:8])
        assert major == 1 and minor == 0

    def test_ase_contains_all_palettes(self, tmp_path):
        from dysonsphere.palettes import _write_ase, colors

        _write_ase(colors, tmp_path / "test.ase")
        raw = (tmp_path / "test.ase").read_bytes()
        for name in list(colors.keys())[:5]:
            assert name.encode("utf-16-be") in raw

    def test_ase_rgb_values_correct(self, tmp_path):
        from dysonsphere.palettes import _write_ase

        _write_ase({"test": ["#ff8040"]}, tmp_path / "t.ase")
        raw = (tmp_path / "t.ase").read_bytes()
        # find "RGB " marker and read the three floats after it
        idx = raw.index(b"RGB ")
        r, g, b = struct.unpack(">fff", raw[idx + 4 : idx + 16])
        assert r == pytest.approx(1.0, abs=0.001)
        assert g == pytest.approx(0x80 / 255, abs=0.001)
        assert b == pytest.approx(0x40 / 255, abs=0.001)

    def test_ase_block_count(self, tmp_path):
        from dysonsphere.palettes import _write_ase

        # 2 palettes × (group_start + group_end) + 3 color entries = 7 blocks
        _write_ase({"a": ["#ff0000", "#00ff00"], "b": ["#0000ff"]}, tmp_path / "t.ase")
        raw = (tmp_path / "t.ase").read_bytes()
        (block_count,) = struct.unpack(">I", raw[8:12])
        assert block_count == 7

    def test_find_illustrator_swatches_returns_none_when_absent(self, tmp_path, monkeypatch):
        from pathlib import Path

        from dysonsphere.palettes import _find_illustrator_swatches

        monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
        monkeypatch.delenv("APPDATA", raising=False)
        assert _find_illustrator_swatches() is None

    def test_defaults_to_cwd(self, tmp_path, monkeypatch):
        from dysonsphere.palettes import export_swatches

        monkeypatch.chdir(tmp_path)
        export_swatches()
        assert (tmp_path / "import_dysonsphere_palettes_to_illustrator.jsx").exists()
        assert (tmp_path / "dysonsphere.ase").exists()

    def test_palettes_subset(self, tmp_path, monkeypatch):
        from dysonsphere import palettes as p

        monkeypatch.setattr(p, "_find_illustrator_swatches", lambda: None)
        p.export_swatches(tmp_path, palettes=["reds", "blues"])
        content = (tmp_path / "import_dysonsphere_palettes_to_illustrator.jsx").read_text()
        assert '"reds"' in content and '"blues"' in content
        assert '"greys"' not in content  # not selected
        # ASE holds only the two groups: 2 * (group_start + group_end) + all their colors
        raw = (tmp_path / "dysonsphere.ase").read_bytes()
        (block_count,) = struct.unpack(">I", raw[8:12])
        assert block_count == 2 * 2 + len(p.colors["reds"]) + len(p.colors["blues"])

    def test_custom_name(self, tmp_path, monkeypatch):
        from dysonsphere import palettes as p

        monkeypatch.setattr(p, "_find_illustrator_swatches", lambda: None)
        p.export_swatches(tmp_path, palettes=["reds"], name="myproj")
        assert (tmp_path / "myproj.ase").exists()
        assert (tmp_path / "import_myproj_palettes_to_illustrator.jsx").exists()
        assert not (tmp_path / "dysonsphere.ase").exists()  # default name not used

    def test_unknown_palette_raises(self, tmp_path):
        from dysonsphere.palettes import export_swatches

        with pytest.raises(ValueError, match="unknown palette name"):
            export_swatches(tmp_path, palettes=["reds", "not_a_palette_xyz"])

    def test_empty_palettes_raises(self, tmp_path):
        from dysonsphere.palettes import export_swatches

        with pytest.raises(ValueError, match="non-empty list"):
            export_swatches(tmp_path, palettes=[])
