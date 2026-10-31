"""Генерация картинки-«билета» для найденного ника (бренд RAVVO)."""
import hashlib
import io
import random
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

import generator

BRAND = "RAVVO"
W, H = 1280, 640
S = 2  # суперсэмплинг для гладких краёв

BG = (16, 16, 18)
PAPER = (244, 241, 234)
INK = (17, 17, 20)
BLUE = (47, 75, 255)
GREY = (222, 220, 214)
LINE = (200, 198, 192)
GREEN = (34, 160, 90)

FONT_DIR = Path(__file__).resolve().parent / "assets" / "fonts"
_fonts: dict = {}
_DICT: set[str] | None = None


def font(weight: str, size: int) -> ImageFont.FreeTypeFont:
    key = (weight, size)
    if key not in _fonts:
        _fonts[key] = ImageFont.truetype(str(FONT_DIR / f"Inter-{weight}.otf"), size * S)
    return _fonts[key]


# ------------------------------- оценка ника ---------------------------------
VOW = set("aeiou")


def _dictionary() -> set[str]:
    global _DICT
    if _DICT is None:
        _DICT = set(generator.dictionary_words(5)) | set(generator.dictionary_words(6))
    return _DICT


def scores(name: str) -> tuple[int, int]:
    """(читаемость 1-10, ликвидность 1-10). Эвристика, не рыночная цена."""
    n = name.lower()
    if n in _dictionary():
        read, liq = 10, 9
    else:
        kinds = [c in VOW for c in n]
        vowels = sum(kinds)
        alternations = sum(1 for a, b in zip(kinds, kinds[1:]) if a != b)
        run, worst = 0, 0
        for k in kinds:
            run = 0 if k else run + 1
            worst = max(worst, run)
        read = 2 + alternations
        if vowels == 0:
            read = 1
        if worst >= 3:
            read -= 2
        if any(a == b for a, b in zip(n, n[1:])):
            read -= 1
        if any(c in "qxzjwk" for c in n):
            read -= 1
        read = max(1, min(8, read))
        liq = max(1, min(8, read - 1 + (1 if len(n) == 5 else 0)))
    return read, liq


_PRICE_5 = {1: (5, 9), 2: (7, 13), 3: (10, 18), 4: (14, 25), 5: (25, 45),
            6: (45, 90), 7: (90, 200), 8: (200, 500), 9: (500, 1500), 10: (1500, 5000)}


def price_range(name: str, liq: int) -> tuple[int, int]:
    lo, hi = _PRICE_5[liq]
    if len(name) >= 6:
        lo, hi = max(1, round(lo * 0.45)), max(2, round(hi * 0.45))
    return lo, hi


# -------------------------------- рисование ----------------------------------
def _star(d: ImageDraw.ImageDraw, cx: float, cy: float, r: float, fill) -> None:
    k = r * 0.22
    pts = [(cx, cy - r), (cx + k, cy - k), (cx + r, cy), (cx + k, cy + k),
           (cx, cy + r), (cx - k, cy + k), (cx - r, cy), (cx - k, cy - k)]
    d.polygon([(x * S, y * S) for x, y in pts], fill=fill)


def _text(d, xy, text, f, fill, anchor="la") -> None:
    d.text((xy[0] * S, xy[1] * S), text, font=f, fill=fill, anchor=anchor)


def _wide_text(img: Image.Image, x: float, y: float, text: str, size: int, fill,
               stretch: float = 1.14, max_w: float | None = None) -> None:
    """Крупный «широкий» текст: рисуем и растягиваем по горизонтали."""
    f = font("Black", size)
    l, t, r, b = f.getbbox(text)
    layer = Image.new("RGBA", (r - l + 8, b - t + 8), (0, 0, 0, 0))
    ImageDraw.Draw(layer).text((4 - l, 4 - t), text, font=f, fill=fill)
    new_w = int(layer.width * stretch)
    if max_w and new_w > max_w * S:
        new_w = int(max_w * S)
    layer = layer.resize((new_w, layer.height), Image.LANCZOS)
    img.alpha_composite(layer, (int(x * S - 4), int(y * S - 4)))


def _meter(d, x, y, w, value: int) -> None:
    gap, n = 6, 10
    seg = (w - gap * (n - 1)) / n
    for i in range(n):
        x0 = x + i * (seg + gap)
        d.rounded_rectangle([x0 * S, y * S, (x0 + seg) * S, (y + 11) * S], radius=5.5 * S,
                            fill=BLUE if i < value else GREY)


def _barcode(d, x, y, w, h, seed: str) -> None:
    rnd = random.Random(hashlib.md5(seed.encode()).hexdigest())
    cx = x
    while cx < x + w - 2:
        bw = rnd.choice([2, 2, 3, 4, 5])
        gap = rnd.choice([3, 4, 5, 6])
        d.rectangle([cx * S, y * S, min(cx + bw, x + w) * S, (y + h) * S], fill=INK)
        cx += bw + gap


def _check(d, x, y, color) -> None:
    pts = [(x, y + 7), (x + 5, y + 12), (x + 15, y)]
    d.line([(px * S, py * S) for px, py in pts], fill=color, width=3 * S, joint="curve")


def _noise_bg() -> Image.Image:
    img = Image.new("RGBA", (W * S, H * S), BG + (255,))
    rnd = Image.effect_noise((W * S // 2, H * S // 2), 18).resize((W * S, H * S)).convert("RGBA")
    return Image.blend(img, ImageChops.add(img, rnd, 1, -110), 0.35)


def render_card(name: str, no: int, kind: str = "free", price: float | None = None) -> bytes:
    """kind: 'free' - свободен, 'sale' - выставлен на Fragment за price TON."""
    name = name.lower()
    read, liq = scores(name)
    img = _noise_bg()
    d = ImageDraw.Draw(img)

    # шапка
    _star(d, 66, 50, 12, (244, 241, 234))
    _text(d, (88, 50), BRAND, font("ExtraBold", 22), (244, 241, 234), "lm")
    _text(d, (1224, 50), f"№{no} / НАЙДЕН", font("Bold", 22), (244, 241, 234), "rm")

    # билет
    d.rounded_rectangle([56 * S, 92 * S, 1225 * S, 585 * S], radius=34 * S, fill=PAPER)
    for cy in (92, 585):
        d.ellipse([(930 - 23) * S, (cy - 23) * S, (930 + 23) * S, (cy + 23) * S], fill=BG)
    y = 118
    while y < 560:
        d.line([930 * S, y * S, 930 * S, (y + 8) * S], fill=LINE, width=2 * S)
        y += 16

    # заголовок + плашка
    _text(d, (100, 143), "USERNAME PASS", font("Bold", 20), INK, "lm")
    pill = "СВОБОДЕН" if kind == "free" else "НА FRAGMENT"
    pf = font("Bold", 17)
    pw = pf.getlength(pill) / S + 40
    d.rounded_rectangle([286 * S, 126 * S, (286 + pw) * S, 159 * S], radius=16.5 * S, fill=BLUE)
    _text(d, (286 + pw / 2, 143), pill, pf, (255, 255, 255), "mm")

    # крупный ник
    big = 150 if len(name) <= 5 else 132
    _wide_text(img, 100, 215, f"@{name}", big, INK, stretch=1.12, max_w=780)

    # метрики
    _text(d, (100, 406), "ЧИТАЕМОСТЬ", font("Bold", 17), INK, "lm")
    _text(d, (340, 406), f"{read}/10", font("Bold", 17), INK, "rm")
    _meter(d, 100, 424, 240, read)
    _text(d, (380, 406), "ЛИКВИДНОСТЬ", font("Bold", 17), INK, "lm")
    _text(d, (620, 406), f"{liq}/10", font("Bold", 17), INK, "rm")
    _meter(d, 380, 424, 240, liq)
    _text(d, (661, 406), "ДЛИНА", font("Bold", 17), INK, "lm")
    _text(d, (661, 438), f"{len(name)} симв.", font("ExtraBold", 25), INK, "lm")

    d.line([100 * S, 477 * S, 886 * S, 477 * S], fill=LINE, width=2 * S)

    # статусы
    _text(d, (100, 505), "TELEGRAM", font("Bold", 17), INK, "lm")
    _check(d, 204, 497, GREEN)
    _text(d, (240, 505), "FRAGMENT", font("Bold", 17), INK, "lm")
    _check(d, 352, 497, GREEN)
    _text(d, (886, 505), datetime.now().strftime("%d.%m.%Y %H:%M"), font("SemiBold", 17), INK, "rm")

    # правая часть
    _star(d, 1030, 172, 41, BLUE)
    if kind == "free":
        lo, hi = price_range(name, liq)
        label, val = "ОЦЕНКА", f"{lo}–{hi}"
    else:
        label, val = "ЦЕНА", f"{price:g}" if price is not None else "—"
    _text(d, (970, 256), label, font("Bold", 18), INK, "lm")
    vf = font("Black", 42 if len(val) <= 7 else 34)
    _text(d, (970, 300), val, vf, INK, "lm")
    _text(d, (970, 343), "TON", font("Black", 25), INK, "lm")
    _barcode(d, 970, 392, 215, 80, name + str(no))
    _text(d, (970, 505), BRAND, font("Bold", 18), INK, "lm")

    out = img.convert("RGB").resize((W, H), Image.LANCZOS)
    buf = io.BytesIO()
    out.save(buf, "PNG", optimize=True)
    return buf.getvalue()
