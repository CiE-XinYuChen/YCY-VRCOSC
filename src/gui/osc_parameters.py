"""osc_parameters.py - OSC address → device action mapping (toy motors + estim channels)."""
from __future__ import annotations

import logging
import os

import yaml
from PySide6.QtCore import QLocale, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton,
    QSlider, QVBoxLayout, QWidget,
)

from config import get_config_file_path
from i18n import translate as _

log = logging.getLogger(__name__)
_EN = QLocale(QLocale.Language.English, QLocale.Country.UnitedStates)

_TARGET_TYPES = ["toy", "estim"]
_TOY_CHS   = ("A", "B", "C")
_ESTIM_CHS = ("A", "B")

_ALL_DEVICES_ADDR = ""


class OSCParametersTab(QWidget):
    addresses_updated = Signal()

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.addresses: list[dict] = []
        self._devices: dict = {}

        layout = QVBoxLayout()
        self.setLayout(layout)

        self.list_widget = QListWidget()
        self.list_widget.setLocale(_EN)
        self.list_widget.setSelectionMode(QAbstractItemView.SingleSelection)
        layout.addWidget(self.list_widget)

        btn_row = QHBoxLayout()
        self.add_btn    = QPushButton(str(_("osc_tab.add")))
        self.remove_btn = QPushButton(str(_("osc_tab.remove")))
        btn_row.addWidget(self.add_btn)
        btn_row.addWidget(self.remove_btn)
        layout.addLayout(btn_row)

        self.add_btn.clicked.connect(self._add)
        self.remove_btn.clicked.connect(self._remove)

        self._load()
        self._populate()

    # ── Device list ────────────────────────────────────────────────────────────

    def set_devices(self, devices: dict) -> None:
        """Called whenever connected devices change."""
        self._devices = dict(devices)
        for i in range(self.list_widget.count()):
            w = self.list_widget.itemWidget(self.list_widget.item(i))
            if isinstance(w, _OSCAddressWidget):
                w.update_devices(self._devices)

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def _add(self):
        entry = {
            "address":        "",
            "device_address": "",
            "target_type":    "toy",
            "channels":       {"A": True, "B": False, "C": False},
            "mapping_ranges": {"A": {"min": 0, "max": 100},
                               "B": {"min": 0, "max": 100},
                               "C": {"min": 0, "max": 100}},
        }
        self.addresses.append(entry)
        self._append_widget(entry)
        self._save()
        self.addresses_updated.emit()

    def _remove(self):
        row = self.list_widget.currentRow()
        if row >= 0:
            self.list_widget.takeItem(row)
            del self.addresses[row]
            self._save()
            self.addresses_updated.emit()

    # ── Sync ──────────────────────────────────────────────────────────────────

    def _sync(self):
        new_list = []
        for i in range(self.list_widget.count()):
            w = self.list_widget.itemWidget(self.list_widget.item(i))
            if isinstance(w, _OSCAddressWidget):
                new_list.append(w.get_data())
        self.addresses = new_list

    def _on_changed(self):
        self._sync()
        self._save()
        self.addresses_updated.emit()

    # ── Persistence ────────────────────────────────────────────────────────────

    def _save(self):
        path = get_config_file_path("osc_addresses.yml")
        try:
            with open(path, "w", encoding="utf-8") as f:
                yaml.dump(self.addresses, f, allow_unicode=True)
        except Exception as e:
            log.error("Save OSC addresses failed: %s", e)

    def _load(self):
        path = get_config_file_path("osc_addresses.yml")
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                if isinstance(data, list):
                    self.addresses = data
                    return
        except Exception as e:
            log.error("Load OSC addresses failed: %s", e)
        self.addresses = self._defaults()

    def _defaults(self) -> list:
        return [
            {"address": "/avatar/parameters/DG-LAB/UpperLeg_L",
             "device_address": "", "target_type": "toy",
             "channels": {"A": True, "B": False, "C": False},
             "mapping_ranges": {"A": {"min": 0, "max": 100}}},
            {"address": "/avatar/parameters/DG-LAB/UpperLeg_R",
             "device_address": "", "target_type": "toy",
             "channels": {"A": False, "B": True, "C": False},
             "mapping_ranges": {"B": {"min": 0, "max": 100}}},
        ]

    # ── Widget helpers ─────────────────────────────────────────────────────────

    def _populate(self):
        self.list_widget.clear()
        for entry in self.addresses:
            self._append_widget(entry)

    def _append_widget(self, entry: dict):
        item   = QListWidgetItem()
        widget = _OSCAddressWidget(entry, self._devices)
        widget.changed.connect(self._on_changed)
        self.list_widget.addItem(item)
        item.setSizeHint(widget.sizeHint())
        self.list_widget.setItemWidget(item, widget)

    def get_addresses(self) -> list:
        return self.addresses

    def update_ui_texts(self):
        self.add_btn.setText(str(_("osc_tab.add")))
        self.remove_btn.setText(str(_("osc_tab.remove")))
        for i in range(self.list_widget.count()):
            w = self.list_widget.itemWidget(self.list_widget.item(i))
            if isinstance(w, _OSCAddressWidget):
                w.update_ui_texts()


class _OSCAddressWidget(QWidget):
    changed = Signal()

    def __init__(self, data: dict, devices: dict):
        super().__init__()
        self._building = True
        layout = QVBoxLayout()
        layout.setContentsMargins(4, 4, 4, 4)
        self.setLayout(layout)

        # Row 1: OSC address
        addr_row = QHBoxLayout()
        self.addr_edit = QLineEdit()
        self.addr_edit.setLocale(_EN)
        self.addr_edit.setPlaceholderText(str(_("osc_tab.address_placeholder")))
        self.addr_edit.setText(data.get("address", ""))
        addr_row.addWidget(self.addr_edit)
        layout.addLayout(addr_row)

        # Row 2: device combo + target type
        dev_row = QHBoxLayout()
        self._dev_label = QLabel(str(_("osc_tab.device_addr_label")))
        dev_row.addWidget(self._dev_label)

        self.dev_combo = QComboBox()
        self.dev_combo.setLocale(_EN)
        self._populate_device_combo(devices, data.get("device_address", ""))
        dev_row.addWidget(self.dev_combo, 1)

        self._type_label = QLabel(str(_("osc_tab.type_label")))
        dev_row.addWidget(self._type_label)
        self.type_combo = QComboBox()
        self.type_combo.setLocale(_EN)
        self.type_combo.addItems(_TARGET_TYPES)
        current_type = data.get("target_type", "toy")
        self.type_combo.setCurrentIndex(_TARGET_TYPES.index(current_type)
                                        if current_type in _TARGET_TYPES else 0)
        dev_row.addWidget(self.type_combo)
        layout.addLayout(dev_row)

        # Row 3: channel checkboxes
        ch_row = QHBoxLayout()
        self._checks: dict[str, QCheckBox] = {}
        channels = data.get("channels", {})
        for ch in _TOY_CHS:
            cb = QCheckBox(ch)
            cb.setChecked(bool(channels.get(ch, False)))
            ch_row.addWidget(cb)
            self._checks[ch] = cb
        ch_row.addStretch()
        layout.addLayout(ch_row)

        # Range rows per channel
        self._range_widgets: dict[str, _RangeRow] = {}
        ranges = data.get("mapping_ranges", {})
        for ch in _TOY_CHS:
            r  = ranges.get(ch, {"min": 0, "max": 100})
            rw = _RangeRow(ch, r.get("min", 0), r.get("max", 100))
            rw.changed.connect(self.changed)
            self._range_widgets[ch] = rw
            layout.addWidget(rw)

        self._building = False
        self._update_visibility()

        # Signals
        self.addr_edit.textChanged.connect(self._emit)
        self.dev_combo.currentIndexChanged.connect(self._emit)
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        for cb in self._checks.values():
            cb.stateChanged.connect(self._on_check_changed)

    def _populate_device_combo(self, devices: dict, selected_addr: str = "") -> None:
        self.dev_combo.clear()
        self.dev_combo.addItem(str(_("osc_tab.all_devices")), _ALL_DEVICES_ADDR)
        for addr, info in devices.items():
            name  = info.get("name", addr[-8:])
            dtype = info.get("type", "?")
            self.dev_combo.addItem(f"{name}  [{dtype}]  ({addr[-8:]})", addr)
        idx = 0
        if selected_addr:
            for i in range(self.dev_combo.count()):
                if self.dev_combo.itemData(i) == selected_addr:
                    idx = i
                    break
        self.dev_combo.setCurrentIndex(idx)

    def update_devices(self, devices: dict) -> None:
        current_addr = self.dev_combo.currentData() or ""
        self._building = True
        self._populate_device_combo(devices, current_addr)
        self._building = False

    def _on_type_changed(self, *_):
        is_toy = self.type_combo.currentText() == "toy"
        self._checks["C"].setVisible(is_toy)
        if not is_toy:
            self._checks["C"].setChecked(False)
        self._update_visibility()
        self._emit()

    def _on_check_changed(self):
        self._update_visibility()
        self._emit()

    def _update_visibility(self):
        is_toy = self.type_combo.currentText() == "toy"
        chs = _TOY_CHS if is_toy else _ESTIM_CHS
        for ch in _TOY_CHS:
            visible = ch in chs and self._checks[ch].isChecked()
            self._range_widgets[ch].setVisible(visible)
        self.adjustSize()
        parent = self.parent()
        while parent and not isinstance(parent, QListWidget):
            parent = parent.parent()
        if parent:
            for i in range(parent.count()):
                item = parent.item(i)
                if parent.itemWidget(item) is self:
                    item.setSizeHint(self.sizeHint())
                    parent.viewport().update()
                    break

    def _emit(self):
        if not self._building:
            self.changed.emit()

    def get_data(self) -> dict:
        chs    = {ch: self._checks[ch].isChecked() for ch in _TOY_CHS}
        ranges = {ch: self._range_widgets[ch].get_range() for ch in _TOY_CHS}
        return {
            "address":        self.addr_edit.text(),
            "device_address": self.dev_combo.currentData() or "",
            "target_type":    self.type_combo.currentText(),
            "channels":       chs,
            "mapping_ranges": ranges,
        }

    def update_ui_texts(self):
        self.addr_edit.setPlaceholderText(str(_("osc_tab.address_placeholder")))
        self._dev_label.setText(str(_("osc_tab.device_addr_label")))
        self._type_label.setText(str(_("osc_tab.type_label")))
        if self.dev_combo.count() > 0:
            self.dev_combo.setItemText(0, str(_("osc_tab.all_devices")))
        for rw in self._range_widgets.values():
            rw.update_ui_texts()


class _RangeRow(QWidget):
    changed = Signal()

    def __init__(self, channel: str, lo: int, hi: int):
        super().__init__()
        self._ch = channel
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        layout.addWidget(QLabel(f"{channel} {_('osc_tab.channel_range')}:"))

        self.min_slider = QSlider(Qt.Horizontal)
        self.min_slider.setLocale(_EN)
        self.min_slider.setRange(0, 100)
        self.min_slider.setValue(lo)
        self.min_slider.setFixedWidth(100)
        layout.addWidget(self.min_slider)

        self.min_lbl = QLabel(f"{_('osc_tab.min_value')}:{lo}%")
        layout.addWidget(self.min_lbl)
        layout.addSpacing(8)

        self.max_slider = QSlider(Qt.Horizontal)
        self.max_slider.setLocale(_EN)
        self.max_slider.setRange(0, 100)
        self.max_slider.setValue(hi)
        self.max_slider.setFixedWidth(100)
        layout.addWidget(self.max_slider)

        self.max_lbl = QLabel(f"{_('osc_tab.max_value')}:{hi}%")
        layout.addWidget(self.max_lbl)
        layout.addStretch()

        self.min_slider.valueChanged.connect(self._on_min)
        self.max_slider.valueChanged.connect(self._on_max)

    def _on_min(self, v):
        self.min_lbl.setText(f"{_('osc_tab.min_value')}:{v}%")
        if v > self.max_slider.value():
            self.max_slider.setValue(v)
        self.changed.emit()

    def _on_max(self, v):
        self.max_lbl.setText(f"{_('osc_tab.max_value')}:{v}%")
        if v < self.min_slider.value():
            self.min_slider.setValue(v)
        self.changed.emit()

    def get_range(self) -> dict:
        return {"min": self.min_slider.value(), "max": self.max_slider.value()}

    def update_ui_texts(self):
        lo = self.min_slider.value()
        hi = self.max_slider.value()
        self.min_lbl.setText(f"{_('osc_tab.min_value')}:{lo}%")
        self.max_lbl.setText(f"{_('osc_tab.max_value')}:{hi}%")
