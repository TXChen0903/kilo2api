import json
import os
import random
from pathlib import Path

from .provider import BaseProvider

_DATA_DIR = Path(os.environ.get("ACCOUNTS_DIR", Path.cwd()))
_STRATEGY = os.environ.get("ROTATION_STRATEGY", "round_robin")


class AccountManager:
    """Generic account manager with round-robin/random rotation."""

    def __init__(self):
        self.accounts: list[dict] = []
        self._index: int = 0
        self._file: Path | None = None

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

    def next(self) -> dict | None:
        enabled = [a for a in self.accounts if a.get("enabled", True)]
        if not enabled:
            return None
        if _STRATEGY == "random":
            return random.choice(enabled)
        account = enabled[self._index % len(enabled)]
        self._index += 1
        return account

    def get_any_account(self) -> dict | None:
        enabled = [a for a in self.accounts if a.get("enabled", True)]
        return enabled[0] if enabled else None
