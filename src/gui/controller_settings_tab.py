"""controller_settings_tab.py - Motor A/B/C speed and mode control UI."""
from __future__ import annotations

import asyncio
import logging

from PySide6.QtCore import QLocale, Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QGroupBox, QHBoxLayout,
    QLabel, QSlider, QSpinBox, QToolTip, QWidget,
)
from PySide6.QtCore import QPoint

from command_types import CommandType
from i18n import language_signals, translate as _

log = logging.getLogger(__name__)
_EN = QLocale(QLocale.Language.English, QLocale.Country.UnitedStates)

MOTOR_NAMES = ("A", "B", "C")
MODE_LABELS = ["1", "2", "3", "4"]


class ControllerSettingsTab(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._controller = None

        # Per-motor GUI update guards (prevent slider → command loop while dragging)
        self._slider_dragging: dict[str, bool] = {m: False for m in MOTOR_NAMES}

        root = QFormLayout(self)
        self.setLayout(root)

        # ── Motor control group ───────────────────────────────────────────────
        self.controller_group = QGroupBox(str(_("controller_tab.title")))
        self.controller_group.setEnabled(False)
        ctrl_form = QFormLayout()

        self._speed_labels:  dict[str, QLabel]  = {}
        self._speed_sliders: dict[str, QSlider] = {}
        self._mode_combos:   dict[str, QComboBox] = {}

        for m in MOTOR_NAMES:
            lbl = QLabel(self._format_label(m, 0, 1))
            ctrl_form.addRow(lbl)

            sld = QSlider(Qt.Horizontal)
            sld.setLocale(_EN)
            sld.setRange(0, 100)
            sld.sliderPressed.connect(lambda _m=m: self._on_slider_pressed(_m))
            sld.sliderReleased.connect(lambda _m=m: self._on_slider_released(_m))
            sld.valueChanged.connect(lambda v, _m=m: self._on_slider_changed(_m, v))
            ctrl_form.addRow(sld)

            mode_combo = QComboBox()
            mode_combo.setLocale(_EN)
            for lbl_text in MODE_LABELS:
                mode_combo.addItem(lbl_text)
            mode_combo.currentIndexChanged.connect(
                lambda idx, _m=m: self._on_mode_changed(_m, idx + 1)
            )
            ctrl_form.addRow(f"{m} {_('controller_tab.mode')}:", mode_combo)

            self._speed_labels[m]  = lbl
            self._speed_sliders[m] = sld
            self._mode_combos[m]   = mode_combo

        # ChatBox
        self.chatbox_check = QCheckBox(str(_("controller_tab.enable_chatbox")))
        self.chatbox_check.stateChanged.connect(self._on_chatbox_changed)
        ctrl_form.addRow(self.chatbox_check)

        # Fire / adjust steps
        self.fire_step_spin = QSpinBox()
        self.fire_step_spin.setLocale(_EN)
        self.fire_step_spin.setRange(0, 100)
        self.fire_step_spin.setValue(30)
        self.fire_step_spin.valueChanged.connect(self._on_fire_step_changed)
        ctrl_form.addRow(str(_("controller_tab.strength_step")) + ":", self.fire_step_spin)

        self.adjust_step_spin = QSpinBox()
        self.adjust_step_spin.setLocale(_EN)
        self.adjust_step_spin.setRange(0, 100)
        self.adjust_step_spin.setValue(5)
        self.adjust_step_spin.valueChanged.connect(self._on_adjust_step_changed)
        ctrl_form.addRow(str(_("controller_tab.adjust_step")) + ":", self.adjust_step_spin)

        self.controller_group.setLayout(ctrl_form)
        root.addRow(self.controller_group)

        # ── Command source group ──────────────────────────────────────────────
        self.command_group = QGroupBox(str(_("controller_tab.command_sources")))
        self.command_group.setEnabled(False)
        cmd_form = QFormLayout()

        self.gui_check   = QCheckBox(str(_("controller_tab.enable_gui_control")))
        self.gui_check.setChecked(True)
        self.gui_check.stateChanged.connect(self._on_gui_changed)
        cmd_form.addRow(self.gui_check)

        panel_row = QHBoxLayout()
        self.panel_check = QCheckBox(str(_("controller_tab.enable_soundpad")))
        self.panel_check.setChecked(True)
        self.panel_check.stateChanged.connect(self._on_panel_changed)
        self.current_motor_label = QLabel(
            str(_("controller_tab.current_panel")) + ": " + str(_("controller_tab.not_set"))
        )
        panel_row.addWidget(self.panel_check)
        panel_row.addWidget(self.current_motor_label)
        cmd_form.addRow(panel_row)

        self.interaction_check = QCheckBox(str(_("controller_tab.enable_interaction")))
        self.interaction_check.setChecked(True)
        self.interaction_check.stateChanged.connect(self._on_interaction_changed)
        cmd_form.addRow(self.interaction_check)

        self.command_group.setLayout(cmd_form)
        root.addRow(self.command_group)

        language_signals.language_changed.connect(self.update_ui_texts)

    # ── Controller binding ────────────────────────────────────────────────────

    def bind_controller(self, controller) -> None:
        self._controller = controller
        controller.fire_step   = self.fire_step_spin.value()
        controller.adjust_step = self.adjust_step_spin.value()
        controller.enable_chatbox     = self.chatbox_check.isChecked()
        controller.enable_gui         = self.gui_check.isChecked()
        controller.enable_panel       = self.panel_check.isChecked()
        controller.enable_interaction = self.interaction_check.isChecked()
        self.reset_display()

    def reset_display(self) -> None:
        for m in MOTOR_NAMES:
            sld = self._speed_sliders[m]
            sld.blockSignals(True)
            sld.setValue(0)
            sld.blockSignals(False)
            self._speed_labels[m].setText(self._format_label(m, 0, 1))
            self._mode_combos[m].blockSignals(True)
            self._mode_combos[m].setCurrentIndex(0)
            self._mode_combos[m].blockSignals(False)

    # ── Callbacks from controller ──────────────────────────────────────────────

    def update_motor_display(self, speeds: dict, modes: dict) -> None:
        for m in MOTOR_NAMES:
            spd  = speeds.get(m, 0)
            mode = modes.get(m, 1)
            lbl  = self._speed_labels[m]
            sld  = self._speed_sliders[m]
            cmb  = self._mode_combos[m]

            lbl.setText(self._format_label(m, spd, mode))

            if not self._slider_dragging[m]:
                sld.blockSignals(True)
                sld.setValue(spd)
                sld.blockSignals(False)

            cmb.blockSignals(True)
            cmb.setCurrentIndex(mode - 1)
            cmb.blockSignals(False)

    def update_current_motor_display(self, motor: str) -> None:
        self.current_motor_label.setText(
            str(_("controller_tab.current_panel")) + f": {motor}"
        )

    # ── Slider events ─────────────────────────────────────────────────────────

    def _on_slider_pressed(self, motor: str) -> None:
        self._slider_dragging[motor] = True

    def _on_slider_released(self, motor: str) -> None:
        self._slider_dragging[motor] = False
        sld = self._speed_sliders[motor]
        self._send_speed(motor, sld.value())

    def _on_slider_changed(self, motor: str, value: int) -> None:
        if not self._slider_dragging[motor]:
            return
        sld = self._speed_sliders[motor]
        QToolTip.showText(
            sld.mapToGlobal(QPoint(0, -30)), str(value), sld
        )

    def _send_speed(self, motor: str, speed: int) -> None:
        if self._controller:
            asyncio.create_task(self._controller.gui_set_speed(motor, speed))

    # ── Mode / checkbox events ─────────────────────────────────────────────────

    def _on_mode_changed(self, motor: str, mode: int) -> None:
        if self._controller:
            asyncio.create_task(self._controller.gui_set_mode(motor, mode))

    def _on_chatbox_changed(self, state: int) -> None:
        if self._controller:
            self._controller.enable_chatbox = bool(state)

    def _on_fire_step_changed(self, v: int) -> None:
        if self._controller:
            self._controller.fire_step = v

    def _on_adjust_step_changed(self, v: int) -> None:
        if self._controller:
            self._controller.adjust_step = v

    def _on_gui_changed(self, state: int) -> None:
        if self._controller:
            self._controller.enable_gui = bool(state)

    def _on_panel_changed(self, state: int) -> None:
        if self._controller:
            self._controller.enable_panel = bool(state)

    def _on_interaction_changed(self, state: int) -> None:
        if self._controller:
            self._controller.enable_interaction = bool(state)

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _format_label(motor: str, speed: int, mode: int) -> str:
        return f"{motor}  speed: {speed}  mode: {mode}"

    # ── i18n ──────────────────────────────────────────────────────────────────

    def update_ui_texts(self) -> None:
        self.controller_group.setTitle(str(_("controller_tab.title")))
        self.command_group.setTitle(str(_("controller_tab.command_sources")))
        self.chatbox_check.setText(str(_("controller_tab.enable_chatbox")))
        self.gui_check.setText(str(_("controller_tab.enable_gui_control")))
        self.panel_check.setText(str(_("controller_tab.enable_soundpad")))
        self.interaction_check.setText(str(_("controller_tab.enable_interaction")))
