import asyncio
import os
import random
import secrets
import time
import webbrowser

import httpx

from core import BaseProvider
from config import (
    KILO_BASE_URL,
    CHAT_HEADERS_STATIC,
    MODELS_HEADERS,
    BALANCE_HEADERS,
    DEVICE_AUTH_HEADERS,
    POLL_INTERVAL,
    POLL_TIMEOUT,
)


def _generate_machine_id() -> str:
    return secrets.token_hex(32)


def _generate_task_id() -> str:
    ts_ms = int(time.time() * 1000)
    rand_bytes = os.urandom(10)

    buf = bytearray(16)
    buf[0:6] = ts_ms.to_bytes(6, "big")
    rand_a = int.from_bytes(rand_bytes[0:2], "big") & 0x0FFF
    buf[6:8] = (0x7000 | rand_a).to_bytes(2, "big")
    rand_b = int.from_bytes(rand_bytes[2:10], "big") & 0x3FFFFFFFFFFFFFFF
    buf[8:16] = (0x8000000000000000 | rand_b).to_bytes(8, "big")

    h = buf.hex()
    return f"{h[0:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


class KiloProvider(BaseProvider):
    name = "Kilo2API"

    def __init__(self):
        # Per-machineId task ID state: {machineId: {"task_id", "counter", "rotate_at"}}
        self._task_state: dict[str, dict] = {}

    def base_url(self) -> str:
        return KILO_BASE_URL

    def chat_url(self) -> str:
        return f"{KILO_BASE_URL}/api/openrouter/chat/completions"

    def models_url(self) -> str:
        return f"{KILO_BASE_URL}/api/openrouter/models"

    def _get_task_id(self, machine_id: str) -> str:
        state = self._task_state.get(machine_id)
        if state is None:
            state = {"task_id": _generate_task_id(), "counter": 0, "rotate_at": random.randint(10, 20)}
            self._task_state[machine_id] = state
        if state["counter"] >= state["rotate_at"]:
            state["task_id"] = _generate_task_id()
            state["counter"] = 0
            state["rotate_at"] = random.randint(10, 20)
        state["counter"] += 1
        return state["task_id"]

    def build_chat_headers(self, account: dict) -> dict:
        machine_id = account.get("machineId", _generate_machine_id())
        return {
            **CHAT_HEADERS_STATIC,
            "authorization": f"Bearer {account['token']}",
            "X-KiloCode-MachineId": machine_id,
            "X-KiloCode-TaskId": self._get_task_id(machine_id),
        }

    def build_models_headers(self, account: dict) -> dict:
        return {
            **MODELS_HEADERS,
            "Authorization": f"Bearer {account['token']}",
        }

    def transform_models(self, raw_data: dict) -> list[dict]:
        models = []
        for m in raw_data.get("data", []):
            models.append({
                "id": m["id"],
                "object": "model",
                "created": m.get("created", 0),
                "owned_by": m["id"].split("/")[0] if "/" in m["id"] else "unknown",
            })
        return models

    def on_account_add(self, account: dict) -> dict:
        if not account.get("machineId"):
            account["machineId"] = _generate_machine_id()
        return account

    def balance_url(self) -> str | None:
        return f"{KILO_BASE_URL}/api/profile/balance"

    def build_balance_headers(self, account: dict) -> dict:
        return {
            **BALANCE_HEADERS,
            "Authorization": f"Bearer {account['token']}",
        }

    def parse_balance(self, status_code: int, data: dict) -> dict:
        if status_code == 200:
            return {
                "balance": data.get("balance"),
                "isDepleted": data.get("isDepleted", False),
            }
        return {"balance": None, "error": f"HTTP {status_code}"}

    async def start_login(self) -> dict:
        async with httpx.AsyncClient(timeout=30) as client:
            print("[*] Requesting device code...")
            resp = await client.post(
                f"{KILO_BASE_URL}/api/device-auth/codes",
                headers=DEVICE_AUTH_HEADERS,
            )
            resp.raise_for_status()
            code_data = resp.json()

            device_code = code_data["code"]
            verification_url = code_data["verificationUrl"]
            expires_in = code_data["expiresIn"]

            print(f"[*] Device code: {device_code}")
            print(f"[*] Please visit: {verification_url}")
            print(f"[*] Code expires in {expires_in} seconds")

            try:
                webbrowser.open(verification_url)
                print("[*] Browser opened automatically")
            except Exception:
                print("[!] Could not open browser, please visit the URL manually")

            return {
                "code": device_code,
                "url": verification_url,
                "expires_in": expires_in,
            }

    async def poll_login(self, code: str) -> dict | None:
        async with httpx.AsyncClient(timeout=30) as client:
            poll_resp = await client.get(
                f"{KILO_BASE_URL}/api/device-auth/codes/{code}",
                headers={
                    "accept": "*/*",
                    "accept-language": "*",
                    "sec-fetch-mode": "cors",
                    "user-agent": "node",
                },
            )

            if poll_resp.status_code == 202:
                return None

            if poll_resp.status_code == 200:
                poll_data = poll_resp.json()
                if poll_data.get("status") == "approved":
                    print(f"[+] Login approved! User: {poll_data.get('userEmail')}")
                    return poll_data

            return None

    async def cli_login(self) -> dict:
        """Full CLI login flow with polling (used by --login and auto-login)."""
        login_data = await self.start_login()
        device_code = login_data["code"]
        expires_in = login_data["expires_in"]

        print("[*] Waiting for approval...")
        deadline = time.time() + min(expires_in, POLL_TIMEOUT)

        while time.time() < deadline:
            await asyncio.sleep(POLL_INTERVAL)
            result = await self.poll_login(device_code)
            if result is not None:
                return result
            print(".", end="", flush=True)

        raise TimeoutError("Device auth timed out or was rejected")
