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
# весь расчёт выполняется на чистом Python
requirements = python3,kivy==2.3.1

orientation = all
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
android.release_artifact = aab
android.debug_artifact = apk

# Не сжимать APK-ресурсы, ускоряет старт
android.no_compile_pyo = 1

[buildozer]

log_level = 2
warn_on_root = 0
