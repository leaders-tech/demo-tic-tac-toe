/*
This file runs the same Playwright browser flows against the Docker deployment stack.
Edit this file when docker e2e ports, env values, or stack startup rules change.
Copy a config pattern here when you add another Playwright target environment.
*/
import { defineConfig } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";
var frontendRoot = path.dirname(fileURLToPath(import.meta.url));
var frontendUrl = "http://localhost:4188";
var repoRoot = path.resolve(frontendRoot, "..");
export default defineConfig({
  testDir: "./tests/e2e",
  use: {
    baseURL: frontendUrl,
  },
  webServer: [
    {
      command: "sh ./frontend/scripts/run-docker-e2e-stack.sh",
      cwd: repoRoot,
      url: "".concat(frontendUrl),
      reuseExistingServer: false,
      env: {
        DOCKER_APP_MODE: "dev",
        DOCKER_COOKIE_SECRET: "playwright-docker-secret",
        DOCKER_FRONTEND_PORT: "4188",
        DOCKER_BACKEND_PORT: "4189",
        DOCKER_FRONTEND_ORIGIN: frontendUrl,
        DOCKER_VITE_BACKEND_URL: "http://localhost:4189",
        PW_DOCKER_PROJECT_NAME: "templatepwa_e2e_".concat(process.pid),
      },
    },
  ],
});
