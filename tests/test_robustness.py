"""稳健性检验：Deflated Sharpe + 蒙特卡洛择时置换（确定性构造验证）。"""

import numpy as np
import pandas as pd

from quant import robustness


def test_dsr_is_probability_in_range():
    rng = np.random.default_rng(0)
    returns = pd.Series(rng.normal(0.001, 0.01, 500))
    trials = list(rng.normal(1.0, 0.5, 50))  # 50 组尝试的年化 Sharpe
    out = robustness.deflated_sharpe_ratio(returns, trials)
    assert out["n_trials"] == 50
    assert 0.0 <= out["deflated_sharpe_ratio"] <= 1.0
    # 试得越多，expected_max_sharpe 越高（基准被抬升）
    assert out["expected_max_sharpe"] >= 0


def test_dsr_more_trials_lower_score():
    rng = np.random.default_rng(1)
    returns = pd.Series(rng.normal(0.0008, 0.01, 400))
    few = robustness.deflated_sharpe_ratio(returns, list(rng.normal(0.5, 0.3, 3)))
    many = robustness.deflated_sharpe_ratio(returns, list(rng.normal(0.5, 0.3, 200)))
    # 同样的观测收益，尝试次数越多，去水分后的 DSR 不应更高
    assert many["deflated_sharpe_ratio"] <= few["deflated_sharpe_ratio"] + 1e-9


def test_dsr_short_series_returns_nan():
    out = robustness.deflated_sharpe_ratio(pd.Series([0.01, 0.02]), [1.0])
    assert np.isnan(out["deflated_sharpe_ratio"])


def test_monte_carlo_real_edge_low_pvalue():
    # 构造真实择时：收益为正时持仓、为负时空仓 → 应显著优于随机
    rng = np.random.default_rng(2)
    mkt = pd.Series(rng.normal(0, 0.02, 300))
    position = (mkt > 0).astype(float)
    out = robustness.monte_carlo_signal_pvalue(mkt, position, n_iter=300, seed=3)
    assert out["p_value"] < 0.05
    assert out["observed_sharpe"] > out["null_mean_sharpe"]


def test_monte_carlo_random_signal_pvalue_centered():
    # 仓位与收益独立时，p 值在多次独立抽样下应大致均匀分布（无系统性显著），
    # 均值应靠近 0.5、远离 0——单次抽样可能偶然偏低，所以对多次取均值更稳健。
    rng = np.random.default_rng(4)
    pvals = []
    for _ in range(20):
        mkt = pd.Series(rng.normal(0, 0.02, 300))
        position = pd.Series(rng.integers(0, 2, 300).astype(float))
        pvals.append(
            robustness.monte_carlo_signal_pvalue(mkt, position, n_iter=200)["p_value"]
        )
    assert 0.3 < float(np.mean(pvals)) < 0.7
