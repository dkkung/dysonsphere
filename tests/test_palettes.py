import re

import pytest

from dysonsphere.palettes import colors, palette

HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")

SEQUENTIAL = ["blues", "greens", "reds", "greys", "yellows", "cyans", "magentas",
              "purples", "lavenders", "violets", "oranges", "browns", "pinks", "neongreens"]
SEQUENTIAL_2 = [f"{n}2" for n in SEQUENTIAL]
SEQUENTIAL_3 = [f"{n}3" for n in SEQUENTIAL]
DIVERGING = ["redsblues", "purplesgreens", "greensblues", "redsblues2", "redsblues3",
             "greyspinks", "greyspinks2", "greyspinks3"]


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


class TestExportSwatches:
    def test_creates_jsx_file(self, tmp_path):
        from dysonsphere.palettes import export_swatches
        export_swatches(tmp_path)
        assert (tmp_path / "import_dysonsphere_palettes_to_illustrator.jsx").exists()

    def test_jsx_contains_palette_names(self, tmp_path):
        from dysonsphere.palettes import export_swatches
        export_swatches(tmp_path)
        content = (tmp_path / "import_dysonsphere_palettes_to_illustrator.jsx").read_text()
        assert '"blues"' in content
        assert '"reds"' in content

    def test_defaults_to_cwd(self, tmp_path, monkeypatch):
        from dysonsphere.palettes import export_swatches
        monkeypatch.chdir(tmp_path)
        export_swatches()
        assert (tmp_path / "import_dysonsphere_palettes_to_illustrator.jsx").exists()
