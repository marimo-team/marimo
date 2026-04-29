/* Copyright 2026 Marimo. All rights reserved. */

import { execFile, execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";
import react from "@vitejs/plugin-react";
import { defineConfig, type Plugin } from "vite";
import topLevelAwait from "vite-plugin-top-level-await";
import wasm from "vite-plugin-wasm";
import packageJson from "../package.json";

const execFileAsync = promisify(execFile);

const dirname = path.dirname(fileURLToPath(import.meta.url));

const htmlDevPlugin = (): Plugin => {
  const generateHtml = async (): Promise<string> => {
    // Auto-regenerate HTML in dev mode by running the Python script
    const scriptPath = path.resolve(dirname, "generate.py");
    try {
      const { stdout } = await execFileAsync("uv", ["run", scriptPath], {
        env: { ...process.env, MODE: "dev" },
      });
      return stdout;
    } catch (error) {
      console.error("Failed to generate demo HTML:", error);
      // Fallback to existing file if generation fails
      const indexHtml = await fs.promises.readFile(
        path.resolve(dirname, "__demo__", "index.html"),
        "utf-8",
      );
      const preamble = `<!DOCTYPE html>\n
<script type="module">import { injectIntoGlobalHook } from "/@react-refresh";
injectIntoGlobalHook(window);
window.$RefreshReg$ = () => {};
window.$RefreshSig$ = () => (type) => type;</script>

<script type="module" src="/@vite/client"></script>
      `;
      return `${preamble}\n${indexHtml}`;
    }
  };

  return {
    apply: "serve",
    name: "html-transform",
    transformIndexHtml: async () => {
      return await generateHtml();
    },
    // Watch the generate.py file and trigger HMR on changes
    configureServer(server) {
      const scriptPath = path.resolve(dirname, "generate.py");
      server.watcher.add(scriptPath);
      server.watcher.on("change", (file) => {
        if (file === scriptPath) {
          console.log("Demo script changed, regenerating HTML...");
          server.ws.send({
            type: "full-reload",
            path: "*",
          });
        }
      });
    },
  };
};

const ReactCompilerConfig = {
  target: "19",
};

function getMarimoVersion(): string {
  try {
    return execFileSync("uv", ["run", "marimo", "--version"]).toString().trim();
  } catch {
    return packageJson.version;
  }
}

// https://vitejs.dev/config/
export default defineConfig({
  resolve: {
    tsconfigPaths: true,
    dedupe: ["react", "react-dom", "@emotion/react", "@emotion/cache"],
    alias: [
      // Islands run read-only and never render the slide code editor, so
      // swap `SlideCellView` for a no-op stub. This keeps CodeMirror, the
      // Codeium adapter, and `@bufbuild/protobuf` out of the islands bundle
      // (the latter contains a `process.env.BUF_BIGINT_DISABLE` literal
      // that `islands/validate.sh` otherwise flags).
      {
        find: "@/components/slides/slide-cell-view",
        replacement: path.resolve(
          dirname,
          "../src/core/islands/stubs/slide-cell-view.tsx",
        ),
      },
    ],
  },
  experimental: {
    enableNativePlugin: true,
  },
  worker: {
    format: "es",
  },
  define: {
    "process.env.NODE_ENV": JSON.stringify(process.env.NODE_ENV),
    "process.env.DEBUG": JSON.stringify(process.env.DEBUG ?? ""),
    "process.env.LOG": JSON.stringify(""),
    "process.env.VSCODE_TEXTMATE_DEBUG": JSON.stringify(false),
    "process.env.NODE_DEBUG": JSON.stringify(false),
    // Precedence: VITE_MARIMO_VERSION > uv run marimo --version > package.json
    "import.meta.env.VITE_MARIMO_VERSION": JSON.stringify(
      process.env.VITE_MARIMO_VERSION || getMarimoVersion(),
    ),
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
          ["babel-plugin-react-compiler", ReactCompilerConfig],
        ],
      },
    }),
    wasm(),
    topLevelAwait(),
  ],
  build: {
    emptyOutDir: true,
    lib: {
      entry: path.resolve(dirname, "../src/core/islands/main.ts"),
      formats: ["es"],
    },
    rolldownOptions: {
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
