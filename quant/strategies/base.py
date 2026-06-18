"""策略接口与注册表。

策略：输入价格 DataFrame，输出仓位信号 Series（1=持有，0=空仓），index 对齐。
注册表让策略可按名字发现（供参数寻优、后端 API、前端下拉使用），每个策略通过
``param_space()`` 暴露可寻优的参数候选值。
"""

from typing import Protocol

import pandas as pd


class Strategy(Protocol):
    name: str

    def generate_signal(self, price: pd.DataFrame) -> pd.Series: ...

    @classmethod
    def param_space(cls) -> dict[str, list]: ...


REGISTRY: dict[str, type] = {}


def register(name: str):
    """类装饰器：把策略登记进全局注册表。"""

    def decorator(cls):
        cls.name = name
        REGISTRY[name] = cls
        return cls

    return decorator


def get_strategy(name: str) -> type:
    if name not in REGISTRY:
        raise KeyError(f"未知策略 '{name}'，可选：{list(REGISTRY)}")
    return REGISTRY[name]


def list_strategies() -> dict[str, dict]:
    """返回 {策略名: 参数空间}，供发现与寻优。"""
    return {name: cls.param_space() for name, cls in REGISTRY.items()}
