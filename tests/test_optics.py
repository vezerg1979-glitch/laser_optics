# -*- coding: utf-8 -*-
"""
Сверка расчётного ядра с исходной книгой «Расчет оптики»,
лист «Сравнение оптических схем», столбцы B (схема 1) и E (схема 4).
"""

import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.optics import Scheme, Workpiece, calculate, caustic_points  # noqa: E402
from app.geometry import plate_polygons, nozzle_polygon, wire_circles  # noqa: E402
from app import materials  # noqa: E402

TOL = 1e-6


def approx(a, b, rel=1e-6):
    assert a == b or abs(a - b) <= rel * max(abs(a), abs(b)), (a, b)


SCHEME_1 = Scheme(
    name="Схема 1", wavelength_um=1.069, fiber_diameter_um=200.0,
    bpp_mm_mrad=7.07, collimator_mm=160.0, focusator_mm=300.0,
    focus_position_mm=-11.0, tilt_angle_deg=10.0,
    speed=1.2, speed_unit="м/мин", power=10.0, power_unit="кВт",
)

SCHEME_4 = Scheme(
    name="Схема 4", wavelength_um=1.07, fiber_diameter_um=100.0,
    bpp_mm_mrad=3.8, collimator_mm=100.0, focusator_mm=500.0,
    focus_position_mm=25.0, tilt_angle_deg=-15.0,
    speed=1.0, speed_unit="м/мин", power=0.0, power_unit="кВт",
)

WP = Workpiece(thickness_mm=18.0, target_spot_mm=5.0)


def test_scheme_1_matches_workbook():
    r = calculate(SCHEME_1, WP)
    approx(r.spot_focus_mm, 0.375)                     # B25
    approx(r.waist_length_mm, 9.945190947666195)       # B28
    approx(r.spot_surface_mm, 0.9103695250708791)      # B26
    approx(r.spot_root_mm, 0.6475309810177254)         # B27
    approx(r.magnification, 1.875)                     # B29
    approx(r.m2, 20.777418204751953)                   # B30
    approx(r.beam_on_lens_mm, 22.624000000000002)      # B31
    approx(r.focus_shift_per_mm, 3.515625)             # B32
    approx(r.required_defocus_mm, 66.11453768734242)   # B24
    approx(r.linear_energy_j_mm, 500.0)                # B38


def test_scheme_4_matches_workbook():
    r = calculate(SCHEME_4, WP)
    approx(r.spot_focus_mm, 0.5)                       # E25
    approx(r.waist_length_mm, 32.89473684210527)       # E28
    approx(r.spot_surface_mm, 0.9097252332435326)      # E26
    approx(r.spot_root_mm, 1.3995613026945264)         # E27
    approx(r.magnification, 5.0)                       # E29
    approx(r.m2, 11.157058022094592)                   # E30
    approx(r.beam_on_lens_mm, 15.2)                    # E31
    approx(r.focus_shift_per_mm, 25.0)                 # E32
    approx(r.required_defocus_mm, 163.64924952411513)  # E24


def test_power_density_close_to_workbook():
    """В книге использовано 3.14 вместо pi — расхождение около 0.05 %."""
    r = calculate(SCHEME_1, WP)
    approx(r.power_density_surface, 1537074.5116040858, rel=1e-3)
    approx(r.power_density_lens, 2488.808945142196, rel=1e-3)


def test_spot_grows_symmetrically_around_waist():
    r = calculate(SCHEME_1, WP)
    z = r.rayleigh_mm
    from app.optics import spot_diameter_at
    d_plus = spot_diameter_at(r.spot_focus_mm, z, z)
    d_minus = spot_diameter_at(r.spot_focus_mm, z, -z)
    approx(d_plus, d_minus)
    approx(d_plus, r.spot_focus_mm * math.sqrt(2.0))


def test_required_defocus_reproduces_target_spot():
    r = calculate(SCHEME_1, WP)
    from app.optics import spot_diameter_at
    d = spot_diameter_at(r.spot_focus_mm, r.rayleigh_mm, r.required_defocus_mm)
    approx(d, WP.target_spot_mm, rel=1e-9)


def test_target_spot_smaller_than_focus_warns():
    wp = Workpiece(thickness_mm=18.0, target_spot_mm=0.1)
    r = calculate(SCHEME_1, wp)
    assert r.required_defocus_mm is None
    assert any("недостижимо" in w for w in r.warnings)


def test_invalid_scheme_returns_empty_result():
    r = calculate(Scheme(collimator_mm=0.0), Workpiece())
    assert r.spot_focus_mm == 0.0
    assert r.warnings


def test_caustic_is_tilted_by_angle():
    left, right = caustic_points(SCHEME_1, WP, n=51)
    assert len(left) == len(right) == 51
    # ось пучка наклонена: середина верхней точки смещена влево при +10°
    mid_top_x = 0.5 * (left[0][0] + right[0][0])
    assert mid_top_x < 0
    # ширина пучка минимальна вблизи перетяжки
    widths = [math.hypot(r[0] - l[0], r[1] - l[1]) for l, r in zip(left, right)]
    assert min(widths) < 0.5 * max(widths)


def test_plate_geometry_respects_gap_and_bevel():
    wp = Workpiece(thickness_mm=10.0, gap_mm=2.0, bevel_left_deg=5.0,
                   bevel_right_deg=-10.0, joint_offset_mm=0.0,
                   width_left_mm=5.0, width_right_mm=5.0)
    left, right = plate_polygons(wp)
    # верхние внутренние точки разнесены минимум на зазор
    top_left_inner = max(p[0] for p in left if p[1] == 0.0)
    top_right_inner = min(p[0] for p in right if p[1] == 0.0)
    assert top_right_inner - top_left_inner >= wp.gap_mm - TOL
    # положительный угол слева -> сверху шире, чем снизу
    bot_left_inner = max(p[0] for p in left if p[1] < 0)
    assert top_left_inner < bot_left_inner


def test_nozzle_and_wire_geometry():
    wp = Workpiece(draw_nozzle=True, wire_count=2, wire_diameter_mm=1.6)
    (nozzle,) = nozzle_polygon(wp)
    assert min(p[1] for p in nozzle) == wp.nozzle_gap_mm
    assert max(p[1] for p in nozzle) == wp.nozzle_gap_mm + wp.nozzle_height_mm
    circles = wire_circles(wp)
    assert len(circles) == 2
    for c in circles:
        assert min(p[1] for p in c) > -1e-9   # проволока лежит на поверхности


# --- модель формы шва -------------------------------------------------------


def _weld(material_key, power_kw, speed_m_min, thickness=20.0, dz=0.0):
    s = Scheme(wavelength_um=1.07, fiber_diameter_um=200, bpp_mm_mrad=7.07,
               collimator_mm=160, focusator_mm=300, focus_position_mm=dz,
               power=power_kw, power_unit="кВт",
               speed=speed_m_min, speed_unit="м/мин")
    wp = Workpiece(thickness_mm=thickness, material_key=material_key)
    return calculate(s, wp).weld


def test_melting_enthalpy_matches_handbook():
    """Объёмная энтальпия плавления: сталь ~10, алюминий ~3 Дж/мм³."""
    approx(materials.get("steel_low_carbon").melting_enthalpy_j_mm3,
           10.1, rel=0.05)
    approx(materials.get("aluminium").melting_enthalpy_j_mm3, 3.0, rel=0.05)
    approx(materials.get("titanium").melting_enthalpy_j_mm3, 7.0, rel=0.05)


def test_reference_regimes_reproduced():
    """Каждый материал воспроизводит свой опорный режим 10 кВт, 1,2 м/мин."""
    expected = {
        "steel_low_carbon": 16.0, "steel_low_alloy": 16.0,
        "steel_austenitic": 18.0, "aluminium": 12.0,
        "titanium": 20.0, "nickel_alloy": 17.0, "copper": 5.0,
    }
    for key, depth in expected.items():
        got = _weld(key, 10.0, 1.2).depth_mm
        assert abs(got - depth) <= 0.5 * max(1.0, depth * 0.05), (key, got)


def test_depth_grows_with_power_and_falls_with_speed():
    base = _weld("steel_low_alloy", 10.0, 1.2).depth_mm
    assert _weld("steel_low_alloy", 15.0, 1.2).depth_mm > base
    assert _weld("steel_low_alloy", 6.0, 1.2).depth_mm < base
    assert _weld("steel_low_alloy", 10.0, 3.0).depth_mm < base


def test_aspect_never_exceeds_material_limit():
    """Отношение глубины к ширине ограничено — иначе жёсткая фокусировка
    даёт нефизичные 30:1."""
    for m in materials.MATERIALS:
        for v in (0.5, 1.2, 4.0):
            w = _weld(m.key, 12.0, v)
            assert w.aspect <= m.max_aspect + 1e-6, (m.key, v, w.aspect)


def test_conduction_mode_is_wide_and_shallow():
    """Сильная расфокусировка уводит процесс из кинжального режима."""
    tight = _weld("steel_low_alloy", 10.0, 1.2, dz=0.0)
    wide = _weld("steel_low_alloy", 10.0, 1.2, dz=-60.0)
    assert tight.mode == "кинжальный"
    assert wide.mode == "теплопроводность"
    assert wide.width_mm > tight.width_mm
    assert wide.depth_mm < tight.depth_mm
    assert wide.aspect <= 1.0 + 1e-6


def test_full_penetration_speed_is_consistent():
    """Пересчитанная скорость сквозного проплавления действительно его даёт."""
    w = _weld("steel_low_alloy", 10.0, 1.2, thickness=10.0)
    again = _weld("steel_low_alloy", 10.0, w.speed_full_m_min, thickness=10.0)
    assert again.full_penetration
    approx(again.depth_mm, 10.0, rel=0.02)


def test_copper_needs_far_more_power_than_steel():
    """Медь отражает и отводит тепло — проплавление многократно меньше."""
    steel = _weld("steel_low_carbon", 10.0, 1.2).depth_mm
    copper = _weld("copper", 10.0, 1.2).depth_mm
    assert copper < 0.4 * steel


def test_weld_absent_without_power():
    s = Scheme(collimator_mm=160, focusator_mm=300, power=0.0)
    w = calculate(s, Workpiece()).weld
    assert w.depth_mm == 0.0
    assert w.notes


# --- термический цикл -------------------------------------------------------


def _thermal(material_key="steel_low_alloy", power_kw=10.0, speed=1.2,
             thickness=20.0, preheat=20.0, joint="Стыковой шов"):
    s = Scheme(wavelength_um=1.07, fiber_diameter_um=200, bpp_mm_mrad=7.07,
               collimator_mm=160, focusator_mm=300,
               power=power_kw, power_unit="кВт",
               speed=speed, speed_unit="м/мин")
    wp = Workpiece(thickness_mm=thickness, material_key=material_key,
                   preheat_c=preheat, joint_type=joint)
    return calculate(s, wp).thermal


def test_conductivity_matches_handbook():
    """λ = a·ρ·c: сталь около 27, медь около 400 Вт/(м·К)."""
    approx(materials.get("steel_low_carbon").conductivity_w_mmk * 1000,
           27.0, rel=0.1)
    approx(materials.get("copper").conductivity_w_mmk * 1000, 400.0, rel=0.1)


def test_cooling_time_in_expected_range_for_laser():
    """Лазерная сварка толстой стали даёт t8/5 порядка единиц секунд."""
    t = _thermal().cooling_time_s
    assert 0.5 < t < 5.0, t


def test_cooling_rate_consistent_with_time():
    r = _thermal()
    approx(r.cooling_rate_k_s, 300.0 / r.cooling_time_s, rel=1e-9)


def test_preheat_slows_cooling():
    assert (_thermal(preheat=200.0).cooling_time_s
            > _thermal(preheat=20.0).cooling_time_s)


def test_speed_accelerates_cooling():
    assert _thermal(speed=3.0).cooling_time_s < _thermal(speed=1.2).cooling_time_s


def test_heat_flow_switches_at_transition_thickness():
    """Толстая деталь — трёхмерный отвод, тонкая — двумерный."""
    thick = _thermal(thickness=30.0)
    assert thick.heat_flow == "трёхмерный"
    thin = _thermal(thickness=0.5 * thick.transition_thickness_mm)
    assert thin.heat_flow == "двумерный"
    # При двумерном отводе тонкая деталь остывает медленнее
    assert thin.cooling_time_s > thick.cooling_time_s


def test_thin_plate_cooling_scales_with_thickness_squared():
    """При двумерном отводе время охлаждения обратно квадрату толщины."""
    base = _thermal(thickness=4.0)
    half = _thermal(thickness=2.0)
    assert base.heat_flow == half.heat_flow == "двумерный"
    approx(half.cooling_time_s, base.cooling_time_s * 4.0, rel=1e-6)


def test_joint_type_changes_cooling():
    """У таврового шва больше путей отвода — охлаждение быстрее."""
    butt = _thermal(joint="Стыковой шов").cooling_time_s
    fillet = _thermal(joint="Тавровый шов").cooling_time_s
    assert fillet < butt


def test_haz_narrows_with_speed():
    assert _thermal(speed=3.0).haz_width_mm < _thermal(speed=1.2).haz_width_mm


def test_fast_cooling_warns_about_hardening():
    notes = " ".join(_thermal(speed=6.0).notes)
    assert "закалочные" in notes


def test_preheat_above_interval_is_reported():
    """Подогрев выше нижней границы интервала делает t8/5 бессмысленным."""
    r = _thermal(preheat=520.0)
    assert r.cooling_time_s == 0.0
    assert any("не определено" in n for n in r.notes)


def test_aluminium_uses_its_own_interval():
    r = _thermal(material_key="aluminium")
    assert r.cycle_name == "t4/3"
    assert "400" in r.cycle_range


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("OK   %s" % name)
            except AssertionError as exc:
                failures += 1
                print("FAIL %s: %s" % (name, exc))
    print("\n%s" % ("Все тесты пройдены" if not failures
                    else "Провалено тестов: %d" % failures))
    sys.exit(1 if failures else 0)
