/// <reference types="vitest/config" />
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The browser calls same-origin /api/...; the dev server forwards it to the local
// backend (frontend-spec §1: backend at http://127.0.0.1:8000/api/v1). No CORS needed.
// FME_API_PROXY lets the E2E suite point at its own seeded backend on another port.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: {
      "/api": process.env.FME_API_PROXY ?? "http://127.0.0.1:8000",
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test-setup.ts"],
    globals: false,
    exclude: ["e2e/**", "node_modules/**"],
  },
});
