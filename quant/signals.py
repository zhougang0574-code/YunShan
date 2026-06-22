"""个股"注意点"信号：把技术 / 基本面 / 另类数据当前状态标签化。

供个股详情页展示——不是回测信号，而是"此刻这只股票有哪些值得注意的点"：
是否 RSI 超买超卖、MACD 金叉死叉、布林带突破，估值是否偏高、盈利是否恶化，
是否有大额资金流出等。每个标签带一个 ``level``（good/warn/bad/info）供前端着色。

``evaluate`` 是纯函数（传入已取好的 price/fundamentals/alt），便于离线测试；
``for_symbol`` 是便捷入口，自动拉取所需数据后调用 ``evaluate``。
"""

import datetime
import math

import pandas as pd

from .factors import technical


def _tag(category: str, level: str, text: str) -> dict:
    return {"category": category, "level": level, "text": text}


def _ok(x) -> bool:
    return x is not None and not (isinstance(x, float) and math.isnan(x))


def _technical_tags(price: pd.DataFrame) -> list[dict]:
    tags: list[dict] = []
    if price is None or len(price) < 30:
        return tags
    close = price["close"]

    rsi = technical.rsi(price, 14).iloc[-1]
    if _ok(rsi):
        if rsi > 70:
            tags.append(_tag("technical", "warn", f"RSI {rsi:.0f}：超买，短线或有回调"))
        elif rsi < 30:
            tags.append(_tag("technical", "good", f"RSI {rsi:.0f}：超卖，或有反弹"))

    m = technical.macd(price)
    dif, dea = m["dif"], m["dea"]
    if len(dif) >= 2 and _ok(dif.iloc[-1]) and _ok(dea.iloc[-1]):
        prev, now = dif.iloc[-2] - dea.iloc[-2], dif.iloc[-1] - dea.iloc[-1]
        if prev <= 0 < now:
            tags.append(_tag("technical", "good", "MACD 金叉"))
        elif prev >= 0 > now:
            tags.append(_tag("technical", "bad", "MACD 死叉"))

    boll = technical.bollinger(price)
    if _ok(boll["upper"].iloc[-1]):
        if close.iloc[-1] > boll["upper"].iloc[-1]:
            tags.append(_tag("technical", "warn", "突破布林带上轨"))
        elif close.iloc[-1] < boll["lower"].iloc[-1]:
            tags.append(_tag("technical", "warn", "跌破布林带下轨"))

    sma20, sma60 = technical.sma(price, 20).iloc[-1], technical.sma(price, 60).iloc[-1]
    if _ok(sma20) and _ok(sma60):
        if close.iloc[-1] > sma20 > sma60:
            tags.append(_tag("technical", "good", "多头排列（价>MA20>MA60）"))
        elif close.iloc[-1] < sma20 < sma60:
            tags.append(_tag("technical", "bad", "空头排列（价<MA20<MA60）"))
    return tags


def _fundamental_tags(fund: dict | None) -> list[dict]:
    tags: list[dict] = []
    if not fund:
        return tags
    pe = fund.get("pe_ttm")
    if _ok(pe):
        if pe < 0:
            tags.append(_tag("fundamental", "bad", "PE(TTM) 为负：当前亏损"))
        elif pe > 80:
            tags.append(_tag("fundamental", "warn", f"PE(TTM) {pe:.0f}：估值偏高"))
    roe = fund.get("roe")
    if _ok(roe):
        if roe >= 15:
            tags.append(_tag("fundamental", "good", f"ROE {roe:.1f}%：盈利能力强"))
        elif roe < 0:
            tags.append(_tag("fundamental", "bad", f"ROE {roe:.1f}%：盈利恶化"))
    profit_yoy = fund.get("profit_yoy")
    if _ok(profit_yoy) and profit_yoy < 0:
        tags.append(_tag("fundamental", "warn", f"净利同比 {profit_yoy:.0f}%：下滑"))
    return tags


def _altdata_tags(alt: dict | None) -> list[dict]:
    tags: list[dict] = []
    if not alt:
        return tags
    pct = alt.get("main_net_pct")
    if _ok(pct):
        if pct > 5:
            tags.append(_tag("altdata", "good", f"主力净流入占比 {pct:.1f}%：资金青睐"))
        elif pct < -5:
            tags.append(_tag("altdata", "warn", f"主力净流出占比 {pct:.1f}%：资金离场"))
    return tags


def evaluate(
    price: pd.DataFrame | None = None,
    fundamentals: dict | None = None,
    alt: dict | None = None,
) -> list[dict]:
    """根据已取好的数据计算注意点标签列表（纯函数，便于测试）。"""
    return (
        _technical_tags(price)
        + _fundamental_tags(fundamentals)
        + _altdata_tags(alt)
    )


def for_symbol(symbol: str, lookback_days: int = 250) -> dict:
    """便捷入口：自动拉价格/基本面/资金流，返回 {symbol, tags}。各数据源失败安全降级。"""
    from .data import altdata, fundamentals as fd, get_daily

    end = datetime.date.today()
    start = end - datetime.timedelta(days=lookback_days)
    try:
        price = get_daily(symbol, str(start), str(end))
    except Exception:
        price = None
    fund = fd.get_fundamentals(symbol)
    alt = altdata.fund_flow(symbol)
    return {"symbol": symbol, "tags": evaluate(price, fund, alt)}
