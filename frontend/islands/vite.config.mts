/* Copyright 2024 Marimo. All rights reserved. */
import { type Plugin, defineConfig } from "vite";
import fs from "node:fs";
import wasm from "vite-plugin-wasm";
import topLevelAwait from "vite-plugin-top-level-await";
import path from "node:path";
import react from "@vitejs/plugin-react";
import tsconfigPaths from "vite-tsconfig-paths";
import packageJson from "../package.json";

const htmlDevPlugin = (): Plugin => {
  return {
    apply: "serve",
    name: "html-transform",
    transformIndexHtml: async () => {
      const indexHtml = await fs.promises.readFile(
        path.resolve(__dirname, "__demo__", "index.html"),
        "utf-8",
      );

      return `<!DOCTYPE html>\n${indexHtml}`;
    },
  };
};

const ReactCompilerConfig = {
  target: "19",
};

// https://vitejs.dev/config/
export default defineConfig({
  resolve: {
    dedupe: ["react", "react-dom", "@emotion/react", "@emotion/cache"],
  },
  worker: {
    format: "es",
    plugins: () => [tsconfigPaths()],
  },
  define: {
    "process.env": {
      NODE_ENV: JSON.stringify(process.env.NODE_ENV),
    },
    "import.meta.env.VITE_MARIMO_ISLANDS": JSON.stringify(true),
    // Precedence: VITE_MARIMO_VERSION > package.json version > "latest"
    "import.meta.env.VITE_MARIMO_VERSION": process.env.VITE_MARIMO_VERSION
      ? JSON.stringify(process.env.VITE_MARIMO_VERSION)
      : process.env.NODE_ENV === "production"
        ? JSON.stringify(packageJson.version)
        : JSON.stringify("latest"),
  },
  server: {
    headers: {
      "Cross-Origin-Opener-Policy": "same-origin",
      "Cross-Origin-Embedder-Policy": "require-corp",
    },
  },
  plugins: [
    htmlDevPlugin(),
    react({
      babel: {
        presets: ["@babel/preset-typescript"],
        plugins: [
          ["@babel/plugin-proposal-decorators", { legacy: true }],
          ["@babel/plugin-proposal-class-properties", { loose: true }],
          ["babel-plugin-react-compiler", ReactCompilerConfig],
        ],
      },
    }),
    tsconfigPaths(),
    wasm(),
    topLevelAwait(),
  ],
  build: {
    emptyOutDir: true,
    lib: {
      entry: path.resolve(__dirname, "../src/core/islands/main.ts"),
      formats: ["es"],
    },
    rollupOptions: {
      output: {
        // Remove hash from entry file name, so it's easier to import
        entryFileNames: "[name].js",
        // Ensure CSS is output as style.css instead of frontend.css
        assetFileNames: (assetInfo) => {
          if (
            assetInfo.names.includes("frontend.css") ||
            assetInfo.names.includes("islands.css")
          ) {
            return "style.css";
          }
          return assetInfo.names[0];
        },
      },
    },
  },
});
