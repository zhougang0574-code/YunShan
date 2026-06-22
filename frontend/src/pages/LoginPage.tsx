import { useEffect, useState } from "react";
import { useAuth } from "../auth";
import { clearCreds, getSavedCreds, saveCreds } from "../api/client";

export default function LoginPage() {
  const { login, register } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  // 进页面时若浏览器记住过凭据，自动填充（一键即可登录）
  useEffect(() => {
    const c = getSavedCreds();
    if (c) {
      setUsername(c.username);
      setPassword(c.password);
      setRemember(true);
    }
  }, []);

  async function submit() {
    setError("");
    if (username.trim().length < 2) return setError("用户名至少 2 个字符");
    if (password.length < 4) return setError("密码至少 4 个字符");
    setBusy(true);
    try {
      if (mode === "login") await login(username.trim(), password);
      else await register(username.trim(), password);
      // 登录/注册成功后，按勾选项记住或清除凭据
      if (remember) saveCreds(username.trim(), password);
      else clearCreds();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-shell">
      <div className="login-card">
        <h1 className="login-brand">YunShan 量化</h1>
        <p className="muted" style={{ marginTop: 0 }}>
          {mode === "login" ? "登录后查看你的自选收藏" : "注册一个新账号"}
        </p>

        {error && <div className="error">{error}</div>}

        <label>用户名</label>
        <input
          value={username}
          autoFocus
          onChange={(e) => setUsername(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
        />
        <label>密码</label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
        />

        <label className="remember-row">
          <input
            type="checkbox"
            checked={remember}
            onChange={(e) => setRemember(e.target.checked)}
          />
          记住账号密码（下次自动填充）
        </label>

        <button onClick={submit} disabled={busy}>
          {busy ? "请稍候…" : mode === "login" ? "登录" : "注册并登录"}
        </button>

        <p className="login-switch">
          {mode === "login" ? "还没有账号？" : "已有账号？"}
          <a
            onClick={() => {
              setMode(mode === "login" ? "register" : "login");
              setError("");
            }}
          >
            {mode === "login" ? "去注册" : "去登录"}
          </a>
        </p>
      </div>
    </div>
  );
}
