"""把 src/scene_template.html 打包成单文件 HTML，并生成一张静态预览图。

素材（立绘、音乐）不随仓库分发，按 assets/README.md 放好后运行：
    python tools/build_scene.py
产物默认写到 build/，可用环境变量覆盖：
    DUEL_ASSETS  素材目录      DUEL_BUILD  输出目录
    DUEL_P1/P2   两张立绘      DUEL_FONT   像素字体文件
    DUEL_BGM     循环 BGM       DUEL_END    倒地音乐
"""
import base64
import io
import math
import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ASSETS = os.environ.get('DUEL_ASSETS', os.path.join(ROOT, 'assets'))
BUILD = os.environ.get('DUEL_BUILD', os.path.join(ROOT, 'build'))
os.makedirs(BUILD, exist_ok=True)

T = os.path.join(ROOT, 'src', 'scene_template.html')
OUT = os.path.join(BUILD, 'duel_4x3.html')
PREVIEW = os.path.join(BUILD, 'preview.png')

p1 = os.environ.get('DUEL_P1', os.path.join(ASSETS, 'p1.png'))
p2 = os.environ.get('DUEL_P2', os.path.join(ASSETS, 'p2.png'))
A_BGM = os.environ.get('DUEL_BGM', os.path.join(ASSETS, 'bgm.mp3'))
A_END = os.environ.get('DUEL_END', os.path.join(ASSETS, 'end.mp3'))


def _load_font(size):
    for path in (os.environ.get('DUEL_FONT'),
                 r'C:/Windows/Fonts/simsun.ttc',
                 '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'):
        if path and os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def full(path, maxside=640):
    im = Image.open(path).convert('RGBA')
    im.thumbnail((maxside, maxside), Image.LANCZOS)
    return im


def subject_rect(path):
    im = Image.open(path).convert('RGBA')
    w, h = im.size
    bb = im.getchannel('A').point(lambda p: 255 if p > 60 else 0).getbbox()
    return [round(bb[0] / w, 4), round(bb[1] / h, 4),
            round((bb[2] - bb[0]) / w, 4), round((bb[3] - bb[1]) / h, 4)]


def data_uri(im):
    buf = io.BytesIO()
    try:
        im.save(buf, format='WEBP', quality=90, method=6)
        mime = 'image/webp'
    except Exception:
        im.save(buf, format='PNG', optimize=True)
        mime = 'image/png'
    raw = buf.getvalue()
    return 'data:' + mime + ';base64,' + base64.b64encode(raw).decode('ascii'), len(raw)


assets = {
    '__IMG_FULL_1__': full(p1),
    '__IMG_FULL_2__': full(p2),
}

with open(T, encoding='utf-8') as f:
    html = f.read()

for key, im in assets.items():
    assert key in html, 'missing placeholder: ' + key
    uri, size = data_uri(im)
    html = html.replace(key, uri)
    print(key, im.size, size, 'bytes')

for key, path in [('__BGM_B64__', A_BGM), ('__END_B64__', A_END)]:
    assert key in html, 'missing placeholder: ' + key
    with open(path, 'rb') as f:
        raw = f.read()
    b64 = base64.b64encode(raw).decode('ascii')
    html = html.replace(key, b64)
    print(key, os.path.basename(path), len(raw), 'bytes ->', len(b64), 'base64 chars')

rects = [subject_rect(p1), subject_rect(p2)]
html = html.replace('__RECT1__', repr(rects[0])).replace('__RECT2__', repr(rects[1]))
print('subject rects:', rects)
assert not any(k in html for k in ['__IMG_', '__RECT', '__BGM_B64__', '__END_B64__']), 'unreplaced placeholder remains'
with open(OUT, 'w', encoding='utf-8') as f:
    f.write(html)
print('output:', OUT)
print('html size:', os.path.getsize(OUT), 'bytes')

W, H = 840, 630
r = min(W, H) * 0.09


def lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def cubic(p0, p1, p2, p3, n=48):
    pts = []
    for i in range(n + 1):
        t = i / n
        u = 1 - t
        pts.append((u ** 3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t ** 3 * p3[0],
                    u ** 3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t ** 3 * p3[1]))
    return pts


def backdrop(w, h):
    stops = [(0.0, (142, 18, 32)), (0.48, (196, 33, 53)), (1.0, (121, 15, 29))]
    bg = Image.new('RGBA', (w, h))
    d = ImageDraw.Draw(bg)
    for y in range(h):
        t = y / max(1, h - 1)
        if t <= stops[1][0]:
            c = lerp(stops[0][1], stops[1][1], t / stops[1][0])
        else:
            c = lerp(stops[1][1], stops[2][1], (t - stops[1][0]) / (1 - stops[1][0]))
        d.line((0, y, w, y), fill=c + (255,))

    sw, sh = 96, 72
    glow = Image.new('RGBA', (sw, sh), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for y in range(sh):
        for x in range(sw):
            dist = math.hypot((x - sw / 2) / (sw / 2), (y - sh / 2) / (sh / 2)) / 1.4
            a = int(76 * max(0.0, 1.0 - dist))
            gd.point((x, y), fill=(255, 158, 184, a))
    bg.alpha_composite(glow.resize((w, h), Image.BICUBIC))

    cx, cy, s = w / 2, h / 2, min(w, h) * 0.31
    start = (cx, cy + s * 0.86)
    notch = (cx, cy - s * 0.34)
    pts = cubic(start, (cx - s * 1.28, cy - s * 0.10), (cx - s * 0.56, cy - s * 1.02), notch)
    pts += cubic(notch, (cx + s * 0.56, cy - s * 1.02), (cx + s * 1.28, cy - s * 0.10), start)

    blur_layer = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(blur_layer).polygon(pts, fill=(255, 142, 184, 190))
    bg.alpha_composite(blur_layer.filter(ImageFilter.GaussianBlur(28)))
    heart = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    hd = ImageDraw.Draw(heart)
    hd.polygon(pts, fill=(255, 158, 196, 168))
    hd.line(pts + [pts[0]], fill=(255, 236, 245, 190), width=4, joint='curve')
    bg.alpha_composite(heart)

    vig = Image.new('RGBA', (sw, sh), (0, 0, 0, 0))
    vd = ImageDraw.Draw(vig)
    for y in range(sh):
        for x in range(sw):
            dist = math.hypot((x - sw / 2) / (sw / 2), (y - sh / 2) / (sh / 2))
            a = int(86 * max(0.0, min(1.0, (dist - 0.55) / 0.85)))
            vd.point((x, y), fill=(40, 0, 10, a))
    bg.alpha_composite(vig.resize((w, h), Image.BICUBIC))
    return bg


board = backdrop(W, H)
d = ImageDraw.Draw(board)
d.rectangle((0, 0, W - 1, H - 1), outline=(90, 16, 28, 255), width=2)
items = [
    (assets['__IMG_FULL_1__'], 0.26, 0.32, rects[0], 1.0, (255, 150, 165, 190)),
    (assets['__IMG_FULL_2__'], 0.74, 0.68, rects[1], 0.96, (150, 205, 255, 190)),
]
for im, fx, fy, q, scale, ring in items:
    iw, ih = im.size
    crop = im.crop((int(q[0] * iw), int(q[1] * ih),
                    int((q[0] + q[2]) * iw), int((q[1] + q[3]) * ih)))
    cw, ch = crop.size
    t = 2 * r * scale
    k = min(t / cw, t / ch)
    dw, dh = int(cw * k), int(ch * k)
    rs = crop.resize((dw, dh), Image.LANCZOS)
    cx, cy = fx * W, fy * H
    board.alpha_composite(rs, (int(cx - dw / 2), int(cy - dh / 2)))
    d = ImageDraw.Draw(board)
    MAX_HP, bar_h, gap = 15, 14, 2
    bar_w = max(2 * r, min(W, H) * 0.22)
    cell = (bar_w - gap * (MAX_HP - 1)) / MAX_HP
    bx, by = cx - bar_w / 2, cy - dh / 2 - 26
    d.rectangle((bx - 2, by - 2, bx + bar_w + 2, by + bar_h + 2), fill=(255, 240, 244))
    d.rectangle((bx, by, bx + bar_w, by + bar_h), fill=(231, 217, 221), outline=(31, 35, 40), width=2)
    for seg in range(MAX_HP):
        x0 = bx + seg * (cell + gap)
        d.rectangle((x0, by, x0 + cell, by + bar_h), fill=(226, 75, 74))
    for i in range(0, 72, 2):
        a0, a1 = 2 * math.pi * i / 72, 2 * math.pi * (i + 1) / 72
        d.arc((cx - r, cy - r, cx + r, cy + r),
              a0 * 180 / math.pi, a1 * 180 / math.pi, fill=ring, width=2)

font = _load_font(15)


BIGFONT = _load_font(60)


def pixel_char(ch, color, size=30):
    # 先按 4 倍分辨率绘制，再整数倍缩小，得到清晰的像素字而不是糊边
    g = Image.new('RGBA', (80, 80), (0, 0, 0, 0))
    gd = ImageDraw.Draw(g)
    gd.text((40, 40), ch, font=BIGFONT, anchor='mm', fill=color,
            stroke_width=3, stroke_fill=(31, 35, 40, 235))
    return g.resize((size, size), Image.NEAREST)


shots = [
    (0.26 * W, 0.32 * H, 148, 201, '1', '还', (255, 108, 108, 255)),
    (0.74 * W, 0.68 * H, -179, -147, '我', '们', (120, 190, 255, 255)),
]


def paste(im, x, y):
    x, y = int(x), int(y)
    ox, oy = max(0, -x), max(0, -y)
    c = im.crop((ox, oy, min(im.width, board.width - x), min(im.height, board.height - y)))
    if c.width > 0 and c.height > 0:
        board.alpha_composite(c, (max(0, x), max(0, y)))


for cx, cy, vx, vy, c1, c2, color in shots:
    m = math.hypot(vx, vy)
    ux, uy = vx / m, vy / m
    d = ImageDraw.Draw(board)
    ring_x, ring_y = cx + ux * r * 0.9, cy + uy * r * 0.9
    for i in range(0, 48, 2):
        a0, a1 = 2 * math.pi * i / 48, 2 * math.pi * (i + 1) / 48
        d.arc((ring_x - r * 0.7, ring_y - r * 0.7, ring_x + r * 0.7, ring_y + r * 0.7),
              a0 * 180 / math.pi, a1 * 180 / math.pi, fill=color[:3] + (170,), width=2)
    for n in range(6):
        ang = math.atan2(uy, ux) + (n - 2.5) * 0.22
        sx = ring_x + math.cos(ang) * (r * 0.85 + n * 3)
        sy = ring_y + math.sin(ang) * (r * 0.85 + n * 3)
        s = 3 + n % 3
        d.rectangle((sx, sy, sx + s, sy + s), fill=color[:3] + (220,))
    for ch, dist, boost, lane in [(c1, 150, False, 72), (c2, 168, True, -72)]:
        size = 40 if boost else 28
        g = pixel_char(ch, color, size)
        bx, by = cx + ux * dist - uy * lane, cy + uy * dist + ux * lane
        for t in range(0):
            ts = int(size * (0.66 + 0.12 * t))
            ghost = pixel_char(ch, color[:3] + (int(48 / t),), ts)
            gx, gy = bx - ux * (size * 0.55 * t), by - uy * (size * 0.55 * t)
            paste(ghost, gx - ts / 2, gy - ts / 2)
        px, py = int(bx - size / 2), int(by - size / 2)
        paste(g, px, py)
        if boost:
            d = ImageDraw.Draw(board)
            glow = Image.new('RGBA', (size * 3, size * 3), (0, 0, 0, 0))
            gd2 = ImageDraw.Draw(glow)
            gd2.ellipse((size * 0.55, size * 0.55, size * 2.45, size * 2.45),
                        fill=color[:3] + (70,))
            glow = glow.filter(ImageFilter.GaussianBlur(3))
            board.alpha_composite(glow, (int(px - size), int(py - size)))

# —— 情种1 冲击波：多层扩散环 + 最大范围虚线 + 径向短划线 ——
d = ImageDraw.Draw(board)
sx, sy = 0.26 * W, 0.32 * H
max_r = min(W, H) * 0.58
for rad, col, wd in [(max_r * 0.42, (255, 240, 246, 235), 5), (max_r * 0.68, (255, 158, 196, 155), 3)]:
    d.ellipse((sx - rad, sy - rad, sx + rad, sy + rad), outline=col, width=wd)
for i in range(0, 72, 2):
    a0, a1 = 2 * math.pi * i / 72, 2 * math.pi * (i + 1) / 72
    d.arc((sx - max_r, sy - max_r, sx + max_r, sy + max_r),
          a0 * 180 / math.pi, a1 * 180 / math.pi, fill=(255, 231, 240, 95), width=2)
for n in range(12):
    a = n * math.pi / 6
    rr = max_r * 0.68
    d.line((sx + math.cos(a) * (rr - 15), sy + math.sin(a) * (rr - 15),
            sx + math.cos(a) * rr, sy + math.sin(a) * rr),
           fill=(255, 240, 246, 205), width=3)

# —— 情种2 爱心炮：像素爱心弹 + 拖尾 ——
HEART = ['01100110', '11111111', '11111111', '01111110', '00111100', '00011000']


def pixel_heart(cx, cy, cell, color):
    for yy, row in enumerate(HEART):
        for xx, v in enumerate(row):
            if v != '1':
                continue
            x0, y0 = cx - 4 * cell + xx * cell, cy - 3 * cell + yy * cell
            d.rectangle((x0, y0, x0 + cell - 1, y0 + cell - 1), fill=(140, 20, 40, 255))
    for yy in range(len(HEART) - 1):
        for xx, v in enumerate(HEART[yy]):
            if v != '1':
                continue
            x0, y0 = cx - 4 * cell + xx * cell, cy - 3 * cell + yy * cell
            d.rectangle((x0, y0, x0 + cell - 1, y0 + cell - 1), fill=color)


hx0, hy0 = 0.74 * W, 0.68 * H
dx, dy = sx - hx0, sy - hy0
m = math.hypot(dx, dy)
ux, uy = dx / m, dy / m
px, py = -uy, ux
ctrl = (hx0 + dx * 0.5 + px * 150, hy0 + dy * 0.5 + py * 150)


def bez(t):
    u = 1 - t
    return (u * u * hx0 + 2 * u * t * ctrl[0] + t * t * sx,
            u * u * hy0 + 2 * u * t * ctrl[1] + t * t * sy)


for idx, (t, cell, alpha) in enumerate([(0.34, 5, 0.5), (0.52, 7, 0.75), (0.7, 9, 1.0)]):
    col = (255, 90, 145, int(245 * alpha))
    for k in range(3, 0, -1):
        tt = max(0.0, t - 0.06 * k)
        gx, gy = bez(tt)
        c2 = max(2, int(cell * (0.5 + 0.15 * k)))
        pixel_heart(gx, gy, c2, (255, 111, 156, int(90 / k)))
    gx, gy = bez(t)
    pixel_heart(gx, gy, cell, col)
    d = ImageDraw.Draw(board)
    d.rectangle((gx - 2 * cell, gy - 2 * cell, gx - cell, gy - 2 * cell + cell),
                fill=(255, 240, 246, int(230 * alpha)))

board.convert('RGB').save(PREVIEW)
print('preview:', PREVIEW, board.size)
