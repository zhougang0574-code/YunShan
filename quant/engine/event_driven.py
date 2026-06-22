"""事件驱动回测引擎（Phase 4）。

逐根 K 线重放：行情 → 目标仓位 → 下单 → 撮合 → 更新组合，天然支持**止损止盈**这类
路径依赖逻辑。复用 ``Portfolio`` + ``CostModel``，与向量化引擎共用策略接口（策略零改动）。

与向量化引擎的关系：
- 同样防未来函数——T 日信号 T+1 生效（``signal.shift(1)``）。
- **无成本、无止损**时，本引擎满仓持有期的逐日收益就是标的收益，与向量化引擎逐日完全一致
  （见 tests 的一致性校验）。加入止损止盈后才体现路径依赖差异。

仓位语义沿用向量化引擎的 0/1（空仓/满仓）；用分数股满仓建仓，残留少量现金以容纳费用。
"""

import pandas as pd

from .. import config
from ..costs import CostModel
from ..portfolio import Portfolio

_SYMBOL = "_"


def run_event_backtest(
    price: pd.DataFrame,
    signal: pd.Series,
    initial_capital: float = config.INITIAL_CAPITAL,
    cost_model: CostModel | None = None,
    stop_loss: float | None = None,
    take_profit: float | None = None,
) -> pd.DataFrame:
    """逐根重放回测。

    stop_loss / take_profit: 相对建仓价的比例（如 0.1 = 10%）。持仓期内若当日最低价触及
    止损价、或最高价触及止盈价，则当根以触发价离场，并**在信号回到空仓前不再重新进场**
    （避免同一信号段反复触发）。返回列与向量化引擎一致，可直接喂给 ``metrics.summarize``。
    """
    cost_model = cost_model or CostModel()
    pf = Portfolio(cash=initial_capital, cost_model=cost_model)

    closes = price["close"]
    highs = price["high"] if "high" in price else closes
    lows = price["low"] if "low" in price else closes

    buy_rate = (
        cost_model.commission_rate
        + cost_model.transfer_fee_rate
        + cost_model.slippage_rate
    )

    equity_curve, pos_curve = [], []
    entry_price: float | None = None
    stopped = False

    # 决策在 T 日收盘做出、自 T+1 日起承担收益：每根先用「上一根收盘建立的持仓」做盘中
    # 止损判定与盯市（这就是 T+1 生效，与向量化引擎的 signal.shift(1) 等价），再按本根
    # 信号下单。所以记录的 position[t] 是「进入本根时已持有的仓位」=上一根信号。
    for t, date in enumerate(price.index):
        c = float(closes.iloc[t])

        # 1) 持仓期内先判止损/止盈（路径依赖，盘中触发，影响当日净值）
        if pf.holdings.get(_SYMBOL, 0.0) > 0 and entry_price is not None and (
            stop_loss or take_profit
        ):
            exit_price = None
            if stop_loss and float(lows.iloc[t]) <= entry_price * (1 - stop_loss):
                exit_price = entry_price * (1 - stop_loss)
            elif take_profit and float(highs.iloc[t]) >= entry_price * (1 + take_profit):
                exit_price = entry_price * (1 + take_profit)
            if exit_price is not None:
                pf.sell(date, _SYMBOL, pf.holdings[_SYMBOL], exit_price)
                entry_price = None
                stopped = True

        # 2) 盯市并记录（持仓反映上一根收盘的决策，即承担了本根收益）
        held = pf.holdings.get(_SYMBOL, 0.0)
        equity_curve.append(pf.equity({_SYMBOL: c}))
        pos_curve.append(1.0 if held > 0 else 0.0)

        # 3) 本根收盘按信号下单，自下一根起生效
        sig = float(signal.iloc[t])
        if sig == 0:  # 信号回到空仓，解除"已止损"封锁
            stopped = False
        want_long = sig > 0 and not stopped
        if want_long and held == 0:
            shares = pf.cash / (c * (1 + buy_rate))
            if shares > 0:
                pf.buy(date, _SYMBOL, shares, c)
                entry_price = c
        elif not want_long and held > 0:
            pf.sell(date, _SYMBOL, held, c)
            entry_price = None

    equity = pd.Series(equity_curve, index=price.index)
    benchmark_equity = (1 + closes.pct_change().fillna(0.0)).cumprod() * initial_capital
    return pd.DataFrame(
        {
            "close": closes,
            "position": pd.Series(pos_curve, index=price.index),
            "daily_return": equity.pct_change().fillna(0.0),
            "equity": equity,
            "benchmark_equity": benchmark_equity,
        }
    )
