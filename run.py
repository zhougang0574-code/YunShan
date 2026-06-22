#!/usr/bin/env python3
"""一键启动 YunShan。

一个进程同时服务 REST API（/api/*）和打包好的 React 前端（/）。
首次运行会自动构建前端，之后直接复用 frontend/dist。

用法：
    py -3 run.py                # 自动构建前端（如缺）→ 启动，访问 http://127.0.0.1:8000
    py -3 run.py --rebuild      # 前端代码改过后，强制重新构建
    py -3 run.py --no-build     # 跳过前端构建（dist 已存在 / 只想跑后端）
    py -3 run.py --port 9000    # 换端口
    py -3 run.py --reload       # 后端代码热重载（开发用）

构建前端需要本机装有 Node.js（提供 npm）。仅当 dist 不存在或加 --rebuild 时才会构建。
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / "frontend"
DIST = FRONTEND / "dist"
_SHELL = os.name == "nt"  # Windows 上 npm 是 .cmd，需经 shell 调用


def _find_npm() -> str:
    npm = shutil.which("npm") or shutil.which("npm.cmd")
    if not npm:
        sys.exit(
            "找不到 npm。构建前端需要先安装 Node.js：https://nodejs.org/\n"
            "（或在别处构建好 frontend/dist 后，用 py -3 run.py --no-build 启动）"
        )
    return npm


def build_frontend(force: bool = False) -> None:
    index = DIST / "index.html"
    if index.is_file() and not force:
        print(f"[run] 复用已有前端构建产物：{index}（如改过前端代码，请加 --rebuild）")
        return

    npm = _find_npm()
    if not (FRONTEND / "node_modules").is_dir():
        print("[run] 安装前端依赖：npm install …")
        subprocess.run([npm, "install"], cwd=FRONTEND, check=True, shell=_SHELL)
    print("[run] 构建前端：npm run build …")
    subprocess.run([npm, "run", "build"], cwd=FRONTEND, check=True, shell=_SHELL)
    print(f"[run] 前端构建完成：{DIST}")


def main() -> None:
    parser = argparse.ArgumentParser(description="一键启动 YunShan（API + 前端同进程）")
    parser.add_argument("--host", default="127.0.0.1", help="监听地址（默认 127.0.0.1）")
    parser.add_argument("--port", type=int, default=8000, help="监听端口（默认 8000）")
    parser.add_argument("--rebuild", action="store_true", help="强制重新构建前端")
    parser.add_argument("--no-build", action="store_true", help="跳过前端构建")
    parser.add_argument("--reload", action="store_true", help="后端代码热重载（开发用）")
    args = parser.parse_args()

    if not args.no_build:
        build_frontend(force=args.rebuild)

    try:
        import uvicorn
    except ImportError:
        sys.exit("缺少 uvicorn，请先安装依赖：py -3 -m pip install -r requirements.txt")

    print(f"[run] 启动 → http://{args.host}:{args.port}  （API 文档 /docs）")
    uvicorn.run("backend.main:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
