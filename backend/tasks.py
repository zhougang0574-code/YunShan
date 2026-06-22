"""轻量后台任务注册表（进程内，单用户场景够用）。

截面打分要遍历股票池、可能逐股拉价格，耗时较长，不能在请求里同步跑完。这里提供一个
最小的内存任务存储：提交任务立即返回 ``task_id``，任务在 ``BackgroundTasks`` 线程里跑，
过程中回写 ``progress``，前端轮询 ``GET /screening/{task_id}`` 取进度/结果。

不引入 Celery/Redis 等重型队列——重启即清空，符合本地研究系统定位。
"""

import threading
import uuid

_LOCK = threading.Lock()
_TASKS: dict[str, dict] = {}


def create() -> str:
    task_id = uuid.uuid4().hex[:12]
    with _LOCK:
        _TASKS[task_id] = {
            "status": "pending",
            "progress": 0.0,
            "result": None,
            "error": None,
        }
    return task_id


def get(task_id: str) -> dict | None:
    with _LOCK:
        task = _TASKS.get(task_id)
        return dict(task) if task else None


def set_progress(task_id: str, progress: float) -> None:
    with _LOCK:
        if task_id in _TASKS:
            _TASKS[task_id]["status"] = "running"
            _TASKS[task_id]["progress"] = round(float(progress), 4)


def finish(task_id: str, result) -> None:
    with _LOCK:
        if task_id in _TASKS:
            _TASKS[task_id].update(status="done", progress=1.0, result=result)


def fail(task_id: str, error: str) -> None:
    with _LOCK:
        if task_id in _TASKS:
            _TASKS[task_id].update(status="error", error=error)
