import pandas as pd

from ..factors import technical
from .base import register


@register("macd_trend")
class MacdTrendStrategy:
    """MACD 趋势：DIF 在 DEA 上方（柱状 hist > 0）时持有，否则空仓。"""

    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9):
        if fast >= slow:
            raise ValueError("fast 必须小于 slow")
        self.fast = fast
        self.slow = slow
        self.signal = signal

    def generate_signal(self, price: pd.DataFrame) -> pd.Series:
        macd = technical.macd(price, self.fast, self.slow, self.signal)
        return (macd["hist"] > 0).astype(float)

    @classmethod
    def param_space(cls) -> dict[str, list]:
        return {"fast": [8, 12], "slow": [21, 26], "signal": [9]}
