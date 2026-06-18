import pandas as pd

from .base import register


@register("ma_cross")
class MovingAverageCrossStrategy:
    """双均线交叉策略：短期均线高于长期均线时持有，反之空仓。"""

    def __init__(self, short_window: int = 5, long_window: int = 20):
        if short_window >= long_window:
            raise ValueError("short_window 必须小于 long_window")
        self.short_window = short_window
        self.long_window = long_window

    def generate_signal(self, price: pd.DataFrame) -> pd.Series:
        short_ma = price["close"].rolling(self.short_window).mean()
        long_ma = price["close"].rolling(self.long_window).mean()
        return (short_ma > long_ma).astype(float)

    @classmethod
    def param_space(cls) -> dict[str, list]:
        return {"short_window": [5, 10, 20], "long_window": [20, 30, 60]}
