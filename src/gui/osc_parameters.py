"""osc_parameters.py - OSC address → motor (A/B/C) mapping configuration."""
from __future__ import annotations

import asyncio
import logging
import os

import yaml
from PySide6.QtCore import QLocale, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QPushButton, QSlider, QVBoxLayout, QWidget,
)
from PySide6.QtCore import Qt

from config import get_config_file_path
from i18n import translate as _

log = logging.getLogger(__name__)
_EN = QLocale(QLocale.Language.English, QLocale.Country.UnitedStates)
MOTOR_NAMES = ("A", "B", "C")


class OSCParametersTab(QWidget):
    addresses_updated = Signal()

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.addresses: list[dict] = []

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

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def _add(self):
        entry = {
            "address": "",
            "channels": {m: False for m in MOTOR_NAMES},
            "mapping_ranges": {m: {"min": 0, "max": 100} for m in MOTOR_NAMES},
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

    # ── Sync UI → model ────────────────────────────────────────────────────────

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
             "channels": {"A": True, "B": False, "C": False}},
            {"address": "/avatar/parameters/DG-LAB/UpperLeg_R",
             "channels": {"A": False, "B": True, "C": False}},
        ]

    # ── Widget helpers ─────────────────────────────────────────────────────────

    def _populate(self):
        self.list_widget.clear()
        for entry in self.addresses:
            self._append_widget(entry)

    def _append_widget(self, entry: dict):
        item   = QListWidgetItem()
        widget = _OSCAddressWidget(entry)
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

    def __init__(self, data: dict):
        super().__init__()
        self._building = True
        layout = QVBoxLayout()
        self.setLayout(layout)

        # Address + motor checkboxes
        addr_row = QHBoxLayout()
        self.addr_edit = QLineEdit()
        self.addr_edit.setLocale(_EN)
        self.addr_edit.setPlaceholderText(str(_("osc_tab.address_placeholder")))
        self.addr_edit.setText(data.get("address", ""))
        addr_row.addWidget(self.addr_edit)

        self._checks: dict[str, QCheckBox] = {}
        channels = data.get("channels", {})
        for m in MOTOR_NAMES:
            cb = QCheckBox(m)
            cb.setChecked(bool(channels.get(m, False)))
            addr_row.addWidget(cb)
            self._checks[m] = cb
        layout.addLayout(addr_row)

        # Range sliders per motor
        self._range_widgets: dict[str, _RangeRow] = {}
        ranges = data.get("mapping_ranges", {})
        for m in MOTOR_NAMES:
            r = ranges.get(m, {"min": 0, "max": 100})
            rw = _RangeRow(m, r.get("min", 0), r.get("max", 100))
            rw.changed.connect(self.changed)
            self._range_widgets[m] = rw
            layout.addWidget(rw)

        self._building = False
        self._update_visibility()

        # Connect signals
        self.addr_edit.textChanged.connect(self._emit)
        for cb in self._checks.values():
            cb.stateChanged.connect(self._on_check_changed)

    def _on_check_changed(self):
        self._update_visibility()
        self._emit()

    def _update_visibility(self):
        for m, cb in self._checks.items():
            self._range_widgets[m].setVisible(cb.isChecked())
        self.adjustSize()
        # Update list item size
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
        channels = {m: self._checks[m].isChecked() for m in MOTOR_NAMES}
        ranges   = {m: self._range_widgets[m].get_range() for m in MOTOR_NAMES}
        return {"address": self.addr_edit.text(), "channels": channels, "mapping_ranges": ranges}

    def update_ui_texts(self):
        self.addr_edit.setPlaceholderText(str(_("osc_tab.address_placeholder")))
        for rw in self._range_widgets.values():
            rw.update_ui_texts()


class _RangeRow(QWidget):
    changed = Signal()

    def __init__(self, motor: str, lo: int, hi: int):
        super().__init__()
        self._motor = motor
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        layout.addWidget(QLabel(f"{motor} {_('osc_tab.channel_range')}:"))

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
