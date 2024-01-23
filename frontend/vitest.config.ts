/* Copyright 2024 Marimo. All rights reserved. */
import { defineConfig } from "vitest/config";
import tsconfigPaths from "vite-tsconfig-paths";

export default defineConfig({
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.ts"],
    setupFiles: ["src/__tests__/setup.ts"],
  },
  plugins: [tsconfigPaths()],
});
