import { defineConfig } from "vitest/config";
import vue from "@vitejs/plugin-vue";
export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      "/api": { target: "http://127.0.0.1:8000", changeOrigin: false },
      "/accounts": { target: "http://127.0.0.1:8000", changeOrigin: false },
      "/admin": { target: "http://127.0.0.1:8000", changeOrigin: false },
      "/static": { target: "http://127.0.0.1:8000", changeOrigin: false },
    },
  },
  test: { environment: "jsdom", include: ["tests/**/*.test.ts"] },
});
