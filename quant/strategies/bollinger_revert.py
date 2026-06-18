import numpy as np
import pandas as pd

from ..factors import technical
from .base import register


@register("bollinger_revert")
class BollingerRevertStrategy:
    """布林带均值回归：收盘跌破下轨进场持有，回到中轨上方离场空仓。"""

    def __init__(self, window: int = 20, num_std: float = 2.0):
        self.window = window
        self.num_std = num_std

    def generate_signal(self, price: pd.DataFrame) -> pd.Series:
        bands = technical.bollinger(price, self.window, self.num_std)
        close = price["close"]
        raw = pd.Series(np.nan, index=price.index)
        raw[close < bands["lower"]] = 1.0
        raw[close > bands["mid"]] = 0.0
        return raw.ffill().fillna(0.0)

    @classmethod
    def param_space(cls) -> dict[str, list]:
        return {"window": [10, 20, 30], "num_std": [1.5, 2.0, 2.5]}
