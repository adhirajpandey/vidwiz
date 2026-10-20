# VidWiz brand assets

The primary mark is two white caption lines and a yellow bookmark on an ink
tile. Use the same geometry for the website, browser icons, and extension.

| Asset | Use |
| --- | --- |
| `frontend/public/brand/vidwiz-mark-color.svg` | Navigation, landing page, and sign-in pages |
| `frontend/public/brand/vidwiz-mark-monochrome-ink.svg` | Single-color artwork on light backgrounds |
| `frontend/public/brand/vidwiz-mark-monochrome-white.svg` | Single-color artwork on dark backgrounds |
| `frontend/public/brand/vidwiz-wordmark-on-light.svg` | Horizontal logo on light backgrounds |
| `frontend/public/brand/vidwiz-wordmark-on-dark.svg` | Horizontal logo on dark backgrounds; white frame and yellow bookmark |
| `frontend/public/favicon.ico`, `icon-16.png`, `icon-32.png` | Browser tabs and bookmarks |
| `frontend/public/icon-192.png`, `icon-512.png` | Standard web manifest icons, purpose `any` |
| `frontend/public/icon-maskable-512.png` | Separate full-bleed manifest icon, purpose `maskable` |
| `frontend/public/apple-touch-icon.png` | Opaque 180 x 180 Apple touch icon |
| `frontend/public/og-image.png` | 1200 x 630 social preview, shared by Open Graph and Twitter metadata |
| `frontend/public/brand/vidwiz-social.svg` | Portable outlined source for the social preview |
| `extension/icons/icon16.png`, `icon48.png`, `icon128.png` | Extension toolbar, management, and package icons |
| `extension/icons/wordmark-on-light.svg`, `wordmark-on-dark.svg` | Popup branding, selected by OS color scheme |

The 48 and 128 px web PNGs are also retained as reusable exports. Rounded
standard icons have transparent corners. Apple and maskable icons have a solid
ink background without baked-in outer corners. The maskable symbol fits inside
the central circle with a radius of 40% of the canvas width.

Ink is `#1B1D3A`, caption yellow is `#FFE45C`, and white is `#FAFAFC`.
Single-color marks use outlines on transparent backgrounds. Navigation keeps
live text beside the primary SVG; static wordmarks contain outlined lettering.

## Regenerate the assets

From the repository root, run:

```sh
uv run scripts/brand/generate.py
```

The generator pins its Python dependencies in its script header. CairoSVG also
requires the Cairo system library. Generation uses the checked-in SVG originals
and font in `assets/brand/`; no network font fetch is needed. It writes the web
exports and matching extension assets together.

The supplied wordmarks' original typeface was unverified. Both wordmarks and the
social card were rebuilt from the actual Bricolage Grotesque variable font,
using HarfBuzz shaping and SVG glyph outlines. Wordmarks use weight 800, width
85, and optical size 64. The social title uses weight 800, width 85, and optical
size 96; its tagline uses weight 700, width 85, and optical size 48. Exported
SVGs contain no live text, imported fonts, or raster images.

The font comes from the [Google Fonts Bricolage Grotesque directory](https://github.com/google/fonts/tree/main/ofl/bricolagegrotesque).
The checked-in font has SHA-256
`413e7357809ddd12fd80a96a8a396de0e401638d4acd3cb3e37532f0472ac682`.
Its SIL Open Font License is included as `assets/brand/OFL.txt`. Font bytes are
used only during generation and are not bundled into the web or extension.

After regeneration, check small icons at actual size, light and dark
wordmarks, the mobile mask safe zone, and social-card legibility. Run the
frontend build and build the extension into a temporary output directory.
Asset integration does not change capture behavior or the PWA share target.
