"""把含 numpy 标量 / NaN 的记录转成 JSON 可序列化的原生类型，供各路由复用。"""

import math

import numpy as np


def clean_records(records: list[dict]) -> list[dict]:
    return [{k: clean_value(v) for k, v in row.items()} for row in records]


def clean_value(v):
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, (np.floating, float)):
        f = float(v)
        return None if math.isnan(f) else f
    if isinstance(v, np.bool_):
        return bool(v)
    return v
