"""OpenAI 兼容的最小 chat 客户端（基于 httpx）。

只实现项目需要的部分：单轮/多轮消息、可选 JSON 输出模式、温度。
任何供应商只要兼容 ``POST {base_url}/chat/completions`` 即可直接用。

错误处理刻意"显式抛出、消息可读"：上层（路由）捕获后转成 4xx/5xx 文案给前端，
不把原始 httpx 异常糊脸上。
"""

from __future__ import annotations

import httpx

from . import config


class LLMError(RuntimeError):
    """大模型调用失败（未配置 / 网络 / 接口报错 / 响应异常）。"""


def chat(
    messages: list[dict],
    *,
    json_mode: bool = False,
    temperature: float = 0.3,
    max_tokens: int | None = None,
    timeout: float | None = None,
) -> str:
    """调用 chat 接口，返回首条回复的文本内容。

    Args:
        messages: OpenAI 风格消息列表 ``[{"role": "system"|"user"|..., "content": str}]``。
        json_mode: 为真时请求 ``response_format=json_object``，要求模型只输出 JSON。
        temperature: 采样温度，分析场景默认偏低（0.3）以求稳定。
        max_tokens: 可选的生成上限。
        timeout: 覆盖默认超时。

    Raises:
        LLMError: 未配置 Key、网络异常、HTTP 非 2xx、或响应结构异常时。
    """
    settings = config.get_settings()
    if not settings["api_key"]:
        raise LLMError("未配置大模型 API Key（在项目根目录 .env 填写 DEEPSEEK_API_KEY）。")

    payload: dict = {
        "model": settings["model"],
        "messages": messages,
        "temperature": temperature,
        "stream": False,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens

    url = f"{settings['base_url']}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings['api_key']}",
        "Content-Type": "application/json",
    }

    try:
        resp = httpx.post(
            url,
            json=payload,
            headers=headers,
            timeout=timeout or config.REQUEST_TIMEOUT,
        )
    except httpx.HTTPError as exc:
        raise LLMError(f"调用大模型失败（网络错误）：{exc}") from exc

    if resp.status_code != 200:
        # 取一点点 body 帮助定位（额度耗尽 / key 错误等），但不外泄过多细节。
        snippet = resp.text[:300] if resp.text else ""
        raise LLMError(f"大模型接口返回 {resp.status_code}：{snippet}")

    try:
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise LLMError(f"大模型响应结构异常：{exc}") from exc
