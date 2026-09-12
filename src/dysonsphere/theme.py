import math
import os
import tomllib
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Literal, Sequence

import altair as alt

from .palettes import _DEFAULT_QUALITATIVE_PALETTE, colors

# The module's public API - star-imported into the dysonsphere namespace. Everything
# else here is internal (underscore or not); keep this list in sync with __init__.__all__.
__all__ = ["theme", "create_config"]

# Snapshot of the original palette catalogue at import time — restored on each
# theme() call so custom palettes from config files don't accumulate or bleed
# across theme resets.
_ORIGINAL_COLORS: dict[str, list[str]] = dict(colors)
_DEFAULT_MARK_FILL_LIGHT = "#DBDBDB"
_DEFAULT_MARK_FILL_DARK = "#9D9D9D"

_BUILTIN_STYLES: dict[str, dict[str, Any]] = {
    "notebook": {
        "width": 900,
        "height": 900,
        "darkmode": True,
        "fontSize": 18,
        "transparent": True,
    },
}

# Keys are alphabetical (case-insensitive), with the exception of padding and palette configs.
_BUILTIN_DEFAULTS: dict[str, Any] = {
    "axisOffset": False,
    "axisWidth": 0.25,
    "boxplotOutliers": False,
    "chartFill": None,
    "closed": None,
    "cornerRadius": False,
    "darkmode": False,
    "dashedGrid": False,
    "dashedLine": False,
    "dashedRule": True,
    "dashedWidth": [2, 2],
    "font": "Helvetica Neue, HelveticaNeue, Helvetica, Arial, sans-serif",
    "fontSize": 6,
    "fontStyle": "normal",
    "fontWeight": 400,
    "grid": False,
    "gridColor": colors["greys"][0],
    "height": 100,
    "legend": True,
    "legendColumnPadding": 4,
    "legendGradientLength": None,
    "legendGradientThickness": 5,
    "legendOffset": None,
    "legendRowPadding": 2,
    "legendStroke": False,
    "markFill": colors["greys"][1],
    "markFillOpacity": 1.0,
    "markMedianFill": "black",
    "markSize": None,
    "markStroke": "black",
    "markStrokeOpacity": 1,
    "markStrokeWidth": None,
    "barPadding": 0.1,
    "groupPadding": 0.2,
    "outerPadding": 0.1,
    "rectPadding": 0,
    "subgroupPadding": 0,
    "tickPadding": 0.1,
    "palette": None,
    "categoryPalette": None,
    "divergingPalette": None,
    "heatmapPalette": None,
    "ordinalPalette": None,
    "rampPalette": None,
    "saveBackground": "light",
    "saveFormat": ["svg", "json"],
    "sigFigs": 3,
    "strokeCap": "round",
    "tickDirection": "out",
    "ticks": True,
    "tickSize": 3.0,
    "transparent": False,
    "viewFill": None,
    "viewPadding": True,
    "width": 100,
    "xAxis": True,
    "xDomain": True,
    "xLabelAngle": 0,
    "xLabels": True,
    "xTicks": True,
    "yAxis": True,
    "yDomain": True,
    "yLabelAngle": 0,
    "yLabels": True,
    "yTicks": True,
}


def _find_project_config() -> Path | None:
    """Walk up from cwd to find the nearest dysonsphere.toml."""
    current = Path.cwd()
    while True:
        candidate = current / "dysonsphere.toml"
        if candidate.exists():
            return candidate
        parent = current.parent
        if parent == current:
            return None
        current = parent


def _user_config_dir() -> Path:
    """Platform-appropriate user config directory."""
    if "XDG_CONFIG_HOME" in os.environ:
        return Path(os.environ["XDG_CONFIG_HOME"]) / "dysonsphere"
    if os.name == "nt":
        appdata = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
        return Path(appdata) / "dysonsphere"
    return Path.home() / ".config" / "dysonsphere"


def _config_paths() -> list[Path]:
    """Config file search paths in ascending priority order (user config < project)."""
    paths = []
    user_config = _user_config_dir() / "dysonsphere.toml"
    if user_config.exists():
        paths.append(user_config)
    project_config = _find_project_config()
    if project_config is not None:
        paths.append(project_config)
    return paths


def _load_style_overrides(style: str | None) -> dict[str, Any]:
    """
    Build the final override dict for theme().

    Merge order (ascending priority):
      1. [default] blocks from config files   — user's global baseline
      2. built-in style preset                — preset-specific values beat [default]
      3. [style] blocks from config files     — user can customise the built-in preset
    """
    default_cfg: dict[str, Any] = {}
    style_cfg: dict[str, Any] = {}
    style_found_in_config = False

    for path in _config_paths():
        with open(path, "rb") as f:
            config: dict[str, Any] = tomllib.load(f)

        for section in ("default", style):
            if section and section in config:
                unknown = set(config[section]) - set(_BUILTIN_DEFAULTS)
                if unknown:
                    raise ValueError(f"Unknown theme parameter(s) in [{section}] of {path}: {sorted(unknown)}")

        if "default" in config:
            default_cfg.update(config["default"])

        if style is not None and style in config:
            style_cfg.update(config[style])
            style_found_in_config = True

    if style is not None and style not in _BUILTIN_STYLES and not style_found_in_config:
        raise ValueError(f"Style {style!r} not found as preset or any dysonsphere config file.")

    merged: dict[str, Any] = {}
    merged.update(default_cfg)
    if style is not None:
        merged.update(_BUILTIN_STYLES.get(style, {}))
    merged.update(style_cfg)
    return merged


def _load_custom_palettes() -> dict[str, list[str]]:
    """Load [palettes] sections from all config files (later files take precedence)."""
    custom: dict[str, list[str]] = {}
    for path in _config_paths():
        with open(path, "rb") as f:
            config: dict[str, Any] = tomllib.load(f)
        palettes_section = config.get("palettes", {})
        for name, values in palettes_section.items():
            if not isinstance(values, list) or len(values) == 0:
                raise ValueError(f"Palette {name!r} in {path} must be a non-empty list of color strings.")
            if not all(isinstance(v, str) and v for v in values):
                raise ValueError(f"Palette {name!r} in {path} must contain only color strings.")
            custom[name] = values
    return custom


class _UnsetType:
    def __repr__(self) -> str:
        return "<omitted>"


_UNSET: Any = _UnsetType()


def _resolve_choice(value: str | Sequence[str], valid: tuple[str, ...], name: str) -> list[str]:
    """Normalize and validate a non-empty string-or-sequence choice."""
    if not isinstance(value, str) and (isinstance(value, bytes) or not isinstance(value, Sequence)):
        raise TypeError(f"{name} must be a string or sequence of strings; got {value!r}")
    items = [value] if isinstance(value, str) else list(value)
    if not items:
        raise ValueError(f"{name} must be non-empty; got {value!r}")
    invalid = [item for item in items if not isinstance(item, str) or item not in valid]
    if invalid:
        raise ValueError(f"{name} must be one of {valid}, got {invalid!r}")
    return items


def _validate_options(p: dict[str, Any]) -> None:
    """Validate source values before deriving or committing theme state."""
    bool_keys = {
        "darkmode",
        "dashedGrid",
        "dashedLine",
        "dashedRule",
        "grid",
        "legend",
        "legendStroke",
        "ticks",
        "transparent",
        "xAxis",
        "xDomain",
        "xLabels",
        "xTicks",
        "yAxis",
        "yDomain",
        "yLabels",
        "yTicks",
    }
    for key in bool_keys:
        if not isinstance(p[key], bool):
            raise TypeError(f"{key} must be a bool; got {p[key]!r}")
    if p["closed"] is not None and not isinstance(p["closed"], bool):
        raise TypeError(f"closed must be a bool or None; got {p['closed']!r}")
    if not isinstance(p["tickDirection"], str):
        raise TypeError(f"tickDirection must be 'in' or 'out'; got {p['tickDirection']!r}")
    if p["tickDirection"] not in ("in", "out"):
        raise ValueError(f"tickDirection must be 'in' or 'out'; got {p['tickDirection']!r}")

    def number(key: str, *, positive: bool = False, nonnegative: bool = False, allow_none: bool = False) -> None:
        value = p[key]
        if allow_none and value is None:
            return
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"{key} must be a number{', or None' if allow_none else ''}; got {value!r}")
        if not math.isfinite(value):
            raise ValueError(f"{key} must be finite; got {value!r}")
        if positive and value <= 0:
            raise ValueError(f"{key} must be positive; got {value!r}")
        if nonnegative and value < 0:
            raise ValueError(f"{key} must be nonnegative; got {value!r}")

    for key in ("width", "height", "fontSize", "legendGradientThickness"):
        number(key, positive=True)
    number("legendGradientLength", positive=True, allow_none=True)
    for key in ("axisWidth", "tickSize", "legendColumnPadding", "legendRowPadding"):
        number(key, nonnegative=True)
    for key in ("markSize", "markStrokeWidth"):
        number(key, nonnegative=True, allow_none=True)
    for key in ("axisOffset", "legendOffset", "xLabelAngle", "yLabelAngle"):
        if key == "axisOffset" and isinstance(p[key], bool):
            continue
        if key == "axisOffset" and p[key] is None:
            raise ValueError("axisOffset=None is not supported; use False, True, or a numeric offset.")
        number(key, allow_none=key == "legendOffset")
    for key in ("markFillOpacity", "markStrokeOpacity"):
        number(key, nonnegative=True)
        if p[key] > 1:
            raise ValueError(f"{key} must be between 0 and 1; got {p[key]!r}")
    for key in ("barPadding", "rectPadding", "tickPadding", "groupPadding", "subgroupPadding"):
        number(key, nonnegative=True)
        if p[key] > 1:
            raise ValueError(f"{key} must be at most 1; got {p[key]!r}")
    number("outerPadding", nonnegative=True)
    for key in ("cornerRadius", "boxplotOutliers", "viewPadding"):
        if not isinstance(p[key], bool):
            number(key, nonnegative=True)

    if isinstance(p["sigFigs"], bool) or not isinstance(p["sigFigs"], int):
        raise TypeError(f"sigFigs must be an integer; got {p['sigFigs']!r}")
    if p["sigFigs"] <= 0:
        raise ValueError(f"sigFigs must be positive; got {p['sigFigs']!r}")
    if p["fontStyle"] not in ("normal", "italic", "oblique"):
        raise ValueError("fontStyle must be 'normal', 'italic', or 'oblique'")
    if p["strokeCap"] not in ("butt", "round", "square"):
        raise ValueError("strokeCap must be 'butt', 'round', or 'square'")
    weight = p["fontWeight"]
    if isinstance(weight, bool) or not isinstance(weight, (str, int, float)):
        raise TypeError(f"fontWeight must be a CSS weight name or number; got {weight!r}")
    if isinstance(weight, str):
        if weight not in {"normal", "bold", "lighter", "bolder"}:
            raise ValueError(f"fontWeight has unsupported CSS weight name {weight!r}")
    elif not math.isfinite(weight) or not 1 <= weight <= 1000:
        raise ValueError(f"numeric fontWeight must be finite and between 1 and 1000; got {weight!r}")
    for key in ("font", "gridColor", "markFill", "markMedianFill", "markStroke"):
        if not isinstance(p[key], str) or not p[key]:
            raise TypeError(f"{key} must be a non-empty color or font string; got {p[key]!r}")
    for key in ("chartFill", "viewFill"):
        if p[key] is not None and (not isinstance(p[key], str) or not p[key]):
            raise TypeError(f"{key} must be a non-empty color string or None; got {p[key]!r}")
    dash = p["dashedWidth"]
    if isinstance(dash, (str, bytes)) or not isinstance(dash, Sequence):
        raise TypeError(f"dashedWidth must be a sequence of numbers; got {dash!r}")
    for value in dash:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"dashedWidth must contain only numbers; got {dash!r}")
        if not math.isfinite(value) or value < 0:
            raise ValueError(f"dashedWidth values must be finite and nonnegative; got {dash!r}")
    p["dashedWidth"] = list(dash)
    for key in ("palette", "categoryPalette", "divergingPalette", "heatmapPalette", "ordinalPalette", "rampPalette"):
        value = p[key]
        if isinstance(value, str) and not value.strip():
            raise ValueError(f"{key} must not be blank")
        if value is not None and not isinstance(value, str):
            if not isinstance(value, list) or not value or not all(isinstance(item, str) and item for item in value):
                raise TypeError(f"{key} must be a name, a non-empty list of color strings, or None; got {value!r}")
    _resolve_choice(p["saveFormat"], ("svg", "png", "json", "html"), "saveFormat")
    _resolve_choice(p["saveBackground"], ("light", "dark"), "saveBackground")


def theme(
    style: str | None = None,
    *,
    axisOffset: int | float | bool = _UNSET,
    axisWidth: int | float = _UNSET,
    boxplotOutliers: int | float | bool = _UNSET,
    chartFill: str | None = _UNSET,
    closed: bool | None = _UNSET,
    cornerRadius: int | float | bool = _UNSET,
    darkmode: bool = _UNSET,
    dashedGrid: bool = _UNSET,
    dashedLine: bool = _UNSET,
    dashedRule: bool = _UNSET,
    dashedWidth: Sequence[int | float] = _UNSET,
    font: str = _UNSET,
    fontSize: int | float = _UNSET,
    fontStyle: str = _UNSET,
    fontWeight: str | int | float = _UNSET,
    grid: bool = _UNSET,
    gridColor: str = _UNSET,
    height: int | float = _UNSET,
    legend: bool = _UNSET,
    legendColumnPadding: int | float = _UNSET,
    legendGradientLength: int | float | None = _UNSET,
    legendGradientThickness: int | float = _UNSET,
    legendOffset: int | float | None = _UNSET,
    legendRowPadding: int | float = _UNSET,
    legendStroke: bool = _UNSET,
    markFill: str = _UNSET,
    markFillOpacity: int | float = _UNSET,
    markMedianFill: str = _UNSET,
    markSize: int | float | None = _UNSET,
    markStroke: str = _UNSET,
    markStrokeOpacity: int | float = _UNSET,
    markStrokeWidth: int | float | None = _UNSET,
    barPadding: int | float = _UNSET,
    groupPadding: int | float = _UNSET,
    outerPadding: int | float = _UNSET,
    rectPadding: int | float = _UNSET,
    subgroupPadding: int | float = _UNSET,
    tickPadding: int | float = _UNSET,
    palette: str | list[str] | None = _UNSET,
    categoryPalette: str | list[str] | None = _UNSET,
    divergingPalette: str | list[str] | None = _UNSET,
    heatmapPalette: str | list[str] | None = _UNSET,
    ordinalPalette: str | list[str] | None = _UNSET,
    rampPalette: str | list[str] | None = _UNSET,
    saveBackground: str | Sequence[str] = _UNSET,
    saveFormat: str | Sequence[str] = _UNSET,
    sigFigs: int = _UNSET,
    strokeCap: str = _UNSET,
    tickDirection: Literal["in", "out"] = _UNSET,
    ticks: bool = _UNSET,
    tickSize: int | float = _UNSET,
    transparent: bool = _UNSET,
    viewFill: str | None = _UNSET,
    viewPadding: int | float | bool = _UNSET,
    width: int | float = _UNSET,
    xAxis: bool = _UNSET,
    xDomain: bool = _UNSET,
    xLabelAngle: int | float = _UNSET,
    xLabels: bool = _UNSET,
    xTicks: bool = _UNSET,
    yAxis: bool = _UNSET,
    yDomain: bool = _UNSET,
    yLabelAngle: int | float = _UNSET,
    yLabels: bool = _UNSET,
    yTicks: bool = _UNSET,
) -> None:
    """
    Configure and register the dysonsphere Altair theme.

    Every styling option is keyword-only. Omitted options inherit the applicable TOML/default/style value;
    a successful call replaces, rather than updates, the active theme. Explicit ``None`` retains its
    documented meaning for auto-derived fills, frame state, offsets, and mark dimensions.
    ``style`` remains an optional positional primary input; every styling option is keyword-only.
    Runtime introspection displays ``<omitted>`` for omitted styling defaults; generated source
    signatures may show the private ``_UNSET`` marker. Neither is a value callers pass.

    By family, canvas dimensions default to 100 x 100 pixels. ``fontSize=6`` is a positive, fractional nominal
    publication point size; SVG markup exposes the same number as a renderer user-unit value, and raster
    export scales from 72 intrinsic units per inch. Axis, tick, legend, radius, and linear composite
    dimensions are pixels. ``legendGradientLength=None`` allocates half the panel height to a
    vertical title-plus-gradient span and the full panel width to a horizontal gradient. A positive
    number is instead a dimensionless factor applied to either orientation at spec-resolution time;
    ``legendGradientThickness`` is a positive pixel width independent of marks and chart dimensions.
    Continuous legends require ``ds.save()`` or ``ds.show()`` to resolve their sizing marker; bare
    Altair/notebook rendering may fail. Signed axis/legend offsets and label angles are supported.
    ``markSize=None`` derives one tenth of
    the smaller canvas dimension and is the common basis for symbol areas and composite dimensions;
    ``markStrokeWidth=None`` derives from ``axisWidth``. An omitted and unconfigured ``markFill``
    follows the render mode (``greys[1]`` light, ``greys[4]`` dark); an explicit or configured value
    stays fixed across modes. Circle marks keep their separate black/white fill.

    Boolean axis switches gate domains/ticks but not labels. ``tickDirection`` is ``"out"`` or ``"in"``;
    ``closed=None`` derives from inward ticks or a view fill. ``viewPadding=True``, ``cornerRadius=True``,
    and ``boxplotOutliers=True`` derive
    size-dependent values; False disables them and a nonnegative number is explicit. Inner band
    paddings are dimensionless values in [0, 1]; ``outerPadding`` is any nonnegative value. Opacities
    are in [0, 1], and dash sequences contain finite nonnegative pixel lengths, including empty and
    odd-length sequences.

    Palette options accept a nonblank registered name, renderer scheme name, nonempty color-string
    list, or None. The master ``palette`` overrides every per-type palette after source precedence is
    resolved. ``saveFormat`` accepts svg/png/json/html and ``saveBackground`` accepts light/dark as a
    string or nonempty sequence. See the [configuration guide](/guides/configuration/) for the complete
    per-option defaults and scopes.

    A TOML config file can provide persistent per-project or per-user
    overrides. See the README for the config file format and search path.
    Named styles in the config file are selected with ``style=``.

    Raises
    ------
    TypeError
        If a value has the wrong type. Boolean switches reject numeric substitutes.
    ValueError
        If a configuration file contains an unknown parameter or invalid palette, a requested style
        is unavailable, or a value is outside its finite range or supported enum. Failed calls leave
        the active theme and palette registry unchanged.
    """
    global _ACTIVE_ARGS
    if style is not None and not isinstance(style, str):
        raise TypeError(f"style must be a string or None; got {style!r}")
    supplied = {key: value for key, value in locals().items() if key != "style" and value is not _UNSET}

    overrides = _load_style_overrides(style)
    custom_palettes = _load_custom_palettes()
    p: dict[str, Any] = {**_BUILTIN_DEFAULTS, **overrides, **supplied}
    mark_fill_auto = "markFill" not in overrides and "markFill" not in supplied
    if mark_fill_auto:
        p["markFill"] = _DEFAULT_MARK_FILL_DARK if p["darkmode"] else _DEFAULT_MARK_FILL_LIGHT
    _validate_options(p)
    _compute_derived(p)
    _validate_options(p)  # derived multiplication can overflow even when each source value is finite

    # Resolve every palette-valued key: a name in `colors` (built-in or custom)
    # becomes its hex list; anything else (a raw list, or a Vega scheme name) is
    # passed through unchanged.
    for key in ("palette", "categoryPalette", "divergingPalette", "heatmapPalette", "ordinalPalette", "rampPalette"):
        val = p[key]
        p[key] = custom_palettes.get(val, _ORIGINAL_COLORS.get(val, val)) if isinstance(val, str) else val

    # Commit only after every input has been validated and all derived values have been computed.
    colors.clear()
    colors.update(_ORIGINAL_COLORS)
    colors.update(custom_palettes)
    alt.theme.options = {**p, "tickWidth": p["axisWidth"], "_markFillAuto": mark_fill_auto}
    _ACTIVE_ARGS = {**supplied, **({"style": style} if style is not None else {})}


def _compute_derived(p: dict[str, Any]) -> None:
    """Resolve the derive-at-theme-time sentinels in *p* in place (None / True markers).

    Shared by :func:`theme` and the :func:`_opt` fallback so both resolve the same way.
    """
    # Computed defaults — None means "derive from other params"
    if p["closed"] is None:
        # inward ticks point into the plot, so they need a closed (non-offset) axis;
        # default closed=True for inward ticks (an explicit closed=False still wins).
        p["closed"] = p["tickDirection"] == "in" or p["viewFill"] is not None
    if p["markSize"] is None:
        p["markSize"] = min(p["width"], p["height"]) * 0.1
    if p["markStrokeWidth"] is None:
        p["markStrokeWidth"] = p["axisWidth"]
    if p["cornerRadius"] is True:
        p["cornerRadius"] = min(p["width"], p["height"]) / 100
    if p["boxplotOutliers"] is True:  # True → show at markSize/10; a number is an explicit size; False → hidden
        p["boxplotOutliers"] = p["markSize"] / 10
    if p["viewPadding"] is True:  # continuous-scale data inset, chart-scaled like markSize
        p["viewPadding"] = min(p["width"], p["height"]) * 0.05
    # chartFill=None is resolved at config-build time in _dysonsphere_theme(), NOT here, so it
    # follows darkmode live (save() toggles darkmode per background without re-running theme()).
    # Axes are flush by default; the gap between axis and data comes from viewPadding instead.
    # True restores the Prism-style detached axis at 1.5x tick length - a sentinel rather than a
    # literal 4.5 so it keeps tracking tickSize. Resolved once here so the axis config and
    # save()'s grid-span fix read one consistent value.
    if p["axisOffset"] is None:
        raise ValueError("axisOffset=None is not supported; use False, True, or a numeric offset.")
    if p["axisOffset"] is True:
        p["axisOffset"] = p["tickSize"] * 1.5
    elif p["axisOffset"] is False:
        p["axisOffset"] = 0
    if p["legendOffset"] is None:
        p["legendOffset"] = p["tickSize"] * 1.5


_FALLBACK_OPTIONS: dict[str, Any] | None = None
# the args of the last theme() call - a scoped override rebuilds from these, since the
# resolved options would freeze markSize and friends instead of re-deriving them
_ACTIVE_ARGS: dict[str, Any] = {}


def _active_args() -> dict[str, Any]:
    """A copy of the last theme() call's explicit args - theme() rebinds the global, so read it here."""
    return dict(_ACTIVE_ARGS)


def _restore_theme(theme_args: dict[str, Any], automatic: set[str]) -> None:
    """Restore saved resolved options while retaining supported automatic-option provenance."""
    global _ACTIVE_ARGS
    theme(**theme_args)
    if "markFill" in automatic:
        alt.theme.options["_markFillAuto"] = True
        _ACTIVE_ARGS.pop("markFill", None)


@contextmanager
def _temporary_theme(overrides: dict[str, Any]):
    """Re-derive selected options while preserving the exact active theme state."""
    global _ACTIVE_ARGS
    previous_options = dict(alt.theme.options)
    previous_args = dict(_ACTIVE_ARGS)
    previous_colors = dict(colors)
    # save() changes these resolved options directly. Carry that render mode into the
    # rebuilt theme while size-dependent values are derived from the original arguments.
    render_mode = {key: previous_options.get(key, _opt(key)) for key in ("darkmode", "transparent")}
    rebuild_args: dict[str, Any] = {**previous_args, **render_mode, **overrides}
    mark_fill_auto = previous_options.get("_markFillAuto", True) and "markFill" not in overrides
    if mark_fill_auto:
        rebuild_args["markFill"] = _DEFAULT_MARK_FILL_DARK if rebuild_args["darkmode"] else _DEFAULT_MARK_FILL_LIGHT
    theme(**rebuild_args)
    if mark_fill_auto:
        alt.theme.options["_markFillAuto"] = True
        _ACTIVE_ARGS.pop("markFill", None)
    try:
        yield
    finally:
        alt.theme.options = previous_options
        _ACTIVE_ARGS = previous_args
        colors.clear()
        colors.update(previous_colors)


def _opt(key: str) -> Any:
    """Read a theme option, falling back to the (derived) built-in default.

    The single accessor for theme options outside theme.py — replaces scattered
    ``alt.theme.options.get(key, hardcoded)`` calls, whose per-site hardcoded fallbacks
    could silently drift from ``_BUILTIN_DEFAULTS``. After ``ds.theme()`` every option is
    present in ``alt.theme.options``, so the fallback only matters when a chart helper is
    called before any ``theme()``; it then sees the fully derived built-in defaults
    (``markSize`` 10.0, ``axisOffset`` 0, …), computed once and cached. Unknown keys
    raise ``KeyError``.
    """
    if key == "markFill" and alt.theme.options.get("_markFillAuto", True):
        return _DEFAULT_MARK_FILL_DARK if alt.theme.options.get("darkmode", False) else _DEFAULT_MARK_FILL_LIGHT
    try:
        return alt.theme.options[key]
    except KeyError:
        global _FALLBACK_OPTIONS
        if _FALLBACK_OPTIONS is None:
            defaults = dict(_BUILTIN_DEFAULTS)
            _compute_derived(defaults)
            _FALLBACK_OPTIONS = defaults
        return _FALLBACK_OPTIONS[key]


@alt.theme.register("dysonsphere", enable=True)
def _dysonsphere_theme() -> dict[str, Any]:
    opts = dict(alt.theme.options)
    if opts.get("_markFillAuto", True):
        opts["markFill"] = _DEFAULT_MARK_FILL_DARK if opts.get("darkmode", False) else _DEFAULT_MARK_FILL_LIGHT

    def _scheme(type_key: str, default: Any) -> Any:
        # Precedence: global `palette` (master override) → per-type `<type>Palette` → default.
        if opts.get("palette") is not None:
            return opts["palette"]
        if opts.get(type_key) is not None:
            return opts[type_key]
        return default

    # config.range.category must be a BARE array so a nominal scale maps positionally
    # (category i -> color i), which the tier-major `categorical` palette relies on. The
    # {"scheme": [...]} form is invalid for nominal and silently drops the range. A Vega
    # scheme *name* (a str, e.g. "tableau10") still needs the {"scheme": ...} wrapper.
    _cat = _scheme("categoryPalette", colors[_DEFAULT_QUALITATIVE_PALETTE])
    category_range = _cat if isinstance(_cat, list) else {"scheme": _cat}

    return {
        # background of the entire chart; chartFill=None -> auto (darkmode-aware)
        "background": (
            None
            if opts["transparent"]
            else (opts["chartFill"] if opts["chartFill"] is not None else ("black" if opts["darkmode"] else "white"))
        ),
        "config": {
            "arc": {
                "fill": opts["markFill"],
                "fillOpacity": opts["markFillOpacity"],
                "innerRadius": min(opts["width"], opts["height"]) / 4,
                "padAngle": 0.03,
                "stroke": opts["markStroke"],
                "strokeOpacity": opts["markStrokeOpacity"],
                "strokeWidth": opts["markStrokeWidth"],
                **({"cornerRadius": opts["cornerRadius"]} if opts["cornerRadius"] else {}),
            },
            "area": {
                "fill": opts["markFill"],
                "fillOpacity": opts["markFillOpacity"],
                "stroke": opts["markStroke"],
                "strokeOpacity": opts["markStrokeOpacity"],
                "strokeWidth": opts["markStrokeWidth"],
            },
            "axis": {
                "domain": True,
                "domainCap": opts["strokeCap"],
                "domainColor": "white" if opts["darkmode"] else "black",
                "domainWidth": opts["axisWidth"],
                "grid": opts["grid"],
                "gridCap": opts["strokeCap"],
                "gridColor": (opts["gridColor"] if opts["darkmode"] else opts["gridColor"]),
                "gridDash": opts["dashedWidth"] if opts["dashedGrid"] else [0, 0],
                "gridOpacity": 1.00,
                "gridWidth": opts["axisWidth"],
                "labelColor": "white" if opts["darkmode"] else "black",
                "labelFont": opts["font"],
                "labelFontSize": opts["fontSize"],
                "labelFontStyle": opts["fontStyle"],
                "labelFontWeight": opts["fontWeight"],
                "offset": 0 if opts["closed"] else opts["axisOffset"],
                "ticks": opts["ticks"],
                "tickCap": opts["strokeCap"],
                "tickColor": "white" if opts["darkmode"] else "black",
                # Vega rounds tick/grid positions to integers for on-screen crispness, which
                # drifts them off the (fractional) mark positions at high DPI. tickRound=False
                # keeps ticks on the exact scale positions - the same family of fix as the
                # hardcoded "translate": 0 below (Vega's 0.5px crisp-pixel offset).
                "tickRound": False,
                "tickSize": opts["tickSize"],
                "tickWidth": opts["axisWidth"],
                "titleColor": "white" if opts["darkmode"] else "black",
                "titleFont": opts["font"],
                "titleFontSize": opts["fontSize"],
                "titleFontStyle": opts["fontStyle"],
                "titleFontWeight": opts["fontWeight"],
            },
            "axisX": {
                "domain": opts["xAxis"] and opts["xDomain"],
                "labelAlign": ("right" if opts["xLabelAngle"] < 0 else "left" if opts["xLabelAngle"] > 0 else "center"),
                "labelAngle": opts["xLabelAngle"] % 360,
                "labels": opts["xLabels"],
                "ticks": opts["xAxis"] and opts["xTicks"] and opts["ticks"],
                "translate": 0,
            },
            "axisY": {
                "domain": opts["yAxis"] and opts["yDomain"],
                "labelAlign": "center" if opts["yLabelAngle"] != 0 else "right",
                "labelAngle": opts["yLabelAngle"] % 360,
                "labels": opts["yLabels"],
                "ticks": opts["yAxis"] and opts["yTicks"] and opts["ticks"],
                "translate": 0,
            },
            "axisRight": {
                "domain": opts["yAxis"] and opts["yDomain"],
                "labelAlign": "center" if opts["yLabelAngle"] != 0 else "left",
                "labelAngle": (-opts["yLabelAngle"]) % 360,
                "labels": opts["yLabels"],
                "ticks": opts["yAxis"] and opts["yTicks"] and opts["ticks"],
                "translate": 0,
            },
            "axisTop": {
                "domain": opts["xAxis"] and opts["xDomain"],
                "labelAlign": ("left" if opts["xLabelAngle"] < 0 else "right" if opts["xLabelAngle"] > 0 else "center"),
                "labelAngle": (-opts["xLabelAngle"]) % 360,
                "labels": opts["xLabels"],
                "ticks": opts["xAxis"] and opts["xTicks"] and opts["ticks"],
                "translate": 0,
            },
            # Band-scale axes place ticks 0.5px off the band centre by default (Vega's
            # tickOffset, resolved via the scale-type-specific axisBand config, not
            # config.axis). Zeroing it puts ticks exactly on band centres.
            "axisBand": {
                "tickOffset": 0,
            },
            "bar": {
                "fill": opts["markFill"],
                "fillOpacity": opts["markFillOpacity"],
                "stroke": opts["markStroke"],
                "strokeOpacity": opts["markStrokeOpacity"],
                "strokeWidth": opts["markStrokeWidth"],
                **({"cornerRadiusEnd": opts["cornerRadius"]} if opts["cornerRadius"] else {}),
            },
            "boxplot": {
                "size": opts["markSize"] * 0.9,
                "ticks": {
                    "cornerRadius": opts["markStrokeWidth"],
                    "fill": "white" if opts["darkmode"] else "black",
                    # opacity 1 so config.tick's opacity (markFillOpacity) can't leak in
                    # through the composite lowering and double-dim with fillOpacity
                    "opacity": 1,
                    "size": opts["markSize"] * 0.45,  # half the box width (markSize * 0.9)
                    "thickness": opts["markStrokeWidth"],
                },
                "box": {
                    "fillOpacity": opts["markFillOpacity"],
                    "stroke": opts["markStroke"],
                    "strokeOpacity": opts["markStrokeOpacity"],
                    "strokeWidth": opts["markStrokeWidth"],
                    **({"cornerRadius": opts["cornerRadius"]} if opts["cornerRadius"] else {}),
                },
                "median": {
                    # square ends, flush with the box edges (config.tick's round caps
                    # would otherwise inherit through the composite lowering)
                    "cornerRadius": 0,
                    "fill": opts["markMedianFill"],
                    "fillOpacity": opts["markFillOpacity"],
                    # opacity 1: see the ticks block (fillOpacity alone governs the fade)
                    "opacity": 1,
                    "size": opts["markSize"] * 0.9,  # spans the box
                    # a single stroke of markStrokeWidth thickness (no competing outline stroke)
                    "thickness": opts["markStrokeWidth"],
                },
                "rule": {
                    "fill": "white" if opts["darkmode"] else "black",
                    "fillOpacity": opts["markFillOpacity"],
                    "size": opts["markSize"],
                    "stroke": "white" if opts["darkmode"] else "black",
                    "strokeDash": [0, 0],
                    "strokeOpacity": opts["markStrokeOpacity"],
                    "strokeWidth": opts["markStrokeWidth"],
                },
                "outliers": {
                    "color": "white" if opts["darkmode"] else "black",
                    "fill": "white" if opts["darkmode"] else "black",
                    "fillOpacity": opts["markFillOpacity"],
                    "size": opts["boxplotOutliers"] or 0,  # False → 0 (hidden); a number → that size
                    "stroke": opts["markStroke"],
                    "strokeOpacity": opts["markStrokeOpacity"],
                    "strokeWidth": opts["markStrokeWidth"],
                },
            },
            "circle": {
                "fill": "white" if opts["darkmode"] else "black",
                "fillOpacity": opts["markFillOpacity"],
                # Small default: mark_circle is primarily used to layer raw points over
                # boxplots/violins/strips, where small dots read best.
                "size": opts["markSize"] / 8,
                # No outline: at this dot size a stroke swamps the fill. Explicit None
                # (not omitted) so nothing is inherited from other mark configs. The
                # opacity/width stay configured so a re-enabled stroke (per chart or a
                # future config) renders with the house style.
                "stroke": None,
                "strokeOpacity": opts["markStrokeOpacity"],
                "strokeWidth": opts["markStrokeWidth"],
            },
            "errorband": {
                "band": {
                    "fillOpacity": 0.60,
                    "stroke": None,
                    "strokeWidth": opts["markStrokeWidth"],
                    "strokeOpacity": opts["markStrokeOpacity"],
                },
                "borders": {
                    "opacity": 0,
                    "strokeOpacity": opts["markStrokeOpacity"],
                    "strokeWidth": opts["markStrokeWidth"],
                },
            },
            "errorbar": {
                "opacity": 1,
                "rule": {
                    "strokeDash": [0, 0],
                    "strokeWidth": opts["markStrokeWidth"],
                },
                "ticks": {
                    "color": "white" if opts["darkmode"] else "black",
                    "cornerRadius": opts["markStrokeWidth"] / 2,
                    "opacity": 1,
                    "size": opts["markSize"] * 0.6,
                    "thickness": opts["markStrokeWidth"],
                },
                "thickness": opts["markStrokeWidth"],
            },
            "font": opts["font"],
            "geoshape": {
                "fill": opts["markFill"],
                "fillOpacity": opts["markFillOpacity"],
                "stroke": "white" if opts["darkmode"] else "black",
                "strokeOpacity": opts["markStrokeOpacity"],
                "strokeWidth": opts["markStrokeWidth"],
            },
            "header": {
                "labelColor": "white" if opts["darkmode"] else "black",
                "labelFont": opts["font"],
                "labelFontSize": opts["fontSize"],
                "labelFontStyle": opts["fontStyle"],
                "labelFontWeight": opts["fontWeight"],
                "titleColor": "white" if opts["darkmode"] else "black",
                "titleFont": opts["font"],
                "titleFontSize": opts["fontSize"],
                "titleFontStyle": opts["fontStyle"],
                "titleFontWeight": opts["fontWeight"],
                "titlePadding": 0,
            },
            "legend": {
                "disable": not opts["legend"],
                "offset": opts["legendOffset"],
                # Legend text spacing mirrors the axis defaults: label gap 2, title gap 4.
                # titlePadding = title->content (default 5); labelOffset = symbol->label (default
                # 4); gradientLabelOffset = gradient-bar->label (labelOffset does NOT reach
                # gradient labels). Applies to every legend (symbol + gradient).
                "titlePadding": 4,
                "labelOffset": 2,
                "gradientLabelOffset": 2,
                # Entry spacing. Vega's own defaults are lopsided - 10 across, 2 down - which
                # reads loose on a horizontal legend next to this theme's 2/4px gaps.
                "columnPadding": opts["legendColumnPadding"],
                "rowPadding": opts["legendRowPadding"],
                # Save/show replace this non-executable ExprRef marker with panel geometry.
                # Bare Altair rendering cannot resolve it; explicit configure_legend lengths win.
                "gradientLength": {"expr": f"dysonsphereLegendGradientLength({opts['legendGradientLength']!r})"},
                "gradientThickness": opts["legendGradientThickness"],
                "gradientOpacity": opts["markFillOpacity"],
                "gradientStrokeColor": "white" if opts["darkmode"] else "black",
                "gradientStrokeWidth": opts["markStrokeWidth"],
                "labelColor": "white" if opts["darkmode"] else "black",
                "labelFont": opts["font"],
                "labelFontSize": opts["fontSize"],
                "labelFontStyle": opts["fontStyle"],
                "labelFontWeight": opts["fontWeight"],
                "strokeColor": "white" if opts["darkmode"] else "black",
                "strokeWidth": opts["axisWidth"] if opts["legendStroke"] else 0,
                "symbolSize": opts["fontSize"] * 6,
                "symbolStrokeColor": "white" if opts["darkmode"] else "black",
                "symbolStrokeWidth": opts["markStrokeWidth"] if opts["markStrokeOpacity"] > 0 else 0,
                "titleColor": "white" if opts["darkmode"] else "black",
                "titleFont": opts["font"],
                "titleFontSize": opts["fontSize"],
                "titleFontStyle": opts["fontStyle"],
                "titleFontWeight": opts["fontWeight"],
            },
            "line": {
                "color": "white" if opts["darkmode"] else "black",
                "stroke": "white" if opts["darkmode"] else "black",
                "strokeCap": "butt",
                "strokeDash": opts["dashedWidth"] if opts["dashedLine"] else [0, 0],
                "strokeOpacity": 1,
                "strokeWidth": opts["axisWidth"] * 2,
            },
            "point": {
                "filled": True,
                "fill": opts["markFill"],
                "fillOpacity": opts["markFillOpacity"],
                "size": opts["markSize"] / 2,
                "stroke": opts["markStroke"],
                "strokeOpacity": opts["markStrokeOpacity"],
                "strokeWidth": opts["markStrokeWidth"],
            },
            "range": {
                "category": category_range,
                "diverging": {"scheme": _scheme("divergingPalette", colors["div1"])},
                "heatmap": {"scheme": _scheme("heatmapPalette", colors["viridis"])},
                "ordinal": {"scheme": _scheme("ordinalPalette", colors["greys"])},
                "ramp": {"scheme": _scheme("rampPalette", colors["viridis"])},
            },
            "rule": {
                "color": "white" if opts["darkmode"] else "black",
                "stroke": "white" if opts["darkmode"] else "black",
                "strokeCap": opts["strokeCap"],
                "strokeDash": opts["dashedWidth"] if opts["dashedRule"] else [0, 0],
                "strokeOpacity": 1,
                "strokeWidth": opts["axisWidth"],
            },
            "scale": {
                # Band padding is set per mark type, never via the global bandPaddingInner -
                # that key overrides all three mark-specific defaults at once, which is what
                # used to band heatmap cells with the bar spacing. Outer has no mark-specific
                # counterpart in Vega-Lite, so one key covers every band scale.
                "barBandPaddingInner": opts["barPadding"],
                "rectBandPaddingInner": opts["rectPadding"],
                "tickBandPaddingInner": opts["tickPadding"],
                "bandPaddingOuter": opts["outerPadding"],
                "bandWithNestedOffsetPaddingInner": opts["groupPadding"],
                "bandWithNestedOffsetPaddingOuter": opts["groupPadding"],
                "offsetBandPaddingInner": opts["subgroupPadding"],
                "offsetBandPaddingOuter": opts["subgroupPadding"],
                # The data inset that keeps marks off the axes. export._suppress_nice drops `nice`
                # wherever this is emitted, so the inset lands at exactly this many pixels.
                **({"continuousPadding": opts["viewPadding"]} if opts["viewPadding"] else {}),
                "round": False,
            },
            "rect": {
                "fill": opts["markFill"],
                "fillOpacity": opts["markFillOpacity"],
                "stroke": opts["markStroke"],
                "strokeOpacity": opts["markStrokeOpacity"],
                "strokeWidth": opts["markStrokeWidth"],
                **({"cornerRadius": opts["cornerRadius"]} if opts["cornerRadius"] else {}),
            },
            "square": {
                "fill": opts["markFill"],
                "fillOpacity": opts["markFillOpacity"],
                "size": opts["markSize"],
                "stroke": opts["markStroke"],
                "strokeOpacity": opts["markStrokeOpacity"],
                "strokeWidth": opts["markStrokeWidth"],
            },
            "text": {
                "color": "white" if opts["darkmode"] else "black",
                "font": opts["font"],
                "fontSize": opts["fontSize"],
                "fontStyle": opts["fontStyle"],
                "fontWeight": opts["fontWeight"],
            },
            "tick": {
                "color": "white" if opts["darkmode"] else "black",
                "cornerRadius": opts["markStrokeWidth"] / 2,
                "opacity": opts["markFillOpacity"],
                "size": opts["markSize"] * 0.9,
                "thickness": opts["markStrokeWidth"],
            },
            "title": {
                "anchor": "middle",
                "frame": "group",
                "color": "white" if opts["darkmode"] else "black",
                "font": opts["font"],
                "fontSize": opts["fontSize"],
                "fontStyle": opts["fontStyle"],
                "fontWeight": opts["fontWeight"],
                "subtitleColor": "white" if opts["darkmode"] else "black",
                "subtitleFont": opts["font"],
                "subtitleFontSize": opts["fontSize"],
                "subtitleFontStyle": opts["fontStyle"],
                "subtitleFontWeight": opts["fontWeight"],
            },
            "trail": {
                "color": "white" if opts["darkmode"] else "black",
                "opacity": 1,
                # default width when there is no size encoding - matches config.line's
                # strokeWidth so an unsized trail renders exactly like a line
                "size": opts["axisWidth"] * 2,
            },
            "view": {
                "continuousWidth": opts["width"],
                "continuousHeight": opts["height"],
                "discreteWidth": opts["width"],
                "discreteHeight": opts["height"],
                "fill": None if opts["darkmode"] else opts["viewFill"],
                "stroke": ("white" if opts["darkmode"] else "black") if opts["closed"] else None,
                "strokeWidth": opts["axisWidth"],
            },
        },
    }


def _toml_value(v: Any) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)


def create_config(directory: str | Path | None = None, *, persist: bool = False) -> None:
    """
    Write a dysonsphere.toml template to *directory* (default: current working directory).

    Pass persist=True to write to the platform user config directory instead
    (~/.config/dysonsphere/ on macOS/Linux, %APPDATA%/dysonsphere/ on Windows).
    This file applies across all your projects.

    The file is not overwritten if it already exists. Edit the values in each
    section, rename [my_style] to your own style name, and load it with
    ds.theme(style="name").
    """
    if persist:
        dest = _user_config_dir() / "dysonsphere.toml"
    else:
        dest = Path(directory) if directory is not None else Path.cwd()
        dest = dest / "dysonsphere.toml"

    if dest.exists():
        print(f"dysonsphere.toml already exists at {dest} - not overwriting.")
        return

    lines = [
        "# dysonsphere.toml",
        "# Theme configuration for dysonsphere.",
        '# Load a style with ds.theme(style="name").',
        "",
        "# Only the keys present in a section are applied - everything else uses",
        "# dysonsphere's built-in defaults. Unknown keys raise a ValueError immediately.",
        "",
        "# [default] applies to every ds.theme() call regardless of style.",
        "# Leave it empty or omit to use dysonsphere's built-in defaults unchanged,",
        "# or add keys to override the defaults, such as default palettes for range types.",
        "",
        "[default]",
        "",
        "# Built-in styles - edit values or remove sections you don't need.",
    ]

    for name, params in _BUILTIN_STYLES.items():
        lines.append("")
        lines.append(f"[{name}]")
        for k, v in params.items():
            lines.append(f"{k} = {_toml_value(v)}")

    lines += [
        "",
        "# Custom styles - add your own style sections below",
        "",
        "[my_style]  # Rename to your desired style name",
        "",
        '# Custom palettes - lists of hex strings, available via ds.palette("name")',
        '# or ds.theme(palette="name"). dysonsphere palettes are typically 12 stops',
        "# for sequential palettes, and 13 stops for diverging palettes.",
        "",
        "[palettes]",
        '# my_palette = ["#DFE9F7", "#C6D9F1", "#ADC8EC", "#94B8E6", "#7AA8E0", "#6097DA", "#4D87CA", "#4177B1", "#386898", "#2F597F", "#264A69", "#1D3A58"]',  # noqa: E501
    ]

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Created {dest}")
