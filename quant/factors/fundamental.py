"""基本面 / 量价快照因子，供截面选股使用。

数据来源是 ``quant.data.fundamentals.market_snapshot()`` 的全市场快照（一次网络调用），
所以这些因子能在全市场上廉价地按截面计算，不必逐股拉财务接口。每个因子声明一个
``direction``：``"low"`` 表示数值越小越好（如低估值、低波动），``"high"`` 表示越大越好
（如动量）。截面打分时按 direction 统一符号后做 z-score。
"""

# 因子 key -> (快照列名, 方向, 展示名)
FUNDAMENTAL_FACTORS = {
    "pe": ("pe", "low", "市盈率(低估值优)"),
    "pb": ("pb", "low", "市净率(低估值优)"),
    "small_cap": ("total_mv", "low", "总市值(小市值优)"),
    "turnover": ("turnover", "high", "换手率(活跃度)"),
    "mom_60d": ("ret_60d", "high", "60日动量"),
    "mom_ytd": ("ret_ytd", "high", "年初至今涨幅"),
}


def factor_direction(key: str) -> str:
    return FUNDAMENTAL_FACTORS[key][1]


def factor_label(key: str) -> str:
    return FUNDAMENTAL_FACTORS[key][2]


def snapshot_column(key: str) -> str:
    return FUNDAMENTAL_FACTORS[key][0]


def is_fundamental(key: str) -> bool:
    return key in FUNDAMENTAL_FACTORS
