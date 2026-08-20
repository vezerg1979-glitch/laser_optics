# -*- coding: utf-8 -*-
"""Интерфейс приложения «Расчёт фокусировки лазерного излучения»."""

from __future__ import annotations

import json
import os

from kivy.clock import Clock
from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView

from . import theme as th
from .beamview import BeamView
from .optics import POWER_UNITS, SPEED_UNITS, Scheme, Workpiece, calculate
from .widgets import (
    Card,
    ChoiceRow,
    NavButton,
    RaisedButton,
    StepperField,
    flash,
    parse_number,
)

N_SCHEMES = 5

# Шаг стрелок и минимум для каждого параметра схемы
SCHEME_FIELDS = [
    ("Длина волны, мкм", "wavelength_um", 0.01, 0.0, 3),
    ("Диаметр волокна, мкм", "fiber_diameter_um", 10.0, 0.0, 0),
    ("BPP, мм·мрад", "bpp_mm_mrad", 0.1, 0.0, 2),
    ("Коллиматор, мм", "collimator_mm", 5.0, 0.0, 1),
    ("Фокусатор, мм", "focusator_mm", 5.0, 0.0, 1),
    ("Положение фокуса, мм", "focus_position_mm", 0.5, None, 1),
    ("Угол наклона луча, °", "tilt_angle_deg", 0.5, None, 1),
]

WP_PLATE = [
    ("Толщина детали, мм", "thickness_mm", 0.5, 0.0, 1),
    ("Ширина слева, мм", "width_left_mm", 1.0, 0.0, 1),
    ("Ширина справа, мм", "width_right_mm", 1.0, 0.0, 1),
    ("Зазор, мм", "gap_mm", 0.1, 0.0, 2),
    ("Угол скоса левой кромки, °", "bevel_left_deg", 0.5, None, 1),
    ("Угол скоса правой кромки, °", "bevel_right_deg", 0.5, None, 1),
    ("Смещение стыка, мм", "joint_offset_mm", 0.1, None, 2),
]

WP_WIRE = [
    ("Диаметр проволоки, мм", "wire_diameter_mm", 0.1, 0.0, 2),
    ("Смещение проволоки, мм", "wire_offset_mm", 0.1, None, 2),
]

WP_NOZZLE = [
    ("Диаметр верхний, мм", "nozzle_d_upper_mm", 0.5, 0.0, 1),
    ("Диаметр нижний, мм", "nozzle_d_lower_mm", 0.1, 0.0, 2),
    ("Общая высота, мм", "nozzle_height_mm", 1.0, 0.0, 1),
    ("Высота конуса, мм", "nozzle_cone_mm", 0.5, 0.0, 1),
    ("Смещение сопла, мм", "nozzle_offset_mm", 0.1, None, 2),
    ("Зазор сопло—деталь, мм", "nozzle_gap_mm", 0.5, 0.0, 1),
]

WP_VIEW = [
    ("Требуемое пятно, мм", "target_spot_mm", 0.5, 0.0, 2),
    ("Максимальный Y, мм", "y_max_mm", 5.0, None, 1),
    ("Минимальный Y, мм", "y_min_mm", 5.0, None, 1),
]

RESULT_ROWS = [
    ("Диаметр пятна в фокусе, мм", "spot_focus_mm", "%.3f"),
    ("Диаметр пятна на поверхности, мм", "spot_surface_mm", "%.3f"),
    ("Диаметр пятна в корне шва, мм", "spot_root_mm", "%.3f"),
    ("Длина перетяжки, мм", "waist_length_mm", "%.2f"),
    ("Длина Рэлея, мм", "rayleigh_mm", "%.2f"),
    ("Увеличение оптики", "magnification", "%.3f"),
    ("Параметр M²", "m2", "%.2f"),
    ("Расходимость (полный угол), мрад", "divergence_full_mrad", "%.1f"),
    ("Диаметр пучка на линзе, мм", "beam_on_lens_mm", "%.2f"),
    ("Сдвиг фокуса на 1 мм коллиматора, мм", "focus_shift_per_mm", "%.2f"),
    ("Расфокусировка под заданное пятно, мм", "required_defocus_mm", "%.1f"),
    ("Мощность, Вт", "power_w", "%.0f"),
    ("Скорость, мм/с", "speed_mm_s", "%.2f"),
    ("Плотность мощности в фокусе, Вт/см²", "power_density_focus", "%.3g"),
    ("Плотность мощности на поверхности, Вт/см²",
     "power_density_surface", "%.3g"),
    ("Плотность мощности на линзе, Вт/см²", "power_density_lens", "%.3g"),
    ("Погонная энергия, Дж/мм", "linear_energy_j_mm", "%.1f"),
]


def fmt_density(value):
    """Плотность мощности в удобных единицах вместо 1.5e+06 Вт/см²."""
    if not value:
        return "—"
    if value >= 1e6:
        return "%.2f МВт/см²" % (value / 1e6)
    if value >= 1e3:
        return "%.1f кВт/см²" % (value / 1e3)
    return "%.0f Вт/см²" % value


class MainUI(BoxLayout):
    """Корневой виджет: три раздела и нижняя навигация."""

    def __init__(self, storage_dir: str, **kwargs):
        super().__init__(orientation="vertical", **kwargs)
        self.storage_dir = storage_dir
        self.schemes = [Scheme(name="Схема %d" % (i + 1))
                        for i in range(N_SCHEMES)]
        for s in self.schemes[1:]:
            s.collimator_mm = 0.0
            s.focusator_mm = 0.0
        self.workpiece = Workpiece()
        self.active = 0
        self.section = 0
        self._updating = False
        self._prev_summary = ["", "", ""]
        self._load()
        self._build()

    # ----------------------------------------------------------- построение

    def _build(self):
        self.clear_widgets()
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*th.c("bg"))
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._sync_bg, size=self._sync_bg)

        self.body = BoxLayout()
        self.add_widget(self.body)

        nav = BoxLayout(size_hint_y=None, height=dp(60), padding=dp(4))
        self.nav_buttons = []
        for i, (glyph, caption) in enumerate(
                (("params", "Параметры"), ("table", "Результаты"),
                 ("beam", "Схема"))):
            btn = NavButton(glyph, caption,
                            lambda idx=i: self.show_section(idx))
            self.nav_buttons.append(btn)
            nav.add_widget(btn)
        self.add_widget(nav)

        self._build_input()
        self._build_results()
        self._build_view()
        self.show_section(self.section)
        self.refresh()

    def _sync_bg(self, *args):
        self._bg.pos = self.pos
        self._bg.size = self.size

    def show_section(self, index):
        self.section = index
        self.body.clear_widgets()
        self.body.add_widget(
            (self.input_root, self.result_root, self.view_root)[index])
        for i, btn in enumerate(self.nav_buttons):
            btn.set_selected(i == index)

    # ----------------------------------------------------------------- ввод

    def _scheme_label(self, index):
        s = self.schemes[index]
        mark = "•" if s.is_valid else "·"
        color = th.scheme_markup(index) if s.is_valid else th.markup("text_dim")
        if not s.is_valid:
            return "%s  %s — не заполнена" % (mark, s.name)
        dz = s.focus_position_mm
        return "%s  %s • %g/%g, фокус %s мм" % (
            mark, s.name, s.focusator_mm, s.collimator_mm,
            "%g" % dz if dz == 0 else "%+g" % dz)

    def _build_input(self):
        self.input_root = BoxLayout(orientation="vertical")

        top = BoxLayout(size_hint_y=None, height=dp(56), padding=dp(6),
                        spacing=dp(6))
        self.scheme_row = ChoiceRow(
            "Схема", [self._scheme_label(i) for i in range(N_SCHEMES)],
            self._scheme_label(self.active), self._on_scheme_switch)
        self.scheme_row.children[0].size_hint_x = 0.78
        self.scheme_row.children[1].size_hint_x = 0.22
        top.add_widget(self.scheme_row)
        clear = RaisedButton("Очистить", on_tap=self._clear_scheme,
                             size_hint_x=None, width=dp(96), font_size=dp(13))
        top.add_widget(clear)
        self.input_root.add_widget(top)

        self.form_scroll = ScrollView()
        self.form = GridLayout(cols=1, size_hint_y=None, padding=dp(8),
                               spacing=dp(8))
        self.form.bind(minimum_height=self.form.setter("height"))
        self.form_scroll.add_widget(self.form)
        self.input_root.add_widget(self.form_scroll)
        self._build_form()

        self.input_root.add_widget(self._build_summary())

        bottom = BoxLayout(size_hint_y=None, height=dp(60), padding=dp(6),
                           spacing=dp(6))
        bottom.add_widget(RaisedButton("Сохранить", variant="primary",
                                       on_tap=self._save))
        bottom.add_widget(RaisedButton("Сбросить", on_tap=self._reset_all))
        self.theme_btn = RaisedButton(
            "Тема", on_tap=self._toggle_theme,
            size_hint_x=None, width=dp(70), font_size=dp(13))
        bottom.add_widget(self.theme_btn)
        self.input_root.add_widget(bottom)

    def _build_summary(self):
        """Полоса ключевых чисел со светофором режима."""
        box = BoxLayout(orientation="vertical", size_hint_y=None,
                        height=dp(72), padding=[dp(8), dp(5)], spacing=dp(2))
        row = BoxLayout(size_hint_y=0.62, spacing=dp(4))
        self.summary_labels = []
        for caption in ("Пятно на поверхности", "Плотность мощности",
                        "Погонная энергия"):
            col = BoxLayout(orientation="vertical")
            col.add_widget(Label(text=caption, font_size=dp(10),
                                 color=th.c("text_dim"), size_hint_y=0.42))
            value = Label(text="—", font_size=dp(15), bold=True,
                          color=th.c("text"), size_hint_y=0.58)
            self.summary_labels.append(value)
            col.add_widget(value)
            row.add_widget(col)
        box.add_widget(row)
        self.mode_label = Label(text="", font_size=dp(11), markup=True,
                                size_hint_y=0.38, color=th.c("text_dim"))
        box.add_widget(self.mode_label)
        return box

    def _scheme_setter(self, attr, cast=float):
        def setter(value):
            setattr(self.schemes[self.active], attr,
                    parse_number(value) if cast is float else value)
            self.refresh()
        return setter

    def _wp_setter(self, attr, cast=float):
        def setter(value):
            if cast is float:
                setattr(self.workpiece, attr, parse_number(value))
            elif cast is int:
                setattr(self.workpiece, attr, int(parse_number(value)))
            elif cast is bool:
                setattr(self.workpiece, attr, str(value) == "Да")
            else:
                setattr(self.workpiece, attr, value)
            self.refresh()
        return setter

    def _build_form(self):
        self.form.clear_widgets()
        s = self.schemes[self.active]
        wp = self.workpiece
        self.scheme_fields = {}

        card = Card("Излучение и оптика")
        for caption, attr, step, minimum, dec in SCHEME_FIELDS:
            fld = StepperField(caption, getattr(s, attr),
                               self._scheme_setter(attr), step=step,
                               minimum=minimum, decimals=dec,
                               on_focus=self._on_field_focus)
            self.scheme_fields[attr] = fld
            card.add_widget(fld)
        self.form.add_widget(card)

        card = Card("Режим обработки")
        card.add_widget(StepperField(
            "Скорость обработки", s.speed, self._scheme_setter("speed"),
            step=0.1, minimum=0.0, decimals=2,
            on_focus=self._on_field_focus))
        card.add_widget(ChoiceRow("Единицы скорости", SPEED_UNITS,
                                  s.speed_unit,
                                  self._scheme_setter("speed_unit", str)))
        card.add_widget(StepperField(
            "Мощность излучения", s.power, self._scheme_setter("power"),
            step=0.5, minimum=0.0, decimals=2,
            on_focus=self._on_field_focus))
        card.add_widget(ChoiceRow("Единицы мощности", POWER_UNITS,
                                  s.power_unit,
                                  self._scheme_setter("power_unit", str)))
        self.form.add_widget(card)

        card = Card("Деталь и разделка")
        card.add_widget(ChoiceRow("Рисовать деталь", ("Да", "Нет"),
                                  "Да" if wp.draw_plate else "Нет",
                                  self._wp_setter("draw_plate", bool)))
        self._add_wp_fields(card, WP_PLATE)
        self.form.add_widget(card)

        card = Card("Присадочная проволока")
        card.add_widget(ChoiceRow("Количество проволок", ("0", "1", "2"),
                                  str(wp.wire_count),
                                  self._wp_setter("wire_count", int)))
        self._add_wp_fields(card, WP_WIRE)
        self.form.add_widget(card)

        card = Card("Сопло для резки")
        card.add_widget(ChoiceRow("Показывать сопло", ("Да", "Нет"),
                                  "Да" if wp.draw_nozzle else "Нет",
                                  self._wp_setter("draw_nozzle", bool)))
        self._add_wp_fields(card, WP_NOZZLE)
        self.form.add_widget(card)

        card = Card("Построение и цель")
        self._add_wp_fields(card, WP_VIEW)
        self.form.add_widget(card)

    def _add_wp_fields(self, card, spec):
        for caption, attr, step, minimum, dec in spec:
            card.add_widget(StepperField(
                caption, getattr(self.workpiece, attr),
                self._wp_setter(attr), step=step, minimum=minimum,
                decimals=dec, on_focus=self._on_field_focus))

    def _on_field_focus(self, field, focused):
        """
        Прокрутка к полю, получившему фокус.

        На Android экранная клавиатура закрывает нижнюю часть формы.
        Задержка нужна, чтобы клавиатура успела появиться и высота
        видимой области пересчиталась.
        """
        if not focused:
            return
        Clock.schedule_once(
            lambda *a: self.form_scroll.scroll_to(field, padding=dp(24)), 0.2)

    def _on_scheme_switch(self, text):
        if self._updating:
            return
        for i in range(N_SCHEMES):
            if self._scheme_label(i) == text:
                self.active = i
                break
        self._build_form()
        self.refresh()

    def _update_scheme_row(self):
        self._updating = True
        try:
            self.scheme_row.spinner.values = [
                self._scheme_label(i) for i in range(N_SCHEMES)]
            self.scheme_row.spinner.text = self._scheme_label(self.active)
        finally:
            self._updating = False

    def _clear_scheme(self):
        name = self.schemes[self.active].name
        self.schemes[self.active] = Scheme(name=name, collimator_mm=0.0,
                                           focusator_mm=0.0)
        self._build_form()
        self.refresh()

    def _reset_all(self):
        self.schemes = [Scheme(name="Схема %d" % (i + 1))
                        for i in range(N_SCHEMES)]
        for s in self.schemes[1:]:
            s.collimator_mm = 0.0
            s.focusator_mm = 0.0
        self.workpiece = Workpiece()
        self.active = 0
        self._build_form()
        self.refresh()

    def _toggle_theme(self):
        th.set_mode("light" if th.mode() == "dark" else "dark")
        self._save(silent=True)
        self._prev_summary = ["", "", ""]
        self._build()

    # ----------------------------------------------------------- результаты

    def _build_results(self):
        self.result_root = ScrollView()
        self.result_box = GridLayout(cols=1, size_hint_y=None, padding=dp(10),
                                     spacing=dp(6))
        self.result_box.bind(minimum_height=self.result_box.setter("height"))
        self.result_root.add_widget(self.result_box)

    def _fill_results(self):
        self.result_box.clear_widgets()
        results = [(i, calculate(s, self.workpiece))
                   for i, s in enumerate(self.schemes) if s.is_valid]
        if not results:
            self.result_box.add_widget(Label(
                text="Заполните коллиматор и фокусатор хотя бы одной схемы",
                color=th.c("text_dim"), size_hint_y=None, height=dp(60),
                font_size=dp(14)))
            return

        # Первый столбец с названиями закреплён, столбцы схем прокручиваются
        # вбок. Межстрочный интервал у обоих одинаковый, иначе строки
        # расходятся по вертикали тем сильнее, чем ниже.
        row_h, gap = dp(33), dp(2)
        name_w, col_w = dp(178), dp(122)
        n_rows = len(RESULT_ROWS) + 1
        total_h = (row_h + gap) * n_rows

        table = BoxLayout(size_hint_y=None, height=total_h, spacing=gap)
        names = GridLayout(cols=1, size_hint=(None, None), spacing=gap,
                           width=name_w, height=total_h)
        names.add_widget(Label(text="[b]Параметр[/b]", markup=True,
                               font_size=dp(12), halign="left",
                               valign="middle", size_hint_y=None,
                               height=row_h, color=th.c("text"),
                               text_size=(name_w - dp(6), row_h)))
        for caption, _a, _f in RESULT_ROWS:
            names.add_widget(Label(
                text=caption, font_size=dp(12), halign="left",
                valign="middle", size_hint_y=None, height=row_h,
                color=th.c("text_dim"),
                text_size=(name_w - dp(6), row_h),
                shorten=True, shorten_from="right"))
        table.add_widget(names)

        hscroll = ScrollView(do_scroll_x=True, do_scroll_y=False,
                             bar_width=dp(3))
        values = GridLayout(cols=len(results), size_hint=(None, None),
                            spacing=gap, width=col_w * len(results),
                            height=total_h)
        for idx, _ in results:
            values.add_widget(Label(
                text="[b][color=%s]•  %s[/color][/b]"
                     % (th.scheme_markup(idx), self.schemes[idx].name),
                markup=True, font_size=dp(12), size_hint_y=None,
                height=row_h))
        for _c, attr, fmt in RESULT_ROWS:
            for _, res in results:
                value = getattr(res, attr)
                values.add_widget(Label(
                    text="—" if value is None else fmt % value,
                    color=th.c("text"), font_size=dp(12),
                    size_hint_y=None, height=row_h))
        hscroll.add_widget(values)
        table.add_widget(hscroll)
        self.result_box.add_widget(table)

        if len(results) > 2:
            self.result_box.add_widget(Label(
                text="Столбцы схем прокручиваются вбок",
                color=th.c("text_dim"), font_size=dp(11),
                size_hint_y=None, height=dp(22)))

        for idx, res in results:
            for w in res.warnings:
                lbl = Label(text="[color=%s]!  %s: %s[/color]"
                                 % (th.markup("warning"),
                                    self.schemes[idx].name, w),
                            markup=True, size_hint_y=None, font_size=dp(12),
                            halign="left", valign="top")
                lbl.bind(width=lambda i, v: setattr(i, "text_size", (v, None)),
                         texture_size=lambda i, v: setattr(
                             i, "height", v[1] + dp(8)))
                self.result_box.add_widget(lbl)

        export = RaisedButton("Выгрузить отчёт в CSV", variant="primary",
                              size_hint_y=None, height=dp(th.TOUCH),
                              on_tap=lambda: self._export_csv(results))
        self.result_box.add_widget(export)

    # ----------------------------------------------------------------- схема

    def _build_view(self):
        self.view_root = BoxLayout(orientation="vertical")
        self.view = BeamView()
        self.view_root.add_widget(self.view)
        bar = BoxLayout(size_hint_y=None, height=dp(56), padding=dp(6),
                        spacing=dp(6))
        bar.add_widget(RaisedButton("−", font_size=dp(20),
                                    on_tap=lambda: self._zoom(1 / 1.3)))
        bar.add_widget(RaisedButton("+", font_size=dp(20),
                                    on_tap=lambda: self._zoom(1.3)))
        bar.add_widget(RaisedButton("Вписать", variant="primary",
                                    on_tap=lambda: self.view.reset_view()))
        self.view_root.add_widget(bar)

    def _zoom(self, factor):
        self.view.zoom = max(0.2, min(self.view.zoom * factor, 40.0))
        self.view.redraw()

    # ---------------------------------------------------------- общие методы

    def refresh(self):
        self._fill_results()
        self._update_summary()
        self._update_scheme_row()
        self.view.update(self.schemes, self.workpiece)

    def _update_summary(self):
        s = self.schemes[self.active]
        if not s.is_valid:
            for lbl in self.summary_labels:
                lbl.text = "—"
            self.mode_label.text = ""
            return
        r = calculate(s, self.workpiece)
        values = (
            "%.3f мм" % r.spot_surface_mm,
            fmt_density(r.power_density_surface),
            "%.0f Дж/мм" % r.linear_energy_j_mm
            if r.linear_energy_j_mm else "—",
        )
        for i, (lbl, text) in enumerate(zip(self.summary_labels, values)):
            changed = text != self._prev_summary[i]
            lbl.text = text          # присваиваем всегда: после смены темы
            if changed:              # метки создаются заново и пусты
                flash(lbl)
        self._prev_summary = list(values)

        role, caption = th.density_level(r.power_density_surface)
        self.mode_label.text = "[color=%s]•[/color]  %s" % (
            th.markup(role), caption)

    # ------------------------------------------------------------ сохранение

    @property
    def _state_path(self):
        return os.path.join(self.storage_dir, "state.json")

    def _save(self, silent=False):
        data = {
            "schemes": [s.to_dict() for s in self.schemes],
            "workpiece": self.workpiece.to_dict(),
            "theme": th.mode(),
        }
        try:
            os.makedirs(self.storage_dir, exist_ok=True)
            with open(self._state_path, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=2)
            if not silent:
                self._toast("Параметры сохранены")
        except OSError as exc:
            self._toast("Не удалось сохранить: %s" % exc)

    def _load(self):
        try:
            with open(self._state_path, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            return
        try:
            self.schemes = [Scheme.from_dict(d) for d in data["schemes"]]
            self.workpiece = Workpiece.from_dict(data["workpiece"])
            th.set_mode(data.get("theme", "dark"))
        except (KeyError, TypeError):
            pass

    def _export_csv(self, results):
        path = os.path.join(self.storage_dir, "raschet_optiki.csv")
        try:
            os.makedirs(self.storage_dir, exist_ok=True)
            with open(path, "w", encoding="utf-8-sig") as fh:
                fh.write("Параметр;" + ";".join(
                    self.schemes[i].name for i, _ in results) + "\n")
                for caption, attr, fmt in RESULT_ROWS:
                    cells = []
                    for _, res in results:
                        v = getattr(res, attr)
                        cells.append("" if v is None
                                     else (fmt % v).replace(".", ","))
                    fh.write("%s;%s\n" % (caption, ";".join(cells)))
            self._toast("Сохранено: %s" % path)
        except OSError as exc:
            self._toast("Ошибка выгрузки: %s" % exc)

    def _toast(self, text):
        content = Label(text=text, font_size=dp(13), color=th.c("text"))
        popup = Popup(title="", separator_height=0, content=content,
                      size_hint=(0.86, None), height=dp(130),
                      background_color=th.c("surface"))
        popup.open()
        Clock.schedule_once(lambda *a: popup.dismiss(), 1.8)
