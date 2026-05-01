"""fusion_controller.py — Multi-device fusion controller for YCY-VRCOSC.

Replaces ToyController with a panel/button driven model:
  - 3 panels × 15 buttons (3 rows × 5 cols)
  - Each button can target multiple devices simultaneously
  - Hold mode: button held → repeat actions every 100 ms; release → stop
  - OSC: /SoundPad/Page → select panel; /SoundPad/Button/N → press/release
"""
from __future__ import annotations

import asyncio
import logging

from panel_config import get_button, load_panels

log = logging.getLogger("yokonex_vrcosc.fusion")

_HOLD_INTERVAL = 0.1   # seconds between repeated sends while held
_HOLD_INITIAL  = 0.0   # delay before first send (immediate)


class FusionController:
    def __init__(self, yokonex_client, osc_client=None, main_window=None):
        self.client      = yokonex_client
        self.osc_client  = osc_client
        self.main_window = main_window

        self._devices: dict[str, dict]       = {}   # addr → {name, type}
        self._device_states: dict[str, dict] = {}   # addr → live state
        self._panels:  list[dict]            = load_panels()
        self._current_panel: int             = 0
        self._hold_tasks: dict[tuple, asyncio.Task] = {}  # (panel, btn) → Task

        # ChatBox
        self.chatbox_enabled:  bool  = False
        self.chatbox_template: str   = "{dev1_name}  A:{dev1_speed_A} B:{dev1_speed_B}"
        self.chatbox_interval: float = 3.0
        # Periodic send is driven by a QTimer in ChatBoxTab (avoids asyncio task context conflicts)

    # ── Device registry ────────────────────────────────────────────────────────

    @property
    def devices(self) -> dict[str, dict]:
        return self._devices

    # ── Panel config ───────────────────────────────────────────────────────────

    def reload_panels(self) -> None:
        self._panels = load_panels()

    @property
    def panels(self) -> list[dict]:
        return self._panels

    # ── OSC entry point ────────────────────────────────────────────────────────

    async def handle_osc_panel(self, address: str, *args) -> None:
        if not args:
            return
        value = args[0]

        if address == "/avatar/parameters/SoundPad/Page":
            self._current_panel = min(2, max(0, int(value)))
            log.debug("Panel → %d", self._current_panel)
            return

        if address.startswith("/avatar/parameters/SoundPad/Button/"):
            try:
                n = int(address.rsplit("/", 1)[-1])
            except ValueError:
                return
            btn_idx = n - 1   # 1-based OSC → 0-based index
            pressed = bool(value)
            await self.handle_button(self._current_panel, btn_idx, pressed)

    # ── Button press / release ─────────────────────────────────────────────────

    async def handle_button(self, panel: int, btn: int, pressed: bool) -> None:
        key = (panel, btn)
        if pressed:
            # Cancel any existing task for this key first
            existing = self._hold_tasks.pop(key, None)
            if existing and not existing.done():
                existing.cancel()
            task = asyncio.create_task(
                self._hold_loop(panel, btn),
                name=f"hold-{panel}-{btn}",
            )
            self._hold_tasks[key] = task
        else:
            task = self._hold_tasks.pop(key, None)
            if task and not task.done():
                task.cancel()

    # ── Hold loop ──────────────────────────────────────────────────────────────

    async def _hold_loop(self, panel: int, btn: int) -> None:
        button = get_button(self._panels, panel, btn)
        if not button:
            log.debug("Button p%d/b%d not configured", panel, btn)
            return
        actions = button.get("actions", [])
        if not actions:
            return

        once_actions = [a for a in actions if a.get("once", False)]
        loop_actions = [a for a in actions if not a.get("once", False)]

        # Save pre-fire intensities for fire_channel restore on release
        fire_restores: list[dict] = []
        for a in loop_actions:
            if a.get("action") == "fire_channel":
                addr = self._resolve_addr(a)
                if addr:
                    ch    = a.get("params", {}).get("channel", "A")
                    state = self._device_states.get(addr, {})
                    fire_restores.append({
                        "addr":      addr,
                        "channel":   ch,
                        "intensity": state.get(f"intensity_{ch}", 1),
                        "mode":      state.get(f"mode_{ch}", 1),
                        "enabled":   state.get(f"enabled_{ch}", True),
                    })

        log.debug("Hold start  p%d/b%d  label=%s", panel, btn, button.get("label", ""))
        try:
            first = True
            while True:
                if first:
                    await self._fire_actions(once_actions + loop_actions)
                    first = False
                    if not loop_actions:
                        return  # pure once-actions: no repeat needed
                else:
                    await self._fire_actions(loop_actions)
                await asyncio.sleep(_HOLD_INTERVAL)
        except asyncio.CancelledError:
            for restore in fire_restores:
                try:
                    await self.client.command(restore["addr"], "set_channel", {
                        "channel":   restore["channel"],
                        "enabled":   restore["enabled"],
                        "intensity": restore["intensity"],
                        "mode":      restore["mode"],
                        "freq":      0,
                        "pulse_us":  0,
                    })
                except Exception as e:
                    log.warning("fire_channel restore %s ch%s: %s",
                                restore["addr"][-8:], restore["channel"], e)
            log.debug("Hold stop   p%d/b%d", panel, btn)

    async def _fire_actions(self, actions: list[dict]) -> None:
        """Execute all actions concurrently."""
        tasks = [asyncio.create_task(self._execute_action(a)) for a in actions]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, Exception):
                log.warning("Action error: %s", r)

    def _resolve_addr(self, action: dict) -> str:
        """Resolve device_address, auto-routing empty address via device_type."""
        addr = action.get("device_address", "")
        if addr:
            return addr
        device_type = action.get("device_type", "")
        if device_type:
            for a, info in self._devices.items():
                if info.get("type") == device_type:
                    return a
        return ""

    async def _execute_action(self, action: dict) -> None:
        act = action.get("action", "")
        if not act:
            return

        params = action.get("params", {})

        # Controller-level actions (no device address needed)
        if act == "toggle_chatbox":
            self.chatbox_enabled = not self.chatbox_enabled
            return

        addr = self._resolve_addr(action)
        if not addr:
            return

        # Pass-through device commands
        if act in ("set_speed", "set_mode", "stop", "set_channel"):
            try:
                await self.client.command(addr, act, params)
            except Exception as e:
                log.warning("command %s@%s failed: %s", act, addr[-8:], e)
            return

        if act == "adjust_channel":
            ch      = params.get("channel", "A")
            delta   = params.get("delta", 0)
            state   = self._device_states.get(addr, {})
            cap     = state.get(f"cap_{ch}", 276)
            new_int = max(0, min(cap, state.get(f"intensity_{ch}", 0) + delta))
            try:
                await self.client.command(addr, "set_channel", {
                    "channel":   ch,
                    "enabled":   state.get(f"enabled_{ch}", True),
                    "intensity": new_int,
                    "mode":      state.get(f"mode_{ch}", 1),
                    "freq":      0,
                    "pulse_us":  0,
                })
                self._device_states.setdefault(addr, {})[f"intensity_{ch}"] = new_int
            except Exception as e:
                log.warning("adjust_channel %s ch%s: %s", addr[-8:], ch, e)
            return

        if act == "fire_channel":
            ch         = params.get("channel", "A")
            fire_delta = params.get("fire_intensity", 30)
            state      = self._device_states.get(addr, {})
            cap        = state.get(f"cap_{ch}", 276)
            new_int    = max(0, min(cap, state.get(f"intensity_{ch}", 0) + fire_delta))
            try:
                await self.client.command(addr, "set_channel", {
                    "channel":   ch,
                    "enabled":   state.get(f"enabled_{ch}", True),
                    "intensity": new_int,
                    "mode":      state.get(f"mode_{ch}", 1),
                    "freq":      0,
                    "pulse_us":  0,
                })
            except Exception as e:
                log.warning("fire_channel %s ch%s: %s", addr[-8:], ch, e)
            return

        if act == "set_channel_mode":
            ch    = params.get("channel", "A")
            mode  = params.get("mode", 1)
            state = self._device_states.get(addr, {})
            try:
                await self.client.command(addr, "set_channel", {
                    "channel":   ch,
                    "enabled":   state.get(f"enabled_{ch}", True),
                    "intensity": state.get(f"intensity_{ch}", 1),
                    "mode":      mode,
                    "freq":      0,
                    "pulse_us":  0,
                })
                self._device_states.setdefault(addr, {})[f"mode_{ch}"] = mode
            except Exception as e:
                log.warning("set_channel_mode %s ch%s mode%d: %s", addr[-8:], ch, mode, e)
            return

        if act == "toggle_channel":
            ch          = params.get("channel", "A")
            state       = self._device_states.get(addr, {})
            new_enabled = not state.get(f"enabled_{ch}", True)
            try:
                await self.client.command(addr, "set_channel", {
                    "channel":   ch,
                    "enabled":   new_enabled,
                    "intensity": state.get(f"intensity_{ch}", 1),
                    "mode":      state.get(f"mode_{ch}", 1),
                    "freq":      0,
                    "pulse_us":  0,
                })
                self._device_states.setdefault(addr, {})[f"enabled_{ch}"] = new_enabled
            except Exception as e:
                log.warning("toggle_channel %s ch%s: %s", addr[-8:], ch, e)
            return

        if act == "adjust_speed":
            motor = params.get("motor", "A")
            delta = params.get("delta", 0)
            state = self._device_states.get(addr, {})
            new_speed = max(0, min(20, state.get(f"speed_{motor}", 0) + delta))
            speed_cmd = {
                "motor_a": state.get("speed_A", 0),
                "motor_b": state.get("speed_B", 0),
                "motor_c": state.get("speed_C", 0),
            }
            speed_cmd[f"motor_{motor.lower()}"] = new_speed
            try:
                await self.client.command(addr, "set_speed", speed_cmd)
                self._device_states.setdefault(addr, {})[f"speed_{motor}"] = new_speed
            except Exception as e:
                log.warning("adjust_speed %s motor%s: %s", addr[-8:], motor, e)
            return


        # Fallback: pass unknown action straight to device
        try:
            await self.client.command(addr, act, params)
        except Exception as e:
            log.warning("command %s@%s failed: %s", act, addr[-8:], e)

    # ── GUI trigger (manual button press from UI) ──────────────────────────────

    async def gui_press(self, panel: int, btn: int) -> None:
        await self.handle_button(panel, btn, True)

    async def gui_release(self, panel: int, btn: int) -> None:
        await self.handle_button(panel, btn, False)

    # ── Cleanup ────────────────────────────────────────────────────────────────

    # ── GUI direct commands ────────────────────────────────────────────────────

    async def gui_toy_set_speed(self, addr: str, motor_a: int, motor_b: int, motor_c: int) -> None:
        try:
            await self.client.command(addr, "set_speed",
                                      {"motor_a": motor_a, "motor_b": motor_b, "motor_c": motor_c})
        except Exception as e:
            log.error("gui_toy_set_speed %s: %s", addr[-8:], e)

    async def gui_toy_set_mode(self, addr: str, motors: int, mode: int) -> None:
        try:
            await self.client.command(addr, "set_mode", {"motors": motors, "mode": mode})
        except Exception as e:
            log.error("gui_toy_set_mode %s: %s", addr[-8:], e)

    async def gui_estim_set_channel(
        self, addr: str, channel: str, enabled: bool,
        intensity: int, mode: int, freq: int = 0, pulse_us: int = 0,
    ) -> None:
        try:
            await self.client.command(addr, "set_channel", {
                "channel": channel, "enabled": enabled, "intensity": intensity,
                "mode": mode, "freq": freq, "pulse_us": pulse_us,
            })
        except Exception as e:
            log.error("gui_estim_set_channel %s: %s", addr[-8:], e)

    async def gui_stop_device(self, addr: str) -> None:
        try:
            await self.client.command(addr, "stop", {})
        except Exception as e:
            log.error("gui_stop_device %s: %s", addr[-8:], e)

    # ── OSC interaction (PhysBone / Contact float values) ─────────────────────

    async def handle_osc_interaction(self, address: str, value: float, entry: dict) -> None:
        """
        entry schema (from osc_addresses.yml, extended):
          device_address: str   # "" = all toy devices
          target_type:    str   # "toy" | "estim"
          channels:       dict  # {A: bool, B: bool, C: bool} (toy) or {A: bool, B: bool} (estim)
          mapping_ranges: dict  # {A: {min:0-100, max:0-100}, ...}
        """
        dtype    = entry.get("target_type", "toy")
        dev_addr = entry.get("device_address", "")
        channels = entry.get("channels", {})
        ranges   = entry.get("mapping_ranges", {})

        if dtype == "toy":
            addrs = [dev_addr] if dev_addr else [
                a for a, i in self._devices.items() if i.get("type") == "toy"
            ]
            for addr in addrs:
                speeds = {}
                for m in ("A", "B", "C"):
                    if channels.get(m, False):
                        r  = ranges.get(m, {"min": 0, "max": 100})
                        lo = r.get("min", 0) / 100.0
                        hi = r.get("max", 100) / 100.0
                        if lo > hi:
                            lo, hi = hi, lo
                        speeds[f"motor_{m.lower()}"] = int((lo + (hi - lo) * value) * 20)
                if speeds:
                    full = {f"motor_{m.lower()}": speeds.get(f"motor_{m.lower()}", 0)
                            for m in ("A", "B", "C")}
                    await self._execute_action({"device_address": addr,
                                                "action": "set_speed", "params": full})

        elif dtype == "estim":
            addrs = [dev_addr] if dev_addr else [
                a for a, i in self._devices.items() if i.get("type") == "estim"
            ]
            for addr in addrs:
                for ch in ("A", "B"):
                    if channels.get(ch, False):
                        r  = ranges.get(ch, {"min": 0, "max": 100})
                        lo = r.get("min", 0) / 100.0
                        hi = r.get("max", 100) / 100.0
                        if lo > hi:
                            lo, hi = hi, lo
                        intensity = max(1, int((lo + (hi - lo) * value) * 276))
                        await self._execute_action({"device_address": addr,
                                                    "action": "set_channel",
                                                    "params": {
                                                        "channel": ch, "enabled": True,
                                                        "intensity": intensity, "mode": 1,
                                                        "freq": 0, "pulse_us": 0,
                                                    }})

    # ── Device change callbacks ────────────────────────────────────────────────

    on_device_added:   "callable | None" = None
    on_device_removed: "callable | None" = None

    def register_device(self, address: str, name: str, device_type: str) -> None:
        self._devices[address] = {"name": name, "type": device_type}
        log.info("Registered device %s (%s) type=%s", name, address, device_type)
        if callable(self.on_device_added):
            self.on_device_added(address, name, device_type)

    def unregister_device(self, address: str) -> None:
        self._devices.pop(address, None)
        log.info("Unregistered device %s", address)
        if callable(self.on_device_removed):
            self.on_device_removed(address)

    # ── Device state tracking ──────────────────────────────────────────────────

    def set_intensity_cap(self, addr: str, ch: str, cap: int) -> None:
        self._device_states.setdefault(addr, {})[f"cap_{ch}"] = cap

    def update_device_state(self, addr: str, event_type: str, data: dict) -> None:
        """Called by network_config_tab when a device event arrives."""
        state = self._device_states.setdefault(addr, {})
        if event_type == "channel_status":
            ch = data.get("channel", "A")
            state[f"intensity_{ch}"] = data.get("intensity", 0)
            state[f"mode_{ch}"]      = data.get("mode", 1)
            state[f"enabled_{ch}"]   = data.get("enabled", False)
        elif event_type == "battery":
            state["battery"] = data.get("level", data.get("battery", 0))
        elif event_type in ("set_speed", "motor_status"):
            state["speed_A"] = data.get("motor_a", data.get("speed_A", 0))
            state["speed_B"] = data.get("motor_b", data.get("speed_B", 0))
            state["speed_C"] = data.get("motor_c", data.get("speed_C", 0))

    def build_chatbox_context(self) -> dict:
        """Build flat template variable dict from all device states."""
        ctx: dict = {"panel": self._current_panel + 1}
        for i, (addr, info) in enumerate(sorted(self._devices.items()), start=1):
            prefix = f"dev{i}"
            state  = self._device_states.get(addr, {})
            ctx[f"{prefix}_name"]    = info.get("name", addr[-8:])
            ctx[f"{prefix}_type"]    = info.get("type", "?")
            ctx[f"{prefix}_battery"] = state.get("battery", "?")
            dtype = info.get("type", "toy")
            if dtype == "toy":
                for m in ("A", "B", "C"):
                    ctx[f"{prefix}_speed_{m}"] = state.get(f"speed_{m}", 0)
                    ctx[f"{prefix}_mode_{m}"]  = state.get(f"mode_{m}", 1)
            else:
                for ch in ("A", "B"):
                    ctx[f"{prefix}_intensity_{ch}"] = state.get(f"intensity_{ch}", 0)
                    ctx[f"{prefix}_mode_{ch}"]      = state.get(f"mode_{ch}", 1)
                    ctx[f"{prefix}_enabled_{ch}"]   = state.get(f"enabled_{ch}", False)
        return ctx

    # ── ChatBox ────────────────────────────────────────────────────────────────

    def send_chatbox_now(self) -> None:
        """Force-send the chatbox message once (called by QTimer or test button)."""
        if not self.osc_client:
            return
        ctx = self.build_chatbox_context()
        try:
            text = self.chatbox_template.format_map(ctx)
        except (KeyError, ValueError):
            text = self.chatbox_template
        self.osc_client.send_message("/chatbox/input", [text, True, False])

    # ── Cleanup ────────────────────────────────────────────────────────────────

    def cancel_all(self) -> None:
        for task in list(self._hold_tasks.values()):
            if not task.done():
                task.cancel()
        self._hold_tasks.clear()
