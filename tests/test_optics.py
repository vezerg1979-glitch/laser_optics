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
