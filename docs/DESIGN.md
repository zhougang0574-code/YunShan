# YunShan 股票量化系统 — 总体设计方案

## Context

YunShan 是一款**研究型 A 股量化回测系统**（后续扩展美股），目标是做出一款能力优秀、前后端分离的系统，把「数据 → 因子/策略 → 回测 → 业绩分析 → 可视化」这条链路做到扎实、可复用、可扩展。

定位与边界（本阶段明确不做）：
- **纯研究回测，不碰实盘**：不设计行情推送、订单管理、实时风控、券商接口、资金安全等模块。架构会为未来扩展预留接口，但本阶段不实现。
- **单用户**：不做多用户/登录鉴权/数据隔离，本地或单人部署即可。

技术总基调：
- **后端 Python（FastAPI）**：与核心计算库同语言，API 层可直接函数调用计算层，复用 akshare / pandas / numpy 生态，无跨语言集成成本。
- **前端 React + TypeScript + 图表库**：做成专业的交互式 SPA，前后端通过 REST（必要时 WebSocket/轮询）通信。
- **`quant/` 核心库与 Web 层解耦**：核心库是纯 Python 包，不依赖 FastAPI/Streamlit，既能被 API 调用，也能在 Notebook/脚本里直接用。

> 现状：上一版本已用 Streamlit 跑通最小闭环（数据→双均线→回测→指标→页面）。本设计是在此基础上的**架构升级与能力扩展**，Streamlit 保留为可选的快速验证入口，正式交付以 FastAPI + React 为准。

## 总体架构

前后端分离 + 核心计算库三层结构：

```
YunShan/
├── quant/                         # 核心计算库（纯 Python，不依赖 Web 框架）
│   ├── __init__.py
│   ├── config.py                  # 配置（数据目录、交易成本默认值、数据源参数等）
│   ├── data/
│   │   ├── fetcher.py             # 数据源适配（akshare A股；预留 yfinance 美股）
│   │   ├── storage.py             # 本地存储（DuckDB/Parquet），范围感知 + 增量更新
│   │   ├── calendar.py            # 交易日历（校验日期、对齐缺口）
│   │   └── updater.py             # 增量更新/定时同步逻辑
│   ├── factors/                   # 因子库
│   │   ├── base.py                # 因子接口
│   │   └── technical.py           # 技术指标因子（MA/MACD/RSI/布林带…）
│   ├── strategies/
│   │   ├── base.py                # 引擎无关的策略接口
│   │   ├── ma_cross.py            # 双均线交叉（示例）
│   │   └── ...                    # 其他策略
│   ├── engine/
│   │   ├── base.py                # 引擎抽象接口（策略/组合接口引擎无关）
│   │   ├── vectorized.py          # 向量化引擎 + 成本模型 + 多标的组合（Phase 1）
│   │   └── event_driven.py        # 事件驱动引擎（Phase 2，路径依赖/真实性终检）
│   ├── portfolio.py               # 组合与资金管理（仓位、现金、成交记录）
│   ├── costs.py                   # 交易成本模型（手续费/滑点/印花税/过户费）
│   ├── metrics.py                 # 业绩指标（含基准对比、交易级胜率、Sortino/Calmar…）
│   └── optimize.py                # 参数寻优 / 走动检验（walk-forward）
├── backend/                       # FastAPI 后端（API 层，薄封装，调用 quant）
│   ├── main.py                    # 应用入口
│   ├── routers/                   # 路由：symbols / backtest / strategies / optimize / data
│   ├── schemas.py                 # Pydantic 请求/响应模型
│   ├── tasks.py                   # 长耗时回测/寻优的后台任务（BackgroundTasks/进程池）
│   └── scheduler.py               # 定时数据更新（APScheduler）
├── frontend/                      # React + TypeScript SPA
│   ├── src/
│   │   ├── api/                   # 后端接口封装
│   │   ├── pages/                 # 回测 / 策略对比 / 参数寻优 / 数据管理
│   │   └── components/            # K线+信号图、净值曲线、回撤图、指标卡片（ECharts/lightweight-charts）
│   └── package.json
├── tests/                         # 单元/集成测试（pytest）
├── data/                          # 本地数据缓存（gitignore）
├── app.py                         # 可选：Streamlit 快速验证入口（保留）
├── requirements.txt
└── README.md
```

**技术选型说明：**

| 层 | 选型 | 理由 |
|---|---|---|
| 数据源 | `akshare`（A股），预留 `yfinance`（美股） | 免费、覆盖全；通过 `fetcher` 适配层统一接口，换源不影响上层 |
| 存储 | 本地 **DuckDB**（或分区 Parquet） | 支持按 symbol+adjust+日期范围查询、增量追加；比"一股一个 parquet 文件"更可靠，规模上来也不卡 |
| 回测引擎 | 自建**向量化**（Phase 1）+ **事件驱动**（Phase 2） | 向量化跑得快、看得懂、支撑参数寻优；事件驱动做止损止盈等路径依赖逻辑和真实性终检。接口引擎无关，策略不用重写。详见下文「回测引擎」 |
| 后端 | `FastAPI` + Pydantic | 与计算层同语言、异步、自动生成 OpenAPI 文档，前端对接顺畅 |
| 前端 | `React` + `TypeScript` + `ECharts`/`lightweight-charts` | 做专业交互式图表与多页面分析，前后端彻底分离 |
| 定时任务 | `APScheduler` | 收盘后增量更新行情，无需引入 Celery 这类重型队列（单用户场景够用） |

## 回测引擎（核心模块详解）

引擎是系统心脏：输入「行情 + 信号」，模拟逐日持仓/现金/成交/成本，输出净值曲线与业绩指标。采用**两种引擎分工 + 分阶段**实现：

- **向量化引擎（Phase 1，先建）**：pandas/numpy 一次性算完整条净值。快、代码清晰，适合多策略筛选与**参数寻优**。在现有 0/1 满仓逻辑上升级为：
  - **成本模型**：手续费、滑点、印花税（卖出 0.05%/0.1%）、过户费——按换手计入，参数可配。
  - **多标的组合**：支持组合权重、资金分配、现金管理，而非单股满仓。
  - **基准对比**：内置买入持有基准，输出超额收益。
  - 严格防未来函数：信号 T 日生成、T+1 生效（现有 `signal.shift(1)` 已正确，保留）。
- **事件驱动引擎（Phase 2，预留接口后建）**：逐根 K 线重放（行情→信号→下单→撮合→更新组合），自然支持**止损止盈、限价单、部分成交、动态仓位**；结构贴近实盘，为未来扩展打底。
- **引擎无关接口**：Phase 1 就把「策略接口」「组合/撮合接口」抽象好，Phase 2 接事件驱动引擎时已有策略零改动。
- 备选：`vectorbt`（向量化、极快）/`backtrader`（事件驱动、成熟）作为后续可选项；本阶段以自建为主，保证"看得懂每一行计算"。

## 已发现并需修正的问题（来自对现有代码的审查）

新设计已针对性修复以下现有实现中的问题：

1. **数据缓存正确性 bug（必修）**
   - 现状：缓存只按 `symbol` 存，**忽略 `adjust`**（qfq/hfq/不复权互相覆盖，导致价格错误）。
   - 现状：缓存**忽略请求日期范围**——首次拉 2022–2023 后再请求 2020–2024，会命中缓存只返回子集，缺失区间永不补齐。
   - 新设计：存储按 `symbol + adjust` 维度组织，**范围感知 + 增量更新**（缺失区间按需补拉、新交易日追加），并用交易日历校验缺口。
2. **指标口径修正**
   - `win_rate` 现统计"每日上涨天数占比"，与"胜率"语义不符 → 新增**交易级胜率**（按每笔完整买卖盈亏统计），日级胜率单列。
   - `sharpe_ratio` 把空仓日 0 收益计入会系统性低估 → 提供"全周期/仅持仓期"两种口径。
   - 新增**基准对比**（买入持有）、Sortino、Calmar、换手率、持仓暴露等。
3. **工程化补齐**：配置管理（`config.py`）、日志、akshare 限流/重试、`tests/` 测试、交易日历校验。

## 实现步骤（按阶段推进）

**Phase 0 — 核心库重构（在现有代码上演进）**
- 将 `quant/` 重组为 `data/ factors/ strategies/ engine/` 等子包；现有 `data_fetcher/storage/backtest/metrics/ma_cross` 平移并修复上述 bug。
- 引入 `config.py`、`costs.py`、`portfolio.py`、交易日历。

**Phase 1 — 能力完善（研究闭环升级）**
- 升级向量化引擎：成本模型 + 多标的组合 + 基准对比。
- 修正并扩展 `metrics.py`（交易级胜率、Sortino/Calmar、基准超额等）。
- `factors/`：技术指标因子库（MA/MACD/RSI/布林带等），多策略模板。
- `optimize.py`：参数网格寻优 + **walk-forward 走动检验** + 过拟合检查。
- `tests/`：核心模块单测，确保无未来函数、指标数值正确。

**Phase 2 — 后端 API**
- FastAPI 路由：`/symbols`（查/搜代码）、`/data`（拉取/更新状态）、`/backtest`（运行回测）、`/strategies`（列出参数）、`/optimize`（参数寻优，后台任务 + 进度查询）。
- Pydantic schema 定义请求/响应；长耗时回测/寻优走后台任务，前端轮询进度。
- `scheduler.py`：APScheduler 收盘后增量更新行情 + 数据质量校验。

**Phase 3 — 前端 SPA**
- React + TS 工程；`api/` 封装后端接口。
- 页面：① 单策略回测（选股票/区间/参数 → K线+信号、净值、回撤、指标卡）② 多策略/多参数对比 ③ 参数寻优结果热力图 ④ 数据管理（已缓存标的、更新状态）。
- 图表用 ECharts / lightweight-charts。

**Phase 4 — 事件驱动引擎（预留接口已就绪）**
- 实现 `engine/event_driven.py`，支持止损止盈、限价单等路径依赖策略；已有策略零改动接入。

## 验证方式

- **核心库**：pytest 覆盖——构造已知行情验证回测净值/成本/指标数值正确；专门用例验证"无未来函数"（把未来数据打乱不应改变历史信号）；缓存增量更新用例（先拉小区间再拉大区间应补齐而非返回子集）。
- **后端**：`uvicorn` 起服务，用 OpenAPI 文档 / curl 跑通各端点；长耗时回测的后台任务+进度查询可用。
- **前端**：`npm run dev` 起前端，连后端跑一次完整回测，确认 K线/净值/回撤/指标四类视图与寻优页正常。
- **端到端**：选股票→跑策略→看指标→改参数寻优→对比，全链路无报错、数值合理（最大回撤为负、年化为百分数、夏普量级正常、有基准超额）。

## 后续阶段（本次不做，仅记录）

- 美股数据源（yfinance）接入（适配层已预留）。
- 更丰富的因子库与机器学习因子。
- 实盘/模拟盘对接（订单、实时风控、券商接口）——需引入实时行情、撮合、资金安全模块，届时事件驱动引擎可直接复用。
- 多用户与权限（如需对外提供）。

## 实施状态

- 上一版本：Streamlit 最小闭环已完成（数据→双均线→回测→指标→页面）。
- 本设计：架构升级为 FastAPI + React + 解耦核心库；Phase 0–4 规划如上，按阶段推进。
- **Phase 0 已完成**（2026-06-18）：
  - `quant/` 重组为 `data/ engine/ strategies/` 子包 + `config/costs/portfolio/metrics`。
  - **修复缓存 bug**：缓存按 `symbol+adjust` 分文件、记录已请求区间、增量补拉头尾缺口（`quant/data/`）。
  - 新增交易日历 `quant/data/calendar.py`、成本模型 `costs.py`、组合账户 `portfolio.py`。
  - 向量化引擎接入成本模型 + 买入持有基准（`quant/engine/vectorized.py`）。
  - 指标修正：交易级胜率、Sortino/Calmar、基准超额、active-only 夏普（`metrics.py`）。
  - `tests/` 7 个用例全绿（缓存增量/adjust隔离/无未来函数/成本扣减/基准/交易胜率）。
  - 已在用户本机用真实行情端到端验证通过（此前失败是本地 Clash 代理 7890 未运行导致，与代码无关）。
- **Phase 1 已完成**（2026-06-18）：
  - 因子库 `quant/factors/technical.py`：SMA/EMA/MACD/RSI/布林带/动量/ATR。
  - 策略扩展 + 注册表 `quant/strategies/`：新增 `rsi_reversal`/`macd_trend`/`bollinger_revert`，
    `base.py` 提供 `register`/`get_strategy`/`list_strategies` 与每策略 `param_space()`（供寻优与后端发现）。
  - 参数寻优 `quant/optimize.py`：`grid_search`（按指标排序）+ `walk_forward`（样本内选参/样本外检验，识别过拟合）。
  - `app.py` 升级：策略下拉 + 动态参数 + 可选网格寻优面板（含双参数热力图）。
  - `tests/` 增至 18 用例全绿（因子范围/对齐/无未来值、策略注册、寻优排序、walk-forward 形状）。
  - 行情源直连修复：`config.py` 自动把 eastmoney/sina 加入 `no_proxy`，绕开本地代理避免 ProxyError。
- **Phase 2 已完成**（2026-06-18）：FastAPI 后端 `backend/`
  - `main.py`：应用入口 + CORS（放行本地 React 端口）+ `/health`；交互文档 `/docs`。
  - `schemas.py`：Pydantic 请求/响应模型。
  - `routers/`：`GET /strategies`（列策略+参数空间）、`GET /data/{symbol}`（拉/查行情）、
    `POST /backtest`（运行回测，返回指标+逐日序列）、`POST /optimize`（grid / walk_forward）。
  - `quant/runner.py`：按策略名跑回测的共享入口（后端与页面复用）。
  - `tests/` 增至 26 用例全绿（含 8 个后端 TestClient 用例，离线 monkeypatch get_daily）。
  - 启动：`uvicorn backend.main:app --reload`，文档 http://127.0.0.1:8000/docs
- **Phase 3 已完成**（2026-06-18）：React + TypeScript + ECharts 前端 `frontend/`
  - Vite 工程；`src/api/client.ts` 封装后端接口与类型；`src/metrics.ts` 指标元信息（含**问号悬停说明**）。
  - `App.tsx`：策略下拉（来自 `/strategies`）+ 动态参数 + symbol/日期。
  - 组件：`MetricCard`、`PriceSignalChart`、`EquityChart`（策略 vs 基准）、`OptimizePanel`（结果表 + 双参数热力图）。
  - 指标卡为新手优化：每张卡按阈值自动评级（🟢不错/🟡一般/🔴偏差/⚪参考彩色徽章）+ 一句大白话点评，
    数字好坏一眼可懂；详细解释仍保留在问号 tooltip（评级规则与点评见 `frontend/src/metrics.ts`）。
  - dev 经 `/api` 代理到后端；`vite.config.ts` 强制 loopback 不走 HTTP 代理（避免本地 Clash 代理导致 502）。
  - `npm run build` 通过 tsc 类型检查；前后端联调链路（前端→vite 代理→FastAPI→quant）已实测打通。
  - 启动见根目录 `README.md`：终端1 `uvicorn backend.main:app --reload`，终端2 `cd frontend && npm run dev`，浏览器开 http://localhost:5173。
- 至此 Phase 0–3 全部完成：核心研究能力 + 后端 API + React 前端，端到端可用。仍待后续：多标的组合、scheduler 定时更新、事件驱动引擎（Phase 4）。
