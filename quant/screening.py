"""截面多因子选股打分 / 排名。

输入股票池（``universe``）+ 一组因子（基本面快照因子 + 技术因子）和权重，对池内每只
股票按**截面 z-score** 标准化各因子（按因子 direction 统一符号），加权求和得到综合分，
降序排名输出 Top N 及各因子明细分。

两类因子来源不同：
- **基本面/量价因子**（``factors.fundamental``）：来自一次全市场快照，廉价、覆盖全市场。
- **技术因子**（基于 ``factors.technical``）：需逐股拉取近端价格历史计算最新值，较慢——
  通过注入的 ``price_loader`` 获取（默认 ``data.get_daily``），仅在选了技术因子时触发。

不引入复杂的多因子风险模型（按当前"辅助选股"需求等权/自定义权重 z-score 足够）。
"""

import datetime

import numpy as np
import pandas as pd

from .data import fundamentals, universe
from .factors import fundamental, technical


def _latest(series: pd.Series) -> float:
    s = series.dropna()
    return float(s.iloc[-1]) if len(s) else float("nan")


# 技术因子 key -> (price->最新值 的函数, 方向, 展示名)
TECHNICAL_FACTORS = {
    "tech_mom_20": (lambda p: _latest(technical.momentum(p, 20)), "high", "20日动量"),
    "tech_mom_60": (lambda p: _latest(technical.momentum(p, 60)), "high", "60日动量"),
    "tech_rsi_14": (lambda p: _latest(technical.rsi(p, 14)), "low", "RSI(偏低=超卖)"),
    "tech_volatility": (
        lambda p: float(p["close"].pct_change().std() * np.sqrt(252)),
        "low",
        "年化波动率(低优)",
    ),
    "tech_ma20_bias": (
        lambda p: _latest(p["close"] / technical.sma(p, 20) - 1),
        "high",
        "相对20日均线乖离",
    ),
}


def available_factors() -> dict:
    """列出可选因子：{key: {label, direction, kind}}，供前端因子选择与后端 /screening。"""
    out = {}
    for key, (_, direction, label) in fundamental.FUNDAMENTAL_FACTORS.items():
        out[key] = {"label": label, "direction": direction, "kind": "fundamental"}
    for key, (_, direction, label) in TECHNICAL_FACTORS.items():
        out[key] = {"label": label, "direction": direction, "kind": "technical"}
    return out


def _direction_sign(key: str) -> float:
    if fundamental.is_fundamental(key):
        direction = fundamental.factor_direction(key)
    else:
        direction = TECHNICAL_FACTORS[key][1]
    return -1.0 if direction == "low" else 1.0


def _zscore(col: pd.Series) -> pd.Series:
    """截面 z-score；标准差为 0 或全缺失时返回全 0（该因子不影响排名）。"""
    valid = col.dropna()
    if len(valid) < 2 or valid.std(ddof=0) == 0:
        return pd.Series(0.0, index=col.index)
    z = (col - valid.mean()) / valid.std(ddof=0)
    return z.fillna(0.0)


def screen(
    factors: list[dict],
    universe_key: str = "all",
    top_n: int = 50,
    max_symbols: int = 500,
    lookback_days: int = 180,
    snapshot: pd.DataFrame | None = None,
    price_loader=None,
    progress=None,
) -> pd.DataFrame:
    """对股票池做截面打分排名。

    factors: ``[{"key": "pe", "weight": 1.0}, ...]``，key 取自 ``available_factors()``。
    返回按综合分降序的 DataFrame：rank/code/name/score + 各因子原始值 ``<key>`` 与
    标准化分 ``<key>_z``。
    """
    if not factors:
        raise ValueError("至少需要一个因子")
    keys = [f["key"] for f in factors]
    weights = {f["key"]: float(f.get("weight", 1.0)) for f in factors}
    catalog = available_factors()
    for k in keys:
        if k not in catalog:
            raise ValueError(f"未知因子 '{k}'，可选：{list(catalog)}")

    members = universe.get_constituents(universe_key)
    if members.empty:
        return pd.DataFrame()
    members = members.head(max_symbols).reset_index(drop=True)

    snap = snapshot if snapshot is not None else fundamentals.market_snapshot()
    df = members.set_index("code")

    # 基本面/量价因子：从全市场快照按 code 对齐取列
    fund_keys = [k for k in keys if fundamental.is_fundamental(k)]
    for k in fund_keys:
        col = fundamental.snapshot_column(k)
        df[k] = snap[col] if (not snap.empty and col in snap.columns) else np.nan

    # 技术因子：逐股拉近端价格计算最新值
    tech_keys = [k for k in keys if not fundamental.is_fundamental(k)]
    if tech_keys:
        loader = price_loader or _default_price_loader
        end = datetime.date.today()
        start = end - datetime.timedelta(days=lookback_days)
        for k in tech_keys:
            df[k] = np.nan
        total = len(df)
        for i, code in enumerate(df.index):
            try:
                price = loader(code, str(start), str(end))
            except Exception:
                price = None
            if price is not None and not price.empty:
                for k in tech_keys:
                    fn = TECHNICAL_FACTORS[k][0]
                    try:
                        df.at[code, k] = fn(price)
                    except Exception:
                        pass
            if progress:
                progress((i + 1) / total)

    # 截面标准化 + 加权综合分
    score = pd.Series(0.0, index=df.index)
    for k in keys:
        z = _zscore(df[k]) * _direction_sign(k)
        df[f"{k}_z"] = z
        score += weights[k] * z
    df["score"] = score

    ranked = df.sort_values("score", ascending=False).head(top_n).reset_index()
    ranked.insert(0, "rank", range(1, len(ranked) + 1))
    return ranked


def _default_price_loader(symbol: str, start: str, end: str) -> pd.DataFrame:
    from .data import get_daily

    return get_daily(symbol, start, end)
