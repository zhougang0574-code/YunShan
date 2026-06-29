"""AI（大模型）配置：供应商无关，走 OpenAI 兼容协议。

Key 与接入点经环境变量 / 根目录 ``.env`` 注入，**不入库**。默认 DeepSeek：
读取顺序——已存在的环境变量 > 根目录 ``.env`` 文件 > 这里的默认值。

``.env`` 解析刻意做成零依赖的极简版（``KEY=VALUE`` 行，``#`` 注释、可选引号），
避免为一个个人项目引入 python-dotenv。需要更复杂的格式再换正式库。
"""

import os

from quant.config import PROJECT_ROOT

# DeepSeek 既是默认接入点，也兼容任意 OpenAI 风格服务（豆包/通义/OpenAI…只需改这三个值）。
DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-chat"

# 单次调用超时（秒）。大模型生成个股报告通常十几秒，给足余量但不无限等。
REQUEST_TIMEOUT = 60.0

_ENV_LOADED = False


def _load_dotenv_once() -> None:
    """把根目录 ``.env`` 里尚未出现在环境变量中的键加载进来（只做一次）。"""
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    _ENV_LOADED = True
    path = PROJECT_ROOT / ".env"
    if not path.is_file():
        return
    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            # 不覆盖进程里已显式设置的环境变量（环境变量优先级更高）。
            if key and key not in os.environ:
                os.environ[key] = val
    except OSError:
        # .env 读不出来不应影响主流程，安静降级到"未配置"。
        pass


def _env(*names: str, default: str = "") -> str:
    for name in names:
        val = os.environ.get(name)
        if val:
            return val.strip()
    return default


def get_settings() -> dict:
    """返回当前 LLM 接入配置：``{base_url, api_key, model}``。"""
    _load_dotenv_once()
    return {
        # 兼容多种常见命名：专用的 DEEPSEEK_API_KEY，或通用的 LLM_API_KEY / OPENAI_API_KEY。
        "api_key": _env("DEEPSEEK_API_KEY", "LLM_API_KEY", "OPENAI_API_KEY"),
        "base_url": _env("LLM_BASE_URL", "OPENAI_BASE_URL", default=DEFAULT_BASE_URL).rstrip("/"),
        "model": _env("LLM_MODEL", "OPENAI_MODEL", default=DEFAULT_MODEL),
    }


def is_configured() -> bool:
    """是否已填入可用的 API Key（前端据此决定显隐 AI 按钮）。"""
    return bool(get_settings()["api_key"])
