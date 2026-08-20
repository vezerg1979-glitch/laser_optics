# -*- coding: utf-8 -*-
"""
Собственные виджеты оформления.

В Kivy нет теней и градиентов, поэтому объём кнопок делается рисованием
на канве: скруглённый прямоугольник, светлая кромка сверху, тёмная снизу.
При нажатии кромки меняются местами по яркости, а содержимое смещается
вниз на пиксель — получается эффект вдавливания.
"""

from __future__ import annotations

from kivy.animation import Animation
from kivy.clock import Clock
from kivy.graphics import Color, Ellipse, Line, RoundedRectangle, Triangle
from kivy.metrics import dp
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget

from . import theme as th


def parse_number(text, default=0.0):
    """Мягкий разбор числа: принимает и точку, и запятую."""
    try:
        return float(str(text).replace(",", ".").strip())
    except (TypeError, ValueError):
        return default


def numeric_filter(text, from_undo, get_current):
    """
    Фильтр ввода вещественного числа со знаком.

    Пропускает цифры, один разделитель дробной части и минус — только
    первым символом. Штатный input_filter="float" минус не пропускает,
    а он нужен постоянно: фокус под поверхностью, наклон в другую
    сторону, отрицательный скос кромки.
    """
    current = get_current()
    out = []
    for ch in text:
        if ch.isdigit():
            out.append(ch)
        elif ch in ".," and not any(x in current for x in ".,"):
            out.append(".")
            current += "."
        elif ch == "-" and not current and not out:
            out.append("-")
    return "".join(out)


class RaisedButton(ButtonBehavior, Label):
    """Объёмная кнопка со светлой верхней и тёмной нижней кромкой."""

    def __init__(self, text="", variant="secondary", on_tap=None,
                 font_size=None, **kwargs):
        super().__init__(text=text, **kwargs)
        self.variant = variant
        self.font_size = font_size or dp(15)
        self.markup = True
        self._on_tap = on_tap
        if on_tap is not None:
            self.bind(on_release=lambda *a: on_tap())
        self.bind(pos=self._redraw, size=self._redraw, state=self._redraw)
        self._redraw()

    def _colors(self):
        if self.variant == "primary":
            return "primary", "primary_light", "primary_dark", "on_primary"
        if self.variant == "danger":
            return "danger", "danger", "danger", "on_primary"
        return "secondary_fill", "secondary_light", "secondary_dark", "text"

    def _redraw(self, *args):
        fill, light, dark, text = self._colors()
        pressed = self.state == "down"
        self.color = th.c(text)
        self.canvas.before.clear()
        r = dp(th.RADIUS)
        edge = dp(th.EDGE)
        with self.canvas.before:
            Color(*th.c(fill))
            RoundedRectangle(pos=self.pos, size=self.size, radius=[r])
            # Верхняя кромка ловит свет, нижняя уходит в тень.
            # При нажатии яркости меняются местами.
            Color(*th.c(dark if pressed else light))
            RoundedRectangle(pos=(self.x + r, self.top - edge),
                             size=(max(self.width - 2 * r, 1), edge),
                             radius=[edge / 2])
            Color(*th.c(light if pressed else dark))
            RoundedRectangle(pos=(self.x + r, self.y),
                             size=(max(self.width - 2 * r, 1), edge),
                             radius=[edge / 2])
        self.padding_y = dp(2) if pressed else 0


class Card(BoxLayout):
    """Скруглённая карточка-секция с заголовком."""

    def __init__(self, title, **kwargs):
        super().__init__(orientation="vertical", size_hint_y=None,
                         padding=[dp(10), dp(8), dp(10), dp(10)],
                         spacing=dp(4), **kwargs)
        self.bind(minimum_height=self.setter("height"))
        head = Label(text="[b]%s[/b]" % title, markup=True, halign="left",
                     valign="middle", size_hint_y=None, height=dp(26),
                     font_size=dp(14), color=th.c("primary_light"))
        head.bind(size=lambda i, v: setattr(i, "text_size", v))
        self.add_widget(head)
        self.bind(pos=self._redraw, size=self._redraw)
        self._redraw()

    def _redraw(self, *args):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*th.c("surface"))
            RoundedRectangle(pos=self.pos, size=self.size,
                             radius=[dp(th.RADIUS_CARD)])
            Color(*th.c("border"))
            RoundedRectangle(pos=(self.x, self.y),
                             size=(self.width, dp(1)),
                             radius=[dp(1)])


class _StepButton(ButtonBehavior, BoxLayout):
    """
    Кнопка со стрелкой вверх или вниз и автоповтором при удержании.

    Стрелка рисуется треугольником, а не символом: шрифт Kivy по
    умолчанию не содержит знаков ▲ и ▼ и показывает вместо них пустые
    прямоугольники.
    """

    def __init__(self, up, on_step, **kwargs):
        super().__init__(**kwargs)
        self.up = up
        self._on_step = on_step
        self._event = None
        self._count = 0
        self.bind(pos=self._redraw, size=self._redraw, state=self._redraw)
        self._redraw()

    def _redraw(self, *args):
        self.canvas.before.clear()
        w, h = self.width, self.height
        aw, ah = dp(11), dp(6)
        cx, cy = self.center_x, self.center_y
        with self.canvas.before:
            Color(*th.c("secondary_light" if self.state == "down"
                        else "secondary_fill"))
            RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(5)])
            Color(*th.c("text_dim"))
            if self.up:
                Triangle(points=[cx - aw / 2, cy - ah / 2,
                                 cx + aw / 2, cy - ah / 2,
                                 cx, cy + ah / 2])
            else:
                Triangle(points=[cx - aw / 2, cy + ah / 2,
                                 cx + aw / 2, cy + ah / 2,
                                 cx, cy - ah / 2])

    def on_press(self):
        self._on_step()
        self._count = 0
        # Через полсекунды удержания включается повтор, который затем
        # ускоряется — так подбирают значение, не отпуская палец.
        self._event = Clock.schedule_once(self._start_repeat, 0.5)

    def _start_repeat(self, *args):
        self._event = Clock.schedule_interval(self._repeat, 0.12)

    def _repeat(self, *args):
        self._count += 1
        steps = 1 if self._count < 12 else (3 if self._count < 30 else 10)
        for _ in range(steps):
            self._on_step()

    def on_release(self):
        if self._event is not None:
            self._event.cancel()
            self._event = None


class StepperField(BoxLayout):
    """
    Строка «подпись — поле ввода — кнопки ▲▼».

    Шаг подбирается под смысл параметра: 0,1 мм для положения фокуса,
    1 мм для фокусных расстояний, 0,5° для углов. Набирать значение
    с клавиатуры по-прежнему можно.
    """

    def __init__(self, caption, value, on_change, step=1.0, minimum=None,
                 decimals=2, on_focus=None, **kwargs):
        super().__init__(orientation="horizontal", size_hint_y=None,
                         height=dp(th.TOUCH), spacing=dp(5), **kwargs)
        self.step = step
        self.minimum = minimum
        self.decimals = decimals
        self._on_change = on_change

        label = Label(text=caption, halign="left", valign="middle",
                      size_hint_x=0.50, font_size=dp(13),
                      color=th.c("text_dim"),
                      text_size=(None, dp(th.TOUCH - 6)),
                      shorten=True, shorten_from="right")
        self.add_widget(label)

        self.input = TextInput(
            text=self._fmt(value), multiline=False, input_type="number",
            size_hint_x=0.34, font_size=dp(16),
            padding=[dp(9), dp(12)],
            background_color=th.c("field_bg"),
            foreground_color=th.c("text"),
            cursor_color=th.c("primary_light"),
            selection_color=th.c("primary", 0.35),
            input_filter=lambda t, u: numeric_filter(
                t, u, lambda: self.input.text))
        self.input.bind(text=lambda inst, val: on_change(val))
        if on_focus is not None:
            self.input.bind(focus=lambda inst, val: on_focus(self, val))
        self.add_widget(self.input)

        arrows = BoxLayout(orientation="vertical", size_hint_x=0.16,
                           spacing=dp(3))
        arrows.add_widget(_StepButton(True, lambda: self._bump(+1)))
        arrows.add_widget(_StepButton(False, lambda: self._bump(-1)))
        self.add_widget(arrows)

    def _fmt(self, value):
        text = ("%%.%df" % self.decimals) % float(value)
        return text.rstrip("0").rstrip(".") if "." in text else text

    def _bump(self, direction):
        value = parse_number(self.input.text) + direction * self.step
        if self.minimum is not None and value < self.minimum:
            value = self.minimum
        self.input.text = self._fmt(value)

    def set(self, value):
        self.input.text = self._fmt(value)


class ChoiceRow(BoxLayout):
    """Строка «подпись — выпадающий список»."""

    def __init__(self, caption, values, value, on_change, **kwargs):
        super().__init__(orientation="horizontal", size_hint_y=None,
                         height=dp(th.TOUCH), spacing=dp(5), **kwargs)
        label = Label(text=caption, halign="left", valign="middle",
                      size_hint_x=0.50, font_size=dp(13),
                      color=th.c("text_dim"),
                      text_size=(None, dp(th.TOUCH - 6)),
                      shorten=True, shorten_from="right")
        self.add_widget(label)
        self.spinner = Spinner(
            text=str(value), values=[str(v) for v in values],
            size_hint_x=0.50, font_size=dp(14),
            background_normal="", background_down="",
            background_color=th.c("secondary_fill"),
            color=th.c("text"))
        self.spinner.bind(text=lambda inst, val: on_change(val))
        self.add_widget(self.spinner)

    def set(self, value):
        self.spinner.text = str(value)


class NavButton(ButtonBehavior, BoxLayout):
    """
    Кнопка нижней навигации: значок над подписью.

    Значки рисуются примитивами, а не шрифтовыми символами — набор
    пиктограмм в стандартном шрифте Kivy отсутствует.
    """

    def __init__(self, kind, caption, on_tap, **kwargs):
        super().__init__(orientation="vertical", **kwargs)
        self.bind(on_release=lambda *a: on_tap())
        self.kind = kind
        self.selected = False
        self.icon = Widget(size_hint_y=0.52)
        self.caption = Label(text=caption, font_size=dp(11), size_hint_y=0.48)
        self.add_widget(self.icon)
        self.add_widget(self.caption)
        self.icon.bind(pos=self._redraw, size=self._redraw)
        self.bind(pos=self._redraw, size=self._redraw)
        self._redraw()

    def set_selected(self, value):
        self.selected = value
        self._redraw()

    def _redraw(self, *args):
        role = "primary_light" if self.selected else "text_dim"
        self.caption.color = th.c(role)

        self.canvas.before.clear()
        with self.canvas.before:
            if self.selected:
                Color(*th.c("primary", 0.16))
                RoundedRectangle(
                    pos=(self.x + dp(6), self.y + dp(4)),
                    size=(self.width - dp(12), self.height - dp(8)),
                    radius=[dp(th.RADIUS)])

        self.icon.canvas.after.clear()
        cx, cy = self.icon.center_x, self.icon.center_y
        with self.icon.canvas.after:
            Color(*th.c(role))
            if self.kind == "params":
                # ползунки: три линии с движками
                for i, off in enumerate((dp(7), 0, -dp(7))):
                    Line(points=[cx - dp(11), cy + off, cx + dp(11), cy + off],
                         width=dp(1.1))
                    kx = cx + (dp(4), -dp(5), dp(1))[i]
                    Ellipse(pos=(kx - dp(2.5), cy + off - dp(2.5)),
                            size=(dp(5), dp(5)))
            elif self.kind == "table":
                # таблица: сетка два на два
                for ry in (dp(1), -dp(9)):
                    for rx in (-dp(11), dp(1)):
                        RoundedRectangle(pos=(cx + rx, cy + ry),
                                         size=(dp(10), dp(8)),
                                         radius=[dp(1.5)])
            else:
                # каустика: две сходящиеся линии с перетяжкой
                Line(points=[cx - dp(9), cy + dp(10), cx - dp(2), cy,
                             cx - dp(9), cy - dp(10)], width=dp(1.2))
                Line(points=[cx + dp(9), cy + dp(10), cx + dp(2), cy,
                             cx + dp(9), cy - dp(10)], width=dp(1.2))


def flash(label):
    """Короткая подсветка изменившегося числа."""
    label.color = th.c("primary_light")
    Animation.cancel_all(label, "color")
    Animation(color=th.c("text"), duration=0.45).start(label)
