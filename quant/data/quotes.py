"""近实时报价（轮询式，非推送）。

供个股详情页分钟级轮询：取最新价/涨跌幅与当日分时。延迟几秒到几十秒对"选股看走势"
场景足够，不引入 WebSocket/券商订阅。复用 ``config`` 的直连（no_proxy）设置。
**不做按天缓存**——这是近实时数据，每次都直接取最新。akshare 偶发失败时返回空结构，
由上层降级展示。
"""

import time

import pandas as pd

from .instruments import is_fund


def _f(v) -> float | None:
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


# 场内基金/ETF 实时快照（新浪全表），短 TTL 进程内缓存，避免分钟级轮询每次拉全表。
_ETF_SPOT_TTL = 30  # 秒
_etf_spot_cache: dict = {"ts": 0.0, "df": None}


def _etf_spot() -> pd.DataFrame:
    now = time.time()
    if _etf_spot_cache["df"] is not None and now - _etf_spot_cache["ts"] < _ETF_SPOT_TTL:
        return _etf_spot_cache["df"]
    import akshare as ak

    df = ak.fund_etf_category_sina(symbol="ETF基金").copy()
    df["__code"] = df["代码"].astype(str).str[-6:]
    _etf_spot_cache.update(ts=now, df=df)
    return df


def _fund_quote(symbol: str, result: dict) -> dict:
    """ETF 报价：用新浪 ETF 实时全表过滤出本只。"""
    try:
        df = _etf_spot()
        row = df[df["__code"] == symbol]
        if not row.empty:
            r = row.iloc[0]
            mapping = {
                "最新价": "price",
                "涨跌幅": "pct_chg",
                "今开": "open",
                "最高": "high",
                "最低": "low",
                "昨收": "prev_close",
                "成交量": "volume",
                "成交额": "amount",
            }
            for zh, en in mapping.items():
                if zh in r.index:
                    result[en] = _f(r[zh])
    except Exception:
        pass
    return result


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
    if is_fund(symbol):
        return _fund_quote(symbol, result)
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
                result[en] = _f(kv[zh])
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
