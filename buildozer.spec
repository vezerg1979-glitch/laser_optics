[app]

# Название, которое увидит пользователь на устройстве
title = Расчёт фокусировки

package.name = laseroptics
package.domain = ru.vpglaser

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json
source.include_patterns = app/*.py
source.exclude_dirs = tests,.github,bin,.buildozer,p4a-recipes,tools
source.exclude_patterns = tests/*,*.spec.bak

version = 1.1.0

# Иконка и заставка генерируются скриптом tools/make_icons.py в палитре
# приложения — при правке цветов достаточно перезапустить его.
icon.filename = %(source.dir)s/assets/icon.png
presplash.filename = %(source.dir)s/assets/presplash.png

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
# Только 64-битная архитектура. Причина не в совместимости, а в баге p4a:
# этап установки чистых Python-модулей (run_pymodules_install) выполняется
# по разу на каждую архитектуру, но использует один и тот же каталог venv.
# На второй архитектуре `hostpython -m venv venv` запускается поверх
# существующего каталога, и пропатченный в p4a ensurepip (он убирает
# site-packages из sys.path) не видит уже обновлённый pip 26.x и пишет
# поверх него свой pip 25.3. Получается смесь двух версий, и сборка падает
# с ImportError: cannot import name 'BuildDependencyInstallError'.
# С одной архитектурой этап выполняется единожды и проблема не возникает.
# Побочный плюс — сборка вдвое быстрее и APK вдвое меньше.
# 64-битный ARM поддерживают практически все устройства с 2015 года,
# и RuStore с Google Play в любом случае требуют 64-битные сборки.
android.archs = arm64-v8a

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

# Версия python-for-android фиксируется, иначе buildozer тянет master,
# и любое изменение в нём ломает сборку без изменений в проекте.
p4a.branch = v2026.05.09

# Локальный рецепт kivy без сетевой цепочки requests/urllib3/certifi —
# см. пояснение в p4a-recipes/kivy/__init__.py
p4a.local_recipes = ./p4a-recipes

[buildozer]

log_level = 2
warn_on_root = 0
