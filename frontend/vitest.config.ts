/* Copyright 2024 Marimo. All rights reserved. */

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
    setupFiles: ["src/__tests__/setup.ts"],
    sequence: {
      hooks: "parallel", // Maintain parallel hook execution from Vitest 1.x
    },
    watch: false,
  },
  resolve: {
    tsconfigPaths: true,
  },
  plugins: [react()],
});
