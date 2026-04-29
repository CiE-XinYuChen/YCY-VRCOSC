"""yokonex_client.py - Async WebSocket client for the YokoNex BLE server.

Supports two connection modes:
  Direct  — connects straight to yokonex server (ws://127.0.0.1:8765)
  Relay   — connects via YokoNex-Cloud relay:
              1. send client_hello  (auth)
              2. send subscribe     (bind to an agent)
            Both steps complete before the recv loop starts.
"""
from __future__ import annotations

import asyncio
import json
import logging

import websockets

log = logging.getLogger("yokonex_vrcosc.ws")


class YokoNexClient:
    def __init__(self, url: str = "ws://127.0.0.1:8765") -> None:
        self.url = url
        self._ws = None
        self._pending: dict[int, asyncio.Future] = {}
        self._counter = 0
        self._recv_task: asyncio.Task | None = None
        self._event_handlers: list = []
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

    def add_event_handler(self, handler) -> None:
        self._event_handlers.append(handler)

    # ── Connection ────────────────────────────────────────────────────────────

    async def connect(self) -> bool:
        """Connect directly to a yokonex WS server (no auth required)."""
        try:
            self._ws = await websockets.connect(self.url, open_timeout=5)
            loop = asyncio.get_running_loop()
            self._recv_task = loop.create_task(self._recv_loop(), name="yokonex-recv")
            self._connected = True
            log.info("Connected (direct) to %s", self.url)
            return True
        except Exception as e:
            log.error("Cannot connect to YokoNex: %s", e)
            self._connected = False
            return False

    async def connect_relay(self, token: str, agent_id: str) -> bool:
        """Connect via YokoNex-Cloud relay: auth → subscribe → start recv loop."""
        try:
            self._ws = await websockets.connect(self.url, open_timeout=5)

            # Step 1: authenticate
            await self._ws.send(json.dumps({"type": "client_hello", "token": token}))
            raw   = await asyncio.wait_for(self._ws.recv(), timeout=5)
            hello = json.loads(raw)
            if not hello.get("ok"):
                log.error("Relay auth failed: %s", hello.get("message"))
                await self._ws.close()
                return False

            # Step 2: subscribe to agent
            self._counter += 1
            req_id = self._counter
            await self._ws.send(json.dumps({
                "id":       req_id,
                "type":     "subscribe",
                "agent_id": agent_id,
            }))
            raw  = await asyncio.wait_for(self._ws.recv(), timeout=5)
            resp = json.loads(raw)
            if not resp.get("ok"):
                log.error("Relay subscribe failed: %s", resp.get("error"))
                await self._ws.close()
                return False

            loop = asyncio.get_running_loop()
            self._recv_task = loop.create_task(self._recv_loop(), name="yokonex-recv")
            self._connected = True
            log.info("Connected (relay) to %s  agent=%s", self.url, agent_id)
            return True

        except Exception as e:
            log.error("Cannot connect via relay: %s", e)
            self._connected = False
            return False

    async def list_agents(self) -> list:
        """List agents registered on the relay (only valid in relay mode)."""
        self._counter += 1
        req_id = self._counter
        loop   = asyncio.get_running_loop()
        fut    = loop.create_future()
        self._pending[req_id] = fut
        await self._ws.send(json.dumps({"id": req_id, "type": "list_agents"}))
        resp = await asyncio.wait_for(fut, timeout=10)
        return resp.get("agents", [])

    # ── Recv loop ─────────────────────────────────────────────────────────────

    async def _recv_loop(self) -> None:
        try:
            async for raw in self._ws:
                data = json.loads(raw)
                if data.get("type") == "event":
                    for h in list(self._event_handlers):
                        asyncio.create_task(h(data))
                else:
                    req_id = data.get("id")
                    if req_id in self._pending:
                        fut = self._pending.pop(req_id)
                        if not fut.done():
                            fut.set_result(data)
        except Exception as e:
            log.warning("Recv loop ended: %s", e)
        finally:
            self._connected = False
            for fut in list(self._pending.values()):
                if not fut.done():
                    fut.cancel()
            self._pending.clear()

    # ── Commands ──────────────────────────────────────────────────────────────

    async def _send(self, kind: str, params: dict, timeout: float = 10.0) -> dict:
        self._counter += 1
        req_id = self._counter
        loop = asyncio.get_running_loop()
        fut = loop.create_future()
        self._pending[req_id] = fut
        await self._ws.send(json.dumps({"id": req_id, "type": kind, "params": params}))
        return await asyncio.wait_for(fut, timeout=timeout)

    async def scan(self, duration: float = 5.0) -> list:
        resp = await self._send("scan", {"duration": duration}, timeout=duration + 5)
        return resp.get("devices", [])

    async def connect_device(self, address: str, name: str = "", device_type: str = "toy") -> dict:
        return await self._send("connect", {"address": address, "name": name, "device_type": device_type})

    async def disconnect_device(self, address: str) -> dict:
        return await self._send("disconnect", {"address": address})

    async def list_devices(self) -> list:
        resp = await self._send("list_devices", {})
        return resp.get("devices", [])

    async def command(self, address: str, action: str, data: dict | None = None) -> dict:
        return await self._send("command", {"address": address, "action": action, "data": data or {}})

    async def set_speed(self, address: str, motor_a: int, motor_b: int, motor_c: int) -> dict:
        return await self.command(address, "set_speed",
                                  {"motor_a": motor_a, "motor_b": motor_b, "motor_c": motor_c})

    async def set_mode(self, address: str, motors: int, mode: int) -> dict:
        return await self.command(address, "set_mode", {"motors": motors, "mode": mode})

    async def stop(self, address: str) -> dict:
        return await self.command(address, "stop")

    async def close(self) -> None:
        self._connected = False
        if self._recv_task:
            self._recv_task.cancel()
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass

