import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import * as api from "./api/client";

interface AuthState {
  username: string | null;
  ready: boolean; // 是否已完成初始 token 校验
  login: (u: string, p: string) => Promise<void>;
  register: (u: string, p: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [username, setUsername] = useState<string | null>(null);
  const [ready, setReady] = useState(false);

  // 启动时若本地有 token，校验一次拿回用户名
  useEffect(() => {
    if (!api.getToken()) {
      setReady(true);
      return;
    }
    api
      .getMe()
      .then((m) => setUsername(m.username))
      .catch(() => api.clearToken())
      .finally(() => setReady(true));
  }, []);

  // token 失效时（任意请求 401）回到登录态
  useEffect(() => {
    const onLogout = () => setUsername(null);
    window.addEventListener("auth:logout", onLogout);
    return () => window.removeEventListener("auth:logout", onLogout);
  }, []);

  async function login(u: string, p: string) {
    const res = await api.login(u, p);
    api.setToken(res.token);
    setUsername(res.username);
  }

  async function register(u: string, p: string) {
    const res = await api.register(u, p);
    api.setToken(res.token);
    setUsername(res.username);
  }

  function logout() {
    api.logout().catch(() => {});
    api.clearToken();
    setUsername(null);
  }

  return (
    <AuthContext.Provider value={{ username, ready, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth 必须在 AuthProvider 内使用");
  return ctx;
}
