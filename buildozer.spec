[app]

# Название, которое увидит пользователь на устройстве
title = Расчёт фокусировки

package.name = laseroptics
package.domain = ru.vpglaser

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json
source.include_patterns = app/*.py
source.exclude_dirs = tests,.github,bin,.buildozer
source.exclude_patterns = tests/*,*.spec.bak

version = 1.0.0

# Зависимости: только Kivy, тяжёлых научных библиотек нет —
# весь расчёт выполняется на чистом Python.
# Версия Kivy НЕ фиксируется: python-for-android собирает её по своему
# рецепту, а явное "kivy==X.Y.Z" ломает сверку контрольной суммы,
# если версия в рецепте отличается.
requirements = python3,kivy

# Список допустимых ориентаций (buildozer 1.5 не принимает "all"):
# portrait, landscape, portrait-reverse, landscape-reverse
orientation = portrait, landscape
fullscreen = 0

# --- Android ----------------------------------------------------------------

android.api = 34
android.minapi = 24
android.ndk_api = 24
android.archs = arm64-v8a, armeabi-v7a

# Приложение работает офлайн и не запрашивает разрешений.
# Если понадобится выгрузка отчёта во внешнюю память — раскомментируйте:
# android.permissions = WRITE_EXTERNAL_STORAGE

android.accept_sdk_license = True

# КРИТИЧНО. Версию build-tools buildozer настраивать не умеет: он всегда
# ставит максимальную доступную (сейчас 37.0.0) и сразу проверяет утилиту
# aidl, которой в свежих build-tools уже нет — сборка падает.
# Поэтому SDK готовится заранее (см. шаг workflow «Подготовка Android SDK»),
# а обновление отключается, чтобы buildozer не подтянул 37.0.0.
# При локальной сборке с нуля закомментируйте строку ниже на первый запуск.
android.skip_update = True
android.release_artifact = aab
android.debug_artifact = apk

[buildozer]

log_level = 2
warn_on_root = 0
