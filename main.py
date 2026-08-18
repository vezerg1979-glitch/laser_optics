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

from app.ui import MainUI


class LaserOpticsApp(App):
    title = "Расчёт фокусировки"

    def build(self):
        Window.clearcolor = (0.07, 0.08, 0.10, 1)
        storage = self.user_data_dir
        if platform not in ("android", "ios"):
            storage = os.path.join(os.path.expanduser("~"), ".laser_optics")
        return MainUI(storage_dir=storage)

    def on_pause(self):
        return True


if __name__ == "__main__":
    LaserOpticsApp().run()
