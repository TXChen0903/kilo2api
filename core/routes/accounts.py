import asyncio
import time

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter()

_login_tasks: dict[str, dict] = {}


@router.get("/api/accounts")
async def api_list_accounts(request: Request):
    account_manager = request.app.state.account_manager
    result = []
    for i, a in enumerate(account_manager.accounts):
        result.append({
            "index": i,
            "email": a.get("userEmail", "unknown"),
            "userId": a.get("userId", ""),
            "enabled": a.get("enabled", True),
        })
    return {"accounts": result}


@router.delete("/api/accounts/{index}")
async def api_remove_account(index: int, request: Request):
    account_manager = request.app.state.account_manager
    if 0 <= index < len(account_manager.accounts):
        removed = account_manager.accounts.pop(index)
        account_manager.save()
        return {"ok": True, "removed": removed.get("userEmail", "unknown")}
    return JSONResponse(status_code=404, content={"error": "Account not found"})


@router.post("/api/accounts/{index}/enable")
async def api_enable_account(index: int, request: Request):
    account_manager = request.app.state.account_manager
    if 0 <= index < len(account_manager.accounts):
        account_manager.accounts[index]["enabled"] = True
        account_manager.save()
        return {"ok": True}
    return JSONResponse(status_code=404, content={"error": "Account not found"})


@router.post("/api/accounts/{index}/disable")
async def api_disable_account(index: int, request: Request):
    account_manager = request.app.state.account_manager
    if 0 <= index < len(account_manager.accounts):
        account_manager.accounts[index]["enabled"] = False
        account_manager.save()
        return {"ok": True}
    return JSONResponse(status_code=404, content={"error": "Account not found"})


@router.get("/api/accounts/balance")
async def api_accounts_balance(request: Request):
    provider = request.app.state.provider
    account_manager = request.app.state.account_manager
    http_client = request.app.state.http_client

    balance_url = provider.balance_url()
    if balance_url is None:
        return {"balances": []}

    async def fetch_one(index: int, account: dict) -> dict:
        try:
            headers = provider.build_balance_headers(account)
            resp = await http_client.get(balance_url, headers=headers, timeout=10)
            data = resp.json() if resp.status_code == 200 else {}
            return {"index": index, **provider.parse_balance(resp.status_code, data)}
        except Exception as e:
            return {"index": index, "balance": None, "error": str(e)}

    tasks = [fetch_one(i, a) for i, a in enumerate(account_manager.accounts)]
    results = await asyncio.gather(*tasks)
    return {"balances": list(results)}


@router.post("/api/accounts/login")
async def api_start_login(request: Request):
    provider = request.app.state.provider
    login_data = await provider.start_login()

    code = login_data["code"]
    _login_tasks[code] = {
        "status": "pending",
        "verificationUrl": login_data["url"],
        "expiresAt": time.time() + login_data["expires_in"],
    }

    return {
        "deviceCode": code,
        "verificationUrl": login_data["url"],
        "expiresIn": login_data["expires_in"],
    }


@router.get("/api/accounts/login/{device_code}")
async def api_poll_login(device_code: str, request: Request):
    provider = request.app.state.provider
    account_manager = request.app.state.account_manager

    task = _login_tasks.get(device_code)
    if not task:
        return JSONResponse(status_code=404, content={"error": "Unknown device code"})

    if time.time() > task["expiresAt"]:
        _login_tasks.pop(device_code, None)
        return JSONResponse(status_code=410, content={"error": "Device code expired"})

    result = await provider.poll_login(device_code)
    if result is None:
        return {"status": "pending"}

    account_manager.add(result, provider)
    _login_tasks.pop(device_code, None)
    return {"status": "approved", "email": result.get("userEmail", "unknown")}
