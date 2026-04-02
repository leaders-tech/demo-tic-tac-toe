/*
This file runs the same Playwright browser flows against the Docker deployment stack.
Edit this file when docker e2e ports, env values, or stack startup rules change.
Copy a config pattern here when you add another Playwright target environment.
*/

import { defineConfig } from "@playwright/test";
const frontendUrl = process.env.PW_DOCKER_FRONTEND_URL || "http://localhost:4188";

export default defineConfig({
  testDir: "./tests/e2e",
  use: {
    baseURL: frontendUrl,
  },
});
