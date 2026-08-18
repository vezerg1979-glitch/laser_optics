# -*- coding: utf-8 -*-
"""
Построение контуров детали, разделки кромок, присадочной проволоки и сопла.

Все координаты — в миллиметрах, начало координат на верхней поверхности
детали в точке пересечения с осью пучка. Ось Y направлена вверх.
"""

from __future__ import annotations

import math
from typing import List, Tuple

from .optics import Workpiece

Point = Tuple[float, float]
Polygon = List[Point]


def _bevel_offset(thickness_mm: float, angle_deg: float) -> float:
    """Горизонтальный катет скоса кромки при заданном угле разделки."""
    return abs(thickness_mm * math.tan(math.radians(angle_deg)))


def plate_polygons(wp: Workpiece) -> List[Polygon]:
    """
    Контуры левой и правой пластин с учётом зазора, смещения стыка
    и углов скоса кромок.

    Положительный угол скоса — разделка расширяется кверху (V-образная),
    отрицательный — книзу.
    """
    if not wp.draw_plate or wp.thickness_mm <= 0:
        return []

    t = wp.thickness_mm
    half_gap = 0.5 * wp.gap_mm
    x0 = wp.joint_offset_mm

    # --- левая пластина
    b_left = _bevel_offset(t, wp.bevel_left_deg)
    if wp.bevel_left_deg > 0:
        top_right = x0 - half_gap - b_left
        bot_right = x0 - half_gap
    else:
        top_right = x0 - half_gap
        bot_right = x0 - half_gap - b_left
    outer_left = x0 - half_gap - max(wp.width_left_mm, b_left)
    left_plate: Polygon = [
        (outer_left, 0.0),
        (top_right, 0.0),
        (bot_right, -t),
        (outer_left, -t),
    ]

    # --- правая пластина
    b_right = _bevel_offset(t, wp.bevel_right_deg)
    if wp.bevel_right_deg > 0:
        top_left = x0 + half_gap + b_right
        bot_left = x0 + half_gap
    else:
        top_left = x0 + half_gap
        bot_left = x0 + half_gap + b_right
    outer_right = x0 + half_gap + max(wp.width_right_mm, b_right)
    right_plate: Polygon = [
        (top_left, 0.0),
        (outer_right, 0.0),
        (outer_right, -t),
        (bot_left, -t),
    ]

    return [left_plate, right_plate]


def wire_circles(wp: Workpiece, segments: int = 48) -> List[Polygon]:
    """
    Контуры присадочной проволоки. Проволока лежит на верхней поверхности
    детали; при двух проволоках они располагаются симметрично относительно
    точки смещения и касаются друг друга.
    """
    if wp.wire_count <= 0 or wp.wire_diameter_mm <= 0:
        return []

    r = 0.5 * wp.wire_diameter_mm
    if wp.wire_count == 1:
        centers = [wp.wire_offset_mm]
    else:
        centers = [wp.wire_offset_mm - r, wp.wire_offset_mm + r]

    circles: List[Polygon] = []
    for cx in centers:
        poly: Polygon = []
        for i in range(segments + 1):
            a = 2.0 * math.pi * i / segments
            poly.append((cx + r * math.cos(a), r + r * math.sin(a)))
        circles.append(poly)
    return circles


def nozzle_polygon(wp: Workpiece) -> List[Polygon]:
    """
    Контур режущего сопла: цилиндрический носик снизу и конус, переходящий
    в корпус сверху. Нижний срез сопла отстоит от детали на заданный зазор.
    """
    if not wp.draw_nozzle or wp.nozzle_height_mm <= 0:
        return []

    x0 = wp.nozzle_offset_mm
    d_low = 0.5 * wp.nozzle_d_lower_mm
    d_up = 0.5 * wp.nozzle_d_upper_mm
    y_bot = wp.nozzle_gap_mm
    y_top = y_bot + wp.nozzle_height_mm
    y_cone = y_top - min(wp.nozzle_cone_mm, wp.nozzle_height_mm)

    poly: Polygon = [
        (x0 - d_low, y_bot),
        (x0 - d_low, y_cone),
        (x0 - d_up, y_top),
        (x0 + d_up, y_top),
        (x0 + d_low, y_cone),
        (x0 + d_low, y_bot),
    ]
    return [poly]


def scene_bounds(polys: List[Polygon], extra: List[Polygon] = None):
    """Габариты сцены (xmin, ymin, xmax, ymax) по всем контурам."""
    pts: List[Point] = []
    for group in (polys, extra or []):
        for poly in group:
            pts.extend(poly)
    if not pts:
        return -10.0, -10.0, 10.0, 10.0
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)
