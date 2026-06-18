"""因子接口。

因子是「价格 DataFrame → 指标 Series（或多列 DataFrame）」的纯函数/可调用对象，
index 与输入对齐。技术指标、量价、基本面因子都遵循同一约定，便于组合与复用。
"""

from typing import Protocol

import pandas as pd


class Factor(Protocol):
    def __call__(self, price: pd.DataFrame) -> pd.Series | pd.DataFrame: ...
