/* Copyright 2024 Marimo. All rights reserved. */
import { type Plugin, defineConfig } from "vite";
import fs from "node:fs";
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
  target: "18",
};

// https://vitejs.dev/config/
export default defineConfig({
  resolve: {
    dedupe: ["react", "react-dom", "@emotion/react", "@emotion/cache"],
    conditions: [
      "module",
      "browser",
      process.env.NODE_ENV === "production" ? "production" : "development",
    ],
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
  ],
  build: {
    emptyOutDir: true,
    outDir: "dist",
    assetsDir: "assets",
    lib: {
      entry: path.resolve(__dirname, "../src/core/islands/main.ts"),
      formats: ["es"],
      fileName: () => "main.js",
    },
    rollupOptions: {
      output: {
        assetFileNames: (assetInfo) => {
          if (assetInfo.name === "style.css") return "style.css";
          return `assets/${assetInfo.name}`;
        },
      },
    },
  },
});
