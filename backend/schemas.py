"""API 请求/响应模型（Pydantic）。"""

from typing import Any, Literal

from pydantic import BaseModel, Field

from quant import config


class StrategyInfo(BaseModel):
    name: str
    param_space: dict[str, list[Any]]


class DataInfo(BaseModel):
    symbol: str
    name: str = ""
    adjust: str
    rows: int
    start: str | None = None
    end: str | None = None


class BacktestRequest(BaseModel):
    symbol: str = Field(..., examples=["000001"])
    start: str = Field(..., examples=["2022-01-01"])
    end: str = Field(..., examples=["2023-12-31"])
    strategy: str = Field(..., examples=["ma_cross"])
    params: dict[str, Any] = Field(default_factory=dict)
    adjust: str = config.DEFAULT_ADJUST


class BacktestSeries(BaseModel):
    """逐日序列，按列存放便于前端直接画图。"""

    dates: list[str]
    close: list[float]
    equity: list[float]
    benchmark_equity: list[float]
    position: list[float]


class BacktestResponse(BaseModel):
    symbol: str
    name: str = ""
    strategy: str
    params: dict[str, Any]
    stats: dict[str, float]
    series: BacktestSeries


class OptimizeRequest(BaseModel):
    symbol: str
    start: str
    end: str
    strategy: str
    adjust: str = config.DEFAULT_ADJUST
    metric: str = "sharpe_ratio"
    mode: Literal["grid", "walk_forward"] = "grid"
    n_splits: int = 4
    param_grid: dict[str, list[Any]] | None = None


class OptimizeResponse(BaseModel):
    symbol: str
    strategy: str
    metric: str
    mode: str
    results: list[dict[str, Any]]
