# src/gui/about_tab.py
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTextEdit
from PySide6.QtCore import QLocale
from i18n import translate as _, language_signals
import version

class AboutTab(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window

        layout = QVBoxLayout()

        self.version_label = QLabel(str(_('about_tab.current_version')) + ": " + version.VERSION)
        layout.addWidget(self.version_label)

        self.update_disabled_label = QLabel(str(_('about_tab.online_update_disabled')))
        layout.addWidget(self.update_disabled_label)

        info = QTextEdit()
        info.setLocale(QLocale(QLocale.Language.English, QLocale.Country.UnitedStates))
        info.setReadOnly(True)
        info.setText(
            "开发者: 可乐Shayne\n\n"
            "本项目基于 DG-LAB-VRCOSC 改造，加入多设备 WebSocket 控制支持。\n\n"
            "源仓库:\n"
            "  https://github.com/ccvrc/DG-LAB-VRCOSC\n\n"
            "WebSocket 桥接由 YokoNex-OpenCLI 提供:\n"
            "  https://github.com/CiE-XinYuChen/YokoNex-OpenCLI\n\n"
            "本项目为开发者个人项目，开源并遵循 MIT 协议。\n\n"
            "---\n\n"
            "使用的开源项目:\n"
            "- PySide6 (LGPL)\n"
            "- websockets (BSD)\n"
            "- qasync (MIT)\n"
            "- python-osc (MIT)\n"
            "- pyyaml (MIT)\n"
            "- colorlog (MIT)\n"
            "- psutil (BSD)\n"
            "- aiohttp (Apache 2.0)"
        )

        layout.addWidget(info)
        self.setLayout(layout)

    def update_ui_texts(self):
        self.version_label.setText(str(_('about_tab.current_version')) + ": " + version.VERSION)
        self.update_disabled_label.setText(str(_('about_tab.online_update_disabled')))
