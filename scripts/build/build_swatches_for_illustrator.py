"""
Generates import_palettes_to_illustrator.jsx — an Adobe Illustrator ExtendScript
that adds all palettes from theme/palettes.py as named swatch groups.

Usage:
    python scripts/build/make_palettes_illustrator.py
"""

import json
import pathlib

from dysonsphere.palettes import colors

ROOT = pathlib.Path(__file__).resolve().parents[2]


def main():
    js_palettes = json.dumps(colors, indent=4)

    jsx = f"""\
// Adobe Illustrator script to import palettes as named swatch groups.
// Run via File > Scripts > Other Script...
var doc = app.documents.length > 0 ? app.activeDocument : app.documents.add();

function hexToRGB(hex) {{
    hex = hex.replace('#', '');
    return [
        parseInt(hex.substring(0, 2), 16),
        parseInt(hex.substring(2, 4), 16),
        parseInt(hex.substring(4, 6), 16),
    ];
}}

var palettes = {js_palettes};

for (var paletteName in palettes) {{
    var hexColors = palettes[paletteName];
    var colorGroup = doc.swatchGroups.add();
    colorGroup.name = paletteName;
    for (var i = 0; i < hexColors.length; i++) {{
        var rgb = hexToRGB(hexColors[i]);
        var color = new RGBColor();
        color.red = rgb[0];
        color.green = rgb[1];
        color.blue = rgb[2];
        var swatch = doc.swatches.add();
        swatch.name = paletteName + " - " + i;
        swatch.color = color;
        colorGroup.addSwatch(swatch);
    }}
}}

alert("Imported " + Object.keys(palettes).length + " palettes.");
"""

    out = ROOT / "scripts" / "import_dysonsphere_palettes_to_illustrator.jsx"
    out.write_text(jsx)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
