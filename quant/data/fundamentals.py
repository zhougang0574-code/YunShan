"""基本面数据：估值 / 盈利能力 / 成长性。

两种粒度：
- ``market_snapshot()``：一次拉全市场实时快照（``stock_zh_a_spot_em``），含 PE/PB/市值/
  换手率/近端涨跌幅等。**截面选股**用它做基本面/量价因子的来源——一次网络调用覆盖全市场，
  避免逐股拉财务接口（数千次调用不现实）。按天缓存。
- ``get_fundamentals(symbol)``：单只股票的详细基本面快照（估值 + ROE/毛利率 + 营收/
  净利增速），供**个股详情页**展示"注意点"。逐股财务接口较慢，仅在看单只时调用，缓存较久。

akshare 接口列名口径多变，全部做防御式模糊匹配，取不到的指标返回 NaN，不中断流程。
"""

import math

import pandas as pd

from . import daycache
from .instruments import is_fund

# 全市场快照里我们关心的列（akshare 中文列名 -> 标准名）
_SNAPSHOT_COLS = {
    "代码": "code",
    "名称": "name",
    "最新价": "price",
    "涨跌幅": "pct_chg",
    "量比": "volume_ratio",
    "换手率": "turnover",
    "市盈率-动态": "pe",
    "市净率": "pb",
    "总市值": "total_mv",
    "流通市值": "circ_mv",
    "60日涨跌幅": "ret_60d",
    "年初至今涨跌幅": "ret_ytd",
}


def market_snapshot(use_cache: bool = True) -> pd.DataFrame:
    """全市场实时快照，索引为 6 位代码，含 pe/pb/total_mv/turnover 等列（按天缓存）。"""
    if use_cache:
        cached = daycache.load("fundamentals_snapshot")
        if cached is not None:
            return cached
    try:
        import akshare as ak

        raw = ak.stock_zh_a_spot_em()
    except Exception:
        return pd.DataFrame()
    present = {zh: en for zh, en in _SNAPSHOT_COLS.items() if zh in raw.columns}
    df = raw[list(present)].rename(columns=present)
    df["code"] = df["code"].astype(str).str.zfill(6)
    df = df.set_index("code")
    for col in df.columns:
        if col != "name":
            df[col] = pd.to_numeric(df[col], errors="coerce")
    daycache.save("fundamentals_snapshot", df.reset_index())
    return df


def _last_row(df: pd.DataFrame) -> pd.Series:
    return df.iloc[-1] if df is not None and not df.empty else pd.Series(dtype=float)


def _pick(row: pd.Series, *keywords: str) -> float:
    """从一行里按关键词模糊匹配取数值，取不到返回 NaN。"""
    for col in row.index:
        label = str(col)
        if all(k in label for k in keywords):
            try:
                val = float(row[col])
                return val if not math.isnan(val) else float("nan")
            except (ValueError, TypeError):
                continue
    return float("nan")


def get_fundamentals(symbol: str, use_cache: bool = True) -> dict:
    """单只股票的基本面指标字典（估值/盈利/成长）。逐股慢接口，缓存 7 天。"""
    key = f"fundamentals_detail_{symbol}"
    if use_cache:
        cached = daycache.load(key, max_age_days=7)
        if cached is not None:
            return cached.iloc[0].to_dict()

    result = {
        "pe_ttm": float("nan"),
        "pb": float("nan"),
        "ps_ttm": float("nan"),
        "dv_ttm": float("nan"),
        "total_mv": float("nan"),
        "roe": float("nan"),
        "gross_margin": float("nan"),
        "revenue_yoy": float("nan"),
        "profit_yoy": float("nan"),
    }
    # 基金/ETF 没有个股财务指标，直接返回空值，跳过逐股慢接口。
    if is_fund(symbol):
        return result
    try:
        import akshare as ak

        val = _last_row(ak.stock_a_indicator_lg(symbol=symbol))
        if not val.empty:
            result.update(
                pe_ttm=_pick(val, "pe_ttm") if "pe_ttm" in val.index else _pick(val, "pe"),
                pb=_pick(val, "pb"),
                ps_ttm=_pick(val, "ps_ttm") if "ps_ttm" in val.index else _pick(val, "ps"),
                dv_ttm=_pick(val, "dv_ttm") if "dv_ttm" in val.index else _pick(val, "dv"),
                total_mv=_pick(val, "total_mv"),
            )
    except Exception:
        pass
    try:
        import akshare as ak

        fin = _last_row(ak.stock_financial_analysis_indicator(symbol=symbol))
        if not fin.empty:
            result.update(
                roe=_pick(fin, "净资产收益率"),
                gross_margin=_pick(fin, "销售毛利率"),
                revenue_yoy=_pick(fin, "主营业务收入增长率"),
                profit_yoy=_pick(fin, "净利润增长率"),
            )
    except Exception:
        pass

    daycache.save(key, pd.DataFrame([result]))
    return result
