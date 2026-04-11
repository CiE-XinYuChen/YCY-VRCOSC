from PySide6.QtWidgets import (
    QWidget,
    QGroupBox,
    QFormLayout,
    QComboBox,
    QSpinBox,
    QLabel,
    QPushButton,
    QHBoxLayout,
    QVBoxLayout,
    QLineEdit,
    QCheckBox,
    QSizePolicy,
    QMessageBox,
)
from PySide6.QtCore import Qt, QLocale, QTimer
from PySide6.QtGui import QPixmap
import asyncio
import functools
import io
import logging

import qrcode
import requests
from pythonosc import dispatcher, osc_server, udp_client

from config import get_active_ip_addresses, save_settings
from dglab_controller import DGLabController
from i18n import (
    LANGUAGES,
    get_current_language,
    language_signals,
    set_language,
    translate as _,
)
from pydglab_ws import DGLabWSServer, FeedbackButton, RetCode, StrengthData

logger = logging.getLogger(__name__)


class NetworkConfigTab(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.original_qrcode_pixmap = None
        self.server_task = None
        self.osc_transport = None
        self.osc_protocol = None
        self.bluetooth_action_in_progress = False
        self.current_bluetooth_status = "ready"
        self._osc_signal_connected = False

        self.main_layout = QVBoxLayout(self)
        self.content_layout = QHBoxLayout()
        self.config_layout = QVBoxLayout()
        self.setLayout(self.main_layout)

        self.network_config_group = QGroupBox(str(_("network_tab.title")))
        self.form_layout = QFormLayout()

        self.ip_combobox = QComboBox()
        self.ip_combobox.setLocale(QLocale(QLocale.Language.English, QLocale.Country.UnitedStates))
        for interface, ip in get_active_ip_addresses().items():
            self.ip_combobox.addItem(f"{interface}: {ip}")
        self.form_layout.addRow(str(_("network_tab.interface")) + ":", self.ip_combobox)

        self.port_spinbox = QSpinBox()
        self.port_spinbox.setLocale(QLocale(QLocale.Language.English, QLocale.Country.UnitedStates))
        self.port_spinbox.setRange(1024, 65535)
        self.port_spinbox.setValue(self.main_window.settings["port"])
        self.form_layout.addRow(str(_("network_tab.websocket_port")) + ":", self.port_spinbox)

        self.osc_port_spinbox = QSpinBox()
        self.osc_port_spinbox.setLocale(QLocale(QLocale.Language.English, QLocale.Country.UnitedStates))
        self.osc_port_spinbox.setRange(1024, 65535)
        self.osc_port_spinbox.setValue(self.main_window.settings["osc_port"])
        self.form_layout.addRow(str(_("network_tab.osc_port")) + ":", self.osc_port_spinbox)

        self.remote_address_layout = QHBoxLayout()
        self.enable_remote_checkbox = QCheckBox(str(_("network_tab.enable_remote")))
        self.enable_remote_checkbox.setChecked(self.main_window.settings.get("enable_remote", False))
        self.enable_remote_checkbox.stateChanged.connect(self.on_remote_enabled_changed)

        self.remote_address_edit = QLineEdit()
        self.remote_address_edit.setLocale(QLocale(QLocale.Language.English, QLocale.Country.UnitedStates))
        self.remote_address_edit.setText(self.main_window.settings.get("remote_address", ""))
        self.remote_address_edit.setEnabled(self.enable_remote_checkbox.isChecked())
        self.remote_address_edit.setPlaceholderText(_("network_tab.please_enter_valid_ip"))
        self.remote_address_edit.textChanged.connect(self.on_remote_address_changed)

        self.get_public_ip_button = QPushButton(str(_("network_tab.get_public_ip")))
        self.get_public_ip_button.clicked.connect(self.get_public_ip)
        self.get_public_ip_button.setEnabled(self.enable_remote_checkbox.isChecked())

        self.remote_address_layout.addWidget(self.enable_remote_checkbox)
        self.remote_address_layout.addWidget(self.remote_address_edit)
        self.remote_address_layout.addWidget(self.get_public_ip_button)
        self.form_layout.addRow(str(_("network_tab.remote_address")) + ":", self.remote_address_layout)

        self.dispatcher = dispatcher.Dispatcher()
        self.osc_address_handlers = {}
        self.panel_control_handlers = {}

        self.connection_status_label = QLabel(str(_("network_tab.offline")))
        self.connection_status_label.setAlignment(Qt.AlignCenter)
        self.form_layout.addRow(str(_("network_tab.status")) + ":", self.connection_status_label)

        self.bluetooth_status_label = QLabel(str(_("network_tab.bluetooth_ready")))
        self.bluetooth_status_label.setAlignment(Qt.AlignCenter)
        self.form_layout.addRow(str(_("network_tab.bluetooth_status")) + ":", self.bluetooth_status_label)

        self.bluetooth_buttons_layout = QHBoxLayout()
        self.disconnect_bluetooth_button = QPushButton(str(_("network_tab.disconnect_bluetooth")))
        self.disconnect_bluetooth_button.clicked.connect(self.disconnect_bluetooth_button_clicked)
        self.reconnect_bluetooth_button = QPushButton(str(_("network_tab.reconnect_bluetooth")))
        self.reconnect_bluetooth_button.clicked.connect(self.reconnect_bluetooth_button_clicked)
        self.bluetooth_buttons_layout.addWidget(self.disconnect_bluetooth_button)
        self.bluetooth_buttons_layout.addWidget(self.reconnect_bluetooth_button)
        self.form_layout.addRow(self.bluetooth_buttons_layout)

        self.start_button = QPushButton(str(_("network_tab.connect")))
        self.start_button.setStyleSheet("background-color: green; color: white;")
        self.start_button.clicked.connect(self.start_server_button_clicked)
        self.form_layout.addRow(self.start_button)

        self.network_config_group.setLayout(self.form_layout)
        self.config_layout.addWidget(self.network_config_group, 0)

        self.language_layout = QHBoxLayout()
        self.language_label = QLabel(str(_("main.settings.language")) + ":")
        self.language_combo = QComboBox()
        self.language_combo.setLocale(QLocale(QLocale.Language.English, QLocale.Country.UnitedStates))
        for lang_code, lang_name in LANGUAGES.items():
            self.language_combo.addItem(lang_name, lang_code)

        current_language = self.main_window.settings.get("language") or get_current_language()
        for i in range(self.language_combo.count()):
            if self.language_combo.itemData(i) == current_language:
                self.language_combo.setCurrentIndex(i)
                break
        self.language_combo.currentTextChanged.connect(self.on_language_changed)

        self.language_layout.addWidget(self.language_label)
        self.language_layout.addWidget(self.language_combo)
        self.language_layout.addStretch()
        self.config_layout.addLayout(self.language_layout)

        self.content_layout.addLayout(self.config_layout)

        self.qrcode_label = QLabel(self)
        self.qrcode_label.setAlignment(Qt.AlignCenter)
        self.qrcode_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.qrcode_label.setMinimumSize(300, 300)
        self.content_layout.addWidget(self.qrcode_label, 1)
        self.main_layout.addLayout(self.content_layout)

        self.apply_settings_to_ui()
        self.ip_combobox.currentTextChanged.connect(self.save_network_settings)
        self.port_spinbox.valueChanged.connect(self.save_network_settings)
        self.osc_port_spinbox.valueChanged.connect(self.save_network_settings)
        self.remote_address_edit.textChanged.connect(self.save_network_settings)
        language_signals.language_changed.connect(self.update_ui_texts)

        self.update_connection_status(False)
        self.update_bluetooth_status("ready")
        self.refresh_bluetooth_buttons()
        self.qrcode_label.setText(str(_("network_tab.bluetooth_direct_hint")))

    def apply_settings_to_ui(self):
        for i in range(self.ip_combobox.count()):
            interface_ip = self.ip_combobox.itemText(i).split(": ")
            if len(interface_ip) != 2:
                continue
            interface, ip = interface_ip
            if interface == self.main_window.settings["interface"] and ip == self.main_window.settings["ip"]:
                self.ip_combobox.setCurrentIndex(i)
                logger.info("set to previous used network interface")
                break

    def save_network_settings(self):
        selected_interface_ip = self.ip_combobox.currentText().split(": ")
        if len(selected_interface_ip) != 2:
            return

        selected_interface, selected_ip = selected_interface_ip
        remote_address = self.remote_address_edit.text()
        if remote_address and not self.validate_ip_address(remote_address):
            logger.warning(f"无效的远程IP地址格式: {remote_address}")
            return

        self.main_window.settings["interface"] = selected_interface
        self.main_window.settings["ip"] = selected_ip
        self.main_window.settings["port"] = self.port_spinbox.value()
        self.main_window.settings["osc_port"] = self.osc_port_spinbox.value()
        self.main_window.settings["remote_address"] = remote_address
        self.main_window.settings["enable_remote"] = self.enable_remote_checkbox.isChecked()
        save_settings(self.main_window.settings)
        logger.info("Network settings saved.")

    def on_language_changed(self):
        selected_language = self.language_combo.currentData()
        if not selected_language:
            return
        self.main_window.settings["language"] = selected_language
        save_settings(self.main_window.settings)
        set_language(selected_language)
        logger.info(f"Language changed to {LANGUAGES.get(selected_language, selected_language)} ({selected_language})")

    def start_server_button_clicked(self):
        if self.server_task and not self.server_task.done():
            return
        self.start_server()

    def start_server(self):
        if self.enable_remote_checkbox.isChecked():
            remote_address = self.remote_address_edit.text()
            if remote_address and not self.validate_ip_address(remote_address):
                error_msg = "远程地址格式无效，无法启动服务器"
                logger.error(error_msg)
                QMessageBox.warning(self, "错误", error_msg)
                return

        selected_ip = self.ip_combobox.currentText().split(": ")[-1]
        selected_port = self.port_spinbox.value()
        osc_port = self.osc_port_spinbox.value()
        logger.info(
            f"正在启动 WebSocket 服务器，监听地址: {selected_ip}:{selected_port} 和 OSC 数据接收端口: {osc_port}"
        )

        loop = asyncio.get_running_loop()
        self.server_task = loop.create_task(self.run_server(selected_ip, selected_port, osc_port))
        self.start_button.setText(str(_("network_tab.disconnect")))
        self.start_button.setStyleSheet("background-color: grey; color: white;")
        self.start_button.setEnabled(False)

        if not self._osc_signal_connected:
            self.main_window.osc_parameters_tab.addresses_updated.connect(self.update_osc_mappings)
            self._osc_signal_connected = True

    async def run_server(self, ip: str, port: int, osc_port: int):
        try:
            async with DGLabWSServer(ip, port, 60) as server:
                client = server.new_local_client()
                logger.info("WebSocket 客户端已初始化")

                remote_address = self.remote_address_edit.text()
                if remote_address:
                    url = client.get_qrcode(f"ws://{remote_address}:{port}")
                    logger.info(f"使用远程地址生成二维码: ws://{remote_address}:{port}")
                else:
                    url = client.get_qrcode(f"ws://{ip}:{port}")
                    logger.info(f"使用本地地址生成二维码: ws://{ip}:{port}")

                if url:
                    self.update_qrcode(self.generate_qrcode(url))
                else:
                    self.original_qrcode_pixmap = None
                    self.qrcode_label.clear()
                    self.qrcode_label.setText(str(_("network_tab.bluetooth_direct_hint")))

                controller = DGLabController(client, udp_client.SimpleUDPClient("127.0.0.1", 9000), self.main_window)
                self.main_window.controller = controller
                logger.info("DGLabController 已初始化")
                self.main_window.controller_settings_tab.bind_controller_settings()
                self.main_window.controller_settings_tab.sync_from_controller()

                osc_server_instance = osc_server.AsyncIOOSCUDPServer(
                    ("0.0.0.0", osc_port), self.dispatcher, asyncio.get_event_loop()
                )
                self.osc_transport, self.osc_protocol = await osc_server_instance.create_serve_endpoint()
                logger.info(f"OSC Server Listening on port {osc_port}")

                self.update_osc_mappings(controller)
                self.update_bluetooth_status("connected" if controller.is_bluetooth_connected() else "disconnected")
                self.refresh_bluetooth_buttons()
                await self.monitor_client(client, controller)
        except Exception as e:
            error_message = f"WebSocket 服务器启动失败: {e}"
            logger.error(error_message, exc_info=True)
            self.start_button.setText("启动失败，请重试")
            self.start_button.setStyleSheet("background-color: red; color: white;")
            self.start_button.setEnabled(True)
            self.main_window.log_viewer_tab.log_text_edit.append(f"ERROR: {error_message}")
            self.update_bluetooth_status("error")
            self.refresh_bluetooth_buttons()
        finally:
            if self.osc_transport is not None:
                self.osc_transport.close()
                self.osc_transport = None
                self.osc_protocol = None

    async def monitor_client(self, client, controller):
        if hasattr(client, "connected") and hasattr(client, "strength_data"):
            await self.monitor_ble_client(client, controller)
            return

        while True:
            async for data in client.data_generator():
                await self.handle_client_data(controller, data)
                if data == RetCode.CLIENT_DISCONNECTED:
                    logger.info("上层连接断开，尝试重新绑定")
                    self.update_bluetooth_status("reconnecting")
                    await client.rebind()
                    controller.pulse_last_update_time = {}
                    break

    async def monitor_ble_client(self, client, controller):
        was_connected = False
        while True:
            connected = bool(getattr(client, "connected", False))
            if connected:
                if not was_connected:
                    logger.info("BLE 设备已连接")
                    controller.pulse_last_update_time = {}
                await self.handle_client_data(controller, client.strength_data)
                was_connected = True
                await asyncio.sleep(0.2)
                continue

            if was_connected or controller.app_status_online:
                logger.info("BLE 设备已断开")
                controller.mark_device_disconnected()
                self.update_connection_status(False)
                self.update_bluetooth_status("disconnected")
                self.main_window.controller_settings_tab.reset_channel_strength_display()
                self.refresh_bluetooth_buttons()

            was_connected = False
            await asyncio.sleep(0.3)

    async def handle_client_data(self, controller, data):
        if isinstance(data, StrengthData):
            controller.sync_strength_data(data)
            controller.data_updated_event.set()
            self.update_connection_status(True)
            self.update_bluetooth_status("connected")
            self.main_window.controller_settings_tab.update_channel_strength_labels(data)
            self.refresh_bluetooth_buttons()
            return

        if isinstance(data, FeedbackButton):
            logger.info(f"App 触发了反馈按钮：{data.name}")
            return

        if data == RetCode.CLIENT_DISCONNECTED:
            logger.info("设备连接已断开")
            controller.mark_device_disconnected()
            self.update_connection_status(False)
            self.update_bluetooth_status("disconnected")
            self.main_window.controller_settings_tab.reset_channel_strength_display()
            self.refresh_bluetooth_buttons()
            return

        logger.info(f"获取到状态码：{data}")

    def disconnect_bluetooth_button_clicked(self):
        if self.main_window.controller is None or self.bluetooth_action_in_progress:
            return
        asyncio.create_task(self.disconnect_bluetooth())

    async def disconnect_bluetooth(self):
        self.bluetooth_action_in_progress = True
        self.update_bluetooth_status("disconnecting")
        self.refresh_bluetooth_buttons()
        try:
            success = await self.main_window.controller.disconnect_bluetooth()
            if success:
                self.update_connection_status(False)
                self.update_bluetooth_status("disconnected")
                self.main_window.controller_settings_tab.reset_channel_strength_display()
            else:
                self.update_bluetooth_status("error")
        finally:
            self.bluetooth_action_in_progress = False
            self.refresh_bluetooth_buttons()

    def reconnect_bluetooth_button_clicked(self):
        if self.main_window.controller is None or self.bluetooth_action_in_progress:
            return
        asyncio.create_task(self.reconnect_bluetooth())

    async def reconnect_bluetooth(self):
        self.bluetooth_action_in_progress = True
        self.update_bluetooth_status("reconnecting")
        self.refresh_bluetooth_buttons()
        try:
            success = await self.main_window.controller.reconnect_bluetooth()
            if success:
                self.update_bluetooth_status("connected")
            else:
                self.update_bluetooth_status("error")
        finally:
            self.bluetooth_action_in_progress = False
            self.refresh_bluetooth_buttons()

    def update_bluetooth_status(self, status):
        self.current_bluetooth_status = status
        status_text = {
            "ready": _("network_tab.bluetooth_ready"),
            "connected": _("network_tab.bluetooth_connected"),
            "disconnected": _("network_tab.bluetooth_disconnected"),
            "reconnecting": _("network_tab.bluetooth_reconnecting"),
            "disconnecting": _("network_tab.bluetooth_disconnecting"),
            "error": _("network_tab.bluetooth_error"),
        }.get(status, status)
        status_style = {
            "ready": "background-color: grey; color: white;",
            "connected": "background-color: green; color: white;",
            "disconnected": "background-color: red; color: white;",
            "reconnecting": "background-color: orange; color: white;",
            "disconnecting": "background-color: orange; color: white;",
            "error": "background-color: orange; color: white;",
        }.get(status, "background-color: grey; color: white;")
        self.bluetooth_status_label.setText(str(status_text))
        self.bluetooth_status_label.setStyleSheet(
            f"QLabel {{ {status_style} border-radius: 5px; padding: 5px; }}"
        )
        self.bluetooth_status_label.adjustSize()

    def refresh_bluetooth_buttons(self):
        controller = self.main_window.controller
        ready = controller is not None and controller.supports_bluetooth_management()
        connected = ready and controller.is_bluetooth_connected()
        self.disconnect_bluetooth_button.setEnabled(ready and connected and not self.bluetooth_action_in_progress)
        self.reconnect_bluetooth_button.setEnabled(ready and not self.bluetooth_action_in_progress)

    def generate_qrcode(self, data: str):
        qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=16, border=2)
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill='black', back_color='white')

        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)

        qimage = QPixmap()
        qimage.loadFromData(buffer.read(), 'PNG')
        return qimage

    def update_qrcode(self, qrcode_pixmap):
        self.original_qrcode_pixmap = qrcode_pixmap
        self.scale_qrcode()
        logger.info("二维码已更新")

    def scale_qrcode(self):
        if self.original_qrcode_pixmap and not self.original_qrcode_pixmap.isNull():
            self.qrcode_label.clear()
            scaled_pixmap = self.original_qrcode_pixmap.scaled(
                self.qrcode_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            self.qrcode_label.setPixmap(scaled_pixmap)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(0, self.scale_qrcode)

    def update_connection_status(self, is_online):
        was_online = self.main_window.app_status_online
        self.main_window.app_status_online = is_online
        if is_online:
            self.connection_status_label.setText(str(_("network_tab.online")))
            self.connection_status_label.setStyleSheet(
                "QLabel { background-color: green; color: white; border-radius: 5px; padding: 5px; }"
            )
            if hasattr(self.main_window, "controller_settings_tab") and not was_online:
                self.main_window.controller_settings_tab.controller_group.setEnabled(True)
                self.main_window.controller_settings_tab.command_types_group.setEnabled(True)
                self.main_window.controller_settings_tab.sync_from_controller()
            if hasattr(self.main_window, "ton_damage_system_tab") and not was_online:
                self.main_window.ton_damage_system_tab.damage_group.setEnabled(True)
        else:
            self.connection_status_label.setText(str(_("network_tab.offline")))
            self.connection_status_label.setStyleSheet(
                "QLabel { background-color: red; color: white; border-radius: 5px; padding: 5px; }"
            )
            if hasattr(self.main_window, "controller_settings_tab") and was_online:
                self.main_window.controller_settings_tab.controller_group.setEnabled(False)
                self.main_window.controller_settings_tab.command_types_group.setEnabled(False)
                self.main_window.controller_settings_tab.reset_channel_strength_display()
            if hasattr(self.main_window, "ton_damage_system_tab") and was_online:
                self.main_window.ton_damage_system_tab.damage_group.setEnabled(False)
        self.connection_status_label.adjustSize()

    def update_osc_mappings(self, controller=None):
        if controller is None:
            controller = self.main_window.controller
        if controller is None:
            return
        asyncio.run_coroutine_threadsafe(self._update_osc_mappings(controller), asyncio.get_event_loop())

    async def _update_osc_mappings(self, controller):
        for address, handler in self.osc_address_handlers.items():
            self.dispatcher.unmap(address, handler)
        self.osc_address_handlers.clear()

        osc_addresses = self.main_window.get_osc_addresses()
        for addr in osc_addresses:
            address = addr["address"]
            channels = addr["channels"]
            mapping_ranges = addr.get(
                "mapping_ranges",
                {"A": {"min": 0, "max": 100}, "B": {"min": 0, "max": 100}},
            )
            handler = functools.partial(
                self.handle_osc_message_task_pb_with_channels,
                controller=controller,
                channels=channels,
                mapping_ranges=mapping_ranges,
            )
            self.dispatcher.map(address, handler)
            self.osc_address_handlers[address] = handler
        logger.info("OSC dispatcher mappings updated with custom addresses.")

        if not self.panel_control_handlers:
            self.add_panel_control_mappings(controller)

    def add_panel_control_mappings(self, controller):
        panel_addresses = [
            "/avatar/parameters/SoundPad/Button/*",
            "/avatar/parameters/SoundPad/Volume",
            "/avatar/parameters/SoundPad/Page",
            "/avatar/parameters/SoundPad/PanelControl",
        ]
        for address in panel_addresses:
            handler = functools.partial(self.handle_osc_message_task_pad, controller=controller)
            self.dispatcher.map(address, handler)
            self.panel_control_handlers[address] = handler
        logger.info("OSC dispatcher mappings updated with panel control addresses.")

    def handle_osc_message_task_pad(self, address, *args, controller):
        logger.info(f"收到OSC消息 (面板控制): {address} {args}")
        asyncio.create_task(controller.handle_osc_message_pad(address, *args))

    def handle_osc_message_task_pb_with_channels(self, address, *args, controller, channels, mapping_ranges=None):
        channel_list = []
        if isinstance(channels, dict):
            if channels.get("A", False):
                channel_list.append("A")
            if channels.get("B", False):
                channel_list.append("B")
        elif isinstance(channels, list):
            channel_list = channels

        logger.info(f"收到OSC消息 (参数绑定): {address} {args} 通道: {channel_list}")
        asyncio.create_task(
            controller.handle_osc_message_pb(
                address,
                *args,
                channels=channel_list,
                mapping_ranges=mapping_ranges,
            )
        )

    def update_ui_texts(self):
        self.network_config_group.setTitle(str(_("network_tab.title")))

        for i in range(self.form_layout.rowCount()):
            label_item = self.form_layout.itemAt(i, QFormLayout.LabelRole)
            field_item = self.form_layout.itemAt(i, QFormLayout.FieldRole)
            if not label_item or not label_item.widget() or not isinstance(label_item.widget(), QLabel):
                continue
            label_widget = label_item.widget()

            if field_item and field_item.widget():
                field_widget = field_item.widget()
                if field_widget == self.ip_combobox:
                    label_widget.setText(str(_("network_tab.interface")) + ":")
                elif field_widget == self.port_spinbox:
                    label_widget.setText(str(_("network_tab.websocket_port")) + ":")
                elif field_widget == self.osc_port_spinbox:
                    label_widget.setText(str(_("network_tab.osc_port")) + ":")
                elif field_widget == self.connection_status_label:
                    label_widget.setText(str(_("network_tab.status")) + ":")
                elif field_widget == self.bluetooth_status_label:
                    label_widget.setText(str(_("network_tab.bluetooth_status")) + ":")
            elif field_item and field_item.layout() == self.remote_address_layout:
                label_widget.setText(str(_("network_tab.remote_address")) + ":")

        self.connection_status_label.setText(str(_("network_tab.online")) if self.main_window.app_status_online else str(_("network_tab.offline")))
        self.language_label.setText(str(_("main.settings.language")) + ":")
        self.enable_remote_checkbox.setText(str(_("network_tab.enable_remote")))
        self.get_public_ip_button.setText(str(_("network_tab.get_public_ip")))
        self.remote_address_edit.setPlaceholderText(_("network_tab.please_enter_valid_ip"))
        self.disconnect_bluetooth_button.setText(str(_("network_tab.disconnect_bluetooth")))
        self.reconnect_bluetooth_button.setText(str(_("network_tab.reconnect_bluetooth")))
        self.update_bluetooth_status(self.current_bluetooth_status)
        if self.original_qrcode_pixmap is None:
            self.qrcode_label.setText(str(_("network_tab.bluetooth_direct_hint")))

    def on_remote_enabled_changed(self, state):
        is_enabled = bool(state)
        self.remote_address_edit.setEnabled(is_enabled)
        self.get_public_ip_button.setEnabled(is_enabled)
        server_running = self.server_task is not None and not self.server_task.done()

        if server_running:
            self.main_window.settings["enable_remote"] = is_enabled
            self.save_network_settings()
            return

        if is_enabled:
            remote_address = self.remote_address_edit.text()
            if remote_address and not self.validate_ip_address(remote_address):
                self.start_button.setEnabled(False)
                self.start_button.setStyleSheet("background-color: grey; color: white;")
            else:
                self.start_button.setEnabled(True)
                self.start_button.setStyleSheet("background-color: green; color: white;")
        else:
            self.start_button.setEnabled(True)
            self.start_button.setStyleSheet("background-color: green; color: white;")

        self.main_window.settings["enable_remote"] = is_enabled
        self.save_network_settings()

    def get_public_ip(self):
        try:
            response = requests.get("http://myip.ipip.net", timeout=5)
            public_ip = response.text.split("：")[1].split(" ")[0]
            self.remote_address_edit.setText(public_ip)
            logger.info(f"获取到公网IP: {public_ip}")
            self.save_network_settings()
        except Exception as e:
            error_msg = f"获取公网IP失败: {e}"
            logger.error(error_msg)
            QMessageBox.warning(self, "错误", error_msg)

    def validate_ip_address(self, ip_str: str) -> bool:
        try:
            parts = ip_str.split(".")
            if len(parts) != 4:
                return False
            for part in parts:
                if not part.isdigit():
                    return False
                num = int(part)
                if num < 0 or num > 255:
                    return False
            return True
        except (AttributeError, TypeError):
            return False

    def on_remote_address_changed(self, text: str):
        enable_remote = self.enable_remote_checkbox.isChecked()
        server_running = self.server_task is not None and not self.server_task.done()
        if enable_remote and text:
            is_valid = self.validate_ip_address(text)
            if not is_valid:
                self.remote_address_edit.setStyleSheet(
                    "QLineEdit { border: 1px solid red; padding: 2px; }"
                )
                if not server_running:
                    self.start_button.setEnabled(False)
                    self.start_button.setStyleSheet("background-color: grey; color: white;")
            else:
                self.remote_address_edit.setStyleSheet("")
                if not server_running:
                    self.start_button.setEnabled(True)
                    self.start_button.setStyleSheet("background-color: green; color: white;")
                self.save_network_settings()
        else:
            self.remote_address_edit.setStyleSheet("")
            if not server_running:
                self.start_button.setEnabled(True)
                self.start_button.setStyleSheet("background-color: green; color: white;")
