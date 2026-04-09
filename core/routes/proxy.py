import json
import os
import time

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse, JSONResponse

router = APIRouter()

MAX_RETRIES = int(os.environ.get("MAX_RETRIES", 3))
MODELS_CACHE_TTL = int(os.environ.get("MODELS_CACHE_TTL", 600))

_models_cache: dict | None = None
_models_cache_time: float = 0


@router.get("/v1/models")
async def list_models(request: Request):
    global _models_cache, _models_cache_time

    provider = request.app.state.provider
    account_manager = request.app.state.account_manager

    now = time.time()
    if _models_cache is not None and (now - _models_cache_time) < MODELS_CACHE_TTL:
        return _models_cache

    account = account_manager.get_any_account()
    if account is None:
        return {"object": "list", "data": []}

    headers = provider.build_models_headers(account)
    http_client = request.app.state.http_client

    resp = await http_client.get(provider.models_url(), headers=headers)
    resp.raise_for_status()

    models = provider.transform_models(resp.json())
    _models_cache = {"object": "list", "data": models}
    _models_cache_time = now
    print(f"[*] Models cache refreshed: {len(models)} models")
    return _models_cache


@router.post("/v1/chat/completions")
async def chat_completions(request: Request):
    provider = request.app.state.provider
    account_manager = request.app.state.account_manager
    http_client = request.app.state.http_client

    body = await request.json()
    model_name = body.get("model", "")
    body = provider.transform_request(body)

    account = account_manager.next(model=model_name)
    if account is None:
        return JSONResponse(
            status_code=503,
            content={"error": {"message": "No enabled accounts available", "type": "server_error"}},
        )

    is_stream = body.get("stream", False)

    if is_stream:
        if "stream_options" not in body:
            body["stream_options"] = {"include_usage": True}

        async def stream_generator():
            last_error = None
            last_status = 500
            current_account = account

            for attempt in range(MAX_RETRIES + 1):
                headers = provider.build_chat_headers(current_account)
                async with http_client.stream(
                    "POST",
                    provider.chat_url(),
                    headers=headers,
                    json=body,
                ) as resp:
                    if resp.status_code != 200:
                        last_status = resp.status_code
                        error_body = await resp.aread()
                        last_error = error_body.decode()
                        print(f"[!] Request failed (attempt {attempt + 1}/{MAX_RETRIES + 1}), status {resp.status_code}, switching account...")
                        current_account = account_manager.next(model=model_name)
                        if current_account is None:
                            break
                        continue

                    async for line in resp.aiter_lines():
                        if line.strip():
                            yield f"{line}\n\n"
                    return

            yield f"data: {json.dumps({'error': {'message': last_error or 'All retries exhausted', 'type': 'upstream_error', 'code': last_status}})}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            stream_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    else:
        last_error_text = None
        last_status = 500
        current_account = account

        for attempt in range(MAX_RETRIES + 1):
            headers = provider.build_chat_headers(current_account)
            resp = await http_client.post(
                provider.chat_url(),
                headers=headers,
                json=body,
            )

            if resp.status_code == 200:
                return JSONResponse(content=resp.json())

            last_status = resp.status_code
            last_error_text = resp.text
            print(f"[!] Request failed (attempt {attempt + 1}/{MAX_RETRIES + 1}), status {resp.status_code}, switching account...")
            current_account = account_manager.next(model=model_name)
            if current_account is None:
                break

        return JSONResponse(
            status_code=last_status,
            content={"error": {"message": last_error_text or "All retries exhausted", "type": "upstream_error"}},
        )
