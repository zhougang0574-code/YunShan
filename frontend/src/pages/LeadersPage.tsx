import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  getLeadersStatus,
  getUniverses,
  ScreeningStatus,
  submitLeaders,
  UniverseList,
} from "../api/client";

// 当月涨幅榜：选若干行业板块，后台逐股算「当月至今涨幅」后取 Top N 龙头。
export default function LeadersPage() {
  const [universes, setUniverses] = useState<UniverseList | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [filter, setFilter] = useState("");
  const [topN, setTopN] = useState(30);
  const [maxSymbols, setMaxSymbols] = useState(300);

  const [error, setError] = useState("");
  const [status, setStatus] = useState<ScreeningStatus | null>(null);
  const pollRef = useRef<number | null>(null);

  useEffect(() => {
    getUniverses().then(setUniverses).catch((e) => setError(e.message));
    return () => {
      if (pollRef.current) window.clearInterval(pollRef.current);
    };
  }, []);

  // 板块名取自股票池里的 industry:<板块名>。
  const industries = (universes?.industries ?? []).map((o) => o.key.replace(/^industry:/, ""));
  const shown = industries.filter((n) => n.includes(filter));

  function toggle(name: string) {
    setSelected((s) => {
      const next = new Set(s);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  }

  async function submit() {
    setError("");
    setStatus(null);
    if (selected.size === 0) {
      setError("请至少选择一个板块");
      return;
    }
    try {
      const { task_id } = await submitLeaders({
        industries: [...selected],
        top_n: topN,
        max_symbols: maxSymbols,
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
        const st = await getLeadersStatus(taskId);
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

  return (
    <div className="app">
      <aside className="sidebar">
        <label>筛选板块</label>
        <input
          placeholder="输入板块名过滤"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />

        <label>Top N（龙头数量）</label>
        <input type="number" value={topN} onChange={(e) => setTopN(Number(e.target.value))} />
        <label>最多扫描股票数</label>
        <input
          type="number"
          value={maxSymbols}
          onChange={(e) => setMaxSymbols(Number(e.target.value))}
        />
        <p className="muted" style={{ fontSize: 12 }}>
          逐股拉历史算当月涨幅，选的板块越多越慢；扫描数为所有板块合计上限。
        </p>

        <button onClick={submit} disabled={status?.status === "running"}>
          {status?.status === "running" ? "计算中…" : "查龙头"}
        </button>
      </aside>

      <main className="main">
        <h1>板块当月涨幅榜</h1>
        <p className="muted">
          以上月最后收盘价为基准，算当月至今涨幅，取所选板块涨幅最高的龙头股。
        </p>
        {error && <div className="error">{error}</div>}

        <div className="panel">
          <h3>
            选择板块（已选 {selected.size} 个）
            {selected.size > 0 && (
              <a
                className="muted"
                style={{ marginLeft: 12, fontSize: 13, cursor: "pointer" }}
                onClick={() => setSelected(new Set())}
              >
                清空
              </a>
            )}
          </h3>
          <div className="factor-grid">
            {shown.map((name) => (
              <div key={name} className={`factor-item ${selected.has(name) ? "on" : ""}`}>
                <label className="factor-label">
                  <input
                    type="checkbox"
                    checked={selected.has(name)}
                    onChange={() => toggle(name)}
                  />
                  <span>{name}</span>
                </label>
              </div>
            ))}
            {!shown.length && <p className="muted">无匹配板块。</p>}
          </div>
        </div>

        {status?.status === "running" && (
          <div className="panel">
            <div className="progress">
              <div
                className="progress-bar"
                style={{ width: `${Math.round(status.progress * 100)}%` }}
              />
            </div>
            <p className="muted">进度 {Math.round(status.progress * 100)}%</p>
          </div>
        )}

        {status?.status === "error" && <div className="error">查询失败：{status.error}</div>}

        {status?.status === "done" && status.results && <ResultTable rows={status.results} />}
      </main>
    </div>
  );
}

const COLUMN_LABELS: Record<string, string> = {
  rank: "排名",
  code: "代码",
  name: "名称",
  industry: "所属板块",
  month_pct: "当月涨幅%",
  base_price: "月初基准价",
  price: "最新价",
};

function ResultTable({ rows }: { rows: Record<string, number | string | null>[] }) {
  if (!rows.length) return <p className="muted">所选板块无可用数据。</p>;
  const columns = ["rank", "code", "name", "industry", "month_pct", "base_price", "price"].filter(
    (c) => c in rows[0]
  );

  return (
    <div className="panel">
      <h3>龙头榜（共 {rows.length} 只）</h3>
      <table>
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c}>{COLUMN_LABELS[c] ?? c}</th>
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
                    (r[c] as number).toFixed(c === "rank" ? 0 : 2)
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
