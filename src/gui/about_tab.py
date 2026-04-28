# src/gui/about_tab.py
import asyncio
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit
from PySide6.QtCore import QLocale, QUrl
from PySide6.QtGui import QDesktopServices
from i18n import translate as _, language_signals
import version

class AboutTab(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        
        layout = QVBoxLayout()
        
        # 版本信息
        self.version_layout = QVBoxLayout()
        self.version_layout_label = QLabel(_('about_tab.current_version') + ": " + version.VERSION)
        self.version_layout.addWidget(self.version_layout_label)

        self.update_disabled_label = QLabel(_('about_tab.online_update_disabled'))
        self.version_layout.addWidget(self.update_disabled_label)
        
        # 按钮布局 - 使用水平布局让两个按钮并排
        self.buttons_layout = QHBoxLayout()

        # 问题反馈按钮
        self.feedback_btn = QPushButton(_('about_tab.feedback'))
        self.feedback_btn.clicked.connect(self.open_feedback)
        self.buttons_layout.addWidget(self.feedback_btn)
        
        # 将按钮布局添加到版本布局中
        self.version_layout.addLayout(self.buttons_layout)
        
        # 贡献信息
        contributors = QTextEdit()
        # 强制使用英文区域设置，避免数字显示为繁体中文
        contributors.setLocale(QLocale(QLocale.Language.English, QLocale.Country.UnitedStates))
        contributors.setReadOnly(True)
        contributors.setText(
            "开发组织: ccvrc\n\n"
            "贡献者: \n"
            "- icrazt\n"
            "- 光水\n"
            "- icelly_QAQ\n\n"
            "特别感谢:\n"
            "- ChrisFeline (ToNSaveManager)\n"
            "- VRChat OSC 社区\n"
            "- VRSuya SoundPad\n"
            "- WastingMisaka(鱼板)\n"
            "- Wanlin\n"
            "- 所有参与测试、使用本项目及贡献问题反馈的用户\n\n"
            "项目地址: https://github.com/ccvrc/DG-LAB-VRCOSC\n\n"
            "使用的开源项目:\n"
            "- PySide6 (LGPL)\n"
            "- websockets (BSD)\n"
            "- qasync (MIT)\n"
            "- pydglab-ws (BSD)\n"
            "- qrcode (LGPL)\n"
            "- python-osc (MIT)\n"
            "- colorlog (MIT)\n"
            "- pillow (HPND)\n"
            "- pyyaml (MIT)\n"
            "- psutil (BSD)\n"
            "- aiohttp (Apache 2.0)\n"
            "- requests (Apache 2.0)"
        )
        
        layout.addLayout(self.version_layout)
        layout.addWidget(contributors)
        self.setLayout(layout)

    def check_update(self):
        # 防止多次点击
        if not hasattr(self, 'check_update_btn') or not self.check_update_btn.isEnabled():
            return
        self.check_update_btn.setEnabled(False)
        async def do_check():
            try:
                await self.main_window.check_update_manual()
            finally:
                self.check_update_btn.setEnabled(True)
        asyncio.create_task(do_check())

    def open_feedback(self):
        url = QUrl("https://qiz80xlgzfj.feishu.cn/share/base/form/shrcn5tv1swXYDkg8HZ99BwOWfh")
        QDesktopServices.openUrl(url)

    def update_ui_texts(self):
        """更新UI上的所有文本为当前语言"""
        self.feedback_btn.setText(_('about_tab.feedback'))
        self.update_disabled_label.setText(_('about_tab.online_update_disabled'))
        self.version_layout_label.setText(_('about_tab.current_version') + ": " + version.VERSION)
