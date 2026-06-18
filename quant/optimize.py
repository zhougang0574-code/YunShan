"""参数寻优与走动检验（walk-forward）。

- ``grid_search``：遍历参数网格，对每组参数跑回测，按目标指标排序，找最优参数。
- ``walk_forward``：把时间轴切成多段，每段「样本内选参 → 下一段样本外检验」，
  输出样本内/样本外指标对比，用于识别**过拟合**（样本内好、样本外崩）。
"""

import itertools

import pandas as pd

from . import metrics
from .costs import CostModel
from .engine import run_backtest


def _iter_param_combos(param_grid: dict[str, list]):
    keys = list(param_grid)
    for values in itertools.product(*(param_grid[k] for k in keys)):
        yield dict(zip(keys, values))


def _evaluate(
    price: pd.DataFrame,
    strategy_cls: type,
    params: dict,
    metric: str,
    cost_model: CostModel | None,
) -> dict | None:
    """跑一组参数，返回 {参数..., 各指标...}；参数非法则返回 None。"""
    try:
        strategy = strategy_cls(**params)
    except (ValueError, TypeError):
        return None
    signal = strategy.generate_signal(price)
    result = run_backtest(price, signal, cost_model=cost_model)
    stats = metrics.summarize(result)
    if metric not in stats:
        raise KeyError(f"未知指标 '{metric}'，可选：{list(stats)}")
    return {**params, **stats}


def grid_search(
    price: pd.DataFrame,
    strategy_cls: type,
    param_grid: dict[str, list] | None = None,
    metric: str = "sharpe_ratio",
    cost_model: CostModel | None = None,
) -> pd.DataFrame:
    """网格寻优，返回按 ``metric`` 降序排列的结果表（每行一组参数及其指标）。"""
    param_grid = param_grid or strategy_cls.param_space()
    rows = [
        row
        for params in _iter_param_combos(param_grid)
        if (row := _evaluate(price, strategy_cls, params, metric, cost_model))
        is not None
    ]
    if not rows:
        return pd.DataFrame()
    return (
        pd.DataFrame(rows)
        .sort_values(metric, ascending=False)
        .reset_index(drop=True)
    )


def walk_forward(
    price: pd.DataFrame,
    strategy_cls: type,
    param_grid: dict[str, list] | None = None,
    n_splits: int = 4,
    metric: str = "sharpe_ratio",
    cost_model: CostModel | None = None,
) -> pd.DataFrame:
    """走动检验：切 ``n_splits+1`` 段，逐段样本内选参、下一段样本外检验。

    返回每个 split 的最优参数、样本内指标(``is_<metric>``)与样本外指标
    (``oos_<metric>``)。样本外明显差于样本内通常意味着过拟合。
    """
    param_grid = param_grid or strategy_cls.param_space()
    segments = _split_segments(price, n_splits + 1)

    records = []
    for i in range(len(segments) - 1):
        train, test = segments[i], segments[i + 1]
        ranked = grid_search(train, strategy_cls, param_grid, metric, cost_model)
        if ranked.empty:
            continue
        best = ranked.iloc[0]
        # 结果表混了 int 参数列与 float 指标列，pandas 会把参数上转成 float，
        # 这里按值映射回原始候选，恢复 int/float 原类型（否则 rolling(5.0) 会报错）。
        best_params = {
            k: next((c for c in param_grid[k] if c == best[k]), best[k])
            for k in param_grid
        }
        oos = _evaluate(test, strategy_cls, best_params, metric, cost_model)
        records.append(
            {
                "split": i,
                **best_params,
                f"is_{metric}": float(best[metric]),
                f"oos_{metric}": float(oos[metric]) if oos else float("nan"),
            }
        )
    return pd.DataFrame(records)


def _split_segments(price: pd.DataFrame, n: int) -> list[pd.DataFrame]:
    """把价格按时间顺序切成 n 段连续子区间。"""
    bounds = [round(len(price) * k / n) for k in range(n + 1)]
    return [price.iloc[bounds[k] : bounds[k + 1]] for k in range(n)]
