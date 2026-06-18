import numpy as np
import pandas as pd

from ..factors import technical
from .base import register


@register("rsi_reversal")
class RsiReversalStrategy:
    """RSI 反转：RSI 跌破 oversold 进场持有，升破 overbought 离场空仓，区间内维持仓位。"""

    def __init__(self, window: int = 14, oversold: float = 30.0, overbought: float = 70.0):
        if oversold >= overbought:
            raise ValueError("oversold 必须小于 overbought")
        self.window = window
        self.oversold = oversold
        self.overbought = overbought

    def generate_signal(self, price: pd.DataFrame) -> pd.Series:
        rsi = technical.rsi(price, self.window)
        raw = pd.Series(np.nan, index=price.index)
        raw[rsi < self.oversold] = 1.0
        raw[rsi > self.overbought] = 0.0
        return raw.ffill().fillna(0.0)

    @classmethod
    def param_space(cls) -> dict[str, list]:
        return {
            "window": [7, 14, 21],
            "oversold": [20.0, 30.0],
            "overbought": [70.0, 80.0],
        }
