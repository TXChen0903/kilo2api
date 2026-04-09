import asyncio
import json
import os
import random
from pathlib import Path

from .provider import BaseProvider

_DATA_DIR = Path(os.environ.get("ACCOUNTS_DIR", Path.cwd()))
_STRATEGY = os.environ.get("ROTATION_STRATEGY", "round_robin")
_BALANCE_REFRESH_INTERVAL = int(os.environ.get("BALANCE_REFRESH_INTERVAL", 300))  # seconds


class AccountManager:
    """Generic account manager with round-robin/random rotation.

    Rotation rules:
    - Free models (model name contains "free"): only accounts with balance < 1
    - Non-free models: only accounts with balance >= 1
    - If no matching accounts, falls back to all enabled accounts
    """

    def __init__(self):
        self.accounts: list[dict] = []
        self._index: int = 0
        self._index_free: int = 0
        self._file: Path | None = None
        self._balance_cache: dict[str, float] = {}  # userId -> balance
        self._refresh_task: asyncio.Task | None = None

    def load(self, file_path: Path | None = None):
        self._file = file_path or _DATA_DIR / "accounts.json"
        if self._file.exists():
            self.accounts = json.loads(self._file.read_text(encoding="utf-8"))

    def save(self):
        if self._file:
            self._file.write_text(
                json.dumps(self.accounts, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

    def add(self, account_data: dict, provider: BaseProvider | None = None):
        if provider:
            account_data = provider.on_account_add(account_data)
        user_id = account_data.get("userId")
        if user_id:
            self.accounts = [a for a in self.accounts if a.get("userId") != user_id]
        self.accounts.append(account_data)
        self.save()
        print(f"[+] Account added: {account_data.get('userEmail', 'unknown')} (total: {len(self.accounts)})")

    def remove(self, identifier: str) -> bool:
        try:
            idx = int(identifier)
            if 0 <= idx < len(self.accounts):
                removed = self.accounts.pop(idx)
                self.save()
                print(f"[-] Removed account: {removed.get('userEmail', 'unknown')}")
                return True
            print(f"[!] Index {idx} out of range (0-{len(self.accounts) - 1})")
            return False
        except ValueError:
            pass
        for i, a in enumerate(self.accounts):
            if a.get("userEmail") == identifier:
                self.accounts.pop(i)
                self.save()
                print(f"[-] Removed account: {identifier}")
                return True
        print(f"[!] Account not found: {identifier}")
        return False

    def list_accounts(self):
        if not self.accounts:
            print("[!] No accounts configured.")
            return
        print(f"[*] {len(self.accounts)} account(s):")
        for i, a in enumerate(self.accounts):
            print(f"  [{i}] {a.get('userEmail', 'unknown')}")

    @staticmethod
    def _is_free_model(model: str) -> bool:
        """Check if the model name indicates a free model (contains 'free')."""
        return bool(model and "free" in model.lower())

    def _get_balance(self, account: dict) -> float:
        """Get account balance from cache. Returns 0.0 if not cached."""
        user_id = account.get("userId", "")
        return self._balance_cache.get(user_id, 0.0)

    async def refresh_balances(self, http_client, provider: BaseProvider):
        """Fetch balance for all accounts via API and update cache."""
        balance_url = provider.balance_url()
        if balance_url is None:
            print("[!] Provider does not support balance queries")
            return

        for account in self.accounts:
            user_id = account.get("userId", "")
            try:
                headers = provider.build_balance_headers(account)
                resp = await http_client.get(balance_url, headers=headers, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    balance = data.get("balance", 0)
                    self._balance_cache[user_id] = float(balance) if balance is not None else 0.0
                else:
                    print(f"[!] Balance query failed for {account.get('userEmail', 'unknown')}: HTTP {resp.status_code}")
            except Exception as e:
                print(f"[!] Balance query error for {account.get('userEmail', 'unknown')}: {e}")

        print(f"[*] Balance cache refreshed: {len(self._balance_cache)} account(s)")

    async def start_balance_refresh(self, http_client, provider: BaseProvider):
        """Start periodic balance refresh in background."""
        await self.refresh_balances(http_client, provider)
        self._refresh_task = asyncio.create_task(self._periodic_refresh(http_client, provider))

    async def _periodic_refresh(self, http_client, provider: BaseProvider):
        """Periodically refresh balances."""
        while True:
            await asyncio.sleep(_BALANCE_REFRESH_INTERVAL)
            try:
                await self.refresh_balances(http_client, provider)
            except Exception as e:
                print(f"[!] Periodic balance refresh error: {e}")

    async def stop_balance_refresh(self):
        """Stop the periodic balance refresh task."""
        if self._refresh_task:
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass
            self._refresh_task = None

    def next(self, model: str = "") -> dict | None:
        enabled = [a for a in self.accounts if a.get("enabled", True)]
        if not enabled:
            return None

        # Filter accounts by balance based on model type
        is_free = self._is_free_model(model)
        if is_free:
            filtered = [a for a in enabled if self._get_balance(a) < 1]
        else:
            filtered = [a for a in enabled if self._get_balance(a) >= 1]

        # Fall back to all enabled accounts if no matching accounts
        pool = filtered if filtered else enabled

        if _STRATEGY == "random":
            return random.choice(pool)

        # Use separate index for free vs non-free to avoid interference
        if is_free:
            account = pool[self._index_free % len(pool)]
            self._index_free += 1
        else:
            account = pool[self._index % len(pool)]
            self._index += 1
        return account

    def get_any_account(self) -> dict | None:
        enabled = [a for a in self.accounts if a.get("enabled", True)]
        return enabled[0] if enabled else None
