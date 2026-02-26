KILO_BASE_URL = "https://api.kilo.ai"

POLL_INTERVAL = 3
POLL_TIMEOUT = 600

DEVICE_AUTH_HEADERS = {
    "Content-Type": "application/json",
    "accept": "*/*",
    "accept-language": "*",
    "sec-fetch-mode": "cors",
    "user-agent": "node",
}

MODELS_HEADERS = {
    "HTTP-Referer": "https://kilocode.ai",
    "X-Title": "Kilo Code",
    "X-KiloCode-Version": "5.7.0",
    "User-Agent": "Kilo-Code/5.7.0",
    "accept": "*/*",
    "accept-language": "*",
    "sec-fetch-mode": "cors",
}

CHAT_HEADERS_STATIC = {
    "Accept": "application/json",
    "X-Stainless-Retry-Count": "0",
    "X-Stainless-Lang": "js",
    "X-Stainless-Package-Version": "5.12.2",
    "X-Stainless-OS": "Windows",
    "X-Stainless-Arch": "x64",
    "X-Stainless-Runtime": "node",
    "X-Stainless-Runtime-Version": "v22.21.1",
    "HTTP-Referer": "https://kilocode.ai",
    "X-Title": "Kilo Code",
    "X-KiloCode-Version": "5.7.0",
    "User-Agent": "Kilo-Code/5.7.0",
    "content-type": "application/json",
    "X-KiloCode-EditorName": "Visual Studio Code 1.109.4",
    "X-KiloCode-Mode": "code",
    "x-anthropic-beta": "fine-grained-tool-streaming-2025-05-14",
    "accept-language": "*",
    "sec-fetch-mode": "cors",
}

BALANCE_HEADERS = {
    "accept": "*/*",
    "accept-language": "*",
    "sec-fetch-mode": "cors",
    "user-agent": "node",
}
