# -*- coding: utf-8 -*-
"""
Точка входа приложения «Расчёт фокусировки лазерного излучения».

Запуск на ПК:      python main.py
Сборка под Android: buildozer -v android debug
"""

import os

from kivy.app import App
from kivy.core.window import Window
from kivy.utils import platform

from app import theme
from app.ui import MainUI


class LaserOpticsApp(App):
    title = "Расчёт фокусировки"

    def build(self):
        storage = self.user_data_dir
        if platform not in ("android", "ios"):
            storage = os.path.join(os.path.expanduser("~"), ".laser_optics")
        ui = MainUI(storage_dir=storage)
        # Цвет фона окна берётся из темы уже после загрузки сохранённого
        # состояния, иначе при светлой теме по краям остаётся тёмная рамка.
        Window.clearcolor = theme.c("bg")
        return ui

    def on_pause(self):
        return True


if __name__ == "__main__":
    LaserOpticsApp().run()
