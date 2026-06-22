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


def _baidu_last(symbol: str, *indicators: str) -> float:
    """百度估值时间序列取最近一个有效值；依次尝试多个候选指标名。"""
    import akshare as ak

    for indicator in indicators:
        try:
            df = ak.stock_zh_valuation_baidu(symbol=symbol, indicator=indicator, period="近一年")
            s = pd.to_numeric(df["value"], errors="coerce").dropna()
            if len(s):
                return float(s.iloc[-1])
        except Exception:
            continue
    return float("nan")


def _abstract_latest(df: pd.DataFrame, *keywords: str) -> float:
    """从新浪财务摘要里，按关键词匹配指标行，取最近一期（最左日期列）的有效值。"""
    if df is None or df.empty or len(df.columns) < 3:
        return float("nan")
    ind_col = df.columns[1]          # “指标”列
    date_cols = list(df.columns[2:])  # 各报告期，已按日期降序
    for _, row in df.iterrows():
        name = str(row[ind_col])
        if all(k in name for k in keywords):
            for c in date_cols:
                v = pd.to_numeric(pd.Series([row[c]]), errors="coerce").iloc[0]
                if not (isinstance(v, float) and math.isnan(v)):
                    return float(v)
    return float("nan")


def get_fundamentals(symbol: str, use_cache: bool = True) -> dict:
    """单只股票的基本面指标字典（估值/盈利/成长）。逐股慢接口，缓存 7 天。

    数据源用非东财的接口（百度估值 + 新浪财务摘要），在东财被网络掐断时仍可用。
    """
    # v2：换数据源后用新缓存键，自动丢弃旧（可能全空）的缓存
    key = f"fundamentals_detail_v2_{symbol}"
    if use_cache:
        cached = daycache.load(key, max_age_days=7)
        if cached is not None:
            return cached.iloc[0].to_dict()

    result = {
        "pe_ttm": float("nan"),
        "pb": float("nan"),
        "ps_ttm": float("nan"),
        "dv_ttm": float("nan"),
        "total_mv": float("nan"),  # 单位：亿元
        "roe": float("nan"),
        "gross_margin": float("nan"),
        "revenue_yoy": float("nan"),
        "profit_yoy": float("nan"),
    }
    # 基金/ETF 没有个股财务指标，直接返回空值，跳过逐股慢接口。
    if is_fund(symbol):
        return result

    # 估值（百度）
    result["pe_ttm"] = _baidu_last(symbol, "市盈率(TTM)")
    result["pb"] = _baidu_last(symbol, "市净率")
    result["ps_ttm"] = _baidu_last(symbol, "市销率(TTM)", "市销率")
    result["total_mv"] = _baidu_last(symbol, "总市值")

    # 盈利能力 / 成长性（新浪财务摘要）
    try:
        import akshare as ak

        fin = ak.stock_financial_abstract(symbol=symbol)
        result["roe"] = _abstract_latest(fin, "净资产收益率")
        result["gross_margin"] = _abstract_latest(fin, "毛利率")
        result["revenue_yoy"] = _abstract_latest(fin, "营业总收入", "增长")
        result["profit_yoy"] = _abstract_latest(fin, "净利润", "增长")
    except Exception:
        pass

    daycache.save(key, pd.DataFrame([result]))
    return result
