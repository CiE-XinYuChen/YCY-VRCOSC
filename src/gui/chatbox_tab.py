"""chatbox_tab.py — VRChat ChatBox custom message configuration."""
from __future__ import annotations

import asyncio
import logging

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox, QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout,
    QLabel, QPlainTextEdit, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from i18n import language_signals, translate as _

log = logging.getLogger(__name__)

_VARIABLE_HELP = """\
Available variables (use with {variable_name}):

  panel              — current panel number (1-3)

Per device (dev1, dev2, … sorted by address):
  devN_name          — device name
  devN_type          — toy / estim
  devN_battery       — battery % (or ?)

Toy device (type = toy):
  devN_speed_A/B/C   — motor speed (0-20)
  devN_mode_A/B/C    — motor mode (1-4)

Estim device (type = estim):
  devN_intensity_A/B — channel intensity (0-276)
  devN_mode_A/B      — channel mode (1-17)
  devN_enabled_A/B   — channel enabled (True/False)

Example templates:
  A:{dev1_speed_A} B:{dev1_speed_B}
  EMS-A:{dev2_intensity_A} bat:{dev1_battery}%
  [{panel}] {dev1_name} spd:{dev1_speed_A}
"""

_DEFAULT_TEMPLATE = "A:{dev1_speed_A} B:{dev1_speed_B} C:{dev1_speed_C}"


class ChatBoxTab(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._controller = None

        root = QVBoxLayout(self)

        # ── Enable + Interval ─────────────────────────────────────────────────
        self._ctrl_group = QGroupBox(str(_("chatbox_tab.control_group")))
        ctrl_form  = QFormLayout()

        self.enable_check = QCheckBox(str(_("chatbox_tab.enable_check")))
        self.enable_check.stateChanged.connect(self._on_enable_changed)
        ctrl_form.addRow(self.enable_check)

        self.interval_spin = QDoubleSpinBox()
        self.interval_spin.setRange(0.5, 60.0)
        self.interval_spin.setSingleStep(0.5)
        self.interval_spin.setValue(3.0)
        self.interval_spin.setSuffix(" s")
        self.interval_spin.valueChanged.connect(self._on_interval_changed)
        ctrl_form.addRow(str(_("chatbox_tab.interval_label")), self.interval_spin)

        self._ctrl_group.setLayout(ctrl_form)
        root.addWidget(self._ctrl_group)

        # ── Template editor ────────────────────────────────────────────────────
        self._tmpl_group = QGroupBox(str(_("chatbox_tab.template_group")))
        tmpl_layout = QVBoxLayout()

        self._tmpl_hint = QLabel(str(_("chatbox_tab.template_hint")))
        self._tmpl_hint.setWordWrap(True)
        tmpl_layout.addWidget(self._tmpl_hint)

        self.template_edit = QPlainTextEdit()
        self.template_edit.setPlainText(_DEFAULT_TEMPLATE)
        self.template_edit.setMaximumHeight(80)
        self.template_edit.textChanged.connect(self._on_template_changed)
        tmpl_layout.addWidget(self.template_edit)

        # Preview
        preview_row = QHBoxLayout()
        self._preview_title = QLabel(str(_("chatbox_tab.preview_label")))
        preview_row.addWidget(self._preview_title)
        self.preview_lbl = QLabel("—")
        self.preview_lbl.setStyleSheet(
            "QLabel { background:#111; color:#0f0; padding:4px; border-radius:4px; }"
        )
        self.preview_lbl.setWordWrap(True)
        preview_row.addWidget(self.preview_lbl, 1)
        tmpl_layout.addLayout(preview_row)

        self._test_btn = QPushButton(str(_("chatbox_tab.send_test_btn")))
        self._test_btn.clicked.connect(self._send_test)
        tmpl_layout.addWidget(self._test_btn)

        self._tmpl_group.setLayout(tmpl_layout)
        root.addWidget(self._tmpl_group)

        # ── Variable reference ─────────────────────────────────────────────────
        self._ref_group = QGroupBox(str(_("chatbox_tab.ref_group")))
        ref_layout = QVBoxLayout()
        ref_label = QLabel(_VARIABLE_HELP)
        ref_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        ref_label.setStyleSheet("QLabel { font-family: monospace; font-size: 11px; }")
        ref_scroll = QScrollArea()
        ref_scroll.setWidget(ref_label)
        ref_scroll.setWidgetResizable(True)
        ref_scroll.setMaximumHeight(200)
        ref_layout.addWidget(ref_scroll)
        self._ref_group.setLayout(ref_layout)
        root.addWidget(self._ref_group)

        self.setLayout(root)

        # Live preview timer (1 s)
        self._preview_timer = QTimer(self)
        self._preview_timer.setInterval(1000)
        self._preview_timer.timeout.connect(self._refresh_preview)
        self._preview_timer.start()

        # Periodic chatbox send timer (driven by interval_spin)
        self._send_timer = QTimer(self)
        self._send_timer.setInterval(int(self.interval_spin.value() * 1000))
        self._send_timer.timeout.connect(self._auto_send)

        language_signals.language_changed.connect(self.update_ui_texts)

    # ── Controller binding ────────────────────────────────────────────────────

    def bind_controller(self, controller) -> None:
        self._controller = controller
        controller.chatbox_enabled  = self.enable_check.isChecked()
        controller.chatbox_template = self.template_edit.toPlainText()
        controller.chatbox_interval = self.interval_spin.value()
        # Sync timer with current enable state
        if controller.chatbox_enabled:
            self._send_timer.start()
        else:
            self._send_timer.stop()

    # ── Callbacks ─────────────────────────────────────────────────────────────

    def _on_enable_changed(self, state: int) -> None:
        enabled = bool(state)
        if self._controller:
            self._controller.chatbox_enabled = enabled
        if enabled:
            self._send_timer.start()
        else:
            self._send_timer.stop()
            if self._controller and self._controller.osc_client:
                self._controller.osc_client.send_message("/chatbox/input", ["", True, False])

    def _on_interval_changed(self, v: float) -> None:
        if self._controller:
            self._controller.chatbox_interval = v
        self._send_timer.setInterval(int(max(0.5, v) * 1000))

    def _on_template_changed(self) -> None:
        text = self.template_edit.toPlainText()
        if self._controller:
            self._controller.chatbox_template = text
        self._refresh_preview()

    def _auto_send(self) -> None:
        """Called by _send_timer to send chatbox periodically."""
        if self._controller and self._controller.chatbox_enabled:
            self._controller.send_chatbox_now()

    def _refresh_preview(self) -> None:
        if not self._controller:
            return
        ctx = self._controller.build_chatbox_context()
        tmpl = self.template_edit.toPlainText()
        try:
            rendered = tmpl.format_map(ctx)
        except (KeyError, ValueError) as e:
            rendered = f"[format error: {e}]"
        self.preview_lbl.setText(rendered or "—")

    def _send_test(self) -> None:
        if not self._controller:
            self.preview_lbl.setText(str(_("chatbox_tab.no_controller")))
            return
        self._controller.send_chatbox_now()
        self._refresh_preview()

    def update_ui_texts(self) -> None:
        self._ctrl_group.setTitle(str(_("chatbox_tab.control_group")))
        self.enable_check.setText(str(_("chatbox_tab.enable_check")))
        self._tmpl_group.setTitle(str(_("chatbox_tab.template_group")))
        self._tmpl_hint.setText(str(_("chatbox_tab.template_hint")))
        self._preview_title.setText(str(_("chatbox_tab.preview_label")))
        self._test_btn.setText(str(_("chatbox_tab.send_test_btn")))
        self._ref_group.setTitle(str(_("chatbox_tab.ref_group")))
