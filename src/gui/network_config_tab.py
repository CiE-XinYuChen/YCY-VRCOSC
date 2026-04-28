"""network_config_tab.py - YokoNex server connection + BLE device management + OSC server."""
from __future__ import annotations

import asyncio
import functools
import logging

from PySide6.QtCore import Qt, QLocale
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPushButton, QSpinBox, QVBoxLayout, QWidget,
)
from pythonosc import dispatcher, osc_server, udp_client

from config import get_active_ip_addresses, save_settings
from i18n import LANGUAGES, get_current_language, language_signals, set_language, translate as _
from toy_controller import ToyController
from yokonex_client import YokoNexClient

log = logging.getLogger(__name__)
_EN = QLocale(QLocale.Language.English, QLocale.Country.UnitedStates)


class NetworkConfigTab(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window

        # Runtime state
        self._yokonex: YokoNexClient | None = None
        self._osc_transport = None
        self._osc_protocol  = None
        self._osc_dispatcher = dispatcher.Dispatcher()
        self._osc_handlers: dict = {}
        self._panel_handlers: dict = {}
        self._osc_signal_connected = False
        self._scan_task: asyncio.Task | None = None

        self._build_ui()
        self._connect_signals()
        language_signals.language_changed.connect(self.update_ui_texts)

    # ── UI construction ────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        self.setLayout(root)

        # ── Server group ──────────────────────────────────────────────────────
        self.server_group = QGroupBox(str(_("network_tab.server_group")))
        srv_form = QFormLayout()

        self.host_edit = QLineEdit()
        self.host_edit.setLocale(_EN)
        self.host_edit.setText(self.main_window.settings.get("yokonex_host", "127.0.0.1"))
        srv_form.addRow(str(_("network_tab.yokonex_host")) + ":", self.host_edit)

        self.yokonex_port_spin = QSpinBox()
        self.yokonex_port_spin.setLocale(_EN)
        self.yokonex_port_spin.setRange(1024, 65535)
        self.yokonex_port_spin.setValue(self.main_window.settings.get("yokonex_port", 8765))
        srv_form.addRow(str(_("network_tab.yokonex_port")) + ":", self.yokonex_port_spin)

        self.osc_port_spin = QSpinBox()
        self.osc_port_spin.setLocale(_EN)
        self.osc_port_spin.setRange(1024, 65535)
        self.osc_port_spin.setValue(self.main_window.settings.get("osc_port", 9001))
        srv_form.addRow(str(_("network_tab.osc_port")) + ":", self.osc_port_spin)

        self.connect_btn = QPushButton(str(_("network_tab.connect")))
        self.connect_btn.setStyleSheet("background-color: green; color: white;")
        srv_form.addRow(self.connect_btn)

        self.yokonex_status_label = QLabel(str(_("network_tab.disconnected")))
        self.yokonex_status_label.setAlignment(Qt.AlignCenter)
        srv_form.addRow(str(_("network_tab.status")) + ":", self.yokonex_status_label)
        self._set_label_style(self.yokonex_status_label, "red")

        self.server_group.setLayout(srv_form)
        root.addWidget(self.server_group)

        # ── Device group ──────────────────────────────────────────────────────
        self.device_group = QGroupBox(str(_("network_tab.device_group")))
        self.device_group.setEnabled(False)
        dev_form = QFormLayout()

        self.scan_btn = QPushButton(str(_("network_tab.scan")))
        dev_form.addRow(self.scan_btn)

        self.device_combo = QComboBox()
        self.device_combo.setLocale(_EN)
        self.device_combo.setPlaceholderText(str(_("network_tab.no_devices")))
        dev_form.addRow(str(_("network_tab.device")) + ":", self.device_combo)

        dev_btn_row = QHBoxLayout()
        self.connect_device_btn = QPushButton(str(_("network_tab.connect_device")))
        self.connect_device_btn.setStyleSheet("background-color: green; color: white;")
        self.disconnect_device_btn = QPushButton(str(_("network_tab.disconnect_device")))
        self.disconnect_device_btn.setEnabled(False)
        dev_btn_row.addWidget(self.connect_device_btn)
        dev_btn_row.addWidget(self.disconnect_device_btn)
        dev_form.addRow(dev_btn_row)

        self.device_status_label = QLabel(str(_("network_tab.device_offline")))
        self.device_status_label.setAlignment(Qt.AlignCenter)
        dev_form.addRow(str(_("network_tab.device_status")) + ":", self.device_status_label)
        self._set_label_style(self.device_status_label, "red")

        self.device_group.setLayout(dev_form)
        root.addWidget(self.device_group)

        # ── Language ──────────────────────────────────────────────────────────
        lang_row = QHBoxLayout()
        self.lang_label = QLabel(str(_("main.settings.language")) + ":")
        self.lang_combo = QComboBox()
        self.lang_combo.setLocale(_EN)
        for code, name in LANGUAGES.items():
            self.lang_combo.addItem(name, code)
        current = self.main_window.settings.get("language") or get_current_language()
        for i in range(self.lang_combo.count()):
            if self.lang_combo.itemData(i) == current:
                self.lang_combo.setCurrentIndex(i)
                break
        lang_row.addWidget(self.lang_label)
        lang_row.addWidget(self.lang_combo)
        lang_row.addStretch()
        root.addLayout(lang_row)
        root.addStretch()

    def _connect_signals(self):
        self.connect_btn.clicked.connect(self._on_connect_clicked)
        self.scan_btn.clicked.connect(self._on_scan_clicked)
        self.connect_device_btn.clicked.connect(self._on_connect_device_clicked)
        self.disconnect_device_btn.clicked.connect(self._on_disconnect_device_clicked)
        self.lang_combo.currentTextChanged.connect(self._on_language_changed)
        self.host_edit.textChanged.connect(self._save_settings)
        self.yokonex_port_spin.valueChanged.connect(self._save_settings)
        self.osc_port_spin.valueChanged.connect(self._save_settings)

    # ── Button handlers ────────────────────────────────────────────────────────

    def _on_connect_clicked(self):
        asyncio.create_task(self._connect_to_yokonex())

    def _on_scan_clicked(self):
        if self._scan_task and not self._scan_task.done():
            return
        self._scan_task = asyncio.create_task(self._do_scan())

    def _on_connect_device_clicked(self):
        asyncio.create_task(self._connect_device())

    def _on_disconnect_device_clicked(self):
        asyncio.create_task(self._disconnect_device())

    # ── Async operations ───────────────────────────────────────────────────────

    async def _connect_to_yokonex(self):
        host = self.host_edit.text().strip() or "127.0.0.1"
        port = self.yokonex_port_spin.value()
        url  = f"ws://{host}:{port}"

        self.connect_btn.setEnabled(False)
        self.connect_btn.setText(str(_("network_tab.connecting")))

        client = YokoNexClient(url)
        ok = await client.connect()

        if not ok:
            self.connect_btn.setEnabled(True)
            self.connect_btn.setText(str(_("network_tab.connect")))
            self._set_yokonex_status(False)
            QMessageBox.warning(self, "Error",
                                f"Cannot connect to YokoNex at {url}\n"
                                "Make sure 'yokonex server' is running.")
            return

        self._yokonex = client
        self._yokonex.add_event_handler(self._on_yokonex_event)
        self._set_yokonex_status(True)
        self.connect_btn.setText(str(_("network_tab.connected")))

        # Start OSC server
        await self._start_osc_server()

        # Enable device group
        self.device_group.setEnabled(True)

        # Connect OSC update signal
        if not self._osc_signal_connected:
            self.main_window.osc_parameters_tab.addresses_updated.connect(
                self._update_osc_mappings
            )
            self._osc_signal_connected = True

    async def _do_scan(self):
        self.scan_btn.setEnabled(False)
        self.scan_btn.setText(str(_("network_tab.scanning")))
        try:
            devices = await self._yokonex.scan(duration=5.0)
            self.device_combo.clear()
            for d in devices:
                label = f"{d.get('name', 'Unknown')} ({d['address']})"
                self.device_combo.addItem(label, d["address"])
            if not devices:
                QMessageBox.information(self, "Scan", str(_("network_tab.no_devices_found")))
        except Exception as e:
            log.error("Scan error: %s", e)
        finally:
            self.scan_btn.setEnabled(True)
            self.scan_btn.setText(str(_("network_tab.scan")))

    async def _connect_device(self):
        if self.device_combo.currentIndex() < 0:
            return
        address = self.device_combo.currentData()
        name    = self.device_combo.currentText().split(" (")[0]

        self.connect_device_btn.setEnabled(False)
        try:
            result = await self._yokonex.connect_device(address, name, "toy")
        except Exception as e:
            log.error("connect_device error: %s", e)
            self.connect_device_btn.setEnabled(True)
            return

        if not result.get("ok"):
            QMessageBox.warning(self, "Error",
                                f"Device connect failed: {result.get('error')}")
            self.connect_device_btn.setEnabled(True)
            return

        # Create ToyController
        osc_out = udp_client.SimpleUDPClient("127.0.0.1", 9000)
        controller = ToyController(self._yokonex, osc_out, address, self.main_window)
        self.main_window.controller = controller
        self._set_device_status(True)
        self.disconnect_device_btn.setEnabled(True)
        self.main_window.controller_settings_tab.bind_controller(controller)
        self._update_osc_mappings()
        log.info("ToyController created for %s", address)

    async def _disconnect_device(self):
        ctrl = self.main_window.controller
        if ctrl is None:
            return
        self.disconnect_device_btn.setEnabled(False)
        try:
            await self._yokonex.disconnect_device(ctrl.device_address)
            ctrl.cancel_tasks()
        except Exception as e:
            log.error("disconnect_device error: %s", e)
        finally:
            self.main_window.controller = None
            self._set_device_status(False)
            self.connect_device_btn.setEnabled(True)
            if hasattr(self.main_window, "controller_settings_tab"):
                self.main_window.controller_settings_tab.reset_display()

    async def _start_osc_server(self):
        if self._osc_transport is not None:
            return
        osc_port = self.osc_port_spin.value()
        try:
            srv = osc_server.AsyncIOOSCUDPServer(
                ("0.0.0.0", osc_port), self._osc_dispatcher, asyncio.get_event_loop()
            )
            self._osc_transport, self._osc_protocol = await srv.create_serve_endpoint()
            log.info("OSC server listening on port %d", osc_port)
        except Exception as e:
            log.error("Failed to start OSC server: %s", e)

    # ── OSC dispatcher management ──────────────────────────────────────────────

    def _update_osc_mappings(self, *_):
        ctrl = self.main_window.controller
        if ctrl is None:
            return
        asyncio.create_task(self._apply_osc_mappings(ctrl))

    async def _apply_osc_mappings(self, ctrl):
        # Clear previous interaction mappings
        for addr, handler in self._osc_handlers.items():
            self._osc_dispatcher.unmap(addr, handler)
        self._osc_handlers.clear()

        # Register custom interaction addresses
        for entry in self.main_window.get_osc_addresses():
            address = entry["address"]
            channels = entry["channels"]
            ranges   = entry.get("mapping_ranges",
                                  {m: {"min": 0, "max": 100} for m in ("A", "B", "C")})
            motor_list = [m for m in ("A", "B", "C") if channels.get(m)]
            if not motor_list:
                continue
            handler = functools.partial(
                self._osc_interaction_task,
                controller=ctrl,
                motors=motor_list,
                mapping_ranges=ranges,
            )
            self._osc_dispatcher.map(address, handler)
            self._osc_handlers[address] = handler

        log.info("OSC interaction mappings updated (%d addresses)", len(self._osc_handlers))

        # Register panel control addresses (once)
        if not self._panel_handlers:
            for addr in (
                "/avatar/parameters/SoundPad/Button/*",
                "/avatar/parameters/SoundPad/Volume",
                "/avatar/parameters/SoundPad/Page",
                "/avatar/parameters/SoundPad/PanelControl",
            ):
                handler = functools.partial(self._osc_panel_task, controller=ctrl)
                self._osc_dispatcher.map(addr, handler)
                self._panel_handlers[addr] = handler

    def _osc_panel_task(self, address, *args, controller):
        asyncio.create_task(controller.handle_osc_panel(address, *args))

    def _osc_interaction_task(self, address, *args, controller, motors, mapping_ranges):
        if not args:
            return
        value = float(args[0])
        asyncio.create_task(
            controller.handle_osc_interaction(address, value, motors, mapping_ranges)
        )

    # ── YokoNex event handler ──────────────────────────────────────────────────

    async def _on_yokonex_event(self, data: dict):
        event = data.get("event")
        if event == "battery":
            pct = data.get("data", {}).get("battery", "?")
            log.info("Battery: %s%%", pct)

    # ── Status helpers ─────────────────────────────────────────────────────────

    def _set_yokonex_status(self, online: bool):
        if online:
            self.yokonex_status_label.setText(str(_("network_tab.connected")))
            self._set_label_style(self.yokonex_status_label, "green")
        else:
            self.yokonex_status_label.setText(str(_("network_tab.disconnected")))
            self._set_label_style(self.yokonex_status_label, "red")

    def _set_device_status(self, online: bool):
        self.main_window.app_status_online = online
        if online:
            self.device_status_label.setText(str(_("network_tab.device_online")))
            self._set_label_style(self.device_status_label, "green")
            if hasattr(self.main_window, "controller_settings_tab"):
                self.main_window.controller_settings_tab.controller_group.setEnabled(True)
                self.main_window.controller_settings_tab.command_group.setEnabled(True)
        else:
            self.device_status_label.setText(str(_("network_tab.device_offline")))
            self._set_label_style(self.device_status_label, "red")
            if hasattr(self.main_window, "controller_settings_tab"):
                self.main_window.controller_settings_tab.controller_group.setEnabled(False)
                self.main_window.controller_settings_tab.command_group.setEnabled(False)

    @staticmethod
    def _set_label_style(label, color):
        label.setStyleSheet(
            f"QLabel {{ background-color: {color}; color: white; "
            f"border-radius: 5px; padding: 5px; }}"
        )
        label.adjustSize()

    # ── Settings persistence ───────────────────────────────────────────────────

    def _save_settings(self):
        self.main_window.settings["yokonex_host"] = self.host_edit.text().strip()
        self.main_window.settings["yokonex_port"] = self.yokonex_port_spin.value()
        self.main_window.settings["osc_port"]     = self.osc_port_spin.value()
        save_settings(self.main_window.settings)

    def _on_language_changed(self):
        code = self.lang_combo.currentData()
        if not code:
            return
        self.main_window.settings["language"] = code
        save_settings(self.main_window.settings)
        set_language(code)

    # ── i18n ──────────────────────────────────────────────────────────────────

    def update_ui_texts(self):
        self.server_group.setTitle(str(_("network_tab.server_group")))
        self.device_group.setTitle(str(_("network_tab.device_group")))
        self.connect_btn.setText(
            str(_("network_tab.connected")) if self._yokonex and self._yokonex.connected
            else str(_("network_tab.connect"))
        )
        self.scan_btn.setText(str(_("network_tab.scan")))
        self.connect_device_btn.setText(str(_("network_tab.connect_device")))
        self.disconnect_device_btn.setText(str(_("network_tab.disconnect_device")))
        self.lang_label.setText(str(_("main.settings.language")) + ":")
        self.device_combo.setPlaceholderText(str(_("network_tab.no_devices")))
