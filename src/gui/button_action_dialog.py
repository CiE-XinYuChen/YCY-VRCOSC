"""button_action_dialog.py — Dialog for editing a panel button's label and actions."""
from __future__ import annotations

import copy
import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QPushButton, QScrollArea, QSpinBox, QVBoxLayout, QWidget,
)

from panel_config import action_summary
from i18n import translate as _

log = logging.getLogger(__name__)

_TOY_ACTIONS   = ["adjust_speed", "set_speed", "set_mode", "stop"]
_ESTIM_ACTIONS = ["set_channel", "adjust_channel", "fire_channel",
                  "set_channel_mode", "toggle_channel", "stop"]
_GLOBAL_ACTIONS = ["toggle_chatbox"]  # no device address required


class _AddActionDialog(QDialog):
    """Sub-dialog: choose device + action type + parameters."""

    def __init__(self, devices: dict[str, dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle(str(_("button_dialog.add_action_title")))
        self.setMinimumWidth(380)
        self._devices = devices
        self._result_action: dict | None = None

        layout = QVBoxLayout(self)

        # Device selector
        dev_box = QGroupBox(str(_("button_dialog.device_group")))
        dev_form = QFormLayout()
        self._device_combo = QComboBox()
        self._device_combo.addItem(str(_("button_dialog.global_device")), "__global__")
        for addr, info in devices.items():
            self._device_combo.addItem(
                f"{info.get('name', addr[-8:])}  [{info.get('type', '?')}]", addr
            )
        dev_form.addRow(str(_("button_dialog.device_label")), self._device_combo)
        dev_box.setLayout(dev_form)
        layout.addWidget(dev_box)

        # Action type
        act_box = QGroupBox(str(_("button_dialog.action_group")))
        act_form = QFormLayout()
        self._action_combo = QComboBox()
        act_form.addRow(str(_("button_dialog.action_label")), self._action_combo)
        act_box.setLayout(act_form)
        layout.addWidget(act_box)

        # Params area
        self._params_group = QGroupBox(str(_("button_dialog.params_group")))
        self._params_form  = QFormLayout()
        self._params_group.setLayout(self._params_form)
        layout.addWidget(self._params_group)

        # Once checkbox
        self._once_check = QCheckBox(str(_("button_dialog.once_check")))
        layout.addWidget(self._once_check)

        # Buttons
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        self._device_combo.currentIndexChanged.connect(self._on_device_changed)
        self._action_combo.currentIndexChanged.connect(self._on_action_changed)
        self._on_device_changed()

    def _current_device_type(self) -> str:
        addr = self._device_combo.currentData()
        if addr == "__global__":
            return "__global__"
        return self._devices.get(addr, {}).get("type", "toy")

    def _on_device_changed(self, *_args):
        dtype = self._current_device_type()
        self._action_combo.blockSignals(True)
        self._action_combo.clear()
        if dtype == "__global__":
            for a in _GLOBAL_ACTIONS:
                self._action_combo.addItem(a)
        elif dtype == "toy":
            for a in _TOY_ACTIONS:
                self._action_combo.addItem(a)
        else:
            for a in _ESTIM_ACTIONS:
                self._action_combo.addItem(a)
        self._action_combo.blockSignals(False)
        self._on_action_changed()

    def _on_action_changed(self, *_args):
        # Clear old widgets
        while self._params_form.rowCount():
            self._params_form.removeRow(0)
        self._param_widgets: dict = {}

        act   = self._action_combo.currentText()
        dtype = self._current_device_type()

        if act in ("stop", "toggle_chatbox"):
            self._params_group.setVisible(False)
            self._once_check.setChecked(act == "toggle_chatbox")
            self.adjustSize()
            return

        self._params_group.setVisible(True)

        if dtype == "toy":
            if act == "adjust_speed":
                mc = QComboBox()
                mc.addItems(["A", "B", "C"])
                self._params_form.addRow(str(_("button_dialog.motor_label")), mc)
                self._param_widgets["motor_combo"] = mc

                delta = QSpinBox(); delta.setRange(-20, 20); delta.setValue(5)
                self._params_form.addRow(str(_("button_dialog.delta_label")), delta)
                self._param_widgets["delta"] = delta
                self._once_check.setChecked(False)

            elif act == "set_speed":
                for motor, key in (("A", "motor_a_label"), ("B", "motor_b_label"), ("C", "motor_c_label")):
                    sp = QSpinBox(); sp.setRange(0, 20); sp.setValue(0)
                    self._params_form.addRow(str(_("button_dialog." + key)), sp)
                    self._param_widgets[f"motor_{motor.lower()}"] = sp
            elif act == "set_mode":
                mc = QComboBox()
                mc.addItems(["A", "B", "C", "AB", "ABC"])
                self._params_form.addRow(str(_("button_dialog.motors_label")), mc)
                self._param_widgets["motors_combo"] = mc
                md = QSpinBox(); md.setRange(1, 4); md.setValue(1)
                self._params_form.addRow(str(_("button_dialog.mode_label")), md)
                self._param_widgets["mode"] = md

        elif dtype == "estim":
            if act == "set_channel":
                ch = QComboBox(); ch.addItems(["A", "B"])
                self._params_form.addRow(str(_("button_dialog.channel_label")), ch)
                self._param_widgets["channel_combo"] = ch

                en = QCheckBox(str(_("button_dialog.enabled_label"))); en.setChecked(True)
                self._params_form.addRow(en)
                self._param_widgets["enabled"] = en

                inten = QSpinBox(); inten.setRange(1, 276); inten.setValue(20)
                self._params_form.addRow(str(_("button_dialog.intensity_label")), inten)
                self._param_widgets["intensity"] = inten

                mode = QSpinBox(); mode.setRange(1, 17); mode.setValue(1)
                self._params_form.addRow(str(_("button_dialog.mode_fixed_label")), mode)
                self._param_widgets["mode"] = mode

                freq = QSpinBox(); freq.setRange(1, 100); freq.setValue(10)
                self._params_form.addRow(str(_("button_dialog.freq_label")), freq)
                self._param_widgets["freq"] = freq

                pulse = QSpinBox(); pulse.setRange(0, 100); pulse.setValue(30)
                self._params_form.addRow(str(_("button_dialog.pulse_label")), pulse)
                self._param_widgets["pulse_us"] = pulse

            elif act == "adjust_channel":
                ch = QComboBox(); ch.addItems(["A", "B"])
                self._params_form.addRow(str(_("button_dialog.channel_label")), ch)
                self._param_widgets["channel_combo"] = ch

                delta = QSpinBox(); delta.setRange(-276, 276); delta.setValue(5)
                self._params_form.addRow(str(_("button_dialog.delta_label")), delta)
                self._param_widgets["delta"] = delta
                self._once_check.setChecked(False)

            elif act == "fire_channel":
                ch = QComboBox(); ch.addItems(["A", "B"])
                self._params_form.addRow(str(_("button_dialog.channel_label")), ch)
                self._param_widgets["channel_combo"] = ch

                fi = QSpinBox(); fi.setRange(1, 276); fi.setValue(30)
                self._params_form.addRow(str(_("button_dialog.fire_delta_label")), fi)
                self._param_widgets["fire_intensity"] = fi
                self._once_check.setChecked(False)

            elif act == "set_channel_mode":
                ch = QComboBox(); ch.addItems(["A", "B"])
                self._params_form.addRow(str(_("button_dialog.channel_label")), ch)
                self._param_widgets["channel_combo"] = ch

                mode = QSpinBox(); mode.setRange(1, 17); mode.setValue(1)
                self._params_form.addRow(str(_("button_dialog.waveform_label")), mode)
                self._param_widgets["mode"] = mode
                self._once_check.setChecked(True)

            elif act == "toggle_channel":
                ch = QComboBox(); ch.addItems(["A", "B"])
                self._params_form.addRow(str(_("button_dialog.channel_label")), ch)
                self._param_widgets["channel_combo"] = ch
                self._once_check.setChecked(True)

        self._params_group.adjustSize()
        self.adjustSize()

    def _on_accept(self):
        addr  = self._device_combo.currentData()
        act   = self._action_combo.currentText()
        pw    = self._param_widgets
        once  = self._once_check.isChecked()

        if addr == "__global__":
            addr = ""

        if act == "stop":
            params = {}
        elif act == "toggle_chatbox":
            params = {}
        elif act == "toggle_channel":
            ch_w = pw.get("channel_combo")
            params = {"channel": ch_w.currentText() if ch_w else "A"}
        elif act == "adjust_speed":
            params = {
                "motor": pw["motor_combo"].currentText(),
                "delta": pw["delta"].value(),
            }
        elif act == "set_speed":
            params = {
                "motor_a": pw["motor_a"].value(),
                "motor_b": pw["motor_b"].value(),
                "motor_c": pw["motor_c"].value(),
            }
        elif act == "set_mode":
            params = {
                "motors": pw["motors_combo"].currentText(),
                "mode":   pw["mode"].value(),
            }
        elif act == "set_channel":
            params = {
                "channel":   pw["channel_combo"].currentText(),
                "enabled":   pw["enabled"].isChecked(),
                "intensity": pw["intensity"].value(),
                "mode":      pw["mode"].value(),
                "freq":      pw["freq"].value(),
                "pulse_us":  pw["pulse_us"].value(),
            }
        elif act == "adjust_channel":
            params = {
                "channel": pw["channel_combo"].currentText(),
                "delta":   pw["delta"].value(),
            }
        elif act == "fire_channel":
            params = {
                "channel":        pw["channel_combo"].currentText(),
                "fire_intensity": pw["fire_intensity"].value(),
            }
        elif act == "set_channel_mode":
            params = {
                "channel": pw["channel_combo"].currentText(),
                "mode":    pw["mode"].value(),
            }
        else:
            params = {}

        self._result_action = {"device_address": addr, "action": act, "params": params}
        if once:
            self._result_action["once"] = True
        self.accept()

    def result_action(self) -> dict | None:
        return self._result_action


class ButtonActionDialog(QDialog):
    """Main dialog: edit label + action list for one panel button."""

    def __init__(self, panel_idx: int, btn_idx: int, button: dict | None,
                 devices: dict[str, dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle(
            str(_("button_dialog.title")).format(panel=panel_idx + 1, btn=btn_idx + 1)
        )
        self.setMinimumWidth(480)
        self._panel_idx = panel_idx
        self._btn_idx   = btn_idx
        self._devices   = devices
        self._button    = copy.deepcopy(button) if button else {
            "index": btn_idx, "label": "", "actions": []
        }

        layout = QVBoxLayout(self)

        # Label
        lbl_row = QHBoxLayout()
        lbl_row.addWidget(QLabel(str(_("button_dialog.label_prefix"))))
        self._label_edit = QLineEdit(self._button.get("label", ""))
        lbl_row.addWidget(self._label_edit)
        layout.addLayout(lbl_row)

        # Action list
        act_group = QGroupBox(str(_("button_dialog.actions_group")))
        act_layout = QVBoxLayout()

        self._action_list = QListWidget()
        self._action_list.setMinimumHeight(120)
        self._refresh_list()
        act_layout.addWidget(self._action_list)

        btn_row = QHBoxLayout()
        add_btn = QPushButton(str(_("button_dialog.add_btn")))
        add_btn.clicked.connect(self._add_action)
        del_btn = QPushButton(str(_("button_dialog.remove_btn")))
        del_btn.clicked.connect(self._remove_action)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(del_btn)
        btn_row.addStretch()
        act_layout.addLayout(btn_row)
        act_group.setLayout(act_layout)
        layout.addWidget(act_group)

        # OK / Cancel
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _refresh_list(self):
        self._action_list.clear()
        for action in self._button.get("actions", []):
            self._action_list.addItem(action_summary(action, self._devices))

    def _add_action(self):
        if not self._devices:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, str(_("button_dialog.no_devices_title")),
                                str(_("button_dialog.no_devices_msg")))
            return
        dlg = _AddActionDialog(self._devices, parent=self)
        if dlg.exec() == QDialog.Accepted:
            action = dlg.result_action()
            if action:
                self._button.setdefault("actions", []).append(action)
                self._refresh_list()

    def _remove_action(self):
        row = self._action_list.currentRow()
        if row < 0:
            return
        actions = self._button.get("actions", [])
        if row < len(actions):
            actions.pop(row)
            self._refresh_list()

    def _on_accept(self):
        self._button["label"] = self._label_edit.text().strip()
        self._button["index"] = self._btn_idx
        self.accept()

    def result_button(self) -> dict:
        return self._button
