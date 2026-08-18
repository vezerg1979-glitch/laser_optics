# -*- coding: utf-8 -*-
"""Интерфейс приложения «Расчёт фокусировки лазерного излучения»."""

from __future__ import annotations

import json
import os

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem
from kivy.uix.textinput import TextInput

from .beamview import BeamView, SCHEME_COLORS
from .optics import (
    POWER_UNITS,
    SPEED_UNITS,
    Scheme,
    Workpiece,
    calculate,
)

N_SCHEMES = 5


def _f(text, default=0.0):
    """Мягкий разбор числа: принимает и точку, и запятую."""
    try:
        return float(str(text).replace(",", ".").strip())
    except (TypeError, ValueError):
        return default


class Field(BoxLayout):
    """Строка «подпись — поле ввода»."""

    def __init__(self, caption, value, on_change, **kwargs):
        super().__init__(orientation="horizontal", size_hint_y=None,
                         height=dp(42), spacing=dp(6), **kwargs)
        self.add_widget(Label(text=caption, halign="left", valign="middle",
                              size_hint_x=0.62, font_size=dp(13),
                              text_size=(None, dp(40)),
                              shorten=True, shorten_from="right"))
        self.input = TextInput(text=str(value), multiline=False,
                               input_type="number", size_hint_x=0.38,
                               font_size=dp(15), padding=[dp(8), dp(10)])
        self.input.bind(text=lambda inst, val: on_change(val))
        self.add_widget(self.input)

    def set(self, value):
        self.input.text = str(value)


class ChoiceField(BoxLayout):
    """Строка «подпись — выпадающий список»."""

    def __init__(self, caption, values, value, on_change, **kwargs):
        super().__init__(orientation="horizontal", size_hint_y=None,
                         height=dp(42), spacing=dp(6), **kwargs)
        self.add_widget(Label(text=caption, halign="left", valign="middle",
                              size_hint_x=0.62, font_size=dp(13),
                              text_size=(None, dp(40)),
                              shorten=True, shorten_from="right"))
        self.spinner = Spinner(text=str(value), values=[str(v) for v in values],
                               size_hint_x=0.38, font_size=dp(14))
        self.spinner.bind(text=lambda inst, val: on_change(val))
        self.add_widget(self.spinner)

    def set(self, value):
        self.spinner.text = str(value)


class SectionLabel(Label):
    def __init__(self, text, **kwargs):
        super().__init__(text="[b]%s[/b]" % text, markup=True,
                         size_hint_y=None, height=dp(36), halign="left",
                         valign="bottom", font_size=dp(15), **kwargs)
        self.bind(size=lambda inst, val: setattr(inst, "text_size", val))


class MainUI(TabbedPanel):
    """Три вкладки: параметры, результаты, схема."""

    def __init__(self, storage_dir: str, **kwargs):
        super().__init__(do_default_tab=False, tab_width=dp(120), **kwargs)
        self.storage_dir = storage_dir
        self.schemes = [Scheme(name="Схема %d" % (i + 1)) for i in range(N_SCHEMES)]
        # по умолчанию заполнена только первая схема
        for s in self.schemes[1:]:
            s.collimator_mm = 0.0
            s.focusator_mm = 0.0
        self.workpiece = Workpiece()
        self.active = 0
        self._load()

        self._build_input_tab()
        self._build_result_tab()
        self._build_view_tab()
        self.refresh()

    # ------------------------------------------------------------------ ввод

    def _build_input_tab(self):
        tab = TabbedPanelItem(text="Параметры")
        root = BoxLayout(orientation="vertical")

        top = BoxLayout(size_hint_y=None, height=dp(48), padding=dp(6),
                        spacing=dp(6))
        self.scheme_spinner = Spinner(
            text=self.schemes[0].name,
            values=[s.name for s in self.schemes], font_size=dp(14))
        self.scheme_spinner.bind(text=self._on_scheme_switch)
        top.add_widget(Label(text="Схема:", size_hint_x=0.28, font_size=dp(14)))
        top.add_widget(self.scheme_spinner)
        clear_btn = Button(text="Очистить", size_hint_x=0.32, font_size=dp(13))
        clear_btn.bind(on_release=lambda *a: self._clear_scheme())
        top.add_widget(clear_btn)
        root.add_widget(top)

        scroll = ScrollView()
        self.form = GridLayout(cols=1, size_hint_y=None, padding=dp(8),
                               spacing=dp(2))
        self.form.bind(minimum_height=self.form.setter("height"))
        scroll.add_widget(self.form)
        root.add_widget(scroll)
        self._build_form()

        bottom = BoxLayout(size_hint_y=None, height=dp(52), padding=dp(6),
                           spacing=dp(6))
        save = Button(text="Сохранить", font_size=dp(14))
        save.bind(on_release=lambda *a: self._save())
        reset = Button(text="Сбросить всё", font_size=dp(14))
        reset.bind(on_release=lambda *a: self._reset_all())
        bottom.add_widget(save)
        bottom.add_widget(reset)
        root.add_widget(bottom)

        tab.add_widget(root)
        self.add_widget(tab)

    def _scheme_setter(self, attr, cast=float):
        def setter(value):
            setattr(self.schemes[self.active], attr,
                    _f(value) if cast is float else value)
            self.refresh()
        return setter

    def _wp_setter(self, attr, cast=float):
        def setter(value):
            if cast is float:
                setattr(self.workpiece, attr, _f(value))
            elif cast is int:
                setattr(self.workpiece, attr, int(_f(value)))
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

        def add_scheme(caption, attr):
            fld = Field(caption, getattr(s, attr), self._scheme_setter(attr))
            self.scheme_fields[attr] = fld
            self.form.add_widget(fld)

        self.form.add_widget(SectionLabel("Излучение и оптика"))
        add_scheme("Длина волны, мкм", "wavelength_um")
        add_scheme("Диаметр волокна, мкм", "fiber_diameter_um")
        add_scheme("BPP, мм·мрад", "bpp_mm_mrad")
        add_scheme("Коллиматор, мм", "collimator_mm")
        add_scheme("Фокусатор, мм", "focusator_mm")
        add_scheme("Положение фокуса, мм (+ над деталью)", "focus_position_mm")
        add_scheme("Угол наклона луча, °", "tilt_angle_deg")

        self.form.add_widget(SectionLabel("Режим обработки"))
        add_scheme("Скорость обработки", "speed")
        self.speed_unit = ChoiceField(
            "Единицы скорости", SPEED_UNITS, s.speed_unit,
            self._scheme_setter("speed_unit", cast=str))
        self.form.add_widget(self.speed_unit)
        add_scheme("Мощность излучения", "power")
        self.power_unit = ChoiceField(
            "Единицы мощности", POWER_UNITS, s.power_unit,
            self._scheme_setter("power_unit", cast=str))
        self.form.add_widget(self.power_unit)

        self.form.add_widget(SectionLabel("Деталь и разделка"))
        self.form.add_widget(Field("Толщина детали, мм", wp.thickness_mm,
                                   self._wp_setter("thickness_mm")))
        self.form.add_widget(ChoiceField("Рисовать деталь", ("Да", "Нет"),
                                         "Да" if wp.draw_plate else "Нет",
                                         self._wp_setter("draw_plate", bool)))
        self.form.add_widget(Field("Ширина слева, мм", wp.width_left_mm,
                                   self._wp_setter("width_left_mm")))
        self.form.add_widget(Field("Ширина справа, мм", wp.width_right_mm,
                                   self._wp_setter("width_right_mm")))
        self.form.add_widget(Field("Зазор, мм", wp.gap_mm,
                                   self._wp_setter("gap_mm")))
        self.form.add_widget(Field("Угол скоса левой кромки, °",
                                   wp.bevel_left_deg,
                                   self._wp_setter("bevel_left_deg")))
        self.form.add_widget(Field("Угол скоса правой кромки, °",
                                   wp.bevel_right_deg,
                                   self._wp_setter("bevel_right_deg")))
        self.form.add_widget(Field("Смещение стыка, мм", wp.joint_offset_mm,
                                   self._wp_setter("joint_offset_mm")))

        self.form.add_widget(SectionLabel("Присадочная проволока"))
        self.form.add_widget(ChoiceField(
            "Количество проволок", ("0", "1", "2"), str(wp.wire_count),
            self._wp_setter("wire_count", int)))
        self.form.add_widget(Field("Диаметр проволоки, мм", wp.wire_diameter_mm,
                                   self._wp_setter("wire_diameter_mm")))
        self.form.add_widget(Field("Смещение проволоки, мм", wp.wire_offset_mm,
                                   self._wp_setter("wire_offset_mm")))

        self.form.add_widget(SectionLabel("Сопло для резки"))
        self.form.add_widget(ChoiceField("Показывать сопло", ("Да", "Нет"),
                                         "Да" if wp.draw_nozzle else "Нет",
                                         self._wp_setter("draw_nozzle", bool)))
        self.form.add_widget(Field("Диаметр верхний, мм", wp.nozzle_d_upper_mm,
                                   self._wp_setter("nozzle_d_upper_mm")))
        self.form.add_widget(Field("Диаметр нижний, мм", wp.nozzle_d_lower_mm,
                                   self._wp_setter("nozzle_d_lower_mm")))
        self.form.add_widget(Field("Общая высота, мм", wp.nozzle_height_mm,
                                   self._wp_setter("nozzle_height_mm")))
        self.form.add_widget(Field("Высота конуса, мм", wp.nozzle_cone_mm,
                                   self._wp_setter("nozzle_cone_mm")))
        self.form.add_widget(Field("Смещение сопла, мм", wp.nozzle_offset_mm,
                                   self._wp_setter("nozzle_offset_mm")))
        self.form.add_widget(Field("Зазор сопло—деталь, мм", wp.nozzle_gap_mm,
                                   self._wp_setter("nozzle_gap_mm")))

        self.form.add_widget(SectionLabel("Построение и цель"))
        self.form.add_widget(Field("Требуемое пятно на поверхности, мм",
                                   wp.target_spot_mm,
                                   self._wp_setter("target_spot_mm")))
        self.form.add_widget(Field("Максимальный Y для луча, мм", wp.y_max_mm,
                                   self._wp_setter("y_max_mm")))
        self.form.add_widget(Field("Минимальный Y для луча, мм", wp.y_min_mm,
                                   self._wp_setter("y_min_mm")))

    def _on_scheme_switch(self, spinner, text):
        for i, s in enumerate(self.schemes):
            if s.name == text:
                self.active = i
                break
        self._build_form()
        self.refresh()

    def _clear_scheme(self):
        name = self.schemes[self.active].name
        self.schemes[self.active] = Scheme(name=name, collimator_mm=0.0,
                                           focusator_mm=0.0)
        self._build_form()
        self.refresh()

    def _reset_all(self):
        self.schemes = [Scheme(name="Схема %d" % (i + 1)) for i in range(N_SCHEMES)]
        for s in self.schemes[1:]:
            s.collimator_mm = 0.0
            s.focusator_mm = 0.0
        self.workpiece = Workpiece()
        self.active = 0
        self.scheme_spinner.text = self.schemes[0].name
        self._build_form()
        self.refresh()

    # ------------------------------------------------------------ результаты

    def _build_result_tab(self):
        tab = TabbedPanelItem(text="Результаты")
        scroll = ScrollView()
        self.result_box = GridLayout(cols=1, size_hint_y=None, padding=dp(10),
                                     spacing=dp(4))
        self.result_box.bind(minimum_height=self.result_box.setter("height"))
        scroll.add_widget(self.result_box)
        tab.add_widget(scroll)
        self.add_widget(tab)

    def _fill_results(self):
        self.result_box.clear_widgets()
        rows = [
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

        results = [(i, calculate(s, self.workpiece))
                   for i, s in enumerate(self.schemes) if s.is_valid]
        if not results:
            self.result_box.add_widget(Label(
                text="Заполните коллиматор и фокусатор хотя бы одной схемы",
                size_hint_y=None, height=dp(60), font_size=dp(14)))
            return

        header = GridLayout(cols=1 + len(results), size_hint_y=None,
                            height=dp(34), spacing=dp(2))
        header.add_widget(Label(text="[b]Параметр[/b]", markup=True,
                                font_size=dp(12), halign="left",
                                text_size=(dp(180), dp(32))))
        for idx, _ in results:
            col = SCHEME_COLORS[idx % len(SCHEME_COLORS)]
            header.add_widget(Label(
                text="[b][color=%02x%02x%02x]%s[/color][/b]" % (
                    int(col[0] * 255), int(col[1] * 255), int(col[2] * 255),
                    self.schemes[idx].name),
                markup=True, font_size=dp(12)))
        self.result_box.add_widget(header)

        for caption, attr, fmt in rows:
            grid = GridLayout(cols=1 + len(results), size_hint_y=None,
                              height=dp(32), spacing=dp(2))
            grid.add_widget(Label(text=caption, font_size=dp(12), halign="left",
                                  valign="middle", text_size=(dp(180), dp(30)),
                                  shorten=True, shorten_from="right"))
            for _, res in results:
                value = getattr(res, attr)
                grid.add_widget(Label(
                    text="—" if value is None else fmt % value,
                    font_size=dp(12)))
            self.result_box.add_widget(grid)

        for idx, res in results:
            for w in res.warnings:
                lbl = Label(text="[color=ffcc55]! %s: %s[/color]"
                                 % (self.schemes[idx].name, w),
                            markup=True, size_hint_y=None, font_size=dp(12),
                            halign="left", valign="top")
                lbl.bind(width=lambda i, v: setattr(i, "text_size", (v, None)),
                         texture_size=lambda i, v: setattr(i, "height", v[1] + dp(8)))
                self.result_box.add_widget(lbl)

        export = Button(text="Выгрузить отчёт в CSV", size_hint_y=None,
                        height=dp(46), font_size=dp(14))
        export.bind(on_release=lambda *a: self._export_csv(rows, results))
        self.result_box.add_widget(export)

    # ----------------------------------------------------------------- схема

    def _build_view_tab(self):
        tab = TabbedPanelItem(text="Схема")
        root = BoxLayout(orientation="vertical")
        self.view = BeamView()
        root.add_widget(self.view)
        bar = BoxLayout(size_hint_y=None, height=dp(48), padding=dp(6),
                        spacing=dp(6))
        for caption, factor in (("−", 1 / 1.3), ("+", 1.3)):
            btn = Button(text=caption, font_size=dp(20))
            btn.bind(on_release=lambda inst, f=factor: self._zoom(f))
            bar.add_widget(btn)
        fit = Button(text="Вписать", font_size=dp(14))
        fit.bind(on_release=lambda *a: self.view.reset_view())
        bar.add_widget(fit)
        root.add_widget(bar)
        tab.add_widget(root)
        self.add_widget(tab)

    def _zoom(self, factor):
        self.view.zoom = max(0.2, min(self.view.zoom * factor, 40.0))
        self.view.redraw()

    # ---------------------------------------------------------- общие методы

    def refresh(self):
        self._fill_results()
        self.view.update(self.schemes, self.workpiece)

    # -------------------------------------------------------- сохранение

    @property
    def _state_path(self):
        return os.path.join(self.storage_dir, "state.json")

    def _save(self):
        data = {
            "schemes": [s.to_dict() for s in self.schemes],
            "workpiece": self.workpiece.to_dict(),
        }
        try:
            os.makedirs(self.storage_dir, exist_ok=True)
            with open(self._state_path, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=2)
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
        except (KeyError, TypeError):
            pass

    def _export_csv(self, rows, results):
        path = os.path.join(self.storage_dir, "raschet_optiki.csv")
        try:
            os.makedirs(self.storage_dir, exist_ok=True)
            with open(path, "w", encoding="utf-8-sig") as fh:
                fh.write("Параметр;" +
                         ";".join(self.schemes[i].name for i, _ in results) + "\n")
                for caption, attr, fmt in rows:
                    cells = []
                    for _, res in results:
                        v = getattr(res, attr)
                        cells.append("" if v is None else (fmt % v).replace(".", ","))
                    fh.write("%s;%s\n" % (caption, ";".join(cells)))
            self._toast("Сохранено: %s" % path)
        except OSError as exc:
            self._toast("Ошибка выгрузки: %s" % exc)

    def _toast(self, text):
        popup = Popup(title="", separator_height=0,
                      content=Label(text=text, font_size=dp(13)),
                      size_hint=(0.86, None), height=dp(140))
        popup.open()
        Clock.schedule_once(lambda *a: popup.dismiss(), 1.8)
