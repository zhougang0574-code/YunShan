import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// 确保本机回环地址不走 HTTP 代理：否则若 shell 里设了 HTTP_PROXY（如 Clash
// 127.0.0.1:7890），dev-proxy 转发到后端会被代理拦截而 502。
const loopback = "127.0.0.1,localhost";
process.env.NO_PROXY = process.env.NO_PROXY
  ? `${process.env.NO_PROXY},${loopback}`
  : loopback;
process.env.no_proxy = process.env.NO_PROXY;

// 开发时把 /api 代理到 FastAPI 后端，前端代码统一用 /api 前缀调用。
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
