import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  FactorInfo,
  getFactors,
  getScreeningStatus,
  getUniverses,
  ScreeningStatus,
  submitScreening,
  UniverseList,
} from "../api/client";

interface Selected {
  [key: string]: number; // factor key -> weight
}

export default function ScreeningPage() {
  const [universes, setUniverses] = useState<UniverseList | null>(null);
  const [factors, setFactors] = useState<Record<string, FactorInfo>>({});
  const [universeKey, setUniverseKey] = useState("index:000300");
  const [selected, setSelected] = useState<Selected>({});
  const [topN, setTopN] = useState(30);
  const [maxSymbols, setMaxSymbols] = useState(300);
  const [lookback, setLookback] = useState(180);

  const [error, setError] = useState("");
  const [status, setStatus] = useState<ScreeningStatus | null>(null);
  const pollRef = useRef<number | null>(null);

  useEffect(() => {
    getUniverses().then(setUniverses).catch((e) => setError(e.message));
    getFactors()
      .then((f) => {
        setFactors(f);
        // 默认选两个基本面因子
        setSelected({ pe: 1, mom_60d: 1 });
      })
      .catch((e) => setError(e.message));
    return () => {
      if (pollRef.current) window.clearInterval(pollRef.current);
    };
  }, []);

  function toggle(key: string) {
    setSelected((s) => {
      const next = { ...s };
      if (key in next) delete next[key];
      else next[key] = 1;
      return next;
    });
  }

  function setWeight(key: string, w: number) {
    setSelected((s) => ({ ...s, [key]: w }));
  }

  async function submit() {
    setError("");
    setStatus(null);
    const specs = Object.entries(selected).map(([key, weight]) => ({ key, weight }));
    if (!specs.length) {
      setError("请至少选择一个因子");
      return;
    }
    try {
      const { task_id } = await submitScreening({
        universe_key: universeKey,
        factors: specs,
        top_n: topN,
        max_symbols: maxSymbols,
        lookback_days: lookback,
      });
      poll(task_id);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  function poll(taskId: string) {
    if (pollRef.current) window.clearInterval(pollRef.current);
    const tick = async () => {
      try {
        const st = await getScreeningStatus(taskId);
        setStatus(st);
        if (st.status === "done" || st.status === "error") {
          if (pollRef.current) window.clearInterval(pollRef.current);
        }
      } catch (e) {
        setError((e as Error).message);
        if (pollRef.current) window.clearInterval(pollRef.current);
      }
    };
    tick();
    pollRef.current = window.setInterval(tick, 1000);
  }

  const usingTechnical = Object.keys(selected).some((k) => factors[k]?.kind === "technical");
  const allOptions = universes
    ? [universes.all, ...universes.indices, ...universes.industries]
    : [];

  return (
    <div className="app">
      <aside className="sidebar">
        <label>股票池</label>
        <select value={universeKey} onChange={(e) => setUniverseKey(e.target.value)}>
          {allOptions.map((o) => (
            <option key={o.key} value={o.key}>
              {o.label}
            </option>
          ))}
        </select>

        <label>Top N</label>
        <input type="number" value={topN} onChange={(e) => setTopN(Number(e.target.value))} />
        <label>最多扫描股票数</label>
        <input type="number" value={maxSymbols} onChange={(e) => setMaxSymbols(Number(e.target.value))} />
        {usingTechnical && (
          <>
            <label>技术因子回看天数</label>
            <input type="number" value={lookback} onChange={(e) => setLookback(Number(e.target.value))} />
            <p className="muted" style={{ fontSize: 12 }}>
              含技术因子需逐股拉历史，股票池较大时会慢。
            </p>
          </>
        )}

        <button onClick={submit} disabled={status?.status === "running"}>
          {status?.status === "running" ? "计算中…" : "开始选股"}
        </button>
      </aside>

      <main className="main">
        <h1>截面多因子选股</h1>
        {error && <div className="error">{error}</div>}

        <div className="panel">
          <h3>选择因子与权重</h3>
          <div className="factor-grid">
            {Object.entries(factors).map(([key, info]) => (
              <div key={key} className={`factor-item ${key in selected ? "on" : ""}`}>
                <label className="factor-label">
                  <input type="checkbox" checked={key in selected} onChange={() => toggle(key)} />
                  <span>{info.label}</span>
                  <span className={`tag tag-${info.kind}`}>{info.kind === "fundamental" ? "基本面" : "技术"}</span>
                </label>
                {key in selected && (
                  <input
                    className="weight"
                    type="number"
                    step="any"
                    value={selected[key]}
                    onChange={(e) => setWeight(key, Number(e.target.value))}
                  />
                )}
              </div>
            ))}
          </div>
        </div>

        {status?.status === "running" && (
          <div className="panel">
            <div className="progress">
              <div className="progress-bar" style={{ width: `${Math.round(status.progress * 100)}%` }} />
            </div>
            <p className="muted">进度 {Math.round(status.progress * 100)}%</p>
          </div>
        )}

        {status?.status === "error" && <div className="error">选股失败：{status.error}</div>}

        {status?.status === "done" && status.results && <ResultTable rows={status.results} />}
      </main>
    </div>
  );
}

function ResultTable({ rows }: { rows: Record<string, number | string | null>[] }) {
  if (!rows.length) return <p className="muted">股票池为空或无结果。</p>;
  // 列顺序：rank/code/name/score 在前，其余因子列在后
  const head = ["rank", "code", "name", "score"];
  const rest = Object.keys(rows[0]).filter((c) => !head.includes(c));
  const columns = [...head.filter((c) => c in rows[0]), ...rest];

  return (
    <div className="panel">
      <h3>选股结果（共 {rows.length} 只）</h3>
      <table>
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c}>{c}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              {columns.map((c) => (
                <td key={c}>
                  {c === "code" ? (
                    <Link to={`/stock/${r[c]}`}>{r[c]}</Link>
                  ) : typeof r[c] === "number" ? (
                    (r[c] as number).toFixed(c === "rank" ? 0 : 3)
                  ) : (
                    r[c] ?? "—"
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
