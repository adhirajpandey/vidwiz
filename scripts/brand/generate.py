# /// script
# requires-python = ">=3.11"
# dependencies = ["fonttools==4.61.1", "uharfbuzz==0.53.3", "cairosvg==2.8.2", "pillow==12.1.0"]
# ///
"""Regenerate the web and extension branding: uv run scripts/brand/generate.py."""
from io import BytesIO
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

import cairosvg
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.boundsPen import BoundsPen
from PIL import Image
import uharfbuzz as hb

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "assets/brand"
PUBLIC = ROOT / "frontend/public"
BRAND = PUBLIC / "brand"
INK, WHITE, YELLOW = "#1B1D3A", "#FAFAFC", "#FFE45C"
SVG = '{http://www.w3.org/2000/svg}'


def svg(width, height, body, title):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" role="img"><title>{title}</title>{body}</svg>\n')


def body(path):
    root = ET.parse(path).getroot()
    # Strip namespace prefixes when embedding the trusted, local source artwork.
    for element in root.iter():
        element.tag = element.tag.removeprefix(SVG)
    return ''.join(ET.tostring(child, encoding='unicode') for child in root)


def raster(source, path, size):
    data = cairosvg.svg2png(bytestring=source.encode(), output_width=size[0] * 4,
                           output_height=size[1] * 4)
    image = Image.open(BytesIO(data)).resize(size, Image.Resampling.LANCZOS)
    if image.mode == "RGBA" and image.getchannel("A").getextrema() == (255, 255):
        image = image.convert("RGB")
    image.save(path)


class Lettering:
    """Shape the actual font, then export glyph outlines without font dependencies."""
    def __init__(self, optical_size, weight=800):
        self.font = instantiateVariableFont(TTFont(SOURCE / 'BricolageGrotesque.ttf'),
                                           {'opsz': optical_size, 'wdth': 85, 'wght': weight})
        self.glyphs = self.font.getGlyphSet()
        buffer = BytesIO()
        self.font.save(buffer)
        self.hbfont = hb.Font(hb.Face(buffer.getvalue()))
        self.upem = self.font['head'].unitsPerEm
        self.hbfont.scale = (self.upem, self.upem)

    def path(self, text, x, y, size, color, tracking=0):
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(self.hbfont, buf)
        scale = size / self.upem
        pen = SVGPathPen(self.glyphs)
        cursor = 0
        for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
            glyph = self.glyphs[self.font.getGlyphName(info.codepoint)]
            transform = (scale, 0, 0, -scale,
                         x + cursor + pos.x_offset * scale, y - pos.y_offset * scale)
            glyph.draw(TransformPen(pen, transform))
            # Check actual ink bounds, not just advances, before writing artwork.
            bounds = BoundsPen(self.glyphs)
            glyph.draw(TransformPen(bounds, transform))
            if bounds.bounds:
                left, top, right, bottom = bounds.bounds
                assert 0 <= left < right <= 1200 and 0 <= top < bottom <= 630, text
            cursor += pos.x_advance * scale + tracking
        return f'<path fill="{color}" d="{pen.getCommands()}"/>', cursor - tracking


def main():
    BRAND.mkdir(parents=True, exist_ok=True)
    for file in SOURCE.glob('vidwiz-mark-*.svg'):
        shutil.copyfile(file, BRAND / file.name)
    mark = body(SOURCE / 'vidwiz-mark-color.svg')
    raw = (SOURCE / 'vidwiz-mark-color.svg').read_text()
    for size in (16, 32, 48, 128, 192, 512):
        raster(raw, PUBLIC / f'icon-{size}.png', (size, size))
    Image.open(PUBLIC / 'icon-512.png').save(PUBLIC / 'favicon.ico',
                                            sizes=[(16, 16), (32, 32), (48, 48)])
    # The standard icon has rounded, transparent corners. Mobile exports have a
    # solid square background; platform launchers apply their own outer masks.
    symbols = mark.replace('<rect x="0" y="0" width="160" height="160" rx="34" fill="#1B1D3A" />', '')
    assert 'rx="34"' not in symbols
    for name, size, extent in [('apple-touch-icon.png', 180, 180),
                               ('icon-maskable-512.png', 512, 400)]:
        offset = (size - extent) / 2
        art = svg(size, size, f'<rect width="{size}" height="{size}" fill="{INK}"/>'
                  f'<g transform="translate({offset} {offset}) scale({extent / 160})">{symbols}</g>',
                  'VidWiz')
        raster(art, PUBLIC / name, (size, size))
    lettering = Lettering(64)
    for theme, color, tile in [('light', INK, mark),
                                ('dark', WHITE, body(SOURCE / 'vidwiz-mark-monochrome-white.svg'))]:
        # Preserve the supplied dark treatment's yellow bookmark.
        if theme == 'dark':
            tile = tile.replace('fill="white" /></g>', f'fill="{YELLOW}" /></g>')
        text, advance = lettering.path('VidWiz', 94, 72, 66, color, -1.5)
        width = round(94 + advance + 12)
        art = svg(width, 100, f'<g transform="translate(12 14) scale(0.45)">{tile}</g>{text}', 'VidWiz')
        (BRAND / f'vidwiz-wordmark-on-{theme}.svg').write_text(art)
    # Reference composition: identity on the left, timeline on the right.
    title, _ = Lettering(96).path('VidWiz', 208, 282, 128, WHITE, -2)
    tagline, width = Lettering(48, 700).path('Tap once. Find it later.', 88, 370, 52, WHITE, -0.5)
    assert width < 620
    timeline = ''
    for y, start, end, dots in [(217, 742, 1100, [842]),
                                (310, 770, 1130, [805, 935, 1075]),
                                (450, 744, 1130, [780, 916, 1038, 1092])]:
        timeline += f'<path d="M{start} {y}H{end}" fill="none" stroke="#6F748E" stroke-width="9" stroke-linecap="round"/>'
        for x in dots:
            timeline += f'<circle cx="{x}" cy="{y}" r="9" fill="#9399B0"/>'
    timeline += f'<path d="M980 398Q980 392 986 392H1002Q1008 392 1008 398V445L994 434L980 445Z" fill="{YELLOW}"/>'
    timeline += f'<circle cx="994" cy="450" r="9" fill="{YELLOW}"/>'
    social = svg(1200, 630, f'<rect width="1200" height="630" fill="{INK}"/>'
                 f'<g transform="translate(88 190) scale(0.6)">{mark}</g>{title}{tagline}{timeline}',
                 'VidWiz. Tap once. Find it later.')
    (BRAND / 'vidwiz-social.svg').write_text(social)
    raster(social, PUBLIC / 'og-image.png', (1200, 630))
    icons = ROOT / 'extension/icons'
    for size in (16, 48, 128):
        shutil.copyfile(PUBLIC / f'icon-{size}.png', icons / f'icon{size}.png')
    # The popup header shows the colour mark beside the name as live text, like the web app.
    shutil.copyfile(BRAND / 'vidwiz-mark-color.svg', icons / 'mark.svg')
    print('Generated web branding, favicon, mobile icons, social card, and extension assets.')


if __name__ == '__main__':
    main()
