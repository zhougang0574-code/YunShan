import { NavLink, Route, Routes } from "react-router-dom";
import BacktestPage from "./pages/BacktestPage";
import ScreeningPage from "./pages/ScreeningPage";
import StockDetailPage from "./pages/StockDetailPage";
import ExperimentsPage from "./pages/ExperimentsPage";
import FavoritesPage from "./pages/FavoritesPage";
import BrowsePage from "./pages/BrowsePage";
import LoginPage from "./pages/LoginPage";
import { useAuth } from "./auth";

const NAV = [
  { to: "/", label: "策略回测", end: true },
  { to: "/browse", label: "标的库" },
  { to: "/screening", label: "截面选股" },
  { to: "/stock", label: "个股详情" },
  { to: "/favorites", label: "我的收藏" },
  { to: "/experiments", label: "历史记录" },
];

export default function App() {
  const { username, ready, logout } = useAuth();

  if (!ready) return <div className="login-shell" />; // 初始校验 token 时的空屏
  if (!username) return <LoginPage />;

  return (
    <div className="shell">
      <nav className="navbar">
        <span className="brand">YunShan 量化</span>
        {NAV.map((n) => (
          <NavLink
            key={n.to}
            to={n.to}
            end={n.end}
            className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")}
          >
            {n.label}
          </NavLink>
        ))}
        <span className="nav-user">
          {username}
          <a className="nav-logout" onClick={logout}>
            退出
          </a>
        </span>
      </nav>
      <Routes>
        <Route path="/" element={<BacktestPage />} />
        <Route path="/browse" element={<BrowsePage />} />
        <Route path="/screening" element={<ScreeningPage />} />
        <Route path="/stock" element={<StockDetailPage />} />
        <Route path="/stock/:symbol" element={<StockDetailPage />} />
        <Route path="/favorites" element={<FavoritesPage />} />
        <Route path="/experiments" element={<ExperimentsPage />} />
      </Routes>
    </div>
  );
}
