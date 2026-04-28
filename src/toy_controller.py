"""toy_controller.py - YokoNex toy device controller for VRChat OSC.

Motor mapping:
    SoundPad Page 0 → Motor A
    SoundPad Page 1 → Motor B
    SoundPad Page 2 → Motor C

SoundPad Buttons:
    Button/1  → Cycle mode (1→2→3→4→1) for current motor
    Button/2  → Stop current motor (speed = 0)
    Button/3  → Speed - adjust_step
    Button/4  → Speed + adjust_step
    Button/5  → Fire mode (hold to spike, release to restore)
    Button/6  → Toggle ChatBox
    Button/7  → Set mode 1
    Button/8  → Set mode 2
    Button/9  → Set mode 3
    Button/10 → Set mode 4
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid

from command_types import CommandType

log = logging.getLogger("yokonex_vrcosc.controller")

MOTOR_NAMES = ("A", "B", "C")
MOTOR_BITS  = {"A": 1, "B": 2, "C": 4}
MAX_MODES   = 4


class _MotorCommand:
    __slots__ = ("command_type", "motor", "speed", "mode", "source_id", "timestamp")

    def __init__(self, command_type, motor, speed, mode, source_id="", timestamp=None):
        self.command_type = command_type
        self.motor        = motor
        self.speed        = speed   # int | None
        self.mode         = mode    # int | None
        self.source_id    = source_id or str(uuid.uuid4())
        self.timestamp    = timestamp or time.time()

    def __lt__(self, other):
        if self.command_type.value != other.command_type.value:
            return self.command_type.value < other.command_type.value
        return self.timestamp < other.timestamp


class ToyController:
    def __init__(self, yokonex_client, osc_client, device_address: str, ui_callback=None):
        self.client         = yokonex_client
        self.osc_client     = osc_client
        self.device_address = device_address
        self.main_window    = ui_callback

        # Motor state — all start at 0 / mode 1
        self.motor_speeds: dict[str, int] = {"A": 0, "B": 0, "C": 0}
        self.motor_modes:  dict[str, int] = {"A": 1, "B": 1, "C": 1}
        self.current_motor: str           = "A"   # controlled by Page

        # Control params
        self.fire_step   = 30
        self.adjust_step = 5

        # Feature toggles
        self.enable_chatbox     = False
        self.enable_panel       = True
        self.enable_interaction = True
        self.enable_gui         = True

        # Fire-mode state
        self._fire_pre_speed: dict[str, int] = {}
        self._fire_active = False
        self._fire_lock   = asyncio.Lock()

        # Rate-limiting
        self._source_times: dict[str, float] = {}
        self._cooldowns = {
            CommandType.GUI_COMMAND:         0.0,
            CommandType.PANEL_COMMAND:       0.1,
            CommandType.INTERACTION_COMMAND: 0.05,
        }

        # Command queue
        self._cmd_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._cmd_task   = asyncio.create_task(self._process_commands(), name="toy-cmd")
        self._chatbox_task = asyncio.create_task(self._periodic_chatbox(), name="toy-chatbox")
        self._prev_chatbox = False

    # ── Page → motor selection ────────────────────────────────────────────────

    def set_current_motor(self, page_value: int) -> None:
        idx = min(page_value, len(MOTOR_NAMES) - 1)
        self.current_motor = MOTOR_NAMES[idx]
        log.info("Current motor → %s (page %d)", self.current_motor, page_value)
        if self.main_window and hasattr(self.main_window, "controller_settings_tab"):
            self.main_window.controller_settings_tab.update_current_motor_display(self.current_motor)

    # ── OSC panel handler (SoundPad buttons) ─────────────────────────────────

    async def handle_osc_panel(self, address: str, *args) -> None:
        if not args:
            return
        value = args[0]

        if address == "/avatar/parameters/SoundPad/Page":
            self.set_current_motor(int(value))
            return
        if address == "/avatar/parameters/SoundPad/Volume":
            self.fire_step = int(value * 100)
            return
        if address == "/avatar/parameters/SoundPad/PanelControl":
            self.enable_panel = bool(value)
            return

        m = self.current_motor

        if address == "/avatar/parameters/SoundPad/Button/1":
            if value:
                new_mode = (self.motor_modes[m] % MAX_MODES) + 1
                await self._enqueue(CommandType.PANEL_COMMAND, m, None, new_mode, "panel_mode_cycle")

        elif address == "/avatar/parameters/SoundPad/Button/2":
            if value:
                await self._enqueue(CommandType.PANEL_COMMAND, m, 0, None, "panel_stop")

        elif address == "/avatar/parameters/SoundPad/Button/3":
            if value:
                spd = max(0, self.motor_speeds[m] - self.adjust_step)
                await self._enqueue(CommandType.PANEL_COMMAND, m, spd, None, "panel_dec")

        elif address == "/avatar/parameters/SoundPad/Button/4":
            if value:
                spd = min(100, self.motor_speeds[m] + self.adjust_step)
                await self._enqueue(CommandType.PANEL_COMMAND, m, spd, None, "panel_inc")

        elif address == "/avatar/parameters/SoundPad/Button/5":
            await self._fire_mode(bool(value), m)

        elif address == "/avatar/parameters/SoundPad/Button/6":
            if value:
                self.enable_chatbox = not self.enable_chatbox
                if not self.enable_chatbox:
                    self._send_chatbox("")

        elif address.startswith("/avatar/parameters/SoundPad/Button/"):
            try:
                btn = int(address.rsplit("/", 1)[-1])
            except ValueError:
                return
            if 7 <= btn <= 10 and value:
                mode = btn - 6   # 7→1, 8→2, 9→3, 10→4
                await self._enqueue(CommandType.PANEL_COMMAND, m, None, mode, "panel_mode_select")

    # ── OSC interaction handler (PhysBone / Contact) ─────────────────────────

    async def handle_osc_interaction(
        self,
        address: str,
        value: float,
        motors: list[str],
        mapping_ranges: dict | None = None,
    ) -> None:
        if mapping_ranges is None:
            mapping_ranges = {m: {"min": 0, "max": 100} for m in MOTOR_NAMES}

        for m in motors:
            if m not in MOTOR_BITS:
                continue
            r  = mapping_ranges.get(m, {"min": 0, "max": 100})
            lo = r.get("min", 0)   / 100.0
            hi = r.get("max", 100) / 100.0
            if lo > hi:
                lo, hi = hi, lo
            spd = int((lo + (hi - lo) * value) * 100)
            await self._enqueue(CommandType.INTERACTION_COMMAND, m, spd, None,
                                 f"interaction_{address}")

    # ── Fire mode ─────────────────────────────────────────────────────────────

    async def _fire_mode(self, pressed: bool, motor: str) -> None:
        async with self._fire_lock:
            if pressed:
                self._fire_pre_speed[motor] = self.motor_speeds[motor]
                target = min(100, self.motor_speeds[motor] + self.fire_step)
                await self._enqueue(CommandType.PANEL_COMMAND, motor, target, None, "fire_start")
                self._fire_active = True
            else:
                if self._fire_active:
                    original = self._fire_pre_speed.get(motor, 0)
                    await self._enqueue(CommandType.PANEL_COMMAND, motor, original, None, "fire_end")
                    self._fire_active = False

    # ── Command queue ─────────────────────────────────────────────────────────

    async def _enqueue(
        self,
        cmd_type: CommandType,
        motor: str,
        speed: int | None,
        mode: int | None,
        source_id: str = "",
    ) -> None:
        now = time.time()
        key = f"{cmd_type.name}_{source_id}"
        cooldown = self._cooldowns.get(cmd_type, 0.0)
        if cooldown and key in self._source_times and now - self._source_times[key] < cooldown:
            return
        self._source_times[key] = now
        await self._cmd_queue.put(_MotorCommand(cmd_type, motor, speed, mode, source_id, now))

    async def _process_commands(self) -> None:
        while True:
            try:
                cmd: _MotorCommand = await self._cmd_queue.get()

                # Check enabled state
                if cmd.command_type == CommandType.GUI_COMMAND and not self.enable_gui:
                    self._cmd_queue.task_done(); continue
                if cmd.command_type == CommandType.PANEL_COMMAND and not self.enable_panel:
                    self._cmd_queue.task_done(); continue
                if cmd.command_type == CommandType.INTERACTION_COMMAND and not self.enable_interaction:
                    self._cmd_queue.task_done(); continue

                # Apply mode change
                if cmd.mode is not None:
                    self.motor_modes[cmd.motor] = cmd.mode
                    try:
                        await self.client.set_mode(
                            self.device_address, MOTOR_BITS[cmd.motor], cmd.mode
                        )
                        log.info("Motor %s mode → %d", cmd.motor, cmd.mode)
                    except Exception as e:
                        log.error("set_mode error: %s", e)

                # Apply speed change
                if cmd.speed is not None:
                    self.motor_speeds[cmd.motor] = max(0, min(100, cmd.speed))
                    try:
                        await self.client.set_speed(
                            self.device_address,
                            self.motor_speeds["A"],
                            self.motor_speeds["B"],
                            self.motor_speeds["C"],
                        )
                        log.info("Speed → A:%d B:%d C:%d",
                                 self.motor_speeds["A"],
                                 self.motor_speeds["B"],
                                 self.motor_speeds["C"])
                    except Exception as e:
                        log.error("set_speed error: %s", e)

                # Notify GUI
                if self.main_window and hasattr(self.main_window, "controller_settings_tab"):
                    self.main_window.controller_settings_tab.update_motor_display(
                        self.motor_speeds, self.motor_modes
                    )

                self._cmd_queue.task_done()
            except Exception as e:
                log.error("Command processing error: %s", e)
                await asyncio.sleep(0.05)

    # ── GUI entry points ───────────────────────────────────────────────────────

    async def gui_set_speed(self, motor: str, speed: int) -> None:
        await self._enqueue(CommandType.GUI_COMMAND, motor, speed, None, f"gui_speed_{motor}")

    async def gui_set_mode(self, motor: str, mode: int) -> None:
        await self._enqueue(CommandType.GUI_COMMAND, motor, None, mode, f"gui_mode_{motor}")

    async def stop_all(self) -> None:
        for m in MOTOR_NAMES:
            self.motor_speeds[m] = 0
        try:
            await self.client.stop(self.device_address)
        except Exception as e:
            log.error("stop error: %s", e)

    # ── ChatBox ────────────────────────────────────────────────────────────────

    async def _periodic_chatbox(self) -> None:
        while True:
            try:
                if self.enable_chatbox:
                    self._send_chatbox(self._chatbox_text())
                    self._prev_chatbox = True
                elif self._prev_chatbox:
                    self._send_chatbox("")
                    self._prev_chatbox = False
            except Exception as e:
                log.error("chatbox task error: %s", e)
            await asyncio.sleep(3)

    def _chatbox_text(self) -> str:
        s = self.motor_speeds
        m = self.motor_modes[self.current_motor]
        return f"[{self.current_motor}] A:{s['A']} B:{s['B']} C:{s['C']} M:{m}"

    def _send_chatbox(self, text: str) -> None:
        self.osc_client.send_message("/chatbox/input", [text, True, False])

    # ── Cleanup ────────────────────────────────────────────────────────────────

    def cancel_tasks(self) -> None:
        for t in (self._cmd_task, self._chatbox_task):
            if t and not t.done():
                t.cancel()
