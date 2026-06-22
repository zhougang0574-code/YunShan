"""近实时报价（轮询式，非推送）。

供个股详情页分钟级轮询：取最新价/涨跌幅与当日分时。延迟几秒到几十秒对"选股看走势"
场景足够，不引入 WebSocket/券商订阅。复用 ``config`` 的直连（no_proxy）设置。
**不做按天缓存**——这是近实时数据，每次都直接取最新。akshare 偶发失败时返回空结构，
由上层降级展示。
"""

import pandas as pd


def _market(symbol: str) -> str:
    """按代码前缀粗判交易所：6→sh，否则 sz（北交所 8/4 暂归 bj）。"""
    if symbol.startswith("6"):
        return "sh"
    if symbol.startswith(("4", "8")):
        return "bj"
    return "sz"


def get_quote(symbol: str) -> dict:
    """最新报价：price / pct_chg / open / high / low / prev_close / volume / amount。"""
    result = {
        "symbol": symbol,
        "price": None,
        "pct_chg": None,
        "open": None,
        "high": None,
        "low": None,
        "prev_close": None,
        "volume": None,
        "amount": None,
    }
    try:
        import akshare as ak

        df = ak.stock_bid_ask_em(symbol=symbol)
        # 该接口返回两列 item/value 的键值表
        kv = dict(zip(df["item"].astype(str), df["value"]))
        mapping = {
            "最新": "price",
            "涨幅": "pct_chg",
            "今开": "open",
            "最高": "high",
            "最低": "low",
            "昨收": "prev_close",
            "总手": "volume",
            "金额": "amount",
        }
        for zh, en in mapping.items():
            if zh in kv:
                try:
                    result[en] = float(kv[zh])
                except (ValueError, TypeError):
                    pass
    except Exception:
        pass
    return result


def get_intraday(symbol: str) -> pd.DataFrame:
    """当日分时（时间 + 价格 + 成交量）。失败返回空 DataFrame。"""
    try:
        import akshare as ak

        raw = ak.stock_intraday_em(symbol=symbol)
        if raw is None or raw.empty:
            return pd.DataFrame(columns=["time", "price", "volume"])
        cols = {c: str(c) for c in raw.columns}
        time_col = next((c for c in raw.columns if "时间" in str(c)), raw.columns[0])
        price_col = next((c for c in raw.columns if "成交价" in str(c) or "价" in str(c)), None)
        vol_col = next((c for c in raw.columns if "手" in str(c) or "量" in str(c)), None)
        out = pd.DataFrame({"time": raw[time_col].astype(str)})
        out["price"] = pd.to_numeric(raw[price_col], errors="coerce") if price_col else None
        out["volume"] = pd.to_numeric(raw[vol_col], errors="coerce") if vol_col else None
        return out
    except Exception:
        return pd.DataFrame(columns=["time", "price", "volume"])
