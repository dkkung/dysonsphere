#!/usr/bin/env python
"""Generate the config-generator page's inputs from the library.

Writes two build inputs for ConfigGenerator.astro:

- ``website/src/generated/default_config.toml`` - the exact file ``ds.create_config()``
  scaffolds (the honest starting point for edits).
- ``website/src/generated/theme_defaults.json`` - the ``ds.theme()`` parameter cheat sheet:
  every ``_BUILTIN_DEFAULTS`` key with its default rendered as a TOML value (``null`` for the
  ``None`` sentinels that are derived at theme() time).

Run from the repo/worktree root:

    uv run python website/scripts/gen_config.py
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import dysonsphere as ds
from dysonsphere.theme import _BUILTIN_DEFAULTS

OUT = Path("website/src/generated")

# One-line hints for the derived (None-default) sentinels, so the cheat sheet can say what
# "auto" resolves to instead of showing nothing.
AUTO_HINTS = {
    "axisOffset": "auto: tickSize * 1.5",
    "chartFill": "auto: white / black by darkmode",
    "closed": "auto: True when inwardTicks or viewFill",
    "legendOffset": "auto: tickSize * 1.5",
    "markSize": "auto: min(chartWidth, chartHeight) / 10",
    "markStrokeWidth": "auto: axisWidth",
    "secondaryFontSize": "auto: fontSize - 1 (floored)",
    "palette": "auto: per-type defaults",
    "categoryPalette": "auto: categorical",
    "divergingPalette": "auto: built-in default",
    "heatmapPalette": "auto: built-in default",
    "ordinalPalette": "auto: greys",
    "rampPalette": "auto: built-in default",
    "viewFill": "auto: none",
}


def toml_value(v: object) -> str | None:
    """Render a Python default as a TOML literal (None -> no literal; it is derived)."""
    if v is None:
        return None
    if isinstance(v, bool):
        return "true" if v else "false"
    # json.dumps covers ints, floats, double-quoted strings, and flat lists - all valid TOML.
    return json.dumps(v)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as d:
        ds.create_config(d)
        toml_text = (Path(d) / "dysonsphere.toml").read_text(encoding="utf-8")
    (OUT / "default_config.toml").write_text(toml_text, encoding="utf-8")
    print(f"wrote {OUT / 'default_config.toml'}  ({len(toml_text.splitlines())} lines)")

    params = [
        {"key": k, "default": toml_value(v), "hint": AUTO_HINTS.get(k)}
        for k, v in _BUILTIN_DEFAULTS.items()
    ]
    (OUT / "theme_defaults.json").write_text(
        json.dumps(params, indent=1, ensure_ascii=False), encoding="utf-8"
    )
    print(f"wrote {OUT / 'theme_defaults.json'}  ({len(params)} parameters)")


if __name__ == "__main__":
    main()
