"""panel_config.py — Panel/button configuration model.

Storage: panels.yml (next to settings.yml)
Structure:
  panels[3]:
    name: str
    buttons[0-14]:
      index: int
      label: str
      actions[]:
        device_address: str
        action: str   # set_speed | set_mode | stop | set_channel
        params: dict
"""
from __future__ import annotations

import logging
import os
import sys
from typing import Any

import yaml

log = logging.getLogger(__name__)

NUM_PANELS  = 3
NUM_BUTTONS = 15  # 3 rows × 5 cols


def _config_path(filename: str) -> str:
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(os.path.dirname(sys.executable), filename)
    return os.path.join(
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),
        filename,
    )


def _make_estim_buttons(channels: list[str]) -> list[dict]:
    """Build 15 buttons for an estim panel targeting the given channel(s)."""

    def ea(action: str, extra_params: dict, once: bool = False) -> list[dict]:
        result = []
        for ch in channels:
            a: dict = {
                "device_address": "",
                "device_type":    "estim",
                "action":         action,
                "params":         {"channel": ch, **extra_params},
            }
            if once:
                a["once"] = True
            result.append(a)
        return result

    return [
        # Row 1: channel on/off toggle | zero intensity | −5 | +5 | +30 fire
        {"index": 0,  "label": "模式",    "actions": ea("toggle_channel",  {},                       once=True)},
        {"index": 1,  "label": "归零",    "actions": ea("adjust_channel",  {"delta": -9999})},
        {"index": 2,  "label": "−5",      "actions": ea("adjust_channel",  {"delta": -5})},
        {"index": 3,  "label": "+5",      "actions": ea("adjust_channel",  {"delta":  5})},
        {"index": 4,  "label": "+30🔥",  "actions": ea("fire_channel",    {"fire_intensity": 30})},
        # Row 2: ChatBox toggle | waveform 1-4
        {"index": 5,  "label": "ChatBox", "actions": [{"device_address": "", "device_type": "",
                                                        "action": "toggle_chatbox", "params": {},
                                                        "once": True}]},
        {"index": 6,  "label": "波形 1",  "actions": ea("set_channel_mode", {"mode": 1},  once=True)},
        {"index": 7,  "label": "波形 2",  "actions": ea("set_channel_mode", {"mode": 2},  once=True)},
        {"index": 8,  "label": "波形 3",  "actions": ea("set_channel_mode", {"mode": 3},  once=True)},
        {"index": 9,  "label": "波形 4",  "actions": ea("set_channel_mode", {"mode": 4},  once=True)},
        # Row 3: waveform 5-9
        {"index": 10, "label": "波形 5",  "actions": ea("set_channel_mode", {"mode": 5},  once=True)},
        {"index": 11, "label": "波形 6",  "actions": ea("set_channel_mode", {"mode": 6},  once=True)},
        {"index": 12, "label": "波形 7",  "actions": ea("set_channel_mode", {"mode": 7},  once=True)},
        {"index": 13, "label": "波形 8",  "actions": ea("set_channel_mode", {"mode": 8},  once=True)},
        {"index": 14, "label": "波形 9",  "actions": ea("set_channel_mode", {"mode": 9},  once=True)},
    ]


def _make_toy_buttons(motors: list[str]) -> list[dict]:
    """Build 15 buttons for a toy panel targeting the given motor(s)."""
    motors_str = "".join(motors)

    def ta(action: str, extra_params: dict, once: bool = False) -> list[dict]:
        result = []
        for m in motors:
            a: dict = {
                "device_address": "",
                "device_type":    "toy",
                "action":         action,
                "params":         {"motor": m, **extra_params},
            }
            if once:
                a["once"] = True
            result.append(a)
        return result

    def mode_actions(mode: int) -> list[dict]:
        return [{
            "device_address": "", "device_type": "toy",
            "action": "set_mode",
            "params": {"motors": motors_str, "mode": mode},
            "once": True,
        }]

    return [
        # Row 1: stop | zero | −5 | +5 | full speed
        {"index": 0,  "label": "停止",    "actions": [
            {"device_address": "", "device_type": "toy",
             "action": "stop", "params": {}, "once": True}
        ]},
        {"index": 1,  "label": "归零",    "actions": ta("adjust_speed", {"delta": -999})},
        {"index": 2,  "label": "−2",      "actions": ta("adjust_speed", {"delta": -2})},
        {"index": 3,  "label": "+2",      "actions": ta("adjust_speed", {"delta": 2})},
        {"index": 4,  "label": "全速",    "actions": ta("adjust_speed", {"delta": 999})},
        # Row 2: ChatBox | mode 1-4
        {"index": 5,  "label": "ChatBox", "actions": [
            {"device_address": "", "device_type": "",
             "action": "toggle_chatbox", "params": {}, "once": True}
        ]},
        {"index": 6,  "label": "模式 1",  "actions": mode_actions(1)},
        {"index": 7,  "label": "模式 2",  "actions": mode_actions(2)},
        {"index": 8,  "label": "模式 3",  "actions": mode_actions(3)},
        {"index": 9,  "label": "模式 4",  "actions": mode_actions(4)},
        # Row 3: empty
    ]


def _default_toy_panels() -> list[dict]:
    return [
        {"name": "马达 A",  "buttons": _make_toy_buttons(["A"])},
        {"name": "马达 B",  "buttons": _make_toy_buttons(["B"])},
        {"name": "马达 AB", "buttons": _make_toy_buttons(["A", "B"])},
    ]


def _default_panels() -> list[dict]:
    return [
        {"name": "通道 A",  "buttons": _make_estim_buttons(["A"])},
        {"name": "通道 B",  "buttons": _make_estim_buttons(["B"])},
        {"name": "通道 AB", "buttons": _make_estim_buttons(["A", "B"])},
    ]


# ── Preset registry ────────────────────────────────────────────────────────────

PRESETS: dict[str, callable] = {
    "estim": _default_panels,
    "toy":   _default_toy_panels,
}

PRESET_LABELS: dict[str, str] = {
    "estim": "DG-LAB 电击",
    "toy":   "飞机杯",
}

# (display_label, targets_list) per preset type
PRESET_TARGETS: dict[str, list[tuple[str, list[str]]]] = {
    "estim": [
        ("通道 A",  ["A"]),
        ("通道 B",  ["B"]),
        ("通道 AB", ["A", "B"]),
    ],
    "toy": [
        ("马达 A",   ["A"]),
        ("马达 B",   ["B"]),
        ("马达 C",   ["C"]),
        ("马达 AB",  ["A", "B"]),
        ("马达 AC",  ["A", "C"]),
        ("马达 BC",  ["B", "C"]),
        ("马达 ABC", ["A", "B", "C"]),
    ],
}


def make_panel_buttons(preset_name: str, targets: list[str]) -> list[dict]:
    """Generate 15 buttons for a single panel with the given targets."""
    if preset_name == "toy":
        return _make_toy_buttons(targets)
    if preset_name == "estim":
        return _make_estim_buttons(targets)
    return []


def apply_preset(name: str) -> list[dict]:
    """Load a built-in preset, save it to disk, and return the panels list."""
    fn = PRESETS.get(name, _default_panels)
    panels = fn()
    save_panels(panels)
    return panels


def load_panels() -> list[dict]:
    path = _config_path("panels.yml")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            panels = data.get("panels", [])
            # Ensure exactly NUM_PANELS entries
            while len(panels) < NUM_PANELS:
                panels.append({"name": f"Panel {len(panels) + 1}", "buttons": []})
            return panels[:NUM_PANELS]
        except Exception as e:
            log.error("load_panels failed: %s", e)
    return _default_panels()


def save_panels(panels: list[dict]) -> None:
    path = _config_path("panels.yml")
    try:
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump({"panels": panels}, f, allow_unicode=True, default_flow_style=False)
    except Exception as e:
        log.error("save_panels failed: %s", e)


def get_button(panels: list[dict], panel_idx: int, btn_idx: int) -> dict | None:
    """Return button config dict or None if not configured."""
    if panel_idx >= len(panels):
        return None
    for btn in panels[panel_idx].get("buttons", []):
        if btn.get("index") == btn_idx:
            return btn
    return None


def set_button(panels: list[dict], panel_idx: int, btn_idx: int, button: dict) -> None:
    """Insert or replace button config, then save."""
    while len(panels) < NUM_PANELS:
        panels.append({"name": f"Panel {len(panels) + 1}", "buttons": []})
    buttons = panels[panel_idx].setdefault("buttons", [])
    for i, b in enumerate(buttons):
        if b.get("index") == btn_idx:
            buttons[i] = button
            return
    buttons.append(button)


def action_summary(action: dict, devices: dict[str, dict]) -> str:
    """One-line summary for display in the action list."""
    addr   = action.get("device_address", "")
    dtype  = action.get("device_type", "")
    name   = (devices.get(addr, {}).get("name", addr[-8:] if addr else "")
              or (f"[{dtype}]" if dtype else "?"))
    act    = action.get("action", "?")
    params = action.get("params", {})
    ch     = params.get("channel", "")

    if act == "set_speed":
        s = f"A:{params.get('motor_a',0)} B:{params.get('motor_b',0)} C:{params.get('motor_c',0)}"
        return f"[{name}] speed {s}"
    if act == "set_mode":
        return f"[{name}] mode {params.get('motors','?')} → {params.get('mode','?')}"
    if act == "set_channel":
        if not params.get("enabled", True):
            return f"[{name}] estim {ch} OFF"
        return (f"[{name}] estim {ch}  {params.get('intensity','?')}  "
                f"mode{params.get('mode','?')}")
    if act == "stop":
        return f"[{name}] STOP"
    if act == "adjust_channel":
        delta = params.get("delta", 0)
        sign  = "+" if delta >= 0 else ""
        return f"[{name}] {ch} {sign}{delta}"
    if act == "adjust_speed":
        motor = params.get("motor", "A")
        delta = params.get("delta", 0)
        sign  = "+" if delta >= 0 else ""
        return f"[{name}] 马达{motor} 速度 {sign}{delta}"
    if act == "fire_channel":
        return f"[{name}] {ch} +{params.get('fire_intensity', 30)} fire"
    if act == "toggle_channel":
        return f"[{name}] {ch} 开/关切换"
    if act == "set_channel_mode":
        return f"[{name}] {ch} → 波形 {params.get('mode','?')}"
    if act == "toggle_chatbox":
        return "ChatBox 开/关切换"
    return f"[{name}] {act}"
