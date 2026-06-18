"""回测接口：按策略名+参数运行回测，返回指标与逐日序列。"""

from fastapi import APIRouter, HTTPException

from quant import get_daily, run_strategy_backtest

from ..schemas import BacktestRequest, BacktestResponse, BacktestSeries

router = APIRouter(prefix="/backtest", tags=["backtest"])


@router.post("", response_model=BacktestResponse)
def run(req: BacktestRequest) -> BacktestResponse:
    try:
        price = get_daily(req.symbol, req.start, req.end, adjust=req.adjust)
    except RuntimeError as err:
        raise HTTPException(status_code=502, detail=str(err)) from err
    if price.empty:
        raise HTTPException(status_code=404, detail="未获取到数据")

    try:
        result, stats = run_strategy_backtest(price, req.strategy, req.params)
    except KeyError as err:  # 未知策略
        raise HTTPException(status_code=400, detail=str(err)) from err
    except (ValueError, TypeError) as err:  # 参数非法
        raise HTTPException(status_code=422, detail=f"参数不合法：{err}") from err

    series = BacktestSeries(
        dates=[str(d.date()) for d in result.index],
        close=result["close"].tolist(),
        equity=result["equity"].tolist(),
        benchmark_equity=result["benchmark_equity"].tolist(),
        position=result["position"].tolist(),
    )
    return BacktestResponse(
        symbol=req.symbol,
        strategy=req.strategy,
        params=req.params,
        stats={k: float(v) for k, v in stats.items()},
        series=series,
    )
