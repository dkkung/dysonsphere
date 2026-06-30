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
// Adobe Illustrator script to import dysonsphere palettes as named swatch groups.
// Also saves a 'dysonsphere' swatch library to your Illustrator User Defined folder.
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
    colorGroup.name = "dysonsphere " + paletteName;
    for (var i = 0; i < hexColors.length; i++) {{
        var rgb = hexToRGB(hexColors[i]);
        var color = new RGBColor();
        color.red = rgb[0];
        color.green = rgb[1];
        color.blue = rgb[2];
        var swatch = doc.swatches.add();
        swatch.name = "dysonsphere " + paletteName + " - " + i;
        swatch.color = color;
        colorGroup.addSwatch(swatch);
    }}
}}

var libSaved = false;
try {{
    var aiMajor = parseInt(app.version.split('.')[0]);
    var candidates = [
        new Folder(Folder.userData + "/Library/Application Support/Adobe/"
            + "Adobe Illustrator " + aiMajor + "/en_US/Swatches/"),
        new Folder(Folder.userData + "/Library/Application Support/Adobe/"
            + "Adobe Illustrator " + aiMajor + ".0/en_US/Swatches/"),
        new Folder(Folder.userData + "/Adobe/Adobe Illustrator " + aiMajor + " Settings/en_US/Swatches/"),
        new Folder(Folder.userData + "/Adobe/Adobe Illustrator " + aiMajor + ".0 Settings/en_US/Swatches/"),
    ];
    var swatchFolder = null;
    for (var k = 0; k < candidates.length; k++) {{
        if (candidates[k].exists) {{
            swatchFolder = candidates[k];
            break;
        }}
    }}
    if (swatchFolder !== null) {{
        var libDoc = app.documents.add(DocumentColorSpace.RGB);
        for (var pn in palettes) {{
            var hc = palettes[pn];
            var cg = libDoc.swatchGroups.add();
            cg.name = pn;
            for (var j = 0; j < hc.length; j++) {{
                var rgb2 = hexToRGB(hc[j]);
                var col = new RGBColor();
                col.red = rgb2[0];
                col.green = rgb2[1];
                col.blue = rgb2[2];
                var sw = libDoc.swatches.add();
                sw.name = pn + " - " + j;
                sw.color = col;
                cg.addSwatch(sw);
            }}
        }}
        var libFile = new File(swatchFolder.fsName + "/dysonsphere.ai");
        var saveOpts = new IllustratorSaveOptions();
        saveOpts.pdfCompatible = false;
        libDoc.saveAs(libFile, saveOpts);
        libDoc.close(SaveOptions.DONOTSAVECHANGES);
        libSaved = true;
    }}
}} catch (e) {{}}

if (libSaved) {{
    alert("Imported " + Object.keys(palettes).length + " palettes.\\n"
        + "Saved 'dysonsphere' to User Defined swatch libraries. "
        + "Restart Illustrator to see it under Open Swatch Library > User Defined.");
}} else {{
    alert("Imported " + Object.keys(palettes).length + " palettes.\\n"
        + "To save as a permanent library: Swatches panel menu"
        + " > Save Swatch Library as AI > name it 'dysonsphere'.");
}}
"""

    out = ROOT / "scripts" / "import_dysonsphere_palettes_to_illustrator.jsx"
    out.write_text(jsx)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
