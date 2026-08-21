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

from . import materials

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

    material_key: str = materials.DEFAULT_KEY   # материал детали
    preheat_c: float = 20.0              # температура предварительного подогрева
    joint_type: str = materials.DEFAULT_JOINT   # тип соединения

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
class ThermalResult:
    """Оценка термического цикла сварки."""

    cycle_name: str = ""                 # обозначение, например t8/5
    cycle_range: str = ""                # «800–500 °C»
    cooling_time_s: float = 0.0          # время охлаждения в этом интервале
    cooling_rate_k_s: float = 0.0        # скорость охлаждения в середине
    heat_flow: str = ""                  # «трёхмерный» или «двумерный»
    transition_thickness_mm: float = 0.0  # толщина смены характера отвода
    haz_width_mm: float = 0.0            # ширина ЗТВ от границы сплавления
    haz_temp_c: float = 0.0
    haz_basis: str = ""
    joint_factor: float = 1.0
    heat_input_j_mm: float = 0.0         # поглощённая погонная энергия
    notes: list = field(default_factory=list)


@dataclass
class WeldResult:
    """Оценка формы шва для выбранного материала."""

    material_name: str = ""
    material_short: str = ""             # краткое имя для узкого столбца
    mode: str = ""                       # «кинжальный» или «теплопроводность»
    depth_mm: float = 0.0                # глубина проплавления
    width_mm: float = 0.0                # ширина шва по лицевой стороне
    area_mm2: float = 0.0                # площадь сечения расплава
    aspect: float = 0.0                  # отношение глубины к ширине
    absorbed_w: float = 0.0              # поглощённая мощность
    melting_enthalpy: float = 0.0        # объёмная энтальпия плавления
    full_penetration: bool = False       # хватает ли на всю толщину
    speed_full_penetration: float = 0.0  # скорость полного проплавления, мм/с
    speed_full_m_min: float = 0.0        # то же в м/мин
    notes: list = field(default_factory=list)


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
    weld: Optional["WeldResult"] = None  # оценка формы шва
    thermal: Optional["ThermalResult"] = None  # оценка термического цикла
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

    res.weld = predict_weld(scheme, wp, res)
    res.thermal = predict_thermal(scheme, wp, res, res.weld)

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



# --- форма шва ---------------------------------------------------------------

# Доля площади описанного прямоугольника, занятая расплавом. Кинжальный шов
# в сечении близок к клину с расширением у лицевой поверхности, шов в режиме
# теплопроводности — к половине эллипса.
SHAPE_KEYHOLE = 0.70
SHAPE_CONDUCTION = 0.60


def predict_weld(scheme: Scheme, wp: Workpiece, res: "Result") -> WeldResult:
    """
    Оценка глубины проплавления и ширины шва из энергетического баланса.

    Модель. Поглощённая мощность, за вычетом отведённой теплопроводностью,
    расходуется на нагрев и плавление металла:

        S = k_пл * A * P / (v * H_пл),

    где S — площадь сечения расплава, k_пл — эффективность плавления,
    A — поглощательная способность, H_пл — объёмная энтальпия плавления.

    Ширина шва складывается из диаметра пятна и бокового подплавления за
    время взаимодействия: w = d + 2*sqrt(a * d / v), где a —
    температуропроводность. Глубина получается из площади и ширины с учётом
    коэффициента формы сечения.

    Границы применимости. Это оценка порядка величины для стыкового шва без
    разделки и без присадки, при устойчивом процессе и нормальном падении
    луча. Модель не учитывает наклон луча, защитный газ, зазор, колебания
    луча, состояние поверхности и переходные режимы. Расхождение с
    экспериментом в 20–30 % для неё нормально, поэтому для аттестации
    режима она не годится — только для прикидки и сужения области поиска
    перед натурными пробами.
    """
    mat = materials.get(wp.material_key)
    out = WeldResult(material_name=mat.name, material_short=mat.short_name)

    if not scheme.is_valid or res.power_w <= 0 or res.speed_mm_s <= 0:
        out.notes.append("Задайте мощность и скорость обработки")
        return out

    h_melt = mat.melting_enthalpy_j_mm3
    out.melting_enthalpy = h_melt

    keyhole = res.power_density_surface >= mat.keyhole_threshold
    out.mode = "кинжальный" if keyhole else "теплопроводность"
    absorptivity = (mat.absorptivity_keyhole if keyhole
                    else mat.absorptivity_conduction)
    out.absorbed_w = absorptivity * res.power_w

    # Геометрия шва как функция скорости. Скорость входит и в площадь
    # расплава, и в ширину (через время взаимодействия), поэтому расчёт
    # вынесен в отдельную функцию — она же используется при подборе
    # скорости сквозного проплавления.
    energy_coeff = mat.melting_efficiency * out.absorbed_w / h_melt
    d_spot = res.spot_surface_mm
    shape = SHAPE_KEYHOLE if keyhole else SHAPE_CONDUCTION
    # Ограничение по отношению глубины к ширине. Парогазовый канал не
    # сужается вслед за пятном: при жёсткой фокусировке его поперечник
    # выходит на насыщение. Без этого ограничения энергетический баланс
    # при малом пятне даёт отношения вроде 30:1, каких не бывает.
    # В режиме теплопроводности канала нет вовсе, тепло идёт во все
    # стороны примерно одинаково, поэтому предел равен единице.
    limit = mat.max_aspect if keyhole else 1.0

    def geometry(speed_mm_s):
        """Возвращает (площадь, ширина, глубина) при заданной скорости."""
        if speed_mm_s <= 0:
            return 0.0, 0.0, 0.0
        area = energy_coeff / speed_mm_s
        # Ширина: пятно плюс боковое подплавление за время взаимодействия
        lateral = math.sqrt(mat.diffusivity_mm2_s * d_spot / speed_mm_s)
        width = d_spot + 2.0 * lateral
        depth = area / (shape * width)
        if depth > limit * width:
            # Излишек площади уходит в расширение шва
            width = math.sqrt(area / (shape * limit))
            depth = limit * width
        return area, width, depth

    area, width, depth = geometry(res.speed_mm_s)
    out.area_mm2 = area
    out.width_mm = width
    out.depth_mm = depth
    out.aspect = depth / width if width > 0 else 0.0

    # Полное проплавление и скорость, при которой оно достигается.
    # Глубина монотонно убывает со скоростью, но зависимость неявная
    # (скорость входит и в площадь, и в ширину), поэтому уравнение
    # решается делением отрезка пополам, а не переворачиванием формулы.
    t = wp.thickness_mm
    if t > 0:
        out.full_penetration = depth >= t
        lo, hi = 1e-3, 1e5
        if geometry(lo)[2] >= t:
            for _ in range(80):
                mid = 0.5 * (lo + hi)
                if geometry(mid)[2] >= t:
                    lo = mid
                else:
                    hi = mid
            out.speed_full_penetration = lo
            out.speed_full_m_min = lo * 0.06

    # Пояснения
    # Переход между режимами модель делает скачком, тогда как в
    # действительности канал образуется постепенно. Вблизи порога
    # расчёту доверять нельзя ни в ту, ни в другую сторону.
    ratio = res.power_density_surface / mat.keyhole_threshold
    if 0.7 < ratio < 1.5:
        out.notes.append(
            "Плотность мощности вблизи порога образования канала — "
            "переходная область, где расчёт особенно груб")

    if not keyhole:
        out.notes.append(
            "Плотность мощности %.2g Вт/см² ниже порога %.2g Вт/см² — "
            "канал не образуется, шов широкий и неглубокий"
            % (res.power_density_surface, mat.keyhole_threshold))
    if t > 0 and not out.full_penetration:
        if out.speed_full_m_min > 0:
            out.notes.append(
                "Проплавление %.1f мм при толщине %.1f мм — неполное; для "
                "сквозного шва снизьте скорость до %.2f м/мин"
                % (depth, t, out.speed_full_m_min))
        else:
            out.notes.append(
                "Проплавление %.1f мм при толщине %.1f мм — неполное, и "
                "снижением скорости этого не исправить: не хватает мощности"
                % (depth, t))
    if t > 0 and depth > 1.6 * t and out.speed_full_m_min > 0:
        out.notes.append(
            "Запас по проплавлению более чем полуторный — скорость можно "
            "поднять примерно до %.2f м/мин" % out.speed_full_m_min)
    if out.aspect > 12:
        out.notes.append(
            "Отношение глубины к ширине %.0f:1 — режим на границе "
            "устойчивости канала, вероятны поры в корне" % out.aspect)
    if mat.note:
        out.notes.append(mat.note)
    return out



# --- термический цикл --------------------------------------------------------


def predict_thermal(scheme: Scheme, wp: Workpiece, res: "Result",
                    weld: "WeldResult") -> ThermalResult:
    """
    Оценка времени и скорости охлаждения по формулам EN 1011-2.

    Отвод тепла бывает двух характеров. В толстой детали тепло уходит во
    все стороны — отвод трёхмерный, и время охлаждения не зависит от
    толщины. В тонкой пластина прогревается насквозь, отвод становится
    двумерным, и время охлаждения растёт обратно квадрату толщины.
    Граничная толщина вычисляется и сравнивается с фактической.

    Трёхмерный отвод:
        t = F3 * E / (2*pi*λ) * (1/(T2−T0) − 1/(T1−T0))

    Двумерный отвод:
        t = F2 * E² / (4*pi*λ*ρc*d²) * (1/(T2−T0)² − 1/(T1−T0)²)

    Здесь E — поглощённая погонная энергия, F2 и F3 — коэффициенты формы
    соединения, T0 — температура подогрева. Для сталей интервал берётся
    800–500 °C, для других материалов — свой, см. app/materials.py.

    Ширина зоны термического влияния оценивается из того, что при
    трёхмерном отводе максимальная температура убывает обратно квадрату
    расстояния от оси шва. Отсюда отношение радиуса изотермы границы ЗТВ
    к радиусу границы сплавления зависит только от температур, а
    абсолютный размер берётся от рассчитанной полуширины шва.

    Границы применимости те же, что у модели формы шва: это оценка для
    однопроходного шва при устойчивом процессе. Формулы EN 1011-2
    выведены для дуговой сварки и на лазерных режимах с очень высокой
    концентрацией энергии дают заниженное время охлаждения.
    """
    mat = materials.get(wp.material_key)
    out = ThermalResult(cycle_name=mat.cycle_name,
                        haz_temp_c=mat.haz_temp_c,
                        haz_basis=mat.haz_basis)
    out.cycle_range = "%.0f–%.0f °C" % (mat.cycle_upper_c, mat.cycle_lower_c)

    if weld is None or weld.absorbed_w <= 0 or res.speed_mm_s <= 0:
        out.notes.append("Задайте мощность и скорость обработки")
        return out

    t0 = wp.preheat_c
    t_up = mat.cycle_upper_c
    t_low = mat.cycle_lower_c
    if t0 >= t_low - 20.0:
        out.notes.append(
            "Подогрев %.0f °C не ниже нижней границы интервала %s — "
            "время охлаждения в этом интервале не определено"
            % (t0, out.cycle_range))
        return out

    f2, f3 = materials.JOINT_FACTORS.get(
        wp.joint_type, materials.JOINT_FACTORS[materials.DEFAULT_JOINT])

    lam = mat.conductivity_w_mmk
    rho_c = mat.volumetric_heat_j_mm3k
    energy = weld.absorbed_w / res.speed_mm_s      # Дж/мм, уже поглощённая
    out.heat_input_j_mm = energy

    d_up = t_up - t0
    d_low = t_low - t0

    # Толщина, на которой характер отвода тепла меняется
    transition = math.sqrt(energy / (2.0 * rho_c) * (1.0 / d_low + 1.0 / d_up))
    out.transition_thickness_mm = transition

    thickness = wp.thickness_mm
    if thickness <= 0 or thickness >= transition:
        out.heat_flow = "трёхмерный"
        out.joint_factor = f3
        cooling = f3 * energy / (2.0 * math.pi * lam) * (1.0 / d_low
                                                         - 1.0 / d_up)
    else:
        out.heat_flow = "двумерный"
        out.joint_factor = f2
        cooling = (f2 * energy ** 2
                   / (4.0 * math.pi * lam * rho_c * thickness ** 2)
                   * (1.0 / d_low ** 2 - 1.0 / d_up ** 2))
    out.cooling_time_s = cooling
    if cooling > 0:
        out.cooling_rate_k_s = (t_up - t_low) / cooling

    # Ширина ЗТВ: отношение изотерм при трёхмерном отводе
    t_melt = mat.melting_c
    if weld.width_mm > 0 and mat.haz_temp_c > t0 and t_melt > t0:
        ratio = math.sqrt((t_melt - t0) / (mat.haz_temp_c - t0))
        out.haz_width_mm = 0.5 * weld.width_mm * (ratio - 1.0)

    # Пояснения
    if mat.cycle_min_s > 0 and cooling < mat.cycle_min_s:
        out.notes.append(
            "Время охлаждения %s = %.2f с ниже рекомендуемых %.0f–%.0f с — "
            "вероятны закалочные структуры и повышенная твёрдость в ЗТВ; "
            "рассмотрите подогрев" % (mat.cycle_name, cooling,
                                      mat.cycle_min_s, mat.cycle_max_s))
    elif mat.cycle_max_s > 0 and cooling > mat.cycle_max_s:
        out.notes.append(
            "Время охлаждения %s = %.1f с выше рекомендуемых %.0f–%.0f с — "
            "возможен рост зерна и снижение ударной вязкости"
            % (mat.cycle_name, cooling, mat.cycle_min_s, mat.cycle_max_s))

    if out.heat_flow == "двумерный":
        out.notes.append(
            "Толщина %.1f мм меньше граничной %.1f мм — отвод тепла "
            "двумерный, деталь прогревается насквозь"
            % (thickness, transition))

    out.notes.append(
        "Формулы EN 1011-2 выведены для дуговой сварки; на лазерных "
        "режимах они дают заниженное время охлаждения")
    return out


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
