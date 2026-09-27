# dysonsphere — vector brand kit

Tagline: **SCIENTIFIC PLOTTING**

The tagline is centered on the visible wordmark, not on the combined emblem-and-wordmark block. The approved panel/orbit concept has been redrawn as clean Bézier paths with consistent geometry across every variant. The PNG concept was not an original vector source; tiny contour differences are expected in this clean reconstruction.

## Start here

- `svg/dysonsphere-light.svg`: indigo and amber, for a light background.
- `svg/dysonsphere-dark.svg`: white and amber, for a dark background.
- `svg/dysonsphere-mono-black.svg`: genuinely single-color black.
- `svg/dysonsphere-mono-white.svg`: genuinely single-color white.
- `dysonsphere-brand-board.svg`: the complete editable presentation board.

These files have transparent backgrounds. In particular, white variants may look blank in a white-background preview; place them on a dark surface. The board and app icons intentionally have backgrounds.

## Vector and editing details

The artwork consists of vector paths and a circular sun, not a PNG wrapped in an SVG. The primary files have outlined lettering and no external images, fonts, scripts, or linked dependencies. Colors and Bézier geometry remain editable. Separate groups identify the emblem, wordmark, and tagline. This is an SVG delivery, not a native `.ai` document.

The custom wordmark is outlined artwork, not a bundled font. `source/dysonsphere-editable-tagline.svg` additionally supplies a live-text tagline for future edits, with Inter Display Medium preferred and Inter or Arial as fallbacks. Font files are not included; install the preferred font to preserve that live-text source's exact typesetting. All production SVGs already have the correct outlined tagline and require no font installation.

## Palette

- Primary indigo: `#28287D`
- Sun / amber accent: `#F5A623`
- Supporting cool gray: `#CBD5E1`
- Dark preview surface: `#191D28`
- Light-mode tagline: `#64748B` (a darker supporting slate, not a change to the gray brand swatch)

The logo is flat color, with no generated shading, glow, or simulated paper texture. Monochrome means all artwork, including the sun and tagline, uses one ink.

## Additional versions

The `svg/` folder includes lockups without taglines, isolated wordmarks, transparent emblems, and light/dark app icons. The same exact master shapes are shared by the light, dark, and monochrome logo variants.

The `png/` folder supplies transparent high-resolution exports. Main lockups are 2160 × 750 pixels and isolated icons are 1024 × 1024 pixels.

## Favicons

`favicons/favicon.svg` and `favicons/favicon.ico` use a white-and-amber emblem on the indigo tile. The panel details are optically simplified for small sizes. Light-background equivalents are also included. ICO files contain 16, 24, 32, 48, 64, 128, and 256 pixel images. App-icon PNGs are supplied at 180, 192, and 512 pixels.

Example HTML (adjust paths to your site):

```html
<link rel="icon" href="/assets/favicon.svg" type="image/svg+xml">
<link rel="icon" href="/assets/favicon.ico" sizes="any">
<link rel="apple-touch-icon" href="/assets/apple-touch-icon.png">
```

For small placements, choose the no-tagline lockup or isolated icon instead of shrinking the entire tagline lockup. Keep the panel gaps open, preserve the aspect ratio, and do not recolor the amber sun in the full-color variants.
