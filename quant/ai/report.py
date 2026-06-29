"""AI 个股分析报告：取数 → 校验 → 拼提示词 → 调用模型 → 解析结构化结果。

核心设计（吸取友商报告的教训）：
1. **数据先校验再喂模型**：每个数据源标注 ``available/partial/missing``，缺失的明确告知模型，
   避免"业绩缺失却算出 PE 偏低""缩量与放大并存"这类自相矛盾。
2. **强制结构化 JSON 输出**：模型只填字段、不写小作文，前端按字段渲染，可控可审计。

数据全部复用既有数据层（报价/日线/基本面/资金面/注意点信号），AI 层不重复造数据源。
"""

from __future__ import annotations

import datetime
import json
import math

from . import client
from .config import get_settings

# 报告必备字段与默认值——模型偶尔漏字段时用它兜底，保证前端拿到完整结构。
_REPORT_DEFAULTS: dict = {
    "conclusion": "观望",
    "score": None,
    "trend": "震荡",
    "confidence": "低",
    "summary": "",
    "key_points": [],
    "risks": [],
    "catalysts": [],
    "operation": {"holder": "", "empty": ""},
    "checklist": [],
    "data_limitations": [],
}

_SYSTEM_PROMPT = (
    "你是严谨的 A 股投资研究助手。请只依据【数据包】里标注为 available 或 partial 的字段做分析；"
    "凡是标注 missing、或取值为 null 的字段，必须如实说明'数据不足，无法判断'，严禁臆测或编造任何数字。"
    "结论必须与数据自洽，不得自相矛盾（例如基本面缺失时不要对估值高低下结论，量价异常时要降权说明）。"
    "你面向中国 A 股个人投资者，语言简洁、专业、克制，不喊口号。只能输出一个 JSON 对象，不要任何额外文字。"
)

_OUTPUT_SCHEMA = """请严格按以下 JSON 结构输出（字段必须齐全，缺数据的字段给出保守值并在 data_limitations 说明）：
{
  "conclusion": "买入｜观望｜卖出 三选一",
  "score": 0-100 的整数（综合评分，越高越看多）,
  "trend": "看多｜看空｜震荡 三选一",
  "confidence": "高｜中｜低 三选一（数据越完整置信度越高）",
  "summary": "一句话决策，不超过40字",
  "key_points": ["客观信息速览，3条以内"],
  "risks": ["风险点，基于数据，最多4条"],
  "catalysts": ["潜在利好/催化，无则空数组"],
  "operation": {"holder": "持仓者操作建议", "empty": "空仓者操作建议"},
  "checklist": [{"item": "检查项", "status": "pass｜warn｜fail"}],
  "data_limitations": ["本次分析的数据缺口说明"]
}"""


def _clean(x):
    """NaN/inf → None，numpy 标量 → python 标量，便于 JSON 序列化。"""
    if x is None:
        return None
    if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
        return None
    if hasattr(x, "item"):  # numpy 标量
        try:
            return x.item()
        except (ValueError, TypeError):
            return None
    return x


def _round(x, ndigits: int = 2):
    v = _clean(x)
    return round(v, ndigits) if isinstance(v, (int, float)) else v


def _availability(values: list) -> str:
    """按非空字段比例给数据源打可用性标签。"""
    total = len(values)
    if total == 0:
        return "missing"
    present = sum(1 for v in values if _clean(v) is not None)
    if present == 0:
        return "missing"
    if present < total:
        return "partial"
    return "available"


def _technical_block(symbol: str) -> tuple[dict, str, "object"]:
    """从日线算技术快照，返回 (block, availability, price_df)；失败安全降级为 missing。"""
    from quant.data import get_daily
    from quant.factors import technical

    end = datetime.date.today()
    start = end - datetime.timedelta(days=400)
    try:
        price = get_daily(symbol, str(start), str(end))
    except Exception:
        price = None
    if price is None or len(price) < 30:
        return {}, "missing", price

    close = price["close"]
    last = close.iloc[-1]
    macd = technical.macd(price)
    dif, dea = macd["dif"].iloc[-1], macd["dea"].iloc[-1]
    macd_state = None
    if _clean(dif) is not None and _clean(dea) is not None:
        macd_state = "金叉/多头" if dif > dea else "死叉/空头"

    ma5 = technical.sma(price, 5).iloc[-1]
    ma10 = technical.sma(price, 10).iloc[-1]
    ma20 = technical.sma(price, 20).iloc[-1]
    ma60 = technical.sma(price, 60).iloc[-1] if len(price) >= 60 else None

    alignment = None
    if all(_clean(v) is not None for v in (last, ma5, ma20, ma60)):
        if last > ma5 > ma20 > ma60:
            alignment = "多头排列"
        elif last < ma5 < ma20 < ma60:
            alignment = "空头排列"
        else:
            alignment = "均线交织"

    block = {
        "close": _round(last),
        "ma5": _round(ma5),
        "ma10": _round(ma10),
        "ma20": _round(ma20),
        "ma60": _round(ma60),
        "rsi14": _round(technical.rsi(price, 14).iloc[-1], 1),
        "macd_state": macd_state,
        "ma_alignment": alignment,
        "bars_used": int(len(price)),
    }
    return block, _availability([block["ma5"], block["ma20"], block["rsi14"], block["macd_state"]]), price


def build_data_pack(symbol: str) -> dict:
    """汇总并校验个股各维度数据，附 availability 标注。各数据源独立 try，互不拖累。"""
    from quant import signals
    from quant.data import altdata, fundamentals as fd, get_name, quotes

    name = ""
    try:
        name = get_name(symbol) or ""
    except Exception:
        name = ""

    # 报价
    quote: dict = {}
    try:
        quote = quotes.get_quote(symbol) or {}
    except Exception:
        quote = {}
    quote = {k: _clean(v) for k, v in quote.items()}

    # 技术面（顺带拿到 price_df 供 signals 复用）
    tech, tech_avail, price = _technical_block(symbol)

    # 基本面
    fund: dict = {}
    try:
        fund = {k: _clean(v) for k, v in (fd.get_fundamentals(symbol) or {}).items()}
    except Exception:
        fund = {}

    # 资金面（另类数据）
    flow: dict = {}
    try:
        flow = {k: _clean(v) for k, v in (altdata.fund_flow(symbol) or {}).items()}
    except Exception:
        flow = {}

    # 注意点信号（复用纯函数，喂已取好的数据）
    tags: list = []
    try:
        tags = signals.evaluate(price, fund or None, flow or None)
    except Exception:
        tags = []

    availability = {
        "quote": _availability([quote.get("price"), quote.get("prev_close")]),
        "technical": tech_avail,
        "fundamentals": _availability(list(fund.values())),
        "fund_flow": _availability([flow.get("main_net"), flow.get("main_net_pct")]),
    }

    return {
        "symbol": symbol,
        "name": name,
        "as_of": str(datetime.date.today()),
        "quote": quote,
        "technical": tech,
        "fundamentals": fund,
        "fund_flow": flow,
        "signal_tags": tags,
        "availability": availability,
    }


def _normalize_report(raw: dict) -> dict:
    """用默认值补齐模型可能漏掉的字段，做轻度类型收敛。"""
    report = dict(_REPORT_DEFAULTS)
    if isinstance(raw, dict):
        for key in _REPORT_DEFAULTS:
            if key in raw and raw[key] is not None:
                report[key] = raw[key]
    # score 收敛为 0-100 整数或 None
    try:
        report["score"] = max(0, min(100, int(report["score"]))) if report["score"] is not None else None
    except (ValueError, TypeError):
        report["score"] = None
    # operation 必须是带两键的 dict
    op = report.get("operation")
    if not isinstance(op, dict):
        op = {}
    report["operation"] = {"holder": op.get("holder", ""), "empty": op.get("empty", "")}
    # 列表字段兜底
    for key in ("key_points", "risks", "catalysts", "checklist", "data_limitations"):
        if not isinstance(report.get(key), list):
            report[key] = []
    return report


def generate_stock_report(symbol: str) -> dict:
    """生成个股 AI 分析报告。抛 client.LLMError 由上层转成 HTTP 错误。"""
    pack = build_data_pack(symbol)

    user_prompt = (
        f"请分析以下 A 股个股的当前状况，给出结构化决策报告。\n\n"
        f"【数据包】（availability 标注各数据源完整度，null 表示该字段缺失）：\n"
        f"{json.dumps(pack, ensure_ascii=False, indent=2)}\n\n"
        f"{_OUTPUT_SCHEMA}"
    )

    content = client.chat(
        [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        json_mode=True,
        temperature=0.3,
    )

    try:
        raw = json.loads(content)
    except (ValueError, TypeError) as exc:
        raise client.LLMError(f"模型未返回合法 JSON：{exc}") from exc

    return {
        "symbol": symbol,
        "name": pack.get("name", ""),
        "generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "model": get_settings()["model"],
        "availability": pack["availability"],
        "quote": pack["quote"],
        "report": _normalize_report(raw),
    }
