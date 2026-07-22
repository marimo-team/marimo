/* Copyright 2026 Marimo. All rights reserved. */

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    reporters:
      process.env.GITHUB_ACTIONS === "true"
        ? ["default", "github-actions"]
        : ["default"],
    environment: "jsdom",
    // Coverage is opt-in via `--coverage` (see the `test:coverage` script) so
    // it never slows down the default `pnpm test` run. CI enables it to post a
    // PR comment. `reportOnFailure` keeps the summary available even when tests
    // fail; `json-summary` is what the PR-comment action reads.
    coverage: {
      provider: "v8",
      include: ["src/**"],
      reportOnFailure: true,
      reporter: ["text", "html", "json-summary", "json"],
    },
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
    setupFiles: ["src/__tests__/setup.ts"],
    sequence: {
      hooks: "parallel", // Maintain parallel hook execution from Vitest 1.x
    },
    watch: false,
    server: {
      deps: {
        // Inline streamdown so it gets processed by Vite's transform pipeline.
        // This allows CSS imports from streamdown's dependencies (e.g., katex CSS) to be processed.
        inline: [/streamdown/],
      },
    },
  },
  resolve: {
    tsconfigPaths: true,
  },
  plugins: [react()],
});
