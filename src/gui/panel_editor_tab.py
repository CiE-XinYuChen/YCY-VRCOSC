"""panel_editor_tab.py — 3-panel × 15-button grid UI for fusion controller."""
from __future__ import annotations

import asyncio
import logging
import os

import yaml
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QGridLayout, QGroupBox, QHBoxLayout, QLabel,
    QMessageBox, QPushButton, QTabWidget, QVBoxLayout, QWidget,
)

from panel_config import (
    NUM_BUTTONS, NUM_PANELS, PRESET_LABELS, PRESET_TARGETS, PRESETS,
    get_button, load_panels, make_panel_buttons, save_panels, set_button,
)
from gui.button_action_dialog import ButtonActionDialog
from i18n import language_signals, translate as _

log = logging.getLogger(__name__)

_ROWS = 3
_COLS = 5   # 3 × 5 = 15 buttons


class PanelEditorTab(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window  = main_window
        self._controller  = None
        self._panels      = load_panels()

        layout = QVBoxLayout(self)
        self.setLayout(layout)

        self._hint_lbl = QLabel(str(_("panel_tab.hint")))
        self._hint_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._hint_lbl)

        # Preset selector row
        preset_row = QHBoxLayout()
        self._preset_lbl = QLabel(str(_("panel_tab.preset_label")))
        self._preset_combo = QComboBox()
        for key, label in PRESET_LABELS.items():
            self._preset_combo.addItem(label, key)

        self._target_lbl = QLabel(str(_("panel_tab.target_label")))
        self._target_combo = QComboBox()
        self._refresh_target_combo()

        self._device_lbl = QLabel(str(_("panel_tab.device_label")))
        self._device_combo = QComboBox()
        self._device_combo.setMinimumWidth(140)
        self._refresh_device_combo()

        self._preset_apply_btn = QPushButton(str(_("panel_tab.preset_apply_btn")))
        self._preset_apply_btn.clicked.connect(self._apply_preset)
        self._preset_combo.currentIndexChanged.connect(self._refresh_target_combo)

        preset_row.addWidget(self._preset_lbl)
        preset_row.addWidget(self._preset_combo)
        preset_row.addWidget(self._target_lbl)
        preset_row.addWidget(self._target_combo)
        preset_row.addWidget(self._device_lbl)
        preset_row.addWidget(self._device_combo)
        preset_row.addWidget(self._preset_apply_btn)
        preset_row.addStretch()
        layout.addLayout(preset_row)

        # Import / Export row
        io_row = QHBoxLayout()
        self._import_btn = QPushButton(str(_("panel_tab.import_btn")))
        self._export_btn = QPushButton(str(_("panel_tab.export_btn")))
        self._import_btn.clicked.connect(self._import_preset)
        self._export_btn.clicked.connect(self._export_preset)
        io_row.addWidget(self._import_btn)
        io_row.addWidget(self._export_btn)
        io_row.addStretch()
        layout.addLayout(io_row)

        self._tab_widget = QTabWidget()
        layout.addWidget(self._tab_widget)

        self._btn_widgets: list[list[QPushButton]] = []

        for p in range(NUM_PANELS):
            page = QWidget()
            page_layout = QVBoxLayout(page)

            grid_box = QGroupBox("")
            grid = QGridLayout()
            grid.setSpacing(6)

            btns: list[QPushButton] = []
            for r in range(_ROWS):
                for c in range(_COLS):
                    idx = r * _COLS + c
                    btn = QPushButton(self._btn_label(p, idx))
                    btn.setMinimumSize(90, 48)
                    btn.setCheckable(False)
                    btn.clicked.connect(
                        lambda _checked, _p=p, _i=idx: self._on_btn_clicked(_p, _i)
                    )
                    grid.addWidget(btn, r, c)
                    btns.append(btn)

            grid_box.setLayout(grid)
            page_layout.addWidget(grid_box)
            self._tab_widget.addTab(page, str(_("panel_tab.page_label")).format(n=p + 1))
            self._btn_widgets.append(btns)

        language_signals.language_changed.connect(self.update_ui_texts)

    # ── Preset ────────────────────────────────────────────────────────────────

    def _refresh_target_combo(self) -> None:
        name = self._preset_combo.currentData()
        self._target_combo.clear()
        for label, targets in PRESET_TARGETS.get(name, []):
            self._target_combo.addItem(label, targets)

    def _refresh_device_combo(self) -> None:
        devices = self._controller.devices if self._controller else {}
        current_addr = self._device_combo.currentData() or ""
        self._device_combo.clear()
        self._device_combo.addItem(str(_("panel_tab.auto_device")), "")
        for addr, info in devices.items():
            name  = info.get("name", addr[-8:])
            dtype = info.get("type", "?")
            self._device_combo.addItem(f"{name} [{dtype}]", addr)
        # restore selection
        idx = 0
        if current_addr:
            for i in range(self._device_combo.count()):
                if self._device_combo.itemData(i) == current_addr:
                    idx = i
                    break
        self._device_combo.setCurrentIndex(idx)

    def _apply_preset(self) -> None:
        name    = self._preset_combo.currentData()
        targets = self._target_combo.currentData()
        current = self._tab_widget.currentIndex()
        device_addr = self._device_combo.currentData() or ""
        if not targets:
            return
        buttons = make_panel_buttons(name, targets)
        # Stamp specific device address into all actions if selected
        if device_addr:
            for btn in buttons:
                for action in btn.get("actions", []):
                    if action.get("device_type") in (name, "") or action.get("device_address") == "":
                        action["device_address"] = device_addr
        self._panels[current]["buttons"] = buttons
        save_panels(self._panels)
        if self._controller:
            self._controller.reload_panels()
        for idx in range(NUM_BUTTONS):
            self._btn_widgets[current][idx].setText(self._btn_label(current, idx))

    # ── Import / Export ────────────────────────────────────────────────────────

    def _export_preset(self) -> None:
        path, _f = QFileDialog.getSaveFileName(
            self, str(_("panel_tab.export_dialog_title")), os.path.expanduser("~"),
            "YAML Files (*.yml *.yaml)"
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                yaml.dump({"panels": self._panels}, f,
                          allow_unicode=True, default_flow_style=False)
            QMessageBox.information(self, str(_("panel_tab.export_title")),
                                    str(_("panel_tab.export_success")).format(path=path))
        except Exception as e:
            QMessageBox.critical(self, str(_("panel_tab.export_failed")), str(e))

    def _import_preset(self) -> None:
        path, _f = QFileDialog.getOpenFileName(
            self, str(_("panel_tab.import_dialog_title")), os.path.expanduser("~"),
            "YAML Files (*.yml *.yaml)"
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            panels = data.get("panels", [])
            if not isinstance(panels, list) or not panels:
                raise ValueError(str(_("panel_tab.no_valid_panels")))
            self._panels = panels
            save_panels(self._panels)
            if self._controller:
                self._controller.reload_panels()
            for p in range(NUM_PANELS):
                for idx in range(NUM_BUTTONS):
                    self._btn_widgets[p][idx].setText(self._btn_label(p, idx))
            QMessageBox.information(self, str(_("panel_tab.import_title")),
                                    str(_("panel_tab.import_success")))
        except Exception as e:
            QMessageBox.critical(self, str(_("panel_tab.import_failed")), str(e))

    # ── Controller binding ────────────────────────────────────────────────────

    def bind_controller(self, controller) -> None:
        self._controller = controller
        self._refresh_device_combo()
        self.refresh()

    def refresh_preset_devices(self) -> None:
        """Call when connected devices change to update the device selector."""
        self._refresh_device_combo()

    def refresh(self) -> None:
        """Reload panels from disk and redraw all button labels."""
        if self._controller:
            self._controller.reload_panels()
            self._panels = self._controller.panels
        else:
            self._panels = load_panels()
        for p in range(NUM_PANELS):
            for idx in range(NUM_BUTTONS):
                self._btn_widgets[p][idx].setText(self._btn_label(p, idx))

    # ── Button click → edit dialog ────────────────────────────────────────────

    def _on_btn_clicked(self, panel: int, btn_idx: int) -> None:
        devices = self._controller.devices if self._controller else {}
        existing = get_button(self._panels, panel, btn_idx)

        dlg = ButtonActionDialog(panel, btn_idx, existing, devices, parent=self)
        if dlg.exec() == ButtonActionDialog.Accepted:
            new_btn = dlg.result_button()
            set_button(self._panels, panel, btn_idx, new_btn)
            save_panels(self._panels)
            if self._controller:
                self._controller.reload_panels()
            # Refresh label
            self._btn_widgets[panel][btn_idx].setText(self._btn_label(panel, btn_idx))

    # ── Label helper ──────────────────────────────────────────────────────────

    def _btn_label(self, panel: int, idx: int) -> str:
        btn = get_button(self._panels, panel, idx)
        if btn and btn.get("label"):
            return btn["label"]
        r, c = divmod(idx, _COLS)
        return f"R{r+1}C{c+1}"

    def update_ui_texts(self) -> None:
        self._hint_lbl.setText(str(_("panel_tab.hint")))
        self._preset_lbl.setText(str(_("panel_tab.preset_label")))
        self._target_lbl.setText(str(_("panel_tab.target_label")))
        self._device_lbl.setText(str(_("panel_tab.device_label")))
        self._preset_apply_btn.setText(str(_("panel_tab.preset_apply_btn")))
        self._import_btn.setText(str(_("panel_tab.import_btn")))
        self._export_btn.setText(str(_("panel_tab.export_btn")))
        if self._device_combo.count() > 0:
            self._device_combo.setItemText(0, str(_("panel_tab.auto_device")))
        for p in range(NUM_PANELS):
            self._tab_widget.setTabText(p, str(_("panel_tab.page_label")).format(n=p + 1))
