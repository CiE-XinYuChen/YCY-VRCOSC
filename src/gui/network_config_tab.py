"""network_config_tab.py — YokoNex server connection + multi-device management + OSC server."""
from __future__ import annotations

import asyncio
import functools
import logging

from PySide6.QtCore import Qt, QLocale
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox,
    QPushButton, QSpinBox, QVBoxLayout, QWidget,
)
from pythonosc import dispatcher, osc_server, udp_client

from config import save_settings
from fusion_controller import FusionController
from i18n import LANGUAGES, get_current_language, language_signals, set_language, translate as _
from yokonex_client import YokoNexClient

log = logging.getLogger(__name__)
_EN = QLocale(QLocale.Language.English, QLocale.Country.UnitedStates)

_DEVICE_TYPES = ["toy", "estim"]


def _spawn(coro):
    """Schedule a coroutine as a task from any thread (OSC callbacks run in a non-loop thread)."""
    loop = asyncio.get_event_loop()
    loop.call_soon_threadsafe(lambda: loop.create_task(coro))


class NetworkConfigTab(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window

        self._yokonex: YokoNexClient | None = None
        self._osc_transport  = None
        self._osc_protocol   = None
        self._osc_dispatcher = dispatcher.Dispatcher()
        self._panel_handlers: dict = {}
        self._osc_interaction_handlers: dict = {}
        self._osc_signal_connected = False
        self._scan_task: asyncio.Task | None = None

        # (address, name, type) of scanned devices waiting to be connected
        self._scanned: list[dict] = []

        self._build_ui()
        language_signals.language_changed.connect(self.update_ui_texts)

    # ── UI ─────────────────────────────────────────────────────────────────────

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

        self.relay_check = QCheckBox(str(_("network_tab.relay_mode")))
        self.relay_check.setChecked(self.main_window.settings.get("relay_mode", False))
        srv_form.addRow(self.relay_check)

        self.relay_token_edit = QLineEdit()
        self.relay_token_edit.setLocale(_EN)
        self.relay_token_edit.setPlaceholderText("CLIENT_TOKEN")
        self.relay_token_edit.setText(self.main_window.settings.get("relay_token", ""))
        self.relay_token_label = QLabel(str(_("network_tab.relay_token")) + ":")
        srv_form.addRow(self.relay_token_label, self.relay_token_edit)

        relay_agent_row = QHBoxLayout()
        self.relay_agent_edit = QLineEdit()
        self.relay_agent_edit.setLocale(_EN)
        self.relay_agent_edit.setPlaceholderText("home-pc")
        self.relay_agent_edit.setText(self.main_window.settings.get("relay_agent_id", ""))
        self.relay_agent_label = QLabel(str(_("network_tab.relay_agent")) + ":")
        self.relay_list_btn = QPushButton(str(_("network_tab.relay_list_agents")))
        relay_agent_row.addWidget(self.relay_agent_edit)
        relay_agent_row.addWidget(self.relay_list_btn)
        srv_form.addRow(self.relay_agent_label, relay_agent_row)

        self._set_relay_fields_visible(self.relay_check.isChecked())

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
        dev_layout = QVBoxLayout()

        # Scan row
        scan_row = QHBoxLayout()
        self.scan_btn = QPushButton(str(_("network_tab.scan")))
        self.scan_combo = QComboBox()
        self.scan_combo.setLocale(_EN)
        self.scan_combo.setPlaceholderText(str(_("network_tab.no_devices")))
        self.scan_combo.setMinimumWidth(200)
        scan_row.addWidget(self.scan_btn)
        scan_row.addWidget(self.scan_combo, 1)
        dev_layout.addLayout(scan_row)

        # Device type + add row
        add_row = QHBoxLayout()
        self.dtype_combo = QComboBox()
        self.dtype_combo.setLocale(_EN)
        for t in _DEVICE_TYPES:
            self.dtype_combo.addItem(t)
        self.add_device_btn = QPushButton(str(_("network_tab.connect_device_btn")))
        self.add_device_btn.setStyleSheet("background-color: #2d862d; color: white;")
        add_row.addWidget(QLabel(str(_("network_tab.type_label"))))
        add_row.addWidget(self.dtype_combo)
        add_row.addWidget(self.add_device_btn)
        add_row.addStretch()
        dev_layout.addLayout(add_row)

        # Connected devices list
        dev_layout.addWidget(QLabel(str(_("network_tab.connected_devices"))))
        self.device_list = QListWidget()
        self.device_list.setMinimumHeight(90)
        dev_layout.addWidget(self.device_list)

        remove_row = QHBoxLayout()
        self.remove_device_btn = QPushButton(str(_("network_tab.disconnect_selected")))
        self.remove_device_btn.setEnabled(False)
        remove_row.addWidget(self.remove_device_btn)
        remove_row.addStretch()
        dev_layout.addLayout(remove_row)

        self.device_group.setLayout(dev_layout)
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

        # Signals
        self.connect_btn.clicked.connect(self._on_connect_clicked)
        self.scan_btn.clicked.connect(self._on_scan_clicked)
        self.add_device_btn.clicked.connect(self._on_add_device_clicked)
        self.remove_device_btn.clicked.connect(self._on_remove_device_clicked)
        self.device_list.itemSelectionChanged.connect(self._on_selection_changed)
        self.device_list.currentItemChanged.connect(self._on_selection_changed)
        self.relay_check.stateChanged.connect(self._on_relay_toggled)
        self.relay_list_btn.clicked.connect(self._on_list_agents_clicked)
        self.lang_combo.currentTextChanged.connect(self._on_language_changed)
        self.host_edit.textChanged.connect(self._save_settings)
        self.yokonex_port_spin.valueChanged.connect(self._save_settings)
        self.osc_port_spin.valueChanged.connect(self._save_settings)
        self.relay_token_edit.textChanged.connect(self._save_settings)
        self.relay_agent_edit.textChanged.connect(self._save_settings)

    # ── Button handlers ────────────────────────────────────────────────────────

    def _on_connect_clicked(self):
        _spawn(self._connect_to_yokonex())

    def _on_scan_clicked(self):
        if self._scan_task and not self._scan_task.done():
            return
        _spawn(self._do_scan())

    def _on_add_device_clicked(self):
        _spawn(self._add_device())

    def _on_remove_device_clicked(self):
        _spawn(self._remove_device())

    def _on_selection_changed(self, *_args):
        has = (len(self.device_list.selectedItems()) > 0
               or self.device_list.currentItem() is not None)
        self.remove_device_btn.setEnabled(has)

    def _on_relay_toggled(self, state: int):
        self._set_relay_fields_visible(bool(state))
        self._save_settings()

    def _on_list_agents_clicked(self):
        _spawn(self._list_and_pick_agent())

    # ── Async operations ───────────────────────────────────────────────────────

    async def _connect_to_yokonex(self):
        host = self.host_edit.text().strip() or "127.0.0.1"
        port = self.yokonex_port_spin.value()
        url  = f"ws://{host}:{port}"

        # Tear down any existing connection before reconnecting
        if self._yokonex is not None:
            try:
                await self._yokonex.close()
            except Exception:
                pass
            self._yokonex = None
            self._set_yokonex_status(False)

        old_ctrl = getattr(self.main_window, "controller", None)
        if old_ctrl is not None:
            try:
                old_ctrl.stop()
            except Exception:
                pass
            self.main_window.controller = None

        self.connect_btn.setEnabled(False)
        self.connect_btn.setText(str(_("network_tab.connecting")))

        relay_mode = self.relay_check.isChecked()
        client = YokoNexClient(url)

        if relay_mode:
            token    = self.relay_token_edit.text().strip()
            agent_id = self.relay_agent_edit.text().strip()
            if not token or not agent_id:
                QMessageBox.warning(self, "Error",
                                    "Cloud relay mode requires both Token and Agent ID.")
                self.connect_btn.setEnabled(True)
                self.connect_btn.setText(str(_("network_tab.connect")))
                return
            ok = await client.connect_relay(token, agent_id)
        else:
            ok = await client.connect()

        if not ok:
            self.connect_btn.setEnabled(True)
            self.connect_btn.setText(str(_("network_tab.connect")))
            self._set_yokonex_status(False)
            QMessageBox.warning(self, "Error",
                                f"Cannot connect to {'relay' if relay_mode else 'YokoNex'} at {url}")
            return

        self._yokonex = client
        self._yokonex.add_event_handler(self._on_yokonex_event)
        self._set_yokonex_status(True)
        self.connect_btn.setText(str(_("network_tab.connected")))

        # Create FusionController
        osc_out    = udp_client.SimpleUDPClient("127.0.0.1", 9000)
        controller = FusionController(client, osc_out, self.main_window)
        self.main_window.controller = controller

        # Bind panel editor
        if hasattr(self.main_window, "panel_editor_tab"):
            self.main_window.panel_editor_tab.bind_controller(controller)

        # Bind controller settings tab (for device callbacks)
        if hasattr(self.main_window, "controller_settings_tab"):
            self.main_window.controller_settings_tab.bind_controller(controller)

        # Bind ChatBox tab
        if hasattr(self.main_window, "chatbox_tab"):
            self.main_window.chatbox_tab.bind_controller(controller)

        # Start OSC server
        await self._start_osc_server()
        self._register_panel_osc(controller)

        self.device_group.setEnabled(True)

        if not self._osc_signal_connected:
            if hasattr(self.main_window, "osc_parameters_tab"):
                self.main_window.osc_parameters_tab.addresses_updated.connect(
                    lambda: self._update_osc_interaction(controller)
                )
            self._osc_signal_connected = True
        self._update_osc_interaction(controller)

        # Populate scan combo with devices already connected to the WS server
        await self._load_connected_devices()

    async def _list_and_pick_agent(self):
        host  = self.host_edit.text().strip() or "127.0.0.1"
        port  = self.yokonex_port_spin.value()
        token = self.relay_token_edit.text().strip()
        url   = f"ws://{host}:{port}"

        if not token:
            QMessageBox.warning(self, "Error", "Enter the Token first.")
            return

        self.relay_list_btn.setEnabled(False)
        try:
            import websockets as _ws
            import json as _json
            async with _ws.connect(url, open_timeout=5) as ws:
                await ws.send(_json.dumps({"type": "client_hello", "token": token}))
                hello = _json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
                if not hello.get("ok"):
                    QMessageBox.warning(self, "Error", f"Auth failed: {hello.get('message')}")
                    return
                await ws.send(_json.dumps({"id": 1, "type": "list_agents"}))
                resp = _json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
                agents = resp.get("agents", [])

            if not agents:
                QMessageBox.information(self, "Agents", "No agents online.")
                return

            from PySide6.QtWidgets import QInputDialog
            items = [f"{a['id']}  ({a['clients']} client(s))" for a in agents]
            item, ok = QInputDialog.getItem(self, "Select Agent", "Agent:", items, 0, False)
            if ok and item:
                self.relay_agent_edit.setText(agents[items.index(item)]["id"])
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed: {e}")
        finally:
            self.relay_list_btn.setEnabled(True)

    async def _load_connected_devices(self):
        """Fetch devices already connected on the WS server and populate the scan combo."""
        if not self._yokonex:
            return
        try:
            devices = await self._yokonex.list_devices()
        except Exception as e:
            log.warning("list_devices failed: %s", e)
            return
        if not devices:
            return
        self._scanned = devices
        self.scan_combo.clear()
        for d in devices:
            label = f"{d.get('name', 'Unknown')} ({d['address']})"
            idx = self.scan_combo.count()
            self.scan_combo.addItem(label, d["address"])
            # Mark as already-connected + store type hint
            dtype = d.get("type") or d.get("device_type", "")
            self.scan_combo.setItemData(idx, {"connected": True, "type": dtype}, Qt.UserRole + 1)
        if self.scan_combo.count() > 0:
            # Pre-select dtype from first device if known
            first_extra = self.scan_combo.itemData(0, Qt.UserRole + 1) or {}
            dtype = first_extra.get("type", "")
            if dtype in _DEVICE_TYPES:
                self.dtype_combo.setCurrentText(dtype)
        log.info("Loaded %d existing device(s) from server", len(devices))

    async def _do_scan(self):
        self.scan_btn.setEnabled(False)
        self.scan_btn.setText(str(_("network_tab.scanning")))
        try:
            devices = await self._yokonex.scan(duration=5.0)
            self._scanned = devices
            self.scan_combo.clear()
            for d in devices:
                label = f"{d.get('name', 'Unknown')} ({d['address']})"
                idx = self.scan_combo.count()
                self.scan_combo.addItem(label, d["address"])
                self.scan_combo.setItemData(idx, {"connected": False, "type": ""}, Qt.UserRole + 1)
            if not devices:
                QMessageBox.information(self, "Scan", str(_("network_tab.no_devices_found")))
        except Exception as e:
            log.error("Scan error: %s", e)
        finally:
            self.scan_btn.setEnabled(True)
            self.scan_btn.setText(str(_("network_tab.scan")))

    async def _add_device(self):
        idx = self.scan_combo.currentIndex()
        if idx < 0:
            QMessageBox.warning(self, "Error", "Scan for devices first.")
            return
        address = self.scan_combo.currentData(Qt.UserRole)
        name    = self.scan_combo.currentText().split(" (")[0]
        dtype   = self.dtype_combo.currentText()
        extra   = self.scan_combo.itemData(idx, Qt.UserRole + 1) or {}
        already_connected = extra.get("connected", False)
        # Use server-provided type if available and user hasn't explicitly overridden
        if extra.get("type") in _DEVICE_TYPES:
            dtype = extra["type"]

        # Prevent duplicate entries
        ctrl = self.main_window.controller
        if ctrl and address in ctrl.devices:
            QMessageBox.information(self, str(_("network_tab.already_added_title")),
                                    str(_("network_tab.already_added_msg")).format(name=name))
            return

        self.add_device_btn.setEnabled(False)
        try:
            if not already_connected:
                result = await self._yokonex.connect_device(address, name, dtype)
                if not result.get("ok"):
                    QMessageBox.warning(self, str(_("network_tab.error_title")),
                                        str(_("network_tab.connect_failed")).format(
                                            error=result.get("error", "")))
                    self.add_device_btn.setEnabled(True)
                    return
        except Exception as e:
            log.error("connect_device error: %s", e)
            self.add_device_btn.setEnabled(True)
            return

        # Register with controller
        if ctrl:
            ctrl.register_device(address, name, dtype)

        # Notify OSC parameters tab of updated device list
        if hasattr(self.main_window, "osc_parameters_tab") and ctrl:
            self.main_window.osc_parameters_tab.set_devices(ctrl.devices)

        # Refresh panel editor device selector
        if hasattr(self.main_window, "panel_editor_tab"):
            self.main_window.panel_editor_tab.refresh_preset_devices()

        # Add to list widget
        item = QListWidgetItem(f"● {name}  ({address})  [{dtype}]")
        item.setData(Qt.UserRole, address)
        self.device_list.addItem(item)

        # Refresh panel editor button labels (devices changed)
        if hasattr(self.main_window, "panel_editor_tab"):
            self.main_window.panel_editor_tab.refresh()

        log.info("Connected device %s (%s) type=%s", name, address, dtype)
        self.add_device_btn.setEnabled(True)

    async def _remove_device(self):
        selected = self.device_list.selectedItems()
        if not selected:
            return
        item = selected[0]
        address = item.data(Qt.UserRole)

        try:
            await self._yokonex.disconnect_device(address)
        except Exception as e:
            log.error("disconnect_device error: %s", e)

        ctrl = self.main_window.controller
        if ctrl:
            ctrl.unregister_device(address)

        self.device_list.takeItem(self.device_list.row(item))
        # Let _on_selection_changed handle button state based on remaining items

        # Notify OSC parameters tab
        if hasattr(self.main_window, "osc_parameters_tab") and ctrl:
            self.main_window.osc_parameters_tab.set_devices(ctrl.devices)

        if hasattr(self.main_window, "panel_editor_tab"):
            self.main_window.panel_editor_tab.refresh()
            self.main_window.panel_editor_tab.refresh_preset_devices()

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

    def _register_panel_osc(self, controller):
        if self._panel_handlers:
            return
        for addr in (
            "/avatar/parameters/SoundPad/Button/*",
            "/avatar/parameters/SoundPad/Page",
        ):
            handler = functools.partial(self._osc_panel_task, controller=controller)
            self._osc_dispatcher.map(addr, handler)
            self._panel_handlers[addr] = handler

    def _update_osc_interaction(self, controller):
        """Rebuild OSC interaction address → handler mappings."""
        # Unmap previous interaction handlers
        for addr, handler in list(self._osc_interaction_handlers.items()):
            self._osc_dispatcher.unmap(addr, handler)
        self._osc_interaction_handlers.clear()

        if not hasattr(self.main_window, "osc_parameters_tab"):
            return
        for entry in self.main_window.osc_parameters_tab.get_addresses():
            addr = entry.get("address", "")
            if not addr:
                continue
            handler = functools.partial(
                self._osc_interaction_task, controller=controller, entry=entry
            )
            self._osc_dispatcher.map(addr, handler)
            self._osc_interaction_handlers[addr] = handler
        log.info("OSC interaction mappings updated (%d entries)",
                 len(self._osc_interaction_handlers))

    def _osc_panel_task(self, address, *args, controller):
        _spawn(controller.handle_osc_panel(address, *args))

    def _osc_interaction_task(self, address, *args, controller, entry):
        if not args:
            return
        value = float(args[0])
        _spawn(controller.handle_osc_interaction(address, value, entry))

    # ── YokoNex event handler ──────────────────────────────────────────────────

    async def _on_yokonex_event(self, data: dict):
        event   = data.get("event")
        payload = data.get("data", {})
        addr    = payload.get("address", "")

        # Route device state events to fusion controller + controller settings tab
        if event in ("channel_status", "battery", "motor_status") and addr:
            ctrl = self.main_window.controller
            if ctrl:
                ctrl.update_device_state(addr, event, payload)
            if hasattr(self.main_window, "controller_settings_tab"):
                self.main_window.controller_settings_tab.on_device_event(addr, data)

        if event == "battery":
            pct = payload.get("battery") or payload.get("level", "?")
            log.info("Battery %s: %s%%", addr, pct)
        elif event == "disconnected":
            log.warning("Device disconnected: %s", addr)
            ctrl = self.main_window.controller
            if ctrl:
                ctrl.unregister_device(addr)
                if hasattr(self.main_window, "osc_parameters_tab"):
                    self.main_window.osc_parameters_tab.set_devices(ctrl.devices)
            for i in range(self.device_list.count()):
                item = self.device_list.item(i)
                if item and item.data(Qt.UserRole) == addr:
                    self.device_list.takeItem(i)
                    break

    # ── Status helpers ─────────────────────────────────────────────────────────

    def _set_yokonex_status(self, online: bool):
        if online:
            self.yokonex_status_label.setText(str(_("network_tab.connected")))
            self._set_label_style(self.yokonex_status_label, "green")
        else:
            self.yokonex_status_label.setText(str(_("network_tab.disconnected")))
            self._set_label_style(self.yokonex_status_label, "red")

    @staticmethod
    def _set_label_style(label, color):
        label.setStyleSheet(
            f"QLabel {{ background-color: {color}; color: white; "
            f"border-radius: 5px; padding: 5px; }}"
        )
        label.adjustSize()

    def _save_settings(self):
        self.main_window.settings["yokonex_host"]   = self.host_edit.text().strip()
        self.main_window.settings["yokonex_port"]   = self.yokonex_port_spin.value()
        self.main_window.settings["osc_port"]       = self.osc_port_spin.value()
        self.main_window.settings["relay_mode"]     = self.relay_check.isChecked()
        self.main_window.settings["relay_token"]    = self.relay_token_edit.text().strip()
        self.main_window.settings["relay_agent_id"] = self.relay_agent_edit.text().strip()
        save_settings(self.main_window.settings)

    def _set_relay_fields_visible(self, visible: bool):
        for w in (self.relay_token_label, self.relay_token_edit,
                  self.relay_agent_label, self.relay_agent_edit,
                  self.relay_list_btn):
            w.setVisible(visible)

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
        self.add_device_btn.setText(str(_("network_tab.connect_device_btn")))
        self.remove_device_btn.setText(str(_("network_tab.disconnect_selected")))
        self.lang_label.setText(str(_("main.settings.language")) + ":")
        self.scan_combo.setPlaceholderText(str(_("network_tab.no_devices")))

    # ── Legacy compat (OSC parameters tab still calls this) ───────────────────
    def get_osc_addresses(self) -> list:
        return []
