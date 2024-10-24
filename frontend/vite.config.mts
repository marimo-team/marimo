/* Copyright 2024 Marimo. All rights reserved. */
import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";
import tsconfigPaths from "vite-tsconfig-paths";
import { JSDOM } from "jsdom";

const SERVER_PORT = process.env.SERVER_PORT || 2718;
const HOST = process.env.HOST || "127.0.0.1";
const TARGET = `http://${HOST}:${SERVER_PORT}`;
const isDev = process.env.NODE_ENV === "development";
const isStorybook = process.env.npm_lifecycle_script?.includes("storybook");
const isPyodide = process.env.PYODIDE === "true";

const htmlDevPlugin = (): Plugin => {
  return {
    apply: "serve",
    name: "html-transform",
    transformIndexHtml: async (html, ctx) => {
      if (isStorybook) {
        return html;
      }

      if (isPyodide) {
        const modeFromUrl = ctx.originalUrl?.includes("mode=read")
          ? "read"
          : "edit";
        html = html.replace("{{ base_url }}", "");
        html = html.replace("{{ title }}", "marimo");
        html = html.replace(
          "{{ user_config }}",
          JSON.stringify({
            // Add/remove user config here while developing
            // runtime: {
            //   auto_instantiate: false,
            // },
          }),
        );
        html = html.replace("{{ app_config }}", JSON.stringify({}));
        html = html.replace("{{ server_token }}", "");
        if (process.env.VITE_MARIMO_VERSION) {
          // If VITE_MARIMO_VERSION is defined, pull the local version of marimo
          html = html.replace("{{ version }}", "local");
        } else {
          // Otherwise, pull the latest version of marimo from PyPI
          html = html.replace("{{ version }}", "latest");
        }
        html = html.replace("{{ filename }}", "notebook.py");
        html = html.replace("{{ mode }}", modeFromUrl);
        html = html.replace(/<\/head>/, "<marimo-wasm></marimo-wasm></head>");
        return html;
      }

      // fetch html from server
      const serverHtmlResponse = await fetch(TARGET + ctx.originalUrl);
      const serverHtml = await serverHtmlResponse.text();

      const serverDoc = new JSDOM(serverHtml).window.document;
      const devDoc = new JSDOM(html).window.document;

      // Login page
      if (!serverHtml.includes("marimo-mode") && serverHtml.includes("login")) {
        return `
        <html>
          <body>
          In development mode, please run the server without authentication: <code style="color: red;">marimo edit --no-token</code>
          </body>
        </html>
        `;
      }

      // copies these elements from server to dev
      const copyElements = [
        "base",
        "title",
        "marimo-filename",
        "marimo-version",
        "marimo-mode",
        "marimo-user-config",
        "marimo-app-config",
        "marimo-server-token",
      ];

      // remove from dev
      copyElements.forEach((id) => {
        const element = devDoc.querySelector(id);
        if (!element) {
          console.warn(`Element ${id} not found.`);
          return;
        }
        element.remove();
      });

      // copy from server
      copyElements.forEach((id) => {
        const element = serverDoc.querySelector(id);
        if (!element) {
          console.warn(`Element ${id} not found.`);
          return;
        }
        devDoc.head.append(element);
      });

      return `<!DOCTYPE html>\n${devDoc.documentElement.outerHTML}`;
    },
  };
};

const ReactCompilerConfig = {
  target: "18",
};

// https://vitejs.dev/config/
export default defineConfig({
  // This allows for a dynamic <base> tag in index.html
  base: "./",
  server: {
    host: "localhost",
    port: 3000,
    proxy: {
      "/api": {
        target: TARGET,
        changeOrigin: true,
      },
      "/auth": {
        target: TARGET,
        changeOrigin: true,
      },
      "/@file": {
        target: TARGET,
        changeOrigin: true,
      },
      "/custom.css": {
        target: TARGET,
        changeOrigin: true,
      },
      "/ws": {
        target: `ws://${HOST}:${SERVER_PORT}`,
        ws: true,
        changeOrigin: true,
        headers: {
          origin: TARGET,
        },
      },
      "/terminal/ws": {
        target: `ws://${HOST}:${SERVER_PORT}`,
        ws: true,
        changeOrigin: true,
        headers: {
          origin: TARGET,
        },
      },
    },
    headers: isPyodide
      ? {
          "Cross-Origin-Opener-Policy": "same-origin",
          "Cross-Origin-Embedder-Policy": "require-corp",
        }
      : {},
  },
  define: {
    "import.meta.env.VITE_MARIMO_VERSION": process.env.VITE_MARIMO_VERSION
      ? JSON.stringify(process.env.VITE_MARIMO_VERSION)
      : JSON.stringify("latest"),
  },
  build: {
    minify: isDev ? false : "terser",
    sourcemap: isDev,
  },
  resolve: {
    dedupe: ["react", "react-dom", "@emotion/react", "@emotion/cache"],
  },
  worker: {
    plugins: () => [tsconfigPaths()],
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
});
