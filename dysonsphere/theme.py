import os
import tomllib
from pathlib import Path
from typing import Any

import altair as alt

from .palettes import colors

# The module's public API - star-imported into the dysonsphere namespace. Everything
# else here is internal (underscore or not); keep this list in sync with __init__.__all__.
__all__ = ["theme", "create_config"]

# Snapshot of the original palette catalogue at import time — restored on each
# theme() call so custom palettes from config files don't accumulate or bleed
# across theme resets.
_ORIGINAL_COLORS: dict[str, list[str]] = dict(colors)

_BUILTIN_STYLES: dict[str, dict[str, Any]] = {
    "notebook": {
        "chartWidth": 900,
        "chartHeight": 900,
        "darkmode": True,
        "fontSize": 18,
        "transparent": True,
    },
}

# DEPRECATED (remove at v3.0): dev-only aliases for renamed parameters - the old names
# last shipped in v2.0.0 and the rename lands as a v3.0.0 breaking change, so the alias
# never ships in a release (the release step-0 sweep deletes it).
_DEPRECATED_ALIASES: dict[str, str] = {
    "transparentBackground": "transparent",  # renamed in v3.0
}

_BUILTIN_DEFAULTS: dict[str, Any] = {
    "axisOffset": None,
    "axisWidth": 0.25,
    "bandPadding": 0.1,
    "boxplotOutliers": False,
    "chartFill": None,
    "chartHeight": 100,
    "chartWidth": 100,
    "closed": None,
    "cornerRadius": False,
    "inwardTicks": False,
    "darkmode": False,
    "dashedGrid": False,
    "dashedLine": False,
    "dashedRule": True,
    "dashedWidth": [2, 2],
    "font": "HelveticaNeue",
    "fontSize": 7,
    "secondaryFontSize": None,
    "smallestFontSize": 5,
    "fontStyle": "normal",
    "fontWeight": 400,
    "sigFigs": 3,
    "grid": False,
    "gridColor": colors["greys"][0],
    "legend": True,
    "legendOffset": None,
    "legendStroke": False,
    "markFill": colors["greys"][1],
    "markFillOpacity": 1.0,
    "markMedianFill": "black",
    "markMedianStroke": "black",
    "markSize": None,
    "markStroke": "black",
    "markStrokeOpacity": 1,
    "markStrokeWidth": None,
    "palette": None,
    "categoryPalette": None,
    "divergingPalette": None,
    "heatmapPalette": None,
    "ordinalPalette": None,
    "rampPalette": None,
    "saveBackground": "light",
    "saveFormat": ["svg", "json"],
    "strokeCap": "round",
    "ticks": True,
    "tickSize": 3,
    "transparent": False,
    "viewFill": None,
    "xAxis": True,
    "xDomain": True,
    "xLabels": True,
    "xLabelAngle": 0,
    "xTicks": True,
    "yAxis": True,
    "yDomain": True,
    "yLabels": True,
    "yLabelAngle": 0,
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


def _apply_deprecated_aliases(params: dict[str, Any], source: str) -> dict[str, Any]:
    """Map deprecated parameter names to their replacements, warning once per use.

    Returns a new dict with old keys renamed. When both the old and new name are
    present, the new name wins (the old key is dropped).
    """
    import warnings

    out = dict(params)
    for old, new in _DEPRECATED_ALIASES.items():
        if old in out:
            warnings.warn(
                f"{old!r} ({source}) is deprecated and will be removed in v3.0; use {new!r}.",
                DeprecationWarning,
                stacklevel=3,
            )
            val = out.pop(old)
            out.setdefault(new, val)
    return out


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
                config[section] = _apply_deprecated_aliases(config[section], f"[{section}] in {path}")
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
                raise ValueError(f"Palette {name!r} in {path} must be a non-empty list of hex strings.")
            if not all(isinstance(v, str) for v in values):
                raise ValueError(f"Palette {name!r} in {path} must contain only strings (hex color codes).")
            custom[name] = values
    return custom


def theme(style: str | None = None, **kwargs: Any) -> None:
    """
    Configure and register the dysonsphere Altair theme.

    All parameters are optional — pass only the ones you want to change.
    Everything else uses the dysonsphere built-in defaults.

    A TOML config file can provide persistent per-project or per-user
    overrides. See the README for the config file format and search path.
    Named styles in the config file are selected with ``style=``.
    """
    kwargs = _apply_deprecated_aliases(kwargs, "theme() keyword argument")
    unknown = set(kwargs) - set(_BUILTIN_DEFAULTS)
    if unknown:
        raise TypeError(f"theme() got unexpected keyword argument(s): {sorted(unknown)}")

    # Restore built-in palettes, then layer in any custom palettes from config files.
    colors.clear()
    colors.update(_ORIGINAL_COLORS)
    colors.update(_load_custom_palettes())

    overrides = _load_style_overrides(style)
    p: dict[str, Any] = {**_BUILTIN_DEFAULTS, **overrides, **kwargs}
    _compute_derived(p)

    # Resolve every palette-valued key: a name in `colors` (built-in or custom)
    # becomes its hex list; anything else (a raw list, or a Vega scheme name) is
    # passed through unchanged.
    for key in ("palette", "categoryPalette", "divergingPalette", "heatmapPalette", "ordinalPalette", "rampPalette"):
        val = p[key]
        p[key] = colors[val] if isinstance(val, str) and val in colors else val

    alt.theme.options = {**p, "tickWidth": p["axisWidth"]}


def _compute_derived(p: dict[str, Any]) -> None:
    """Resolve the derive-at-theme-time sentinels in *p* in place (None / True markers).

    Shared by :func:`theme` and the :func:`_opt` fallback so both resolve the same way.
    """
    # Computed defaults — None means "derive from other params"
    if p["closed"] is None:
        # inward ticks point into the plot, so they need a closed (non-offset) axis;
        # default closed=True when inwardTicks is set (an explicit closed=False still wins).
        p["closed"] = p["inwardTicks"] or p["viewFill"] is not None
    if p["markSize"] is None:
        p["markSize"] = min(p["chartWidth"], p["chartHeight"]) * 0.1
    if p["markStrokeWidth"] is None:
        p["markStrokeWidth"] = p["axisWidth"]
    if p["cornerRadius"] is True:
        p["cornerRadius"] = min(p["chartWidth"], p["chartHeight"]) / 100
    if p["boxplotOutliers"] is True:  # True → show at markSize/10; a number is an explicit size; False → hidden
        p["boxplotOutliers"] = p["markSize"] / 10
    # chartFill=None means "auto" (white in light mode, black in dark mode) and is resolved
    # at config-build time in _dysonsphere_theme(), NOT here - save() toggles darkmode per
    # background variant without re-running theme(), so the fill must follow darkmode live
    # (the same pattern as every other darkmode-aware colour).
    # Offset the axis line and legend from the plot by 1.5x the tick length — enough separation
    # to read as an intentional (Prism-style) detached axis, not a rendering gap. Resolved once
    # here (not inline at each use) so the axis config, legend config, and save()'s grid-span fix
    # all read one consistent value from alt.theme.options.
    if p["axisOffset"] is None:
        p["axisOffset"] = p["tickSize"] * 1.5
    if p["legendOffset"] is None:
        p["legendOffset"] = p["tickSize"] * 1.5
    # smallestFontSize is a fixed floor (5) and a minimize switch: True drops the whole
    # plot's base font to it; False / an int just leaves it retrievable.
    if p["smallestFontSize"] is True:
        p["smallestFontSize"] = 5
        p["fontSize"] = p["smallestFontSize"]
    elif p["smallestFontSize"] is False:
        p["smallestFontSize"] = 5
    if p["secondaryFontSize"] is None:
        p["secondaryFontSize"] = max(1, p["fontSize"] - 1)  # smaller tier for in-plot annotations
        if p["fontSize"] >= p["smallestFontSize"]:  # don't let the tier dip below the floor …
            p["secondaryFontSize"] = max(p["secondaryFontSize"], p["smallestFontSize"])
        # … unless the user explicitly set fontSize below the floor (escape hatch)


_FALLBACK_OPTIONS: dict[str, Any] | None = None


def _opt(key: str) -> Any:
    """Read a theme option, falling back to the (derived) built-in default.

    The single accessor for theme options outside theme.py — replaces scattered
    ``alt.theme.options.get(key, hardcoded)`` calls, whose per-site hardcoded fallbacks
    could silently drift from ``_BUILTIN_DEFAULTS``. After ``ds.theme()`` every option is
    present in ``alt.theme.options``, so the fallback only matters when a chart helper is
    called before any ``theme()``; it then sees the fully derived built-in defaults
    (``markSize`` 10.0, ``axisOffset`` 4.5, …), computed once and cached. Unknown keys
    raise ``KeyError``.
    """
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
    opts = alt.theme.options

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
    _cat = _scheme("categoryPalette", colors["categorical"])
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
                "innerRadius": min(opts["chartWidth"], opts["chartHeight"]) / 4,
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
                    "fill": opts["markMedianFill"],
                    "fillOpacity": opts["markFillOpacity"],
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
                "size": opts["markSize"] / 20,
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
                    "strokeOpacity": opts["markStrokeWidth"],
                    "strokeWidth": opts["markStrokeOpacity"],
                },
            },
            "errorbar": {
                "opacity": 1,
                "rule": {
                    "strokeDash": [0, 0],
                    "strokeWidth": opts["markStrokeWidth"] * 2,
                },
                "ticks": {
                    "color": "white" if opts["darkmode"] else "black",
                    "cornerRadius": opts["markStrokeWidth"],
                    "opacity": 1,
                    "size": opts["markSize"] * 0.6,
                    "thickness": opts["markStrokeWidth"] * 2,
                },
                "thickness": opts["markStrokeWidth"] * 2,
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
                "gradientLength": opts["markSize"] * 5,
                "gradientThickness": opts["markSize"] * 0.5,
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
                "strokeCap": opts["strokeCap"],
                "strokeDash": opts["dashedWidth"] if opts["dashedLine"] else [0, 0],
                "strokeOpacity": 1,
                "strokeWidth": opts["axisWidth"] * 1.5,
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
                "diverging": {"scheme": _scheme("divergingPalette", colors["pinksblues"])},
                "heatmap": {"scheme": _scheme("heatmapPalette", colors["blues"])},
                "ordinal": {"scheme": _scheme("ordinalPalette", colors["greys"])},
                "ramp": {"scheme": _scheme("rampPalette", colors["blues"])},
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
                "bandPaddingInner": opts["bandPadding"],
                "bandPaddingOuter": opts["bandPadding"],
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
                "subtitleFontSize": opts["font"],
                "subtitleFontStyle": opts["fontStyle"],
                "subtitleFontWeight": opts["fontWeight"],
            },
            "view": {
                "continuousWidth": opts["chartWidth"],
                "continuousHeight": opts["chartHeight"],
                "discreteWidth": opts["chartWidth"],
                "discreteHeight": opts["chartHeight"],
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
        print(f"dysonsphere.toml already exists at {dest} — not overwriting.")
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
        '# Custom palettes — lists of hex strings, available via ds.palette("name")',
        '# or ds.theme(palette="name"). dysonsphere palettes are typically 12 stops',
        "# for sequential palettes, and 13 stops for diverging palettes.",
        "",
        "[palettes]",
        '# my_palette = ["#DFE9F7", "#C6D9F1", "#ADC8EC", "#94B8E6", "#7AA8E0", "#6097DA", "#4D87CA", "#4177B1", "#386898", "#2F597F", "#264A69", "#1D3A58"]',  # noqa: E501
    ]

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Created {dest}")
