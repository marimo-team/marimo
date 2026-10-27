/* Copyright 2026 Marimo. All rights reserved. */

import { defineConfig, mergeConfig } from "vite";
import config from "./vite.config.mts";

// Use only for attribution. Measure latency with the normal production build.
export default defineConfig(
  mergeConfig(config, {
    resolve: {
      alias: [
        { find: /^react-dom\/client$/, replacement: "react-dom/profiling" },
      ],
    },
    build: { minify: false, sourcemap: true },
  }),
);
