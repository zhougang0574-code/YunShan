"""稳健性检验：识别"虚假 alpha"。

与 ``optimize.walk_forward`` 互补——walk-forward 看"样本外是否还有效"，本模块看
"结果是不是只是统计噪音 / 过拟合了多次尝试"：

- ``deflated_sharpe_ratio``（Bailey & López de Prado）：寻优试了很多组参数，最高的那个
  Sharpe 天然被"选择偏差"抬高。DSR 在考虑【尝试次数、收益偏度/峰度、样本长度】后，给出
  "真实 Sharpe > 0 的概率"，把多重检验的水分挤掉。
- ``monte_carlo_signal_pvalue``：随机打乱仓位与收益的对应关系（保持持仓天数不变），重复
  多次得到"随机择时"的 Sharpe 分布，看原策略是否显著优于随机。p 值越小越可信。

只用标准库 ``statistics.NormalDist`` 做正态分布 CDF/分位，不依赖 scipy。
"""

import math
from statistics import NormalDist

import numpy as np
import pandas as pd

from . import config

_NORM = NormalDist()
_EULER = 0.5772156649015329
_PPY = config.TRADING_DAYS_PER_YEAR


def _clean_returns(returns) -> np.ndarray:
    arr = pd.Series(returns).dropna().to_numpy(dtype=float)
    return arr


def _sharpe_per_period(returns: np.ndarray) -> float:
    if len(returns) < 2 or returns.std(ddof=1) == 0:
        return 0.0
    return float(returns.mean() / returns.std(ddof=1))


def deflated_sharpe_ratio(
    returns,
    trial_sharpes,
    periods_per_year: int = _PPY,
) -> dict:
    """计算 Deflated Sharpe Ratio。

    returns: 最优参数那条策略的逐期收益序列（用于偏度/峰度/样本长度与观测 Sharpe）。
    trial_sharpes: 寻优中**所有**尝试的（年化）Sharpe 列表——用来估计"尝试越多、最高
        Sharpe 被抬得越高"的基准 ``expected_max_sharpe``。
    返回 {sr_observed(年化), expected_max_sharpe(年化), n_trials, deflated_sharpe_ratio}。
    DSR 是个概率（0~1）：越接近 1，越说明该 Sharpe 不是多重尝试的运气产物。
    """
    r = _clean_returns(returns)
    n_trials = max(1, len(list(trial_sharpes)))
    scale = math.sqrt(periods_per_year)
    result = {
        "sr_observed": 0.0,
        "expected_max_sharpe": 0.0,
        "n_trials": n_trials,
        "deflated_sharpe_ratio": float("nan"),
    }
    if len(r) < 3:
        return result

    sr_hat = _sharpe_per_period(r)  # 每期口径
    result["sr_observed"] = sr_hat * scale

    # 偏度、峰度（Pearson，正态=3）
    std = r.std(ddof=1)
    if std == 0:
        return result
    z = (r - r.mean()) / std
    skew = float((z**3).mean())
    kurt = float((z**4).mean())

    # 尝试 Sharpe 的离散度（转回每期口径）
    trials_pp = np.array(list(trial_sharpes), dtype=float) / scale
    trials_pp = trials_pp[~np.isnan(trials_pp)]
    var_trials = float(trials_pp.var(ddof=1)) if len(trials_pp) > 1 else 0.0

    if n_trials > 1 and var_trials > 0:
        # E[max] of N independent standard-normal Sharpe estimators（Bailey/LdP 近似）
        q1 = _NORM.inv_cdf(1 - 1.0 / n_trials)
        q2 = _NORM.inv_cdf(1 - 1.0 / (n_trials * math.e))
        sr0 = math.sqrt(var_trials) * ((1 - _EULER) * q1 + _EULER * q2)
    else:
        sr0 = 0.0
    result["expected_max_sharpe"] = sr0 * scale

    denom = math.sqrt(max(1e-12, 1 - skew * sr_hat + (kurt - 1) / 4 * sr_hat**2))
    stat = (sr_hat - sr0) * math.sqrt(len(r) - 1) / denom
    result["deflated_sharpe_ratio"] = float(_NORM.cdf(stat))
    return result


def monte_carlo_signal_pvalue(
    market_returns,
    position,
    n_iter: int = 1000,
    seed: int = 0,
    periods_per_year: int = _PPY,
) -> dict:
    """打乱仓位-收益对应关系的置换检验。

    market_returns: 标的逐期收益；position: 策略逐期仓位（0/1 或权重，已 shift 对齐）。
    随机打乱 position（保持持仓分布不变）重算 Sharpe，得到"随机择时"分布；
    p 值 = 随机 Sharpe ≥ 原策略 Sharpe 的比例。p 越小，原策略的择时越不像运气。
    """
    mkt = _clean_returns(market_returns)
    pos = pd.Series(position).reindex(pd.Series(market_returns).index).fillna(0.0)
    pos = pos.to_numpy(dtype=float)[: len(mkt)]
    mkt = mkt[: len(pos)]

    observed = _sharpe_per_period(mkt * pos)
    rng = np.random.default_rng(seed)
    null = np.empty(n_iter)
    for i in range(n_iter):
        null[i] = _sharpe_per_period(mkt * rng.permutation(pos))

    scale = math.sqrt(periods_per_year)
    p_value = float((null >= observed).mean())
    return {
        "observed_sharpe": observed * scale,
        "null_mean_sharpe": float(null.mean()) * scale,
        "p_value": p_value,
        "n_iter": n_iter,
    }
