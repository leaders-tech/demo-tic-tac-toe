/*
This file configures Playwright e2e tests and the temporary dev servers they use.
Edit this file when browser test setup, ports, or e2e server env values change.
Copy a config pattern here when you add another shared e2e setting.
*/

import { defineConfig } from "@playwright/test";
import path from "node:path";
import os from "node:os";
import { fileURLToPath } from "node:url";

const frontendRoot = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(frontendRoot, "..");
const backendUrl = "http://127.0.0.1:9010";
const frontendUrl = "http://127.0.0.1:4173";
const dbPath = process.env.E2E_DB_PATH ?? path.join(os.tmpdir(), `templatepwa-e2e-${Date.now()}-${process.pid}.sqlite3`);
const uvCacheDir = path.join(os.tmpdir(), "templatepwa-uv-cache");

export default defineConfig({
  testDir: "./tests/e2e",
  use: {
    baseURL: frontendUrl,
  },
  webServer: [
    {
      command: "uv run python -m backend.main",
      cwd: repoRoot,
      url: `${backendUrl}/health`,
      reuseExistingServer: !process.env.CI,
      env: {
        APP_MODE: "dev",
        APP_HOST: "127.0.0.1",
        APP_PORT: "9010",
        DB_PATH: dbPath,
        COOKIE_SECRET: "playwright-secret",
        FRONTEND_ORIGIN: frontendUrl,
        UV_CACHE_DIR: uvCacheDir,
      },
    },
    {
      command: "npm run dev -- --host 127.0.0.1 --port 4173",
      cwd: frontendRoot,
      url: frontendUrl,
      reuseExistingServer: !process.env.CI,
      env: {
        VITE_BACKEND_URL: backendUrl,
      },
    },
  ],
});
