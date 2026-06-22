import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Favorite, getFavorites, removeFavorite } from "../api/client";

export default function FavoritesPage() {
  const navigate = useNavigate();
  const [rows, setRows] = useState<Favorite[]>([]);
  const [error, setError] = useState("");
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    getFavorites()
      .then(setRows)
      .catch((e) => setError(e.message))
      .finally(() => setLoaded(true));
  }, []);

  async function remove(symbol: string) {
    setError("");
    try {
      setRows(await removeFavorite(symbol));
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <div className="app">
      <main className="main">
        <h1>我的收藏</h1>
        {error && <div className="error">{error}</div>}
        {loaded && !rows.length && !error && (
          <p className="muted">还没有收藏。去「个股详情」页点 ☆ 收藏关注的股票吧。</p>
        )}

        {rows.length > 0 && (
          <div className="panel">
            <table>
              <thead>
                <tr>
                  <th>代码</th>
                  <th>名称</th>
                  <th>收藏时间</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.symbol} className="clickable" onClick={() => navigate(`/stock/${r.symbol}`)}>
                    <td>{r.symbol}</td>
                    <td>{r.name || "—"}</td>
                    <td>{r.created_at.replace("T", " ")}</td>
                    <td>
                      <a
                        className="result-link"
                        onClick={(e) => {
                          e.stopPropagation();
                          remove(r.symbol);
                        }}
                      >
                        取消收藏
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </div>
  );
}
