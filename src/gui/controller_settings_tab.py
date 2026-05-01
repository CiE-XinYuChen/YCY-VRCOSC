"""controller_settings_tab.py — Multi-device live control panel (toy + estim)."""
from __future__ import annotations

import asyncio
import contextvars
import logging

from PySide6.QtCore import QLocale, Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QGroupBox, QHBoxLayout,
    QLabel, QPushButton, QScrollArea, QSlider, QSpinBox, QVBoxLayout, QWidget,
)

from i18n import language_signals, translate as _

log = logging.getLogger(__name__)
_EN = QLocale(QLocale.Language.English, QLocale.Country.UnitedStates)


def _spawn(coro):
    loop = asyncio.get_event_loop()
    loop.call_soon(lambda: loop.create_task(coro, context=contextvars.copy_context()))

_TOY_MOTORS = ("A", "B", "C")
_ESTIM_CHS  = ("A", "B")
_MOTOR_BITS = {"A": 1, "B": 2, "C": 4}


class _ToySection(QGroupBox):
    """Per-device control section for a toy (3-motor) device."""

    def __init__(self, address: str, name: str, controller):
        super().__init__(f"🟢 {name}  [{address[-8:]}]  [toy]")
        self._addr       = address
        self._controller = controller

        self._speeds: dict[str, int] = {m: 0 for m in _TOY_MOTORS}
        self._modes:  dict[str, int] = {m: 1 for m in _TOY_MOTORS}

        form = QFormLayout()

        self._sliders: dict[str, QSlider]  = {}
        self._combos:  dict[str, QComboBox] = {}

        for m in _TOY_MOTORS:
            lbl = QLabel(str(_("controller_tab.speed_fmt")).format(m=m, v=0, mode=1))
            form.addRow(lbl)
            setattr(self, f"_lbl_{m}", lbl)

            sld = QSlider(Qt.Horizontal)
            sld.setLocale(_EN)
            sld.setRange(0, 20)
            sld.valueChanged.connect(lambda v, _m=m: self._on_speed(_m, v))
            form.addRow(sld)
            self._sliders[m] = sld

            combo = QComboBox()
            combo.setLocale(_EN)
            combo.addItems([str(i) for i in range(1, 5)])
            combo.currentIndexChanged.connect(lambda idx, _m=m: self._on_mode(_m, idx + 1))
            form.addRow(str(_("controller_tab.mode_row")).format(m=m), combo)
            self._combos[m] = combo

        self._stop_btn = QPushButton(str(_("controller_tab.stop_btn")))
        self._stop_btn.clicked.connect(self._on_stop)
        form.addRow(self._stop_btn)

        self.setLayout(form)

    def _on_speed(self, motor: str, value: int) -> None:
        self._speeds[motor] = value
        getattr(self, f"_lbl_{motor}").setText(
            str(_("controller_tab.speed_fmt")).format(
                m=motor, v=value, mode=self._modes[motor])
        )
        _spawn(self._controller.gui_toy_set_speed(
            self._addr,
            self._speeds["A"], self._speeds["B"], self._speeds["C"],
        ))

    def _on_mode(self, motor: str, mode: int) -> None:
        self._modes[motor] = mode
        getattr(self, f"_lbl_{motor}").setText(
            str(_("controller_tab.speed_fmt")).format(
                m=motor, v=self._speeds[motor], mode=mode)
        )
        _spawn(self._controller.gui_toy_set_mode(
            self._addr, _MOTOR_BITS.get(motor, 1), mode
        ))

    def _on_stop(self) -> None:
        for m in _TOY_MOTORS:
            self._speeds[m] = 0
            self._sliders[m].blockSignals(True)
            self._sliders[m].setValue(0)
            self._sliders[m].blockSignals(False)
            getattr(self, f"_lbl_{m}").setText(
                str(_("controller_tab.speed_fmt")).format(m=m, v=0, mode=self._modes[m])
            )
        _spawn(self._controller.gui_stop_device(self._addr))

    def update_from_event(self, data: dict) -> None:
        pass

    def update_ui_texts(self) -> None:
        self._stop_btn.setText(str(_("controller_tab.stop_btn")))
        for m in _TOY_MOTORS:
            getattr(self, f"_lbl_{m}").setText(
                str(_("controller_tab.speed_fmt")).format(
                    m=m, v=self._speeds[m], mode=self._modes[m])
            )


class _EstimSection(QGroupBox):
    """Per-device control section for an estim (dual-channel) device."""

    _DEFAULT_CAP = 100

    def __init__(self, address: str, name: str, controller):
        super().__init__(f"🟢 {name}  [{address[-8:]}]  [estim]")
        self._addr       = address
        self._controller = controller

        self._enabled:   dict[str, bool] = {ch: False for ch in _ESTIM_CHS}
        self._intensity: dict[str, int]  = {ch: 0     for ch in _ESTIM_CHS}
        self._modes:     dict[str, int]  = {ch: 1     for ch in _ESTIM_CHS}
        self._caps:      dict[str, int]  = {ch: self._DEFAULT_CAP for ch in _ESTIM_CHS}

        # Debounce timers — only send to device 80ms after slider stops moving
        self._debounce: dict[str, QTimer] = {}
        for ch in _ESTIM_CHS:
            t = QTimer(self)
            t.setSingleShot(True)
            t.setInterval(80)
            t.timeout.connect(lambda _c=ch: self._send(_c))
            self._debounce[ch] = t

        form = QFormLayout()

        self._en_checks:   dict[str, QCheckBox] = {}
        self._int_sliders: dict[str, QSlider]   = {}
        self._val_labels:  dict[str, QLabel]    = {}
        self._cap_spins:   dict[str, QSpinBox]  = {}
        self._md_combos:   dict[str, QComboBox] = {}
        self._int_labels:  dict[str, QLabel]    = {}
        self._cap_labels:  dict[str, QLabel]    = {}
        self._mode_labels: dict[str, QLabel]    = {}

        self._batt_lbl = QLabel(str(_("controller_tab.battery_unknown")))
        form.addRow(self._batt_lbl)

        for ch in _ESTIM_CHS:
            en = QCheckBox(str(_("controller_tab.ch_enabled")).format(ch=ch))
            en.stateChanged.connect(lambda s, _c=ch: self._on_enabled(_c, bool(s)))
            form.addRow(en)
            self._en_checks[ch] = en

            # Intensity row: [强度:] [slider] [val] [上限:] [cap_spinbox]
            int_row = QHBoxLayout()
            int_lbl = QLabel(str(_("controller_tab.intensity_label")))
            int_row.addWidget(int_lbl)
            self._int_labels[ch] = int_lbl

            sld = QSlider(Qt.Horizontal)
            sld.setLocale(_EN)
            sld.setRange(0, self._caps[ch])
            sld.setValue(self._intensity[ch])
            sld.valueChanged.connect(lambda v, _c=ch: self._on_intensity(_c, v))
            int_row.addWidget(sld, stretch=2)
            self._int_sliders[ch] = sld

            val_lbl = QLabel(str(self._intensity[ch]))
            val_lbl.setMinimumWidth(28)
            int_row.addWidget(val_lbl)
            self._val_labels[ch] = val_lbl

            cap_lbl = QLabel(str(_("controller_tab.cap_label")))
            int_row.addWidget(cap_lbl)
            self._cap_labels[ch] = cap_lbl

            cap_sp = QSpinBox()
            cap_sp.setLocale(_EN)
            cap_sp.setRange(1, 276)
            cap_sp.setValue(self._caps[ch])
            cap_sp.setFixedWidth(64)
            cap_sp.valueChanged.connect(lambda v, _c=ch: self._on_cap(_c, v))
            int_row.addWidget(cap_sp)
            self._cap_spins[ch] = cap_sp

            form.addRow(int_row)

            # Mode row
            mode_row = QHBoxLayout()
            mode_lbl = QLabel(str(_("controller_tab.mode_label")))
            mode_row.addWidget(mode_lbl)
            self._mode_labels[ch] = mode_lbl

            md = QComboBox()
            md.setLocale(_EN)
            md.addItems([str(i) for i in range(1, 18)])
            md.currentIndexChanged.connect(lambda idx, _c=ch: self._on_mode(_c, idx + 1))
            mode_row.addWidget(md)
            self._md_combos[ch] = md
            mode_row.addStretch()

            form.addRow(mode_row)

        self._stop_btn = QPushButton(str(_("controller_tab.stop_all_btn")))
        self._stop_btn.clicked.connect(self._on_stop)
        form.addRow(self._stop_btn)

        self.setLayout(form)

    def _on_cap(self, ch: str, cap: int) -> None:
        self._caps[ch] = cap
        self._int_sliders[ch].setRange(0, cap)
        if self._intensity[ch] > cap:
            self._int_sliders[ch].setValue(cap)
        self._controller.set_intensity_cap(self._addr, ch, cap)

    def _on_enabled(self, ch: str, enabled: bool) -> None:
        self._enabled[ch] = enabled
        self._send(ch)

    def _on_intensity(self, ch: str, value: int) -> None:
        self._intensity[ch] = value
        self._val_labels[ch].setText(str(value))
        self._debounce[ch].start()  # restart 80ms countdown on every tick

    def _on_mode(self, ch: str, mode: int) -> None:
        self._modes[ch] = mode
        self._send(ch)

    def _send(self, ch: str) -> None:
        _spawn(self._controller.gui_estim_set_channel(
            self._addr, ch, self._enabled[ch],
            self._intensity[ch], self._modes[ch],
        ))

    def _on_stop(self) -> None:
        for ch in _ESTIM_CHS:
            self._enabled[ch] = False
            self._en_checks[ch].blockSignals(True)
            self._en_checks[ch].setChecked(False)
            self._en_checks[ch].blockSignals(False)
        _spawn(self._controller.gui_stop_device(self._addr))

    def update_from_event(self, data: dict) -> None:
        etype = data.get("type") or data.get("event")
        payload = data.get("data", data)

        if etype == "channel_status":
            ch = payload.get("channel")
            if ch in _ESTIM_CHS:
                cap = self._caps.get(ch, 276)
                self._enabled[ch]   = payload.get("enabled", False)
                self._intensity[ch] = max(0, min(cap, payload.get("intensity", 0)))
                self._modes[ch]     = payload.get("mode", 1)

                self._en_checks[ch].blockSignals(True)
                self._en_checks[ch].setChecked(self._enabled[ch])
                self._en_checks[ch].blockSignals(False)

                self._int_sliders[ch].blockSignals(True)
                self._int_sliders[ch].setValue(self._intensity[ch])
                self._int_sliders[ch].blockSignals(False)
                self._val_labels[ch].setText(str(self._intensity[ch]))

                self._md_combos[ch].blockSignals(True)
                self._md_combos[ch].setCurrentIndex(self._modes[ch] - 1)
                self._md_combos[ch].blockSignals(False)

        elif etype == "battery":
            level = payload.get("level", payload.get("battery", "?"))
            self._batt_lbl.setText(
                str(_("controller_tab.battery_fmt")).format(v=level)
            )

    def update_ui_texts(self) -> None:
        self._batt_lbl.setText(str(_("controller_tab.battery_unknown")))
        self._stop_btn.setText(str(_("controller_tab.stop_all_btn")))
        for ch in _ESTIM_CHS:
            self._en_checks[ch].setText(
                str(_("controller_tab.ch_enabled")).format(ch=ch)
            )
            self._int_labels[ch].setText(str(_("controller_tab.intensity_label")))
            self._cap_labels[ch].setText(str(_("controller_tab.cap_label")))
            self._mode_labels[ch].setText(str(_("controller_tab.mode_label")))


class ControllerSettingsTab(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._controller = None
        self._sections: dict[str, QWidget] = {}

        root = QVBoxLayout(self)

        self._hint_lbl = QLabel(str(_("controller_tab.hint")))
        self._hint_lbl.setAlignment(Qt.AlignCenter)
        root.addWidget(self._hint_lbl)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._scroll_content = QWidget()
        self._device_layout  = QVBoxLayout(self._scroll_content)
        self._device_layout.setAlignment(Qt.AlignTop)
        self._placeholder = QLabel(str(_("controller_tab.no_devices")))
        self._placeholder.setAlignment(Qt.AlignCenter)
        self._device_layout.addWidget(self._placeholder)
        scroll.setWidget(self._scroll_content)
        root.addWidget(scroll)

        self.setLayout(root)
        language_signals.language_changed.connect(self.update_ui_texts)

    def bind_controller(self, controller) -> None:
        self._controller = controller
        controller.on_device_added   = self._on_device_added
        controller.on_device_removed = self._on_device_removed
        for addr, info in controller.devices.items():
            self._on_device_added(addr, info.get("name", addr), info.get("type", "toy"))

    def _on_device_added(self, addr: str, name: str, dtype: str) -> None:
        if addr in self._sections:
            return
        self._placeholder.setVisible(False)
        if dtype == "estim":
            section = _EstimSection(addr, name, self._controller)
        else:
            section = _ToySection(addr, name, self._controller)
        self._sections[addr] = section
        self._device_layout.addWidget(section)

    def _on_device_removed(self, addr: str) -> None:
        section = self._sections.pop(addr, None)
        if section:
            self._device_layout.removeWidget(section)
            section.deleteLater()
        if not self._sections:
            self._placeholder.setVisible(True)

    def on_device_event(self, addr: str, data: dict) -> None:
        section = self._sections.get(addr)
        if section and hasattr(section, "update_from_event"):
            section.update_from_event(data)

    def reset_display(self) -> None:
        for addr in list(self._sections.keys()):
            self._on_device_removed(addr)

    def update_ui_texts(self) -> None:
        self._hint_lbl.setText(str(_("controller_tab.hint")))
        self._placeholder.setText(str(_("controller_tab.no_devices")))
        for section in self._sections.values():
            if hasattr(section, "update_ui_texts"):
                section.update_ui_texts()
