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
import EquityChart from "../components/EquityChart";
import MetricCard from "../components/MetricCard";
import OptimizePanel from "../components/OptimizePanel";
import PriceSignalChart from "../components/PriceSignalChart";
import RobustnessPanel from "../components/RobustnessPanel";
import { METRIC_CARDS } from "../metrics";

const OPT_METRICS = ["sharpe_ratio", "annualized_return", "calmar_ratio", "sortino_ratio"];

export default function BacktestPage() {
  const [strategies, setStrategies] = useState<StrategyInfo[]>([]);
  const [symbol, setSymbol] = useState("000001");
  const [start, setStart] = useState("2022-01-01");
  const [end, setEnd] = useState("2023-12-31");
  const [strategyName, setStrategyName] = useState("");
  const [params, setParams] = useState<Params>({});
  const [optMetric, setOptMetric] = useState("sharpe_ratio");
  const [engine, setEngine] = useState<"vectorized" | "event">("vectorized");
  const [stopLoss, setStopLoss] = useState("");
  const [takeProfit, setTakeProfit] = useState("");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<BacktestResponse | null>(null);
  const [optResult, setOptResult] = useState<OptimizeResponse | null>(null);

  const current = useMemo(
    () => strategies.find((s) => s.name === strategyName),
    [strategies, strategyName]
  );

  useEffect(() => {
    getStrategies()
      .then((list) => {
        setStrategies(list);
        if (list.length) selectStrategy(list[0]);
      })
      .catch((e) => setError(`无法加载策略列表：${e.message}（后端启动了吗？）`));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
        <input type="date" value={start} onChange={(e) => setStart(e.target.value)} />

        <label>结束日期</label>
        <input type="date" value={end} onChange={(e) => setEnd(e.target.value)} />

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
