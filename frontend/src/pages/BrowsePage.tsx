import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { CatalogItem, getCatalog } from "../api/client";

const PAGE_SIZE = 20;
type Kind = "stock" | "fund";

export default function BrowsePage() {
  const navigate = useNavigate();
  const [kind, setKind] = useState<Kind>("stock");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [items, setItems] = useState<CatalogItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // 切 tab 或改搜索词时回到第 1 页
  useEffect(() => {
    setPage(1);
  }, [kind, query]);

  // 加载（对搜索词做 300ms 防抖，避免每个按键都打一次请求）
  useEffect(() => {
    let cancelled = false;
    const timer = window.setTimeout(() => {
      setLoading(true);
      setError("");
      getCatalog(kind, query.trim(), page, PAGE_SIZE)
        .then((res) => {
          if (cancelled) return;
          setItems(res.items);
          setTotal(res.total);
        })
        .catch((e) => !cancelled && setError(e.message))
        .finally(() => !cancelled && setLoading(false));
    }, 300);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [kind, query, page]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="app">
      <main className="main">
        <h1>标的库</h1>

        <div className="tabs">
          <button
            className={kind === "stock" ? "tab on" : "tab"}
            onClick={() => setKind("stock")}
          >
            股票
          </button>
          <button
            className={kind === "fund" ? "tab on" : "tab"}
            onClick={() => setKind("fund")}
          >
            基金 / ETF
          </button>
        </div>

        <input
          className="browse-search"
          placeholder="按代码或名称搜索…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />

        {error && <div className="error">{error}</div>}

        <div className="panel">
          <table>
            <thead>
              <tr>
                <th>代码</th>
                <th>名称</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {items.map((it) => (
                <tr key={it.symbol} className="clickable" onClick={() => navigate(`/stock/${it.symbol}`)}>
                  <td>{it.symbol}</td>
                  <td>{it.name || "—"}</td>
                  <td>
                    <span className="result-link">查看详情 →</span>
                  </td>
                </tr>
              ))}
              {!items.length && !loading && (
                <tr>
                  <td colSpan={3} className="muted">
                    {error ? "" : "没有匹配的标的。"}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="pager">
          <button
            className="secondary"
            disabled={page <= 1 || loading}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
          >
            上一页
          </button>
          <span className="pager-info">
            第 {page} / {totalPages} 页，共 {total} 条
          </span>
          <button
            className="secondary"
            disabled={page >= totalPages || loading}
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
          >
            下一页
          </button>
        </div>
      </main>
    </div>
  );
}
