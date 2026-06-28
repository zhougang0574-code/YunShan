"""近实时报价（轮询式，非推送）。

供个股详情页分钟级轮询：取最新价/涨跌幅与当日分时。延迟几秒到几十秒对"选股看走势"
场景足够，不引入 WebSocket/券商订阅。复用 ``config`` 的直连（no_proxy）设置。
**不做按天缓存**——这是近实时数据；但实时全表用很短的进程内 TTL 缓存，避免分钟级
轮询每次都拉一遍全市场快照。akshare 偶发失败时返回空结构，由上层降级展示。

数据源选用新浪（``stock_zh_a_spot`` / ``fund_etf_category_sina`` / ``stock_zh_a_minute``），
在东财被网络掐断的环境下仍可用。
"""

import time

import pandas as pd

from .instruments import is_fund, market


def _f(v) -> float | None:
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


# 实时快照：个股 / 基金各一张新浪全表，短 TTL 进程内缓存。
_SPOT_TTL = 30  # 秒
_spot_cache: dict[str, tuple[float, pd.DataFrame]] = {}


def _spot(kind: str) -> pd.DataFrame:
    """取（缓存的）新浪实时全表，附加 6 位代码列 ``__code`` 供过滤。"""
    now = time.time()
    cached = _spot_cache.get(kind)
    if cached is not None and now - cached[0] < _SPOT_TTL:
        return cached[1]

    import akshare as ak

    if kind == "fund":
        df = ak.fund_etf_category_sina(symbol="ETF基金").copy()
    else:
        df = ak.stock_zh_a_spot().copy()
    df["__code"] = df["代码"].astype(str).str[-6:]
    _spot_cache[kind] = (now, df)
    return df


# 新浪快照里的中文列 -> 我们的字段（个股与基金两张表列名一致）
_QUOTE_MAP = {
    "最新价": "price",
    "涨跌幅": "pct_chg",
    "今开": "open",
    "最高": "high",
    "最低": "low",
    "昨收": "prev_close",
    "成交量": "volume",
    "成交额": "amount",
}


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
    kind = "fund" if is_fund(symbol) else "stock"
    try:
        df = _spot(kind)
        row = df[df["__code"] == symbol]
        if not row.empty:
            r = row.iloc[0]
            for zh, en in _QUOTE_MAP.items():
                if zh in r.index:
                    result[en] = _f(r[zh])
    except Exception:
        pass
    return result


def get_intraday(symbol: str) -> pd.DataFrame:
    """当日分时（时间 + 价格 + 成交量）。用新浪分钟线取最近一个交易日，失败返回空。"""
    try:
        import akshare as ak

        raw = ak.stock_zh_a_minute(symbol=f"{market(symbol)}{symbol}", period="1", adjust="")
        if raw is None or raw.empty:
            return pd.DataFrame(columns=["date", "time", "price", "volume"])
        df = raw.copy()
        df["day"] = df["day"].astype(str)
        # 分钟线含最近若干交易日，这里只取最新一个交易日
        last_date = df["day"].str.slice(0, 10).max()
        today = df[df["day"].str.startswith(last_date)]
        out = pd.DataFrame(
            {
                "date": last_date,  # 该分时数据所属交易日（YYYY-MM-DD）
                "time": today["day"].str.slice(11, 16),
                "price": pd.to_numeric(today["close"], errors="coerce"),
                "volume": pd.to_numeric(today["volume"], errors="coerce"),
            }
        )
        return out.reset_index(drop=True)
    except Exception:
        return pd.DataFrame(columns=["date", "time", "price", "volume"])
