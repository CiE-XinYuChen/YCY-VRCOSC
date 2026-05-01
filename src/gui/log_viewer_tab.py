"""log_viewer_tab.py - Log display and debug info panel."""
from __future__ import annotations

import logging
import time

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QFormLayout, QGroupBox, QHBoxLayout, QLabel, QTextEdit, QWidget,
)

from i18n import translate as _

logger = logging.getLogger(__name__)

MOTOR_NAMES = ("A", "B", "C")


class _LogEmitter(QObject):
    log_signal = Signal(str)


class QTextEditHandler(logging.Handler):
    """Thread-safe logging handler that writes to a QTextEdit via Qt signals."""

    def __init__(self, text_edit):
        super().__init__()
        self.text_edit = text_edit
        self._emitter  = _LogEmitter()
        self._emitter.log_signal.connect(self._append)

    def _append(self, msg: str):
        self.text_edit.append(msg)
        self.text_edit.ensureCursorVisible()

    def emit(self, record):
        msg = self.format(record)
        if record.levelno >= logging.ERROR:
            msg = f"<b style='color:red;'>{msg}</b>"
        elif record.levelno == logging.WARNING:
            msg = f"<b style='color:orange;'>{msg}</b>"
        else:
            msg = f"<span>{msg}</span>"
        self._emitter.log_signal.emit(msg)


class _SimpleFormatter(logging.Formatter):
    _MAP = {"DEBUG": "D", "INFO": "I", "WARNING": "W", "ERROR": "E", "CRITICAL": "C"}

    def format(self, record):
        lvl = self._MAP.get(record.levelname, record.levelname)
        record.asctime = self.formatTime(record, self.datefmt)
        return f"{record.asctime}-{lvl}: {record.getMessage()}"


class LogViewerTab(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window

        layout = QFormLayout(self)
        self.setLayout(layout)

        # ── Log box ───────────────────────────────────────────────────────────
        self.log_groupbox = QGroupBox(str(_("log_tab.simple_log")))
        self.log_groupbox.setCheckable(True)
        self.log_groupbox.setChecked(True)
        self.log_groupbox.toggled.connect(
            lambda on: self.log_text_edit.setVisible(on)
        )

        self.log_text_edit = QTextEdit()
        self.log_text_edit.setReadOnly(True)

        from PySide6.QtWidgets import QVBoxLayout
        log_layout = QVBoxLayout()
        log_layout.addWidget(self.log_text_edit)
        self.log_groupbox.setLayout(log_layout)
        layout.addWidget(self.log_groupbox)

        # Set up logging handler (used by app.py)
        self.log_handler = QTextEditHandler(self.log_text_edit)
        self.log_handler.setLevel(logging.DEBUG)
        self.log_handler.setFormatter(
            _SimpleFormatter("%(asctime)s-%(levelname)s: %(message)s", datefmt="%H:%M:%S")
        )

        # ── Debug panel ───────────────────────────────────────────────────────
        self.debug_group = QGroupBox(str(_("log_tab.debug_info")))
        self.debug_group.setCheckable(True)
        self.debug_group.setChecked(False)
        self.debug_group.toggled.connect(self._toggle_debug)

        debug_h = QHBoxLayout()
        debug_h.addWidget(QLabel(str(_("log_tab.controller_params")) + ":"))
        self.param_label = QLabel(str(_("log_tab.controller_not_initialized")))
        self.param_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        debug_h.addWidget(self.param_label)
        self.debug_group.setLayout(debug_h)
        layout.addRow(self.debug_group)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_debug)
        self._timer.start(1000)

    def _toggle_debug(self, checked: bool):
        for child in self.debug_group.findChildren(QWidget):
            child.setVisible(checked)

    def _update_debug(self):
        ctrl = self.main_window.controller
        if ctrl is None:
            self.param_label.setText(str(_("log_tab.controller_not_initialized")))
            return

        lines = [
            f"Devices: {len(ctrl.devices)}",
        ]
        for addr, info in ctrl.devices.items():
            state = ctrl._device_states.get(addr, {})
            lines.append(f"  {info.get('name', addr[-8:])} [{info.get('type','?')}]  {state}")
        lines += [
            f"Panel: {ctrl._current_panel + 1}",
            f"ChatBox: {ctrl.chatbox_enabled}  interval={ctrl.chatbox_interval}s",
            f"Hold tasks: {len(ctrl._hold_tasks)}",
        ]
        self.param_label.setText("\n".join(lines))

    def limit_log_lines(self, max_lines: int = 500):
        doc   = self.log_text_edit.document()
        count = doc.blockCount()
        if count <= max_lines:
            return
        cursor = self.log_text_edit.textCursor()
        cursor.movePosition(QTextCursor.Start)
        for _ in range(count - max_lines):
            cursor.select(QTextCursor.BlockUnderCursor)
            cursor.removeSelectedText()
            cursor.deleteChar()
        cursor.movePosition(QTextCursor.End)
        self.log_text_edit.setTextCursor(cursor)
        self.log_text_edit.ensureCursorVisible()

    def update_ui_texts(self):
        self.log_groupbox.setTitle(str(_("log_tab.simple_log")))
        self.debug_group.setTitle(str(_("log_tab.debug_info")))
