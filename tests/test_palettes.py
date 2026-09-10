import hashlib
import importlib.util
import json
import math
import re
import struct

import pytest

from dysonsphere.palettes import (
    _CMOCEAN_PALETTES,
    _MATPLOTLIB_PALETTES,
    _PORTED_PALETTE_NAMES,
    categorical,
    colors,
    palette,
)

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


def test_palette_n_zero_is_empty():
    assert palette("blues", n=0) == []


def test_palette_n_oversampling_keeps_inclusive_endpoints():
    result = palette("blues", n=20, start=2, end=5, step=99)
    assert len(result) == 20
    assert result[0] == colors["blues"][2]
    assert result[-1] == colors["blues"][5]


@pytest.mark.parametrize("n", [-1, 1.0, True, "4"])
def test_palette_n_requires_a_nonnegative_integer(n):
    with pytest.raises(ValueError, match="nonnegative integer"):
        palette("blues", n=n)


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
        "cat2": ("cat2_teals", "cat2_blues", "cat2_purples", "cat2_greens", "cat2_golds"),
        "cat3": ("blues", "pinks", "yellows", "greens"),
    }
    PALETTES = ["cat2", "cat3"]

    def test_default_is_members_one(self):
        assert categorical() == categorical(1)

    def test_default_palette_is_cat1(self):
        assert categorical() == categorical(1, palette="cat1")

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


class TestCat1:
    """cat1 uses hand-tuned stops rather than the canonical (1, 4, 7), and gives each
    hue its own usable window in grouped mode - so it needs its own assertions."""

    HUES = ("greys", "cat1_blues", "cat1_greens", "cat1_purples", "cat1_teals")
    # The designed palette: tier-major over grey/blue/green/purple/teal, so the first five
    # categories are five distinct hues and the sixth restarts the cycle one tier down.
    EXPECTED = [
        "#B2B2B2",  # greys[3]        light grey
        "#4A7CD3",  # cat1_blues[5]   blue (the hero)
        "#008542",  # cat1_greens[6]  green
        "#664CAF",  # cat1_purples[6] violet
        "#509F98",  # cat1_teals[4]   teal
        "#636363",  # greys[7]        dark grey
        "#284F93",  # cat1_blues[8]   cobalt
        "#005226",  # cat1_greens[9]  dark green
        "#382864",  # cat1_purples[9] indigo
        "#285753",  # cat1_teals[8]   dark teal
    ]

    def test_flat_palette_is_the_designed_order(self):
        assert colors["cat1"] == self.EXPECTED

    def test_named_palette_matches_function(self):
        assert colors["cat1"] == categorical(1, palette="cat1")

    @pytest.mark.parametrize("cvd", ["deuteranopia", "protanopia"])
    @pytest.mark.parametrize("n", [4, 5, 6])
    def test_cvd_separation_at_common_category_counts(self, cvd, n):
        # cat1_purples stops 3-5 sit at blue's lightness and collapse against it under
        # dichromacy; 0.07 is the palette's own worst pair. Grouped mode caps at 6.
        import itertools

        matrix = _DEUTERANOPIA if cvd == "deuteranopia" else _PROTANOPIA
        labs = [_hex_to_oklab(_simulate_cvd(c, matrix)) for c in colors["cat1"][:n]]
        worst = min(math.dist(labs[i], labs[j]) for i, j in itertools.combinations(range(n), 2))
        assert worst >= 0.07

    def test_every_color_derived_from_base_hues(self):
        # Nothing de novo - every entry is a stop on one of the base ramps.
        pool = {hx for h in self.HUES for hx in colors[h]}
        assert set(colors["cat1"]) <= pool

    @pytest.mark.parametrize("members", [2, 3, 4, 5, 6])
    def test_grouped_lengths_and_distinctness(self, members):
        got = categorical(members, palette="cat1")
        assert len(got) == len(self.HUES) * members
        assert len(set(got)) == len(got)

    def test_grouped_is_hue_major(self):
        # Each family contributes a consecutive block spanning its own window.
        got = categorical(2, palette="cat1")
        assert got[:2] == [colors["greys"][3], colors["greys"][10]]
        assert got[2:4] == [colors["cat1_blues"][1], colors["cat1_blues"][11]]

    def test_members_above_ceiling_raises_naming_the_family(self):
        # cat1_greens has the narrowest window (stops 6-11), so it binds at 6.
        with pytest.raises(ValueError, match="cat1_greens"):
            categorical(7, palette="cat1")

    def test_other_palettes_unaffected(self):
        # The per-family window path must not touch the canonical-stop palettes.
        cat1 = ("cat2_teals", "cat2_blues", "cat2_purples", "cat2_greens", "cat2_golds")
        assert categorical(1, palette="cat2") == [colors[h][s] for s in (1, 4, 7) for h in cat1]
        assert categorical(2, palette="cat3") == [
            colors[h][s] for h in ("blues", "pinks", "yellows", "greens") for s in (1, 4)
        ]


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
# Every dysonsphere-native palette (ported palettes ship as-is and are exempt) must uphold the
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
    return name not in _PORTED_PALETTE_NAMES


# cat3 carries 12 stops but is a QUALITATIVE hue-cycling palette, not a ramp (cat2 has 15,
# so it is excluded by the stop count). The cat_* base ramps ARE genuine 12-stop sequential ramps.
_QUALITATIVE = {"cat1", "cat2", "cat3"}
NATIVE_SEQUENTIAL = sorted(n for n, c in colors.items() if _native(n) and len(c) == 12 and n not in _QUALITATIVE)
NATIVE_DIVERGING = sorted(n for n, c in colors.items() if _native(n) and len(c) == 13)


def _digest(value) -> str:
    return hashlib.sha256(json.dumps(value, separators=(",", ":")).encode()).hexdigest()


def test_registry_name_migration_exact_parity():
    assert len(colors) == 315
    assert _digest(colors) == "4d46342974fc6d67e2dcdfe12da73c0afc48ed37b29f107c6fac3c4c3384c671"
    for removed in (
        "cmocean_gray",
        "mpl_viridis",
        "ds_cat_1",
        "ds_cat_2",
        "ds_cat_3",
        "cat3_blues",
        "cat3_greens",
        "cat3_purples",
        "cat3_teals",
    ):
        assert removed not in colors
    assert {"gray", "greys", "Greys", "greenblue", "GnBu", "yellowgreenblue", "YlGnBu"} <= colors.keys()
    assert colors["greenblue"] != colors["GnBu"]
    assert colors["yellowgreenblue"] != colors["YlGnBu"]
    assert _digest(colors["greenblue"]) == "f2544b8324a44a221971ea1f6f0905d82c054e66e38e2f04c121519b59b6af0f"
    assert _digest(colors["GnBu"]) == "679ef045c95c5231a041d43e0ff65f004fe7e9e78c0becd84a82f723b2906844"
    assert _digest(colors["yellowgreenblue"]) == "daf85baa7248b7190d149303992529803b98f4bc3d0568fc6425d0294faf6a57"
    assert _digest(colors["YlGnBu"]) == "baa0bb23103c336626367fee486e9610bea3978a7cc9411f157b2e0034c28974"
    assert len(_PORTED_PALETTE_NAMES) == 104
    assert _PORTED_PALETTE_NAMES <= colors.keys()


def test_current_registry_reconstructs_prechange_ordered_baseline():
    # The inverse comparison intentionally excludes the approved palette removals; its
    # digest still guards every surviving pre-change palette and its order.
    removed_neongreens = {
        "neongreens",
        "neongreens2",
        "neongreens3",
    } | {
        f"{arm}neongreens{suffix}"
        for arm in ("browns", "greys", "lavenders", "magentas", "oranges", "pinks", "purples", "reds")
        for suffix in ("", "2", "3")
    }
    assert len(removed_neongreens) == 27
    removed_palettes = removed_neongreens | {"bluerlagoon", "bluestlagoon"}
    assert len(removed_palettes) == 29
    assert not removed_palettes & colors.keys()
    intentional_discrete_changes = {
        "Accent",
        "Dark2",
        "Paired",
        "Pastel1",
        "Pastel2",
        "Set1",
        "Set2",
        "Set3",
        "tab10",
        "tab20",
        "tab20b",
        "tab20c",
    }
    native_old_names = {
        "greenblue": "GnBu",
        "yellowgreenblue": "YlGnBu",
        "brgn": "BrGn",
        "brte": "BrTe",
        "gdbu": "GdBu",
        "mggn": "MgGn",
        "pkte": "PkTe",
        "pugn": "PuGn",
        "rdbu": "RdBu",
        "rdylbu": "RdYlBu",
        "cat1": "ds_cat_3",
        "cat2": "ds_cat_1",
        "cat3": "ds_cat_2",
        "cat1_blues": "cat3_blues",
        "cat1_greens": "cat3_greens",
        "cat1_purples": "cat3_purples",
        "cat1_teals": "cat3_teals",
        "cat2_blues": "cat_blues",
        "cat2_golds": "cat_golds",
        "cat2_greens": "cat_greens",
        "cat2_purples": "cat_purples",
        "cat2_teals": "cat_teals",
        "div1": "ds_div_3",
        "div2": "ds_div_1",
        "greyslavenders": "greyslavender",
    }
    old_gray = [
        "#000000",
        "#020202",
        "#121212",
        "#272727",
        "#3E3D3D",
        "#575656",
        "#70706F",
        "#8A8A89",
        "#A6A6A5",
        "#C3C2C1",
        "#E0E0DF",
        "#FEFEFD",
    ]
    reconstructed = {}
    for name, stops in colors.items():
        if name in intentional_discrete_changes:
            continue
        if name == "haline":
            reconstructed["cmocean_gray"] = old_gray
        if name in _MATPLOTLIB_PALETTES:
            old_name = f"mpl_{name}"
        elif name in _CMOCEAN_PALETTES:
            old_name = f"cmocean_{name}"
        else:
            old_name = native_old_names.get(name, name)
        reconstructed[old_name] = stops
    assert len(reconstructed) == 304
    assert _digest(reconstructed) == "65a0b45c5f4fb9f96d5e610fd3fd977659a5f9c476766629232109eaa89d871c"


def test_authoring_recipe_omits_unshipped_diverging_candidates():
    spec = importlib.util.spec_from_file_location("print_palettes", "scripts/print_palettes.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    names = []
    setattr(module, "_print_palette", lambda name, _hexes: names.append(name))
    module.main()
    assert len(module.DIVERG_SEQ2_PAIRS) == 43
    assert len(module.DIVERG_SEQ3_PAIRS) == 43
    expected_pairs = {arm1.removesuffix("2") + arm2 for arm1, arm2 in module.DIVERG_SEQ2_PAIRS} | {
        arm1.removesuffix("3") + arm2 for arm1, arm2 in module.DIVERG_SEQ3_PAIRS
    }
    assert expected_pairs <= colors.keys()
    assert "greyslavenders2" in names
    assert "greyslavenders3" in names
    assert {"greenblue", "yellowgreenblue", "lagoon"} <= set(names)
    assert {"gnbu", "ylgnbu", "bluerlagoon", "bluestlagoon"}.isdisjoint(names)
    assert {"bluestgrotto", "bluergrotto", "bluegrotto"}.isdisjoint(names)
    assert "ylpu" not in names
    assert not any(name.endswith("_sat") for name in names)
    assert not any("neongreen" in name for name in names)


def test_neongreens_family_is_fully_removed_without_affecting_green_families():
    assert not any("neongreen" in name for name in colors)
    assert {"greens", "greens2", "greens3", "cat1_greens", "cat2_greens"} <= colors.keys()


def test_lagoon_cleanup_retains_only_authorized_variants():
    assert {"lagoon", "bluelagoon"} <= colors.keys()
    assert {"bluerlagoon", "bluestlagoon", "gnbu", "ylgnbu"}.isdisjoint(colors)


def test_matplotlib_discrete_palettes_are_complete_upstream_lists():
    expected_lengths = {
        "Accent": 8,
        "Dark2": 8,
        "Paired": 12,
        "Pastel1": 9,
        "Pastel2": 8,
        "Set1": 9,
        "Set2": 8,
        "Set3": 12,
        "tab10": 10,
        "tab20": 20,
        "tab20b": 20,
        "tab20c": 20,
    }
    actual = {name: colors[name] for name in expected_lengths}
    assert {name: len(stops) for name, stops in actual.items()} == expected_lengths
    assert _digest(actual) == "a81f529d37455e190b49ca2c469dde357cb0f06e77eed481be1a925cc6e36ff5"


_CATEGORICAL_HASHES = {
    "cat1": [
        "33e77658a0d4fafeddbee81f2199c5288adf5416810acd328adde4efc1aa99d1",
        "31f2d2bc51a159aa316d0681b89e81bb39ce6a262d4b9f1a50623cc51f39b6d7",
        "6baff5757f6c7a78b308d78ba8e8e11e5ffced786cc4a3d50166758583bb38e1",
        "3f5bf22eac774e394a66d45fcb85a953f3cdb13cf01b25b9b284ab7553a7f36d",
        "435ce8acd1c7f477b9f84ad6098305cf70a7791c75f008eb4b26d664f5355383",
        "3a482ea0e4a5643679a55e9e70e4b81f4ae02b35be431437b770214ebcb802ed",
    ],
    "cat2": [
        "2fda3ab43e172de97d910fce22b8e3ad6b789313d792fa71f6683a095eedf778",
        "ea0f9df00c1e96a26ac5db8c9241ebb7175847145cad26655407497cfd6782ff",
        "2c02e1155a4e9871d1410c14332eff40775162b55abe06dfac1139f61df820bf",
        "5d7f69efa8db66efdcbc024ba63ed2c094bf4b85585597d02710991c087c842c",
        "4309a9eb9e6e7f7f607988d168f7db0becf65044c22f52709a4f1a369d585e84",
        "b6146489c4d3e2e4d185cdf6217ce4890d43c09761190c0a59a445c664c967ae",
        "49bf1a20d221e6d5382e61f3098c6a8b4693557264c9fab5219cd761721494c2",
        "b8925a396197c3c5aacf6b692a11ea6391c9064a40cde8776ba06256e1af26dc",
        "c03d8c7ea37368603eb6226a6641d51d4bcd460e11d88d7d3011629eb93e1342",
        "e082ac8793faee51ce7c74785daeb364eb9e22233a47c93c7ed8def0acbd513f",
    ],
    "cat3": [
        "87d079b68eb532c6496634a740384974ee039a4505dffcfacf1e178be147a321",
        "bcfe408b494ca2e1a51f352572723fdb86f324a0effe1d20c925b7df205d6bfe",
        "1a8dfe09cff4e05581cc6cefb649c71d4fdd4118a04320d79910e9f1666ee328",
        "044a969d5da0c64cbb9a4880f9a20c9f4577ab63f6d54b05e4fdd44898fb0190",
        "4296a1c239e8418cc959b3cc27d56e70ec0440aab90d79df5fd4a2ecb67d5327",
        "3b991788591599550340316b63c46e531ec9f87649e1614079f45bfb7b19ce0e",
        "c80c17ce6c798b65767d83ef35c28755c37dfb26b47a08be196740456bee767d",
        "2a9c5be655c910706f9a97cd7f579ad3e11f69fd34c4b2898390173ce7e57743",
        "867b069991aa917b82a06e929d1029f530b43f734e8319af591a1e93fb797626",
        "c153e83b315bb264c938865f75c7e505ee8628831e4cb154cd715a191dbc5f00",
    ],
}


@pytest.mark.parametrize("name", ["cat1", "cat2", "cat3"])
def test_categorical_name_migration_exact_parity(name):
    for members, expected in enumerate(_CATEGORICAL_HASHES[name], 1):
        assert _digest(categorical(members, palette=name)) == expected


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
