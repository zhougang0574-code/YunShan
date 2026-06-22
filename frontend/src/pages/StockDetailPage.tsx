import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import ReactECharts from "echarts-for-react";
import {
  addFavorite,
  AltData,
  getAltData,
  getFavorites,
  getFundamentals,
  getIntraday,
  getQuote,
  getSignals,
  IntradayPoint,
  Quote,
  removeFavorite,
  SignalTag,
} from "../api/client";

const FUND_LABELS: Record<string, string> = {
  pe_ttm: "PE(TTM)",
  pb: "PB",
  ps_ttm: "PS(TTM)",
  dv_ttm: "股息率%",
  total_mv: "总市值(亿)",
  roe: "ROE%",
  gross_margin: "毛利率%",
  revenue_yoy: "营收增速%",
  profit_yoy: "净利增速%",
};

const QUOTE_REFRESH_MS = 60_000; // 分钟级轮询

export default function StockDetailPage() {
  const { symbol: routeSymbol } = useParams();
  const navigate = useNavigate();
  const [symbol, setSymbol] = useState(routeSymbol || "000001");
  const [input, setInput] = useState(routeSymbol || "000001");

  const [quote, setQuote] = useState<Quote | null>(null);
  const [intraday, setIntraday] = useState<IntradayPoint[]>([]);
  const [tags, setTags] = useState<SignalTag[]>([]);
  const [fund, setFund] = useState<Record<string, number | null>>({});
  const [alt, setAlt] = useState<AltData | null>(null);
  const [error, setError] = useState("");
  const [favSymbols, setFavSymbols] = useState<Set<string>>(new Set());
  const quoteTimer = useRef<number | null>(null);

  // 收藏集合（进页面加载一次，收藏/取消后同步更新）
  useEffect(() => {
    getFavorites()
      .then((rows) => setFavSymbols(new Set(rows.map((r) => r.symbol))))
      .catch(() => {});
  }, []);

  const isFav = favSymbols.has(symbol);

  async function toggleFav() {
    try {
      const rows = isFav ? await removeFavorite(symbol) : await addFavorite(symbol);
      setFavSymbols(new Set(rows.map((r) => r.symbol)));
    } catch (e) {
      setError((e as Error).message);
    }
  }

  useEffect(() => {
    if (routeSymbol) {
      setSymbol(routeSymbol);
      setInput(routeSymbol);
    }
  }, [routeSymbol]);

  useEffect(() => {
    let cancelled = false;
    setError("");
    setTags([]);
    setAlt(null);

    const loadQuote = () => {
      getQuote(symbol).then((q) => !cancelled && setQuote(q)).catch(() => {});
    };
    loadQuote();
    if (quoteTimer.current) window.clearInterval(quoteTimer.current);
    quoteTimer.current = window.setInterval(loadQuote, QUOTE_REFRESH_MS);

    getIntraday(symbol).then((d) => !cancelled && setIntraday(d)).catch(() => {});
    getSignals(symbol).then((s) => !cancelled && setTags(s.tags)).catch(() => {});
    getFundamentals(symbol).then((f) => !cancelled && setFund(f)).catch(() => {});
    getAltData(symbol).then((a) => !cancelled && setAlt(a)).catch(() => {});

    return () => {
      cancelled = true;
      if (quoteTimer.current) window.clearInterval(quoteTimer.current);
    };
  }, [symbol]);

  function go() {
    const s = input.trim();
    if (s) navigate(`/stock/${s}`);
  }

  const up = (quote?.pct_chg ?? 0) >= 0;

  return (
    <div className="app">
      <aside className="sidebar">
        <label>股票代码</label>
        <input value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => e.key === "Enter" && go()} />
        <button onClick={go}>查看</button>
        <p className="muted" style={{ fontSize: 12, marginTop: 16 }}>
          报价每 60 秒自动刷新（轮询，非实时推送）。
        </p>
      </aside>

      <main className="main">
        {error && <div className="error">{error}</div>}

        <div className="result-header">
          <span className="result-symbol">{symbol}</span>
          <span className="result-name">{quote?.name || alt?.name || ""}</span>
          {quote?.price != null && (
            <span className={up ? "price-up" : "price-down"} style={{ fontSize: 22, fontWeight: 700 }}>
              {quote.price.toFixed(2)}
              {quote.pct_chg != null && `  ${up ? "+" : ""}${quote.pct_chg.toFixed(2)}%`}
            </span>
          )}
          <button
            className={isFav ? "fav-btn on" : "fav-btn"}
            style={{ marginLeft: "auto" }}
            onClick={toggleFav}
            title={isFav ? "取消收藏" : "收藏"}
          >
            {isFav ? "★ 已收藏" : "☆ 收藏"}
          </button>
        </div>

        <div className="panel">
          <h3>注意点</h3>
          {tags.length ? (
            <div className="tags">
              {tags.map((t, i) => (
                <span key={i} className={`signal-tag level-${t.level}`}>
                  <span className="tag-cat">{catLabel(t.category)}</span>
                  {t.text}
                </span>
              ))}
            </div>
          ) : (
            <p className="muted">暂无触发的注意点信号（或数据源未取到）。</p>
          )}
        </div>

        <div className="panel">
          <IntradayChart data={intraday} prevClose={quote?.prev_close ?? null} />
        </div>

        <div className="two-col">
          <div className="panel">
            <h3>基本面</h3>
            <table>
              <tbody>
                {Object.entries(FUND_LABELS).map(([k, label]) => (
                  <tr key={k}>
                    <td>{label}</td>
                    <td>{fund[k] == null ? "—" : Number(fund[k]).toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="panel">
            <h3>另类数据</h3>
            <table>
              <tbody>
                <tr>
                  <td>主力净流入(元)</td>
                  <td>{fmt(alt?.fund_flow?.main_net)}</td>
                </tr>
                <tr>
                  <td>主力净流入占比%</td>
                  <td>{fmt(alt?.fund_flow?.main_net_pct)}</td>
                </tr>
                <tr>
                  <td>北向持股市值</td>
                  <td>{fmt(alt?.north_hold?.hold_market_value)}</td>
                </tr>
              </tbody>
            </table>
            <p className="muted" style={{ fontSize: 12 }}>另类数据仅作展示，不参与回测计算。</p>
          </div>
        </div>
      </main>
    </div>
  );
}

function catLabel(c: SignalTag["category"]): string {
  return c === "technical" ? "技术" : c === "fundamental" ? "基本面" : "资金";
}

function fmt(v: number | string | null | undefined): string {
  if (v == null) return "—";
  return typeof v === "number" ? v.toLocaleString() : String(v);
}

function IntradayChart({ data, prevClose }: { data: IntradayPoint[]; prevClose: number | null }) {
  if (!data.length) return <p className="muted">暂无分时数据（盘后或数据源未取到）。</p>;
  const option = {
    title: { text: "当日分时", left: "center", textStyle: { fontSize: 14 } },
    tooltip: { trigger: "axis" },
    grid: { left: 60, right: 20, top: 40, bottom: 40 },
    xAxis: { type: "category", data: data.map((d) => d.time), axisLabel: { show: false } },
    yAxis: { type: "value", scale: true },
    series: [
      {
        name: "价格",
        type: "line",
        showSymbol: false,
        data: data.map((d) => d.price),
        lineStyle: { color: "#2563eb" },
        markLine: prevClose
          ? { silent: true, symbol: "none", data: [{ yAxis: prevClose, lineStyle: { color: "#9aa5b1", type: "dashed" } }] }
          : undefined,
      },
    ],
  };
  return <ReactECharts option={option} style={{ height: 300 }} notMerge />;
}
