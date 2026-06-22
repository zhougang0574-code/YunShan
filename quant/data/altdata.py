"""A 股另类数据：资金流向 / 龙虎榜 / 北向资金持股（展示标签用）。

定位为**展示与标签数据**，不参与回测引擎计算（更新频率/口径与日线行情不完全对齐，
强行做成可回测因子易引入未来函数风险）。接入个股详情页的"注意点"标签卡。全部 akshare
免费接口，失败时安全降级为空，不中断个股详情展示。
"""

import pandas as pd

from . import daycache
from .instruments import market


def fund_flow(symbol: str, use_cache: bool = True) -> dict:
    """个股最近一日主力资金净流入（净额 + 净占比）。"""
    key = f"altdata_fundflow_{symbol}"
    if use_cache:
        cached = daycache.load(key)
        if cached is not None and not cached.empty:
            return cached.iloc[0].to_dict()

    result = {"date": None, "main_net": float("nan"), "main_net_pct": float("nan")}
    try:
        import akshare as ak

        df = ak.stock_individual_fund_flow(stock=symbol, market=market(symbol))
        if df is not None and not df.empty:
            row = df.iloc[-1]
            date_col = next((c for c in df.columns if "日期" in str(c)), None)
            net_col = next((c for c in df.columns if "主力净流入-净额" in str(c)), None)
            pct_col = next((c for c in df.columns if "主力净流入-净占比" in str(c)), None)
            result = {
                "date": str(row[date_col]) if date_col else None,
                "main_net": float(row[net_col]) if net_col else float("nan"),
                "main_net_pct": float(row[pct_col]) if pct_col else float("nan"),
            }
    except Exception:
        pass

    daycache.save(key, pd.DataFrame([result]))
    return result


def north_hold(symbol: str, use_cache: bool = True) -> dict:
    """北向资金持股市值（最近一日，取不到返回 NaN）。"""
    key = f"altdata_north_{symbol}"
    if use_cache:
        cached = daycache.load(key)
        if cached is not None and not cached.empty:
            return cached.iloc[0].to_dict()

    result = {"date": None, "hold_market_value": float("nan")}
    try:
        import akshare as ak

        df = ak.stock_hsgt_individual_em(stock=symbol)
        if df is not None and not df.empty:
            row = df.iloc[0]
            date_col = next((c for c in df.columns if "日期" in str(c)), None)
            mv_col = next((c for c in df.columns if "持股市值" in str(c)), None)
            result = {
                "date": str(row[date_col]) if date_col else None,
                "hold_market_value": float(row[mv_col]) if mv_col else float("nan"),
            }
    except Exception:
        pass

    daycache.save(key, pd.DataFrame([result]))
    return result
