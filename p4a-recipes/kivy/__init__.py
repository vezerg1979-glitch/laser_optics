# -*- coding: utf-8 -*-
"""
Локальное переопределение рецепта Kivy для python-for-android.

Штатный рецепт объявляет python_depends = certifi, chardet, idna, requests,
urllib3, filetype. Эти модули нужны только классу kivy.network.urlrequest,
который в нашем приложении не используется: расчёт полностью офлайновый,
сетевых обращений нет.

Зачем убирать. p4a устанавливает эти модули кросс-сборкой через pip, причём
в окружении задан _PYTHON_HOST_PLATFORM, из-за чего собранные колёса
получают платформенный тег вида cp314-cp314-android_24_arm64_v8a. Питон
внутри venv такой тег не принимает и падает с «is not a supported wheel on
this platform» — на этом обрывается вся сборка. Исключение цепочки requests
снимает проблему и заодно заметно ускоряет сборку.

Рецепт наследуется от штатного, поэтому версия Kivy, патчи и вся логика
сборки остаются теми, что заданы в используемой версии p4a, — здесь
переопределён единственный атрибут.
"""

from pythonforandroid.recipes.kivy import KivyRecipe as UpstreamKivyRecipe


class KivyRecipe(UpstreamKivyRecipe):
    # filetype оставлен: это чистый Python, используется при определении
    # типа изображений и собирается без нативного расширения.
    python_depends = ["filetype"]


recipe = KivyRecipe()
