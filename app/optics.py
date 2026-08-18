# -*- coding: utf-8 -*-
"""
Ядро расчёта фокусировки лазерного излучения на детали.

Перенесено из книги «Расчет оптики» (лист «Сравнение оптических схем»).
Модуль не зависит от Kivy — его можно использовать отдельно и тестировать.

Система координат:
    y = 0    — поверхность обрабатываемой детали;
    y > 0    — над поверхностью (в сторону оптики);
    y = -t   — корень шва (нижняя поверхность пластины толщиной t).
Положение фокуса dz: «+» — перетяжка над поверхностью, «-» — под поверхностью.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict
from typing import Optional

# --- единицы измерения -------------------------------------------------------

SPEED_UNITS = ("м/мин", "мм/с")
POWER_UNITS = ("кВт", "Вт")


def speed_to_mm_s(value: float, unit: str) -> float:
    """Скорость обработки -> мм/с."""
    if unit == "м/мин":
        return value * 1000.0 / 60.0
    return value


def power_to_w(value: float, unit: str) -> float:
    """Мощность -> Вт."""
    if unit == "кВт":
        return value * 1000.0
    return value


# --- исходные данные схемы ---------------------------------------------------


@dataclass
class Scheme:
    """Исходные данные одной оптической схемы."""

    name: str = "Схема 1"
    wavelength_um: float = 1.07          # длина волны, мкм
    fiber_diameter_um: float = 200.0     # диаметр волокна, мкм
    bpp_mm_mrad: float = 7.07            # BPP, мм*мрад
    collimator_mm: float = 160.0         # фокусное расстояние коллиматора, мм
    focusator_mm: float = 300.0          # фокусное расстояние фокусатора, мм
    focus_position_mm: float = 0.0       # положение фокуса, мм ("+" над деталью)
    tilt_angle_deg: float = 0.0          # угол наклона луча, градусы
    speed: float = 1.2                   # скорость обработки
    speed_unit: str = "м/мин"
    power: float = 10.0                  # мощность излучения (непрерывный режим)
    power_unit: str = "кВт"

    @property
    def is_valid(self) -> bool:
        """Схема заполнена и пригодна для расчёта."""
        return (
            self.wavelength_um > 0
            and self.fiber_diameter_um > 0
            and self.bpp_mm_mrad > 0
            and self.collimator_mm > 0
            and self.focusator_mm > 0
        )

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Scheme":
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})


@dataclass
class Workpiece:
    """Деталь, разделка кромок, присадочная проволока, сопло."""

    thickness_mm: float = 18.0           # толщина обрабатываемой пластины
    draw_plate: bool = True
    width_left_mm: float = 5.0           # ширина пластины слева
    width_right_mm: float = 5.0          # ширина пластины справа
    gap_mm: float = 2.0                  # зазор в стыке
    bevel_left_deg: float = 5.0          # угол скоса левой кромки (+/-)
    bevel_right_deg: float = -10.0       # угол скоса правой кромки (+/-)
    joint_offset_mm: float = 0.0         # смещение стыка вправо/влево

    wire_count: int = 1                  # 0 / 1 / 2 проволоки
    wire_diameter_mm: float = 1.6
    wire_offset_mm: float = 0.0          # смещение проволок влево/вправо

    draw_nozzle: bool = False            # сопло для резки
    nozzle_d_upper_mm: float = 15.0
    nozzle_d_lower_mm: float = 3.0
    nozzle_height_mm: float = 10.0       # общая высота
    nozzle_cone_mm: float = 3.0          # высота конуса
    nozzle_offset_mm: float = 0.0        # смещение сопла влево-вправо
    nozzle_gap_mm: float = 5.0           # зазор между соплом и пластиной

    y_max_mm: float = 70.0               # верхняя граница построения луча
    y_min_mm: float = -20.0              # нижняя граница построения луча
    target_spot_mm: float = 5.0          # требуемый размер пятна на поверхности

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Workpiece":
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})


# --- результаты --------------------------------------------------------------


@dataclass
class Result:
    """Результаты расчёта одной схемы."""

    name: str = ""
    spot_focus_mm: float = 0.0           # диаметр пятна в фокусе (перетяжке)
    waist_length_mm: float = 0.0         # длина перетяжки (2*z_R)
    rayleigh_mm: float = 0.0             # длина Рэлея
    spot_surface_mm: float = 0.0         # диаметр пятна на поверхности детали
    spot_root_mm: float = 0.0            # диаметр пятна в корне шва
    magnification: float = 0.0           # коэффициент увеличения оптики
    m2: float = 0.0                      # параметр качества пучка M2
    divergence_full_mrad: float = 0.0    # полный угол расходимости после фокусатора
    beam_on_lens_mm: float = 0.0         # диаметр пучка на линзе / защитном стекле
    focus_shift_per_mm: float = 0.0      # сдвиг фокуса при сдвиге коллиматора на 1 мм
    required_defocus_mm: Optional[float] = None  # расфокусировка под заданное пятно
    power_w: float = 0.0
    speed_mm_s: float = 0.0
    power_density_surface: float = 0.0   # Вт/см2 на поверхности детали
    power_density_focus: float = 0.0     # Вт/см2 в перетяжке
    power_density_lens: float = 0.0      # Вт/см2 на линзе
    linear_energy_j_mm: float = 0.0      # погонная энергия, Дж/мм
    warnings: list = field(default_factory=list)


# --- расчёт ------------------------------------------------------------------


def spot_diameter_at(d0_mm: float, rayleigh_mm: float, dz_mm: float) -> float:
    """Диаметр пятна на расстоянии dz от перетяжки (гиперболическая каустика)."""
    if rayleigh_mm <= 0:
        return d0_mm
    return d0_mm * math.sqrt(1.0 + (dz_mm / rayleigh_mm) ** 2)


def _power_density(power_w: float, diameter_mm: float) -> float:
    """Средняя плотность мощности по пятну, Вт/см2."""
    if power_w <= 0 or diameter_mm <= 0:
        return 0.0
    area_cm2 = math.pi * 0.25 * (diameter_mm / 10.0) ** 2
    return power_w / area_cm2 if area_cm2 > 0 else 0.0


def calculate(scheme: Scheme, wp: Workpiece) -> Result:
    """Полный расчёт одной оптической схемы."""
    res = Result(name=scheme.name)
    if not scheme.is_valid:
        res.warnings.append("Схема не заполнена — расчёт не выполнен")
        return res

    # Геометрическая оптика: перенос изображения торца волокна
    magnification = scheme.focusator_mm / scheme.collimator_mm
    d0 = 0.001 * scheme.fiber_diameter_um * magnification   # мм
    w0 = 0.5 * d0

    # Длина перетяжки (удвоенная длина Рэлея) через BPP [мм*мрад]
    # z_R = w0 / theta, theta = BPP / w0 [мрад] => z_R = 1000 * w0^2 / BPP [мм]
    rayleigh = 1000.0 * w0 * w0 / scheme.bpp_mm_mrad
    waist_len = 2.0 * rayleigh

    dz = scheme.focus_position_mm
    t = wp.thickness_mm

    res.spot_focus_mm = d0
    res.rayleigh_mm = rayleigh
    res.waist_length_mm = waist_len
    res.magnification = magnification
    res.m2 = scheme.bpp_mm_mrad * math.pi / scheme.wavelength_um
    res.beam_on_lens_mm = scheme.collimator_mm * 4.0 * scheme.bpp_mm_mrad / scheme.fiber_diameter_um
    res.divergence_full_mrad = 2.0 * scheme.bpp_mm_mrad / w0 if w0 > 0 else 0.0
    res.focus_shift_per_mm = magnification ** 2

    res.spot_surface_mm = spot_diameter_at(d0, rayleigh, dz)
    res.spot_root_mm = spot_diameter_at(d0, rayleigh, dz + t)

    # Расфокусировка, дающая требуемое пятно на поверхности
    if wp.target_spot_mm > 0:
        ratio = wp.target_spot_mm / d0
        if ratio >= 1.0:
            res.required_defocus_mm = rayleigh * math.sqrt(ratio * ratio - 1.0)
        else:
            res.warnings.append(
                "Требуемое пятно %.3f мм меньше пятна в фокусе %.3f мм — недостижимо"
                % (wp.target_spot_mm, d0)
            )

    # Энергетика
    res.power_w = power_to_w(scheme.power, scheme.power_unit)
    res.speed_mm_s = speed_to_mm_s(scheme.speed, scheme.speed_unit)
    res.power_density_surface = _power_density(res.power_w, res.spot_surface_mm)
    res.power_density_focus = _power_density(res.power_w, d0)
    res.power_density_lens = _power_density(res.power_w, res.beam_on_lens_mm)
    if res.speed_mm_s > 0:
        res.linear_energy_j_mm = res.power_w / res.speed_mm_s

    # Предупреждения
    if scheme.focusator_mm + dz < t:
        res.warnings.append("Фокусатор ближе к детали, чем рабочее расстояние")
    if res.power_density_lens > 5000:
        res.warnings.append(
            "Плотность мощности на защитном стекле %.0f Вт/см2 — проверьте охлаждение"
            % res.power_density_lens
        )
    if wp.gap_mm > 0.6 * res.spot_surface_mm and wp.wire_count == 0:
        res.warnings.append(
            "Зазор %.2f мм велик для пятна %.2f мм без присадочной проволоки"
            % (wp.gap_mm, res.spot_surface_mm)
        )
    return res


def caustic_points(scheme: Scheme, wp: Workpiece, n: int = 400):
    """
    Точки контура каустики с учётом наклона луча.

    Возвращает (left, right) — два списка (x, y) в мм: левая и правая
    образующие пучка. Начало координат — точка пересечения оси пучка
    с поверхностью детали.
    """
    if not scheme.is_valid:
        return [], []

    magnification = scheme.focusator_mm / scheme.collimator_mm
    d0 = 0.001 * scheme.fiber_diameter_um * magnification
    rayleigh = 1000.0 * (0.5 * d0) ** 2 / scheme.bpp_mm_mrad
    dz = scheme.focus_position_mm

    a = math.radians(scheme.tilt_angle_deg)
    ca, sa = math.cos(a), math.sin(a)

    # По оси пучка идём от y_max до y_min с поправкой на наклон
    y_top = wp.y_max_mm / max(ca, 1e-6)
    y_bot = wp.y_min_mm / max(ca, 1e-6)
    # Луч не может существовать выше выходной апертуры фокусатора
    y_top = min(y_top, scheme.focusator_mm + dz)

    r_max = 0.5 * scheme.collimator_mm * 4.0 * scheme.bpp_mm_mrad / scheme.fiber_diameter_um

    left, right = [], []
    step = (y_top - y_bot) / max(n - 1, 1)
    for i in range(n):
        y = y_top - i * step
        r = min(0.5 * spot_diameter_at(d0, rayleigh, y - dz), r_max)
        # поворот на угол наклона
        left.append((-r * ca - y * sa, -r * sa + y * ca))
        right.append((r * ca - y * sa, r * sa + y * ca))
    return left, right
