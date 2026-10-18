"""Export approved artwork to platform sizes without redrawing its design."""
from __future__ import annotations
import base64
from io import BytesIO
from math import hypot
from pathlib import Path
import json
import xml.etree.ElementTree as ET
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
BRAND = ROOT / 'assets/branding/pulse-cards'
WEB = ROOT / 'web/public'
RES = ROOT / 'app/android/app/src/main/res'
FILTER = Image.Resampling.LANCZOS

def save_png(image: Image.Image, target: Path, size: int) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    image.resize((size, size), FILTER).save(target, optimize=True)

def gradient(size: int) -> Image.Image:
    start, end = (14, 180, 158), (0, 90, 102)
    result = Image.new('RGBA', (size, size))
    result.putdata([
        tuple(round(a + (b - a) * (x + y) / (2 * (size - 1))) for a, b in zip(start, end)) + (255,)
        for y in range(size) for x in range(size)
    ])
    return result

def fitted_foreground(source: Image.Image, size: int, radius: float) -> Image.Image:
    """Fit opaque artwork inside the platform's circular safe area."""
    alpha = source.getchannel('A')
    opaque = alpha.point(lambda value: 255 if value >= 240 else 0)
    bounds = opaque.getbbox()
    if bounds is None:
        raise ValueError('Foreground contains no opaque artwork')
    left, top, right, bottom = bounds
    center_x, center_y = (left + right - 1) / 2, (top + bottom - 1) / 2
    pixels = opaque.load()
    maximum = max(
        hypot(x - center_x, y - center_y)
        for y in range(top, bottom) for x in range(left, right) if pixels[x, y]
    )
    scale = radius / maximum
    resized = source.resize((round(source.width * scale), round(source.height * scale)), FILTER)
    output = Image.new('RGBA', (size, size))
    output.alpha_composite(resized, (round(size / 2 - center_x * scale), round(size / 2 - center_y * scale)))
    return output

def data_url(image: Image.Image) -> str:
    stream = BytesIO()
    image.save(stream, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(stream.getvalue()).decode('ascii')

def main() -> None:
    master = Image.open(BRAND / 'master.png').convert('RGB')
    foreground = Image.open(BRAND / 'cards-transparent.png').convert('RGBA')
    if foreground.getchannel('A').getextrema() != (0, 255):
        raise ValueError('Adaptive foreground must have actual transparent and opaque pixels')
    for name, size in {
        'favicon-pulse-32.png': 32, 'brand-pulse-192.png': 192,
        'apple-touch-icon.png': 180, 'icon-pulse-192.png': 192, 'icon-pulse-512.png': 512,
    }.items():
        save_png(master, WEB / name, size)
    master.save(WEB / 'favicon.ico', format='ICO', sizes=[(16, 16), (32, 32), (48, 48)])
    embedded = data_url(master.resize((64, 64), FILTER))
    (WEB / 'favicon.svg').write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><image width="64" height="64" href="{embedded}"/></svg>\n', encoding='utf-8')
    maskable = gradient(512)
    maskable.alpha_composite(fitted_foreground(foreground, 512, 512 * .38))
    maskable.convert('RGB').save(WEB / 'icon-pulse-maskable-512.png', optimize=True)
    save_png(master, ROOT / 'app/assets/branding/pulse-cards.png', 512)
    for density, launcher_size, adaptive_size in [
        ('mdpi', 48, 108), ('hdpi', 72, 162), ('xhdpi', 96, 216),
        ('xxhdpi', 144, 324), ('xxxhdpi', 192, 432),
    ]:
        save_png(master, RES / f'mipmap-{density}/ic_launcher.png', launcher_size)
        target = RES / f'drawable-{density}/ic_launcher_foreground.png'
        target.parent.mkdir(parents=True, exist_ok=True)
        fitted_foreground(foreground, adaptive_size, adaptive_size * 30.5 / 108).save(target, optimize=True)
    adaptive = Image.open(RES / 'drawable-xxxhdpi/ic_launcher_foreground.png')
    preview = ROOT / 'tmp/pulse-icon-release/preview'
    preview.mkdir(parents=True, exist_ok=True)
    main_url, adaptive_url = data_url(master.resize((256, 256), FILTER)), data_url(adaptive)
    images = ''.join(
        f'<div><img src="{main_url}" style="width:{size}px;height:{size}px;border-radius:{round(size*.23)}px"><small>{size}px</small></div>'
        for size in (128, 64, 48, 32, 16))
    masks = ''.join(
        f'<div><div class="adaptive" style="border-radius:{radius}"><img src="{adaptive_url}"></div><small>{label}</small></div>'
        for radius, label in [('50%', '圆形'), ('24%', '圆角方形'), ('8%', '方形')])
    android = '{http://schemas.android.com/apk/res/android}'
    vector = ET.parse(RES / 'drawable/ic_launcher_monochrome.xml').getroot()
    paths = ''.join(f'<path fill="white" fill-rule="evenodd" d="{path.attrib[android + "pathData"]}"/>' for path in vector)
    mono = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 108 108">{paths}</svg>'
    mono_url = 'data:image/svg+xml;base64,' + base64.b64encode(mono.encode('utf-8')).decode('ascii')
    themed = f'<div><div class="adaptive" style="border-radius:24%;background:#26534c"><img src="{mono_url}"></div><small>单色主题图标</small></div>'
    html = f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>医学知识库 · 图标检查</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#101b22;color:#eef5f3;font:16px system-ui;padding:36px}}main{{max-width:850px;margin:auto}}h1{{font-size:23px}}h2{{font-size:17px;margin-top:32px}}.row{{display:flex;gap:28px;align-items:center;flex-wrap:wrap;background:#1b2b32;padding:28px;border-radius:22px}}.row>div{{text-align:center}}small{{display:block;color:#b8c9c9;margin-top:12px}}img{{display:block}}.adaptive{{width:96px;height:96px;position:relative;overflow:hidden;background:linear-gradient(135deg,#0eb49e,#005a66)}}.adaptive img{{position:absolute;width:150%;height:150%;left:-25%;top:-25%}}.light{{background:#eff4f1;color:#193e3b}}.light small{{color:#45615e}}</style>
<main><h1>医学知识库 · 心电复习卡</h1><h2>网页与应用图标尺寸</h2><section class="row">{images}</section><h2>Android 自适应裁切</h2><section class="row">{masks}{themed}</section><h2>浅色背景</h2><section class="row light">{images}</section></main></html>'''
    (preview / 'index.html').write_text(html, encoding='utf-8')
    print(json.dumps({'master': str(BRAND / 'master.png'), 'adaptive_safe_radius_dp': 30.5, 'maskable_safe_radius': .38, 'preview': str(preview / 'index.html')}, ensure_ascii=False))

if __name__ == '__main__':
    main()
