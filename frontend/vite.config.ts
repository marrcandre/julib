import { defineConfig } from "vitest/config";
import vue from "@vitejs/plugin-vue";
import { readFileSync } from "node:fs";
const packageJson = JSON.parse(
  readFileSync(new URL("./package.json", import.meta.url), "utf8"),
);
export default defineConfig({
  plugins: [vue()],
  define: { __APP_VERSION__: JSON.stringify(packageJson.version) },
  server: {
    proxy: {
      "/api": { target: process.env.E2E_API_URL ?? "http://127.0.0.1:8000", changeOrigin: false },
      "/accounts": { target: process.env.E2E_API_URL ?? "http://127.0.0.1:8000", changeOrigin: false },
      "/admin": { target: process.env.E2E_API_URL ?? "http://127.0.0.1:8000", changeOrigin: false },
      "/static": { target: process.env.E2E_API_URL ?? "http://127.0.0.1:8000", changeOrigin: false },
    },
  },
  test: { environment: "jsdom", include: ["tests/**/*.test.ts"] },
});
