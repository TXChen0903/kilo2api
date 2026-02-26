from abc import ABC, abstractmethod


class BaseProvider(ABC):
    """Abstract base class for API providers.

    Subclass this and implement all abstract methods to create
    a new "xxx2api" provider.
    """

    name: str = "API2API"

    @abstractmethod
    def base_url(self) -> str:
        ...

    @abstractmethod
    def chat_url(self) -> str:
        ...

    @abstractmethod
    def models_url(self) -> str:
        ...

    @abstractmethod
    def build_chat_headers(self, account: dict) -> dict:
        ...

    @abstractmethod
    def build_models_headers(self, account: dict) -> dict:
        ...

    @abstractmethod
    def transform_models(self, raw_data: dict) -> list[dict]:
        ...

    @abstractmethod
    async def start_login(self) -> dict:
        """Start a login flow.
        Returns {"code": str, "url": str, "expires_in": int}
        """
        ...

    @abstractmethod
    async def poll_login(self, code: str) -> dict | None:
        """Poll login status. Returns account dict if approved, None if pending."""
        ...

    # --- Optional overrides ---

    def transform_request(self, body: dict) -> dict:
        return body

    def balance_url(self) -> str | None:
        return None

    def build_balance_headers(self, account: dict) -> dict:
        return {}

    def parse_balance(self, status_code: int, data: dict) -> dict:
        return {}

    def on_account_add(self, account: dict) -> dict:
        return account

    async def cli_login(self) -> dict:
        """Full CLI login flow with polling. Override for custom behavior.
        Default implementation calls start_login() then polls poll_login() every 3s.
        Returns account dict on success.
        """
        import asyncio

        login_data = await self.start_login()
        code = login_data["code"]
        expires_in = login_data["expires_in"]

        import time
        print("[*] Waiting for approval...")
        deadline = time.time() + min(expires_in, 600)

        while time.time() < deadline:
            await asyncio.sleep(3)
            result = await self.poll_login(code)
            if result is not None:
                return result
            print(".", end="", flush=True)

        raise TimeoutError("Login timed out or was rejected")
