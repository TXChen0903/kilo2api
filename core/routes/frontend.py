from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter()

_CORE_STATIC_DIR = Path(__file__).parent.parent / "static"
_PROJECT_STATIC_DIR = Path(__file__).parent.parent.parent / "static"


@router.get("/")
async def root(request: Request):
    provider = request.app.state.provider
    account_manager = request.app.state.account_manager

    # 项目级 static/ 优先，fallback 到 core/static/
    html_path = _PROJECT_STATIC_DIR / "index.html"
    if not html_path.exists():
        html_path = _CORE_STATIC_DIR / "index.html"
    if html_path.exists():
        html = html_path.read_text(encoding="utf-8")
        html = html.replace("{{TITLE}}", provider.name)
        return HTMLResponse(content=html)

    count = len(account_manager.accounts)
    emails = [a.get("userEmail", "unknown") for a in account_manager.accounts]
    return {
        "status": "ok",
        "message": f"{provider.name} - OpenAI compatible proxy",
        "accounts": count,
        "emails": emails,
    }
