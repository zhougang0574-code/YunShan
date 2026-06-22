import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  BacktestResponse,
  getStrategies,
  OptimizeResponse,
  Params,
  runBacktest,
  runOptimize,
  StrategyInfo,
} from "../api/client";
import DatePicker from "../components/DatePicker";
import EquityChart from "../components/EquityChart";
import MetricCard from "../components/MetricCard";
import OptimizePanel from "../components/OptimizePanel";
import PriceSignalChart from "../components/PriceSignalChart";
import RobustnessPanel from "../components/RobustnessPanel";
import { METRIC_CARDS } from "../metrics";

const OPT_METRICS = ["sharpe_ratio", "annualized_return", "calmar_ratio", "sortino_ratio"];

function fmtDate(d: Date): string {
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${m}-${day}`;
}
// 默认区间：当年 1 月 1 日 ~ 今天
const DEFAULT_START = `${new Date().getFullYear()}-01-01`;
const DEFAULT_END = fmtDate(new Date());

// 模块级缓存：在 SPA 内切到别的页面再回到本页时，保留上次的查询条件与结果，
// 不会被重置回默认值（组件卸载/重挂载时从这里恢复）。
interface PageCache {
  symbol: string;
  start: string;
  end: string;
  strategyName: string;
  params: Params;
  optMetric: string;
  engine: "vectorized" | "event";
  stopLoss: string;
  takeProfit: string;
  result: BacktestResponse | null;
  optResult: OptimizeResponse | null;
}
const cache: PageCache = {
  symbol: "000001",
  start: DEFAULT_START,
  end: DEFAULT_END,
  strategyName: "",
  params: {},
  optMetric: "sharpe_ratio",
  engine: "vectorized",
  stopLoss: "",
  takeProfit: "",
  result: null,
  optResult: null,
};

export default function BacktestPage() {
  const [strategies, setStrategies] = useState<StrategyInfo[]>([]);
  const [symbol, setSymbol] = useState(cache.symbol);
  const [start, setStart] = useState(cache.start);
  const [end, setEnd] = useState(cache.end);
  const [strategyName, setStrategyName] = useState(cache.strategyName);
  const [params, setParams] = useState<Params>(cache.params);
  const [optMetric, setOptMetric] = useState(cache.optMetric);
  const [engine, setEngine] = useState<"vectorized" | "event">(cache.engine);
  const [stopLoss, setStopLoss] = useState(cache.stopLoss);
  const [takeProfit, setTakeProfit] = useState(cache.takeProfit);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<BacktestResponse | null>(cache.result);
  const [optResult, setOptResult] = useState<OptimizeResponse | null>(cache.optResult);

  const current = useMemo(
    () => strategies.find((s) => s.name === strategyName),
    [strategies, strategyName]
  );

  useEffect(() => {
    getStrategies()
      .then((list) => {
        setStrategies(list);
        // 仅在没有从缓存恢复出策略时才默认选第一个，避免覆盖上次的选择
        if (list.length && !strategyName) selectStrategy(list[0]);
      })
      .catch((e) => setError(`无法加载策略列表：${e.message}（后端启动了吗？）`));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 任意查询条件/结果变化时写回模块级缓存，供下次回到本页恢复
  useEffect(() => {
    Object.assign(cache, {
      symbol,
      start,
      end,
      strategyName,
      params,
      optMetric,
      engine,
      stopLoss,
      takeProfit,
      result,
      optResult,
    });
  }, [symbol, start, end, strategyName, params, optMetric, engine, stopLoss, takeProfit, result, optResult]);

  function selectStrategy(s: StrategyInfo) {
    setStrategyName(s.name);
    const init: Params = {};
    for (const [k, candidates] of Object.entries(s.param_space)) init[k] = candidates[0];
    setParams(init);
  }

  function pct(v: string): number | null {
    const n = Number(v);
    return v.trim() === "" || Number.isNaN(n) ? null : n / 100;
  }

  async function handleRun() {
    setLoading(true);
    setError("");
    setOptResult(null);
    try {
      const res = await runBacktest({
        symbol,
        start,
        end,
        strategy: strategyName,
        params,
        engine,
        stop_loss: engine === "event" ? pct(stopLoss) : null,
        take_profit: engine === "event" ? pct(takeProfit) : null,
      });
      setResult(res);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  async function handleOptimize(mode: "grid" | "walk_forward") {
    setLoading(true);
    setError("");
    try {
      const res = await runOptimize({ symbol, start, end, strategy: strategyName, metric: optMetric, mode, n_splits: 4 });
      setOptResult(res);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app">
      <aside className="sidebar">
        <label>股票代码</label>
        <input value={symbol} onChange={(e) => setSymbol(e.target.value)} />

        <label>开始日期</label>
        <DatePicker value={start} onChange={setStart} />

        <label>结束日期</label>
        <DatePicker value={end} onChange={setEnd} />

        <label>策略</label>
        <select
          value={strategyName}
          onChange={(e) => {
            const s = strategies.find((x) => x.name === e.target.value);
            if (s) selectStrategy(s);
          }}
        >
          {strategies.map((s) => (
            <option key={s.name} value={s.name}>
              {s.name}
            </option>
          ))}
        </select>

        {current &&
          Object.keys(current.param_space).map((p) => (
            <div key={p}>
              <label>{p}</label>
              <input
                type="number"
                value={params[p] ?? ""}
                step="any"
                onChange={(e) => setParams({ ...params, [p]: Number(e.target.value) })}
              />
            </div>
          ))}

        <label>回测引擎</label>
        <select value={engine} onChange={(e) => setEngine(e.target.value as "vectorized" | "event")}>
          <option value="vectorized">向量化（快）</option>
          <option value="event">事件驱动（支持止损止盈）</option>
        </select>

        {engine === "event" && (
          <>
            <label>止损 %（留空=不设）</label>
            <input type="number" step="any" value={stopLoss} onChange={(e) => setStopLoss(e.target.value)} />
            <label>止盈 %（留空=不设）</label>
            <input type="number" step="any" value={takeProfit} onChange={(e) => setTakeProfit(e.target.value)} />
          </>
        )}

        <button onClick={handleRun} disabled={loading || !strategyName}>
          {loading ? "运行中…" : "运行回测"}
        </button>

        <label>寻优目标指标</label>
        <select value={optMetric} onChange={(e) => setOptMetric(e.target.value)}>
          {OPT_METRICS.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>
        <button className="secondary" onClick={() => handleOptimize("grid")} disabled={loading || !strategyName}>
          网格寻优
        </button>
        <button className="secondary" onClick={() => handleOptimize("walk_forward")} disabled={loading || !strategyName}>
          走动检验
        </button>
      </aside>

      <main className="main">
        {error && <div className="error">{error}</div>}

        {!result && !error && <p className="muted">在左侧设置参数后点击「运行回测」。</p>}

        {result && (
          <>
            <div className="result-header">
              <span className="result-symbol">{result.symbol}</span>
              <span className="result-name">{result.name || "（未知名称）"}</span>
              <Link className="result-link" to={`/stock/${result.symbol}`}>
                查看个股详情 →
              </Link>
              <span className="result-strategy">策略：{result.strategy}</span>
            </div>
            <div className="cards">
              {METRIC_CARDS.map((m) => (
                <MetricCard key={m.key} meta={m} value={result.stats[m.key]} />
              ))}
            </div>
            <div className="panel">
              <PriceSignalChart series={result.series} />
            </div>
            <div className="panel">
              <EquityChart series={result.series} />
            </div>
          </>
        )}

        {optResult && (
          <>
            <div className="panel">
              <h3>
                参数{optResult.mode === "grid" ? "网格寻优" : "走动检验"}（目标：{optResult.metric}）
              </h3>
              <OptimizePanel data={optResult} paramKeys={current ? Object.keys(current.param_space) : []} />
            </div>
            {optResult.robustness && (
              <div className="panel">
                <RobustnessPanel data={optResult.robustness} />
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}
