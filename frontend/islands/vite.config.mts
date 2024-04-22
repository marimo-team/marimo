/* Copyright 2024 Marimo. All rights reserved. */
import { Plugin, defineConfig } from "vite";
import fs from "fs";
import path from "path";
import react from "@vitejs/plugin-react-swc";
import tsconfigPaths from "vite-tsconfig-paths";
import packageJson from "../package.json";

const htmlDevPlugin = (): Plugin => {
  return {
    apply: "serve",
    name: "html-transform",
    transformIndexHtml: async () => {
      const indexHtml = await fs.promises.readFile(
        path.resolve(__dirname, "index.html"),
        "utf-8",
      );

      return "<!DOCTYPE html>\n" + indexHtml;
    },
  };
};

// https://vitejs.dev/config/
export default defineConfig({
  resolve: {
    dedupe: ["react", "react-dom", "@emotion/react", "@emotion/cache"],
  },
  worker: {
    plugins: () => [tsconfigPaths()],
  },
  define: {
    "process.env": {
      NODE_ENV: JSON.stringify(process.env.NODE_ENV),
    },
    "import.meta.env.VITE_MARIMO_ISLANDS": JSON.stringify(true),
    "import.meta.env.VITE_MARIMO_VERSION":
      process.env.NODE_ENV === "production"
        ? JSON.stringify(packageJson.version)
        : JSON.stringify("latest"),
  },
  plugins: [htmlDevPlugin(), react({ tsDecorators: true }), tsconfigPaths()],
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
      },
    },
  },
});
