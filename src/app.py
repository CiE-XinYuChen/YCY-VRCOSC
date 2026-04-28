"""app.py - YokoNex Toy Controller for VRChat — main window."""
import asyncio
import logging
import os
import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget
from qasync import QEventLoop

import version
from config import load_settings, save_settings
from i18n import language_signals, set_language, translate as _
from logger_config import setup_logging
from gui.network_config_tab import NetworkConfigTab
from gui.controller_settings_tab import ControllerSettingsTab
from gui.log_viewer_tab import LogViewerTab
from gui.osc_parameters import OSCParametersTab
from gui.about_tab import AboutTab

software_version = version.VERSION
setup_logging()
logger = logging.getLogger(__name__)


def resource_path(relative_path: str) -> str:
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),
        relative_path,
    )


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.settings = load_settings()
        if "language" in self.settings:
            set_language(self.settings["language"])

        self.setWindowTitle(str(_("main.title")))
        self.setGeometry(300, 300, 860, 480)
        self.setWindowIcon(QIcon(resource_path("docs/images/fish-cake.ico")))

        self.controller = None
        self.app_status_online = False

        tabs = QTabWidget()
        self.setCentralWidget(tabs)

        self.network_config_tab      = NetworkConfigTab(self)
        self.controller_settings_tab = ControllerSettingsTab(self)
        self.osc_parameters_tab      = OSCParametersTab(self)
        self.log_viewer_tab          = LogViewerTab(self)
        self.about_tab               = AboutTab(self)

        tabs.addTab(self.network_config_tab,      str(_("main.tabs.network")))
        tabs.addTab(self.controller_settings_tab, str(_("main.tabs.controller")))
        tabs.addTab(self.osc_parameters_tab,      str(_("main.tabs.osc")))
        tabs.addTab(self.log_viewer_tab,          str(_("main.tabs.log")))
        tabs.addTab(self.about_tab,               str(_("about_tab.title")))

        self.tab_widget = tabs

        # Hook logging into the log viewer
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        root_logger.addHandler(self.log_viewer_tab.log_handler)
        self.log_viewer_tab.log_text_edit.textChanged.connect(
            lambda: self.log_viewer_tab.limit_log_lines(100)
        )

        language_signals.language_changed.connect(self._update_tab_titles)

    def get_osc_addresses(self) -> list:
        return self.osc_parameters_tab.get_addresses()

    def save_settings(self):
        save_settings(self.settings)

    def _update_tab_titles(self):
        self.setWindowTitle(str(_("main.title")))
        self.tab_widget.setTabText(0, str(_("main.tabs.network")))
        self.tab_widget.setTabText(1, str(_("main.tabs.controller")))
        self.tab_widget.setTabText(2, str(_("main.tabs.osc")))
        self.tab_widget.setTabText(3, str(_("main.tabs.log")))
        self.tab_widget.setTabText(4, str(_("about_tab.title")))
        for tab in (self.network_config_tab, self.controller_settings_tab,
                    self.osc_parameters_tab, self.log_viewer_tab, self.about_tab):
            if hasattr(tab, "update_ui_texts"):
                tab.update_ui_texts()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    window = MainWindow()
    window.show()

    with loop:
        loop.run_forever()
