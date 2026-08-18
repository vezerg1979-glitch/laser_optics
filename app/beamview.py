# -*- coding: utf-8 -*-
"""
Виджет отрисовки схемы фокусировки: каустика пучка, деталь с разделкой,
присадочная проволока, режущее сопло.

Рисование выполняется примитивами Kivy (Line/Mesh) — без matplotlib,
чтобы не тянуть тяжёлые зависимости в APK.
"""

from __future__ import annotations

from kivy.graphics import Color, Line, Mesh, Rectangle
from kivy.metrics import dp
from kivy.uix.widget import Widget
from kivy.core.text import Label as CoreLabel

from . import geometry
from .optics import Scheme, Workpiece, caustic_points

SCHEME_COLORS = [
    (1.00, 0.30, 0.20),   # схема 1
    (0.20, 0.70, 1.00),   # схема 2
    (0.40, 0.90, 0.40),   # схема 3
    (1.00, 0.80, 0.20),   # схема 4
    (0.85, 0.45, 1.00),   # схема 5
]


def _triangulate(poly):
    """Простая веерная триангуляция выпуклого/почти выпуклого контура."""
    if len(poly) < 3:
        return [], []
    verts, indices = [], []
    for x, y in poly:
        verts.extend([x, y, 0.0, 0.0])
    for i in range(1, len(poly) - 1):
        indices.extend([0, i, i + 1])
    return verts, indices


class BeamView(Widget):
    """Канва со схемой. Поддерживает масштабирование и перетаскивание."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.schemes: list[Scheme] = []
        self.workpiece = Workpiece()
        self.zoom = 1.0
        self.pan = [0.0, 0.0]
        self._scale = 1.0
        self._origin = (0.0, 0.0)
        self.bind(pos=lambda *a: self.redraw(), size=lambda *a: self.redraw())

    # --- API -----------------------------------------------------------------

    def update(self, schemes, workpiece: Workpiece):
        self.schemes = [s for s in schemes if s.is_valid]
        self.workpiece = workpiece
        self.redraw()

    def reset_view(self):
        self.zoom = 1.0
        self.pan = [0.0, 0.0]
        self.redraw()

    # --- преобразование координат -------------------------------------------

    def _fit(self):
        """Подбирает масштаб мм -> пиксели так, чтобы сцена вошла целиком."""
        wp = self.workpiece
        polys = geometry.plate_polygons(wp)
        polys += geometry.wire_circles(wp)
        polys += geometry.nozzle_polygon(wp)

        beams = []
        for sch in self.schemes:
            left, right = caustic_points(sch, wp, n=120)
            if left:
                beams.append(left + list(reversed(right)))

        xmin, ymin, xmax, ymax = geometry.scene_bounds(polys, beams)
        # запас по краям
        pad_x = max((xmax - xmin) * 0.06, 1.0)
        pad_y = max((ymax - ymin) * 0.06, 1.0)
        xmin, xmax = xmin - pad_x, xmax + pad_x
        ymin, ymax = ymin - pad_y, ymax + pad_y

        w = max(xmax - xmin, 1e-6)
        h = max(ymax - ymin, 1e-6)
        scale = min(self.width / w, self.height / h) * self.zoom
        cx = 0.5 * (xmin + xmax)
        cy = 0.5 * (ymin + ymax)
        self._scale = scale
        self._origin = (
            self.center_x - cx * scale + self.pan[0],
            self.center_y - cy * scale + self.pan[1],
        )

    def to_px(self, x_mm, y_mm):
        ox, oy = self._origin
        return ox + x_mm * self._scale, oy + y_mm * self._scale

    def _flat(self, poly):
        out = []
        for x, y in poly:
            px, py = self.to_px(x, y)
            out.extend([px, py])
        return out

    # --- отрисовка -----------------------------------------------------------

    def redraw(self, *args):
        self.canvas.clear()
        self.canvas.after.clear()
        if self.width < 10 or self.height < 10:
            return
        self._fit()
        wp = self.workpiece

        with self.canvas:
            Color(0.09, 0.10, 0.13)
            Rectangle(pos=self.pos, size=self.size)

            self._draw_grid()

            # деталь
            for poly in geometry.plate_polygons(wp):
                verts, idx = _triangulate(poly)
                if idx:
                    Color(0.38, 0.40, 0.45)
                    Mesh(vertices=self._mesh_verts(poly), indices=idx,
                         mode="triangles")
                Color(0.75, 0.78, 0.82)
                Line(points=self._flat(poly + [poly[0]]), width=dp(1.2))

            # сопло
            for poly in geometry.nozzle_polygon(wp):
                Color(0.30, 0.33, 0.40)
                verts, idx = _triangulate(poly)
                if idx:
                    Mesh(vertices=self._mesh_verts(poly), indices=idx, mode="triangles")
                Color(0.65, 0.70, 0.80)
                Line(points=self._flat(poly + [poly[0]]), width=dp(1.2))

            # проволока
            for poly in geometry.wire_circles(wp):
                Color(0.85, 0.65, 0.30)
                verts, idx = _triangulate(poly)
                if idx:
                    Mesh(vertices=self._mesh_verts(poly), indices=idx, mode="triangles")
                Color(1.0, 0.85, 0.45)
                Line(points=self._flat(poly), width=dp(1.0))

            # пучки
            for i, sch in enumerate(self.schemes):
                col = SCHEME_COLORS[i % len(SCHEME_COLORS)]
                left, right = caustic_points(sch, wp, n=200)
                if not left:
                    continue
                verts, idx = _triangulate_strip(left, right)
                Color(col[0], col[1], col[2], 0.22)
                if idx:
                    Mesh(vertices=self._mesh_verts_raw(verts), indices=idx,
                         mode="triangles")
                Color(*col)
                Line(points=self._flat(left), width=dp(1.3))
                Line(points=self._flat(right), width=dp(1.3))

                # отметка перетяжки
                dz = sch.focus_position_mm
                import math
                a = math.radians(sch.tilt_angle_deg)
                fx = -dz * math.sin(a)
                fy = dz * math.cos(a)
                px, py = self.to_px(fx, fy)
                Color(*col)
                Line(circle=(px, py, dp(5)), width=dp(1.4))

            # линия поверхности детали
            Color(0.55, 0.60, 0.68, 0.9)
            x1, y1 = self.to_px(-1e4, 0)
            x2, y2 = self.to_px(1e4, 0)
            Line(points=[max(x1, self.x), y1, min(x2, self.right), y2],
                 width=dp(0.8), dash_offset=4, dash_length=6)

        self._draw_legend()

    def _mesh_verts(self, poly):
        out = []
        for x, y in poly:
            px, py = self.to_px(x, y)
            out.extend([px, py, 0.0, 0.0])
        return out

    def _mesh_verts_raw(self, verts):
        out = []
        for i in range(0, len(verts), 4):
            px, py = self.to_px(verts[i], verts[i + 1])
            out.extend([px, py, 0.0, 0.0])
        return out

    def _draw_grid(self):
        """Координатная сетка с шагом, кратным 1/5/10/20 мм."""
        if self._scale <= 0:
            return
        span_mm = self.width / self._scale
        for step in (1, 2, 5, 10, 20, 50, 100, 200):
            if span_mm / step <= 14:
                break
        ox, oy = self._origin
        Color(0.16, 0.18, 0.22)
        x_mm = int((self.x - ox) / self._scale / step) * step
        while True:
            px = ox + x_mm * self._scale
            if px > self.right:
                break
            if px >= self.x:
                Line(points=[px, self.y, px, self.top], width=dp(0.6))
            x_mm += step
        y_mm = int((self.y - oy) / self._scale / step) * step
        while True:
            py = oy + y_mm * self._scale
            if py > self.top:
                break
            if py >= self.y:
                Line(points=[self.x, py, self.right, py], width=dp(0.6))
            y_mm += step

    def _draw_legend(self):
        """Подписи схем и масштабная линейка."""
        y = self.top - dp(18)
        with self.canvas.after:
            for i, sch in enumerate(self.schemes):
                col = SCHEME_COLORS[i % len(SCHEME_COLORS)]
                Color(*col)
                Line(points=[self.x + dp(10), y, self.x + dp(28), y], width=dp(2))
                self._text(sch.name, self.x + dp(34), y - dp(8), col)
                y -= dp(18)

            # масштабная линейка
            if self._scale > 0:
                for step in (1, 2, 5, 10, 20, 50, 100):
                    if step * self._scale >= dp(60):
                        break
                length = step * self._scale
                bx = self.right - dp(20) - length
                by = self.y + dp(20)
                Color(0.85, 0.88, 0.92)
                Line(points=[bx, by, bx + length, by], width=dp(1.4))
                Line(points=[bx, by - dp(4), bx, by + dp(4)], width=dp(1.2))
                Line(points=[bx + length, by - dp(4), bx + length, by + dp(4)],
                     width=dp(1.2))
                self._text("%d мм" % step, bx + length / 2 - dp(15), by + dp(6),
                           (0.85, 0.88, 0.92))

    def _text(self, text, x, y, color):
        lbl = CoreLabel(text=text, font_size=dp(12))
        lbl.refresh()
        Color(*color)
        Rectangle(texture=lbl.texture, pos=(x, y), size=lbl.texture.size)

    # --- жесты ---------------------------------------------------------------

    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return False
        if touch.is_mouse_scrolling:
            self.zoom *= 1.15 if touch.button == "scrollup" else 1 / 1.15
            self.zoom = max(0.2, min(self.zoom, 40.0))
            self.redraw()
            return True
        touch.grab(self)
        return True

    def on_touch_move(self, touch):
        if touch.grab_current is self:
            self.pan[0] += touch.dx
            self.pan[1] += touch.dy
            self.redraw()
            return True
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        if touch.grab_current is self:
            touch.ungrab(self)
            return True
        return super().on_touch_up(touch)


def _triangulate_strip(left, right):
    """Триангуляция полосы между левой и правой образующими пучка."""
    n = min(len(left), len(right))
    if n < 2:
        return [], []
    verts = []
    for i in range(n):
        verts.extend([left[i][0], left[i][1], 0.0, 0.0])
    for i in range(n):
        verts.extend([right[i][0], right[i][1], 0.0, 0.0])
    indices = []
    for i in range(n - 1):
        a, b, c, d = i, i + 1, n + i, n + i + 1
        indices.extend([a, b, c, b, d, c])
    return verts, indices
