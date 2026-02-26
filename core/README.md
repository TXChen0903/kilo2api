# core/ — 通用 2API 框架

将任意第三方 API 转换为 OpenAI 兼容接口的框架。只需实现一个 `BaseProvider` 子类即可创建新的 `xxx2api` 项目。

---

## 快速开始

创建一个新的 `foo2api` 项目只需 3 个文件：

### 1. `provider.py` — 实现 Provider

```python
import httpx
from core import BaseProvider


class FooProvider(BaseProvider):
    name = "Foo2API"  # 显示名称，用于前端标题和 CLI 描述

    def base_url(self) -> str:
        return "https://api.foo.com"

    def chat_url(self) -> str:
        return "https://api.foo.com/v1/chat/completions"

    def models_url(self) -> str:
        return "https://api.foo.com/v1/models"

    def build_chat_headers(self, account: dict) -> dict:
        return {
            "Authorization": f"Bearer {account['token']}",
            "Content-Type": "application/json",
        }

    def build_models_headers(self, account: dict) -> dict:
        return {
            "Authorization": f"Bearer {account['token']}",
        }

    def transform_models(self, raw_data: dict) -> list[dict]:
        # 将上游模型列表转换为 OpenAI 格式
        return [
            {
                "id": m["id"],
                "object": "model",
                "created": m.get("created", 0),
                "owned_by": "foo",
            }
            for m in raw_data.get("data", [])
        ]

    async def start_login(self) -> dict:
        # 发起登录流程，返回标准格式
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post("https://api.foo.com/auth/device-code")
            resp.raise_for_status()
            data = resp.json()
            return {
                "code": data["device_code"],      # 必须
                "url": data["verification_url"],   # 必须
                "expires_in": data["expires_in"],  # 必须，秒数
            }

    async def poll_login(self, code: str) -> dict | None:
        # 轮询登录状态
        # 返回 account dict（至少包含 "token" 和 "userEmail"）= 登录成功
        # 返回 None = 仍在等待
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(f"https://api.foo.com/auth/device-code/{code}")
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "approved":
                    return data  # 必须包含 "token" 字段
            return None
```

### 2. `main.py` — 入口

```python
import asyncio
from core import run
from provider import FooProvider

if __name__ == "__main__":
    asyncio.run(run(FooProvider()))
```

### 3. `config.py`（可选）— Provider 专有常量

```python
FOO_BASE_URL = "https://api.foo.com"
# 把 headers、轮询间隔等专有常量放这里，provider.py 引用
```

---

## BaseProvider 接口参考

### 必须实现的抽象方法

| 方法 | 签名 | 说明 |
|------|------|------|
| `base_url` | `() -> str` | 上游 API 基础 URL |
| `chat_url` | `() -> str` | chat completions 完整 URL |
| `models_url` | `() -> str` | models 列表完整 URL |
| `build_chat_headers` | `(account: dict) -> dict` | 为 chat 请求构造完整 headers |
| `build_models_headers` | `(account: dict) -> dict` | 为 models 请求构造完整 headers |
| `transform_models` | `(raw_data: dict) -> list[dict]` | 将上游模型响应转为 OpenAI 格式的 model 列表 |
| `start_login` | `async () -> dict` | 发起登录，返回 `{"code", "url", "expires_in"}` |
| `poll_login` | `async (code: str) -> dict \| None` | 轮询登录状态，成功返回 account dict，等待中返回 None |

### 可选覆盖的方法

| 方法 | 默认行为 | 说明 |
|------|---------|------|
| `transform_request(body)` | 原样返回 | 在发送到上游前修改请求体（如注入参数、重写字段） |
| `balance_url()` | 返回 None（禁用余额查询） | 余额查询 URL。返回 None 则前端不显示余额 |
| `build_balance_headers(account)` | 空 dict | 余额查询请求 headers |
| `parse_balance(status_code, data)` | 空 dict | 解析余额响应，返回 `{"balance": float, ...}` |
| `on_account_add(account)` | 原样返回 | 新账户入库前的钩子（如自动生成 machineId） |
| `cli_login()` | 调用 `start_login()` 然后每 3 秒调用 `poll_login()` | CLI 完整登录流程。若上游有特殊轮询逻辑可覆盖 |

### account dict 规范

account 是一个普通 dict，存储在 `accounts.json` 中。框架只要求：

- **`token`**（str）— 必须存在，用于 `build_chat_headers` / `build_models_headers`
- **`userEmail`**（str）— 建议存在，用于前端显示和 CLI 列表
- **`userId`**（str）— 建议存在，用于去重（同 userId 的账户会被覆盖）
- **`enabled`**（bool）— 可选，默认 True。前端可切换

Provider 可以在 account 中存储任意额外字段（如 `machineId`、`refreshToken` 等），框架会原样持久化。

---

## 框架自动提供的功能

### API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `GET /` | — | 前端仪表盘（替换 `{{TITLE}}` 为 `provider.name`） |
| `GET /v1/models` | — | 模型列表（带缓存） |
| `POST /v1/chat/completions` | — | Chat 代理（支持 stream/non-stream，自动重试 + 账户轮换） |
| `GET /api/accounts` | — | 列出所有账户 |
| `DELETE /api/accounts/{index}` | — | 删除账户 |
| `POST /api/accounts/{index}/enable` | — | 启用账户 |
| `POST /api/accounts/{index}/disable` | — | 禁用账户 |
| `GET /api/accounts/balance` | — | 查询所有账户余额（并行） |
| `POST /api/accounts/login` | — | 发起登录流程 |
| `GET /api/accounts/login/{device_code}` | — | 轮询登录状态 |

### CLI 参数

```
python main.py              # 启动服务器（无账户时自动登录）
python main.py --login      # 添加新账户
python main.py --list       # 列出所有账户
python main.py --remove 0   # 按索引删除账户
python main.py --remove foo@bar.com  # 按邮箱删除
python main.py --port 8080  # 指定端口
python main.py --host 127.0.0.1  # 指定监听地址
```

### 代理行为

- **重试**：chat 请求失败时自动切换到下一个账户重试，最多 `MAX_RETRIES` 次
- **轮换**：支持 `round_robin`（默认）和 `random` 两种策略
- **缓存**：models 列表缓存 `MODELS_CACHE_TTL` 秒
- **流式**：自动处理 SSE 流式响应和非流式响应

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `PORT` | `9090` | 服务端口 |
| `HOST` | `0.0.0.0` | 监听地址 |
| `ACCOUNTS_DIR` | 当前工作目录 | `accounts.json` 存放目录 |
| `MAX_RETRIES` | `3` | 请求失败重试次数 |
| `ROTATION_STRATEGY` | `round_robin` | 账户轮换策略（`round_robin` / `random`） |
| `MODELS_CACHE_TTL` | `600` | 模型列表缓存秒数 |

---

## 请求处理流程

```
客户端 POST /v1/chat/completions
  │
  ├── body = provider.transform_request(original_body)
  ├── account = account_manager.next()        # 轮换选一个账户
  ├── headers = provider.build_chat_headers(account)
  ├── 请求 provider.chat_url()
  │
  ├── 成功 → 返回响应（流式或非流式）
  └── 失败 → 切换账户重试（最多 MAX_RETRIES 次）
```

```
客户端 GET /v1/models
  │
  ├── 检查缓存（TTL 内直接返回）
  ├── account = account_manager.get_any_account()
  ├── headers = provider.build_models_headers(account)
  ├── 请求 provider.models_url()
  └── models = provider.transform_models(raw_data)
```

---

## 前端仪表盘

框架内置了一个默认的前端仪表盘（`core/static/index.html`），`GET /` 时自动渲染并将 `{{TITLE}}` 替换为 `provider.name`。

查找优先级：
1. **项目级** `static/index.html`（项目根目录）— 如果存在则优先使用
2. **框架内置** `core/static/index.html`（fallback）

如需自定义前端，在项目根目录创建 `static/index.html` 即可覆盖。模板中可用的占位符：

- `{{TITLE}}` — 替换为 `provider.name`（如 `"Foo2API"`）

前端通过 `/api/accounts` 系列端点与后端交互，这些端点是框架自动注册的，无需额外配置。

---

## 项目结构模板

```
foo2api/
├── core/                  # 直接复制此目录（不要修改）
│   ├── __init__.py
│   ├── provider.py
│   ├── account_manager.py
│   ├── app.py
│   ├── static/
│   │   └── index.html     # 框架内置前端（使用 {{TITLE}} 占位符）
│   └── routes/
│       ├── __init__.py
│       ├── proxy.py
│       ├── accounts.py
│       └── frontend.py
├── provider.py            # FooProvider(BaseProvider)
├── config.py              # Foo 专有常量（可选）
├── main.py                # 入口：3 行代码
├── static/                # （可选）自定义前端，覆盖框架内置
│   └── index.html
├── requirements.txt       # fastapi, uvicorn, httpx
├── Dockerfile
└── docker-compose.yml
```

---

## 完整示例：KiloProvider

参考本项目的 `provider.py`，它演示了：

- 自定义 headers 构造（含动态字段如 `machineId`、`taskId`）
- Provider 内部状态管理（`_task_state` 用于 taskId 轮换）
- `on_account_add` 钩子（自动生成 `machineId`）
- 余额查询（`balance_url` + `build_balance_headers` + `parse_balance`）
- Device auth 登录流程（`start_login` + `poll_login`）
- 覆盖 `cli_login` 使用自定义轮询间隔和超时

---

## 常见问题

**Q: 如何在 Provider 中维护状态？**
A: 在 `__init__` 中初始化实例变量即可。Provider 是单例，整个生命周期中只创建一次。

**Q: account 可以存储哪些字段？**
A: 任意字段。框架只读取 `token`、`userEmail`、`userId`、`enabled`。其余字段原样持久化到 `accounts.json`，Provider 可在 `build_chat_headers` 等方法中自由读取。

**Q: 如何自定义请求体？**
A: 覆盖 `transform_request(body)`。比如注入默认参数、重写模型名、添加系统提示等。

**Q: 如何禁用余额功能？**
A: 不覆盖 `balance_url()`（默认返回 None）即可。前端会自动隐藏余额列。

**Q: 如何使用不同的登录方式（非 device auth）？**
A: `start_login` 和 `poll_login` 是完全灵活的。只要 `start_login` 返回 `{"code", "url", "expires_in"}` 格式，`poll_login` 返回 account dict 或 None 即可。对于 OAuth、邮箱验证码等方式，将 `url` 设为验证链接，`code` 作为会话标识。
