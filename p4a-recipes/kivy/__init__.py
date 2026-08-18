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

Рецепт наследуется от штатного, поэтому версия Kivy, URL исходников, патчи
и зависимости остаются теми, что заданы в используемой версии p4a.
"""

from os.path import join

from pythonforandroid.recipes.kivy import KivyRecipe as UpstreamKivyRecipe


class KivyRecipe(UpstreamKivyRecipe):
    # filetype оставлен: это чистый Python, используется при определении
    # типа изображений и собирается без нативного расширения.
    python_depends = ["filetype"]

    def get_recipe_dir(self):
        """
        Каталог рецепта для поиска патчей и вспомогательных файлов.

        По умолчанию p4a возвращает каталог локального рецепта, то есть эту
        папку, и тогда унаследованные патчи (sdl-gl-swapwindow-nogil.patch,
        use_cython.patch, no-ast-str.patch) не находятся — сборка падает с
        «Can't open patch file». Копировать их сюда нельзя: набор патчей
        меняется от версии к версии p4a и быстро разойдётся с рецептом.
        Поэтому возвращаем штатный каталог: патчи всегда берутся из той
        версии p4a, которая реально используется.
        """
        return join(self.ctx.root_dir, "recipes", self.name)


recipe = KivyRecipe()
