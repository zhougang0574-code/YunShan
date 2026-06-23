import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import ReactECharts from "echarts-for-react";
import {
  EquityPoint,
  getPaperAccount,
  getPaperEquity,
  getPaperTrades,
  PaperAccount,
  PaperTrade,
  placePaperOrder,
  resetPaperAccount,
} from "../api/client";

const yuan = (v: number | null | undefined) =>
  v == null ? "—" : v.toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export default function PaperPage() {
  const navigate = useNavigate();
  const [account, setAccount] = useState<PaperAccount | null>(null);
  const [trades, setTrades] = useState<PaperTrade[]>([]);
  const [equity, setEquity] = useState<EquityPoint[]>([]);
  const [symbol, setSymbol] = useState("000001");
  const [side, setSide] = useState<"buy" | "sell">("buy");
  const [shares, setShares] = useState(100);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  function refresh() {
    getPaperAccount().then(setAccount).catch((e) => setError(e.message));
    getPaperTrades().then(setTrades).catch(() => {});
    getPaperEquity().then(setEquity).catch(() => {});
  }

  useEffect(() => {
    refresh();
  }, []);

  async function submit() {
    setError("");
    setNotice("");
    const s = symbol.trim();
    if (!s) return;
    setBusy(true);
    try {
      const res = await placePaperOrder(s, side, shares);
      setAccount(res.account);
      const f = res.fill;
      setNotice(
        `已${side === "buy" ? "买入" : "卖出"} ${s} ${f.shares} 股 @ ${yuan(Number(f.price))}` +
          (f.realized != null ? `，本笔已实现盈亏 ${yuan(Number(f.realized))}` : "")
      );
      getPaperTrades().then(setTrades).catch(() => {});
      getPaperEquity().then(setEquity).catch(() => {});
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function doReset() {
    if (!window.confirm("确定清空模拟账户？持仓、成交、净值记录都会重置。")) return;
    setError("");
    setNotice("");
    try {
      setAccount(await resetPaperAccount());
      setTrades([]);
      setEquity([]);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  const profitUp = (account?.profit ?? 0) >= 0;

  return (
    <div className="app">
      <main className="main">
        <h1>模拟交易</h1>
        <p className="muted">
          虚拟账户，按最新价撮合，计真实 A 股费用（佣金/印花税/过户费），买入需 100 股整数倍。仅供练习，不接券商。
        </p>
        {error && <div className="error">{error}</div>}
        {notice && <div className="notice">{notice}</div>}

        {account && (
          <div className="panel paper-summary">
            <div className="stat">
              <span className="stat-label">总资产</span>
              <span className="stat-value">{yuan(account.total)}</span>
            </div>
            <div className="stat">
              <span className="stat-label">可用现金</span>
              <span className="stat-value">{yuan(account.cash)}</span>
            </div>
            <div className="stat">
              <span className="stat-label">持仓市值</span>
              <span className="stat-value">{yuan(account.market_value)}</span>
            </div>
            <div className="stat">
              <span className="stat-label">累计盈亏</span>
              <span className={profitUp ? "stat-value price-up" : "stat-value price-down"}>
                {yuan(account.profit)} ({account.profit_pct.toFixed(2)}%)
              </span>
            </div>
            <div className="stat">
              <span className="stat-label">初始资金</span>
              <span className="stat-value">{yuan(account.initial)}</span>
            </div>
            <button className="ghost" onClick={doReset} style={{ marginLeft: "auto" }}>
              重置账户
            </button>
          </div>
        )}

        <div className="panel">
          <h3>下单</h3>
          <div className="order-form">
            <label>
              代码
              <input value={symbol} onChange={(e) => setSymbol(e.target.value)} />
            </label>
            <label>
              方向
              <select value={side} onChange={(e) => setSide(e.target.value as "buy" | "sell")}>
                <option value="buy">买入</option>
                <option value="sell">卖出</option>
              </select>
            </label>
            <label>
              数量(股)
              <input
                type="number"
                step={100}
                min={100}
                value={shares}
                onChange={(e) => setShares(Number(e.target.value))}
              />
            </label>
            <button onClick={submit} disabled={busy}>
              {busy ? "提交中…" : "按最新价下单"}
            </button>
          </div>
        </div>

        <div className="panel">
          <h3>净值曲线</h3>
          <EquityChart data={equity} />
        </div>

        <div className="panel">
          <h3>持仓</h3>
          {account && account.positions.length ? (
            <table>
              <thead>
                <tr>
                  <th>代码</th>
                  <th>名称</th>
                  <th>股数</th>
                  <th>成本价</th>
                  <th>现价</th>
                  <th>市值</th>
                  <th>浮动盈亏</th>
                </tr>
              </thead>
              <tbody>
                {account.positions.map((p) => (
                  <tr key={p.symbol} className="clickable" onClick={() => navigate(`/stock/${p.symbol}`)}>
                    <td>{p.symbol}</td>
                    <td>{p.name || "—"}</td>
                    <td>{p.shares}</td>
                    <td>{yuan(p.avg_cost)}</td>
                    <td>{p.price == null ? "—" : yuan(p.price)}</td>
                    <td>{yuan(p.market_value)}</td>
                    <td className={p.unrealized >= 0 ? "price-up" : "price-down"}>
                      {yuan(p.unrealized)} ({p.unrealized_pct.toFixed(2)}%)
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="muted">暂无持仓。</p>
          )}
        </div>

        <div className="panel">
          <h3>成交记录</h3>
          {trades.length ? (
            <table>
              <thead>
                <tr>
                  <th>时间</th>
                  <th>代码</th>
                  <th>名称</th>
                  <th>方向</th>
                  <th>价格</th>
                  <th>股数</th>
                  <th>成交额</th>
                  <th>费用</th>
                  <th>已实现盈亏</th>
                </tr>
              </thead>
              <tbody>
                {trades.map((t, i) => (
                  <tr key={i}>
                    <td>{t.ts.replace("T", " ")}</td>
                    <td>{t.symbol}</td>
                    <td>{t.name || "—"}</td>
                    <td className={t.side === "buy" ? "price-down" : "price-up"}>
                      {t.side === "buy" ? "买入" : "卖出"}
                    </td>
                    <td>{yuan(t.price)}</td>
                    <td>{t.shares}</td>
                    <td>{yuan(t.amount)}</td>
                    <td>{yuan(t.fee)}</td>
                    <td className={t.realized >= 0 ? "price-up" : "price-down"}>
                      {t.side === "sell" ? yuan(t.realized) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="muted">还没有成交记录。</p>
          )}
        </div>
      </main>
    </div>
  );
}

function EquityChart({ data }: { data: EquityPoint[] }) {
  if (!data.length) return <p className="muted">暂无净值数据（每次查看账户会记录当日一笔）。</p>;
  const option = {
    tooltip: { trigger: "axis" },
    grid: { left: 80, right: 20, top: 20, bottom: 40 },
    xAxis: { type: "category", data: data.map((d) => d.date) },
    yAxis: { type: "value", scale: true },
    series: [
      {
        name: "总资产",
        type: "line",
        showSymbol: data.length < 30,
        data: data.map((d) => d.total),
        lineStyle: { color: "#2563eb" },
        areaStyle: { color: "rgba(37,99,235,0.08)" },
      },
    ],
  };
  return <ReactECharts option={option} style={{ height: 320 }} notMerge />;
}
