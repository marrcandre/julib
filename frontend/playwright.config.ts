import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  use: {
    baseURL: "http://127.0.0.1:5173",
    viewport: { width: 1280, height: 900 },
  },
  workers: 1,
  reporter: "list",
});
