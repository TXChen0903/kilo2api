import argparse
import os
from contextlib import asynccontextmanager

import httpx
import uvicorn
from fastapi import FastAPI

from .provider import BaseProvider
from .account_manager import AccountManager
from .routes import proxy, accounts, frontend


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http_client = httpx.AsyncClient(timeout=httpx.Timeout(300, connect=10))
    # Start periodic balance refresh
    account_manager = app.state.account_manager
    provider = app.state.provider
    if account_manager.accounts:
        await account_manager.start_balance_refresh(app.state.http_client, provider)
    yield
    # Stop balance refresh and close HTTP client
    await account_manager.stop_balance_refresh()
    await app.state.http_client.aclose()


def create_app(provider: BaseProvider) -> FastAPI:
    app = FastAPI(title=provider.name, lifespan=lifespan)
    app.state.provider = provider
    app.state.account_manager = AccountManager()
    app.include_router(proxy.router)
    app.include_router(accounts.router)
    app.include_router(frontend.router)
    return app


async def run(provider: BaseProvider):
    default_port = int(os.environ.get("PORT", 9090))
    default_host = os.environ.get("HOST", "0.0.0.0")

    parser = argparse.ArgumentParser(description=f"{provider.name} - OpenAI compatible proxy")
    parser.add_argument("--login", action="store_true", help="Add a new account via login flow")
    parser.add_argument("--list", action="store_true", help="List all configured accounts")
    parser.add_argument("--remove", type=str, metavar="INDEX_OR_EMAIL", help="Remove an account by index or email")
    parser.add_argument("--port", type=int, default=default_port, help=f"Server port (default: {default_port})")
    parser.add_argument("--host", default=default_host, help=f"Server host (default: {default_host})")
    args = parser.parse_args()

    app = create_app(provider)
    account_manager = app.state.account_manager
    account_manager.load()

    if args.list:
        account_manager.list_accounts()
        return

    if args.remove is not None:
        account_manager.remove(args.remove)
        return

    if args.login:
        token_data = await provider.cli_login()
        account_manager.add(token_data, provider)
        print("[+] Login complete. You can now start the server.")
        return

    if not account_manager.accounts:
        print("[!] No accounts found. Starting login flow...")
        token_data = await provider.cli_login()
        account_manager.add(token_data, provider)

    count = len(account_manager.accounts)
    emails = [a.get("userEmail", "unknown") for a in account_manager.accounts]
    print(f"[+] Loaded {count} account(s): {', '.join(emails)}")
    print(f"[*] Starting server on {args.host}:{args.port}")
    print(f"[*] OpenAI base URL: http://localhost:{args.port}/v1")

    config = uvicorn.Config(app, host=args.host, port=args.port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()
