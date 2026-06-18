"""引擎无关的抽象接口。

向量化引擎与（未来的）事件驱动引擎遵循同一接口，策略产出的 signal 不绑定
具体引擎，Phase 4 接入事件驱动引擎时已有策略零改动。
"""

from typing import Protocol

import pandas as pd


class BacktestEngine(Protocol):
    def run(
        self,
        price: pd.DataFrame,
        signal: pd.Series,
        initial_capital: float = ...,
    ) -> pd.DataFrame:
        """输入行情与仓位信号，输出含权益曲线等列的结果 DataFrame。"""
        ...
