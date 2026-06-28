"""板块当月涨幅榜接口：提交板块列表（后台逐股算当月涨幅）+ 轮询进度/结果。

逐股拉日线算当月至今涨幅较慢，与 ``screening`` 一样走后台任务：
- ``POST /leaders``：提交行业板块列表，立即返回 ``task_id``。
- ``GET  /leaders/{task_id}``：轮询任务状态/进度，完成后取 Top N 龙头股。
可选板块列表复用 ``GET /universe``（其中的 ``industries``）。
"""

from fastapi import APIRouter, BackgroundTasks, HTTPException

from quant import movers
from quant.experiments import record as record_experiment

from .. import serialize, tasks
from ..schemas import LeadersRequest, ScreeningStatusResponse, TaskSubmitResponse

router = APIRouter(prefix="/leaders", tags=["leaders"])


def _run(task_id: str, req: LeadersRequest) -> None:
    try:
        df = movers.month_leaders(
            industries=req.industries,
            top_n=req.top_n,
            max_symbols=req.max_symbols,
            progress=lambda p: tasks.set_progress(task_id, p),
        )
        results = serialize.clean_records(df.to_dict(orient="records"))
        tasks.finish(task_id, results)
        record_experiment(
            kind="leaders",
            params={"industries": req.industries, "top_n": req.top_n},
            summary={"candidates": len(results)},
        )
    except Exception as err:  # 后台任务里任何失败都记录到任务状态，避免静默
        tasks.fail(task_id, f"{type(err).__name__}: {err}")


@router.post("", response_model=TaskSubmitResponse)
def submit(req: LeadersRequest, background: BackgroundTasks) -> TaskSubmitResponse:
    task_id = tasks.create()
    background.add_task(_run, task_id, req)
    return TaskSubmitResponse(task_id=task_id)


@router.get("/{task_id}", response_model=ScreeningStatusResponse)
def status(task_id: str) -> ScreeningStatusResponse:
    task = tasks.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在（可能已重启清空）")
    return ScreeningStatusResponse(
        task_id=task_id,
        status=task["status"],
        progress=task["progress"],
        error=task["error"],
        results=task["result"],
    )
