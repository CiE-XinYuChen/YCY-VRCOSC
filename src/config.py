import logging
import os
import socket
import sys

import psutil
import yaml

logger = logging.getLogger(__name__)

DEFAULT_SETTINGS = {
    "yokonex_host": "127.0.0.1",
    "yokonex_port": 8765,
    "osc_port":     9001,
    "language":     "zh",
}


def get_config_file_path(filename: str) -> str:
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(os.path.dirname(sys.executable), filename)
    return os.path.join(
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),
        filename,
    )


def get_active_ip_addresses() -> dict:
    result = {}
    for iface, addrs in psutil.net_if_addrs().items():
        if psutil.net_if_stats()[iface].isup:
            for addr in addrs:
                if addr.family == socket.AF_INET:
                    result[iface] = addr.address
    return result


def load_settings() -> dict:
    path = get_config_file_path("settings.yml")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            for k, v in DEFAULT_SETTINGS.items():
                data.setdefault(k, v)
            return data
        except Exception as e:
            logger.error("Load settings failed: %s", e)
    return DEFAULT_SETTINGS.copy()


def save_settings(settings: dict) -> None:
    path = get_config_file_path("settings.yml")
    try:
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(settings, f, allow_unicode=True)
    except Exception as e:
        logger.error("Save settings failed: %s", e)
