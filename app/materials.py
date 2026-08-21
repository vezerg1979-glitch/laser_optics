# -*- coding: utf-8 -*-
"""
Теплофизические свойства материалов для оценки формы шва.

Значения — справочные, усреднённые по интервалу от комнатной температуры
до температуры плавления. Точность такого усреднения ограничена: теплоёмкость
и теплопроводность сталей меняются в разы при нагреве, а у алюминия при
плавлении скачком падает отражательная способность. Для оценочного расчёта
этого достаточно, для аттестации режима — нет.

Поглощательная способность задана двумя значениями. В режиме теплопроводности
работает френелевское поглощение на длине волны около 1 мкм. В кинжальном
режиме излучение многократно переотражается внутри парогазового канала, и
эффективное поглощение приближается к единице — поэтому для меди разница
между режимами более чем десятикратная.

Эффективность плавления — доля поглощённой энергии, ушедшая именно на
плавление, а не отведённая теплопроводностью в металл. Теоретический предел
для движущегося линейного источника составляет около 0,48, у алюминия и меди
из-за высокой теплопроводности реальные значения вдвое-втрое ниже. Строго
говоря, это уже не чистая эффективность плавления, а собирательный
подгоночный коэффициент: в нём растворены и потери на испарение, и неточность
усреднённых теплофизических свойств, поэтому сравнивать его значения между
материалами напрямую не следует.

Этот коэффициент задан не из общих соображений, а подобран так, чтобы модель
воспроизводила опорный режим, указанный в поле reference. Опорные режимы —
типичные для волоконного лазера киловаттного класса. Если под рукой есть свои
макрошлифы, коэффициент стоит пересчитать по ним: подобрать так, чтобы расчёт
совпал с замеренной глубиной, и дальше модель будет давать осмысленные
значения в окрестности этого режима.

Предельное отношение глубины к ширине ограничивает расчёт снизу по ширине.
Парогазовый канал не сужается вслед за пятном: при жёсткой фокусировке его
поперечник выходит на насыщение, и без этого ограничения энергетический
баланс даёт нереальные отношения вроде 30:1. У алюминия и особенно у меди
канал заметно менее устойчив, поэтому предел ниже.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Material:
    key: str
    name: str
    density_g_cm3: float          # плотность
    heat_capacity_j_gk: float     # средняя теплоёмкость до плавления
    melting_c: float              # температура плавления (солидус-ликвидус)
    latent_heat_j_g: float        # удельная теплота плавления
    diffusivity_mm2_s: float      # температуропроводность при высокой T
    absorptivity_keyhole: float   # поглощение в кинжальном режиме
    absorptivity_conduction: float
    melting_efficiency: float     # доля энергии, идущая на плавление
    keyhole_threshold: float      # порог кинжального режима, Вт/см²
    max_aspect: float             # предельное отношение глубины к ширине
    # Температурный интервал, по которому принято оценивать скорость
    # охлаждения. Для сталей это классический t8/5: в интервале 800–500 °C
    # идёт распад аустенита, и от его длительности зависит структура шва.
    # У алюминия превращений нет, но в интервале 400–300 °C происходит
    # разупрочнение термоупрочняемых сплавов, поэтому смотрят его.
    cycle_upper_c: float = 800.0
    cycle_lower_c: float = 500.0
    cycle_name: str = "t8/5"
    # Температура границы зоны термического влияния: ниже неё структура
    # основного металла считается неизменной.
    haz_temp_c: float = 723.0
    haz_basis: str = "Ac1"
    # Рекомендуемый диапазон времени охлаждения, с. Задан только там, где
    # он осмыслен: для углеродистых и низколегированных сталей слишком
    # быстрое охлаждение даёт мартенсит и трещины.
    cycle_min_s: float = 0.0
    cycle_max_s: float = 0.0
    reference: str = ""           # опорный режим, по которому калибровано
    note: str = ""

    @property
    def volumetric_heat_j_mm3k(self) -> float:
        """Объёмная теплоёмкость ρ·c, Дж/(мм³·К)."""
        return self.density_g_cm3 * 1e-3 * self.heat_capacity_j_gk

    @property
    def conductivity_w_mmk(self) -> float:
        """
        Теплопроводность λ = a·ρ·c, Вт/(мм·К).

        Выводится из температуропроводности, а не задаётся отдельно, чтобы
        свойства не разошлись между собой при правке таблицы.
        """
        return self.diffusivity_mm2_s * self.volumetric_heat_j_mm3k

    @property
    def short_name(self) -> str:
        """Марка без пояснения — для узких столбцов таблицы."""
        if "(" in self.name:
            return self.name.split("(", 1)[1].rstrip(")").split(",")[0]
        return self.name

    @property
    def melting_enthalpy_j_mm3(self) -> float:
        """
        Объёмная энтальпия плавления, Дж/мм³.

        Энергия, необходимая для нагрева единицы объёма от 20 °C до
        температуры плавления и последующего расплавления.
        """
        rho_g_mm3 = self.density_g_cm3 * 1e-3
        heating = self.heat_capacity_j_gk * (self.melting_c - 20.0)
        return rho_g_mm3 * (heating + self.latent_heat_j_g)


MATERIALS = [
    Material(
        key="steel_low_carbon",
        name="Сталь низкоуглеродистая (Ст3, S235)",
        density_g_cm3=7.85, heat_capacity_j_gk=0.68, melting_c=1520.0,
        latent_heat_j_g=270.0, diffusivity_mm2_s=5.0,
        absorptivity_keyhole=0.80, absorptivity_conduction=0.35,
        melting_efficiency=0.45, keyhole_threshold=1.0e6, max_aspect=10.0,
        haz_temp_c=723.0, haz_basis="Ac1",
        cycle_min_s=5.0, cycle_max_s=25.0,
        reference="10 кВт, 1,2 м/мин — около 16 мм",
    ),
    Material(
        key="steel_low_alloy",
        name="Сталь низколегированная (09Г2С)",
        density_g_cm3=7.85, heat_capacity_j_gk=0.68, melting_c=1500.0,
        latent_heat_j_g=270.0, diffusivity_mm2_s=4.8,
        absorptivity_keyhole=0.80, absorptivity_conduction=0.35,
        melting_efficiency=0.45, keyhole_threshold=1.0e6, max_aspect=10.0,
        haz_temp_c=723.0, haz_basis="Ac1",
        cycle_min_s=6.0, cycle_max_s=25.0,
        reference="10 кВт, 1,2 м/мин — около 16 мм",
    ),
    Material(
        key="steel_austenitic",
        name="Сталь аустенитная (12Х18Н10Т, 304)",
        density_g_cm3=7.90, heat_capacity_j_gk=0.60, melting_c=1450.0,
        latent_heat_j_g=270.0, diffusivity_mm2_s=4.0,
        absorptivity_keyhole=0.80, absorptivity_conduction=0.35,
        melting_efficiency=0.46, keyhole_threshold=1.0e6, max_aspect=11.0,
        cycle_upper_c=800.0, cycle_lower_c=500.0, cycle_name="t8/5",
        haz_temp_c=600.0, haz_basis="межкристаллитная коррозия",
        reference="10 кВт, 1,2 м/мин — около 18 мм",
        note="Низкая теплопроводность — проплавление глубже, чем у "
             "углеродистой стали при том же режиме",
    ),
    Material(
        key="aluminium",
        name="Алюминиевый сплав (АМг6, 5083)",
        density_g_cm3=2.66, heat_capacity_j_gk=1.18, melting_c=640.0,
        latent_heat_j_g=397.0, diffusivity_mm2_s=50.0,
        absorptivity_keyhole=0.60, absorptivity_conduction=0.12,
        melting_efficiency=0.195, keyhole_threshold=1.5e6, max_aspect=6.0,
        cycle_upper_c=400.0, cycle_lower_c=300.0, cycle_name="t4/3",
        haz_temp_c=250.0, haz_basis="разупрочнение",
        reference="10 кВт, 1,2 м/мин — около 12 мм",
        note="Высокая температуропроводность и отражательная способность; "
             "склонность к порам и горячим трещинам",
    ),
    Material(
        key="titanium",
        name="Титановый сплав (ВТ1-0, Grade 2)",
        density_g_cm3=4.51, heat_capacity_j_gk=0.70, melting_c=1670.0,
        latent_heat_j_g=390.0, diffusivity_mm2_s=6.5,
        absorptivity_keyhole=0.80, absorptivity_conduction=0.45,
        melting_efficiency=0.48, keyhole_threshold=0.8e6, max_aspect=10.0,
        cycle_upper_c=1000.0, cycle_lower_c=700.0, cycle_name="t10/7",
        haz_temp_c=882.0, haz_basis="β-переход",
        reference="10 кВт, 1,2 м/мин — около 20 мм",
        note="Обязательна защита сварочной ванны и корня шва инертным газом",
    ),
    Material(
        key="nickel_alloy",
        name="Никелевый сплав (Инконель 625)",
        density_g_cm3=8.44, heat_capacity_j_gk=0.60, melting_c=1350.0,
        latent_heat_j_g=270.0, diffusivity_mm2_s=3.4,
        absorptivity_keyhole=0.78, absorptivity_conduction=0.32,
        melting_efficiency=0.42, keyhole_threshold=1.0e6, max_aspect=11.0,
        cycle_upper_c=900.0, cycle_lower_c=600.0, cycle_name="t9/6",
        haz_temp_c=650.0, haz_basis="выделение карбидов",
        reference="10 кВт, 1,2 м/мин — около 17 мм",
    ),
    Material(
        key="copper",
        name="Медь (М1, Cu-ETP)",
        density_g_cm3=8.96, heat_capacity_j_gk=0.42, melting_c=1085.0,
        latent_heat_j_g=205.0, diffusivity_mm2_s=110.0,
        absorptivity_keyhole=0.55, absorptivity_conduction=0.05,
        melting_efficiency=0.24, keyhole_threshold=3.0e6, max_aspect=3.0,
        cycle_upper_c=600.0, cycle_lower_c=300.0, cycle_name="t6/3",
        haz_temp_c=250.0, haz_basis="рекристаллизация",
        reference="10 кВт, 1,2 м/мин — около 5 мм",
        note="На длине волны 1 мкм холодная медь отражает почти всё "
             "излучение; устойчивый процесс начинается только после "
             "образования канала",
    ),
]

# Коэффициенты формы соединения по EN 1011-2: отвод тепла зависит от того,
# сколько направлений для него открыто. Первое число — для тонкой пластины
# (двумерный отвод), второе — для толстой (трёхмерный).
JOINT_FACTORS = {
    "Наплавка валика на пластину": (1.00, 1.00),
    "Стыковой шов": (0.90, 0.90),
    "Тавровый шов": (0.45, 0.67),
    "Нахлёсточный шов": (0.70, 0.80),
}
JOINT_NAMES = list(JOINT_FACTORS)
DEFAULT_JOINT = "Стыковой шов"


BY_KEY = {m.key: m for m in MATERIALS}
NAMES = [m.name for m in MATERIALS]
BY_NAME = {m.name: m for m in MATERIALS}
DEFAULT_KEY = "steel_low_alloy"


def get(key: str) -> Material:
    return BY_KEY.get(key, BY_KEY[DEFAULT_KEY])


def by_name(name: str) -> Material:
    return BY_NAME.get(name, BY_KEY[DEFAULT_KEY])
