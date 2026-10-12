import { defineConfig } from "@playwright/test";

// E2E runs against a real backend serving the SYNTHETIC demo run (no live model calls).
// `make e2e` seeds the database first; see the Makefile.
const API_PORT = 8010;
const UI_PORT = 5180;
const db = process.env.FME_E2E_DB ?? "../e2e.db";

export default defineConfig({
  testDir: "e2e",
  timeout: 30_000,
  fullyParallel: false,
  reporter: [["list"]],
  use: {
    baseURL: `http://127.0.0.1:${UI_PORT}`,
    viewport: { width: 1280, height: 900 }, // D-9: desktop, min 1024 px
  },
  webServer: [
    {
      command: `.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port ${API_PORT}`,
      cwd: "../backend",
      url: `http://127.0.0.1:${API_PORT}/api/v1/health`,
      env: {
        FME_DATABASE_URL: `sqlite:///${new URL(db, `file://${process.cwd()}/`).pathname}`,
        FME_MODELS_FILE: "../config/models.demo.yaml",
      },
      reuseExistingServer: false,
    },
    {
      command: `npx vite --host 127.0.0.1 --port ${UI_PORT} --strictPort`,
      url: `http://127.0.0.1:${UI_PORT}`,
      env: { FME_API_PROXY: `http://127.0.0.1:${API_PORT}` },
      reuseExistingServer: false,
    },
  ],
});
