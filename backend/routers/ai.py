"""AI 智能分析接口。

- ``GET /ai/status``  —— 是否已配置大模型 Key（前端据此显隐"生成 AI 报告"按钮）。
- ``POST /ai/report`` —— 同步生成个股结构化分析报告（单股耗时十几秒，前端展示加载态）。

报告生成复用既有数据层（报价/日线/基本面/资金面/注意点），见 ``quant.ai.report``。
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from quant import ai

router = APIRouter(prefix="/ai", tags=["ai"])


class ReportRequest(BaseModel):
    symbol: str


@router.get("/status")
def ai_status() -> dict:
    """返回 AI 是否可用及当前模型名（不泄露 Key）。"""
    settings = ai.config.get_settings()
    return {"enabled": ai.config.is_configured(), "model": settings["model"]}


@router.post("/report")
def ai_report(req: ReportRequest) -> dict:
    """生成个股 AI 分析报告。未配置 Key → 400，模型调用失败 → 502。"""
    symbol = (req.symbol or "").strip()
    if not symbol:
        raise HTTPException(status_code=400, detail="缺少股票代码")
    if not ai.config.is_configured():
        raise HTTPException(status_code=400, detail="未配置大模型 API Key（在项目根目录 .env 填写 DEEPSEEK_API_KEY）")
    try:
        return ai.report.generate_stock_report(symbol)
    except ai.LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
