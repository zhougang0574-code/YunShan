# YunShan 股票量化回测系统

研究型 A 股量化回测系统：数据 → 因子/策略 → 回测 → 业绩分析 → 可视化。
单进程一体化部署（FastAPI 同时服务 API 和前端页面），纯研究回测（不接实盘）。
设计文档见 [`docs/DESIGN.md`](docs/DESIGN.md)。

## 架构

- `quant/` — 核心计算库（纯 Python）：数据/因子/策略/回测引擎（向量化+事件驱动）/指标/
  参数寻优/稳健性检验/截面选股/个股信号/实验记录
- `backend/` — FastAPI：把核心能力封装为 `/api/*` REST 接口，**并托管打包后的前端页面**
- `frontend/` — React + TypeScript + ECharts 前端（react-router 多页面），构建到 `frontend/dist`
- `run.py` / `start.bat` — **一键启动**：自动构建前端 + 起一个进程同时服务 API 和页面
- `app.py` — Streamlit 快速验证入口（可选，单文件即可跑）
- `tests/` — pytest 测试

## 功能一览

- **策略回测**：多策略 + 动态参数；向量化引擎（快）或事件驱动引擎（支持止损/止盈）。
- **参数寻优**：网格寻优（含双参数热力图）/ walk-forward 走动检验，并附 **Deflated Sharpe +
  蒙特卡洛置换**稳健性检验，判断结果是真本事还是过拟合/运气。
- **截面选股**：选股票池（全市场/指数/行业）+ 基本面与技术因子加权打分排名（后台任务 + 进度轮询）。
- **个股详情**：分钟级轮询近实时报价 + 分时图 + 技术/基本面/资金面"注意点"标签。
- **历史记录**：回测/寻优/选股运行自动落地，可回看入参与结果做对比。
- **登录与收藏**：用户名+密码注册登录（轻量本地 SQLite），每个用户维护各自的自选股
  收藏；个股详情页一键 ☆ 收藏，「我的收藏」页集中查看。首次使用在登录页注册即可。

## 环境准备

```bash
# Python 依赖（项目根目录）
py -3 -m pip install -r requirements.txt
```

> 前端依赖与构建由 `run.py` 在首次启动时自动完成，无需手动 `npm install`。
> 仅需本机装有 [Node.js](https://nodejs.org/)（提供 npm）。

> 行情源（eastmoney/sina）是国内站点，代码已自动让它们直连、绕开本地代理
> （如 Clash 127.0.0.1:7890），无需手动 unset 代理。

## 启动（一键）

只要**一个命令**，在项目根目录：

```bash
py -3 run.py
```

Windows 下也可直接**双击 `start.bat`**。首次会自动 `npm install` + 构建前端（约几十秒），
之后复用构建产物秒起。启动后浏览器打开 **http://127.0.0.1:8000** 即可，顶部导航在四个页面间
切换：**策略回测 / 截面选股 / 个股详情 / 历史记录**；API 文档在 `/docs`。

常用参数：

```bash
py -3 run.py --rebuild      # 改过前端代码后，强制重新构建
py -3 run.py --port 9000    # 换端口
py -3 run.py --no-build     # 跳过前端构建（dist 已存在）
py -3 run.py --reload       # 后端代码热重载（开发用）
```

### 需要前端热更新（HMR）时

日常开发若想改前端即时生效，可仍按前后端分离方式跑两个终端：

```bash
py -3 -m uvicorn backend.main:app --reload   # 终端 1：后端 :8000
cd frontend && npm run dev                   # 终端 2：前端 :5173（经 /api 代理到后端）
```

## 仅用 Streamlit 快速看（可选）

```bash
py -3 -m streamlit run app.py
```

## 跑测试

```bash
py -3 -m pytest tests/ -v
```
