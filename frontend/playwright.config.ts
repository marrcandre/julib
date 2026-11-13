import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://127.0.0.1:5173",
    viewport: { width: 1280, height: 900 },
    ...(process.env.CAMERA_FIXTURE
      ? {
          permissions: ["camera"],
          launchOptions: {
            args: [
              "--use-fake-ui-for-media-stream",
              "--use-fake-device-for-media-stream",
              "--use-file-for-fake-video-capture=" + process.env.CAMERA_FIXTURE,
            ],
          },
        }
      : {}),
  },
  workers: 1,
  reporter: "list",
});
