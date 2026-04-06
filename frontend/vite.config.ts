/*
This file configures the frontend build, test setup, and PWA plugin.
Edit this file when Vite plugins, frontend test setup, or build settings change.
Copy a config pattern here when you add another shared frontend build setting.
*/

import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      registerType: "autoUpdate",
      workbox: {
        navigateFallbackDenylist: [
          /^\/auth\//,
          /^\/api\//,
          /^\/notes\//,
          /^\/admin\//,
          /^\/ws$/,
          /^\/health$/,
        ],
      },
      manifest: {
        name: "Template PWA",
        short_name: "TemplatePWA",
        description: "Small starter app for school projects.",
        theme_color: "#0e1a2b",
        background_color: "#eff6ff",
        display: "standalone",
        start_url: "/",
        icons: [
          {
            src: "/pwa-192.svg",
            sizes: "192x192",
            type: "image/svg+xml",
            purpose: "any",
          },
          {
            src: "/pwa-512.svg",
            sizes: "512x512",
            type: "image/svg+xml",
            purpose: "any",
          },
        ],
      },
    }),
  ],
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: "./vitest.setup.ts",
    exclude: ["tests/e2e/**", "node_modules/**", "dist/**"],
  },
});
