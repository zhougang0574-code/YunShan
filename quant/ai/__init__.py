"""AI（大模型）层：把系统已算好的结构化数据翻译成决策报告。

供应商无关（OpenAI 兼容，默认 DeepSeek），数据全部复用既有数据层。
当前提供个股分析报告，后续可在此地基上叠加回测解读 / 问股 Agent / 大盘复盘。
"""

from . import client, config, report
from .client import LLMError

__all__ = ["client", "config", "report", "LLMError"]
