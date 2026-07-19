import math
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
    # The two qualitative palettes and their base hues, keyed by the `palette=` argument.
    HUES = {
        "ds_cat_1": ("cat_teals", "cat_blues", "cat_purples", "cat_greens", "cat_golds"),
        "ds_cat_2": ("blues", "pinks", "yellows", "greens"),
    }
    PALETTES = ["ds_cat_1", "ds_cat_2"]

    def test_default_is_members_one(self):
        assert categorical() == categorical(1)

    def test_default_palette_is_ds_cat_1(self):
        assert categorical() == categorical(1, palette="ds_cat_1")

    @pytest.mark.parametrize("name", PALETTES)
    def test_named_palette_matches_function(self, name):
        assert colors[name] == categorical(1, palette=name)

    @pytest.mark.parametrize("name", PALETTES)
    @pytest.mark.parametrize("members", [1, 2, 3, 4, 5, 6, 10])
    def test_lengths(self, name, members):
        # flat (members=1) = 3 stops per hue; grouped = `members` stops per hue.
        expected = len(self.HUES[name]) * (3 if members == 1 else members)
        assert len(categorical(members, palette=name)) == expected

    @pytest.mark.parametrize("name", PALETTES)
    def test_flat_is_tier_major(self, name):
        # members=1 cycles the hues at each tier: hue-inner, stop-outer.
        expected = [colors[h][s] for s in (1, 4, 7) for h in self.HUES[name]]
        assert categorical(1, palette=name) == expected

    @pytest.mark.parametrize("name", PALETTES)
    def test_grouped_is_hue_major(self, name):
        # members>=2 groups by hue: stop-inner, hue-outer.
        expected = [colors[h][s] for h in self.HUES[name] for s in (1, 4)]
        assert categorical(2, palette=name) == expected

    @pytest.mark.parametrize("name", PALETTES)
    def test_every_color_derived_from_base_hues(self, name):
        # Nothing is generated de novo - every color lives in one of the base hues.
        pool = {hx for h in self.HUES[name] for hx in colors[h]}
        for members in (1, 2, 3, 4, 5, 8, 10):
            assert set(categorical(members, palette=name)) <= pool

    @pytest.mark.parametrize("name", PALETTES)
    @pytest.mark.parametrize("members", [2, 3, 4])
    def test_classic_tier_stops_preserved(self, name, members):
        # members<=4 keep the exact (1, 4, 7, 10)[:members] tier stops - byte-identical
        # to prior versions and consistent with the flat palette's tiers.
        expected = [colors[h][s] for h in self.HUES[name] for s in (1, 4, 7, 10)[:members]]
        assert categorical(members, palette=name) == expected

    @pytest.mark.parametrize("name", PALETTES)
    def test_five_members_spread_evenly(self, name):
        # beyond 4, stops spread evenly across the usable ramp [1, 10]
        expected = [colors[h][s] for h in self.HUES[name] for s in (1, 3, 6, 8, 10)]
        assert categorical(5, palette=name) == expected

    @pytest.mark.parametrize("name", PALETTES)
    def test_stops_strictly_increasing_within_hue(self, name):
        # each hue block must climb monotonically in lightness stops (no duplicates)
        first_hue = self.HUES[name][0]
        for members in range(2, 11):
            block = categorical(members, palette=name)[:members]  # first hue block
            indices = [colors[first_hue].index(c) for c in block]
            assert indices == sorted(set(indices)), f"{name} members={members}: {indices}"

    @pytest.mark.parametrize("name", PALETTES)
    def test_ten_is_the_cap(self, name):
        assert len(categorical(10, palette=name)) == len(self.HUES[name]) * 10
        with pytest.raises(ValueError, match="distinct lightness stops"):
            categorical(11, palette=name)

    @pytest.mark.parametrize("bad", [0, -1])
    def test_below_one_raises(self, bad):
        with pytest.raises(ValueError, match="at least 1"):
            categorical(bad)

    def test_unknown_palette_raises(self):
        with pytest.raises(ValueError, match="unknown palette"):
            categorical(palette="nope")


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


# ── perceptual quality invariants ────────────────────────────────────────────
# Every dysonsphere-NATIVE palette (mpl_/cmocean_ ship as-is and are exempt) must uphold the
# perceptual guarantees the build recipes promise. These are safety nets against hand-edits:
# the bounds are empirical (worst native adjacent-ΔE ratio is bluelagoon at 1.29; viridis-grade
# is ~1.05), so a failure means a palette regressed, not that the bound is tight.


def _srgb_linear(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _srgb_gamma(c: float) -> float:
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def _hex_to_oklab(hx: str) -> tuple[float, float, float]:
    r, g, b = (_srgb_linear(int(hx[i : i + 2], 16) / 255) for i in (1, 3, 5))
    lv = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l_, m_, s_ = lv ** (1 / 3), m ** (1 / 3), s ** (1 / 3)
    return (
        0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
        1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
        0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_,
    )


# Machado et al. 2009 severity-1.0 dichromacy matrices, applied in linear sRGB.
_DEUTERANOPIA = ((0.367322, 0.860646, -0.227968), (0.280085, 0.672501, 0.047413), (-0.011820, 0.042940, 0.968881))
_PROTANOPIA = ((0.152286, 1.052583, -0.204868), (0.114503, 0.786281, 0.099216), (-0.003882, 0.048116, 0.955765))


def _simulate_cvd(hx: str, matrix) -> str:
    r, g, b = (_srgb_linear(int(hx[i : i + 2], 16) / 255) for i in (1, 3, 5))
    out = (max(0.0, min(1.0, m0 * r + m1 * g + m2 * b)) for m0, m1, m2 in matrix)
    return "#" + "".join(f"{round(_srgb_gamma(c) * 255):02X}" for c in out)


def _monotonic(values: list[float]) -> bool:
    ascending = all(values[i + 1] > values[i] for i in range(len(values) - 1))
    descending = all(values[i + 1] < values[i] for i in range(len(values) - 1))
    return ascending or descending


def _adjacent_delta_e(pal: list[str]) -> list[float]:
    labs = [_hex_to_oklab(h) for h in pal]
    return [math.dist(labs[i], labs[i + 1]) for i in range(len(labs) - 1)]


def _native(name: str) -> bool:
    return not name.startswith(("mpl_", "cmocean_"))


# ds_cat_2 carries 12 stops but is a QUALITATIVE hue-cycling palette, not a ramp (ds_cat_1 has 15,
# so it is excluded by the stop count). The cat_* base ramps ARE genuine 12-stop sequential ramps.
_QUALITATIVE = {"ds_cat_1", "ds_cat_2"}
NATIVE_SEQUENTIAL = sorted(n for n, c in colors.items() if _native(n) and len(c) == 12 and n not in _QUALITATIVE)
NATIVE_DIVERGING = sorted(n for n, c in colors.items() if _native(n) and len(c) == 13)


class TestPaletteQuality:
    """One test per invariant (not per palette); a failure message lists every offender by
    name. Only the dichromacy axis stays parametrized, so a CVD failure still says WHICH
    colorblindness type broke."""

    def test_sequential_lightness_monotonic(self):
        bad = [n for n in NATIVE_SEQUENTIAL if not _monotonic([_hex_to_oklab(h)[0] for h in colors[n]])]
        assert not bad, f"non-monotonic Oklab lightness (greyscale ordering breaks): {bad}"

    def test_sequential_step_uniformity(self):
        bad = []
        for n in NATIVE_SEQUENTIAL:
            dEs = _adjacent_delta_e(colors[n])
            ratio = max(dEs) / min(dEs)
            if ratio > 1.5:
                bad.append(f"{n} ({ratio:.2f})")
        assert not bad, f"adjacent-ΔE ratio exceeds 1.5 (uneven perceptual steps): {bad}"

    @pytest.mark.parametrize("matrix", [_DEUTERANOPIA, _PROTANOPIA], ids=["deuteranopia", "protanopia"])
    def test_sequential_cvd_monotonic(self, matrix):
        bad = [
            n
            for n in NATIVE_SEQUENTIAL
            if not _monotonic([_hex_to_oklab(_simulate_cvd(h, matrix))[0] for h in colors[n]])
        ]
        assert not bad, f"lightness not monotonic under this simulated dichromacy: {bad}"

    def test_diverging_v_shape(self):
        bad = []
        for n in NATIVE_DIVERGING:
            Ls = [_hex_to_oklab(h)[0] for h in colors[n]]
            if not (max(Ls) == Ls[6] and _monotonic(Ls[:7]) and _monotonic(Ls[6:])):
                bad.append(n)
        assert not bad, f"not V-shaped around the stop-6 pivot: {bad}"
