# -*- coding: utf-8 -*-
"""
Генератор иконки и заставки приложения.

Изображения строятся кодом, а не хранятся в репозитории: так они всегда
соответствуют палитре из theme.py, а при правке цветов достаточно
перезапустить скрипт. Сюжет — каустика сфокусированного пучка над
поверхностью детали, то есть ровно то, что приложение и считает.

Запуск:  python tools/make_icons.py
Результат: assets/icon.png (512x512) и assets/presplash.png (1024x1024)
"""

from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PIL import Image, ImageDraw  # noqa: E402

from app import theme as th  # noqa: E402


def rgb(name: str):
    return tuple(int(c * 255) for c in th.c(name)[:3])


def draw_caustic(img: Image.Image, cx: float, top: float, bottom: float,
                 waist_y: float, half_max: float, half_min: float,
                 color, alpha_fill: int, width: int):
    """
    Рисует пучок с гиперболической каустикой.

    Форма та же, что в расчёте: r(y) = r0*sqrt(1 + (dz/zR)^2). Перетяжка
    приходится на waist_y, на краях полуширина равна half_max.
    """
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    span = max(abs(top - waist_y), abs(bottom - waist_y))
    z_r = span / math.sqrt(max((half_max / half_min) ** 2 - 1.0, 1e-6))

    left, right = [], []
    steps = 90
    for i in range(steps + 1):
        y = top + (bottom - top) * i / steps
        r = half_min * math.sqrt(1.0 + ((y - waist_y) / z_r) ** 2)
        left.append((cx - r, y))
        right.append((cx + r, y))

    d.polygon(left + list(reversed(right)), fill=color + (alpha_fill,))
    d.line(left, fill=color + (255,), width=width, joint="curve")
    d.line(right, fill=color + (255,), width=width, joint="curve")
    img.alpha_composite(layer)


def make_icon(size: int = 512) -> Image.Image:
    img = Image.new("RGBA", (size, size), rgb("bg") + (255,))
    d = ImageDraw.Draw(img)
    s = size / 512.0

    # деталь: две пластины с зазором в нижней трети
    plate_top = 344 * s
    plate_bot = 442 * s
    gap = 40 * s
    # Пластины должны читаться на фоне, поэтому заливка светлее фона,
    # а обводка — цветом основного текста.
    for x0, x1 in ((44 * s, size / 2 - gap / 2),
                   (size / 2 + gap / 2, size - 44 * s)):
        d.rectangle([x0, plate_top, x1, plate_bot],
                    fill=(58, 74, 108), outline=rgb("text_dim"),
                    width=max(int(3 * s), 2))

    # пучок: перетяжка чуть выше поверхности детали
    draw_caustic(img, size / 2, 46 * s, plate_bot + 26 * s,
                 waist_y=plate_top - 4 * s,
                 half_max=96 * s, half_min=8 * s,
                 color=rgb("primary"), alpha_fill=70, width=max(int(5 * s), 1))

    # отметка перетяжки
    r = 15 * s
    d.ellipse([size / 2 - r, plate_top - 6 * s - r,
               size / 2 + r, plate_top - 6 * s + r],
              outline=rgb("primary_light"), width=int(4 * s))

    # линия поверхности
    d.line([30 * s, plate_top, size - 30 * s, plate_top],
           fill=rgb("text_dim"), width=max(int(2 * s), 1))
    return img


def make_presplash(size: int = 1024) -> Image.Image:
    img = Image.new("RGBA", (size, size), rgb("bg") + (255,))
    s = size / 1024.0
    d = ImageDraw.Draw(img)

    draw_caustic(img, size / 2, 150 * s, 700 * s, waist_y=560 * s,
                 half_max=150 * s, half_min=10 * s,
                 color=rgb("primary"), alpha_fill=60, width=int(6 * s))

    d.line([200 * s, 700 * s, 824 * s, 700 * s],
           fill=rgb("text_dim"), width=int(3 * s))

    # три точки триады как подпись под сюжетом
    for i, role in enumerate(("primary", "danger", "success")):
        cx = size / 2 + (i - 1) * 46 * s
        r = 11 * s
        d.ellipse([cx - r, 790 * s - r, cx + r, 790 * s + r], fill=rgb(role))
    return img


def main():
    out = os.path.join(os.path.dirname(__file__), "..", "assets")
    os.makedirs(out, exist_ok=True)
    icon_path = os.path.join(out, "icon.png")
    splash_path = os.path.join(out, "presplash.png")
    make_icon().convert("RGB").save(icon_path)
    make_presplash().convert("RGB").save(splash_path)
    print("Записано:")
    print(" ", os.path.normpath(icon_path))
    print(" ", os.path.normpath(splash_path))


if __name__ == "__main__":
    main()
