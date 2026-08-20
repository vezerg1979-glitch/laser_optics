# -*- coding: utf-8 -*-
"""
Оформление приложения: цвета, размеры, скругления.

Цветовое решение — триада на синей основе. Базовый синий 2563EB, две
другие вершины получены поворотом оттенка на 120° и 240°: малиновый
EB2563 и зелёный 63EB25. Роли закреплены за смыслом, а не за красотой:
синий — основное действие и первая схема, зелёный — режим в допуске,
малиновый — превышение и предупреждения. Янтарный выведен смешением
двух вершин и используется только как промежуточная ступень светофора.

Все размеры заданы в dp: 48 — минимальная комфортная зона нажатия
пальцем, на неё ориентированы кнопки и поля ввода.
"""

from __future__ import annotations

# --- палитры ----------------------------------------------------------------

DARK = {
    "bg": "#0F1420",
    "surface": "#182033",
    "surface_alt": "#1E2740",
    "border": "#2A3550",
    "text": "#E4E9F2",
    "text_dim": "#9FB2D6",
    "primary": "#2563EB",
    "primary_light": "#5B92F7",
    "primary_dark": "#1443A8",
    "on_primary": "#F2F6FF",
    "secondary_fill": "#232E47",
    "secondary_light": "#38466A",
    "secondary_dark": "#131A2B",
    "danger": "#EB2563",
    "warning": "#EBA425",
    "success": "#63EB25",
    "field_bg": "#0F1420",
}

LIGHT = {
    "bg": "#EEF2F9",
    "surface": "#FFFFFF",
    "surface_alt": "#E4EAF5",
    "border": "#C4D0E4",
    "text": "#101724",
    "text_dim": "#55637C",
    "primary": "#2563EB",
    "primary_light": "#679DF9",
    "primary_dark": "#1746A8",
    "on_primary": "#FFFFFF",
    "secondary_fill": "#DCE3F0",
    "secondary_light": "#F2F5FB",
    "secondary_dark": "#B6C2D8",
    "danger": "#C41B4F",
    "warning": "#B87708",
    "success": "#3F8F11",
    "field_bg": "#FFFFFF",
}

# Цвета пучков схем — первая вершина триады и производные от неё оттенки,
# различимые и на светлом, и на тёмном фоне.
SCHEME_HEX = ["#2563EB", "#EB2563", "#3F9E4C", "#E08A16", "#8B5BE0"]

# --- размеры ----------------------------------------------------------------

RADIUS = 9          # скругление кнопок и полей
RADIUS_CARD = 14    # скругление карточек-секций
TOUCH = 48          # минимальная зона нажатия
EDGE = 3            # толщина светлой и тёмной кромки объёмной кнопки

_mode = "dark"


def set_mode(mode: str) -> None:
    global _mode
    _mode = "light" if mode == "light" else "dark"


def mode() -> str:
    return _mode


def palette() -> dict:
    return LIGHT if _mode == "light" else DARK


def hex_to_rgba(value: str, alpha: float = 1.0):
    """'#2563EB' -> (0.145, 0.388, 0.921, 1.0)"""
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) / 255.0 for i in (0, 2, 4)) + (alpha,)


def c(name: str, alpha: float = 1.0):
    """Цвет по имени роли из текущей палитры."""
    return hex_to_rgba(palette()[name], alpha)


def scheme_color(index: int, alpha: float = 1.0):
    return hex_to_rgba(SCHEME_HEX[index % len(SCHEME_HEX)], alpha)


def scheme_markup(index: int) -> str:
    """Цвет схемы в формате разметки Kivy — 'ff2563eb'."""
    return SCHEME_HEX[index % len(SCHEME_HEX)].lstrip("#").lower()


def markup(name: str) -> str:
    return palette()[name].lstrip("#").lower()


# --- светофор режима --------------------------------------------------------

# Пороги плотности мощности на поверхности, Вт/см². Ниже нижнего — нагрев
# без плавления, между порогами — сварка теплопроводностью, выше верхнего —
# кинжальное проплавление с парогазовым каналом.
DENSITY_LOW = 1.0e5
DENSITY_HIGH = 1.0e6


def density_level(value: float):
    """Возвращает (цвет, краткое описание режима) по плотности мощности."""
    if not value:
        return "text_dim", "нет данных"
    if value < DENSITY_LOW:
        return "warning", "нагрев без плавления"
    if value < DENSITY_HIGH:
        return "success", "сварка теплопроводностью"
    return "danger", "кинжальное проплавление"
